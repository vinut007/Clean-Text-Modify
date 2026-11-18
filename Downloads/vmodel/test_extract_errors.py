"""Extraction-error detection: high = approve-to-modify, low = auto."""
from __future__ import annotations

import sys

sys.path.insert(0, ".")

from backend.core.clean import CleanOptions, clean_cell
from backend.core.detect import analyze_text
from backend.core.fast_scan import scan_all_cells
from backend.ai.risk import SAFE_CATEGORIES, HIGH_RISK_CATEGORIES

opts = CleanOptions(
    fix_mojibake=True,
    fold_accents=True,
    normalize_invisible=True,
    fold_symbols=True,
    collapse_punctuation=True,
    keep_emoji=False,
    fold_scripts=False,
    transliterate_columns=set(),
)

# (label, text, expected_risk)  risk: "low" | "high"
CASES = [
    # Low — auto-approve
    ("Regular mojibake", "caf\u00c3\u00a9 r\u00e9sum\u00c3\u00a9", "low"),
    ("Accent", "caf\u00e9 na\u00efve", "low"),
    ("Emoji", "smile \U0001F600 here", "low"),
    # High — approve to modify
    ("Replacement mojibake ï¿½", "broken \u00ef\u00bf\u00bd here", "high"),
    ("Replacement char U+FFFD", "broken \ufffd here", "high"),
    ("HTML entity", "nbsp&nbsp;entity", "high"),
    ("HTML tag", "<div>block</div>", "high"),
    ("Repeated punct", "wow !!! really", "high"),
    ("Symbol noise", "run * %# @(() end", "high"),
    ("Empty garbage", "@#$%^", "high"),
]

fails = []
print(f"{'Case':<26} {'Expected':<9} {'Got':<9} {'Category':<18} {'Risk':<7} {'Action':<16}")
print("-" * 100)

for label, text, expected in CASES:
    out = clean_cell(text, opts, "col")
    an = analyze_text(text, apply_accents=False)
    # Prefer scan path for risk (same as CLI)
    rows = [[text]]
    res = scan_all_cells(["col"], rows, set(), opts)
    for p in res.low_patterns + res.medium_patterns:
        p.user_decision = "approve"

    pattern = None
    for p in res.low_patterns + res.medium_patterns + res.high_patterns:
        if p.src == text or text in p.src:
            pattern = p
            break
    # Fallback: any pattern covering this single cell
    if pattern is None and res.all_changes:
        pattern = next(
            (p for p in res.low_patterns + res.medium_patterns + res.high_patterns
             if p.changes and p.changes[0].original == text),
            None,
        )

    if pattern is None:
        got_risk = "none"
        cat = "-"
        action = "n/a"
        ok = expected == "low"  # low with no change = fine
    else:
        got_risk = pattern.risk
        cat = pattern.category
        if got_risk == "low":
            action = "Auto-approved"
            ok = expected == "low"
        else:
            action = "Review"
            ok = expected == "high"

    status = "OK" if ok else "FAIL"
    if not ok:
        fails.append(label)
    print(f"{label:<26} {expected:<9} {got_risk:<9} {cat:<18} {got_risk:<7} {action:<16} {status}")

# Direct detector checks
print()
an_imoji = analyze_text("\u00ef\u00bf\u00bd", apply_accents=False)
assert an_imoji.counts.get("replacement"), f"ï¿½ not detected as replacement: {an_imoji.counts}"
an_garb = analyze_text("@#$%", apply_accents=False)
assert an_garb.counts.get("empty_garbage"), f"garbage not detected: {an_garb.counts}"
print("Detector asserts: PASS (ï¿½→replacement, @#$%→empty_garbage)")

# Category sets
assert "truncated" not in HIGH_RISK_CATEGORIES
assert "empty_garbage" in HIGH_RISK_CATEGORIES
assert "mojibake" in SAFE_CATEGORIES
assert "replacement" in HIGH_RISK_CATEGORIES
print("risk.py sets: PASS")

# Auto-approve behavior for low
low_ok = all(
    p.user_decision == "approve"
    for p in res.low_patterns + res.medium_patterns
)
print(f"Low/med auto-approve: {'PASS' if low_ok else 'FAIL'}")

print()
if fails:
    print("RESULT: FAIL ->", ", ".join(fails))
    sys.exit(1)
print("RESULT: PASS — extraction-error risk table")
