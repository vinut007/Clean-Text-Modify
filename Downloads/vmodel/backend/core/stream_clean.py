"""Streaming, memory-bounded scan + apply for very large tables (10M+ rows).

Two passes over the data, both chunked so RAM stays flat:

  pass 1  scan_stream()   — clean-classify every cell, aggregate into the
                            same ScanResult/UniquePattern objects the
                            interactive review UI already consumes.
                            Per-pattern change lists are capped at
                            MAX_CHANGES_PER_PATTERN examples (the review
                            only ever displays examples; total_count keeps
                            the full count), so 10M changed cells do not
                            materialize 10M CellChange objects.

  pass 2  apply_stream()  — re-clean each cell, look up the reviewed
                            decision for its (original, cleaned) pair, and
                            hand the finished output row to a writer
                            (StreamingXlsxWriter) as it goes.

Both passes optionally run row tasks on a ProcessPoolExecutor (spawn-safe:
workers import only this module + backend.core.*, never the CLI).

Parity with fast_scan.scan_all_cells / apply_decisions is guaranteed by
reusing the same classification primitives (_primary_category,
_is_edge_punct_only, _HIGH_PRIMARY, _LOW_CATS) and the same cell cache
semantics (keyed by cell value, exactly like scan_all_cells).
"""
from __future__ import annotations

import os

from backend.core.clean import clean_cell
from backend.core.detect import analyze_text
from backend.core.fast_scan import (
    CellChange,
    ScanResult,
    UniquePattern,
    _HIGH_PRIMARY,
    _LOW_CATS,
    _is_edge_punct_only,
    _primary_category,
)
from backend.core.annotate import (
    _cell_errors,
    _diff_context,
    _esc_display,
    _mark_fixed,
    _sanitize_cell,
    _sentence_case,
)

CHUNK_ROWS = 50_000
MAX_CHANGES_PER_PATTERN = 50
_CACHE_LIMIT = 200_000
_CELL_ERR_CACHE_LIMIT = 50_000
_TASK_CHUNKSIZE = 64

# Per-process worker context (set by pool initializer, or passed explicitly
# in the serial fallback). _CACHE mirrors scan_all_cells' value-keyed cache.
_CTX: dict = {}
_CACHE: dict = {}
_E_CACHE: dict = {}   # (value, column) -> _cell_errors result (apply pass B)
_X_CACHE: dict = {}   # value -> extract-category decision (scan, incl. none)
_MISS = object()


# ---------------------------------------------------------------------------
# row-level scan (one record per changed / extract-error cell)
# ---------------------------------------------------------------------------

def scan_one_row(row, columns, skip_cols, opts, cache):
    """Classify every cell of one row.

    Returns (records, row_has_error); a record is
    (cidx, original, cleaned, category, risk). Logic mirrors
    fast_scan.scan_all_cells cell-for-cell so both paths agree.
    """
    records = []
    row_has_error = False
    for cidx, col in enumerate(columns):
        if cidx >= len(row) or (cidx + 1) in skip_cols:
            continue
        v = row[cidx]
        if not isinstance(v, str) or not v:
            continue

        outcome = cache.get(v)
        if outcome is None:
            outcome = clean_cell(v, opts, col)
            if len(cache) >= _CACHE_LIMIT:
                cache.clear()
            cache[v] = outcome

        if not outcome.changed:
            # Extraction errors that cleaning did not rewrite still need
            # human review (garbage, HTML, symbol noise, ...). Decision
            # cached per value: analysis is pure in (v) for this fallback.
            extract_cat = _X_CACHE.get(v, _MISS)
            if extract_cat is _MISS:
                extract_cat = next(
                    (cc for cc in _HIGH_PRIMARY if outcome.counts.get(cc)),
                    None,
                )
                if extract_cat is None:
                    orig_counts = analyze_text(v, apply_accents=False).counts
                    extract_cat = next(
                        (cc for cc in _HIGH_PRIMARY if orig_counts.get(cc)),
                        None,
                    )
                if len(_X_CACHE) >= _CELL_ERR_CACHE_LIMIT:
                    _X_CACHE.clear()
                _X_CACHE[v] = extract_cat or 0
                extract_cat = extract_cat or None
            elif extract_cat == 0:
                extract_cat = None
            if extract_cat:
                records.append((cidx, v, v, extract_cat, "high"))
                row_has_error = True
            continue

        row_has_error = True
        primary = _primary_category(outcome.counts, v, outcome.cleaned)
        if primary in ("repeated_punct", "symbol_noise") and _is_edge_punct_only(
            v, outcome.cleaned
        ):
            primary = "punctuation"
        risk = "low" if primary in _LOW_CATS else "high"
        records.append((cidx, v, outcome.cleaned, primary, risk))
    return records, row_has_error


