"""Mode-1 single-char parity: clean_cell vs suggest_fold (bare + wrapped)."""
import sys
sys.path.insert(0, '.')
from backend.core.clean import CleanOptions, clean_cell
from backend.core.detect import suggest_fold, INVISIBLE, _INV_SPACE

M1 = dict(apply_accents=True, fold_symbols=True, fold_scripts=False,
          keep_emoji=False, normalize_invisible=True, fix_mojibake=True,
          do_translit=False, collapse_punct=True)
OPTS = CleanOptions(fix_mojibake=True, fold_accents=True, normalize_invisible=True,
                    fold_symbols=True, collapse_punctuation=True, keep_emoji=False,
                    fold_scripts=False, transliterate_columns=set())

RANGES = [
    (0x0000, 0x001F), (0x007F, 0x007F), (0x0009, 0x000D),
    (0x00A0, 0x02FF), (0x0300, 0x036F), (0x0370, 0x058F),
    (0x0400, 0x04FF), (0x0590, 0x05FF), (0x0600, 0x06FF),
    (0x0900, 0x097F), (0x1E00, 0x1EFF), (0x1F00, 0x1FFF),
    (0x2000, 0x206F), (0x2070, 0x209F), (0x20A0, 0x20CF),
    (0x2100, 0x214F), (0x2150, 0x218F), (0x2190, 0x22FF),
    (0x2460, 0x24FF), (0x2500, 0x25FF), (0x2600, 0x27BF),
    (0x2E80, 0x2EFF), (0x3000, 0x30FF), (0x4E00, 0x4E20),
    (0xFB00, 0xFB4F), (0xFE00, 0xFE0F), (0xFE30, 0xFE4F),
    (0xFF00, 0xFFEF), (0x1F300, 0x1F9FF), (0x20E0, 0x20EF),
    (0x202A, 0x202E), (0x2060, 0x2069), (0x00AD, 0x00AD),
]

bare, wrapped = [], []
for lo, hi in RANGES:
    for cp in range(lo, hi + 1):
        ch = chr(cp)
        try:
            o = clean_cell(ch, OPTS, None).cleaned
            s = suggest_fold(ch, **M1)
        except Exception as e:
            bare.append((hex(cp), ch, 'ERR', str(e)[:40], '', ''))
            continue
        if o != s:
            bare.append((hex(cp), ch, repr(o), repr(s),
                         'INV' if ch in INVISIBLE else '-', 'SPC' if ch in _INV_SPACE else '-'))
        try:
            ow = clean_cell("x" + ch + "y", OPTS, None).cleaned
        except Exception as e:
            wrapped.append((hex(cp), ch, 'ERR', str(e)[:40]))
            continue
        if ow != "x" + s + "y":
            wrapped.append((hex(cp), ch, repr(ow), repr("x" + s + "y")))

print(f"=== BARE mismatches (n={len(bare)}) ===")
for x in bare[:200]:
    print('  ', x)
print(f"=== WRAPPED mismatches (n={len(wrapped)}) ===")
for x in wrapped[:200]:
    print('  ', x)
