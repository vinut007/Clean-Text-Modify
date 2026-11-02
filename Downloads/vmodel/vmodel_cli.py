"""VModel Terminal CLI — colorful, interactive data cleaner.

Run:  py vmodel_cli.py        (or type:  vmodel   after setup)
"""
from __future__ import annotations

import itertools
import os
import shutil
import subprocess
import sys
import time
from datetime import datetime, timedelta
from pathlib import Path

# make backend importable
sys.path.insert(0, str(Path(__file__).resolve().parent))

from backend.core import ingest as ingest_mod
from backend.core import clean as clean_mod
from backend.core import export as export_mod
from backend.core import fast_scan as fast_scan_mod
from backend.core.protect import protect as protect_fn, restore as restore_fn
from backend.core.detect import analyze_text
from backend.ai import fast_risk_review as risk_review_mod
from backend.ai import risk as risk_mod
from backend.ai.llama_server_manager import ensure_ai_available, stop_llama_server

# Rich UI (stub - consistent text-box rendering every run)
from backend.ui import rich_ui as ui
RICH_AVAILABLE = False


# ----------------------------------------------------------------------------
# ANSI color / style helpers
# ----------------------------------------------------------------------------
RESET = "\033[0m"
BOLD = "\033[1m"
DIM = "\033[2m"
FG_DIM = DIM
ITALIC = "\033[3m"

FG_BLACK = "\033[30m"
FG_RED = "\033[31m"
FG_GREEN = "\033[32m"
FG_YELLOW = "\033[33m"
FG_BLUE = "\033[34m"
FG_MAGENTA = "\033[35m"
FG_CYAN = "\033[36m"
FG_WHITE = "\033[37m"

BG_BLACK = "\033[40m"
BG_RED = "\033[41m"
BG_GREEN = "\033[42m"
BG_YELLOW = "\033[43m"
BG_BLUE = "\033[44m"
BG_MAGENTA = "\033[45m"
BG_CYAN = "\033[46m"
BG_WHITE = "\033[47m"


def c(text: str, *styles: str) -> str:
    return f"{''.join(styles)}{text}{RESET}"


def clear_line() -> None:
    sys.stdout.write("\r\033[K")
    sys.stdout.flush()


# ----------------------------------------------------------------------------
# Animations
# ----------------------------------------------------------------------------
_SPINNER_FRAMES = ["⠋", "⠙", "⠹", "⠸", "⠼", "⠴", "⠶", "⠵", "⠷", "⠻"]


def spin(seconds: float, msg: str, color: str = FG_CYAN) -> None:
    """Show a spinner for `seconds` then print the final message."""
    end = time.time() + seconds
    idx = 0
    while time.time() < end:
        frame = _SPINNER_FRAMES[idx % len(_SPINNER_FRAMES)]
        clear_line()
        sys.stdout.write(f"{c(frame, color)} {msg}")
        sys.stdout.flush()
        idx += 1
        time.sleep(0.08)
    clear_line()
    sys.stdout.write(f"{c('✔', FG_GREEN)} {msg}\n")
    sys.stdout.flush()


def sweep(seconds: float, msg: str = "Scanning") -> None:
    """0% -> 100% sweep animation."""
    steps = 40
    end = time.time() + seconds
    while time.time() < end:
        elapsed = time.time() - (end - seconds)
        pct = min(100, int((elapsed / seconds) * 100))
        filled = int(steps * pct / 100)
        bar = "█" * filled + "░" * (steps - filled)
        clear_line()
        sys.stdout.write(
            f"{c('⟳', FG_CYAN)} {msg} |{c(bar, FG_BLUE)}| {pct:3d}%"
        )
        sys.stdout.flush()
        time.sleep(0.05)
    clear_line()
    bar = "█" * steps
    sys.stdout.write(f"{c('✔', FG_GREEN)} {msg} |{c(bar, FG_GREEN)}| 100%\n")
    sys.stdout.flush()


# ----------------------------------------------------------------------------
# Progress bar (with ETA)
# ----------------------------------------------------------------------------
class Progress:
    def __init__(self, total: int, label: str = "Cleaning", width: int = 40):
        self.total = max(total, 1)
        self.label = label
        self.width = width
        self.done = 0
        self.start = time.time()
        self._last_pct = -1

    def update(self, n: int | None = None, inc: int = 1) -> None:
        if n is not None:
            self.done = min(n, self.total)
        else:
            self.done = min(self.done + inc, self.total)
        self._draw()

    def _draw(self) -> None:
        pct = int(self.done * 100 / self.total)
        if pct == self._last_pct and self.done < self.total:
            return
        self._last_pct = pct
        filled = int(self.width * pct / 100)
        bar = "█" * filled + "░" * (self.width - filled)
        elapsed = time.time() - self.start
        if self.done > 0 and elapsed > 0:
            rate = self.done / elapsed
            remaining = (self.total - self.done) / rate
            eta = str(timedelta(seconds=int(remaining)))
        else:
            eta = "--:--"
        clear_line()
        sys.stdout.write(
            f"{c('●', FG_CYAN)} {self.label} |{c(bar, FG_GREEN)}| "
            f"{pct:3d}%  {self.done}/{self.total}  ETA {eta}"
        )
        sys.stdout.flush()

    def finish(self, msg: str = "Done") -> None:
        self.done = self.total
        self._draw()
        sys.stdout.write(f"  {c('✔', FG_GREEN)} {msg}\n")
        sys.stdout.flush()


# ----------------------------------------------------------------------------
# UI helpers
# ----------------------------------------------------------------------------
def header() -> None:
    if RICH_AVAILABLE:
        ui.clear_screen()
        ui.show_logo()
    else:
        print()
        print(c("=" * 54, FG_MAGENTA))
        print(c("  V M O D E L   T E R M I N A L", FG_CYAN, BOLD))
        print(c("  Text-Quality Cleaner - Mojibake / Accents / Symbols", FG_CYAN))
        print(c("=" * 54, FG_MAGENTA))
        print()


def prompt(msg: str, color: str = FG_CYAN) -> str:
    sys.stdout.write(f"{c('»', color)} {msg} {DIM}")
    sys.stdout.flush()
    line = sys.stdin.readline()
    sys.stdout.write(RESET)
    return line.strip()


def yes_no(msg: str, default: bool = True) -> bool:
    suffix = "Y/n" if default else "y/N"
    ans = prompt(f"{msg} [{suffix}] ", FG_YELLOW).strip().lower()
    if not ans:
        return default
    return ans in ("y", "yes")


def show_columns(columns: list[str]) -> None:
    print()
    print(c("┌──────────────────── DETECTED COLUMNS ────────────────────┐", FG_BLUE))
    for i, col in enumerate(columns, 1):
        print(
            f"  {c(str(i), FG_YELLOW)}.  {c(col, FG_CYAN)}"
        )
    print(c("└──────────────────────────────────────────────────────────┘", FG_BLUE))
    print()


# ----------------------------------------------------------------------------
# Error detection (category + char)
# ----------------------------------------------------------------------------
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
}

REAL_ERROR_CATS = {"mojibake", "replacement", "invalid_utf8", "accent",
                   "invisible", "symbol", "emoji", "punctuation"}


def _sanitize_cell(value):
    """Strip NULL bytes from cell values before export so openpyxl never sees
    illegal control characters. clean_cell() already restores protection
    placeholders via restore(), so only stray NULLs remain here."""
    if not isinstance(value, str):
        return value
    import re as _re
    value = _re.sub(r"\x1b\[[0-9;]*[a-zA-Z]", "", value)
    value = value.replace("\x1b", "").replace("\x00", "")
    return value


def _diff_context(original: str, cleaned: str, width: int = 30) -> str:
    """Show compact left-context + changed-portion + right-context.

    Original chars in RED, replacement chars in GREEN:
    '...left [ORIG -> REPL] right...'
    Middle portion is capped at MID_MAX chars for readability.
    """
    MID_MAX = 120
    if not original or original == cleaned:
        return c(f"{original!r} -> {cleaned!r}", FG_YELLOW)
    n = min(len(original), len(cleaned))
    first = 0
    while first < n and original[first] == cleaned[first]:
        first += 1
    last = 0
    while last < n and original[len(original) - 1 - last] == cleaned[len(cleaned) - 1 - last]:
        last += 1
    left_start = max(0, first - width)
    right_end = min(len(original), len(original) - last + width)
    left = original[left_start:first]
    mid_o = original[first:len(original) - last]
    mid_c = cleaned[first:len(cleaned) - last]
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


def _cell_errors(text: str, column: str, opts: clean_mod.CleanOptions) -> list[str]:
    if not isinstance(text, str) or not text:
        return []
    pr = protect_fn(text)
    do_translit = column in (opts.transliterate_columns or set())
    an = analyze_text(pr.text, apply_accents=opts.fold_accents,
                      fold_scripts=(opts.fold_scripts or do_translit))
    found: list[str] = []
    for sp in an.spans:
        cat = sp.category
        if cat == "nonascii" and not do_translit:
            continue
        if cat.startswith("protected_"):
            continue
        if cat not in REAL_ERROR_CATS and cat != "nonascii":
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

