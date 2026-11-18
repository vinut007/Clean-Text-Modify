"""Fast HTTP translation backend (keyless, 100% free, no API key).

Providers (both are Google Translate under the hood, no key required):
  1. clients5.google.com  — `translate_a/t?client=dict-chrome-ex`  **primary**
     Supports MANY texts per request (repeated `q` params, POST form body),
     order-preserving, auto language detect per text. Measured ~215 texts/sec
     in a single 500-text batch; ~190/sec with parallel 50-text chunks.
     This host has its own quota, separate from translate.googleapis.com.
  2. translate.googleapis.com — `translate_a/single?client=gtx`  **fallback**
     One GET per text, ~64 texts/sec at 24 workers.

Selection: `TRANSLATE_PROVIDER=auto|clients5|gtx` (default auto: clients5,
falling back to gtx per text if chunked requests fail).
`TRANSLATE_ENDPOINT` overrides the gtx endpoint (testing / proxy).
`TRANSLATE_BATCH` chunk size (default 50, max 200).

Public API (drop-in, unchanged):
  is_reachable(timeout) -> bool
  translate_batch(texts, source, target, workers) -> [{"text", "ok"}, ...]
"""
from __future__ import annotations

import json
import os
import random
import re
import time
import urllib.error
import urllib.parse
import urllib.request
from concurrent.futures import ThreadPoolExecutor

_GTX_ENDPOINT = "https://translate.googleapis.com/translate_a/single"
_C5_ENDPOINT = "https://clients5.google.com/translate_a/t"
_UA = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/126.0 Safari/537.36"
)
_DEFAULT_WORKERS = 16      # parallel chunk requests (clients5 mode)
_DEFAULT_BATCH = 200       # texts per chunk request (max 200)
_CHUNK_CHARS = 20000        # max characters per chunk request
_probe: dict = {"ok": None, "ts": 0.0}
# Provider is Edge/clients5 only — no gtx fallback and no cooldown sleeps.
# 429/503 responses simply fail; callers keep the original text (no wipe).
_cool: dict = {
    "c5": {"until": 0.0, "strikes": 0},
    "gtx": {"until": 0.0, "strikes": 0},
}


def _workers() -> int:
    try:
        n = int(os.environ.get("TRANSLATE_WORKERS", _DEFAULT_WORKERS))
    except ValueError:
        n = _DEFAULT_WORKERS
    return max(1, min(64, n))


def _batch_size() -> int:
    try:
        n = int(os.environ.get("TRANSLATE_BATCH", _DEFAULT_BATCH))
    except ValueError:
        n = _DEFAULT_BATCH
    return max(1, min(200, n))


def _provider() -> str:
    p = (os.environ.get("TRANSLATE_PROVIDER", "auto") or "auto").lower()
    if p in ("gtx", "google", "single"):
        return "gtx"
    if p in ("clients5", "batch", "c5"):
        return "clients5"
    return "auto"


