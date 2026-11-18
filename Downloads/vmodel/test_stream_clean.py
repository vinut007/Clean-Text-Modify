"""Streaming pipeline tests: parity with the in-memory fast_scan path,
chunked/multi-chunk equivalence, parallel==serial, pattern capping,
decisions (approve/reject), sentence case, and xlsx sheet rollover.
"""
from __future__ import annotations

import sys
import tempfile
from pathlib import Path

sys.path.insert(0, ".")

from backend.core.clean import CleanOptions  # noqa: E402
from backend.core import fast_scan  # noqa: E402
from backend.core import stream_clean as sc  # noqa: E402
from backend.core.annotate import (  # noqa: E402
    _cell_errors,
    _diff_context,
    _esc_display,
    _mark_fixed,
    _sanitize_cell,
    _sentence_case,
)
from backend.core.export import StreamingXlsxWriter  # noqa: E402

COLUMNS = ["Name", "Notes", "Extra"]
SKIP: set[int] = set()

OPTS = CleanOptions(
    fix_mojibake=True,
    fold_accents=True,
    normalize_invisible=True,
    fold_symbols=True,
    collapse_punctuation=True,
    keep_emoji=False,
    fold_scripts=False,
    transliterate_columns=set(),
)

# mixed corpus: low-risk fixes, high-risk extraction failures, protected
# tokens (CJK / URL / pipe), and untouched cells
ROWS = [
    ["Jos\u00c3\u00a9 M\u00c3" + "\u00bcller", "caf\u00e9 r\u00e9sum\u00e9 fast | service", 42],
    ["M\u00fcller GmbH", "hello \U0001f600 world", "plain"],
    ["\u4e2d\u6587 \u5929\u6c17", "visit https://example.com | now", "x"],
    ["<div>bad</div>", "@#$%^", "y"],
    ["wow !!! really", "broken \ufffd here", 7],
    ["normal text", "check example.xyz now", "ok"],
    ["Gr\u00fc\u00dfe", "..edge.. punct..", "n"],
    ["", None, 3.5],
]

fails: list[str] = []


