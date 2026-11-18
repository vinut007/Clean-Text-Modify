"""Cell annotation helpers shared by the CLI and the streaming pool workers.

Kept free of CLI dependencies (no stdin, no Rich, no Progress) so
backend.core.stream_clean workers can import them in child processes.
The ANSI helpers live here because _diff_context renders colors for the
interactive review; _sanitize_cell strips those escapes before export.
"""
from __future__ import annotations

import re

from backend.core.clean import CleanOptions
from backend.core.protect import (
    COMMON_MONEY_CODES,
    MONEY_CONTEXT_RE,
    protect as protect_fn,
    restore as restore_fn,
)
from backend.core.detect import analyze_text, _is_empty_garbage

RESET = "\033[0m"
BOLD = "\033[1m"
FG_RED = "\033[31m"
FG_GREEN = "\033[32m"
FG_YELLOW = "\033[33m"


def c(text: str, *styles: str) -> str:
    return f"{''.join(styles)}{text}{RESET}"


_CAT_DISPLAY = {
    "mojibake": "Mojibake",
    "replacement": "Replacement_Character",
    "invalid_utf8": "Invalid_UTF8",
    "accent": "Accent",
    "invisible": "Invisible_Char",
    "symbol": "Symbol",
    "emoji": "Emoji",
    "punctuation": "Punctuation",
    "nonascii": "NonASCII",
    "transliterate": "Transliterate",
    "transliterate_greek": "Transliterate_Greek",
    "empty_garbage": "Empty_Garbage",
    "html_entity": "HTML_Entity",
    "html_tag": "HTML_Tag",
    "symbol_noise": "Symbol_Noise",
    "repeated_punct": "Repeated_Punct",
    "cjk_punct_repeat": "CJK_Punct_Repeat",
}

REAL_ERROR_CATS = {"mojibake", "replacement", "invalid_utf8", "accent",
                   "invisible", "symbol", "emoji", "punctuation",
                   "empty_garbage", "html_entity", "html_tag",
                   "symbol_noise", "repeated_punct", "cjk_punct_repeat"}


# XML 1.0 legal characters only: tab/LF/CR, #x20-#xD7FF, #xE000-#xFFFD,
# and the supplementary planes. Anything else (C0/C1 controls, lone
# surrogates, U+FFFE/U+FFFF) makes lxml/openpyxl raise
# "All strings must be XML compatible".
_XML_ILLEGAL_RE = re.compile(
    "[^\t\n\r\x20-\ud7ff\ue000-\ufffd\U00010000-\U0010ffff]"
)


def _sanitize_cell(value):
    """Strip ANSI escapes and every XML-illegal character from a cell value
    before export so openpyxl/lxml never sees control chars or lone
    surrogates. clean_cell() already restores protection placeholders via
    restore(); this is the final write-boundary gate (idempotent)."""
    if not isinstance(value, str):
        return value
    value = re.sub(r"\x1b\[[0-9;]*[a-zA-Z]", "", value)
    value = value.replace("\x1b", "")
    return _XML_ILLEGAL_RE.sub("", value)


def _short(s: str, n: int = 100) -> str:
    """Head + tail preview for long cell values (readability)."""
    if not s:
        return s
    if len(s) <= n:
        return s
    half = n // 2
    return f"{s[:half]} …({len(s)} chars)… {s[-half:]}"