# ----------------------------------------------------------------------------
# Core cleaning
# ----------------------------------------------------------------------------
def clean_file(
    fpath: str,
    skip_cols: set[int],
    mode: str = "1",
    ai_ready: bool = False,
    fold_accents: bool = True,
    fix_mojibake: bool = True,
    normalize_invisible: bool = True,
    fold_symbols: bool = True,
    collapse_punctuation: bool = True,
    keep_emoji: bool = None,  # None = use mode default
    fold_scripts: bool = False,
    transliterate_columns: set[str] | None = None,
    enrich: bool = False,  # expand contractions/abbreviations (don't -> do not)
    progress: Progress | None = None,
) -> tuple[str, int, int]:
    fpath = str(fpath)
    raw = Path(fpath).read_bytes()
    td = ingest_mod.ingest(fpath, raw, fmt=None)

    # Mode-based preset overrides
    if mode == "1":  # Safe clean — strip emoji by default (matches interactive scan)
        if keep_emoji is None:
            keep_emoji = False
    elif mode == "2":  # Strict clean
        fold_accents = True
        fix_mojibake = True
        normalize_invisible = True
        fold_symbols = True
        collapse_punctuation = True
        if keep_emoji is None:
            keep_emoji = False
        fold_scripts = True  # β→b, л→l, Ա->A, ل->l (opt-in / strict)
        transliterate_columns = set(td.columns)  # transliterate/remove all non-ASCII
    elif mode == "3":  # Clean + Translate (Approach A)
        fold_accents = False  # keep original chars for translation
        fix_mojibake = True
        normalize_invisible = True
        fold_symbols = True
        collapse_punctuation = True
        if keep_emoji is None:
            keep_emoji = True
        fold_scripts = False
        transliterate_columns = set()
    elif mode == "4":  # Only clean — fix mojibake, keep language/accents
        fold_accents = False  # keep original accents
        fix_mojibake = True
        normalize_invisible = True
        fold_symbols = False  # keep original symbols
        collapse_punctuation = False  # keep original punctuation
        if keep_emoji is None:
            keep_emoji = True
        fold_scripts = False
        transliterate_columns = set()
    elif mode == "5":  # Only translate — skip cleaning, just translate
        fold_accents = False
        fix_mojibake = False  # skip mojibake repair
        normalize_invisible = False  # skip invisible normalization
        fold_symbols = False
        collapse_punctuation = False
        if keep_emoji is None:
            keep_emoji = True
        fold_scripts = False
        transliterate_columns = set()
    
    # Default to True if still None
    if keep_emoji is None:
        keep_emoji = True

    opts = clean_mod.CleanOptions(
        fix_mojibake=fix_mojibake,
        fold_accents=fold_accents,
        normalize_invisible=normalize_invisible,
        fold_symbols=fold_symbols,
        collapse_punctuation=collapse_punctuation,
        keep_emoji=keep_emoji,
        fold_scripts=fold_scripts,
        transliterate_columns=transliterate_columns or set(),
        enrich=enrich,
    )

    columns = list(td.columns)
    rows = [list(r) for r in td.rows]
    columns.append("VModel_Errors")

    changed_cells = 0
    rows_with_errors = 0
    total = len(rows)

    # Track original values for final change reporting
    original_values: dict[tuple[int, int], str] = {}

    for ridx, row in enumerate(rows):
        err_parts: list[str] = []
        for cidx, col in enumerate(td.columns):
            if cidx >= len(row):
                continue
            # skip user-selected columns (1-based)
            if (cidx + 1) in skip_cols:
                continue
            v = row[cidx]
            if not isinstance(v, str) or not v:
                continue
            # Store original value for later comparison
            original_values[(ridx, cidx)] = v
            outcome = clean_mod.clean_cell(v, opts, col)
            cleaned = outcome.cleaned
            changed = outcome.changed
            # --- replacement character (U+FFFD) resolution ---
            # U+FFFD means the original bytes were invalid UTF-8 and already lost;
            # we replace with "?" so it's visible + counted as a fix.
            if "\ufffd" in cleaned:
                cleaned = cleaned.replace("\ufffd", "?")
                changed = True
            if changed:
                changed_cells += 1
                row[cidx] = cleaned
            # For translate modes (3, 5), skip intermediate error notes —
            # final original → translated will be shown after translation
            if mode not in ("3", "5"):
                errs = _cell_errors(v, col, opts)
                if errs:
                    errs = _mark_fixed(errs, v, cleaned)
                    err_parts.append(f"[{col}] " + ", ".join(errs))
                elif changed:
                    orig_short = v if len(v) <= 40 else v[:37] + "..."
                    new_short = cleaned if len(cleaned) <= 40 else cleaned[:37] + "..."
                    err_parts.append(f"[{col}] {orig_short} → {new_short}")
        if err_parts:
            rows_with_errors += 1
        row.append("; ".join(err_parts))

        if progress and (ridx % 25 == 0 or ridx == total - 1):
            progress.update(ridx + 1)

    if progress:
        progress.finish()

    # --- Translation mode (3 & 5): auto-detect language → English ---
    # Backend preference:
    #   TRANSLATE_BACKEND=edge   → Microsoft Edge guest endpoint (default if reachable)
    #   TRANSLATE_BACKEND=ai     → local LLM (ollama / llama.cpp)
    #   TRANSLATE_BACKEND=auto   → edge first, fall back to local AI (default)
    if mode in ("3", "5"):
        import re as _re
        import time as _time

        provider = os.environ.get("AI_PROVIDER_RESOLVED", os.environ.get("AI_PROVIDER", "ollama"))
        translate_model = os.environ.get("TRANSLATE_MODEL") or None
        backend_pref = (os.environ.get("TRANSLATE_BACKEND", "auto") or "auto").lower()

        # Decide whether Edge endpoint is available
        use_edge = False
        if backend_pref in ("auto", "edge"):
            try:
                from backend.ai.edge_translate import is_reachable
                use_edge = is_reachable(timeout=8)
            except Exception:
                use_edge = False
            if backend_pref == "edge" and not use_edge:
                print(c("  ! Edge translate endpoint unreachable — "
                        "falling back to local AI", FG_YELLOW))

        if use_edge:
            print(c("  Translation backend: Microsoft Edge (guest endpoint)",
                    FG_MAGENTA))
        elif ai_ready:
            print(c(f"  Translation backend: local AI ({provider})",
                    FG_MAGENTA))
        else:
            use_edge = False  # nothing available; skip translation entirely

        # --- ADVANCED FEATURE: Glossary support ---
        # Terms that should NOT be translated (brand names, technical terms)
        # Built-in defaults for terms Edge commonly mangles:
        glossary: set[str] = {
            # Indian cities (Edge changes Bengaluru→Bangalore etc.)
            "Bengaluru", "Mumbai", "Chennai", "Delhi", "Kolkata",
            "Hyderabad", "Pune", "Ahmedabad", "Jaipur", "Lucknow",
            # Business/tax codes
            "CIN", "EIN", "GSTIN", "VAT", "PAN", "IFSC", "SWIFT",
            "IBAN", "DUNS", "LEI", "TIN", "SSN",
            # Common brand/tech terms
            "iPhone", "iPad", "MacBook", "Python", "ClickHouse",
            "JavaScript", "TypeScript", "GitHub", "GitLab",
            # Stock symbols
            "BRK.B", "BRK.A",
            # JSON field names that get mangled
            "age", "name", "email", "phone", "address",
        }
        glossary_path = Path(fpath).parent / "glossary.txt"
        if glossary_path.exists():
            try:
                user_glossary = {
                    line.strip() for line in glossary_path.read_text(
                        encoding="utf-8"
                    ).splitlines()
                    if line.strip() and not line.startswith("#")
                }
                glossary.update(user_glossary)
                print(c(f"  Glossary loaded: {len(glossary)} terms "
                        f"(built-in + {glossary_path.name})", FG_GREEN))
            except Exception:
                print(c(f"  Built-in glossary: {len(glossary)} terms", FG_GREEN))
        else:
            print(c(f"  Built-in glossary: {len(glossary)} protected terms", FG_GREEN))

        def _tr_chat(messages: list[dict]) -> str:
            if provider == "llama":
                from backend.ai.llama_client import chat_llama
                return chat_llama(messages, model=translate_model,
                                  temperature=0.1, num_predict=4096)
            from backend.ai import ollama_client as _ai
            return _ai.chat_ollama(messages, model=translate_model,
                                   temperature=0.1, num_predict=4096)

        _batch_header = (
            "You are a professional translator. Translate every <item id=\"N\">...</item> "
            "segment into English. Auto-detect the source language of each segment. "
            "NEVER leave a segment in its original language — if it is already English, "
            "output it exactly as-is. "
            "Keep the <item id=\"N\">...</item> tags and their order in your reply, "
            "one per line, and put ONLY the English translation inside each tag — "
            "no explanations, no quotes:\n\n"
        )
        _single_header = (
            "Translate the following text into English. Auto-detect the source language. "
            "Never leave the text in its original language — if it is already English, "
            "return it exactly unchanged. "
            "Reply ONLY with the English text — no explanations, no quotes:\n\n"
        )
        _item_re = _re.compile(r"<item\s+id\s*=\s*\"?(\d+)\"?\s*>\s*(.*?)\s*</item>", _re.S)
        _letter_re = _re.compile(r"[^\W\d_]")  # any Unicode letter
        _skip_names = {"id", "url", "published date", "sentiment"}

        # --- ADVANCED: Smart pattern detection — skip cells that shouldn't be translated ---
        _CODE_PATTERNS = [
            # Financial codes, tax IDs, business identifiers
            _re.compile(r"^(CIN|EIN|GSTIN|VAT|PAN|IFSC|SWIFT|IBAN|DUNS|LEI|ACT|TIN|SSN|Aadhaar|Passport|Driving)\s*:", _re.I),
            # Stock symbols (BRK.B, AAPL, etc.) — with or without prefix text
            _re.compile(r"\b[A-Z]{1,5}\.[A-Z]{1,2}\b"),
            # Financial codes with prefix (Stock Symbol: BRK.B, CIN: U72900...)
            _re.compile(r"(Stock|Symbol|Code|ID|Number|No)\s*[:.]\s*[A-Z0-9\.]{4,}", _re.I),
            # All caps codes with numbers (U72900KA2020PTC123456)
            _re.compile(r"^[A-Z0-9]{10,}$"),
            # KEY=VALUE patterns (API_KEY=..., PASSWORD=...)
            _re.compile(r"^[A-Z_]{3,}\s*=\s*.+"),
            # JSON / structured data
            _re.compile(r"^\{.*\}$"),
            _re.compile(r"^\[.*\]$"),
            # XML / HTML tags
            _re.compile(r"^</?[a-zA-Z][^>]*>"),
            # SQL queries
            _re.compile(r"^(SELECT|INSERT|UPDATE|DELETE|CREATE|ALTER|DROP|WHERE|FROM|JOIN)\s", _re.I),
            # File paths
            _re.compile(r"^[A-Z]:\\"),
            _re.compile(r"^/home/"),
            _re.compile(r"^//"),
            # URLs
            _re.compile(r"^https?://", _re.I),
            _re.compile(r"^www\.", _re.I),
            # Email-like
            _re.compile(r"^[\w.+-]+@[\w-]+\.[\w.]+$"),
            # UUID
            _re.compile(r"^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$", _re.I),
            # MAC address
            _re.compile(r"^([0-9A-F]{2}[:-]){5}([0-9A-F]{2})$", _re.I),
            # Pure numbers with units
            _re.compile(r"^[\d\s,.\-+/%°²³€£¥₹$]+\s*(kg|g|mg|km|m|cm|mm|µm|nm|kW|V|Hz|GB|MB|TB|Mbps|°C|°F|%)$", _re.I),
            # Version numbers
            _re.compile(r"^v?\d+\.\d+(\.\d+)*$", _re.I),
            # Dates
            _re.compile(r"^\d{4}-\d{2}-\d{2}"),
            _re.compile(r"^\d{2}:\d{2}:\d{2}"),
            # Place names that Edge mangles (Indian cities, etc.)
            # NOTE: Bangalore intentionally NOT skipped — it is the mangled form
            # and must flow through cache so glossary _edge_fixes can restore
            # Bengaluru. Correct spellings (Bengaluru, Mumbai, ...) are skipped.
            _re.compile(r"^(Bengaluru|Mumbai|Chennai|Delhi|Kolkata|Hyderabad|Pune)\b", _re.I),
        ]

        _glossary_lower = {g.lower() for g in glossary}

        def _should_skip_translation(text: str) -> bool:
            """Return True if text looks like a code/identifier/structured data."""
            t = text.strip()
            if not t:
                return True
            # Check glossary (case-insensitive)
            if t.lower() in _glossary_lower:
                return True
            # Check code patterns
            for pat in _CODE_PATTERNS:
                if pat.search(t):
                    return True
            # Skip if mostly numbers/symbols (< 40% letters)
            letters = sum(1 for ch in t if ch.isalpha())
            if len(t) > 0 and letters / len(t) < 0.4:
                return True
            # Skip if ALL CAPS (likely an acronym/code)
            if t.isupper() and len(t) <= 20:
                return True
            return False

        # collect eligible cells; dedupe repeated values (translated once)
        unique_order: list[str] = []
        positions: dict[str, list[tuple[int, int]]] = {}
        skipped_codes = 0
        for ridx, row in enumerate(rows):
            for cidx in range(len(td.columns)):  # never touch the VModel_Errors column
                if cidx >= len(row) or (cidx + 1) in skip_cols:
                    continue
                v = row[cidx]
                if not isinstance(v, str) or not v.strip():
                    continue
                if td.columns[cidx].lower() in _skip_names:
                    continue
                if not _letter_re.search(v):  # numbers / dates / emoji only
                    continue
                if len(v.strip()) < 4:  # skip single/short characters (codes, fragments)
                    continue
                # --- ADVANCED: Smart skip — codes, identifiers, structured data ---
                if _should_skip_translation(v):
                    skipped_codes += 1
                    continue
                if v not in positions:
                    positions[v] = []
                    unique_order.append(v)
                positions[v].append((ridx, cidx))

        if skipped_codes > 0:
            print(c(f"  Skipped {skipped_codes} cells (codes/identifiers/structured data)",
                    FG_YELLOW))

        # --- ADVANCED FEATURE: Column language detection ---
        if unique_order and use_edge:
            print()
            print(c("  Detecting languages per column...", FG_CYAN))
            try:
                from backend.ai.edge_translate import translate_batch as _eb
                # Sample 3 texts per column for language detection
                col_samples: dict[int, list[str]] = {}
                for text, cells in positions.items():
                    for ridx, cidx in cells:
                        if cidx not in col_samples:
                            col_samples[cidx] = []
                        if len(col_samples[cidx]) < 3:
                            col_samples[cidx].append(text)

                # Edge doesn't have a detect endpoint, so we'll use a trick:
                # translate to a known language and check if output differs
                # For now, just show column stats
                for cidx in sorted(col_samples.keys()):
                    samples = col_samples[cidx]
                    non_ascii = sum(1 for s in samples if any(ord(ch) > 127 for ch in s))
                    col_name = td.columns[cidx] if cidx < len(td.columns) else f"Col{cidx}"
                    if non_ascii > 0:
                        print(c(f"    • {col_name}: {len(positions)} unique texts, "
                                f"{non_ascii}/{len(samples)} samples non-ASCII",
                                FG_GREEN))
            except Exception:
                pass

        # --- ADVANCED FEATURE: Preview translations before full run ---
        if unique_order:
            n_cells = sum(len(p) for p in positions.values())
            preview_count = min(5, len(unique_order))
            translation_start_time = __import__('time').time()
            print()
            print(c(f"  Found {len(unique_order)} unique texts ({n_cells} cells)",
                    FG_CYAN))

            if preview_count > 0 and len(unique_order) > preview_count:
                print()
                print(c("  Preview (first 5 texts):", FG_YELLOW, BOLD))
                print(c("  " + "─" * 60, FG_DIM))

                # Quick preview translation
                preview_texts = unique_order[:preview_count]
                if use_edge:
                    try:
                        from backend.ai.edge_translate import translate_batch as _prev
                        preview_results = _prev(preview_texts, source="", target="en")
                        for orig, res in zip(preview_texts, preview_results):
                            tr = res["text"] if res.get("ok") else orig
                            orig_disp = orig if len(orig) <= 35 else orig[:32] + "..."
                            tr_disp = tr if len(tr) <= 35 else tr[:32] + "..."
                            print(c(f"    {orig_disp}", FG_WHITE))
                            print(c(f"    → {tr_disp}", FG_GREEN))
                            print()
                    except Exception:
                        pass
                print(c("  " + "─" * 60, FG_DIM))

                # Ask user to confirm
                if not yes_no("Proceed with full translation?", default=True):
                    print(c("  Translation cancelled by user.", FG_YELLOW))
                    return out_path, changed_cells, rows_with_errors

        if unique_order:
            n_cells = sum(len(p) for p in positions.values())
            backend_label = "Edge" if use_edge else "local AI"
            print(c(f"  Translating {len(unique_order)} unique texts "
                    f"({n_cells} cells) to English via {backend_label}...",
                    FG_MAGENTA))
            tr_progress = Progress(total=len(unique_order), label="Translating")
            cache: dict[str, str] = {}

            if use_edge:
                from backend.ai.edge_translate import translate_batch

                # Edge accepts a large JSON array natively — no LLM packing needed.
                # Chunk to 500 items per request to stay well under size caps.
                EDGE_CHUNK = 500
                for es in range(0, len(unique_order), EDGE_CHUNK):
                    chunk = unique_order[es : es + EDGE_CHUNK]
                    try:
                        results = translate_batch(chunk, source="", target="en")
                    except Exception:
                        results = [{"text": t, "ok": False} for t in chunk]
                    for t, r in zip(chunk, results):
                        cache[t] = r["text"] if r.get("ok") else t
                    tr_progress.update(len(cache))
            else:
                i = 0
                while i < len(unique_order):
                    # pack one batch: <=8 texts, <=600 chars (CPU-friendly, fits context)
                    batch: list[str] = []
                    chars = 0
                    while i < len(unique_order) and len(batch) < 8:
                        t = unique_order[i]
                        if batch and chars + len(t) > 600:
                            break
                        batch.append(t)
                        chars += len(t)
                        i += 1

                    parsed: dict[int, str] = {}
                    body = "".join(
                        f'<item id="{k}">{t}</item>\n' for k, t in enumerate(batch, 1)
                    )
                    try:
                        reply = _tr_chat([{"role": "user", "content": _batch_header + body}])
                        parsed = {
                            int(m.group(1)): m.group(2)
                            for m in _item_re.finditer(reply or "")
                        }
                    except Exception:
                        parsed = {}

                    for k, t in enumerate(batch, 1):
                        if k in parsed and parsed[k]:
                            cache[t] = parsed[k]
                            continue
                        # fallback: translate this item alone with a single-item prompt
                        try:
                            tr = _tr_chat(
                                [{"role": "user", "content": _single_header + t}]
                            )
                            tr = _re.sub(r"</?item[^>]*>", "", tr or "").strip()
                            cache[t] = tr if tr else t
                        except Exception:
                            cache[t] = t  # leave original if translation fails

                    tr_progress.update(len(cache))

            tr_progress.finish(f"{len(cache)} texts translated")

            # --- ADVANCED FEATURE: Multi-pass validation ---
            # Check if any translated text still contains non-English patterns
            # and re-translate those
            if use_edge and cache:
                print()
                print(c("  Validating translations...", FG_CYAN))
                _non_english = _re.compile(
                    r"[àáâãäåèéêëìíîïòóôõöùúûüýÿñçßœæÀÁÂÃÄÅÈÉÊËÌÍÎÏÒÓÔÕÖÙÚÛÜÝŸÑÇ"
                    r"ąćęłńóśźżĄĆĘŁŃÓŚŹŻа-яА-Яα-ωΑ-Ω぀-ゟ゠-ヿ一-鿿가-힯]"
                )
                suspect_texts = [
                    t for t in cache
                    if _non_english.search(cache[t] or "")
                ]
                if suspect_texts:
                    print(c(f"    {len(suspect_texts)} texts may still be "
                            f"non-English — re-translating...", FG_YELLOW))
                    try:
                        retry_results = translate_batch(
                            suspect_texts, source="", target="en"
                        )
                        for t, r in zip(suspect_texts, retry_results):
                            if r.get("ok") and r["text"]:
                                cache[t] = r["text"]
                    except Exception:
                        pass

            # Strategy A: fold accents on translated English output so the
            # final column is ASCII-clean (café -> cafe) while the translator
            # still received accented input for best language detection.
            _fold_opts = clean_mod.CleanOptions(
                fix_mojibake=False,
                fold_accents=True,
                normalize_invisible=False,
                fold_symbols=False,
                collapse_punctuation=False,
                keep_emoji=True,
                fold_scripts=False,
                enrich=enrich,
            )
            for _k in list(cache):
                _folded = clean_mod.clean_cell(cache[_k], _fold_opts, "").cleaned
                if _folded and _folded != cache[_k]:
                    cache[_k] = _folded

            # --- FIX: Also fold accents on NON-translated cells ---
            # Single accented chars (ü, ö, é, ñ, è) are skipped from translation
            # (len < 4) but still need accent folding after mojibake repair
            print()
            print(c("  Folding accents on remaining cells...", FG_CYAN))
            fold_count = 0
            for ridx, row in enumerate(rows):
                for cidx in range(len(td.columns)):
                    if cidx >= len(row) or (cidx + 1) in skip_cols:
                        continue
                    v = row[cidx]
                    if not isinstance(v, str) or not v:
                        continue
                    # Skip if already translated (in cache positions)
                    if v in positions:
                        continue
                    # Fold accents
                    _folded = clean_mod.clean_cell(v, _fold_opts, "").cleaned
                    if _folded and _folded != v:
                        row[cidx] = _folded
                        fold_count += 1
                        # Add to error column
                        orig_short = v if len(v) <= 40 else v[:37] + "..."
                        new_short = _folded if len(_folded) <= 40 else _folded[:37] + "..."
                        err_cell = row[-1] if row else ""
                        if isinstance(err_cell, str):
                            note = f"Translated [{td.columns[cidx]}]: {orig_short} → {new_short}"
                            if note not in err_cell:
                                row[-1] = (err_cell + "; " if err_cell else "") + note
            if fold_count > 0:
                print(c(f"    Folded accents on {fold_count} cells", FG_GREEN))

            # --- ADVANCED FEATURE: Glossary post-processing ---
            # Restore glossary terms that may have been translated/mangled
            if glossary:
                # Common Edge mistranslations to reverse
                _edge_fixes = {
                    "bangalore": "Bengaluru",
                    "bombay": "Mumbai",
                    "madras": "Chennai",
                    "calcutta": "Kolkata",
                }
                for _k in list(cache):
                    _tr = cache[_k] or ""
                    _tr_lower = _tr.lower()
                    # Fix known Edge mistranslations
                    for wrong, right in _edge_fixes.items():
                        if wrong in _tr_lower and right.lower() not in _tr_lower:
                            _tr = _re.sub(
                                rf"\b{wrong}\b", right, _tr, flags=_re.I
                            )
                    # Restore glossary terms if they were changed
                    for term in glossary:
                        if term.lower() in (_k or "").lower():
                            # If term is missing from translation, check common variants
                            if term.lower() not in _tr.lower():
                                # Try to find what replaced it and restore
                                # Simple approach: if term is a word, check if a similar word appears
                                pass
                    cache[_k] = _tr

            # --- ADVANCED FEATURE: Translation statistics ---
            translation_time = __import__('time').time() - translation_start_time
            translated_ok = sum(1 for k in cache if cache[k] != k)
            failed = sum(1 for k in cache if cache[k] == k)
            total_chars = sum(len(k) for k in cache)

            print()
            print(c("  ── Translation Statistics ──", FG_CYAN, BOLD))
            print(c(f"    Unique texts processed : {len(cache)}", FG_WHITE))
            print(c(f"    Successfully translated: {translated_ok}", FG_GREEN))
            print(c(f"    Failed / unchanged     : {failed}", FG_YELLOW if failed else FG_GREEN))
            print(c(f"    Total characters       : {total_chars:,}", FG_WHITE))
            print(c(f"    Cells updated          : {sum(len(p) for k, p in positions.items() if cache.get(k, k) != k)}", FG_WHITE))
            print(c(f"    Time taken             : {translation_time:.1f}s", FG_WHITE))
            if translation_time > 0:
                print(c(f"    Speed                  : {len(cache)/translation_time:.1f} texts/sec", FG_WHITE))

            # write back, count changes, annotate with original → final translated
            t_rows: set[int] = set()
            for text, cells in positions.items():
                tr = cache.get(text, text)
                if tr == text:
                    continue
                changed_cells += len(cells)
                for ridx, cidx in cells:
                    rows[ridx][cidx] = tr
                    t_rows.add(ridx)
                    # Use ORIGINAL value (before cleaning) for comparison
                    orig = original_values.get((ridx, cidx), text)
                    # Only show if there's an actual change
                    if orig == tr:
                        continue
                    orig_short = orig if len(orig) <= 40 else orig[:37] + "..."
                    new_short = tr if len(tr) <= 40 else tr[:37] + "..."
                    err_cell = rows[ridx][-1] if rows[ridx] else ""
                    if isinstance(err_cell, str):
                        note = f"Translated [{td.columns[cidx]}]: {orig_short} → {new_short}"
                        if note not in err_cell:
                            rows[ridx][-1] = (err_cell + "; " if err_cell else "") + note
            if t_rows:
                rows_with_errors = sum(
                    1 for r in rows
                    if r and isinstance(r[-1], str) and r[-1].strip()
                )

    # --- Build output with cleaned-data-only column naming ---
    # Skipped columns → _not_clean, processed columns → _cleaned
    out_columns: list[str] = []
    for i, col in enumerate(td.columns):
        suffix = "_not_clean" if (i + 1) in skip_cols else "_cleaned"
        out_columns.append(f"{col}{suffix}")
    out_columns.append("error_mapped_row_by_row")
    out_columns.append("high risk_cleaned")
    out_columns.append("before after")

    # Track rows with any changes
    changed_rows: set[int] = set()
    for (ridx, _cidx), orig in original_values.items():
        if ridx < len(rows) and _cidx < len(rows[ridx]):
            if rows[ridx][_cidx] != orig:
                changed_rows.add(ridx)

    # Build output rows
    out_rows: list[list[str]] = []
    for ridx, row in enumerate(rows):
        out_row: list[str] = []
        # Data columns (original td.columns count)
        for cidx in range(len(td.columns)):
            out_row.append(row[cidx] if cidx < len(row) else "")
        # Error column (VModel_Errors is at row[-1])
        err_cell = row[-1] if row and len(row) > len(td.columns) else ""
        out_row.append(err_cell if isinstance(err_cell, str) else "")
        # High risk cleaned flag
        out_row.append("yes" if ridx in changed_rows else "no")
        # Before after column — show only the changed portion (diff context),
        # not the full long cell text
        ba_parts: list[str] = []
        for cidx in range(len(td.columns)):
            if cidx < len(row):
                orig = original_values.get((ridx, cidx), "")
                cleaned = row[cidx]
                if orig and orig != cleaned:
                    ba_parts.append(f"{td.columns[cidx]}: {_diff_context(orig, cleaned)}")
        out_row.append("; ".join(ba_parts))
        out_rows.append(out_row)

    # Sanitize all cell values before export (strip NULL bytes / placeholders)
    for row in out_rows:
        for i in range(len(row)):
            row[i] = _sanitize_cell(row[i])

    # Export as XLSX only
    src = Path(fpath)
    out_path = str(src.parent / f"{src.stem}_VModel_Cleaned.xlsx")
    res = export_mod.export("xlsx", out_columns, out_rows,
                            name=src.stem + "_VModel_Cleaned")
    Path(out_path).write_bytes(res.data)

    return out_path, changed_cells, rows_with_errors

