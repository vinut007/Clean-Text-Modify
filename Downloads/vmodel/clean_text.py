import re
import sys
import unicodedata

try:
    from ftfy import fix_text
except ImportError:
    fix_text = None

# Emoji / symbol Unicode ranges to strip (covers emoji, pictographs, symbols)
_EMOJI_RE = re.compile(
    "["
    "\U0001F600-\U0001F64F"  # emoticons
    "\U0001F300-\U0001F5FF"  # symbols & pictographs
    "\U0001F680-\U0001F6FF"  # transport & map symbols
    "\U0001F1E0-\U0001F1FF"  # flags
    "\U00002700-\U000027BF"  # dingbats
    "\U000024C2-\U0001F251"  # enclosed chars
    "\U0001F900-\U0001F9FF"  # supplemental symbols
    "\U0001FA70-\U0001FAFF"  # symbols & pictographs extended
    "\U00002600-\U000026FF"  # misc symbols
    "\U00002B00-\U00002BFF"  # misc symbols arrows
    "\U0000200D"             # zero width joiner
    "\U000020E3"             # combining enclosing keycap
    "\U0000FE0F"             # variation selector
    "]+",
    flags=re.UNICODE,
)


def strip_emojis(text):
    """Remove emoji and symbol characters."""
    return _EMOJI_RE.sub("", text)


# Full-width CJK brackets / arrows / symbols to map
FULLWIDTH_MAP = {
    "\u3010": "[",   # 【
    "\u3011": "]",   # 】
    "\u3014": "[",   # ⟪
    "\u3015": "]",   # ⟫
    "\uff3b": "[",   # [
    "\uff3d": "]",   # ]
    "\u2192": "->",  # →
    "\u2190": "<-",  # ←
    "\u2194": "<->", # ↔
}


def strip_fullwidth(text):
    return "".join(FULLWIDTH_MAP.get(ch, ch) for ch in text)


_MATH_MAP = None

_STYLE_WORDS = {
    "BOLD", "ITALIC", "SCRIPT", "FRAKTUR", "DOUBLE-STRUCK",
    "SANS-SERIF", "MONOSPACE",
}


def _build_math_map():
    """Map mathematical alphanumeric symbols (U+1D400..U+1D7FF) to ASCII."""
    mapping = {}
    for cp in range(0x1D400, 0x1D800):
        try:
            ch = chr(cp)
            name = unicodedata.name(ch)
        except (ValueError, KeyError):
            continue
        if not name.startswith("MATHEMATICAL "):
            continue
        rest = name[len("MATHEMATICAL "):]
        tokens = [t for t in rest.split(" ") if t not in _STYLE_WORDS]
        rest = " ".join(tokens)
        m = re.fullmatch(r"(CAPITAL|SMALL) ([A-Z])", rest)
        if m:
            kind, letter = m.group(1), m.group(2)
            mapping[ch] = letter if kind == "CAPITAL" else letter.lower()
            continue
        m = re.fullmatch(r"DIGIT ([0-9])", rest)
        if m:
            mapping[ch] = m.group(1)
    return mapping


def _math_map():
    global _MATH_MAP
    if _MATH_MAP is None:
        _MATH_MAP = _build_math_map()
    return _MATH_MAP


def normalize_math_style(text):
    """𝗧𝗼𝘂𝗿𝗻𝗮𝗺𝗲𝗻𝘁 -> Tournament (mathematical alphanumeric symbols -> ASCII)."""
    m = _math_map()
    return "".join(m.get(ch, ch) for ch in text)


def fix_mojibake(text):
    if fix_text is not None:
        return fix_text(text)
    return text


def strip_accents(text):
    """é -> e by decomposing (NFD) and dropping combining marks (Mn)."""
    return "".join(
        ch for ch in unicodedata.normalize("NFD", text)
        if unicodedata.category(ch) != "Mn"
    )


def find_accented(text):
    """Return list of (index, char) that still carry a combining accent."""
    found = []
    for i, ch in enumerate(text):
        decomposed = unicodedata.normalize("NFD", ch)
        if len(decomposed) > 1:
            found.append((i, ch, decomposed))
    return found


