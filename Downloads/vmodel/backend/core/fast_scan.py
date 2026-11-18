"""Fast scanning: detect cleaning patterns across all cells, group by risk."""
from __future__ import annotations

import unicodedata
from collections import Counter
from dataclasses import dataclass, field

from backend.core.clean import clean_cell, CleanOptions
from backend.core.detect import classify_nonascii


@dataclass(slots=True)
class CellChange:
    row_index: int
    col_index: int
    column: str
    original: str
    cleaned: str
    category: str
    risk: str


@dataclass(slots=True)
class UniquePattern:
    src: str
    dst: str
    category: str
    risk: str
    total_count: int
    reason: str
    changes: list[CellChange] = field(default_factory=list)
    user_decision: str | None = None
    user_dst: str | None = None
    cell_overrides: dict = field(default_factory=dict)


@dataclass(slots=True)
class ScanResult:
    total_rows: int
    total_cols: int
    changed_cells: int = 0
    rows_with_errors: int = 0
    low_patterns: list[UniquePattern] = field(default_factory=list)
    medium_patterns: list[UniquePattern] = field(default_factory=list)
    high_patterns: list[UniquePattern] = field(default_factory=list)
    all_changes: list[CellChange] = field(default_factory=list)


def _infer_category(original: str, cleaned: str) -> str:
    """Infer primary category from chars removed/changed when counts are empty.

    Folding that runs before analyze (dashes, ellipsis, mojibake repair) can
    leave outcome.counts empty even though the cell changed — classify those
    diffs so symbol/punctuation/accent still land in the low-risk auto-approve
    buckets instead of falling through as 'other' -> high.
    """
    oc, cc = Counter(original), Counter(cleaned)
    cats: Counter = Counter()
    for ch, n in oc.items():
        rem = n - cc.get(ch, 0)
        if rem <= 0 or ord(ch) < 128:
            continue
        if ch == "�":
            cats["replacement"] += rem
        elif 0x0400 <= ord(ch) <= 0x04FF:
            cats["transliterate"] += rem
        elif 0x0370 <= ord(ch) <= 0x03FF:
            cats["transliterate_greek"] += rem
        elif unicodedata.category(ch) == "Mn" or (
            0xC0 <= ord(ch) <= 0x24F and unicodedata.category(ch).startswith("L")
        ):
            cats["accent"] += rem
        else:
            cats[classify_nonascii(ch)] += rem
    if cats:
        # High-risk categories win ties so they still reach human review
        high = [c for c in cats if c not in (
            "emoji", "symbol", "punctuation", "accent", "mojibake",
            "transliterate", "nonascii",
        )]
        if high:
            return max(high, key=lambda c: cats[c])
        return cats.most_common(1)[0][0]
    # ASCII-only change (punct collapse, noise strip, whitespace) -> low
    return "punctuation"


# Categories that must win primary selection when present (human review required)
# cjk_punct_repeat before symbol_noise: folding fullwidth brackets also logs
# symbol_noise, which would otherwise hide the CJK extraction failure.
_HIGH_PRIMARY = (
    "replacement", "invalid_utf8", "html_entity", "html_tag",
    "cjk_punct_repeat", "symbol_noise", "repeated_punct",
    "transliterate_greek",
    "empty_garbage",
)

# Low risk — auto-approved and auto-modified
_LOW_CATS = (
    "emoji", "symbol", "punctuation", "accent", "mojibake",
    "transliterate", "nonascii",
)

# Edge-only punct strip (..text.. -> text) is safe cleanup, not high risk
_EDGE_PUNCT = " \t.!?,;:-_~`\"'()[]{}<>…·•"


def _is_edge_punct_only(original: str, cleaned: str) -> bool:
    """True when the only edit is stripping leading/trailing punct/space."""
    if original == cleaned:
        return False
    return original.strip(_EDGE_PUNCT) == cleaned.strip(_EDGE_PUNCT)


def _primary_category(counts: dict, original: str, cleaned: str) -> str:
    """Pick primary category: high-risk first (detected), then mojibake, else max count.

    Detected-but-kept high-risk extraction failures (symbol noise, repeated
    punctuation, HTML, replacement, CJK punct, empty garbage) still force a
    high-risk review even when cleaning left them in place.
    """
    for cat in _HIGH_PRIMARY:
        if counts.get(cat):
            return cat
    if counts.get("mojibake"):
        return "mojibake"
    primary_cat = "other"
    primary_count = 0
    for cat, cnt in counts.items():
        if cat.startswith("protected_"):
            continue
        if cnt > primary_count:
            primary_count = cnt
            primary_cat = cat
    if primary_cat == "other":
        primary_cat = _infer_category(original, cleaned)
    return primary_cat


