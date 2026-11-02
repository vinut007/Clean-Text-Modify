"""Fast scanning: detect cleaning patterns across all cells, group by risk."""
from __future__ import annotations

from dataclasses import dataclass, field

from backend.core.clean import clean_cell, CleanOptions


@dataclass
class CellChange:
    row_index: int
    col_index: int
    column: str
    original: str
    cleaned: str
    category: str
    risk: str


@dataclass
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


@dataclass
class ScanResult:
    total_rows: int
    total_cols: int
    changed_cells: int = 0
    rows_with_errors: int = 0
    low_patterns: list[UniquePattern] = field(default_factory=list)
    medium_patterns: list[UniquePattern] = field(default_factory=list)
    high_patterns: list[UniquePattern] = field(default_factory=list)
    all_changes: list[CellChange] = field(default_factory=list)


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
                continue

            result.changed_cells += 1
            row_has_error = True

            # Determine primary category
            primary_cat = "other"
            primary_count = 0
            for cat, cnt in outcome.counts.items():
                if cat.startswith("protected_"):
                    continue
                if cnt > primary_count:
                    primary_count = cnt
                    primary_cat = cat

            # Risk: emoji/symbol/punctuation/accent/mojibake/transliterate = low (auto-approved);
            # replacement/invalid_utf8/nonascii/html_entity/html_tag/symbol_noise/cjk_punct_repeat/repeated_punct = high
            if primary_cat in ("emoji", "symbol", "punctuation", "accent", "mojibake", "transliterate"):
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
        if risk in ("low", "medium"):
            result.rows_with_errors += len(changes)

    return result


def apply_decisions(rows, scan_result, progress_callback=None):
    """Apply approved pattern decisions to rows in place.

    Returns (cleaned_rows, changed_cells, rows_with_errors).
    """
    cleaned_rows = [list(r) for r in rows]
    changed_cells = 0
    rows_with_errors = 0

    for pattern in scan_result.low_patterns + scan_result.medium_patterns + scan_result.high_patterns:
        if pattern.user_decision != "approve":
            continue
        dst = pattern.user_dst if pattern.user_dst else pattern.dst
        for change in pattern.changes:
            ridx, cidx = change.row_index, change.col_index
            cleaned_rows[ridx][cidx] = dst
            changed_cells += 1

    # Count rows with errors
    for ridx, row in enumerate(cleaned_rows):
        for cidx, val in enumerate(row):
            if isinstance(val, str) and val:
                rows_with_errors += 1
                break
        if progress_callback:
            progress_callback(ridx + 1)

    return cleaned_rows, changed_cells, rows_with_errors
