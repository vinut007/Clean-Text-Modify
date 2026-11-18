"""Mode-1 cell-level probe: how output/annotations are produced for varied cells."""
import sys
sys.path.insert(0, '.')

from backend.core.clean import CleanOptions, clean_cell
import vmodel_cli as V

OPTS = CleanOptions(fix_mojibake=True, fold_accents=True, normalize_invisible=True,
                    fold_symbols=True, collapse_punctuation=True, keep_emoji=False,
                    fold_scripts=False, transliterate_columns=set())

CELLS = [
    "Café naïve résumé",
    "cafÃ© résumÃ©",
    "ï¿½ broken",
    "straße ß",
    "İstanbul ı",
    "ΩµΩ Ohm",
    "… ellipsis • bullet",
    "a \u2192 b \u2265 c",
    "\uff28\uff45\uff4c\uff4c\uff4f\uff11\uff12\uff13",
    "\u2460\u2461\u2462 circled",
    "\ufb01le \ufb02ow \ufb00",
    "\u041f\u0440\u0438\u0432\u0435\u0442 \u043c\u0438\u0440",
    "\u0645\u0631\u062d\u0628\u0627 \u0628\u0627\u0644\u0639\u0627\u0644\u0645",
    "\u05e9\u05c1\u05b8\u05dc\u05b5\u05d5\u05dd \u05e2\u05d5\u05dc\u05dd",
    "\u4e2d\u6587\u6d4b\u8bd5\uff0c\u3002",
    "\u65e5\u672c\u8a9e\u306e\u30c6\u30ad\u30b9\u30c8",
    "\u2081\u2082\u2083 subscripts",
    "\u00b2\u00b3\u00b9 superscripts",
    "\u00bd \u00bc \u00be fractions",
    "1\ufe0f\u20e3 2\ufe0f\u20e3 #\ufe0f\u20e3",
    "\U0001f468\u200d\U0001f469\u200d\U0001f467 family",
    "Hello \U0001f600 World",
    "line1\nline2\ttabbed",
    "soft\u00adhyphen test",
    "bidi\u202e override",
    "zwsp\u200binside and \ufeffbom",
    "\u00a0nbsp\u00a0spacing",
    "a\u2028b line-sep",
    "e\u0301 decomposed",
    "u\u0308 diaeresis",
    "\U0001f600\ufe0f emoji vs",
    "\u20ac100 \u00a350 \u00a55 $25 \u2022",
    "http://example.com/p?q=1#frag",
    "user@domain.com",
    "!!! ??? ... collapse",
    "\u3001\u3002\u3001\u3002 cjk repeat",
    "@#$%^ junk",
    "<div>html</div> &amp; entity",
    "temp 98.6\u00b0F degree",
    "\u21165 para \u00b66 \u00a77",
    "\u0661\u0662\u0663 arabic-indic digits",
    "\u0e51\u0e52\u0e53 thai",
    "\ud55c\uad6d\uc5b4 \ud145\uc2dd",
    "\u0391\u0392\u0393\u0394 Greek",
    "\u03b1\u03b2\u03b3\u03b4\u03b5 lowercase greek",
    "\u1f88 Greek extended capital",
    "\u0259\u026a\u028a IPA",
    "\u0101\u0113\u012b\u014d\u016b macrons",
    "\u00d1 \u00f1 tilde",
    "\u01c5 digraph",
    "\u2163 roman numeral",
    "\u2121 telephone sign",
    "%%%%%%%% percent noise",
    "Wait... what?! seriously???",
    "\u00a1\u00bf accent punct",
    "\u00c5ngstr\u00f6m \u00c5",
    "  leading and trailing  ",
    "",
    "\u00a0",
    "\ufeff",
    "\u212a\u212b\u03a9 KAO",
    ";;",
    "\u2016 double vert",
    "\u2024 dot leader",
]

print(f"{'CLEANED':<40} | CHANGED | ANNOTATION")
print('-' * 130)
for cell in CELLS:
    oc = clean_cell(cell, OPTS, 'description')
    errs = V._cell_errors(cell, 'description', OPTS)
    marked = V._mark_fixed(errs, cell, oc.cleaned)
    disp = repr(cell)[:36]
    print(f"{disp:<40} | {str(oc.changed):<7} | {'; '.join(marked)}")
    if oc.cleaned != cell and not marked:
        print(f"    !! CHANGED BUT NO ANNOTATION -> {oc.cleaned!r}")
    for m in marked:
        lab, _, rest = m.partition(':')
        orig, arrow, sugg = rest.partition('\u2192')
        sugg_stat = sugg.replace(' \u2713fixed', '').replace(' \u2717kept', '')
        if arrow and sugg_stat == orig and '✓fixed' in m:
            print(f"    !! SUGGESTS KEPT BUT MARKED FIXED: {m}")
        if arrow and sugg_stat and sugg_stat not in oc.cleaned and '✓fixed' in m and orig not in oc.cleaned:
            pass
