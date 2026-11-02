"""Curated safe non-ASCII -> ASCII replacement maps."""
from __future__ import annotations

import unicodedata

# Latin-1 supplement / Latin Extended-A letters with diacritics -> base ASCII letter
LATIN_ACCENTS: dict[str, str] = {
    "À": "A", "Á": "A", "Â": "A", "Ã": "A", "Ä": "A", "Å": "A", "Æ": "AE",
    "Ç": "C", "È": "E", "É": "E", "Ê": "E", "Ë": "E", "Ì": "I", "Í": "I",
    "Î": "I", "Ï": "I", "Ð": "D", "Ñ": "N", "Ò": "O", "Ó": "O", "Ô": "O",
    "Õ": "O", "Ö": "O", "Ø": "O", "Ù": "U", "Ú": "U", "Û": "U", "Ü": "U",
    "Ý": "Y", "Þ": "Th", "ß": "ss",
    "à": "a", "á": "a", "â": "a", "ã": "a", "ä": "a", "å": "a", "æ": "ae",
    "ç": "c", "è": "e", "é": "e", "ê": "e", "ë": "e", "ì": "i", "í": "i",
    "î": "i", "ï": "i", "ð": "d", "ñ": "n", "ò": "o", "ó": "o", "ô": "o",
    "õ": "o", "ö": "o", "ø": "o", "ù": "u", "ú": "u", "û": "u", "ü": "u",
    "ý": "y", "þ": "th", "ÿ": "y",
    "Ā": "A", "ā": "a", "Ă": "A", "ă": "a", "Ą": "A", "ą": "a",
    "Ć": "C", "ć": "c", "Ĉ": "C", "ĉ": "c", "Ċ": "C", "ċ": "c", "Č": "C", "č": "c",
    "Ď": "D", "ď": "d", "Đ": "D", "đ": "d",
    "Ē": "E", "ē": "e", "Ĕ": "E", "ĕ": "e", "Ė": "E", "ė": "e", "Ę": "E", "ę": "e", "Ě": "E", "ě": "e",
    "Ĝ": "G", "ĝ": "g", "Ğ": "G", "ğ": "g", "Ġ": "G", "ġ": "g", "Ģ": "G", "ģ": "g",
    "Ĥ": "H", "ĥ": "h", "Ħ": "H", "ħ": "h",
    "Ĩ": "I", "ĩ": "i", "Ī": "I", "ī": "i", "Ĭ": "I", "ĭ": "i", "Į": "I", "į": "i", "İ": "I", "ı": "i",
    "Ĵ": "J", "ĵ": "j",
    "Ķ": "K", "ķ": "k", "ĸ": "k",
    "Ĺ": "L", "ĺ": "l", "Ļ": "L", "ļ": "l", "Ľ": "L", "ľ": "l", "Ł": "L", "ł": "l",
    "Ń": "N", "ń": "n", "Ņ": "N", "ņ": "n", "Ň": "N", "ň": "n", "ŉ": "n",
    "Ō": "O", "ō": "o", "Ŏ": "O", "ŏ": "o", "Ő": "O", "ő": "o", "Œ": "OE", "œ": "oe",
    "Ŕ": "R", "ŕ": "r", "Ŗ": "R", "ŗ": "r", "Ř": "R", "ř": "r",
    "Ś": "S", "ś": "s", "Ŝ": "S", "ŝ": "s", "Ş": "S", "ş": "s", "Š": "S", "š": "s",
    "Ţ": "T", "ţ": "t", "Ť": "T", "ť": "t", "Ŧ": "T", "ŧ": "t",
    "Ũ": "U", "ũ": "u", "Ū": "U", "ū": "u", "Ŭ": "U", "ŭ": "u", "Ů": "U", "ů": "u",
    "Ű": "U", "ű": "u", "Ų": "U", "ų": "u",
    "Ŵ": "W", "ŵ": "w",
    "Ŷ": "Y", "ŷ": "y", "Ÿ": "Y",
    "Ź": "Z", "ź": "z", "Ż": "Z", "ż": "z", "Ž": "Z", "ž": "z",
    # Latin Extended-B
    "ƀ": "b", "Ɓ": "B", "Ƃ": "B", "ƃ": "b", "Ƅ": "b", "ƅ": "b", "Ɔ": "O", "Ƈ": "C",
    "ƈ": "c", "Ɖ": "D", "Ɗ": "D", "Ƌ": "d", "ƌ": "d", "ƍ": "d", "Ǝ": "E", "Ə": "E",
    "Ɛ": "E", "Ƒ": "F", "ƒ": "f", "Ɠ": "G", "ɢ": "g", "Ɣ": "G", "Ɩ": "I", "Ɨ": "I",
    "Ƙ": "K", "ƙ": "k", "ƚ": "l", "ƛ": "l", "Ɯ": "W", "Ɲ": "N", "ƞ": "n", "Ɵ": "O",
    "Ơ": "O", "ơ": "o", "Ƣ": "P", "ƣ": "p", "Ƥ": "P", "ƥ": "p", "Ʀ": "R", "Ƨ": "S",
    "ƨ": "s", "Ʃ": "S", "ƪ": "s", "ƫ": "t", "Ƭ": "T", "ƭ": "t", "Ʈ": "T", "Ư": "U",
    "ư": "u", "Ʊ": "U", "Ʋ": "V", "Ƴ": "Y", "ƴ": "y", "Ƶ": "Z", "ƶ": "z", "Ʒ": "Z",
    "Ƹ": "Z", "ƹ": "z", "ƺ": "z", "ƻ": "f", "Ƽ": "O", "ƽ": "o", "ƾ": "o", "ƿ": "w",
    "ǀ": "|", "ǁ": "|", "ǂ": "|", "ǃ": "!", "Ǆ": "D", "ǅ": "D", "ǆ": "d", "Ǉ": "L",
    "ǈ": "L", "ǉ": "l", "Ǌ": "N", "ǋ": "N", "ǌ": "n", "Ǎ": "A", "ǎ": "a", "Ǐ": "I",
    "ǐ": "i", "Ǒ": "O", "ǒ": "o", "Ǔ": "U", "ǔ": "u", "Ǖ": "U", "ǖ": "u", "Ǘ": "U",
    "ǘ": "u", "Ǚ": "U", "ǚ": "u", "Ǜ": "U", "ǜ": "u", "ǝ": "e", "Ǟ": "A", "ǟ": "a",
    "Ǡ": "A", "ǡ": "a", "Ǣ": "E", "ǣ": "e", "Ǥ": "G", "ǥ": "g", "Ǧ": "G", "ǧ": "g",
    "Ǩ": "K", "ǩ": "k", "Ǫ": "O", "ǫ": "o", "Ǭ": "O", "ǭ": "o", "Ǯ": "Z", "ǯ": "z",
    "ǰ": "j", "Ǳ": "D", "ǲ": "D", "ǳ": "d", "Ǵ": "G", "ǵ": "g", "Ƕ": "H", "Ƿ": "W",
    "Ǹ": "N", "ǹ": "n", "Ǻ": "A", "ǻ": "a", "Ǽ": "AE", "ǽ": "ae", "Ǿ": "O", "ǿ": "o",
    # Vietnamese precomposed (tone marks)
    "À": "A", "Á": "A", "Ả": "A", "Ã": "A", "Ạ": "A", "Â": "A", "Ầ": "A", "Ấ": "A",
    "Ẩ": "A", "Ẫ": "A", "Ậ": "A", "Ă": "A", "Ằ": "A", "Ắ": "A", "Ẳ": "A", "Ẵ": "A",
    "Ặ": "A", "È": "E", "É": "E", "Ẻ": "E", "Ẽ": "E", "Ẹ": "E", "Ê": "E", "Ề": "E",
    "Ế": "E", "Ể": "E", "Ễ": "E", "Ệ": "E", "Ì": "I", "Í": "I", "Ỉ": "I", "Ĩ": "I",
    "Ị": "I", "Ò": "O", "Ó": "O", "Ỏ": "O", "Õ": "O", "Ọ": "O", "Ô": "O", "Ồ": "O",
    "Ố": "O", "Ổ": "O", "Ỗ": "O", "Ộ": "O", "Ơ": "O", "Ờ": "O", "Ớ": "O", "Ở": "O",
    "Ỡ": "O", "Ợ": "O", "Ù": "U", "Ú": "U", "Ủ": "U", "Ũ": "U", "Ụ": "U", "Ư": "U",
    "Ừ": "U", "Ứ": "U", "Ử": "U", "Ữ": "U", "Ự": "U", "Ỳ": "Y", "Ý": "Y", "Ỷ": "Y",
    "Ỹ": "Y", "Ỵ": "Y", "Đ": "D",
    "à": "a", "á": "a", "ả": "a", "ã": "a", "ạ": "a", "â": "a", "ầ": "a", "ấ": "a",
    "ẩ": "a", "ẫ": "a", "ậ": "a", "ă": "a", "ằ": "a", "ắ": "a", "ẳ": "a", "ẵ": "a",
    "ặ": "a", "è": "e", "é": "e", "ẻ": "e", "ẽ": "e", "ẹ": "e", "ê": "e", "ề": "e",
    "ế": "e", "ể": "e", "ễ": "e", "ệ": "e", "ì": "i", "í": "i", "ỉ": "i", "ĩ": "i",
    "ị": "i", "ò": "o", "ó": "o", "ỏ": "o", "õ": "o", "ọ": "o", "ô": "o", "ồ": "o",
    "ố": "o", "ổ": "o", "ỗ": "o", "ộ": "o", "ơ": "o", "ờ": "o", "ớ": "o", "ở": "o",
    "ỡ": "o", "ợ": "o", "ù": "u", "ú": "u", "ủ": "u", "ũ": "u", "ụ": "u", "ư": "u",
    "ừ": "u", "ứ": "u", "ử": "u", "ữ": "u", "ự": "u", "ỳ": "y", "ý": "y", "ỷ": "y",
    "ỹ": "y", "ỵ": "y", "đ": "d",
    # Additional European precomposed
    "Ǻ": "A", "ǻ": "a", "Ǽ": "AE", "ǽ": "ae", "Ǿ": "O", "ǿ": "o",
}