# ---------------------------------------------------------------------------
# row-level apply: decisions + annotation + sentence case + extras
# ---------------------------------------------------------------------------

def apply_one_row(
    row,
    columns,
    skip_cols,
    opts,
    decisions,
    high_srcs,
    extra_cols,
    sentence_case,
    cache,
):
    """Build one finished output row.

    decisions: {(original, cleaned): final_value_or_None}  (None = rejected)
    high_srcs: {original of every high-risk pattern} -> "yes" flag in extra col 2

    Returns (out_row, changed_count, sentence_count) — counts match
    fast_scan.apply_decisions semantics (approved extract patterns count
    as a changed cell even though the value is unchanged).
    """
    finals: dict[int, str] = {}
    changed = 0

    # pass A — decide the final value of every cleanable cell
    for cidx, col in enumerate(columns):
        if cidx >= len(row) or (cidx + 1) in skip_cols:
            continue
        v = row[cidx]
        if not isinstance(v, str) or not v:
            continue
        outcome = cache.get(v)
        if outcome is None:
            outcome = clean_cell(v, opts, col)
            if len(cache) >= _CACHE_LIMIT:
                cache.clear()
            cache[v] = outcome
        if outcome.changed:
            key = (v, outcome.cleaned)
            if key in decisions:
                d = decisions[key]
                if d is None:
                    final = v          # rejected / skipped — keep original
                else:
                    final = d
                    changed += 1       # approved write counts (per pattern)
            else:
                final = outcome.cleaned  # unseen pair: default approve
                changed += 1
        else:
            # extract-error patterns have src == dst: approve writes dst
            # (== v) or the user's override, and still counts as a changed
            # cell — exactly like apply_decisions
            d = decisions.get((v, v))
            if d is not None:
                changed += 1
                final = d
            else:
                final = v
        finals[cidx] = final

    # pass B — error/change annotation (values BEFORE sentence case)
    ann_parts: list[str] = []
    if 1 in extra_cols:
        reported: set[int] = set()
        for cidx, col in enumerate(columns):
            if cidx >= len(row) or (cidx + 1) in skip_cols:
                continue
            vo = row[cidx]
            if not isinstance(vo, str) or not vo:
                continue
            v = finals.get(cidx, vo)
            errs = _cell_errors_cached(vo, col, opts)
            if errs:
                errs = _mark_fixed(errs, vo, v)
                ann_parts.append(f"[{col}] " + _esc_display(", ".join(errs)))
                reported.add(cidx)
        for cidx, col in enumerate(columns):
            if cidx in reported or cidx >= len(row):
                continue
            orig = row[cidx]
            cleaned = finals.get(cidx)
            if isinstance(orig, str) and orig and cleaned is not None and orig != cleaned:
                orig_short = orig if len(orig) <= 40 else orig[:37] + "..."
                new_short = cleaned if len(cleaned) <= 40 else cleaned[:37] + "..."
                ann_parts.append(f"[{col}] {_esc_display(orig_short)} \u2192 {_esc_display(new_short)}")

    # pass C — sentence case on value cells only (annotation keeps cleaning-only)
    sentence_count = 0
    if sentence_case:
        for cidx, val in finals.items():
            if isinstance(val, str) and val:
                nv = _sentence_case(val)
                if nv != val:
                    sentence_count += 1
                finals[cidx] = nv

    # pass D — assemble output row + extra columns, sanitized for export
    out_row: list = []
    for cidx in range(len(columns)):
        if cidx in finals:
            val = finals[cidx]
        elif cidx < len(row):
            val = row[cidx]          # skipped / non-str / empty -> original
        else:
            val = ""
        out_row.append(_sanitize_cell(val))

    high = False
    if high_srcs:
        for cidx in range(min(len(row), len(columns))):
            if (cidx + 1) in skip_cols:
                continue
            v = row[cidx]
            if isinstance(v, str) and v and v in high_srcs:
                high = True
                break

    if 1 in extra_cols:
        out_row.append(_sanitize_cell("; ".join(ann_parts)))
    if 2 in extra_cols:
        out_row.append("yes" if high else "no")
    if 3 in extra_cols:
        ba_parts: list[str] = []
        for cidx, col in enumerate(columns):
            if cidx < len(row):
                orig = row[cidx]
                cleaned_val = out_row[cidx] if cidx < len(out_row) else ""
                if isinstance(orig, str) and orig and orig != cleaned_val:
                    ba_parts.append(f"{col}: {_diff_context(orig, cleaned_val)}")
        out_row.append(_sanitize_cell("; ".join(ba_parts)))

    return out_row, changed, sentence_count