# ---------------------------------------------------------------------------
# Source-language guessing (fixes Google auto-detect misclassifying short
# mixed strings like "Analista de Visual Merchandising | Stylist" as English
# and echoing them back untranslated).
# ---------------------------------------------------------------------------
_STOP: dict[str, tuple[frozenset, frozenset]] = {
    "pt": (frozenset("nao sao esta estao uma um dos das nas nos para com "
                     "pelo pela tambem mais como mas seu sua seus suas os as "
                     "ao aos sera tem foi eram entre sobre depois quando "
                     "onde qual quem da do ja ate".split()),
           frozenset("de e o a em que se por".split())),
    "es": (frozenset("el los las del al para con mas pero como sus una unos "
                     "unas esta estan son fue muy tambien porque cuando donde "
                     "desde hasta entre sobre y".split()),
           frozenset("de la que se por en".split())),
    "fr": (frozenset("les des du une pour avec dans sur aux est sont mais "
                     "plus aussi comme cette ces qui dont ou leur leurs "
                     "et".split()),
           frozenset("de la le en que".split())),
    "de": (frozenset("und mit bei fur fuer von im zum zur ein eine einer einem "
                     "eines ist nicht oder als auch auf aus den dem des der "
                     "die das sind wird werden kann".split()),
           frozenset("in zu an".split())),
    "it": (frozenset("della delle degli dei del gli il lo per con che non "
                     "sono piu anche questo questa nel nella alla uno".split()),
           frozenset("di da in su la le e".split())),
    "nl": (frozenset("het een van voor met op dat dit niet zijn bij aan ook "
                     "maar als dan nog wel".split()),
           frozenset("de in te is".split())),
    "id": (frozenset("yang untuk dengan dan dari ini itu adalah pada ke tidak "
                     "akan atau saya kami sudah juga karena bisa ada".split()),
           frozenset("di".split())),
    "pl": (frozenset("sie jest nie dla oraz przez sa byl byla bylo beda "
                     "jego jej ich tym tego ktory ktora ktore".split()),
           frozenset("i w z na do od po jak tak ze".split())),
    "cs": (frozenset("jsou byl byla bylo pro nebo ale kdyz ktery ktera ktere "
                     "jeho jeji".split()),
           frozenset("v na do po se je ze tak jak".split())),
    "ro": (frozenset("este sunt pentru ca cu pe din nu sau mai fost fi".split()),
           frozenset("in si de la".split())),
    "tr": (frozenset("ve bir bu icin ile cok olarak olan ne var yok ama gibi "
                     "kadar sonra".split()),
           frozenset("da de".split())),
    "vi": (frozenset("cua khong duoc nguoi nhung cac trong voi".split()),
           frozenset("va la co mot nay do de".split())),
    "sv": (frozenset("och att ar pa for med av som den det ett till inte "
                     "har var men ocksa".split()),
           frozenset("i en".split())),
    "da": (frozenset("og er pa for med af som den det et til ikke har "
                     "var men ogsa".split()),
           frozenset("i en at".split())),
    "no": (frozenset("og er pa for med af som den det et til ikke har "
                     "var men ogsa".split()),
           frozenset("i en at".split())),
    "fi": (frozenset("ja on ei etta se han ovat oli mutta kun niin tai myos "
                     "joka tama nama".split()),
           frozenset("".split())),
    "hu": (frozenset("hogy nem egy van volt meg ha mar csak mint vagy ez "
                     "az".split()),
           frozenset("a de is".split())),
    "tl": (frozenset("ang mga hindi ito may para ay si ni".split()),
           frozenset("na ng sa at".split())),
    "en": (frozenset("the and of for with at in on is are was were you this "
                     "that from by as to it an be or not have has will would "
                     "can could should we they he she but if my our your "
                     "their there what when where who how all any some do "
                     "does did".split()),
           frozenset("a i no so".split())),
}
_PRIO = ("pt", "es", "fr", "de", "it", "id", "nl", "pl", "ro", "tr", "vi",
         "tl", "sv", "da", "no", "fi", "hu", "cs")