# Typographic / punctuation / symbol substitutions that are safe ASCII equivalents
TYPOGRAPHIC: dict[str, str] = {
    "‘": "'", "’": "'", "‚": ",", "‛": "'",
    "“": '"', "”": '"', "„": '"', "‟": '"',
    "‹": "<", "›": ">", "«": '"', "»": '"',
    "‐": "-", "‑": "-", "‒": "-", "–": "-", "—": "-", "―": "-", "−": "-",
    "‐": "-", "−": "-",
    "…": "...", "‥": "..",
    " ": " ", " ": " ", " ": " ", " ": " ",
    " ": " ", " ": " ", " ": " ", " ": " ",
    " ": " ", " ": " ", " ": " ", " ": " ",
    " ": " ", " ": " ", "　": " ",
    "​": "", "‌": "", "⁠": "", "﻿": "",
    "­": "", "᠆": "",
    "‘": "'", "′": "'", "″": '""', "‴": "'''",
    "′": "'", "‵": "'", "´": "'",
    "′": "'", "‵": "'", "´": "'",
    "⁄": "/", "∕": "/",
    "×": "x", "÷": "/",
    "≤": "<=", "≥": ">=", "≠": "!=", "≈": "~", "∞": "inf",
    "±": "+/-",
    "°": " deg",
    "·": ".", "‣": "-", "◦": "o",
    "‰": "permille", "‱": "basispoint",
    "″": '"', "ʺ": '"',
    "ª": "a", "º": "o",
    # Remove these symbols entirely (not convert)
    "¶": "", "§": "§", "†": "", "‡": "", "№": "",
    "℮": "approx",
    "⩀": "=", "⩂": "<=", "⩃": ">=",
    # Keycap number emojis (1️⃣ 2️⃣ 3️⃣ etc.) -> plain digits
    "0️⃣": "0", "1️⃣": "1", "2️⃣": "2", "3️⃣": "3", "4️⃣": "4",
    "5️⃣": "5", "6️⃣": "6", "7️⃣": "7", "8️⃣": "8", "9️⃣": "9",
    "🔟": "10",
    # Keycap without variation selector
    "0⃣": "0", "1⃣": "1", "2⃣": "2", "3⃣": "3", "4⃣": "4",
    "5⃣": "5", "6⃣": "6", "7⃣": "7", "8⃣": "8", "9⃣": "9",
    # Hash and asterisk keycaps
    "#️⃣": "#", "*️⃣": "*",
    # Currency symbols -> ASCII
    "¢": "c", "£": "PS", "¥": "Y", "¤": "cur",
    "€": "EUR", "₹": "Rs", "₽": "R", "₩": "W", "₫": "D",
    "₴": "U", "₦": "N", "₱": "P", "₲": "G", "₮": "T",
    "₺": "L", "₼": "M", "₾": "L", "₿": "BTC", "฿": "B",
    "₡": "c", "₢": "Cr", "₣": "F", "₤": "L", "₥": "m",
    "₧": "Pts", "₨": "Rs", "₪": "NIS", "₭": "K",
    "₰": "", "₳": "A", "₵": "C", "₸": "T",
    "﷼": "IRR", "﹩": "$", "￠": "c", "￡": "L",
    "￥": "Y", "￦": "W",
    # Math operators -> ASCII
    "√": "sqrt", "∛": "cbrt", "∜": "sqrt[4]",
    "≡": "=", "≢": "!=", "∼": "~", "≃": "~=", "≅": "~=",
    "∝": "prop", "∘": "o", "∙": ".", "•": "-",
    "∴": "::", "∵": "because",
    "∈": "in", "∉": "not in", "∋": "ni", "∌": "not ni",
    "⊂": "subset", "⊃": "superset", "⊆": "subseteq", "⊇": "supseteq",
    "⊕": "(+)", "⊖": "(-)", "⊗": "(x)", "⊘": "(/)", "⊙": "odot",
    "⊥": "perp", "∀": "for all", "∃": "exists", "∄": "not exists",
    "∅": "{}", "∆": "D", "∇": "del", "∂": "d",
    "∫": "int", "∬": "int", "∮": "oint",
    "∑": "sum", "∏": "prod",
    "≪": "<<", "≫": ">>",
    "≪=": "<<=", "≫=": ">>=",
    "∠": "angle", "∟": "L", "⌀": "dia",
    "¬": "not",
    # Arrows -> ASCII
    "←": "<-", "↑": "^", "→": "->", "↓": "v",
    "↔": "<->", "↕": "updown",
    "↖": "nw", "↗": "ne", "↘": "se", "↙": "sw",
    "⇐": "<=", "⇒": "=>", "⇔": "<=>",
    "➔": "->", "➜": "->", "➞": "->", "➟": "->",
    "⬅": "<-", "⬆": "^", "⬇": "v",
    # Fractions -> ASCII
    "¼": "1/4", "½": "1/2", "¾": "3/4",
    "⅓": "1/3", "⅔": "2/3",
    "⅕": "1/5", "⅖": "2/5", "⅗": "3/5", "⅘": "4/5",
    "⅙": "1/6", "⅚": "5/6",
    "⅛": "1/8", "⅜": "3/8", "⅝": "5/8", "⅞": "7/8",
    "⅟": "1/",
    # Roman numerals (uppercase) -> ASCII
    "Ⅰ": "I", "Ⅱ": "II", "Ⅲ": "III", "Ⅳ": "IV", "Ⅴ": "V",
    "Ⅵ": "VI", "Ⅶ": "VII", "Ⅷ": "VIII", "Ⅸ": "IX", "Ⅹ": "X",
    "Ⅺ": "XI", "Ⅻ": "XII", "Ⅼ": "L", "Ⅽ": "C", "Ⅿ": "M",
    # Roman numerals (lowercase) -> ASCII
    "ⅰ": "i", "ⅱ": "ii", "ⅲ": "iii", "ⅳ": "iv", "ⅴ": "v",
    "ⅵ": "vi", "ⅶ": "vii", "ⅷ": "viii", "ⅸ": "ix", "ⅹ": "x",
    "ⅺ": "xi", "ⅻ": "xii", "ⅼ": "l", "ⅽ": "c", "ⅾ": "d",
    "ↀ": "1000", "ↁ": "5000", "ↂ": "10000",
    # Letterlike symbols / units
    # NOTE: ™ ® © NOT included — protected to KEEP them as-is per user request
    "℃": "C", "℉": "F", "ℓ": "L", "K": "K", "Å": "A",
    "Ω": "Ohm",
    "℡": "TEL", "ℳ": "M", "ℴ": "o",
    # Misc punctuation
    "¡": "!", "¿": "?", "‽": "!?",
    "µ": "u",
    # Enclosed circle numbers ①-⑳ -> 1-20
    "①": "1", "②": "2", "③": "3", "④": "4", "⑤": "5",
    "⑥": "6", "⑦": "7", "⑧": "8", "⑨": "9", "⑩": "10",
    "⑪": "11", "⑫": "12", "⑬": "13", "⑭": "14", "⑮": "15",
    "⑯": "16", "⑰": "17", "⑱": "18", "⑲": "19", "⑳": "20",
    # Enclosed parenthesized numbers ⑴-⒇ -> (1)-(20)
    "⑴": "(1)", "⑵": "(2)", "⑶": "(3)", "⑷": "(4)", "⑸": "(5)",
    "⑹": "(6)", "⑺": "(7)", "⑻": "(8)", "⑼": "(9)", "⑽": "(10)",
    "⑾": "(11)", "⑿": "(12)", "⒀": "(13)", "⒁": "(14)", "⒂": "(15)",
    "⒃": "(16)", "⒄": "(17)", "⒅": "(18)", "⒆": "(19)", "⒇": "(20)",
    # Enclosed dotted numbers ⒈-⒚ -> 1.-10.
    "⒈": "1.", "⒉": "2.", "⒊": "3.", "⒋": "4.", "⒌": "5.",
    "⒍": "6.", "⒎": "7.", "⒏": "8.", "⒐": "9.", "⒑": "10.",
    # Circled Latin uppercase Ⓐ-Ⓩ -> A-Z
    "Ⓐ": "A", "Ⓑ": "B", "Ⓒ": "C", "Ⓓ": "D", "Ⓔ": "E",
    "Ⓕ": "F", "Ⓖ": "G", "Ⓗ": "H", "Ⓘ": "I", "Ⓙ": "J",
    "Ⓚ": "K", "Ⓛ": "L", "Ⓜ": "M", "Ⓝ": "N", "Ⓞ": "O",
    "Ⓟ": "P", "Ⓠ": "Q", "Ⓡ": "R", "Ⓢ": "S", "Ⓣ": "T",
    "Ⓤ": "U", "Ⓥ": "V", "Ⓦ": "W", "Ⓧ": "X", "Ⓨ": "Y", "Ⓩ": "Z",
    # Circled Latin lowercase ⓐ-ⓩ -> a-z
    "ⓐ": "a", "ⓑ": "b", "ⓒ": "c", "ⓓ": "d", "ⓔ": "e",
    "ⓕ": "f", "ⓖ": "g", "ⓗ": "h", "ⓘ": "i", "ⓙ": "j",
    "ⓚ": "k", "ⓛ": "l", "ⓜ": "m", "ⓝ": "n", "ⓞ": "o",
    "ⓟ": "p", "ⓠ": "q", "ⓡ": "r", "ⓢ": "s", "ⓣ": "t",
    "ⓤ": "u", "ⓥ": "v", "ⓦ": "w", "ⓧ": "x", "ⓨ": "y", "ⓩ": "z",
    # Double circled numbers ⓵-⓴ -> 1-20, ⓪ -> 0
    "⓪": "0",
    "⓵": "1", "⓶": "2", "⓷": "3", "⓸": "4", "⓹": "5",
    "⓺": "6", "⓻": "7", "⓼": "8", "⓽": "9", "⓾": "10",
    "⓿": "0",
    # Negative circled ❶-❿ -> 1-10
    "❶": "1", "❷": "2", "❸": "3", "❹": "4", "❺": "5",
    "❻": "6", "❼": "7", "❽": "8", "❾": "9", "❿": "10",
    # Dingbat negative circled ➀-➉ -> 1-10
    "➀": "1", "➁": "2", "➂": "3", "➃": "4", "➄": "5",
    "➅": "6", "➆": "7", "➇": "8", "➈": "9", "➉": "10",
    # CJK compatibility units
    "㎡": "m2", "㎝": "cm", "㎞": "km", "㎟": "mm2",
    "㎤": "mm3", "㎨": "m/s2", "㎪": "Pa", "㎫": "hPa",
    "㎬": "kPa", "㎏": "kg", "㎐": "Hz", "㎑": "kHz",
    "㎒": "MHz", "㎓": "GHz", "㎛": "um",
    # Technical UI glyphs -> remove
    "⌘": "", "⌚": "", "⌛": "", "⏳": "",
    "⌫": "", "⌦": "", "⌨": "", "⏏": "",
    "⏩": "", "⏪": "", "⏫": "", "⏬": "",
    "⏮": "", "⏯": "", "⏭": "", "⏮": "",
    "⏰": "", "⏸": "", "⏹": "", "⏺": "",
    # Missing geometric shapes -> remove
    "▲": "", "▼": "", "◄": "", "►": "",
    "△": "", "▽": "", "◁": "", "▷": "",
    "◢": "", "◣": "", "◤": "", "◥": "",
    "◻": "", "◼": "", "◽": "", "◾": "",
    "⬛": "", "⬜": "", "⬟": "", "⬢": "",
    # Box drawing -> remove
    "─": "", "━": "", "│": "", "┃": "",
    "┌": "", "┐": "", "└": "", "┘": "",
    "├": "", "┤": "", "┬": "", "┴": "", "┼": "",
    "═": "", "║": "", "╔": "", "╗": "", "╚": "", "╝": "",
    "╠": "", "╣": "", "╦": "", "╩": "", "╬": "",
    # More dingbats
    "※": "*", "⁂": "", "⁑": "",
    "⸮": "?",
}

