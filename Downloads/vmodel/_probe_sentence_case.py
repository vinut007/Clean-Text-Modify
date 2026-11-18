"""Probe _sentence_case behavior (Mode-1 sentence case feature)."""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))
from vmodel_cli import _sentence_case

cases = [
    ("arun was going to school", "Arun was going to school"),
    ("ARUN WAS GOING TO SCHOOL", "Arun was going to school"),
    ("Arun was going to school", "Arun was going to school"),
    ("he left. then she came.", "He left. Then she came."),
    ("really? yes! ok", "Really? Yes! Ok"),
    ("see HTTP://EXAMPLE.COM/Path today", "See HTTP://EXAMPLE.COM/Path today"),
    ("email ARUN.S@EXAMPLE.COM now", "Email ARUN.S@EXAMPLE.COM now"),
    ("it costs \u20ac50 EUR today", "It costs \u20ac50 EUR today"),
    ("don't stop", "Don't stop"),
    ("123 go home", "123 Go home"),
    ("  padded text", "  Padded text"),
    ("\u4e2d\u6587\u6d4b\u8bd5", "\u4e2d\u6587\u6d4b\u8bd5"),
    ("\u2022 item one", "\u2022 Item one"),
    ("", ""),
    ("iPhone and iPad sales", "Iphone and ipad sales"),  # true sentence case lowercases inner caps
    ("it was 3.14 approx", "It was 3.14 approx"),
    ("Mrs. smith arrived", "Mrs. Smith arrived"),
]

fails = 0
for src, want in cases:
    got = _sentence_case(src)
    ok = got == want
    if not ok:
        fails += 1
    mark = "OK " if ok else "FAIL"
    print(f"{mark} {src!r:45} -> {got!r}" + ("" if ok else f"   (want {want!r})"))

print(f"\nRESULT: {len(cases) - fails}/{len(cases)} passed")
sys.exit(1 if fails else 0)