# Morphological hints (word endings). Deliberately EXCLUDES suffixes shared
# with English (-tion, -ment, -er, -or, -ist, ...) so English text is never
# mistaken for another language.
_SUFFIX: dict[str, tuple[str, ...]] = {
    "pt": ("cao", "coes", "dor", "dora", "dores", "idade", "idades",
           "eiro", "eira", "inho", "inha"),
    "es": ("cion", "ciones", "sion", "siones", "dad", "dades", "illo",
           "illa", "illos", "illas"),
    "de": ("ung", "ungen", "heit", "keiten", "keit", "lich", "schaft",
           "schaften", "chen"),
    "fr": ("eux", "euse", "ique", "iques", "aison"),
    "it": ("zione", "zioni", "mente", "aggio", "elli", "ello", "ella"),
    "pl": ("ski", "skiego", "ska", "cki"),
    "nl": ("heid", "heden"),
}
_WORD_RE = re.compile(r"[^\W\d_]+", re.UNICODE)
# High-precision role/profession vocabulary (weight 2). These are never
# English words, so a match is strong evidence of the source language.
_ROLE: dict[str, frozenset] = {
    "pt": frozenset("analista desenvolvedor desenvolvedora programador programadora gerente vendedor vendedora atendente auxiliar estagiario engenheiro engenheira coordenador coordenadora consultor consultora contador motorista recepcionista tecnico tecnica especialista operador operadora professor professora enfermeiro enfermeira advogado advogada eletricista mecanico soldador pintor pedreiro cozinheiro garcom vigilante almoxarife comprador planejador vendas".split()),
    "es": frozenset("analista desarrollador desarrolladora programador programadora gerente vendedor vendedora ingeniero ingeniera coordinador coordinadora consultor consultora contador conductor recepcionista tecnico tecnica especialista operador operadora profesor profesora enfermero enfermera abogado abogada electricista mecanico soldador pintor albanil cocinero camarero vigilante comprador planificador".split()),
    "de": frozenset("entwickler entwicklerin ingenieur ingenieurin verkaufer berater beraterin techniker technikerin spezialist spezialistin leiter leiterin mitarbeiter mitarbeiterin angestellte angestellter arbeiter arbeiterin fahrer fahrerin pfleger pflegerin buchhalter elektriker mechaniker schlosser maler koch kellner kellnerin".split()),
    "fr": frozenset("developpeur developpeuse ingenieur gerant gerante coordinateur coordinatrice superviseur technicien technicienne specialiste consultante vendeur vendeuse operateur operatrice receptionniste stagiaire directeur directrice professeur infirmier infirmiere medecin avocat avocate comptable electricien mecanicien soudeur peintre cuisinier cuisiniere serveur serveuse".split()),
    "it": frozenset("sviluppatore sviluppatrice ingegnere gerente coordinatore coordinatrice supervisore tecnico specialista consulente venditore venditrice operatore operatrice autista apprendista direttore direttrice professore professoressa infermiere infermiera medico avvocato avvocatessa contabile elettricista meccanico saldatore pittore muratore cuoco cuoca cameriere cameriera".split()),
    "id": frozenset("analis pengembang insinyur manajer koordinator asisten teknisi spesialis konsultan penjual sopir resepsionis magang direktur guru perawat dokter pengacara akuntan tukang montir koki pelayan keamanan satpam".split()),
    "nl": frozenset("analist ontwikkelaar ingenieur coordinator technicus consultant verkoper chauffeur stagiair directeur leraar verpleegkundige advocaat elektricien monteur lasser schilder metselaar kok ober bewaker".split()),
    "pl": frozenset("analityk programista kierownik sprzedawca inzynier technik specjalista konsultant kierowca recepcjonista praktykant dyrektor nauczyciel pielegniarka lekarz prawnik ksiegowy elektryk mechanik spawacz malarz murarz kucharz kelner ochroniarz".split()),
    "sv": frozenset("analytiker utvecklare ingenjor koordinator tekniker konsult saljare chauffor praktikant direktor larare sjukskoterska lakare advokat revisor elektriker mekaniker svarvare malare murare kock servitor vakt".split()),
    "da": frozenset("analytiker udvikler ingenior koordinator tekniker konsulent salger chauffor praktikant direktor laerer sygeplejerske laege advokat revisor elektriker mekaniker svejser maler murer kok tjener vagt".split()),
    "no": frozenset("analytiker utvikler ingenior koordinator tekniker spesialist konsulent selger sjafor".split()),
    "ro": frozenset("analist dezvoltator inginer coordonator tehnician vanzator sofer receptioner stagiar profesor avocat contabil electrician mecanic sudor zugrav bucatar chelner paznic asistent".split()),
    "tr": frozenset("analist gelistirici muhendis yonetici koordinator teknisyen uzman danisman satici sofor resepsiyonist stajyer mudur ogretmen hemsire doktor avukat muhasebeci elektrikci tamirci kaynakci boyaci duvarci garson guvenlik".split()),
}


def _fold(s: str) -> str:
    import unicodedata
    return "".join(c for c in unicodedata.normalize("NFD", s)
                   if not unicodedata.combining(c))