# Ligatures and compatibility characters
LIGATURES: dict[str, str] = {
    "ﬁ": "fi", "ﬂ": "fl", "ﬃ": "ffi", "ﬄ": "ffl",
    "ﬅ": "st", "ﬆ": "st",
    "Æ": "AE", "æ": "ae",
    "Œ": "OE", "œ": "oe",
    "Ĳ": "IJ", "ĳ": "ij",
    "ẞ": "SS", "ß": "ss",
}

FULLWIDTH: dict[str, str] = {chr(0xFF01 + i): chr(0x21 + i) for i in range(94)}
FULLWIDTH["　"] = " "
# CJK brackets -> ASCII brackets
FULLWIDTH["\u3010"] = "["
FULLWIDTH["\u3011"] = "]"
FULLWIDTH["\u3014"] = "["
FULLWIDTH["\u3015"] = "]"

# Currency and misc symbols -> ASCII equivalents
SYMBOL_TO_ASCII: dict[str, str] = {
    # Remove decorative/symbol glyphs entirely (not convert)
    "★": "", "☆": "", "✦": "", "✧": "", "✩": "", "✪": "", "✫": "", "✬": "",
    "✭": "", "✮": "", "✯": "", "✰": "", "✿": "", "❀": "", "❁": "", "❂": "",
    "❃": "", "❄": "", "❅": "", "❆": "", "❇": "", "❈": "", "❉": "", "❊": "",
    "❋": "", "✠": "", "✡": "", "✢": "", "✣": "", "✤": "", "✥": "", "✦": "",
    "♠": "", "♣": "", "♥": "", "♦": "", "♤": "", "♧": "", "♡": "", "♢": "",
    "✓": "", "✔": "", "✕": "", "✖": "", "✗": "", "✘": "", "☑": "", "☒": "",
    "⚠": "", "⚡": "", "⚙": "", "⚖": "", "⚕": "", "⚛": "", "⚜": "", "⚝": "",
    "♩": "", "♪": "", "♫": "", "♬": "", "♭": "", "♮": "", "♯": "",
    "●": "", "○": "", "◉": "", "◎": "", "◌": "", "◍": "", "◐": "", "◑": "",
    "◒": "", "◓": "", "■": "", "□": "", "▣": "", "▢": "", "▪": "", "▫": "",
    "◆": "", "◇": "", "◈": "", "◉": "", "○": "", "◌": "", "◍": "",
    # Superscript footnote markers -> regular numbers
    "⁰": "0", "¹": "1", "²": "2", "³": "3", "⁴": "4",
    "⁵": "5", "⁶": "6", "⁷": "7", "⁸": "8", "⁹": "9",
}

