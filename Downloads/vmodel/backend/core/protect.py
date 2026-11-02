"""Protect structural tokens (emails, URLs, money, phones, socials) with placeholders
so the cleaner never rewrites them."""
from __future__ import annotations

import re
from dataclasses import dataclass, field

# Order matters: URLs first (they can contain emails in query strings).
# Longer / more specific patterns must come before shorter overlapping ones.
_PATTERNS: list[tuple[str, re.Pattern]] = [
    ("url", re.compile(
        r"https?://[^\s<>\"']+|www\.[^\s<>\"']+|[a-zA-Z0-9.-]+\.(?:com|org|net|io|gov|edu|co|in|uk|de|fr|jp|cn)"
        r"(?:/[^\s<>\"']*)?", re.IGNORECASE)),
    ("email", re.compile(r"[a-zA-Z0-9._%+\-]+@[a-zA-Z0-9.\-]+\.[a-zA-Z]{2,}")),
    ("money", re.compile(
        r"(?:[$€£¥₹₽₩¢¤₿]\s?\d[\d,]*(?:\.\d{1,4})?|\d[\d,]*(?:\.\d{1,4})?\s?(?:USD|EUR|GBP|INR|JPY|CNY|RUB|KRW|AUD|CAD)\b)",
        re.IGNORECASE)),
    ("date_iso", re.compile(r"\b\d{4}-\d{2}-\d{2}\b")),
    ("phone", re.compile(
        r"(?<!\w)(?:\(\+\d{1,3}\)[\s\-./]?|\+\d{1,3}[\s\-./]?)?(?:\(\d{1,4}\)[\s\-./]?)?\d[\d\s\-./]{5,}\d(?!\w)")),
    ("uuid", re.compile(r"\b[0-9a-fA-F]{8}\-[0-9a-fA-F]{4}\-[0-9a-fA-F]{4}\-[0-9a-fA-F]{4}\-[0-9a-fA-F]{12}\b")),
]


PLACEHOLDER_TEMPLATE = "\x00PROT{id}\x00"


@dataclass
class ProtectionResult:
    text: str
    table: dict[str, str] = field(default_factory=dict)
    counts: dict[str, int] = field(default_factory=dict)


def protect(text: str) -> ProtectionResult:
    """Replace protected tokens with placeholders. Returns new text + restore table."""
    if not text:
        return ProtectionResult(text or "")
    table: dict[str, str] = {}
    counts: dict[str, int] = {}
    idx = 0

    def _sub(cat: str):
        def repl(m: re.Match) -> str:
            nonlocal idx
            key = str(idx)
            idx += 1
            table[key] = m.group(0)
            counts[cat] = counts.get(cat, 0) + 1
            return PLACEHOLDER_TEMPLATE.format(id=key)
        return repl

    result = text
    for cat, pat in _PATTERNS:
        result = pat.sub(_sub(cat), result)

    return ProtectionResult(text=result, table=table, counts=counts)


def restore(text: str, table: dict[str, str]) -> str:
    """Restore placeholders back to original tokens."""
    if not table or not text:
        return text
    for _ in range(len(table) + 1):
        prev = text
        for key, val in table.items():
            text = text.replace(PLACEHOLDER_TEMPLATE.format(id=key), val)
        if text == prev:
            break
    return text