# ---------------------------------------------------------------------------
# value-keyed caches (pure in (value[, column]) — same results every call)
# ---------------------------------------------------------------------------

def _cell_errors_cached(v: str, col: str, opts) -> list[str]:
    key = (v, col)
    res = _E_CACHE.get(key, _MISS)
    if res is _MISS:
        res = _cell_errors(v, col, opts)
        if len(_E_CACHE) >= _CELL_ERR_CACHE_LIMIT:
            _E_CACHE.clear()
        _E_CACHE[key] = res
    return res


# ---------------------------------------------------------------------------
# pool plumbing (spawn-safe: initializer args only, no CLI imports)
# ---------------------------------------------------------------------------

def _init_scan_worker(opts, columns, skip_cols):
    _CTX.clear()
    _CTX.update(opts=opts, columns=columns, skip=skip_cols)
    _CACHE.clear()
    _X_CACHE.clear()
    _E_CACHE.clear()


def _init_apply_worker(opts, columns, skip_cols, decisions, high_srcs,
                       extra_cols, sentence_case):
    _CTX.clear()
    _CTX.update(
        opts=opts, columns=columns, skip=skip_cols, decisions=decisions,
        high_srcs=high_srcs, extra_cols=extra_cols,
        sentence_case=sentence_case,
    )
    _CACHE.clear()
    _X_CACHE.clear()
    _E_CACHE.clear()


def _scan_task(row):
    return scan_one_row(row, _CTX["columns"], _CTX["skip"], _CTX["opts"], _CACHE)


def _apply_task(row):
    return apply_one_row(
        row, _CTX["columns"], _CTX["skip"], _CTX["opts"], _CTX["decisions"],
        _CTX["high_srcs"], _CTX["extra_cols"], _CTX["sentence_case"], _CACHE,
    )


def _make_pool(initializer, initargs):
    """Spawn-based process pool, or None (serial) on request/failure."""
    if os.environ.get("VMODEL_SERIAL"):
        return None
    try:
        from concurrent.futures import ProcessPoolExecutor
        import multiprocessing as mp

        n = max(1, (os.cpu_count() or 4) - 1)   # leave a core for the UI
        return ProcessPoolExecutor(
            max_workers=n,
            mp_context=mp.get_context("spawn"),
            initializer=initializer,
            initargs=initargs,
        )
    except Exception:
        return None


def make_scan_pool(opts, columns, skip_cols):
    return _make_pool(_init_scan_worker, (opts, columns, skip_cols))


def make_apply_pool(opts, columns, skip_cols, decisions, high_srcs,
                    extra_cols, sentence_case):
    return _make_pool(
        _init_apply_worker,
        (opts, columns, skip_cols, decisions, high_srcs, extra_cols,
         sentence_case),
    )


def shutdown_pool(pool) -> None:
    if pool is not None:
        try:
            pool.shutdown(wait=True, cancel_futures=True)
        except TypeError:
            pool.shutdown(wait=True)


# ---------------------------------------------------------------------------
# pass 1 — streamed scan
# ---------------------------------------------------------------------------