def _diff_context(original: str, cleaned: str, width: int = 30) -> str:
    """Show compact left-context + changed-portion + right-context.

    Original chars in RED, replacement chars in GREEN:
    '...left [ORIG -> REPL] right...'
    Long values are short-formed so reviews stay readable.
    """
    MID_MAX = 120
    if not original or original == cleaned:
        return c(f"{_short(original)!r} -> {_short(cleaned)!r}", FG_YELLOW)

    n = min(len(original), len(cleaned))
    first = 0
    while first < n and original[first] == cleaned[first]:
        first += 1
    last = 0
    while last < n and original[len(original) - 1 - last] == cleaned[len(cleaned) - 1 - last]:
        last += 1

    mid_o = original[first:len(original) - last]
    mid_c = cleaned[first:len(cleaned) - last]

    # Long texts: tiny window around the change only
    if len(original) > 400 or len(cleaned) > 400:
        left = _short(original[max(0, first - 40):first], 60)
        right = _short(original[len(original) - last:len(original) - last + 40], 60)
        return (
            f"{c(left, FG_YELLOW)} "
            f"[{c(_short(mid_o, 80), FG_RED)} -> {c(_short(mid_c, 80), FG_GREEN)}] "
            f"{c(right, FG_YELLOW)}"
        )

    left_start = max(0, first - width)
    right_end = min(len(original), len(original) - last + width)
    left = original[left_start:first]
    right = original[len(original) - last:right_end]
    l_ell = "…" if left_start > 0 else ""
    r_ell = "…" if right_end < len(original) else ""
    if len(mid_o) > MID_MAX:
        mid_o = mid_o[: MID_MAX // 2] + " …(truncated)… " + mid_o[-(MID_MAX // 2):]
        mid_c = mid_c[: MID_MAX // 2] + " …(truncated)… " + mid_c[-(MID_MAX // 2):]
    return (
        f"{c(l_ell, FG_YELLOW)}{c(left, FG_YELLOW)} "
        f"[{c(mid_o, FG_RED)} -> {c(mid_c, FG_GREEN)}] "
        f"{c(right, FG_YELLOW)}{c(r_ell, FG_YELLOW)}"
    )


def _cell_errors(text: str, column: str, opts: CleanOptions) -> list[str]:
    if not isinstance(text, str) or not text:
        return []
    pr = protect_fn(text)
    do_translit = column in (opts.transliterate_columns or set())
    an = analyze_text(pr.text, apply_accents=opts.fold_accents,
                      fold_scripts=(opts.fold_scripts or do_translit),
                      fold_symbols=opts.fold_symbols,
                      keep_emoji=opts.keep_emoji,
                      normalize_invisible=opts.normalize_invisible,
                      fix_mojibake=opts.fix_mojibake,
                      do_translit=do_translit,
                      collapse_punct=opts.collapse_punctuation)
    # empty_garbage is judged on the RAW cell: protect() can hide digits inside
    # money tokens ("#@#$1232" -> "#@#"+PROT looks garbage), which would
    # falsely label a real value as garbage. Only keep the span when the raw
    # text itself has no letters/digits.
    raw_garbage = _is_empty_garbage(text)
    found: list[str] = []
    for sp in an.spans:
        cat = sp.category
        if cat == "empty_garbage" and not raw_garbage:
            continue
        if cat not in REAL_ERROR_CATS:
            # nonascii / transliterate categories: show only when the span
            # claims a real fold (suggestion differs). Identity keeps (CJK
            # kept, unmapped scripts) are noise — cell-level fallback covers
            # changes these spans don't represent.
            if cat not in ("nonascii", "transliterate", "transliterate_greek"):
                continue
            if sp.suggested == sp.original:
                continue
        if cat.startswith("protected_"):
            continue
        # Restore any protection placeholders back to original tokens for display
        original = restore_fn(sp.original, pr.table)
        suggested = restore_fn(sp.suggested, pr.table)
        label = _CAT_DISPLAY.get(cat, cat)
        found.append(f"{label}:{original}→{suggested}")
    seen: set[str] = set()
    uniq: list[str] = []
    for item in found:
        if item not in seen:
            seen.add(item)
            uniq.append(item)
    return uniq


def _esc_display(s: str) -> str:
    """Escape control chars / line separators so annotations stay one line."""
    out: list[str] = []
    for ch in s:
        o = ord(ch)
        if ch == "\n":
            out.append("\\n")
        elif ch == "\r":
            out.append("\\r")
        elif ch == "\t":
            out.append("\\t")
        elif o < 0x20 or o == 0x7F:
            out.append(f"\\x{o:02x}")
        elif o in (0x2028, 0x2029) or 0x202A <= o <= 0x202E:
            out.append(f"\\u{o:04x}")
        else:
            out.append(ch)
    return "".join(out)


def _mark_fixed(errs: list[str], original: str, cleaned: str) -> list[str]:
    """Annotate each detected error with its outcome on this cell:
    ✓fixed when the original error text is gone from the cleaned value,
    ✗kept when it survives (rejected pattern, protected, or mode keeps it)."""
    marked: list[str] = []
    for e in errs:
        _label, sep, rest = e.partition(":")
        if not sep:
            marked.append(e)
            continue
        orig_text = rest.partition("→")[0]
        status = "✗kept" if (orig_text and orig_text in cleaned) else "✓fixed"
        marked.append(f"{e} {status}")
    return marked


def _sentence_case(s: str) -> str:
    """Sentence-case a cell: lowercase everything, cap the first cased letter
    of the cell and of each sentence (after . ! ?). Protected tokens (URLs,
    emails, money, phones, bullets, currency signs/codes) keep their case."""
    import re
    if not isinstance(s, str) or not s:
        return s
    # Pre-protect tokens protect() would fragment or miss: its URL pattern
    # steals email domains, and money matches only "€50" (not "50 EUR").
    my_table: dict[str, str] = {}

    def _pre(m: "re.Match") -> str:
        key = str(1000000 + len(my_table))
        my_table[key] = m.group(0)
        return f"\x00PROT{key}\x00"

    text = re.sub(r"[a-zA-Z0-9._%+\-]+@[a-zA-Z0-9.\-]+\.[a-zA-Z]{2,}",
                  _pre, s)
    # money amounts in any casing ("50 eur", "EUR 50") + common codes
    # standing alone ("price EUR") — every ISO 4217 code, digits-adjacent
    text = MONEY_CONTEXT_RE.sub(_pre, text)
    text = re.sub(rf"\b(?:{COMMON_MONEY_CODES})\b", _pre, text,
                  flags=re.IGNORECASE)
    pr = protect_fn(text)
    table = dict(pr.table)
    table.update(my_table)
    segments = re.split(r"(\x00PROT\d+\x00)", pr.text)
    first_done = False
    for i in range(0, len(segments), 2):
        seg = segments[i]
        if not seg:
            continue
        low = seg.lower()
        if not first_done:
            for j, ch in enumerate(low):
                if ch.isalpha() and ch.upper() != ch:
                    low = low[:j] + ch.upper() + low[j + 1:]
                    first_done = True
                    break
        low = re.sub(
            r"([.!?][\"')\]]*\s+)([^\W\d_])",
            lambda m: m.group(1) + m.group(2).upper(),
            low,
        )
        segments[i] = low
    return restore_fn("".join(segments), table)