def find_mojibake(text):
    """Heuristic: replacement char or common mojibake sequences."""
    issues = []
    if "\ufffd" in text:
        issues.append(("replacement_char", "\ufffd"))
    for m in re.finditer(r"[ÃÂâÂ][©¨ªº¯°±²³µÀÁÂÃÄÅÆÇÈÉÊËÌÍÎÏÐÑÒÓÔÕÖØÙÚÛÜÝÞßàáâãäåæçèéêëìíîïðñòóôõöøùúûüýþÿ€™]", text):
        issues.append((m.start(), m.group(0)))
    return issues


def find_fullwidth(text):
    """Return remaining full-width bracket/arrow characters."""
    found = []
    for i, ch in enumerate(text):
        if ch in FULLWIDTH_MAP:
            found.append((i, ch, hex(ord(ch))))
    return found


def find_math_style(text):
    """Return remaining mathematical alphanumeric symbols."""
    m = _math_map()
    found = []
    for i, ch in enumerate(text):
        if ch in m:
            found.append((i, ch, hex(ord(ch))))
    return found


def clean(text):
    text = fix_mojibake(text)
    text = normalize_math_style(text)
    text = strip_accents(text)
    text = strip_emojis(text)
    text = strip_fullwidth(text)
    return text


def find_emojis(text):
    """Return list of (index, char) that are emoji/symbol characters."""
    found = []
    for m in _EMOJI_RE.finditer(text):
        for i in range(m.start(), m.end()):
            found.append((i, text[i], hex(ord(text[i]))))
    return found


def verify(text, label=""):
    accented = find_accented(text)
    moji = find_mojibake(text)
    fullwidth = find_fullwidth(text)
    mathstyle = find_math_style(text)
    emojis = find_emojis(text)
    status = "CLEAN" if not accented and not moji and not fullwidth and not mathstyle and not emojis else "DIRTY"
    print(f"[{status}] {label}")
    for i, ch, dec in accented:
        print(f"   accented @{i}: U+{ord(ch):04X} {ch!r} -> NFD {dec!r}")
    for i, ch in moji:
        print(f"   mojibake @{i}: {ch!r}")
    for i, ch, hx in fullwidth:
        print(f"   fullwidth @{i}: U+{hx} {ch!r}")
    for i, ch, hx in mathstyle:
        print(f"   math-style @{i}: U+{hx} {ch!r}")
    for i, ch, hx in emojis:
        print(f"   emoji @{i}: U+{hx} {ch!r}")
    return status == "CLEAN"


def safe_clean(value, default=""):
    """Clean text safely: returns default on None/empty or any cleaning error."""
    if value is None:
        return default
    try:
        text = str(value)
    except Exception:
        return default
    if text == "":
        return default
    try:
        return clean(text)
    except Exception:
        return text


if __name__ == "__main__":
    samples = [
        "Contribution Sociale Généralisée",
        "ITL - Africa Deal Watch - September 2026",
        "Mojibake: cafÃ© rÃ©sumÃ© naÃ¯ve Â€ â€™",
        "Mixed: Générale cafÃ© ITL Deal Watch",
        "Brackets: 【text】 here 【turn912817search1】【turn912817search0】 we mapped right ->】",
        "Section: § preserved, brackets 【a】【b】 mapped to [a][b]",
        "Arrows: a → b ← c ↔ d",
        "Math style: 𝗧𝗼𝘂𝗿𝗻𝗮𝗺𝗲𝗻𝘁 -> Tournament",
        "Mixed all: § 【𝗧𝗼𝘂𝗿𝗻𝗮𝗺𝗲𝗻𝘁】 cafÃ© → →",
        "Emojis: Hello 😀 World 🚀 🎉 Test ✓",
    ]
    all_clean = True
    for s in samples:
        cleaned = clean(s)
        print(f"IN : {s!r}")
        print(f"OUT: {cleaned!r}")
        all_clean &= verify(cleaned, label="after clean")
        print()
    print("ALL CLEAN" if all_clean else "STILL HAS ISSUES")
    sys.exit(0 if all_clean else 1)
