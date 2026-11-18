"""Protect structural tokens (emails, URLs, money, phones, socials) with placeholders
so the cleaner never rewrites them."""
from __future__ import annotations

import re
from dataclasses import dataclass, field

# ---------------------------------------------------------------------------
# Currency symbols — single source of truth for the whole pipeline
# (protect, detect, sentence case). Covers ASCII $, Latin-1 ¢ £ ¤ ¥, the
# whole Unicode "Currency Symbols" block U+20A0-U+20CF (€ ₹ ₽ ₩ ₪ ₫ ₦ ₱ ₸
# ₺ ₼ ₾ ₿ ...) and signs outside the block (؋ ֏ ฿ ៛ ﷼ ৳ ૱ ௹ ৲ ৻ ꠸ ߾ ߿
# 𑿝 𑿞 𑿟 𑿠 𞋿 𞲰 ƒ). Every Unicode category-Sc char + ƒ florin is covered.
# Fullwidth forms ￠ ￡ ￥ ￦ ＄ are deliberately NOT here: ftfy/FULLWIDTH
# normalize them to ¢ £ ¥ ₩ $ before protect() runs, and the standard
# symbols below are what gets wrapped (keeping them would break parity).
# ---------------------------------------------------------------------------
CURRENCY_CLASS = (
    r"$\u00a2\u00a3\u00a4\u00a5"
    r"\u20a0-\u20cf"
    r"؋֏฿៛﷼"
    r"৲৳৻૱"
    r"৹\u0BF9꠸"
    r"߾߿"
    r"𑿝𑿞𑿟𑿠"
    r"𞋿𞲰"
    r"ƒ﹩"
)
CURRENCY_SYMBOLS_RE = re.compile(f"[{CURRENCY_CLASS}]")

# ISO 4217 currency codes for money amounts. Always used adjacent to digits
# so prose words like "try"/"all"/"top" are never mistaken for currency.
MONEY_CODES = (
    "USD|EUR|GBP|JPY|CNY|INR|RUB|KRW|AUD|CAD|CHF|MXN|BRL|SGD|HKD|NZD|"
    "TRY|SEK|NOK|DKK|PLN|CZK|HUF|RON|BGN|UAH|ILS|AED|SAR|QAR|KWD|BHD|"
    "OMR|JOD|LBP|EGP|NGN|KES|GHS|MAD|TND|ZAR|IDR|MYR|THB|VND|PHP|PKR|"
    "BDT|LKR|NPR|AFN|AMD|AZN|BYN|GEL|KZT|KGZ|MNT|UZS|TJS|TMT|ETB|ZMW|"
    "TZS|UGX|RWF|MZN|AOA|XOF|XAF|XPF|XCD|BSD|BBD|JMD|TTD|KYD|BMD|"
    "ANG|SRD|GYD|HTG|DOP|CRC|PAB|NIO|HNL|GTQ|BOB|CLP|COP|PEN|PYG|UYU|"
    "ARS|VES|GIP|FKP|SHP|FJD|PGK|VUV|WST|NAD|BWP|LSL|SZL|MWK|SOS|"
    "DJF|ERN|SDG|LYD|MRU|CVE|GMD|GNF|SLL|LRD|SLE|STN|CDF|BIF|KMF|"
    "MUR|SCR|LAK|KHR|MMK|TWD"
)

# Money amounts in any casing: "50 eur", "EUR 50", "100 chf"
MONEY_CONTEXT_RE = re.compile(
    rf"\b\d[\d,]*(?:\.\d+)?\s?(?:{MONEY_CODES})\b"
    rf"|(?:{MONEY_CODES})\s?\d[\d,]*",
    re.IGNORECASE,
)

# Common codes protected even standalone (sentence case must not lowercase
# "EUR"/"CHF" in prose like "price EUR"); kept short so English words that
# double as codes (try/all/top/pen/mad/gel...) stay out.
COMMON_MONEY_CODES = "USD|EUR|GBP|JPY|CNY|INR|RUB|KRW|AUD|CAD|CHF"

# Order matters: URLs first (they can have emails in query strings).
# Longer or more specific patterns must come before shorter overlapping ones.
_PATTERNS: list[tuple[str, re.Pattern]] = [
    ("url", re.compile(
        r"https?://[^\s<>\"']+|www\.[^\s<>\"']+|[a-zA-Z0-9.-]+\.(?:"
        # longer TLDs first: info before in, design/dev before de,
        # click/cloud/club before cl, group before gr, photo before ph,
        # play before pl, art before ar; (?![a-zA-0-9]) stops mid-word
        # matches like example.information -> example.in
        r"info|design|dev|click|cloud|club|group|photo|play|music|online|"
        r"store|studio|today|world|email|wiki|work|link|life|live|page|news|"
        r"site|fun|tech|top|win|app|art|xyz|"
        r"ai|me|us|ca|au|nl|es|it|br|ru|kr|za|sg|hk|nz|ie|be|dk|fi|pl|cz|"
        r"ro|gr|tr|il|ae|sa|qa|eg|ng|ke|gh|pk|bd|lk|np|vn|th|my|id|ph|mx|"
        r"ar|cl|pe|eu|ch|se|no|at|pt|hu|bg|ua|by|kz|tw|"
        r"com|org|net|io|gov|edu|in|uk|de|fr|jp|cn|co"
        r")(?![a-zA-Z0-9])(?:/[^\s<>\"']*)?", re.IGNORECASE)),
    ("email", re.compile(r"[a-zA-Z0-9._%+\-]+@[a-zA-Z0-9.\-]+\.[a-zA-Z]{2,}")),
    ("money", re.compile(
        rf"(?:[{CURRENCY_CLASS}]\s?\d[\d,]*(?:\.\d{{1,4}})?"
        rf"|\d[\d,]*(?:\.\d{{1,4}})?\s?(?:{MONEY_CODES})\b)",
        re.IGNORECASE)),
    ("date_iso", re.compile(r"\b\d{4}-\d{2}-\d{2}\b")),
    ("phone", re.compile(
        r"(?<!\w)(?:\(\+\d{1,3}\)[\s\-./]?|\+\d{1,3}[\s\-./]?)?(?:\(\d{1,4}\)[\s\-./]?)?\d[\d\s\-./]{5,}\d(?!\w)")),
    ("uuid", re.compile(r"\b[0-9a-fA-F]{8}\-[0-9a-fA-F]{4}\-[0-9a-fA-F]{4}\-[0-9a-fA-F]{4}\-[0-9a-fA-F]{12}\b")),
    # Bullet points preserved exactly as-is (never modified)
    ("bullet", re.compile(r"[•°]")),
    # Pipe (|) preserved exactly as-is — table/text separators are content
    ("pipe", re.compile(r"\|")),
    # Currency symbols preserved exactly as-is (never converted to text)
    ("currency", CURRENCY_SYMBOLS_RE),
    # Logical NOT sign preserved as-is
    ("not_sign", re.compile(r"¬")),
    # Legal/typo signs preserved exactly as-is — never romanized by
    # anyascii (fold_scripts/strict) and never removed as emoji
    ("sign", re.compile("[©®™]")),
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
