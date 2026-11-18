"""Translation backend tests: language table + fast HTTP translate + resolve."""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from backend.ai.languages import LANGUAGES, resolve_language  # noqa: E402
from backend.ai import edge_translate  # noqa: E402

fails: list[str] = []


def check(cond: bool, msg: str) -> None:
    print(("  ok   " if cond else "  FAIL ") + msg)
    if not cond:
        fails.append(msg)


print("== languages table ==")
check(len(LANGUAGES) >= 200,
      f"at least 200 languages (got {len(LANGUAGES)})")
check(len(set(LANGUAGES.values())) >= 150,
      f"distinct names >= 150 (got {len(set(LANGUAGES.values()))})")

print("== resolve_language ==")
check(resolve_language("fr") == ("fr", LANGUAGES["fr"]), "code fr")
check(resolve_language("FR")[0] == "fr", "uppercase FR")
check(resolve_language("French")[0] == "fr", "name French")
check(resolve_language("french")[0] == "fr", "name french")
check(resolve_language("Hindi")[0] == "hi", "name Hindi")
check(resolve_language("  de  ")[0] == "de", "padded de")
check(resolve_language("farsi")[0] == "fa", "alias farsi -> fa")
check(resolve_language("mandarin")[0] == "zh-CN", "alias mandarin -> zh-CN")
check(resolve_language("chinese")[0] == "zh", "ambiguous chinese -> bare zh")
check(resolve_language("spanish")[0] == "es", "ambiguous spanish -> bare es")
check(resolve_language("hind")[0] == "hi", "substring hind -> hi")
check(resolve_language("zzzz") is None, "bogus query -> None")
check(resolve_language("") is None, "empty query -> None")
for code in ("ar", "ja", "ru", "hi", "zh-CN", "pt-BR", "yue", "haw",
             "bo-CN", "sw", "tl", "he", "fa"):
    check(code in LANGUAGES, f"language {code} present")

print("== _parse (offline) ==")
sample = (b'[[["Hello world","Hola mundo",null,null,3]],null,"es",'
          b'null,null,null,1]')
check(edge_translate._parse(sample) == "Hello world", "parses gtx JSON")
check(edge_translate._parse(b"not json") is None, "malformed -> None")
check(edge_translate._parse(b"{}") is None, "dict body -> None")
check(edge_translate._parse(b"[]") is None, "empty list -> None")

print("== is_reachable (network) ==")
reachable = edge_translate.is_reachable(timeout=10)
print(f"  endpoint reachable: {reachable}")
check(isinstance(reachable, bool), "is_reachable returns bool")

print("== _guess_candidates (offline) ==")
gc = edge_translate._guess_candidates
c = gc("Analista de Visual Merchandising | Cia Hering", "en")
check(bool(c) and c[0] in ("pt", "es", "fr"),
      f"mixed Portuguese -> romance source {c}")
c = gc("Angestellte im Vertrieb bei TIB Lackmann GmbH", "en")
check(bool(c) and c[0] == "de", f"German -> de {c}")
c = gc("Software Engineer at Rio de Janeiro", "en")
check(c == [], f"English (en tie) -> no retry {c}")
c = gc("Senior Software Engineer | Python | AWS", "en")
check(c == [], f"pure English -> no retry {c}")

print("== translate_batch (network) ==")
if not reachable:
    print("  SKIP — endpoint unreachable (offline?)")
else:
    # source auto-detect -> English
    res = edge_translate.translate_batch(
        ["Bonjour le monde", "Hola mundo, ¿cómo estás?",
         "Hallo Welt, wie geht es dir?"],
        source="", target="en",
    )
    check(len(res) == 3, "returns 3 results")
    joined = " ".join(r["text"].lower() for r in res)
    check(all(r["ok"] for r in res), "all ok=True")
    check("hello" in joined, f"fr/es/de -> English ({joined[:80]!r})")

    # regression: Google auto-detect calls these Portuguese strings "en"
    # and echoes them back — the retry stage must translate them anyway.
    mixed = [
        "Analista de Visual Merchandising Senior | Stylist | Marketing",
        "Analista de Visual Merchandising | Cia Hering",
        "Analista Desenvolvedor Full Stack | .NET | Angular | TypeScript",
    ]
    res_mixed = edge_translate.translate_batch(mixed, source="", target="en")
    for t, r in zip(mixed, res_mixed):
        check(r["ok"] and r["text"].strip().casefold() != t.strip().casefold(),
              f"portuguese translated ({t[:40]!r} -> {r['text'][:40]!r})")

    # and genuine English must NOT be mangled by the retry stage
    english = ["Senior Software Engineer | Python | AWS",
               "Software Engineer at Rio de Janeiro"]
    res_en = edge_translate.translate_batch(english, source="", target="en")
    for t, r in zip(english, res_en):
        check(r["ok"] and r["text"].strip() == t.strip(),
              f"english unchanged ({t[:35]!r})")

    # English -> French target
    res2 = edge_translate.translate_batch(
        ["Good morning my friend"], source="", target="fr")
    check(res2[0]["ok"] and "bonjour" in res2[0]["text"].lower(),
          f"en -> fr target ({res2[0]['text']!r})")

    # order preserved on a bigger batch with mixed scripts
    texts = [f"text number {i} bonjour" for i in range(20)]
    res3 = edge_translate.translate_batch(texts, source="", target="en")
    check(len(res3) == 20, "20 results")
    check(all(r["ok"] for r in res3), "20 ok")
    check("text number 19" in res3[19]["text"],
          f"order preserved (last={res3[19]['text']!r})")

    # failed/empty handling: empty text passes through
    res4 = edge_translate.translate_batch([""], source="", target="en")
    check(res4[0] == {"text": "", "ok": True}, "empty text passthrough")

print()
if fails:
    print(f"RESULT: FAIL ({len(fails)})")
    for f in fails:
        print("  -", f)
    sys.exit(1)
print("RESULT: PASS")
