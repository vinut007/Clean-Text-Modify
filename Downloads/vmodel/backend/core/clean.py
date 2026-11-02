"""Cleaning pipeline: mojibake fix -> protect -> normalize -> restore.

Guarantees:
  - protected tokens (emails, URLs, money, phones) byte-identical after restore
  - CJK/Hangul/Arabic etc preserved unless column flagged for transliteration
  - row count never changes (we only map cell->cell)
"""
from __future__ import annotations

from dataclasses import dataclass, field

import ftfy

from .detect import INVISIBLE, analyze_text, collapse_punctuation
from .mappings import (
    FULLWIDTH, LATIN_ACCENTS, LIGATURES, PRE_MOJIBAKE_FIX,
    SCRIPT_TO_LATIN, SYMBOL_TO_ASCII, TYPOGRAPHIC, is_emoji_remove,
    is_preserve_script, strip_combining,
)
from .protect import protect, restore

# textacy optional import (provides battle-tested noise normalization)
try:
    from textacy.preprocessing.normalize import repeating_chars as _tx_repeating_chars
    from textacy.preprocessing.normalize import whitespace as _tx_whitespace
    _HAS_TEXTACY = True
except ImportError:
    _HAS_TEXTACY = False

# contractions optional import (enrichment: don't -> do not, ASAP -> as soon
# as possible). Leaves money/IDs/ranges untouched (verified against
# Rs. 45,000 / AABCR1234F / 7.3-9.6% samples).
try:
    import contractions as _contractions_lib
    _HAS_CONTRACTIONS = True
except ImportError:
    _contractions_lib = None
    _HAS_CONTRACTIONS = False

# Pure-Python fallback used when the 'contractions' package is unavailable
# (e.g. Python 3.15: its pyahocorasick dep has no prebuilt wheel).
_CONTRACTION_MAP = {
    "i'm": "i am", "i've": "i have", "i'll": "i will", "i'd": "i would",
    "you're": "you are", "you've": "you have", "you'll": "you will", "you'd": "you would",
    "he's": "he is", "he'll": "he will", "he'd": "he would",
    "she's": "she is", "she'll": "she will", "she'd": "she would",
    "it's": "it is", "it'll": "it will", "it'd": "it would",
    "we're": "we are", "we've": "we have", "we'll": "we will", "we'd": "we would",
    "they're": "they are", "they've": "they have", "they'll": "they will", "they'd": "they would",
    "that's": "that is", "there's": "there is", "here's": "here is",
    "who's": "who is", "what's": "what is", "where's": "where is",
    "when's": "when is", "how's": "how is", "let's": "let us",
    "isn't": "is not", "aren't": "are not", "wasn't": "was not", "weren't": "were not",
    "don't": "do not", "doesn't": "does not", "didn't": "did not",
    "can't": "can not", "cannot": "can not", "couldn't": "could not",
    "won't": "will not", "wouldn't": "would not",
    "shouldn't": "should not", "mustn't": "must not", "needn't": "need not",
    "hasn't": "has not", "haven't": "have not", "hadn't": "had not",
}
_ABBREV_MAP = {
    "asap": "as soon as possible", "btw": "by the way", "thx": "thanks",
    "pls": "please", "plz": "please",
}


def _fallback_expand(text: str) -> str:
    """Minimal pure-Python contraction/abbreviation expander (case-preserving)."""
    import re

    def _keep_case(src: str, dst: str) -> str:
        if src.isupper():
            return dst.upper()
        if src[:1].isupper():
            return dst[:1].upper() + dst[1:]
        return dst

    def _sub_ct(m: "re.Match[str]") -> str:
        key = (m.group(1) + "'" + m.group(2)).lower()
        rep = _CONTRACTION_MAP.get(key)
        return _keep_case(m.group(1), rep) if rep else m.group(0)

    def _sub_ab(m: "re.Match[str]") -> str:
        rep = _ABBREV_MAP.get(m.group(0).lower())
        return _keep_case(m.group(0), rep) if rep else m.group(0)

    # word('|’)word contractions; also handle curly apostrophes
    text = re.sub(r"\b([A-Za-z]+)['\u2019]([A-Za-z]+)\b", _sub_ct, text)
    # whole-word abbreviations (ASAP, btw, Thx ...)
    text = re.sub(r"\b[A-Za-z]+\b", _sub_ab, text)
    return text


