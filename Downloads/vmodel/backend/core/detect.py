"""Text detection: categorize accents, mojibake, emoji, symbols, invisible."""
from __future__ import annotations

import re
from dataclasses import dataclass

import unicodedata

from .mappings import (
    FULLWIDTH, LATIN_ACCENTS, LIGATURES, SCRIPT_TO_LATIN, SYMBOL_TO_ASCII,
    TYPOGRAPHIC, is_emoji_remove, is_preserve_script,
)
from .protect import CURRENCY_CLASS

try:
    import ftfy as _ftfy
except Exception:  # pragma: no cover - clean.py hard-requires ftfy anyway
    _ftfy = None

# Format/control characters that should be normalized or removed
INVISIBLE = {
    "\u00a0", "\u1680", "\u2000", "\u2001", "\u2002", "\u2003", "\u2004",
    "\u2005", "\u2006", "\u2007", "\u2008", "\u2009", "\u200a", "\u202f",
    "\u205f", "\u3000", "\u200b", "\u200c", "\u200d", "\u200e", "\u200f",
    "\ufeff",
    # same chars clean removes/normalizes in step 2c: soft hyphen, word
    # joiner, line/paragraph separators, bidi embeddings/overrides/isolates
    "\u00ad", "\u2060", "\u2028", "\u2029",
    "\u202a", "\u202b", "\u202c", "\u202d", "\u202e",
    "\u2066", "\u2067", "\u2068", "\u2069",
}
# ASCII controls: clean converts \t \n \r to space and deletes the rest
INVISIBLE.update(chr(c) for c in range(0x20))
INVISIBLE.add("\x7f")

# Space-like invisibles -> normal space (clean step 2c); rest of INVISIBLE
# are format controls -> removed. ZWJ (\u200d) handled separately: it is
# kept until the emoji-removal step (meaningful inside emoji sequences).
_INV_SPACE = {
    "\u00a0", "\u1680", "\u3000", "\u2000", "\u2001", "\u2002", "\u2003",
    "\u2004", "\u2005", "\u2006", "\u2007", "\u2008", "\u2009", "\u200a",
    "\u202f", "\u205f",
}

# protect() keeps bullet + currency + legal/typo signs + pipe byte-identical,
# so clean never folds them — suggestions must not claim a fold for these.
# CURRENCY_CLASS covers every country currency symbol ($ ¢ £ ¤ ¥ + U+20A0-U+20CF + ...).
_PROTECTED_CHAR_RE = re.compile(r"[•°©®™|" + CURRENCY_CLASS + "]")

# HTML entities: &nbsp;, &amp;, &lt;, &gt;, &#123;, &quot;, &apos;, etc.
_HTML_ENTITY_RE = re.compile(r"&[a-zA-Z][a-zA-Z0-9]*;|&#[0-9]+;|&#x[0-9a-fA-F]+;")

# HTML tags: <div>, <span>, </p>, etc.
_HTML_TAG_RE = re.compile(r"</?[a-zA-Z][a-zA-Z0-9]*[^>]*>")

# Repeated CJK punctuation: 、。、。 etc.
_CJK_PUNCT_RE = re.compile(r"[、。，！？；：]、*[、。，！？；：]")

# Symbol noise: runs of symbols like * %# @(() ^%$ etc. — pipe excluded:
# | runs (table/text separators) are protected content, not noise
_SYMBOL_NOISE_RE = re.compile(r"[#%@$^&*(){}[\]<>/\\`~]{3,}")

# Repeated punctuation runs: !!! ??? ... etc.
_REPEATED_PUNCT_RE = re.compile(r"([!?.,;::-])\1{2,}")

# Replacement mojibake: UTF-8 U+FFFD (EF BF BD) misread as cp1252 -> ï¿½
_REPLACEMENT_MOJIBAKE_RE = re.compile(r"ï¿½")

# Mojibake pairs: UTF-8 bytes re-decoded as cp1252/latin-1 (Ã©, Â®, â€, ...).
# Emitted as repair spans only when ftfy actually changes them, so legit
# text like "ÃO" (Portuguese) never matches.
_MOJIBAKE_PAIR_RE = re.compile(r"Ã.|Â.|â[\x80-\xff]|â€|ï¿")