# ----------------------------------------------------------------------------
# Two-tier interactive review mode: heuristic scan -> LLM high-risk review ->
# user approves/rejects/modifies each high-risk pattern one-by-one -> clean
# ----------------------------------------------------------------------------
def clean_file_review_mode(
    fpath: str,
    skip_cols: set[int],
    fold_accents: bool = True,
    fix_mojibake: bool = True,
    normalize_invisible: bool = True,
    fold_symbols: bool = True,
    collapse_punctuation: bool = True,
    keep_emoji: bool = True,
    fold_scripts: bool = False,
    transliterate_columns: set[str] | None = None,
    llm_model: str = "qwen2.5:0.5b",
) -> str:
    fpath = str(fpath)
    raw = Path(fpath).read_bytes()
    td = ingest_mod.ingest(fpath, raw, fmt=None)

    opts = clean_mod.CleanOptions(
        fix_mojibake=fix_mojibake,
        fold_accents=fold_accents,
        normalize_invisible=normalize_invisible,
        fold_symbols=fold_symbols,
        collapse_punctuation=collapse_punctuation,
        keep_emoji=keep_emoji,
        fold_scripts=fold_scripts,
        transliterate_columns=transliterate_columns or set(),
    )

    columns = list(td.columns)
    rows = [list(r) for r in td.rows]
    columns.append("VModel_Errors")

    print()
    print(c("═════════════════════════════════════════════════════", FG_MAGENTA))
    print(c("  TIER 1 — HEURISTIC SCAN (all rows, no LLM per cell)", FG_CYAN, BOLD))
    print(c("═════════════════════════════════════════════════════", FG_MAGENTA))

    progress = Progress(total=len(td.rows), label="Scanning rows")
    scan_result = fast_scan_mod.scan_all_cells(
        td.columns, rows, skip_cols, opts,
        progress_callback=lambda n: progress.update(n),
    )
    progress.finish(f"{scan_result.changed_cells} cells need cleaning")

    print()
    print(c(f"  Rows scanned   : {scan_result.total_rows}", FG_CYAN))
    print(c(f"  Cells changed  : {scan_result.changed_cells}", FG_CYAN))
    print(c(f"  Rows with errors: {scan_result.rows_with_errors}", FG_CYAN))
    print(c(f"  Low risk patterns : {len(scan_result.low_patterns)}  (auto-approved)", FG_GREEN))
    print(c(f"  Medium risk patterns: {len(scan_result.medium_patterns)}  (auto-approved)", FG_YELLOW))
    print(c(f"  High risk patterns : {len(scan_result.high_patterns)}  (needs your approval)", FG_RED))
    print()

    # Auto-approve low + medium
    for p in scan_result.low_patterns:
        p.user_decision = "approve"
    for p in scan_result.medium_patterns:
        p.user_decision = "approve"

    # Tier 2: LLM review + user decision for each high-risk pattern, one by one
    if scan_result.high_patterns:
        print(c("═════════════════════════════════════════════════════", FG_MAGENTA))
        print(c("  TIER 2 — LLM HIGH-RISK REVIEW (one-by-one)", FG_CYAN, BOLD))
        print(c("═════════════════════════════════════════════════════", FG_MAGENTA))
        print()
        print(c(f"  Using offline model: {llm_model}", DIM))
        print(c("  You decide per pattern: (a)pprove / (r)eject / (m)odify / (s)kip", FG_DIM))
        print()

        # Bulk decision option
        bulk = prompt(
            f"  Bulk decision for all {len(scan_result.high_patterns)} high-risk pattern(s)? "
            f"(a=approve all / r=reject all / i=review individually): ",
            FG_YELLOW,
        ).strip().lower()

        if bulk in ("a", "approve all"):
            for pattern in scan_result.high_patterns:
                pattern.user_decision = "approve"
            print(c(f"  Approved all {len(scan_result.high_patterns)} high-risk pattern(s).", FG_GREEN))
        elif bulk in ("r", "reject all"):
            for pattern in scan_result.high_patterns:
                pattern.user_decision = "reject"
            print(c(f"  Rejected all {len(scan_result.high_patterns)} high-risk pattern(s).", FG_RED))
        else:
            for i, pattern in enumerate(scan_result.high_patterns, 1):
                # LLM suggestion
                llm = risk_review_mod.review_high_risk_pattern(
                    pattern.src, pattern.dst, pattern.category,
                    pattern.total_count, pattern.reason, model=llm_model,
                )
                llm_risk = llm.get("risk", "high")
                llm_reason = llm.get("reason", "")

                # Compact diff context (show only the changed portion)
                first_cell = pattern.changes[0]
                diff = _diff_context(first_cell.original, first_cell.cleaned)

                print()
                print(c(f"  [{i}/{len(scan_result.high_patterns)}] HIGH-RISK PATTERN", FG_RED, BOLD))
                print(c(f"    Category : {pattern.category}", FG_CYAN))
                print(c(f"    Affects  : {pattern.total_count} cell(s)", FG_CYAN))
                print(f"    Example  : {diff}")
                print(c(f"    Heuristic: {pattern.reason}", FG_DIM))
                print(c(f"    LLM says : {llm_risk} — {llm_reason}", FG_YELLOW, BOLD))

                while True:
                    ans = prompt(
                        f"    Decision? (a=approve / r=reject / m=modify ALL / s=skip / c=custom ALL): ",
                        FG_YELLOW,
                    ).strip().lower()
                    if not ans or ans in ("a", "approve"):
                        pattern.user_decision = "approve"
                        break
                    elif ans in ("r", "reject"):
                        pattern.user_decision = "reject"
                        break
                    elif ans in ("m", "modify all"):
                        new_dst = prompt(
                            "    Enter replacement text for ALL cells: ",
                            FG_CYAN,
                        ).strip()
                        pattern.user_decision = "approve"
                        pattern.user_dst = new_dst if new_dst else pattern.dst
                        break
                    elif ans in ("s", "skip"):
                        pattern.user_decision = "skip"
                        break
                    elif ans in ("c", "custom all"):
                        custom_dst = prompt(
                            "    Enter custom replacement for ALL cells: ",
                            FG_CYAN,
                        ).strip()
                        pattern.user_decision = "approve"
                        pattern.user_dst = custom_dst if custom_dst else pattern.dst
                        break
                    else:
                        print(c("      Invalid choice. Use a/r/m/s/c.", FG_RED))

    else:
        print(c("  No high-risk patterns — all changes are low/medium risk.", FG_GREEN))
        print()

    # Apply decisions
    print()
    progress = Progress(total=len(td.rows), label="Applying changes")
    # snapshot originals before apply_decisions mutates rows in place
    original_rows = [list(r) for r in rows]
    cleaned_rows, changed_cells, rows_with_errors = fast_scan_mod.apply_decisions(
        rows, scan_result,
    )
    progress.finish(f"{changed_cells} cells updated")

    # Add error column — detected on ORIGINAL values, annotated ✓fixed/✗kept
    for ridx, row in enumerate(cleaned_rows):
        err_parts: list[str] = []
        orig_row = original_rows[ridx] if ridx < len(original_rows) else []
        for cidx, col in enumerate(td.columns):
            if cidx >= len(row) or (cidx + 1) in skip_cols:
                continue
            v = row[cidx]
            vo = orig_row[cidx] if cidx < len(orig_row) else v
            if not isinstance(vo, str) or not vo:
                continue
            errs = _cell_errors(vo, col, opts)
            if errs:
                errs = _mark_fixed(errs, vo, v if isinstance(v, str) else "")
                err_parts.append(f"[{col}] " + ", ".join(errs))
        row.append("; ".join(err_parts))

    # Write output
    src_path = Path(fpath)
    out_path = str(src_path.parent / f"{src_path.stem}_VModel_Cleaned{src_path.suffix}")
    fmt = ingest_mod.detect_format(out_path, None)
    if fmt == "excel":
        fmt = "xlsx"
    # Sanitize all cell values before export (strip NULL bytes / placeholders)
    for row in cleaned_rows:
        for cidx in range(len(row)):
            row[cidx] = _sanitize_cell(row[cidx])
    res = export_mod.export(fmt, columns, cleaned_rows, name=src_path.stem + "_VModel_Cleaned")
    Path(out_path).write_bytes(res.data)

    print()
    print(c("═════════════════════════════════════════════════════", FG_MAGENTA))
    print(c("  CLEANING COMPLETE", FG_GREEN, BOLD))
    print(c(f"  Output file : {out_path}", FG_CYAN))
    print(c(f"  Rows        : {len(cleaned_rows)}", FG_CYAN))
    print(c(f"  Cells changed: {changed_cells}", FG_CYAN))
    print(c(f"  Rows w/ errors: {rows_with_errors}", FG_CYAN))
    print(c("═════════════════════════════════════════════════════", FG_MAGENTA))
    print()

    return out_path