# Emoji and symbol ranges to remove entirely (not convert)
EMOJI_REMOVE_RANGES = [
    (0x1F600, 0x1F64F),   # emoticons
    (0x1F300, 0x1F5FF),   # symbols & pictographs
    (0x1F680, 0x1F6FF),   # transport & map
    (0x1F1E0, 0x1F1FF),   # flags
    (0x2600, 0x27BF),     # misc symbols
    (0x1F900, 0x1F9FF),   # supplemental symbols
    (0x1FA70, 0x1FAFF),   # symbols & pictographs ext-A
    (0x2702, 0x27B0),     # dingbats
    (0x24C2, 0x24C2),     # Ⓜ enclosed M only
    (0x1F000, 0x1F02F),   # mahjong
    (0x1F0A0, 0x1F0FF),   # playing cards
    (0x1F100, 0x1F18E),   # enclosed alphanumeric (diced etc.)
    (0x1F191, 0x1F251),   # squared CJK compat
    (0x1F680, 0x1F6FF),   # transport
    (0x1F910, 0x1F93A),   # body parts
    (0x1F93C, 0x1F945),   # more symbols
    (0x1F947, 0x1F9FF),   # more symbols
    (0x20E3, 0x20E3),     # combining enclosing keycap (1⃣ 2⃣ 3⃣ -> 1 2 3)
]