# protect() token placeholders — never analyze their internals
_PROT_PLACEHOLDER_RE = re.compile(r"\x00PROT\d+\x00")

# Pure symbol/punct garbage (no letters, no digits) that survived cleaning.
# Bullet/degree/currency symbols + legal/typo signs + pipe are content, not garbage.
_PRESERVE_ONLY_RE = re.compile(r"[•°©®™|" + CURRENCY_CLASS + "]")

# Chars users label as "Symbol" even though Unicode reports them as Po (punctuation)
_MANUAL_SYMBOLS = set("§†‡¶№℮")

# CJK / fullwidth blocks -> "CJK/non-Latin" (high risk, needs review)
_CJK_RANGES = (
    (0x2E80, 0x2EFF), (0x3000, 0x303F), (0x3040, 0x30FF),
    (0x3100, 0x312F), (0x31A0, 0x31BF), (0x31F0, 0x31FF),
    (0x3400, 0x4DBF), (0x4E00, 0x9FFF), (0xF900, 0xFAFF),
    (0xFE30, 0xFE4F), (0xFF00, 0xFF60), (0xFFE0, 0xFFE6),
    (0x20000, 0x2FA1F),
)


def _is_cjk(cp: int) -> bool:
    return any(lo <= cp <= hi for lo, hi in _CJK_RANGES)


def classify_nonascii(ch: str) -> str:
    """Classify a non-ASCII char for risk reporting.

    - U+FFFD -> replacement (high)
    - CJK / fullwidth (incl. 、。) -> nonascii (low, auto-approved)
    - § † ‡ ¶ № -> symbol (low, product Symbol row)
    - other P* -> punctuation (low), other S* -> symbol (low)
    - else -> nonascii (low)
    """
    if ch == "�":
        return "replacement"
    if ch in _MANUAL_SYMBOLS:
        return "symbol"
    if _is_cjk(ord(ch)):
        return "nonascii"
    ucat = unicodedata.category(ch)
    if ucat.startswith("P"):
        return "punctuation"
    if ucat.startswith("S"):
        return "symbol"
    return "nonascii"


@dataclass
class Span:
    category: str
    original: str
    suggested: str


def _is_empty_garbage(text: str) -> bool:
    """True when text has no letters/digits — pure symbol junk (not currency/bullet).

    Protected tokens are dropped first: an all-protected cell ("€", a lone
    new currency sign, a wrapped URL) is content, not garbage.
    """
    s = _PROT_PLACEHOLDER_RE.sub("", text).strip()
    if not s:
        return False
    if any(ch.isalnum() for ch in s):
        return False
    if all(_PRESERVE_ONLY_RE.match(ch) for ch in s):
        return False
    return True


def _fold_char(c, apply_accents, fold_symbols, fold_scripts, keep_emoji,
               normalize_invisible, do_translit):
    """Mirror clean_cell's per-character fold for a single non-ASCII char."""
    if ord(c) < 128:
        # clean step 2c (gated by normalize_invisible): \t \n \r -> space,
        # remaining C0 controls + DEL -> removed
        if normalize_invisible and c in "\t\n\r":
            return " "
        if normalize_invisible and (ord(c) < 0x20 or c == "\x7F"):
            return ""
        return c
    # invisible normalization (clean step 2c) — ZWJ removed only by the
    # emoji-removal step, so keep_emoji decides its fate
    if c in INVISIBLE:
        if c == "\u200d":
            return c if keep_emoji else ""
        if not normalize_invisible:
            return c
        return " " if c in _INV_SPACE else ""
    # SYMBOL_TO_ASCII first pass (clean step 2, runs before the fold chain)
    if not keep_emoji:
        c = SYMBOL_TO_ASCII.get(c, c)
        if not c or ord(c) < 128:
            return c
    o = ord(c)
    folded = None
    if c in LATIN_ACCENTS or c in LIGATURES:
        if apply_accents or do_translit:
            folded = LATIN_ACCENTS.get(c) or LIGATURES.get(c)
    elif c in TYPOGRAPHIC:
        if (fold_symbols or do_translit) and not (
                c in INVISIBLE and not normalize_invisible):
            folded = TYPOGRAPHIC[c]
    elif c in FULLWIDTH:
        if (fold_symbols or do_translit) and not unicodedata.category(c).startswith("L"):
            folded = FULLWIDTH[c]
    elif c in SCRIPT_TO_LATIN and (
        fold_scripts or do_translit
        # Greek + Cyrillic fold under fold_symbols/fold_accents (clean's
        # 0x0370-0x1FFF gate covers both scripts)
        or (0x0370 <= o <= 0x1FFF and (fold_symbols or apply_accents))
    ):
        folded = SCRIPT_TO_LATIN[c]
    elif (0xC0 <= o <= 0x24F or 0x1E00 <= o <= 0x1EFF) and (
            apply_accents or do_translit) and unicodedata.category(c).startswith("L"):
        base = strip_combining(c)
        if base and base != c and all(ord(x) < 128 for x in base):
            folded = base
    if folded is None:
        folded = c
    # emoji / decorative removal (clean step 5) — per char, like clean
    if not keep_emoji and folded:
        folded = "".join(
            x for x in folded
            if not is_emoji_remove(x) or is_preserve_script(x)
        )
        folded = folded.replace("\u200d", "")
        # orphaned presentation selectors (clean step 5 does the same)
        folded = folded.replace("\ufe0f", "").replace("\ufe0e", "")
    return folded


