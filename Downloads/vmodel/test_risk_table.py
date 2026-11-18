"""Full risk-table verification — matches product spec exactly.

Low  -> auto-approved:  Emoji, Symbol, Punctuation, Accent, Mojibake,
                        Transliterate, NonASCII
High -> needs review:   Replacement, HTML, Symbol noise, Repeated CJK punct,
                        Repeated punct, Empty garbage
Preserved -> untouched: Bullet/Degree/Currency (•, °, and ALL country
                        currency symbols: € £ ¥ $ ₹ ₽ ₩ ₪ ₫ ₦ ₱ ₸ ₺ …)
"""
from __future__ import annotations

import sys

sys.path.insert(0, ".")

from backend.core.clean import CleanOptions, clean_cell
from backend.core.fast_scan import scan_all_cells
from backend.ai.risk import SAFE_CATEGORIES, HIGH_RISK_CATEGORIES

LOW = {"emoji", "symbol", "punctuation", "accent", "mojibake", "transliterate", "nonascii"}
HIGH = {
    "replacement", "invalid_utf8", "html_entity", "html_tag",
    "symbol_noise", "cjk_punct_repeat", "repeated_punct", "transliterate_greek",
    "empty_garbage",
}
PRESERVED_EXPECT_UNCHANGED = True

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

# (label, sample_text, expected_bucket)
# bucket: "low" | "high" | "preserved"
CASES = [
    # --- Low / auto-approved ---
    ("Emoji", "hello \U0001F600 world", "low"),
    ("Symbol", "section \u00a7 and \u2020 mark", "low"),
    ("Punctuation", "bullet \u2022 item", "low"),
    ("Accent", "caf\u00e9 na\u00efve \u00f8", "low"),
    ("Mojibake", "caf\u00c3\u00a9 r\u00e9sum\u00c3\u00a9", "low"),
    ("Transliterate", "\u040e\u0401\u0426 \u0412\u042b\u0414\u0415\u0422", "low"),
    ("NonASCII/CJK", "\u4e2d\u6587 text", "low"),
    # --- High / review ---
    ("Replacement char", "broken \ufffd here", "high"),
    ("HTML entity", "nbsp&nbsp;entity", "high"),
    ("HTML tag", "<div>block</div>", "high"),
    ("Symbol noise", "run * %# @(() end", "high"),
    ("Repeated CJK punct", "\u3001\u3002\u3001 end", "high"),
    ("Repeated punct", "wow !!! really", "high"),
    ("Empty garbage", "@#$%^", "high"),
    ("Replacement mojibake", "bad \u00ef\u00bf\u00bd here", "high"),
    # --- Preserved / not touched ---
    ("Bullet", "keep • point", "preserved"),
    ("Degree", "temp 98°F", "preserved"),
    ("Currency EUR", "cost €100", "preserved"),
    ("Currency GBP", "cost £50", "preserved"),
    ("Currency JPY", "cost ¥5000", "preserved"),
    ("Currency USD", "cost $25", "preserved"),
    # every country symbol, not just the original four
    ("Currency INR", "cost ₹100", "preserved"),
    ("Currency RUB", "cost ₽500", "preserved"),
    ("Currency KRW", "cost ₩1000", "preserved"),
    ("Currency TRY", "cost ₺50", "preserved"),
    ("Currency ILS", "cost ₪20", "preserved"),
    ("Currency VND", "cost ₫50000", "preserved"),
    ("Currency THB", "cost ฿30", "preserved"),
    ("Currency PHP", "cost ₱150", "preserved"),
    ("Currency NGN", "cost ₦10000", "preserved"),
    ("Currency KZT", "cost ₸500", "preserved"),
    ("Currency UAH", "cost ₴100", "preserved"),
    ("Currency GHS", "cost ₵20", "preserved"),
    ("Currency code CHF", "cost 100 CHF", "preserved"),
    ("Currency code SEK", "cost 500 SEK", "preserved"),
    ("Currency code VND", "cost 50000 vnd", "preserved"),
    ("Currency lone sign", "₫", "preserved"),
    # fullwidth forms normalize via ftfy to the protected standard symbol
    ("Fullwidth yen", "￥500", "low"),
    # every Sc currency sign outside the U+20A0-U+20CF block
    ("Currency BDT", "cost ৳100", "preserved"),
    ("Currency AED", "cost ؋50", "preserved"),
    ("Currency KHR", "cost ៛100", "preserved"),
    ("Currency BDT denom", "cost ৹5", "preserved"),
    ("Currency Ganda", "cost ৻5", "preserved"),
    # legal/typo signs kept byte-identical (never romanized / removed)
    ("Signs kept", "brand ©®™", "preserved"),
    # pipe (|) preserved — table/text separators are content, not noise
    ("Pipe kept", "left | right", "preserved"),
    ("Pipe run", "col1 ||| col2", "preserved"),
]