def main():


    def patterns_map(sr):
        out = {}
        for bucket in (sr.low_patterns, sr.medium_patterns, sr.high_patterns):
            for p in bucket:
                out[(p.src, p.dst, p.category)] = (
                    p.risk, p.total_count, p.reason,
                    (p.changes[0].row_index, p.changes[0].col_index,
                     p.changes[0].original, p.changes[0].cleaned)
                    if p.changes else None,
                )
        return out


    def approve_all(sr):
        for bucket in (sr.low_patterns, sr.medium_patterns, sr.high_patterns):
            for p in bucket:
                p.user_decision = "approve"
        return sr


    def ref_build(rows, scan_result, columns, skip, opts, extra_cols, sentence_case):
        """Standalone copy of the CLI's in-memory apply/build block — the oracle
        the streaming path must match byte-for-byte."""
        cleaned_rows, changed, err_rows = fast_scan.apply_decisions(rows, scan_result)
        original_rows = [list(r) for r in rows]

        high_risk_rows: set[int] = set()
        if 2 in extra_cols:
            for pattern in scan_result.high_patterns:
                for change in pattern.changes:
                    high_risk_rows.add(change.row_index)

        if 1 in extra_cols:
            for ridx, row in enumerate(cleaned_rows):
                err_parts = []
                orig_row = original_rows[ridx] if ridx < len(original_rows) else []
                reported: set[int] = set()
                for cidx, col in enumerate(columns):
                    if cidx >= len(row) or (cidx + 1) in skip:
                        continue
                    vo = orig_row[cidx] if cidx < len(orig_row) else row[cidx]
                    if not isinstance(vo, str) or not vo:
                        continue
                    v = row[cidx]
                    errs = _cell_errors(vo, col, opts)
                    if errs:
                        errs = _mark_fixed(errs, vo, v if isinstance(v, str) else "")
                        err_parts.append(f"[{col}] " + _esc_display(", ".join(errs)))
                        reported.add(cidx)
                for cidx, col in enumerate(columns):
                    if cidx in reported or cidx >= len(row):
                        continue
                    orig = orig_row[cidx] if cidx < len(orig_row) else row[cidx]
                    cleaned = row[cidx]
                    if isinstance(orig, str) and orig and orig != cleaned:
                        o_s = orig if len(orig) <= 40 else orig[:37] + "..."
                        n_s = cleaned if len(cleaned) <= 40 else cleaned[:37] + "..."
                        err_parts.append(f"[{col}] {_esc_display(o_s)} \u2192 {_esc_display(n_s)}")
                row.append("; ".join(err_parts))
        else:
            for row in cleaned_rows:
                row.append("")

        sentence_cells = 0
        if sentence_case:
            for row in cleaned_rows:
                for cidx in range(min(len(columns), len(row))):
                    if (cidx + 1) in skip:
                        continue
                    v = row[cidx]
                    if isinstance(v, str) and v:
                        nv = _sentence_case(v)
                        if nv != v:
                            sentence_cells += 1
                        row[cidx] = nv

        for row in cleaned_rows:
            for cidx in range(len(row)):
                row[cidx] = _sanitize_cell(row[cidx])

        out_rows = []
        for ridx, row in enumerate(cleaned_rows):
            out_row = []
            for cidx in range(len(columns)):
                out_row.append(row[cidx] if cidx < len(row) else "")
            if 1 in extra_cols:
                err_cell = row[-1] if row and len(row) > len(columns) else ""
                out_row.append(err_cell if isinstance(err_cell, str) else "")
            if 2 in extra_cols:
                out_row.append("yes" if ridx in high_risk_rows else "no")
            if 3 in extra_cols:
                ba = []
                for cidx, col in enumerate(columns):
                    if cidx < len(original_rows[ridx]) and cidx < len(row):
                        orig = original_rows[ridx][cidx]
                        cleaned_val = row[cidx]
                        if isinstance(orig, str) and orig and orig != cleaned_val:
                            ba.append(f"{col}: {_diff_context(orig, cleaned_val)}")
                out_row.append("; ".join(ba))
            out_rows.append(out_row)

        for row in out_rows:
            for i in range(len(row)):
                row[i] = _sanitize_cell(row[i])

        return out_rows, changed, err_rows, sentence_cells


    class ListWriter:
        def __init__(self):
            self.rows: list = []

        def add_row(self, row):
            self.rows.append(list(row))

        def close(self):
            pass


    def check(label, cond, detail=""):
        if cond:
            print(f"  OK  {label}")
        else:
            fails.append(f"{label}: {detail}")
            print(f"FAIL  {label}: {detail}")


    # ---------------------------------------------------------------------------
    # 1. scan parity: in-memory vs streamed (serial), single + multi chunk
    # ---------------------------------------------------------------------------
    print("== scan parity (serial) ==")
    ref = fast_scan.scan_all_cells(COLUMNS, ROWS, SKIP, OPTS)
    got1 = sc.scan_stream([ROWS], COLUMNS, SKIP, OPTS, len(ROWS))
    got2 = sc.scan_stream([ROWS[:3], ROWS[3:]], COLUMNS, SKIP, OPTS, len(ROWS))

    for label, got in (("single-chunk", got1), ("multi-chunk", got2)):
        check(f"{label} total_rows", got.total_rows == ref.total_rows,
              f"{got.total_rows} != {ref.total_rows}")
        check(f"{label} changed_cells", got.changed_cells == ref.changed_cells,
              f"{got.changed_cells} != {ref.changed_cells}")
        check(f"{label} rows_with_errors", got.rows_with_errors == ref.rows_with_errors,
              f"{got.rows_with_errors} != {ref.rows_with_errors}")
        rp, gp = patterns_map(ref), patterns_map(got)
        check(f"{label} pattern keys", set(rp) == set(gp),
              f"only-ref={set(rp) - set(gp)} only-got={set(gp) - set(rp)}")
        for k in set(rp) & set(gp):
            r_risk, r_cnt, r_reason, r_ex = rp[k]
            g_risk, g_cnt, g_reason, g_ex = gp[k]
            if (r_risk, r_cnt, r_reason) != (g_risk, g_cnt, g_reason):
                fails.append(f"{label} pattern {k!r}: {(r_risk, r_cnt, r_reason)} != "
                             f"{(g_risk, g_cnt, g_reason)}")
            if r_ex != g_ex:
                fails.append(f"{label} example {k!r}: {r_ex} != {g_ex}")

    # ---------------------------------------------------------------------------
    # 2. scan parity via the parallel pool
    # ---------------------------------------------------------------------------
    print("== scan parity (parallel pool) ==")
    pool = sc.make_scan_pool(OPTS, COLUMNS, SKIP)
    try:
        gotp = sc.scan_stream([ROWS], COLUMNS, SKIP, OPTS, len(ROWS), pool=pool)
    finally:
        sc.shutdown_pool(pool)
    check("parallel==serial patterns", patterns_map(ref) == patterns_map(gotp),
          "pattern maps differ")
    check("parallel==serial counts",
          (gotp.changed_cells, gotp.rows_with_errors)
          == (ref.changed_cells, ref.rows_with_errors))
    check("pool was actually used", pool is not None, "make_scan_pool returned None")

    # ---------------------------------------------------------------------------
    # 3. apply parity: approve-all, with and without sentence case
    # ---------------------------------------------------------------------------
    print("== apply parity (approve-all) ==")
    EXTRA = {1, 2, 3}
    for sentence in (False, True):
        ref_scan = approve_all(fast_scan.scan_all_cells(COLUMNS, ROWS, SKIP, OPTS))
        ref_rows, ref_changed, ref_err, ref_sent = ref_build(
            ROWS, ref_scan, COLUMNS, SKIP, OPTS, EXTRA, sentence)

        decisions = sc.build_decisions(ref_scan)
        high_srcs = sc.build_high_srcs(ref_scan)
        w = ListWriter()
        ch, nrows, sent = sc.apply_stream(
            [ROWS], COLUMNS, SKIP, OPTS, decisions, high_srcs, EXTRA, sentence,
            len(ROWS), w,
        )
        check(f"sentence={sentence} row count", nrows == len(ref_rows),
              f"{nrows} != {len(ref_rows)}")
        check(f"sentence={sentence} changed cells", ch == ref_changed,
              f"{ch} != {ref_changed}")
        check(f"sentence={sentence} sentence cells", sent == ref_sent,
              f"{sent} != {ref_sent}")
        if len(w.rows) == len(ref_rows):
            diffs = [i for i, (a, b) in enumerate(zip(w.rows, ref_rows)) if a != b]
            check(f"sentence={sentence} rows byte-equal", not diffs, f"rows {diffs}")
            if diffs:
                i = diffs[0]
                print("    stream:", w.rows[i])
                print("    ref   :", ref_rows[i])

    # ---------------------------------------------------------------------------
    # 4. apply parity with a REJECTED high pattern (kept original, not counted)
    # ---------------------------------------------------------------------------
    print("== apply parity (reject high) ==")
    ref_scan = fast_scan.scan_all_cells(COLUMNS, ROWS, SKIP, OPTS)
    approve_all(ref_scan)
    if ref_scan.high_patterns:
        ref_scan.high_patterns[0].user_decision = "reject"
    ref_rows, ref_changed, ref_err, _ = ref_build(
        ROWS, ref_scan, COLUMNS, SKIP, OPTS, EXTRA, False)
    decisions = sc.build_decisions(ref_scan)
    high_srcs = sc.build_high_srcs(ref_scan)
    w = ListWriter()
    ch, nrows, _ = sc.apply_stream(
        [ROWS], COLUMNS, SKIP, OPTS, decisions, high_srcs, EXTRA, False, len(ROWS), w)
    diffs = [i for i, (a, b) in enumerate(zip(w.rows, ref_rows)) if a != b]
    check("reject rows byte-equal", not diffs, f"rows {diffs}")
    check("reject changed cells", ch == ref_changed, f"{ch} != {ref_changed}")
    if ch != ref_changed or diffs:
        print("    high patterns:", [(p.src, p.user_decision) for p in ref_scan.high_patterns])

    # ---------------------------------------------------------------------------
    # 5. parallel apply == serial apply
    # ---------------------------------------------------------------------------
    print("== apply parity (parallel pool) ==")
    ref_scan2 = approve_all(fast_scan.scan_all_cells(COLUMNS, ROWS, SKIP, OPTS))
    dec = sc.build_decisions(ref_scan2)
    hs = sc.build_high_srcs(ref_scan2)
    w_ser = ListWriter()
    sc.apply_stream([ROWS], COLUMNS, SKIP, OPTS, dec, hs, EXTRA, True, len(ROWS), w_ser)
    pool2 = sc.make_apply_pool(OPTS, COLUMNS, SKIP, dec, hs, EXTRA, True)
    try:
        w_par = ListWriter()
        sc.apply_stream([ROWS], COLUMNS, SKIP, OPTS, dec, hs, EXTRA, True, len(ROWS),
                        w_par, pool=pool2)
    finally:
        sc.shutdown_pool(pool2)
    check("parallel==serial output rows", w_ser.rows == w_par.rows, "rows differ")
    check("apply pool was actually used", pool2 is not None,
          "make_apply_pool returned None")

    # ---------------------------------------------------------------------------
    # 6. pattern capping: total_count exact, changes capped
    # ---------------------------------------------------------------------------
    print("== pattern capping ==")
    rep = [["caf\u00c3\u00a9 x", "note", 1]] * 120
    cap_scan = sc.scan_stream([rep], COLUMNS, SKIP, OPTS, len(rep))
    for p in (cap_scan.low_patterns + cap_scan.high_patterns):
        if p.category == "mojibake" or p.dst != p.src:
            check("total_count exact", p.total_count == 120,
                  f"{p.total_count} != 120")
            check("changes capped", len(p.changes) <= sc.MAX_CHANGES_PER_PATTERN,
                  str(len(p.changes)))
            break
    else:
        fails.append("capping: no changed pattern found in repeated corpus")

    # ---------------------------------------------------------------------------
    # 7. StreamingXlsxWriter sheet rollover
    # ---------------------------------------------------------------------------
    print("== xlsx sheet rollover ==")
    tmp = Path(tempfile.gettempdir()) / "vmodel_stream_rollover.xlsx"
    if tmp.exists():
        tmp.unlink()
    cols = ["a", "b"]
    wr = StreamingXlsxWriter(tmp, cols, max_rows_per_sheet=100)
    for i in range(250):
        wr.add_row([i, f"row {i}"])
    wr.close()
    check("file written", tmp.exists())

    from openpyxl import load_workbook  # noqa: E402
    wb = load_workbook(str(tmp), read_only=True)
    names = wb.sheetnames
    total_data = 0
    headers_ok = True
    for name in names:
        ws = wb[name]
        rows_all = list(ws.iter_rows(values_only=True))
        if not rows_all or list(rows_all[0]) != cols:
            headers_ok = False
        total_data += max(0, len(rows_all) - 1)
    wb.close()
    check("3 sheets (100+100+50)", len(names) == 3, str(names))
    check("header on every sheet", headers_ok)
    check("250 data rows total", total_data == 250, str(total_data))
    tmp.unlink(missing_ok=True)

    # ---------------------------------------------------------------------------
    # 8. XML-safe sanitize (crash regression: openpyxl raised
    #    "All strings must be XML compatible" at 87% of a 10M-row apply)
    # ---------------------------------------------------------------------------
    print("== XML-safe sanitize ==")
    # lxml accepts C1 (0x80-0x9F) per XML 1.0; it rejects C0 controls
    # (except tab/LF/CR), lone surrogates, and U+FFFE/U+FFFF — strip those.
    dirty = "ab\x07c\x00d\x80e\x1b[31mf\tg\nh\ud800i\ufffe"
    clean_v = _sanitize_cell(dirty)
    check("C0 controls/ANSI/surrogates/FFFE stripped",
          clean_v == "abcd\x80ef\tg\nhi", repr(clean_v))
    check("tab + LF kept", "\t" in clean_v and "\n" in clean_v)
    check("non-str passthrough", _sanitize_cell(42) == 42)

    # ---------------------------------------------------------------------------
    # 9. writer write-boundary gate: raw control chars never reach lxml
    # ---------------------------------------------------------------------------
    print("== writer control-char gate ==")
    tmp2 = Path(tempfile.gettempdir()) / "vmodel_stream_ctrl.xlsx"
    tmp2.unlink(missing_ok=True)
    wr = StreamingXlsxWriter(tmp2, ["a", "b"])
    wr.add_row(["ok\x07row", "bad\x00\x01cell"])
    wr.add_row(["clean", "caf\u00e9"])
    wr.close()
    allr: list = []
    ok_w = tmp2.exists()
    if ok_w:
        wb2 = load_workbook(str(tmp2), read_only=True, data_only=True)
        ws2 = wb2[wb2.sheetnames[0]]
        allr = list(ws2.iter_rows(values_only=True))
        wb2.close()
        ok_w = (len(allr) == 3 and allr[1] == ("okrow", "badcell")
                and allr[2] == ("clean", "caf\u00e9"))
    check("control chars scrubbed, file opens", ok_w, str(allr))
    tmp2.unlink(missing_ok=True)

    # ---------------------------------------------------------------------------
    # 10. control-char corpus end to end: scan + apply parity vs in-memory,
    #     with zero XML-illegal characters left anywhere in the output
    # ---------------------------------------------------------------------------
    print("== control-char data parity ==")
    dirty_rows = [
        ["bad\x07char caf\u00e9", "note\x01\x02x", 1],
        ["clean name", "caf\u00e9 r\u00e9sum\u00e9", 2],
        ["\ufffd here", "tab\tsep", 3],
    ]
    ref_d = fast_scan.scan_all_cells(COLUMNS, dirty_rows, SKIP, OPTS)
    got_d = sc.scan_stream([dirty_rows], COLUMNS, SKIP, OPTS, len(dirty_rows))
    check("dirty scan parity",
          patterns_map(ref_d) == patterns_map(got_d)
          and (ref_d.changed_cells, ref_d.rows_with_errors)
          == (got_d.changed_cells, got_d.rows_with_errors),
          f"changed {got_d.changed_cells}/{ref_d.changed_cells} "
          f"errors {got_d.rows_with_errors}/{ref_d.rows_with_errors}")
    approve_all(ref_d)
    dec_d = sc.build_decisions(ref_d)
    hs_d = sc.build_high_srcs(ref_d)
    ref_rows_d, ref_ch_d, _, _ = ref_build(
        dirty_rows, ref_d, COLUMNS, SKIP, OPTS, EXTRA, False)
    w_d = ListWriter()
    ch_d, nrows_d, _ = sc.apply_stream(
        [dirty_rows], COLUMNS, SKIP, OPTS, dec_d, hs_d, EXTRA, False,
        len(dirty_rows), w_d)
    diffs_d = [i for i, (a, b) in enumerate(zip(w_d.rows, ref_rows_d))
               if a != b]
    check("dirty apply parity",
          not diffs_d and ch_d == ref_ch_d and nrows_d == len(dirty_rows),
          f"rows={diffs_d} ch={ch_d}!={ref_ch_d}")
    if diffs_d:
        i = diffs_d[0]
        print("    stream:", w_d.rows[i])
        print("    ref   :", ref_rows_d[i])
    bad: list = []
    for row in w_d.rows:
        for v in row:
            if isinstance(v, str):
                for ch in v:
                    o = ord(ch)
                    if ((o < 0x20 and ch not in "\t\n\r")
                            or 0x80 <= o <= 0x9F
                            or 0xD800 <= o <= 0xDFFF
                            or o in (0xFFFE, 0xFFFF)):
                        bad.append(ch)
    check("no XML-illegal chars in output rows", not bad, repr(bad[:10]))

    # ---------------------------------------------------------------------------
    # 11. sparse decisions (worker-init must stay tiny on 10M-row tables:
    #     one full entry per pattern meant ~1GB pickled into EVERY worker)
    # ---------------------------------------------------------------------------
    print("== sparse decisions ==")
    ref_s = approve_all(fast_scan.scan_all_cells(COLUMNS, ROWS, SKIP, OPTS))
    dec_s = sc.build_decisions(ref_s)
    low_med_keys = ({(p.src, p.dst) for p in ref_s.low_patterns}
                    | {(p.src, p.dst) for p in ref_s.medium_patterns})
    overlap = set(dec_s) & low_med_keys
    check("low/med approved omitted", not overlap, repr(list(overlap)[:3]))
    hr_bad = [(p.src, p.dst) for p in ref_s.high_patterns
              if p.src != p.dst and p.user_decision == "approve"
              and not p.user_dst and (p.src, p.dst) in dec_s]
    check("approved plain rewrites omitted", not hr_bad, repr(hr_bad[:3]))
    ext_missing = [(p.src, p.dst) for p in ref_s.high_patterns
                   if p.src == p.dst and p.user_decision == "approve"
                   and (p.src, p.dst) not in dec_s]
    check("extract approvals present", not ext_missing, repr(ext_missing[:3]))
    rewr = next((p for p in ref_s.high_patterns if p.src != p.dst), None)
    if rewr is not None:
        rewr.user_decision = "reject"
        dec_r = sc.build_decisions(ref_s)
        k = (rewr.src, rewr.dst)
        check("rejected rewrite stored as None",
              k in dec_r and dec_r[k] is None, repr(dec_r.get(k)))
        rewr.user_decision = "approve"
    else:
        check("rejected rewrite stored as None", True, "no rewrite high (n/a)")
    check("decisions not bigger than high bucket",
          len(dec_s) <= len(ref_s.high_patterns),
          f"{len(dec_s)} > {len(ref_s.high_patterns)}")

    # ---------------------------------------------------------------------------
    print()
    if fails:
        print("RESULT: FAIL")
        for f in fails:
            print("  -", f)
        sys.exit(1)
    print("RESULT: PASS — streaming parity, pooling, capping, rollover, "
          "XML-safety, sparse decisions")



if __name__ == "__main__":
    main()