# Non-Latin script ranges to PRESERVE (never remove)
PRESERVE_SCRIPT_RANGES = [
    (0x0370, 0x03FF),   # Greek
    (0x0400, 0x04FF),   # Cyrillic
    (0x0590, 0x05FF),   # Hebrew
    (0x0600, 0x06FF),   # Arabic
    (0x0900, 0x097F),   # Devanagari
    (0x0980, 0x09FF),   # Bengali
    (0x0A00, 0x0A7F),   # Gurmukhi
    (0x0A80, 0x0AFF),   # Gujarati
    (0x0B00, 0x0B7F),   # Oriya
    (0x0B80, 0x0BFF),   # Tamil
    (0x0C00, 0x0C7F),   # Telugu
    (0x0C80, 0x0CFF),   # Kannada
    (0x0D00, 0x0D7F),   # Malayalam
    (0x0D80, 0x0DFF),   # Sinhala
    (0x0E00, 0x0E7F),   # Thai
    (0x0E80, 0x0EFF),   # Lao
    (0x0F00, 0x0FFF),   # Tibetan
    (0x1000, 0x109F),   # Myanmar
    (0x1100, 0x11FF),   # Hangul Jamo
    (0x1E00, 0x1EFF),   # Latin Extended Additional
    (0x1F00, 0x1FFF),   # Greek Extended
    (0x2C60, 0x2C7F),   # Latin Extended-C
    (0xA720, 0xA7FF),   # Latin Extended-D
    (0xAB30, 0xAB6F),   # Latin Extended-E
    (0x3040, 0x309F),   # Hiragana
    (0x30A0, 0x30FF),   # Katakana
    (0x3000, 0x303F),   # CJK Punctuation (、。〈〉《》「」【】〔〕 etc.)
    (0x2800, 0x28FF),   # Braille Patterns
    (0x31F0, 0x31FF),   # Katakana Phonetic Extensions
    (0x3400, 0x4DBF),   # CJK Extension A
    (0x4E00, 0x9FFF),   # CJK Unified Ideographs
    (0xAC00, 0xD7AF),   # Hangul Syllables
    (0xFF00, 0xFFEF),   # Halfwidth/Fullwidth
    (0x1100, 0x11FF),   # Hangul Jamo
    (0x3130, 0x318F),   # Hangul Compatibility Jamo
    (0xA960, 0xA97F),   # Hangul Jamo Extended-A
    (0xD7B0, 0xD7FF),   # Hangul Jamo Extended-B
]