# Noise characters that are safe to collapse and strip at token edges
_NOISE_CHARS = "!@#$%^&*~`?|<>"
# Noise chars that are safe to strip at edges (sentence punctuation kept)
_EDGE_NOISE = "!@#$%^&*~`|<>"


def _collapse_repeating_noise(text: str) -> str:
    """Collapse runs of noise characters to a single occurrence.

    Uses textacy.repeating_chars when available (per-character calls since
    textacy treats chars as a pattern sequence, not individual chars).
    Falls back to regex when textacy is not installed.

    !!!heloo  -> !heloo
    ###test   -> #test
    hello!!!  -> hello!
    """
    if _HAS_TEXTACY:
        for ch in _NOISE_CHARS:
            text = _tx_repeating_chars(text, chars=ch, maxn=1)
        return text
    # Fallback: simple regex collapse
    import re
    for ch in _NOISE_CHARS:
        text = re.sub(re.escape(ch) + r"{2,}", ch, text)
    return text


def _normalize_whitespace(text: str) -> str:
    """Normalize whitespace using textacy when available."""
    if _HAS_TEXTACY:
        return _tx_whitespace(text)
    import re
    return re.sub(r"\s+", " ", text).strip()


def _utf8_mojibake_stats(data: bytes) -> tuple[int, int]:
    """Parse data as UTF-8, returning (valid_multibyte_seqs, invalid_lead_bytes)."""
    valid = invalid = 0
    i, n = 0, len(data)
    while i < n:
        b = data[i]
        if b < 0x80:
            i += 1
            continue
        if 0xC2 <= b <= 0xDF:
            ln = 2
        elif 0xE0 <= b <= 0xEF:
            ln = 3
        elif 0xF0 <= b <= 0xF4:
            ln = 4
        else:
            invalid += 1
            i += 1
            continue
        seq = data[i:i + ln]
        if len(seq) == ln and all(0x80 <= c <= 0xBF for c in seq[1:]):
            valid += 1
            i += ln
        else:
            invalid += 1
            i += 1
    return valid, invalid


def repair_broken_utf8_mojibake(text: str) -> str:
    """Repair UTF-8-read-as-cp1252 mojibake even when byte sequences are broken.

    ftfy re-decodes the whole string in one shot and abandons the repair when
    ANY byte sequence is invalid UTF-8 — which happens when a cp1252-undefined
    byte (0x81, 0x8D, 0x8F, 0x90, 0x9D) was dropped during the original
    corruption, or a stray byte was inserted. One broken sequence then blocks
    the entire fix, and the leftovers (Å¡, Ä, ×) get mangled by the ASCII
    folding step (× -> x, › -> >).

    So this walks the text in cp1252-encodable runs and re-decodes each run
    independently: valid sequences are repaired, orphaned lead bytes whose
    continuation was lost are dropped (that character is unrecoverable), and
    runs that don't look like UTF-8 mojibake are left untouched so legitimate
    text (Swedish 'Ångström', German 'Ära', '2×3') is never re-decoded.

    After the run pass, a word-level pass repairs MIXED-encoding text where
    some characters are already decoded (Polish ą ż Ł) while adjacent ones
    are still mojibake (Ã³ Ä‡ Å„) — the run pass alone can't fix these
    because the decoded chars break the cp1252-encodable runs.
    """
    if not text or text.isascii():
        return text
    # latin-1 flavor mojibake keeps C1 controls (U+0080-U+009F); cp1252 flavor
    # maps those bytes to printable specials (€ • œ š ...). Pick by content.
    enc = "latin-1" if any(0x80 <= ord(c) <= 0x9F for c in text) else "cp1252"
    out: list[str] = []
    run: list[str] = []
    buf = bytearray()

    def flush() -> None:
        if not run:
            return
        data = bytes(buf)
        original = "".join(run)
        run.clear()
        buf.clear()
        if len(data) < 2:
            out.append(original)
            return
        valid, invalid = _utf8_mojibake_stats(data)
        # confident mojibake: mostly valid UTF-8 sequences with a few broken ones
        if valid >= 2 and valid * 10 >= 7 * (valid + invalid):
            out.append(data.decode("utf-8", errors="ignore"))
        else:
            out.append(original)

    for ch in text:
        try:
            b = ch.encode(enc)
        except UnicodeEncodeError:
            # char outside the corruption encoding — boundary between runs
            flush()
            out.append(ch)
            continue
        run.append(ch)
        buf.extend(b)
    flush()
    result = "".join(out)
    # second pass: repair mixed-encoding words the run pass couldn't reach
    return _repair_mixed_encoding_words(result, enc)


