"""Mode-1 (Safe clean) test: 'JosÃ© MÃ¼ller ###Test' — full pipeline view."""
import sys
sys.path.insert(0, '.')
from backend.core.clean import CleanOptions, clean_cell, protect as protect_mod
from backend.core.detect import analyze_text, suggest_fold
from backend.core import fast_scan

SRC = "JosÃ© MÃ¼ller ###Test"

M1 = CleanOptions(fix_mojibake=True, fold_accents=True, normalize_invisible=True,
                  fold_symbols=True, collapse_punctuation=True, keep_emoji=False,
                  fold_scripts=False, transliterate_columns=set())

# 1. clean_cell
res = clean_cell(SRC, M1, None)
print("=== clean_cell (Mode 1 opts) ===")
print("  src    :", repr(SRC))
print("  cleaned:", repr(res.cleaned))
print("  changed:", res.changed)
print("  counts :", {k: v for k, v in res.counts.items() if v})

# 2. (suggest_fold parity is single-char only — covered by _p1_single.py)

# 3. analyze_text spans (annotation view)
pr = protect_mod(SRC)
an = analyze_text(pr.text, apply_accents=True, fold_symbols=True, keep_emoji=False,
                  normalize_invisible=True, fix_mojibake=True, collapse_punct=True)
print("\n=== analyze_text spans ===")
for sp in an.spans:
    print(f"  {sp.category:<16} {sp.original!r} -> {sp.suggested!r}")

# 4. fast_scan classification (risk + pattern)
sr = fast_scan.scan_all_cells(["col"], [[SRC]], set(), M1)
print("\n=== fast_scan ===")
print(f"  changed_cells={sr.changed_cells} low={len(sr.low_patterns)} "
      f"med={len(sr.medium_patterns)} high={len(sr.high_patterns)}")
for bucket, pats in (("low", sr.low_patterns), ("med", sr.medium_patterns),
                     ("high", sr.high_patterns)):
    for p in pats:
        print(f"  [{bucket}] {p.category:<16} risk={p.risk} {p.src!r} -> {p.dst!r}")
        print(f"        reason={p.reason}")
        for ch in p.changes:
            print(f"        change: col={ch.column} {ch.original!r} -> {ch.cleaned!r}")
if not (sr.low_patterns or sr.medium_patterns or sr.high_patterns):
    print("  (no patterns — cell would be unchanged / not reviewed)")

# 5. _cell_errors annotation (what the output 'error' column shows)
from vmodel_cli import _cell_errors, _mark_fixed
errs = _cell_errors(SRC, "col", M1)
print("\n=== output annotation ===")
print("  errors:", errs if errs else "(none)")
if errs:
    print("  marked:", _mark_fixed(errs, SRC, res.cleaned))