def _wordset(text: str) -> set[str]:
    out: set[str] = set()
    for w in _WORD_RE.findall(text):
        if 2 <= len(w) <= 5 and w.isupper():
            continue  # short acronym (IT, AWS, TI, SAP) — not a function word
        out.add(_fold(w).casefold())
    return out


def _suffix_scores(words: set[str]) -> dict[str, int]:
    out: dict[str, int] = {}
    for lang, ends in _SUFFIX.items():
        n = 0
        for w in words:
            for e in ends:
                if len(w) > len(e) + 1 and w.endswith(e):
                    n += 1
                    break
            if n >= 3:
                break
        if n:
            out[lang] = n
    return out


def _guess_candidates(text: str, target: str, limit: int = 3) -> list[str]:
    """Guess likely source languages of `text` from stopword evidence.

    Returns an ordered list of non-target language codes (best first).
    English wins ties, so genuine English text is never retried.
    """
    words = _wordset(text)
    if not words:
        return []
    scored: dict[str, int] = {}
    for lang, (strong, weak) in _STOP.items():
        s = 3 * len(words & strong) + len(words & weak)
        if s:
            scored[lang] = s
    role_hits: dict[str, int] = {}
    for lang, roles_ in _ROLE.items():
        n = len(words & roles_)
        if n:
            role_hits[lang] = n
            scored[lang] = scored.get(lang, 0) + min(4, 2 * n)
    suff = _suffix_scores(words)
    for lang, n in suff.items():
        scored[lang] = scored.get(lang, 0) + n
    en_score = scored.get("en", 0)
    scored.pop(target, None)
    if not scored:
        return []
    top = max(scored.values())
    # Strong foreign evidence (role word or >=2 suffix hits) overrides an
    # English-stopword lead — mixed strings like "Analista Fiscal | ...
    # Accounting and Financial" still need the Portuguese part translated.
    strong_foreign = (any(role_hits.get(l) for l in scored)
                      or any(suff.get(l, 0) >= 2 for l in scored))
    if target == "en" and en_score > top and not strong_foreign:
        return []
    prio = {lang: i for i, lang in enumerate(_PRIO)}
    return sorted(scored, key=lambda l: (-scored[l], prio.get(l, 99)))[:limit]



def _cool_down_state() -> dict:
    """Expose internal rate-limit state for diagnostics/heartbeat logging."""
    return {"until": 0.0, "strikes": 0}


def _http(url: str, timeout: float, data: bytes | None = None,
          content_type: str | None = None) -> bytes | None:
    headers = {"User-Agent": _UA}
    if content_type:
        headers["Content-Type"] = content_type
    req = urllib.request.Request(url, data=data, headers=headers)
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return resp.read()
    except Exception:
        return None


# ---------------------------------------------------------------------------
# clients5 (batched) — primary
# ---------------------------------------------------------------------------
def _parse_batch(body: bytes) -> list[str] | None:
    """Parse a translate_a/t response: [[translated, detected], ...] in order."""
    try:
        data = json.loads(body)
    except Exception:
        return None
    if not isinstance(data, list) or not data:
        return None
    out: list[str] = []
    for item in data:
        if isinstance(item, list) and item and isinstance(item[0], str):
            out.append(item[0])
        elif isinstance(item, str):
            out.append(item)
        else:
            return None
    return out


def _c5_request(texts: list[str], target: str,
                sl: str = "auto") -> list[str] | None:
    """One batched POST. Returns translated texts in order, or None."""
    url = (f"{_C5_ENDPOINT}?client=dict-chrome-ex"
           f"&sl={urllib.parse.quote(sl)}&tl={urllib.parse.quote(target)}")
    data = urllib.parse.urlencode([("q", t) for t in texts]).encode()
    body = _http(url, timeout=45.0, data=data,
                 content_type="application/x-www-form-urlencoded")
    if not body:
        return None
    parsed = _parse_batch(body)
    if parsed is None or len(parsed) != len(texts):
        return None
    return parsed


