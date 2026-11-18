"""Verify auto-approve for: emoji, symbol, punctuation, accent, mojibake, transliterate."""
from backend.core.fast_scan import scan_all_cells
from backend.core.clean import CleanOptions
from backend.ai.risk import SAFE_CATEGORIES

SAFE = {"emoji", "symbol", "punctuation", "accent", "mojibake", "transliterate"}

rows = [[
    "smile \U0001F600 here",
    "section \u00a7 and \u2020 mark",
    "bullet \u2022 item",
    "caf\u00e9 na\u00efve",
    "caf\u00c3\u00a9 r\u00e9sum\u00c3\u00a9",
    "\u040e\u0401\u0426 \u0412\u042b\u0414\u0415\u0422",
]]
cols = ["emoji", "symbol", "punct", "accent", "mojibake", "translit"]

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

res = scan_all_cells(cols, rows, set(), opts)

# CLI auto-approve step (same as vmodel_cli.py)
for p in res.low_patterns + res.medium_patterns:
    p.user_decision = "approve"

print("SAFE_CATEGORIES (risk.py):", sorted(SAFE_CATEGORIES))
print()
hdr = f"{'Category':<14} {'Risk':<7} {'Decision':<14} {'src -> dst'}"
print(hdr)
print("-" * len(hdr))
ok = True
for p in res.low_patterns + res.medium_patterns + res.high_patterns:
    status = "auto-approved" if p.user_decision == "approve" else "NEEDS REVIEW"
    print(f"{p.category:<14} {p.risk:<7} {status:<14} {p.src!r} -> {p.dst!r}")
    if p.category in SAFE and (p.risk != "low" or p.user_decision != "approve"):
        ok = False

print()
counts = f"low={len(res.low_patterns)} medium={len(res.medium_patterns)} high={len(res.high_patterns)}"
print(counts)
print("RESULT:", "PASS - all 6 categories auto-approved" if ok else "FAIL")