def is_preserve_script(ch: str) -> bool:
    """Check if character belongs to a non-Latin script that should be preserved."""
    cp = ord(ch)
    for lo, hi in PRESERVE_SCRIPT_RANGES:
        if lo <= cp <= hi:
            return True
    return False

def is_emoji_remove(ch: str) -> bool:
    """Check if character is in an emoji/symbol range to remove."""
    cp = ord(ch)
    for lo, hi in EMOJI_REMOVE_RANGES:
        if lo <= cp <= hi:
            return True
    return False

# Common mojibake garbage sequences that transliterate would mangle (e.g. € -> EUR).
# Resolve these to a safe ASCII value before any transliterate pass.
# PRE_MOJIBAKE_FIX: sequences ftfy mangles or needs help with, applied BEFORE ftfy.
# Sorted by length descending in clean.py so longer sequences match first.
PRE_MOJIBAKE_FIX: dict[str, str] = {
    "â€¢": "•",        # bullet — ftfy gives horizontal bar (―)
    "â€¦": "...",      # ellipsis — ftfy gives single period (.)
    "â„¢": "™",        # trademark — ftfy mangles to â"¢
    "â€¬": "",         # pop direction formatter (U+202C) — ftfy mangles, remove
}

# POST_MOJIBAKE_FIX: standalone fragments ftfy leaves alone, applied AFTER ftfy
# via regex (context-sensitive: not part of a longer mojibake sequence).
#   â€ not followed by digit   -> a   (standalone garbage)
#   Ã not followed by high byte -> A   (standalone fragment)
#   ã not followed by high byte -> a