def _repair_mixed_encoding_words(text: str, enc: str) -> str:
    """Repair individual mojibake fragments inside otherwise-clean words.

    Handles mixed-encoding text like Polish 'ZaążÃ³Łć' where the run-based
    pass can't help because decoded chars (ą ż Ł) break the cp1252 runs.
    For each 2-char fragment that encodes cleanly under the corruption
    encoding, try re-decoding as UTF-8 — if it yields a single letter,
    accept the replacement.
    """
    if not text or text.isascii():
        return text
    out: list[str] = []
    i = 0
    n = len(text)
    while i < n:
        ch = text[i]
        # fast path: ASCII passes through
        if ord(ch) < 128:
            out.append(ch)
            i += 1
            continue
        # try 2-char fragment starting at i
        matched = False
        if i + 1 < n:
            frag = text[i : i + 2]
            try:
                b = frag.encode(enc)
                if len(b) == 2:
                    decoded = b.decode("utf-8", errors="strict")
                    # accept only single-letter results (safe in word context)
                    if len(decoded) == 1 and decoded.isalpha() and ord(decoded) > 127:
                        out.append(decoded)
                        i += 2
                        matched = True
            except (UnicodeEncodeError, UnicodeDecodeError):
                pass
        if not matched:
            out.append(ch)
            i += 1
    return "".join(out)


@dataclass
class CleanOptions:
    fix_mojibake: bool = True
    fold_accents: bool = True          # café -> cafe
    normalize_invisible: bool = True   # NBSP -> space, ZWSP -> remove
    fold_symbols: bool = True          # curly quotes -> straight
    collapse_punctuation: bool = True  # !!!??? -> ! (high risk, needs approval)
    strip_noise_punct: bool = True     # strip leading/trailing punct+symbol noise per token
    keep_emoji: bool = False           # emoji removed by default in safe mode
    fold_scripts: bool = False         # β->b, л->l, Ա->A, ل->l (opt-in / strict)
    transliterate_columns: set[str] = field(default_factory=set)  # CJK->ascii only here
    enrich: bool = False               # expand contractions/abbreviations (don't -> do not)


@dataclass
class CellOutcome:
    original: str
    cleaned: str
    changed: bool
    counts: dict[str, int] = field(default_factory=dict)


def _strip_noise_punctuation(text: str, keep_emoji: bool = False) -> str:
    """Punctuation normalization disabled — text is returned unchanged.

    Kept as a no-op so callers/tests referencing it keep working while no
    leading/trailing/inner punctuation is ever stripped or collapsed.
    """
    return text