def _c5_batch(texts: list[str], target: str) -> list[dict]:
    """Translate one chunk with clients5; split-and-retry on failure."""
    res = _c5_request(texts, target)
    if res is not None:
        return [{"text": t, "ok": True} for t in res]
    if len(texts) == 1:
        return [{"text": texts[0], "ok": False}]
    # One transient failure shouldn't sink the whole chunk — one retry,
    # then split in half (recursively) so only bad texts fail.
    res = _c5_request(texts, target)
    if res is not None:
        return [{"text": t, "ok": True} for t in res]
    mid = len(texts) // 2
    return _c5_batch(texts[:mid], target) + _c5_batch(texts[mid:], target)


def _chunks(items: list[tuple[int, str]], max_items: int,
            max_chars: int):
    cur: list[tuple[int, str]] = []
    chars = 0
    for idx, text in items:
        if cur and (len(cur) >= max_items or chars + len(text) > max_chars):
            yield cur
            cur, chars = [], 0
        cur.append((idx, text))
        chars += len(text)
    if cur:
        yield cur


# ---------------------------------------------------------------------------
# gtx response parser (kept for the offline tests)
# ---------------------------------------------------------------------------
def _endpoint() -> str:
    """gtx endpoint URL — TRANSLATE_ENDPOINT env overrides (testing/proxy)."""
    return os.environ.get("TRANSLATE_ENDPOINT") or _GTX_ENDPOINT


def _parse(body: bytes) -> str | None:
    """Parse a gtx `translate_a/single` response into the translated text."""
    try:
        data = json.loads(body)
    except Exception:
        return None
    if not isinstance(data, list) or not data or not isinstance(data[0], list):
        return None
    parts: list[str] = []
    for seg in data[0]:
        if isinstance(seg, list) and seg and isinstance(seg[0], str):
            parts.append(seg[0])
    return "".join(parts) if parts else None


def _same(a: str, b: str) -> bool:
    return a.strip().casefold() == b.strip().casefold()


def _c5_batch_sl(texts: list[str], target: str, sl: str) -> list[dict]:
    """Like _c5_batch but with a fixed source language."""
    res = _c5_request(texts, target, sl)
    if res is not None:
        return [{"text": t, "ok": True} for t in res]
    if len(texts) == 1:
        return [{"text": texts[0], "ok": False}]
    mid = len(texts) // 2
    return _c5_batch_sl(texts[:mid], target, sl) + _c5_batch_sl(texts[mid:],
                                                                target, sl)