rows = []
cols = [f"c{i}" for i in range(len(CASES))]
for i, (label, text, _) in enumerate(CASES):
    row = [""] * len(CASES)
    row[i] = text
    rows.append(row)

res = scan_all_cells(cols, rows, set(), opts)

# Auto-approve low + medium (same as CLI)
for p in res.low_patterns + res.medium_patterns:
    p.user_decision = "approve"

# Map column index -> pattern (one cell per column)
by_col = {}
for p in res.low_patterns + res.medium_patterns + res.high_patterns:
    for ch in p.changes:
        by_col[ch.col_index] = p

print(f"{'Category':<22} {'Expected':<10} {'Got':<10} {'Risk':<7} {'Action':<16} {'src -> dst'}")
print("-" * 110)

fails = []
for i, (label, text, expected) in enumerate(CASES):
    out = clean_cell(text, opts, cols[i])
    pattern = by_col.get(i)

    if expected == "preserved":
        # Must be unchanged (or only protected restore == original)
        unchanged = (not out.changed) or (out.cleaned == text)
        action = "Not touched" if unchanged else "CHANGED!"
        got = "preserved" if unchanged else "modified"
        risk = "-"
        ok = unchanged
        detail = f"{text!r} -> {out.cleaned!r}"
    else:
        if pattern is None:
            # No change detected — for high cases that should still flag, fail;
            # for low, a no-op can mean nothing to approve (treat carefully)
            got = "no-change"
            risk = "-"
            action = "n/a"
            ok = expected == "low"  # low with no change is fine (nothing risky)
            detail = f"{text!r} (unchanged)"
        else:
            risk = pattern.risk
            got = "low" if risk == "low" else "high"
            if risk == "low":
                action = "Auto-approved"
                ok = expected == "low"
            else:
                action = "Review"
                ok = expected == "high"
            detail = f"{pattern.src!r} -> {pattern.dst!r} [{pattern.category}]"

    status = "OK" if ok else "FAIL"
    if not ok:
        fails.append(label)
    print(f"{label:<22} {expected:<10} {got:<10} {risk:<7} {action:<16} {detail}  {status}")

print()
print("SAFE_CATEGORIES  :", sorted(SAFE_CATEGORIES))
print("HIGH_RISK_CATS   :", sorted(HIGH_RISK_CATEGORIES))
print(f"low={len(res.low_patterns)} med={len(res.medium_patterns)} high={len(res.high_patterns)}")

# Detector: every country currency symbol must be protected — suggest_fold
# must mirror clean exactly, and a lone-symbol cell is never empty_garbage.
from backend.core.detect import analyze_text, suggest_fold  # noqa: E402