def clean_cell(text: str, opts: CleanOptions, column: str | None = None) -> CellOutcome:
    """Clean one cell. Returns original, cleaned, changed, category counts."""
    if text is None:
        return CellOutcome("", "", False, {})
    original = text if isinstance(text, str) else str(text)
    if not original:
        return CellOutcome(original, original, False, {})

    working = original

    # 0. Preprocessing: convert keycap number emojis to plain digits
    # 1️⃣ (U+0031 U+FE0F U+20E3) -> "1"
    import re as _re_pre
    working = _re_pre.sub(
        r"([0-9#*])\uFE0F?\u20E3",
        r"\1",
        working
    )

    # 0.5. Pre-ftfy fixes: euro-with-digits first, then pre-mojibake map
    # (sequences ftfy mangles). Sorted by length descending.
    # NOTE: standalone â€ -> a is NOT done here — it runs after ftfy (step 4)
    # so ftfy can repair longer mojibake sequences that start with â€.
    if opts.fix_mojibake:
        import re as _re
        working = _re.sub(r"â€(?=\d)", "€", working)                    # euro digits
        # pre-mojibake map first (ftfy-mangled sequences)
        for src in sorted(PRE_MOJIBAKE_FIX, key=len, reverse=True):
            if src in working:
                working = working.replace(src, PRE_MOJIBAKE_FIX[src])

    # 1. mojibake first (encoding-level repair, before protecting)
    if opts.fix_mojibake:
        # iterate: double/triple-encoded mojibake needs multiple passes;
        # stop when stable or after 4 passes to avoid pathological loops
        for _pass in range(4):
            prev = working
            # tolerant re-decode first: ftfy gives up on the whole string when any
            # byte sequence is invalid (dropped/inserted bytes), blocking repair
            working = repair_broken_utf8_mojibake(working)
            try:
                # uncurl_quotes follows fold_symbols so curly quotes are only
                # straightened when symbol folding is enabled
                working = ftfy.fix_text(working, uncurl_quotes=opts.fold_symbols)
            except Exception:
                pass
            if working == prev:
                break

    # 2. protect structural tokens
    # Convert superscript footnote markers to plain digits before protection,
    # so they aren't replaced by PROT placeholders and restored unchanged.
    if not opts.keep_emoji:
        working = "".join(SYMBOL_TO_ASCII.get(ch, ch) for ch in working)
    do_translit = column is not None and column in opts.transliterate_columns
    # 2b. fold dash/ellipsis/comparator family BEFORE protect. These map to
    # pure-punctuation ASCII (— → -, … → ..., → → ->, ≥ → >=) which the
    # noise stripper would eat if folded after strip (protect restores them
    # post-strip, and the next pass then deletes them → non-idempotent).
    if opts.fold_symbols or do_translit:
        working = (working.replace("\u2013", "-").replace("\u2014", "-")
                   .replace("\u2212", "-").replace("\u2026", "...")
                   .replace("\u2192", "->").replace("\u2190", "<-")
                   .replace("\u2265", ">=").replace("\u2264", "<="))
    # 2c. invisible chars / control codes / whitespace normalization — runs
    # BEFORE protect so \x00PROTn\x00 placeholder delimiters are never touched
    if opts.normalize_invisible:
        # space-like invisibles + ASCII whitespace -> normal space
        working = (working
                   .replace("\t", " ").replace("\n", " ").replace("\r", " ")
                   .replace("\u00a0", " ")   # NBSP → normal space
                   .replace("\u3000", " ")   # ideographic space → normal space
                   .replace("\u1680", " "))  # ogham space → normal space
        # collapse leftover exotic spaces → normal space
        for sp in "\u2000\u2001\u2002\u2003\u2004\u2005\u2006\u2007\u2008\u2009\u200a\u202f\u205f":
            working = working.replace(sp, " ")
        # format controls / joiners / bidi marks / BOM -> remove (no space
        # meaning). ZWJ is NOT removed here — it is meaningful inside emoji
        # sequences (mode 3 keeps emoji); the emoji-removal step strips it.
        for ctl in ("­", "‌", "⁠", "﻿",
                    "‎", "‏",
                    "‪", "‫", "‬", "‭", "‮",
                    "⁦", "⁧", "⁨", "⁩", "\u200b"):
            working = working.replace(ctl, "")
        # remaining C0 controls (NUL, BEL, ESC...) and DEL -> remove
        working = "".join(
            ch for ch in working
            if not (ord(ch) < 0x20 or ord(ch) == 0x7F))
    prot = protect(working)
    working = prot.text
    protected_text = prot.text  # analyze on protected text so URLs/money aren't miscounted

    # 4. per-char ASCII folding, aligned with the detector's suggestions:
    #   - accent letters (LATIN_ACCENTS/LIGATURES/Latin ranges) gated by fold_accents
    #   - typographic symbols (TYPOGRAPHIC/FULLWIDTH non-letters) gated by fold_symbols
    #   - combining marks (Mn) stripped ONLY after an ASCII base, so script-defining
    #     marks (Devanagari virama/anusvara, kana dakuten...) are never destroyed
    if opts.fold_accents or opts.fold_symbols or opts.fold_scripts or do_translit:
        import re as _re
        import unicodedata
        # standalone mojibake fragments ftfy leaves alone.
        # gate by fold_accents: Ã/ã are legitimate letters in Portuguese/French
        # (João, pão, garçon) and must not be folded when accents are kept.
        if opts.fold_accents or do_translit:
            working = _re.sub(r"â€(?!\d)", "a", working)      # â€ not followed by digit
            working = _re.sub(r"Ã(?![\xC0-\xFF])", "A", working)  # Ã not part of mojibake seq
            working = _re.sub(r"ã(?![\xC0-\xFF])", "a", working)
        ph_re = _re.compile(r"\x00PROT\d+\x00")
        out: list[str] = []
        prev_ascii = False
        i = 0
        n = len(working)
        while i < n:
            ch = working[i]
            # protection placeholders pass through untouched and break the ASCII chain
            if ch == "\x00":
                m = ph_re.match(working, i)
                if m:
                    out.append(m.group(0))
                    prev_ascii = False
                    i = m.end()
                    continue
            if ord(ch) < 128:
                out.append(ch)
                prev_ascii = True
                i += 1
                continue
            o = ord(ch)
            folded = None
            if ch in LATIN_ACCENTS or ch in LIGATURES:
                if opts.fold_accents or do_translit:
                    folded = LATIN_ACCENTS.get(ch) or LIGATURES.get(ch)
            elif ch in TYPOGRAPHIC:
                # invisible chars normalize only when normalize_invisible is on
                if (opts.fold_symbols or do_translit) and not (
                        ch in INVISIBLE and not opts.normalize_invisible):
                    folded = TYPOGRAPHIC[ch]
            elif ch in FULLWIDTH:
                # fullwidth letters stay (detector classifies them nonascii/preserve);
                # fullwidth digits/punctuation fold to ASCII
                if (opts.fold_symbols or do_translit) and not unicodedata.category(ch).startswith("L"):
                    folded = FULLWIDTH[ch]
            elif (opts.fold_scripts or do_translit) and ch in SCRIPT_TO_LATIN:
                # non-Latin script -> English letters (β→b, л→l, Ա→A, ل→l);
                # strict mode (do_translit) implies this before the final
                # non-ASCII strip, so scripts transliterate instead of vanish
                folded = SCRIPT_TO_LATIN[ch]
            elif (0xC0 <= o <= 0x24F or 0x1E00 <= o <= 0x1EFF) and (
                    opts.fold_accents or do_translit) and unicodedata.category(ch).startswith("L"):
                # uncovered Latin letter — same strip_combining fallback the detector suggests
                base = strip_combining(ch)
                if base and base != ch and all(ord(c) < 128 for c in base):
                    folded = base
            if folded is not None:
                if folded:
                    out.append(folded)
                    prev_ascii = True  # every mapped value is pure ASCII
                # empty fold (e.g. ZWSP -> "") drops the char; prev_ascii unchanged
                i += 1
                continue
            # decomposed accent: strip combining mark only when base is ASCII
            if (opts.fold_accents or do_translit) and unicodedata.category(ch) == "Mn" and prev_ascii:
                i += 1
                continue
            out.append(ch)
            prev_ascii = ord(ch) < 128
            i += 1
        working = "".join(out)

    # 4b. collapse repeated punctuation noise (!!!??? -> !) — high risk, needs approval
    if opts.collapse_punctuation:
        working = collapse_punctuation(working)

    # 4c. strip leading/trailing punctuation+symbol noise per token
    #     hello!!!!@$ -> hello!   #@#$1232 -> $1232   fiopfi<ana -> fiopfi<ana
    if opts.strip_noise_punct:
        working = _strip_noise_punctuation(working, keep_emoji=opts.keep_emoji)

    # 5. Emoji removal (typographic symbols like © ® ™ × ÷ etc. kept as-is)
    if not opts.keep_emoji:
        import re as _re
        # Remove emoji/symbol ranges via helper, but preserve non-Latin scripts
        working = "".join(
            ch for ch in working
            if not is_emoji_remove(ch) or is_preserve_script(ch)
        )
        # Remove decorative symbols listed in SYMBOL_TO_ASCII
        working = "".join(SYMBOL_TO_ASCII.get(ch, ch) for ch in working)
        # Remove orphaned ZWJ left after emoji removal
        working = working.replace("\u200d", "")
    if do_translit:
        # Strict mode: romanize remaining non-ASCII instead of deleting (anyascii),
        # covering 124k chars / Unicode 16 — beats unidecode on CJK/Cyrillic/Greek.
        # Falls back to deletion if anyascii isn't installed (e.g. Python 3.15 has
        # no lingua wheel, but anyascii does ship a cp315 wheel).
        try:
            import anyascii
            working = anyascii.anyascii(working)
        except Exception:
            import re as _re
            working = _re.sub(r"[^\x00-\x7F]", "", working)

    # 5a. collapse internal whitespace runs left behind by removals:
    #   "Hello 😀 world" -> "Hello world" (emoji gone, single space)
    #   "hello\xa0world" -> "hello world"
    # only runs of 2+ spaces INSIDE the cell; leading/trailing spaces untouched,
    # protected tokens are still placeholders here so URLs/money can't be split
    if opts.normalize_invisible:
        import re as _re
        working = _re.sub(r" {2,}", " ", working)

    # 5b. NFC normalize result
    import unicodedata
    working = unicodedata.normalize("NFC", working)

    # 6. restore protected tokens byte-identical
    working = restore(working, prot.table)

    # 6.5. Final accent fold on restored text. Protection may have grabbed
    #      chunks containing non-ASCII (e.g. protected_regex over-matching on
    #      slash-delimited text). Those accents were skipped during the
    #      per-char fold (step 4) because placeholders pass through untouched.
    #      Fold them now so the output is consistently ASCII-clean.
    if opts.fold_accents and any(ord(c) > 127 for c in working):
        import unicodedata
        working = "".join(
            LATIN_ACCENTS.get(ch, ch) if ch in LATIN_ACCENTS else ch
            for ch in working
        )

    # 6a. trim edge whitespace left by removals/collapses ("  test " -> "test").
    # Protected tokens are \x00PROTn\x00 placeholders here (no edge spaces),
    # so trimming cannot touch restored money/URL/JSON content.
    if opts.normalize_invisible:
        working = working.strip()

    # 6b. optional enrichment: expand contractions & common abbreviations
    # (don't -> do not, we'll -> we will, ASAP -> AS SOON AS POSSIBLE).
    # Runs after restore on final text; the contractions library leaves
    # money/IDs/ranges/phones untouched. Failure never blocks cleaning.
    # Uses the 'contractions' package when installed, else pure-Python fallback.
    if opts.enrich and any(c.isalpha() for c in working):
        try:
            if _HAS_CONTRACTIONS:
                working = _contractions_lib.fix(working)
            else:
                working = _fallback_expand(working)
        except Exception:
            pass

    # 7. compute counts for reporting (on protected text so URLs/money aren't miscounted)
    analysis = analyze_text(protected_text, apply_accents=opts.fold_accents,
                            fold_scripts=(opts.fold_scripts or do_translit))
    counts = dict(analysis.counts)
    for k, v in prot.counts.items():
        counts[f"protected_{k}"] = v

    changed = working != original
    return CellOutcome(original=original, cleaned=working, changed=changed, counts=counts)


def clean_column(values: list[str], opts: CleanOptions, column: str) -> list[CellOutcome]:
    return [clean_cell(v, opts, column) for v in values]