def build_full_map() -> dict[str, str]:
    m: dict[str, str] = {}
    m.update(LATIN_ACCENTS)
    m.update(TYPOGRAPHIC)
    m.update(LIGATURES)
    m.update(FULLWIDTH)
    return m


FULL_MAP = build_full_map()


def strip_combining(text: str) -> str:
    """NFD-decompose and drop combining marks (accents) keeping base letters."""
    decomposed = unicodedata.normalize("NFD", text)
    return "".join(c for c in decomposed if unicodedata.category(c) != "Mn")


def transliterate(text: str) -> str:
    """Safe Latin-accent/typographic -> ASCII. Leaves CJK/Hangul/Arabic etc intact."""
    out: list[str] = []
    for ch in text:
        if ch in FULL_MAP:
            out.append(FULL_MAP[ch])
        elif ord(ch) < 128:
            out.append(ch)
        else:
            # try diacritic strip for letters with combining marks
            base = strip_combining(ch)
            # Only fold when stripping yields a non-empty ASCII base; never
            # drop script-defining marks (e.g. Devanagari virama ्, anusvara ं,
            # candrabindu ँ) that are essential to Indic and other scripts.
            if base and base != ch and all(ord(c) < 128 for c in base):
                out.append(base)
            else:
                # non-Latin script (CJK etc.) -> keep as-is
                out.append(ch)
    return "".join(out)


# ---------------------------------------------------------------------------
# Non-Latin scripts -> Latin letters (opt-in via CleanOptions.fold_scripts,
# always on in strict mode). Classical/scholarly transliteration so Greek,
# Cyrillic, Armenian, Syriac, Arabic/Urdu and Hebrew text becomes searchable
# English-letter text instead of being preserved or deleted. CJK/Hangul/
# Indic etc. are NOT included — they stay preserve-by-default.
# ---------------------------------------------------------------------------

_SCRIPT_BASE: dict[str, str] = {
    # Greek
    "Α": "A", "Β": "B", "Γ": "G", "Δ": "D", "Ε": "E", "Ζ": "Z", "Η": "E",
    "Θ": "TH", "Ι": "I", "Κ": "K", "Λ": "L", "Μ": "M", "Ν": "N", "Ξ": "X",
    "Ο": "O", "Π": "P", "Ρ": "R", "Σ": "S", "Τ": "T", "Υ": "U", "Φ": "F",
    "Χ": "KH", "Ψ": "PS", "Ω": "O",
    "α": "a", "β": "b", "γ": "g", "δ": "d", "ε": "e", "ζ": "z", "η": "e",
    "θ": "th", "ι": "i", "κ": "k", "λ": "l", "μ": "m", "ν": "n", "ξ": "x",
    "ο": "o", "π": "p", "ρ": "r", "σ": "s", "ς": "s", "τ": "t", "υ": "u",
    "φ": "f", "χ": "kh", "ψ": "ps", "ω": "o",
    # Cyrillic (Russian core + Ukrainian/Belarusian extras)
    "А": "A", "Б": "B", "В": "V", "Г": "G", "Д": "D", "Е": "E", "Ё": "Yo",
    "Ж": "Zh", "З": "Z", "И": "I", "Й": "Y", "К": "K", "Л": "L", "М": "M",
    "Н": "N", "О": "O", "П": "P", "Р": "R", "С": "S", "Т": "T", "У": "U",
    "Ф": "F", "Х": "Kh", "Ц": "Ts", "Ч": "Ch", "Ш": "Sh", "Щ": "Shch",
    "Ъ": "", "Ы": "Y", "Ь": "", "Э": "E", "Ю": "Yu", "Я": "Ya",
    "а": "a", "б": "b", "в": "v", "г": "g", "д": "d", "е": "e", "ё": "yo",
    "ж": "zh", "з": "z", "и": "i", "й": "y", "к": "k", "л": "l", "м": "m",
    "н": "n", "о": "o", "п": "p", "р": "r", "с": "s", "т": "t", "у": "u",
    "ф": "f", "х": "kh", "ц": "ts", "ч": "ch", "ш": "sh", "щ": "shch",
    "ъ": "", "ы": "y", "ь": "", "э": "e", "ю": "yu", "я": "ya",
    "і": "i", "ї": "yi", "є": "ye", "ґ": "g", "ў": "u",
    "І": "I", "Ї": "Yi", "Є": "Ye", "Ґ": "G", "Ў": "U",
    # Armenian (both cases — no Unicode decomposition links them)
    "Ա": "A", "Բ": "B", "Գ": "G", "Դ": "D", "Ե": "E", "Զ": "Z", "Է": "E",
    "Ը": "A", "Թ": "T", "Ժ": "Zh", "Ի": "I", "Լ": "L", "Խ": "Kh", "Ծ": "Ts",
    "Կ": "K", "Հ": "H", "Ձ": "Dz", "Ղ": "Gh", "Ճ": "Ch", "Մ": "M", "Յ": "Y",
    "Ն": "N", "Շ": "Sh", "Ո": "V", "Չ": "Ch", "Պ": "P", "Ջ": "J", "Ռ": "R",
    "Ս": "S", "Վ": "V", "Տ": "T", "Ր": "R", "Ց": "Ts", "Ւ": "U", "Փ": "P",
    "Ք": "K", "Օ": "O", "Ֆ": "F",
    "ա": "a", "բ": "b", "գ": "g", "դ": "d", "ե": "e", "զ": "z", "է": "e",
    "ը": "a", "ժ": "zh", "ի": "i", "լ": "l", "խ": "kh", "ծ": "ts",
    "կ": "k", "հ": "h", "ձ": "dz", "ղ": "gh", "ճ": "ch", "մ": "m", "յ": "y",
    "ն": "n", "շ": "sh", "ո": "v", "չ": "ch", "պ": "p", "ջ": "j", "ռ": "r",
    "ս": "s", "վ": "v", "տ": "t", "ր": "r", "ց": "ts", "ւ": "u", "փ": "p",
    "ք": "k", "օ": "o", "ֆ": "f",
    # Syriac (incl. Garshuni variants)
    "ܐ": "a", "ܒ": "b", "ܓ": "g", "ܔ": "g", "ܕ": "d", "ܗ": "h", "ܘ": "w",
    "ܙ": "z", "ܚ": "h", "ܛ": "t", "ܝ": "y", "ܟ": "k", "ܠ": "l", "ܡ": "m",
    "ܢ": "n", "ܣ": "s", "ܥ": "a", "ܦ": "p", "ܨ": "s", "ܩ": "q", "ܪ": "r",
    "ܫ": "s", "ܬ": "t",
    # Arabic + common Urdu forms
    "ا": "a", "أ": "a", "إ": "a", "آ": "a", "ب": "b", "ت": "t", "ث": "th",
    "ج": "j", "ح": "h", "خ": "kh", "د": "d", "ذ": "z", "ر": "r", "ز": "z",
    "س": "s", "ش": "sh", "ص": "s", "ض": "d", "ط": "t", "ظ": "z", "ع": "a",
    "غ": "gh", "ف": "f", "ق": "q", "ك": "k", "ل": "l", "م": "m", "ن": "n",
    "ه": "h", "ة": "h", "و": "w", "ي": "y", "ى": "a", "ی": "y", "ے": "e",
    "ہ": "h", "ٹ": "t", "ڈ": "d", "ڑ": "r", "ں": "n", "ھ": "h", "ئ": "e",
    "پ": "p", "چ": "ch", "ژ": "zh", "گ": "g", "ڤ": "v",
    # Hebrew
    "א": "a", "ב": "b", "ג": "g", "ד": "d", "ה": "h", "ו": "v", "ז": "z",
    "ח": "h", "ט": "t", "י": "y", "כ": "k", "ך": "k", "ל": "l", "מ": "m",
    "ם": "m", "נ": "n", "ן": "n", "ס": "s", "ע": "a", "פ": "p", "ף": "p",
    "צ": "ts", "ץ": "ts", "ק": "q", "ר": "r", "ש": "sh", "ת": "t",
}