def _retry_unchanged(out: list[dict], texts: list[str], target: str) -> None:
    """Re-translate results that came back unchanged when stopword evidence
    says the text is NOT in the target language.

    Google's auto-detect misclassifies short mixed strings (e.g.
    "Analista de Visual Merchandising | Stylist" -> detected as "en" and
    echoed back). Retrying with a guessed explicit source language fixes it.
    Modifies `out` in place; never overwrites with an unchanged result.
    """
    if target != "en":
        return
    if (os.environ.get("TRANSLATE_RETRY_UNCHANGED", "1") or "1").lower() in (
            "0", "false", "no", "off"):
        return
    if _provider() == "gtx":  # explicit gtx choice (or mock endpoint in tests)
        return
    pending: dict[int, list[str]] = {}
    for i, r in enumerate(out):
        text = texts[i]
        if not text or not text.strip():
            continue
        # Retry unchanged successes AND failed requests (ok=False == original
        # text) — a failed chunk shouldn't lose the source-language guess.
        if _same(r["text"], text):
            cands = _guess_candidates(text, target)
            if cands:
                pending[i] = cands
    if not pending:
        return

    n_workers = _workers()

    def _run_group(sl: str, idxs: list[int]) -> list[str | None]:
        items = [texts[i] for i in idxs]
        res: list[str | None] = [None] * len(items)
        chunks = list(_chunks(list(enumerate(items)), _batch_size(),
                              _CHUNK_CHARS))
        for chunk in chunks:
            part = [t for _, t in chunk]
            got = _c5_batch_sl(part, target, sl)
            for (idx, _), r in zip(chunk, got):
                res[idx] = r["text"] if r["ok"] else None
        return res

    for _round in range(25):
        groups: dict[str, list[int]] = {}
        for i, cands in pending.items():
            groups.setdefault(cands[0], []).append(i)
        if not groups:
            return
        if len(groups) == 1 or n_workers <= 1:
            results = [(sl, idxs, _run_group(sl, idxs))
                       for sl, idxs in groups.items()]
        else:
            # Retries are gentler on the endpoint: few concurrent groups.
            with ThreadPoolExecutor(
                    max_workers=min(3, n_workers, len(groups))) as pool:
                futs = {sl: pool.submit(_run_group, sl, idxs)
                        for sl, idxs in groups.items()}
                results = [(sl, idxs, futs[sl].result())
                           for sl, idxs in groups.items()]
        next_pending: dict[int, list[str]] = {}
        progressed = False
        for _sl, idxs, res in results:
            for i, tr in zip(idxs, res):
                if tr is None:
                    next_pending[i] = pending[i]
                elif not _same(tr, texts[i]):
                    out[i] = {"text": tr, "ok": True}
                    progressed = True
                else:
                    rest = pending[i][1:]
                    if rest:
                        next_pending[i] = rest
        pending = next_pending
        if progressed:
            continue  # cooldown may have cleared; keep draining pending
        # No text changed this round — stop hammering the endpoint.
        return


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------
def is_reachable(timeout: float = 8) -> bool:
    """Probe the backend once; cache the result for 30 seconds.

    Tries the batched clients5 host first, then the gtx fallback.
    Fails fast (no long wait) while a rate-limit cooldown is active.
    """
    global _probe
    now = time.time()
    if _probe["ok"] is not None and now - _probe["ts"] < 30:
        return bool(_probe["ok"])
    if _cool["c5"]["until"] > now:  # penalty window — do not wait it out here
        _probe = {"ok": False, "ts": now}
        return False
    pref = _provider()
    if pref != "gtx":
        url = f"{_C5_ENDPOINT}?client=dict-chrome-ex&sl=auto&tl=en"
        data = urllib.parse.urlencode([("q", "hello")]).encode()
        body = _http(url, timeout, data=data,
                     content_type="application/x-www-form-urlencoded")
        ok = bool(body) and _parse_batch(body) is not None
    _probe = {"ok": ok, "ts": now}
    return ok


def translate_batch(texts, source: str = "", target: str = "en",
                    workers: int | None = None) -> list[dict]:
    """Translate texts (batched clients5 first, gtx fallback).

    Returns a list of {"text": str, "ok": bool} in the SAME order as `texts`.
    Failed items report ok=False with the original text (callers keep it).
    """
    texts = list(texts)
    if not texts:
        return []
    out: list[dict] = [{"text": t, "ok": True} if (not t or not t.strip())
                       else {"text": t, "ok": False} for t in texts]
    todo = [(i, t) for i, t in enumerate(texts) if t and t.strip()]
    if not todo:
        return out

    pref = _provider()
    if pref != "gtx":  # gtx fallback removed — Edge/clients5 only
        n_workers = workers or _workers()
        chunks = list(_chunks(todo, _batch_size(), _CHUNK_CHARS))

        def _run(chunk):
            return [(i, r) for (i, _), r in
                    zip(chunk, _c5_batch([t for _, t in chunk], target))]

        if len(chunks) == 1 or n_workers <= 1:
            done = [pair for chunk in chunks for pair in _run(chunk)]
        else:
            with ThreadPoolExecutor(max_workers=min(n_workers, len(chunks))) as pool:
                done = [pair for group in pool.map(_run, chunks) for pair in group]
        for i, r in done:
            out[i] = r
        failed = [i for i, r in enumerate(out) if not r["ok"] and texts[i].strip()]
    else:
        failed = [i for i, _ in todo]

    # Fix Google auto-detect misclassification (echoed-back texts).
    _retry_unchanged(out, texts, target)

    # Never accept an EMPTY translation: it would wipe the cell. Google
    # occasionally returns "" under load; mark those failed so callers keep
    # the original text.
    for i, r in enumerate(out):
        if (r.get("ok") and texts[i].strip()
                and not (r.get("text") or "").strip()):
            out[i] = {"text": texts[i], "ok": False}
    return out