def suggest_fold(ch, apply_accents=True, fold_symbols=True, fold_scripts=False,
                 keep_emoji=False, normalize_invisible=True, fix_mojibake=True,
                 do_translit=False, collapse_punct=True):
    """Return what clean_cell turns this single char into.

    Mirrors clean's pipeline: ftfy pre-pass (NFC + uncurl, like clean's whole-
    text ftfy) -> SYMBOL_TO_ASCII -> invisible normalization -> fold chain
    (LATIN_ACCENTS/LIGATURES -> TYPOGRAPHIC -> FULLWIDTH -> SCRIPT_TO_LATIN ->
    strip_combining fallback) -> collapse punct runs -> emoji removal ->
    anyascii in transliterate columns.
    """
    if _PROTECTED_CHAR_RE.match(ch):
        return ch
    queue = [ch]
    out = []
    # bounded loop: ftfy can expand one char into several; maps never requeue
    for _ in range(8):
        if not queue:
            break
        c = queue.pop(0)
        # clean runs ftfy on the whole text first (NFC-normalizes, uncurls
        # quotes, repairs mojibake) — run it per char to stay in parity
        if fix_mojibake and ord(c) > 127 and _ftfy is not None:
            try:
                fx = _ftfy.fix_text(c, uncurl_quotes=fold_symbols)
            except Exception:
                fx = c
            if fx != c:
                queue[0:0] = fx
                continue
        out.append(_fold_char(c, apply_accents, fold_symbols, fold_scripts,
                              keep_emoji, normalize_invisible, do_translit))
    res = "".join(out)
    if apply_accents:
        # mirror clean's Mn-after-ASCII strip for ftfy-split sequences
        # (￣ -> ftfy " ̄" -> clean drops the mark after the space)
        stripped: list[str] = []
        prev_ascii = False
        for x in res:
            if unicodedata.category(x) == "Mn" and prev_ascii:
                continue
            stripped.append(x)
            prev_ascii = ord(x) < 128
        res = "".join(stripped)
    if collapse_punct:
        # clean step 4b: … -> "..." -> "." via run collapse
        res = collapse_punctuation(res)
    if (do_translit or fold_scripts) and any(ord(c) > 127 for c in res):
        try:
            import anyascii
            res = anyascii.anyascii(res)
        except Exception:
            res = re.sub(r"[^\x00-\x7F]", "", res)
    # clean removes U+FFFD outright (never a visible "?") — same here
    res = res.replace("\ufffd", "")
    return res