_SCRIPT_RANGES: list[tuple[int, int]] = [
    (0x0370, 0x03FF),  # Greek and Coptic
    (0x1F00, 0x1FFF),  # Greek Extended (polytonic)
    (0x0400, 0x04FF),  # Cyrillic
    (0x0530, 0x058F),  # Armenian
    (0x0590, 0x05FF),  # Hebrew
    (0x0600, 0x06FF),  # Arabic
    (0x0700, 0x074F),  # Syriac
    (0xFB50, 0xFDFF),  # Arabic Presentation Forms-A
    (0xFE70, 0xFEFF),  # Arabic Presentation Forms-B
]


def build_script_map() -> dict[str, str]:
    """Latin equivalents for non-Latin letters (fold_scripts / strict mode).

    Letters with combining marks (Greek Extended polytonic, Arabic harakat,
    Hebrew points...) collapse to their base letter; pure diacritics map to
    "". CJK/Hangul/Indic are not in the ranges — they stay preserved."""
    m: dict[str, str] = dict(_SCRIPT_BASE)
    for lo, hi in _SCRIPT_RANGES:
        for cp in range(lo, hi + 1):
            ch = chr(cp)
            if ch in m:
                continue
            cat = unicodedata.category(ch)
            if not (cat.startswith("L") or cat in ("Mn", "Mc", "Me", "Sk")):
                continue
            parts: list[str] = []
            for part in unicodedata.normalize("NFD", ch):
                if unicodedata.category(part) == "Mn":
                    continue
                if part in _SCRIPT_BASE:
                    parts.append(_SCRIPT_BASE[part])
                elif ord(part) < 128:
                    parts.append(part)
            if parts:
                m[ch] = "".join(parts)
            elif cat in ("Mn", "Mc", "Me", "Sk"):
                m[ch] = ""
    # phonetic digraphs / math symbols commonly found in messy exports
    m.update({
        "∂": "d", "∆": "D",
        "ʱ": "h", "ʰ": "h",
        "ʣ": "dz", "ʤ": "dz", "ʥ": "dz", "ʦ": "ts", "ʧ": "tsh",
    })
    return m


SCRIPT_TO_LATIN = build_script_map()