def scan_all_cells(columns, rows, skip_cols, opts, progress_callback=None) -> ScanResult:
    """Scan every cell, group changes into patterns by risk level."""
    result = ScanResult(total_rows=len(rows), total_cols=len(columns))
    clean_cache = {}
    pattern_groups = {}

    for ridx, row in enumerate(rows):
        row_has_error = False
        for cidx, col in enumerate(columns):
            if cidx >= len(row) or (cidx + 1) in skip_cols:
                continue
            v = row[cidx]
            if not isinstance(v, str) or not v:
                continue

            outcome = clean_cache.get(v)
            if outcome is None:
                outcome = clean_cell(v, opts, col)
                clean_cache[v] = outcome

            if not outcome.changed:
                # Extraction errors that cleaning did not rewrite still need
                # human review (garbage, HTML, symbol noise, ...).
                extract_cat = next(
                    (c for c in _HIGH_PRIMARY if outcome.counts.get(c)),
                    None,
                )
                if extract_cat is None:
                    from backend.core.detect import analyze_text as _at
                    orig_counts = _at(v, apply_accents=False).counts
                    extract_cat = next(
                        (c for c in _HIGH_PRIMARY if orig_counts.get(c)),
                        None,
                    )
                if extract_cat:
                    result.changed_cells += 1
                    row_has_error = True
                    change = CellChange(
                        row_index=ridx,
                        col_index=cidx,
                        column=col,
                        original=v,
                        cleaned=v,
                        category=extract_cat,
                        risk="high",
                    )
                    result.all_changes.append(change)
                    key = (v, v, extract_cat)
                    pattern_groups.setdefault(key, []).append(change)
                continue

            result.changed_cells += 1
            row_has_error = True

            # Determine primary category (high-risk wins, mojibake labeled, else max)
            primary_cat = _primary_category(outcome.counts, v, outcome.cleaned)

            # Edge-only punct strip (..text.. -> text) is low, not repeated_punct high
            if primary_cat in ("repeated_punct", "symbol_noise") and _is_edge_punct_only(v, outcome.cleaned):
                primary_cat = "punctuation"

            # Risk: low cats auto-approved; everything else high (human review)
            if primary_cat in _LOW_CATS:
                risk = "low"
            else:
                risk = "high"

            change = CellChange(
                row_index=ridx,
                col_index=cidx,
                column=col,
                original=v,
                cleaned=outcome.cleaned,
                category=primary_cat,
                risk=risk,
            )
            result.all_changes.append(change)

            key = (v, outcome.cleaned, primary_cat)
            if key not in pattern_groups:
                pattern_groups[key] = []
            pattern_groups[key].append(change)

        if row_has_error:
            result.rows_with_errors += 1
        # Report progress after each row
        if progress_callback:
            progress_callback(ridx + 1)

    for (src, dst, cat), changes in pattern_groups.items():
        risk = changes[0].risk
        reason = f"{cat} → ASCII ({len(changes)} cell(s))"
        pattern = UniquePattern(
            src=src, dst=dst, category=cat, risk=risk,
            total_count=len(changes), reason=reason, changes=changes,
        )
        if risk == "low":
            result.low_patterns.append(pattern)
        elif risk == "medium":
            result.medium_patterns.append(pattern)
        else:
            result.high_patterns.append(pattern)

    return result


def apply_decisions(rows, scan_result, progress_callback=None):
    """Apply approved pattern decisions to rows in place.

    Returns (cleaned_rows, changed_cells, rows_with_errors).
    """
    cleaned_rows = [list(r) for r in rows]
    changed_cells = 0

    for pattern in scan_result.low_patterns + scan_result.medium_patterns + scan_result.high_patterns:
        if pattern.user_decision != "approve":
            continue
        dst = pattern.user_dst if pattern.user_dst else pattern.dst
        for change in pattern.changes:
            ridx, cidx = change.row_index, change.col_index
            cleaned_rows[ridx][cidx] = dst
            changed_cells += 1

    # Per-row progress (drives the CLI bar); the row count reported back is
    # the scan's issue set so scan/apply/final summaries always agree.
    for ridx, _row in enumerate(cleaned_rows):
        if progress_callback:
            progress_callback(ridx + 1)

    return cleaned_rows, changed_cells, scan_result.rows_with_errors