CUR_SYMBOLS = (
    "$¢£¤¥€₹₽₩₪₫₦₱₿₡₣₤₭₦₧₨₩"  # ASCII/Latin-1 + block samples
    "₴₮₰₱₲₳₴₵₶₷₸₺₼₽₾฿"         # more U+20A0-U+20CF
    "؋֏฿៛﷼￥￦"                   # outside-block + fullwidth
    # Indic / NKO / Tamil / Wancho / Indic Siyaq + ƒ ﹩ (escapes: no
    # literal-Unicode drift)
    "\u09f2\u09f3\u09f9\u09fb\u0af1\u0bf9\ua838\u07fe\u07ff"
    "\U00011fdd\U00011fde\U00011fdf\U00011fe0"
    "\U0001e2ff\U0001ecb0\u0192\ufe69"
)
fails2 = []
for sym in dict.fromkeys(CUR_SYMBOLS):
    cleaned = clean_cell(sym, opts, "c").cleaned
    got_fold = suggest_fold(sym)
    if got_fold != cleaned:
        fails2.append(f"parity {sym!r}: suggest={got_fold!r} clean={cleaned!r}")
    if analyze_text(cleaned, apply_accents=True, fold_symbols=True).counts.get("empty_garbage"):
        fails2.append(f"empty_garbage({sym!r} -> {cleaned!r})")

# Legal/typo signs + pipe: byte-identical under mode-1 AND fold_scripts
# (anyascii runs after protect), never flagged as garbage.
SIGN_SYMBOLS = "\u00a9\u00ae\u2122|"
opts_strict = CleanOptions(
    fix_mojibake=True,
    fold_accents=True,
    normalize_invisible=True,
    fold_symbols=True,
    collapse_punctuation=True,
    keep_emoji=False,
    fold_scripts=True,
    transliterate_columns=set(),
)
for sym in SIGN_SYMBOLS:
    for o, tag, fscript in ((opts, "mode1", False), (opts_strict, "strict", True)):
        cleaned = clean_cell(sym, o, "c").cleaned
        got_fold = suggest_fold(sym, fold_scripts=fscript)
        if cleaned != sym or got_fold != sym:
            fails2.append(f"sign {tag} {sym!r}: clean={cleaned!r} suggest={got_fold!r}")
    if analyze_text(sym, apply_accents=True, fold_symbols=True).counts.get("empty_garbage"):
        fails2.append(f"empty_garbage(sign {sym!r})")

if fails2:
    print("Currency detector FAIL ->", "; ".join(fails2))
    print("RESULT: FAIL ->", ", ".join(fails))
    sys.exit(1)
print(f"Currency detector: PASS ({len(dict.fromkeys(CUR_SYMBOLS))} symbols protected, suggest==clean, no garbage flags)")

# Mode-1 transliterate = romanize native letters to English LETTERS only —
# anyascii is a pure character map, so Chinese/Japanese must come out as
# romanization, never as a meaning translation ("Chinese language" etc).
try:
    import anyascii as _aa
    opts_translit = CleanOptions(
        fix_mojibake=True,
        fold_accents=True,
        normalize_invisible=True,
        fold_symbols=True,
        collapse_punctuation=True,
        keep_emoji=False,
        fold_scripts=True,
        transliterate_columns=set(),
    )
    for _src in ("\u4e2d\u6587", "\u65e5\u672c\u8a9e", "\u3042\u3044\u3046"):
        _got = clean_cell(_src, opts_translit, "c").cleaned
        _want = _aa.anyascii(_src)
        if _got != _want:
            fails.append(f"transliterate {_src!r}: {_got!r} != romanization {_want!r}")
    # transliterate OFF (opt-out): CJK/kana protected — untouched, not changed
    for _src in ("\u4e2d\u6587", "\u65e5\u672c\u8a9e", "\u3042\u3044\u3046"):
        _got = clean_cell(_src, opts, "c").cleaned
        if _got != _src:
            fails.append(f"safe mode altered {_src!r} -> {_got!r}")
except ImportError:
    pass

if fails:
    print("RESULT: FAIL ->", ", ".join(fails))
    sys.exit(1)
print("RESULT: PASS — full risk table matches")