def analyze_text(text, apply_accents=True, fold_scripts=False, fold_symbols=True,
                 keep_emoji=False, normalize_invisible=True, fix_mojibake=True,
                 do_translit=False, collapse_punct=True):
    """Return object with .spans (list of Span) and .counts (dict).

    Detects: mojibake, replacement, accent, invisible, symbol, emoji, punctuation, nonascii.
    Span.suggested mirrors clean_cell's fold for the same options.
    """
    counts: dict[str, int] = {}
    spans: list[Span] = []

    def _sugg(ch: str) -> str:
        return suggest_fold(
            ch, apply_accents=apply_accents, fold_symbols=fold_symbols,
            fold_scripts=fold_scripts, keep_emoji=keep_emoji,
            normalize_invisible=normalize_invisible, fix_mojibake=fix_mojibake,
            do_translit=do_translit, collapse_punct=collapse_punct)

    # Replacement mojibake (ï¿½) first — mark its char indices so the main
    # loop does not misclassify ï/¿/½ as accent/punctuation/number.
    _skip: set[int] = set()
    for m in _REPLACEMENT_MOJIBAKE_RE.finditer(text):
        counts["replacement"] = counts.get("replacement", 0) + 1
        spans.append(Span("replacement", m.group(0), ""))
        _skip.update(range(m.start(), m.end()))

    # protect() placeholders (\x00PROTn\x00): NUL delimiters must not be
    # flagged as invisible characters (analyze may run on protected text)
    for m in _PROT_PLACEHOLDER_RE.finditer(text):
        _skip.update(range(m.start(), m.end()))

    # Mojibake pairs (Ã©, Â®, ...): emit a repair span only when ftfy really
    # changes the pair, and suppress the per-char spans inside it so the
    # annotation reads "Mojibake:cafÃ©→cafe" instead of Ã→A + ©→©.
    for m in _MOJIBAKE_PAIR_RE.finditer(text):
        if any(idx in _skip for idx in range(m.start(), m.end())):
            continue
        pair = m.group(0)
        if _ftfy is None:
            continue
        try:
            fx = _ftfy.fix_text(pair, uncurl_quotes=fold_symbols)
        except Exception:
            continue
        if fx == pair:
            continue  # legit text (e.g. "ÃO"), not mojibake
        sugg = "".join(
            _fold_char(c, apply_accents, fold_symbols, fold_scripts,
                       keep_emoji, normalize_invisible, do_translit)
            for c in fx)
        if collapse_punct:
            sugg = collapse_punctuation(sugg)
        if not sugg or sugg == pair:
            continue
        counts["mojibake"] = counts.get("mojibake", 0) + 1
        spans.append(Span("mojibake", pair, sugg))
        _skip.update(range(m.start(), m.end()))

    # Near-empty garbage: no letters, no digits (e.g. "@#$", "???")
    if _is_empty_garbage(text):
        counts["empty_garbage"] = counts.get("empty_garbage", 0) + 1
        spans.append(Span("empty_garbage", text.strip(), ""))

    i = 0
    n = len(text)
    while i < n:
        if i in _skip:
            i += 1
            continue
        ch = text[i]
        o = ord(ch)

        # Replacement character
        if ch == "\ufffd":
            counts["replacement"] = counts.get("replacement", 0) + 1
            spans.append(Span("replacement", ch, ""))
            i += 1
            continue

        # Invisible / control
        if ch in INVISIBLE:
            counts["invisible"] = counts.get("invisible", 0) + 1
            spans.append(Span("invisible", ch, _sugg(ch)))
            i += 1
            continue

        # Emoji / symbol ranges (non-Latin scripts kept if fold_scripts False)
        if 0x1F600 <= o <= 0x1F64F or 0x1F300 <= o <= 0x1F5FF or 0x1F680 <= o <= 0x1F6FF:
            counts["emoji"] = counts.get("emoji", 0) + 1
            spans.append(Span("emoji", ch, _sugg(ch)))
            i += 1
            continue

        # Non-ASCII letter with accent (Latin-1 Supplement + Latin Extended-A/B)
        if 0xC0 <= o <= 0x24F or 0x1E00 <= o <= 0x1EFF:
            ucat = unicodedata.category(ch)
            if ucat.startswith("L"):
                if apply_accents:
                    # Suggested must match clean's fold chain exactly:
                    # LATIN_ACCENTS/LIGATURES first (Ǣ→AE, not stripped Æ),
                    # then typographic/script maps, then strip_combining.
                    sugg = _sugg(ch)
                    if sugg != ch:
                        counts["accent"] = counts.get("accent", 0) + 1
                        spans.append(Span("accent", ch, sugg))
                else:
                    counts["nonascii"] = counts.get("nonascii", 0) + 1
                    spans.append(Span("nonascii", ch, _sugg(ch)))
            elif ucat.startswith("P"):
                counts["punctuation"] = counts.get("punctuation", 0) + 1
                spans.append(Span("punctuation", ch, _sugg(ch)))
            elif ucat.startswith("S"):
                counts["symbol"] = counts.get("symbol", 0) + 1
                spans.append(Span("symbol", ch, _sugg(ch)))
            else:
                counts["nonascii"] = counts.get("nonascii", 0) + 1
                spans.append(Span("nonascii", ch, _sugg(ch)))
            i += 1
            continue

        # Combining mark after ASCII base
        if unicodedata.category(ch) == "Mn":
            counts["accent"] = counts.get("accent", 0) + 1
            # clean strips Mn only right after an ASCII base; standalone or
            # after a non-ASCII char it survives (script marks are kept too
            # unless a script map folds them)
            prev = text[i - 1] if i > 0 else ""
            if apply_accents and prev and ord(prev) < 128:
                spans.append(Span("accent", ch, ""))
            else:
                spans.append(Span("accent", ch, _sugg(ch)))
            i += 1
            continue

        # Other non-ASCII
        if o > 127:
            # Cyrillic (U+0400-U+04FF) -> transliterate to ASCII (low risk)
            if 0x0400 <= o <= 0x04FF:
                counts["transliterate"] = counts.get("transliterate", 0) + 1
                spans.append(Span("transliterate", ch, _sugg(ch)))
            # Greek (U+0370-U+03FF) -> transliterate to ASCII (high risk, needs review)
            elif 0x0370 <= o <= 0x03FF:
                counts["transliterate_greek"] = counts.get("transliterate_greek", 0) + 1
                spans.append(Span("transliterate_greek", ch, _sugg(ch)))
            else:
                cat = classify_nonascii(ch)
                counts[cat] = counts.get(cat, 0) + 1
                spans.append(Span(cat, ch, _sugg(ch)))
            i += 1
            continue

        i += 1

    # HTML entities: &nbsp;, &amp;, &lt;, &#123;, etc.
    for m in _HTML_ENTITY_RE.finditer(text):
        counts["html_entity"] = counts.get("html_entity", 0) + 1
        spans.append(Span("html_entity", m.group(0), ""))

    # HTML tags: <div>, <span>, etc.
    for m in _HTML_TAG_RE.finditer(text):
        counts["html_tag"] = counts.get("html_tag", 0) + 1
        spans.append(Span("html_tag", m.group(0), ""))

    # Symbol noise runs: * %# @(() ^%$ etc.
    for m in _SYMBOL_NOISE_RE.finditer(text):
        counts["symbol_noise"] = counts.get("symbol_noise", 0) + 1
        spans.append(Span("symbol_noise", m.group(0), ""))

    # Repeated CJK punctuation: 、。、 etc.
    for m in _CJK_PUNCT_RE.finditer(text):
        counts["cjk_punct_repeat"] = counts.get("cjk_punct_repeat", 0) + 1
        spans.append(Span("cjk_punct_repeat", m.group(0), ""))

    # Repeated punctuation: !!! ??? ... etc.
    for m in _REPEATED_PUNCT_RE.finditer(text):
        counts["repeated_punct"] = counts.get("repeated_punct", 0) + 1
        spans.append(Span("repeated_punct", m.group(0), ""))

    class _Analysis:
        def __init__(self, spans, counts):
            self.spans = spans
            self.counts = counts

    return _Analysis(spans, counts)


def strip_combining(ch):
    """Strip combining marks from a decomposed char, return base or None."""
    decomposed = unicodedata.normalize("NFD", ch)
    base = "".join(c for c in decomposed if unicodedata.category(c) != "Mn")
    return base if base else None


def collapse_punctuation(text):
    """Collapse runs of ! ? . to single occurrence."""
    import re
    return re.sub(r"([!?.])\1{2,}", r"\1", text)
