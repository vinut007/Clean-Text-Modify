"""Text detection: categorize accents, mojibake, emoji, symbols, invisible."""
from __future__ import annotations

from dataclasses import dataclass

import unicodedata

# Format/control characters that should be normalized or removed
INVISIBLE = {
    "\u00a0", "\u1680", "\u2000", "\u2001", "\u2002", "\u2003", "\u2004",
    "\u2005", "\u2006", "\u2007", "\u2008", "\u2009", "\u200a", "\u202f",
    "\u205f", "\u3000", "\u200b", "\u200c", "\u200d", "\u200e", "\u200f",
    "\ufeff",
}


@dataclass
class Span:
    category: str
    original: str
    suggested: str


def analyze_text(text, apply_accents=True, fold_scripts=False):
    """Return object with .spans (list of Span) and .counts (dict).

    Detects: mojibake, replacement, accent, invisible, symbol, emoji, punctuation, nonascii.
    """
    counts: dict[str, int] = {}
    spans: list[Span] = []

    i = 0
    n = len(text)
    while i < n:
        ch = text[i]
        o = ord(ch)

        # Replacement character
        if ch == "\ufffd":
            counts["replacement"] = counts.get("replacement", 0) + 1
            spans.append(Span("replacement", ch, "?"))
            i += 1
            continue

        # Invisible / control
        if ch in INVISIBLE:
            counts["invisible"] = counts.get("invisible", 0) + 1
            spans.append(Span("invisible", ch, ""))
            i += 1
            continue

        # Emoji / symbol ranges (non-Latin scripts kept if fold_scripts False)
        if 0x1F600 <= o <= 0x1F64F or 0x1F300 <= o <= 0x1F5FF or 0x1F680 <= o <= 0x1F6FF:
            counts["emoji"] = counts.get("emoji", 0) + 1
            spans.append(Span("emoji", ch, ""))
            i += 1
            continue

        # Non-ASCII letter with accent (Latin-1 Supplement + Latin Extended-A/B)
        if 0xC0 <= o <= 0x24F or 0x1E00 <= o <= 0x1EFF:
            if apply_accents:
                base = strip_combining(ch)
                if base and base != ch:
                    counts["accent"] = counts.get("accent", 0) + 1
                    spans.append(Span("accent", ch, base))
            else:
                counts["nonascii"] = counts.get("nonascii", 0) + 1
                spans.append(Span("nonascii", ch, ch))
            i += 1
            continue

        # Combining mark after ASCII base
        if unicodedata.category(ch) == "Mn":
            counts["accent"] = counts.get("accent", 0) + 1
            spans.append(Span("accent", ch, ""))
            i += 1
            continue

        # Other non-ASCII
        if o > 127:
            counts["nonascii"] = counts.get("nonascii", 0) + 1
            spans.append(Span("nonascii", ch, ch))
            i += 1
            continue

        i += 1

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