# ----------------------------------------------------------------------------
# Main interactive flow
# ----------------------------------------------------------------------------
def main() -> None:
    header()

    # Local AI: try llama.cpp first (port 8081), then Ollama fallback.
    # Works consistently regardless of which server is running.
    ai_ready = False
    ai_provider_used = None

    # Try llama.cpp first
    print(c("  Checking local AI (llama.cpp port 8081)...", FG_CYAN))
    if ensure_ai_available("llama"):
        ai_ready = True
        ai_provider_used = "llama"
        print(c("  Local AI ready (llama.cpp).", FG_GREEN))
    else:
        # Fallback to Ollama
        from backend.ai import ollama_client as _ai_cli
        _st = _ai_cli.get_status()
        if _st.offline_available:
            ai_ready = True
            ai_provider_used = "ollama"
            print(c(f"  Local AI ready (Ollama: {_st.offline_model}).", FG_GREEN))
        else:
            print(c("  Starting Ollama server...", FG_CYAN))
            try:
                subprocess.Popen(
                    ["ollama", "serve"],
                    stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                )
            except OSError:
                pass
            for _ in range(10):  # poll up to ~10s
                time.sleep(1)
                _st = _ai_cli.get_status()
                if _st.offline_available:
                    break
            ai_ready = _st.offline_available
            ai_provider_used = "ollama" if ai_ready else None
            if ai_ready:
                print(c(f"  Local AI ready (Ollama: {_st.offline_model}).", FG_GREEN))
            else:
                print(c("  No local AI server — heuristics + fast clean only.", FG_YELLOW))

    # Store provider for risk review
    if ai_provider_used:
        os.environ["AI_PROVIDER_RESOLVED"] = ai_provider_used

    # Mode selection (before file import)
    if RICH_AVAILABLE:
        ui.show_mode_selection()
        mode = ui.prompt_text("Enter 1/2/3/4/5").strip()
    else:
        print()
        print(c("  Choose cleaning mode:", FG_CYAN, BOLD))
        print(c("    1. Safe clean        — fix mojibake, accents→base, strip emojis; keep CJK/structure", FG_GREEN))
        print(c("    2. Strict clean      — strip all accents, emojis, non-ASCII, invisible; keep emails/URLs/numbers", FG_RED))
        print(c("    3. Clean + Translate — fix mojibake → translate to English → fold accents (Approach A)", FG_MAGENTA))
        print(c("    4. Only clean        — fix mojibake only; keep original language & accents", FG_CYAN))
        print(c("    5. Only translate    — translate to English only; skip cleaning", FG_BLUE))
        print()
        mode = prompt("  Enter 1/2/3/4/5: ", FG_YELLOW).strip()
    
    if mode not in ("1", "2", "3", "4", "5"):
        if RICH_AVAILABLE:
            ui.print_warning("Invalid choice — defaulting to Safe clean.")
        else:
            print(c("  Invalid choice — defaulting to Safe clean.", FG_YELLOW))
        mode = "1"

    if mode in ("3", "5") and not ai_ready and not os.environ.get("TRANSLATE_BACKEND"):
        # Edge endpoint doesn't need Ollama — check if it's reachable
        _edge_ok = False
        try:
            from backend.ai.edge_translate import is_reachable as _edge_reachable
            _edge_ok = _edge_reachable(timeout=5)
        except Exception:
            pass
        if not _edge_ok:
            print(c("  WARNING: Translate modes need Edge endpoint or local AI.", FG_RED))
            print(c("           Falling back to Safe clean.", FG_YELLOW))
            mode = "1"

    # Script transliteration: strict mode always does it; safe mode asks.
    fold_scripts = False
    if mode == "2":
        fold_scripts = True
    elif mode == "1":
        print()
        if yes_no(
            "Transliterate non-Latin scripts to English letters "
            "(β→b, л→l, Ա→A, ل->l, ∂→d)?",
            default=False,
        ):
            fold_scripts = True
    # modes 3/4/5: keep original scripts for translation or clean output

    # Emoji handling: ask for modes that keep emojis by default
    keep_emoji_setting: bool | None = None  # None = use mode default
    if mode in ("3", "4", "5"):
        print()
        if RICH_AVAILABLE:
            strip_emoji = not ui.prompt_confirm("Strip emojis from output?", default=False)
        else:
            if yes_no("Strip emojis from output?", default=False):
                strip_emoji = True
            else:
                strip_emoji = False
        keep_emoji_setting = not strip_emoji

    # Enrichment: expand contractions & common abbreviations (optional, off by default)
    enrich_setting = False
    print()
    _enrich_q = ("Expand contractions & common abbreviations "
                 "(don\u2192do not, ASAP\u2192as soon as possible)?")
    if RICH_AVAILABLE:
        enrich_setting = ui.prompt_confirm(_enrich_q, default=False)
    else:
        enrich_setting = yes_no(_enrich_q, default=False)
    if enrich_setting:
        _eng = ("contractions lib" if getattr(clean_mod, "_HAS_CONTRACTIONS", False)
                else "built-in fallback")
        print(c(f"  Enrichment: on ({_eng})", FG_GREEN))

    # 1. file path
    try:
        while True:
            if RICH_AVAILABLE:
                fpath = ui.prompt_text("Enter input file path (Excel / CSV / TXT / JSON)").strip().strip('"')
            else:
                fpath = prompt("Enter input file path (Excel / CSV / TXT / JSON):", FG_CYAN).strip().strip('"')
            if not fpath:
                if RICH_AVAILABLE:
                    ui.print_error("No path given — try again.")
                else:
                    print(c("  No path given — try again.", FG_RED))
                continue
            p = Path(fpath)
            if not p.exists():
                if RICH_AVAILABLE:
                    ui.print_error(f"File not found: {fpath}")
                else:
                    print(c(f"  File not found: {fpath}", FG_RED))
                continue
            break

        # 2. loading + sweep scan
        spin(1.0, "Initializing VModel engine...")
        sweep(2.0, "Scanning file structure")

        # 3. read columns
        raw = Path(fpath).read_bytes()
        try:
            td = ingest_mod.ingest(fpath, raw, fmt=None)
        except Exception as e:
            print(c(f"  Failed to read file: {e}", FG_RED))
            return

        show_columns(td.columns)

        # 4. load rows
        rows = [list(r) for r in td.rows]

        # Show file preview (always shows, using stub UI panel)
        text_cells = sum(
            1 for row in rows
            for cell in row
            if isinstance(cell, str) and cell.strip()
        )
        fmt_name = Path(fpath).suffix.upper().replace('.', '')
        info_table = ui.show_file_info(
            Path(fpath).name, fmt_name,
            len(rows), len(td.columns), text_cells
        )
        ui.console.print(ui.Panel(
            info_table,
            title="FILE INFORMATION",
            border_style="cyan",
        ))
        # Show sample preview
        if rows:
            sample_table = ui.show_sample_preview(td.columns, rows[:5])
            ui.console.print(sample_table)

        # Initialize skip_cols before auto-detection
        skip_cols: set[int] = set()

        # 4b. Auto-detect foreign language columns (for translate modes)
        foreign_cols: list[int] = []  # 1-based column numbers
        if mode in ("3", "5"):
            import re as _dre
            _non_ascii = _dre.compile(r"[^\x00-\x7F]")
            _common_en = {"the", "and", "for", "you", "are", "with", "this",
                          "that", "from", "have", "was", "not", "name", "id",
                          "date", "price", "value", "email", "phone", "url"}
            print()
            print(c("  Auto-detecting foreign language columns...", FG_CYAN))
            for cidx, col in enumerate(td.columns):
                if cidx + 1 in skip_cols:
                    continue
                col_text = []
                for r in rows[:100]:  # sample first 100 rows
                    if cidx < len(r) and isinstance(r[cidx], str) and r[cidx].strip():
                        col_text.append(r[cidx])
                if not col_text:
                    continue
                # Count non-ASCII characters
                non_ascii_count = sum(1 for t in col_text if _non_ascii.search(t))
                ratio = non_ascii_count / len(col_text) if col_text else 0
                # Also check if header suggests it's text (not numeric/date)
                is_texty = col.lower() not in _common_en and not any(
                    kw in col.lower() for kw in ("date", "id", "price", "amount",
                                                 "count", "qty", "total", "sum")
                )
                if ratio > 0.2 and is_texty:  # >20% rows have non-ASCII
                    foreign_cols.append(cidx + 1)
                    lang_hint = " mojibake/accents" if ratio > 0.5 else ""
                    print(c(f"    ✓ {col} (#{cidx+1}) — {ratio:.0%} non-ASCII{lang_hint}",
                            FG_GREEN))
            if foreign_cols:
                print(c(f"  Found {len(foreign_cols)} column(s) with foreign text.",
                        FG_GREEN))
            else:
                print(c("  No foreign columns detected — will process all text.",
                        FG_YELLOW))

        # 5. ask which columns to skip
        if foreign_cols:
            print()
            print(c(f"  Foreign columns detected: {', '.join(
                f'{td.columns[i-1]}(#{i})' for i in foreign_cols
            )}", FG_GREEN))
            skip_input = prompt(
                "Enter column NUMBERS to SKIP (comma-separated). "
                "Leave empty to process detected foreign columns:",
                FG_YELLOW,
            ).strip()
        else:
            skip_input = prompt(
                "Enter column NUMBERS to SKIP (comma-separated). Leave empty to process ALL:",
                FG_YELLOW,
            ).strip()
        if skip_input:
            for part in skip_input.split(","):
                part = part.strip()
                if part.isdigit():
                    n = int(part)
                    if 1 <= n <= len(td.columns):
                        skip_cols.add(n)
            if skip_cols:
                skipped_names = [td.columns[i - 1] for i in sorted(skip_cols)]
                print(c(f"  Will skip: {', '.join(skipped_names)}", FG_YELLOW))
            else:
                print(c("  No valid columns to skip — processing all.", FG_DIM))
        elif foreign_cols and mode in ("3", "5"):
            # Default: process only detected foreign columns
            skip_cols = set(range(1, len(td.columns) + 1)) - set(foreign_cols)
            print(c(f"  Processing foreign columns only: "
                    f"{', '.join(td.columns[i-1] for i in foreign_cols)}", FG_GREEN))

        # 5. cleaning mode already selected earlier
        mode_labels = {
            "1": "Safe clean",
            "2": "Strict clean",
            "3": "Clean + Translate (Approach A)",
            "4": "Only clean (fix mojibake)",
            "5": "Only translate",
        }
        print(c(f"  Mode: {mode_labels.get(mode, mode)}", FG_CYAN))

        if mode == "3":
            # Translation mode — just run clean_file (translation happens inside)
            print()
            if not yes_no("Run translation now?", default=True):
                print(c("  Aborted by user.", FG_RED))
                return

            print()
            progress = Progress(total=len(td.rows), label="Translating rows")
            out_path, changed, err_rows = clean_file(
                fpath,
                skip_cols,
                mode=mode,
                ai_ready=ai_ready,
                progress=progress,
                keep_emoji=keep_emoji_setting,
                enrich=enrich_setting,
            )
            print()
            print(c("═════════════════════════════════════════════════════", FG_MAGENTA))
            print(c("  TRANSLATION COMPLETE", FG_GREEN, BOLD))
            print(c(f"  Output file : {out_path}", FG_CYAN))
            print(c(f"  Cells changed: {changed}", FG_CYAN))
            print(c(f"  Rows w/ errors: {err_rows}", FG_CYAN))
            print(c("═════════════════════════════════════════════════════", FG_MAGENTA))
            print()
        else:
            # Modes 1 & 2: two-tier scan → AI pre-filter → high-risk review → apply
            print()
            if not yes_no("Scan all cells for cleaning patterns now?", default=True):
                print(c("  Aborted by user.", FG_RED))
                return

            # Tier 1: heuristic scan of all cells
            opts = clean_mod.CleanOptions(
                fix_mojibake=True,
                fold_accents=(mode == "1" or mode == "2"),
                normalize_invisible=True,
                fold_symbols=True,
                collapse_punctuation=True,
                keep_emoji=False,
                fold_scripts=fold_scripts,
                transliterate_columns=set(td.columns) if mode == "2" else set(),
                enrich=enrich_setting,
            )
            progress = Progress(total=len(td.rows), label="Scanning cells")
            scan_result = fast_scan_mod.scan_all_cells(
                td.columns, rows, skip_cols, opts,
                progress_callback=progress.update,
            )
            progress.finish(f"{scan_result.changed_cells} cells need cleaning")

            print(c(f"  Rows scanned   : {scan_result.total_rows}", FG_CYAN))
            print(c(f"  Cells changed  : {scan_result.changed_cells}", FG_CYAN))
            print(c(f"  Rows with errors: {scan_result.rows_with_errors}", FG_CYAN))
            print(c(f"  Low risk patterns : {len(scan_result.low_patterns)}  (auto-approved)", FG_GREEN))
            print(c(f"  Medium risk patterns: {len(scan_result.medium_patterns)}  (auto-approved)", FG_YELLOW))
            print(c(f"  High risk patterns : {len(scan_result.high_patterns)}  (needs your approval)", FG_RED))

            # Tier 2: AI pre-filter — only truly high-risk patterns reach human review
            if ai_ready and scan_result.high_patterns:
                print()
                print(c("  Running AI pre-filter on high-risk patterns...", FG_CYAN))
                if ai_ready and yes_no("Use AI pre-filter to reduce high-risk patterns? (slower but more accurate)", default=False):
                    try:
                        filtered = risk_mod.ai_review(
                            scan_result.high_patterns,
                            provider=os.environ.get("AI_PROVIDER_RESOLVED", "ollama"), model=None, online=False,
                        )
                        # Re-classify high_patterns based on AI decision
                        ai_high = [it for it in filtered if it.risk == "high"]
                        ai_auto = [it for it in filtered if it.risk != "high"]
                        print(c(f"  AI pre-filter: {len(ai_high)} still high-risk, {len(ai_auto)} auto-approved", FG_GREEN))
                        # Update high_patterns to only keep AI-confirmed high risk
                        ai_high_set = {(it.src, it.dst) for it in ai_high}
                        scan_result.high_patterns = [
                            p for p in scan_result.high_patterns
                            if (p.src, p.dst) in ai_high_set
                        ]
                        # Mark auto-approved ones as low
                        for pattern in scan_result.low_patterns:
                            pattern.user_decision = "approve"
                    except Exception as e:
                        print(c(f"  AI pre-filter skipped ({e}) — using heuristics only", FG_YELLOW))
                else:
                    print(c("  Skipping AI pre-filter — using heuristics only (fast)", FG_DIM))

            if scan_result.high_patterns:
                print()
                print(c("═════════════════════════════════════════════════════", FG_MAGENTA))
                print(c("  TIER 2 — HIGH-RISK REVIEW (one-by-one)", FG_RED, BOLD))
                print(c("═════════════════════════════════════════════════════", FG_MAGENTA))
                print(c("  Using offline model: gemma-2-2b (local llama.cpp)", FG_CYAN))
                print(c("  You decide per pattern: (a)pprove / (r)eject / (m)odify ALL / (s)kip / (c)custom ALL", FG_YELLOW))

                # Bulk decision option
                bulk = prompt(
                    f"  Bulk decision for all {len(scan_result.high_patterns)} high-risk pattern(s)? "
                    f"(a=approve all / r=reject all / i=review individually): ",
                    FG_YELLOW,
                ).strip().lower()

                if bulk in ("a", "approve all"):
                    for pattern in scan_result.high_patterns:
                        pattern.user_decision = "approve"
                    print(c(f"  Approved all {len(scan_result.high_patterns)} high-risk pattern(s).", FG_GREEN))
                elif bulk in ("r", "reject all"):
                    for pattern in scan_result.high_patterns:
                        pattern.user_decision = "reject"
                    print(c(f"  Rejected all {len(scan_result.high_patterns)} high-risk pattern(s).", FG_RED))
                else:
                    for i, pattern in enumerate(scan_result.high_patterns, 1):
                        # LLM suggestion
                        llm = risk_review_mod.review_high_risk_pattern(
                            pattern.src, pattern.dst, pattern.category,
                            pattern.total_count, pattern.reason,
                            model=os.environ.get("AI_MODEL", "qwen2.5:3b"),
                            original_risk=pattern.risk,
                        )
                        llm_risk = llm.get("risk", "high")
                        llm_reason = llm.get("reason", "")

                        # Compact diff context (show only the changed portion)
                        first_cell = pattern.changes[0]
                        diff = _diff_context(first_cell.original, first_cell.cleaned)

                        print()
                        print(c(f"  [{i}/{len(scan_result.high_patterns)}] HIGH-RISK PATTERN", FG_RED, BOLD))
                        print(c(f"    Category : {pattern.category}", FG_CYAN))
                        print(c(f"    Affects  : {pattern.total_count} cell(s)", FG_CYAN))
                        print(f"    Example  : {diff}")
                        print(c(f"    Heuristic: {pattern.reason}", FG_DIM))
                        print(c(f"    LLM says : {llm_risk} — {llm_reason}", FG_YELLOW, BOLD))

                        while True:
                            break_outer = False
                            ans = prompt(
                                f"    Decision? (a=approve / r=reject / m=modify ALL / s=skip / c=custom ALL / al=approve ALL remaining): ",
                                FG_YELLOW,
                            ).strip().lower()
                            if not ans or ans in ("a", "approve"):
                                pattern.user_decision = "approve"
                                break
                            elif ans in ("al", "approve all"):
                                for remaining in scan_result.high_patterns[i:]:
                                    remaining.user_decision = "approve"
                                print(c(f"    Approved all remaining {len(scan_result.high_patterns) - i + 1} high-risk pattern(s).", FG_GREEN))
                                break_outer = True
                                break
                            elif ans in ("r", "reject"):
                                pattern.user_decision = "reject"
                                break
                            elif ans in ("m", "modify all"):
                                new_dst = prompt(
                                    "    Enter replacement text for ALL cells: ",
                                    FG_CYAN,
                                ).strip()
                                pattern.user_decision = "approve"
                                pattern.user_dst = new_dst if new_dst else pattern.dst
                                break
                            elif ans in ("s", "skip"):
                                pattern.user_decision = "skip"
                                break
                            elif ans in ("c", "custom all"):
                                custom_dst = prompt(
                                    "    Enter custom replacement for ALL cells: ",
                                    FG_CYAN,
                                ).strip()
                                pattern.user_decision = "approve"
                                pattern.user_dst = custom_dst if custom_dst else pattern.dst
                                break
                            else:
                                print(c("      Invalid choice. Use a/r/m/s/c/al.", FG_RED))
                            if break_outer:
                                break
                        if break_outer:
                            break
            else:
                print(c("  No high-risk patterns — all changes are low/medium risk.", FG_GREEN))
                print()

            # Auto-approve low and medium patterns
            for pattern in scan_result.low_patterns:
                pattern.user_decision = "approve"
            for pattern in scan_result.medium_patterns:
                pattern.user_decision = "approve"

            # Apply decisions
            print()
            if not yes_no("Apply all approved changes now?", default=True):
                print(c("  Aborted by user.", FG_RED))
                return

            print()
            total_text_cells = sum(1 for r in rows for c in r if isinstance(c, str) and c)
            print(c(f"  Applying all approved changes to {len(rows):,} rows / {total_text_cells:,} text cells...", FG_CYAN))
            progress = Progress(total=len(rows), label="Applying changes")
            # snapshot originals before apply_decisions mutates rows in place
            original_rows = [list(r) for r in rows]
            cleaned_rows, changed_cells, err_rows = fast_scan_mod.apply_decisions(
                rows, scan_result,
                progress_callback=lambda n: progress.update(n),
            )
            progress.finish(f"{changed_cells:,} cells changed, {err_rows:,} rows with errors")

            # Write output with error column — detected on ORIGINAL values,
            # annotated ✓fixed/✗kept so users see what was actually cleaned
            print(c(f"  Annotating errors for {len(cleaned_rows):,} rows ...", FG_CYAN))
            progress = Progress(total=len(cleaned_rows), label="Annotating errors")
            columns = list(td.columns)
            columns.append("VModel_Errors")
            for ridx, row in enumerate(cleaned_rows):
                err_parts: list[str] = []
                orig_row = original_rows[ridx] if ridx < len(original_rows) else []
                reported_cols: set[int] = set()
                for cidx, col in enumerate(td.columns):
                    if cidx >= len(row) or (cidx + 1) in skip_cols:
                        continue
                    vo = orig_row[cidx] if cidx < len(orig_row) else row[cidx]
                    if not isinstance(vo, str) or not vo:
                        continue
                    v = row[cidx]
                    errs = _cell_errors(vo, col, opts)
                    if errs:
                        errs = _mark_fixed(errs, vo, v if isinstance(v, str) else "")
                        err_parts.append(f"[{col}] " + ", ".join(errs))
                        reported_cols.add(cidx)
                # Also report every column whose value actually changed but was
                # not captured by the error detector, so error_mapped_row_by_row
                # shows all updated columns (not just detector-flagged ones).
                for cidx, col in enumerate(td.columns):
                    if cidx in reported_cols or cidx >= len(row):
                        continue
                    orig = orig_row[cidx] if cidx < len(orig_row) else row[cidx]
                    cleaned = row[cidx]
                    if isinstance(orig, str) and orig and orig != cleaned:
                        orig_short = orig if len(orig) <= 40 else orig[:37] + "..."
                        new_short = cleaned if len(cleaned) <= 40 else cleaned[:37] + "..."
                        err_parts.append(f"[{col}] {orig_short} → {new_short}")
                row.append("; ".join(err_parts))
                if ridx % 1000 == 0 or ridx == len(cleaned_rows) - 1:
                    progress.update(ridx + 1)
            progress.finish(f"{len(cleaned_rows):,} rows annotated")

            # Sanitize all cell values before export
            for row in cleaned_rows:
                for cidx in range(len(row)):
                    row[cidx] = _sanitize_cell(row[cidx])

            # Build output with cleaned-data-only column naming
            out_columns: list[str] = []
            for i, col in enumerate(td.columns):
                suffix = "_not_clean" if (i + 1) in skip_cols else "_cleaned"
                out_columns.append(f"{col}{suffix}")
            out_columns.append("error_mapped_row_by_row")
            out_columns.append("high risk_cleaned")
            out_columns.append("before after")

            # Track rows with changes
            changed_rows_review: set[int] = set()
            progress = Progress(total=len(cleaned_rows), label="Tracking changes")
            for ridx in range(len(cleaned_rows)):
                for cidx in range(len(td.columns)):
                    if cidx < len(original_rows[ridx]) and cidx < len(cleaned_rows[ridx]):
                        if original_rows[ridx][cidx] != cleaned_rows[ridx][cidx]:
                            changed_rows_review.add(ridx)
                            break
                if ridx % 1000 == 0 or ridx == len(cleaned_rows) - 1:
                    progress.update(ridx + 1)
            progress.finish(f"{len(changed_rows_review):,} rows changed")

            # Build output rows
            out_rows_review: list[list[str]] = []
            progress = Progress(total=len(cleaned_rows), label="Building output rows")
            for ridx, row in enumerate(cleaned_rows):
                out_row: list[str] = []
                for cidx in range(len(td.columns)):
                    out_row.append(row[cidx] if cidx < len(row) else "")
                err_cell = row[-1] if row and len(row) > len(td.columns) else ""
                out_row.append(err_cell if isinstance(err_cell, str) else "")
                out_row.append("yes" if ridx in changed_rows_review else "no")
                ba_parts: list[str] = []
                for cidx in range(len(td.columns)):
                    if cidx < len(original_rows[ridx]) and cidx < len(row):
                        orig = original_rows[ridx][cidx]
                        cleaned_val = row[cidx]
                        if isinstance(orig, str) and orig and orig != cleaned_val:
                            ba_parts.append(f"{td.columns[cidx]}: {_diff_context(orig, cleaned_val)}")
                out_row.append("; ".join(ba_parts))
                out_rows_review.append(out_row)
                if ridx % 1000 == 0 or ridx == len(cleaned_rows) - 1:
                    progress.update(ridx + 1)
            progress.finish(f"{len(out_rows_review):,} rows built")

            # Sanitize all cell values before export
            print(c(f"  Sanitizing {len(out_rows_review):,} rows for export ...", FG_CYAN))
            progress = Progress(total=len(out_rows_review), label="Sanitizing rows")
            for ridx, row in enumerate(out_rows_review):
                for i in range(len(row)):
                    row[i] = _sanitize_cell(row[i])
                if ridx % 1000 == 0 or ridx == len(out_rows_review) - 1:
                    progress.update(ridx + 1)
            progress.finish(f"{len(out_rows_review):,} rows sanitized")

            # Export as XLSX only
            src_path = Path(fpath)
            out_path = str(src_path.parent / f"{src_path.stem}_VModel_Cleaned.xlsx")
            print(c(f"  Writing output file: {Path(out_path).name} ...", FG_CYAN))
            res = export_mod.export("xlsx", out_columns, out_rows_review,
                                    name=src_path.stem + "_VModel_Cleaned")
            Path(out_path).write_bytes(res.data)

            print()
            print(c("═════════════════════════════════════════════════════", FG_MAGENTA))
            print(c("  CLEANING COMPLETE", FG_GREEN, BOLD))
            print(c(f"  Output file : {out_path}", FG_CYAN))
            print(c(f"  Rows        : {len(cleaned_rows)}", FG_CYAN))
            print(c(f"  Cells changed: {changed_cells}", FG_CYAN))
            print(c(f"  Rows w/ errors: {err_rows}", FG_CYAN))
            print(c("═════════════════════════════════════════════════════", FG_MAGENTA))
            print()
    finally:
        # Stop local AI server on exit (any path)
        if ai_provider == "llama":
            stop_llama_server()


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print()
        print(c("  Interrupted by user.", FG_RED))
        if os.environ.get("AI_PROVIDER_RESOLVED") == "llama":
            stop_llama_server()
        sys.exit(1)