def scan_stream(row_chunks, columns, skip_cols, opts, total_rows,
                progress=None, pool=None) -> ScanResult:
    """Scan every row-chunk into a ScanResult without holding the table.

    row_chunks: iterable of lists-of-rows (e.g. ingest.iter_access_rows).
    Aggregation is single-dict: key -> [exact_count, example_changes].
    Low/medium patterns keep only their FIRST example (the review UI only
    ever prints counts for them; high patterns keep up to
    MAX_CHANGES_PER_PATTERN examples for the per-pattern display). The
    example is always the first occurrence, identical to what
    scan_all_cells' changes[0] shows.
    """
    result = ScanResult(total_rows=total_rows, total_cols=len(columns))
    agg: dict = {}   # (src, dst, cat) -> [count, [CellChange, ...]]
    serial_cache: dict = {}
    offset = 0

    for rows in row_chunks:
        if pool is not None:
            results = pool.map(_scan_task, rows, chunksize=_TASK_CHUNKSIZE)
        else:
            results = (
                scan_one_row(r, columns, skip_cols, opts, serial_cache)
                for r in rows
            )
        for local, (records, has_err) in enumerate(results):
            if has_err:
                result.rows_with_errors += 1
            ridx = offset + local
            for (cidx, orig, cleaned, cat, risk) in records:
                result.changed_cells += 1
                key = (orig, cleaned, cat)
                ent = agg.get(key)
                if ent is None:
                    agg[key] = [1, [CellChange(
                        ridx, cidx, columns[cidx], orig, cleaned, cat, risk,
                    )]]
                else:
                    ent[0] += 1
                    cap = MAX_CHANGES_PER_PATTERN if risk == "high" else 1
                    if len(ent[1]) < cap:
                        ent[1].append(CellChange(
                            ridx, cidx, columns[cidx], orig, cleaned, cat, risk,
                        ))
            if progress:
                progress(offset + local + 1)
        offset += len(rows)

    # build patterns in first-seen order (dicts preserve it), same shapes
    # the interactive review / AI pre-filter already expect
    for key, (cnt, ex) in agg.items():
        src, dst, cat = key
        risk = ex[0].risk
        pattern = UniquePattern(
            src=src, dst=dst, category=cat, risk=risk,
            total_count=cnt,
            reason=f"{cat} → ASCII ({cnt} cell(s))",
            changes=ex,
        )
        if risk == "low":
            result.low_patterns.append(pattern)
        elif risk == "medium":
            result.medium_patterns.append(pattern)
        else:
            result.high_patterns.append(pattern)
    return result


# ---------------------------------------------------------------------------
# decisions built from the reviewed ScanResult (shared by both paths)
# ---------------------------------------------------------------------------

def build_decisions(scan_result) -> dict:
    """Sparse {(original, cleaned): final_value_or_None} from user decisions.

    Only HIGH patterns can deviate from what pass 2 derives by default, so
    the dict stays tiny (thousands of entries even on 10M-row tables — a
    full per-pattern dict would be pickled into every pool worker):

      - approved plain rewrite  -> omitted (apply's default rule writes
                                   outcome.cleaned and counts it)
      - rejected/skip/undecided -> explicit None (keep original, no count)
      - approve with user_dst   -> explicit override value (modify/custom)
      - approved extract (src == dst) -> explicit entry so the unchanged
                                   cell still counts as a changed cell

    Low/medium patterns are always auto-approved by the CLI right before
    this runs, and their src != dst, so they need no entries. Absent pairs
    in pass 2 behave exactly like apply_decisions skipping a pattern.
    """
    decisions: dict = {}
    for p in scan_result.high_patterns:
        if p.src == p.dst:                      # extract pattern
            if p.user_decision == "approve":
                decisions[(p.src, p.dst)] = p.user_dst if p.user_dst else p.dst
        elif p.user_decision == "approve":
            if p.user_dst:                      # modify / custom override
                decisions[(p.src, p.dst)] = p.user_dst
            # else: plain approve = pass 2's default -> omit
        else:                                   # reject / skip / undecided
            decisions[(p.src, p.dst)] = None
    return decisions


def build_high_srcs(scan_result) -> set:
    """Originals of every high-risk pattern -> row flag for extra col 2."""
    return {p.src for p in scan_result.high_patterns}


# ---------------------------------------------------------------------------
# pass 2 — streamed apply + write
# ---------------------------------------------------------------------------

def apply_stream(row_chunks, columns, skip_cols, opts, decisions, high_srcs,
                 extra_cols, sentence_case, total_rows, writer,
                 progress=None, pool=None):
    """Apply reviewed decisions row-by-row, writing each finished row.

    Returns (changed_cells, rows_written, sentence_cells).
    """
    changed_cells = 0
    sentence_cells = 0
    rows_written = 0
    serial_cache: dict = {}
    offset = 0

    for rows in row_chunks:
        if pool is not None:
            results = pool.map(_apply_task, rows, chunksize=_TASK_CHUNKSIZE)
        else:
            results = (
                apply_one_row(
                    r, columns, skip_cols, opts, decisions, high_srcs,
                    extra_cols, sentence_case, serial_cache,
                )
                for r in rows
            )
        for local, (out_row, ch, sc) in enumerate(results):
            writer.add_row(out_row)
            changed_cells += ch
            sentence_cells += sc
            rows_written += 1
            if progress:
                progress(offset + local + 1)
        offset += len(rows)

    return changed_cells, rows_written, sentence_cells
