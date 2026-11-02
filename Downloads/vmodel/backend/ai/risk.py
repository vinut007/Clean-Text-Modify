"""AI risk review — uses Ollama to classify high-risk patterns.

Patterns that are obviously safe (accent folding, mojibake fix, emoji removal)
are auto-approved (risk → "low"). Patterns that might be destructive
(CJK transliteration, removing important chars) stay "high" for human review.
"""
from __future__ import annotations

import json
import os
import re
import urllib.error
import urllib.request

from backend.ai.ollama_client import get_status, chat_ollama

OLLAMA_HOST = os.environ.get("OLLAMA_HOST", "http://localhost:11434")


class _Result:
    def __init__(self, src, dst, category, count, risk, reason):
        self.src = src
        self.dst = dst
        self.category = category
        self.count = count
        self.risk = risk
        self.reason = reason


# Categories that are safe to auto-approve without LLM review
SAFE_CATEGORIES = {"emoji", "symbol", "punctuation"}

# Categories that are high-risk extraction failures - auto-classify as high without LLM
HIGH_RISK_CATEGORIES = {"html_entity", "html_tag", "symbol_noise", "cjk_punct_repeat", "repeated_punct"}

# System prompt for classifying cleaning pattern risk
_RISK_SYSTEM = """You review text-cleaning pattern changes (src → dst) and assign a risk level.

Categories:
- "low"   = safe to auto-approve (accent removal, mojibake fix, emoji removal, punctuation cleanup)
- "medium" = mostly safe but slightly aggressive (symbol folding, invisible char removal)
- "high"  = could lose meaning or change language (CJK transliteration, removing non-Latin scripts, changing proper nouns)

Rules:
- Accent folding (é→e, Generalisée→Generalisee) = low
- Mojibake fix (cafÃ©→cafe) = low
- Emoji removal (😀→"") = low
- CJK/non-Latin script removal/transliteration = high
- Punctuation collapsing (!!!→!) = low
- Symbol folding (→→->) = low

For each pattern, output one line: "low", "medium", or "high".
Output exactly N lines for N patterns, in the same order, one per line.
No extra text."""


def ai_review(patterns, provider="llama", model=None, online=False):
    """Review high-risk patterns using Ollama LLM.

    Auto-approves obviously-safe patterns (low risk), keeps truly risky ones
    (high risk) for human review.

    All patterns are classified in a single batched LLM call for speed.
    """
    status = get_status()
    if not status.offline_available:
        # No LLM — keep all heuristic risk levels
        results = []
        for p in patterns:
            results.append(_Result(
                p.src, p.dst, p.category, p.total_count, p.risk, p.reason,
            ))
        return results

    model = model or status.offline_model or "gemma2:2b"
    results: list[_Result] = []
    to_classify: list[_Result] = []
    for p in patterns:
        # Fast-track: obviously safe categories don't need LLM
        if p.category in SAFE_CATEGORIES:
            results.append(_Result(
                p.src, p.dst, p.category, p.total_count,
                "low", f"Auto-approved: {p.category}",
            ))
            continue
        # High-risk extraction failures don't need LLM either
        if p.category in HIGH_RISK_CATEGORIES:
            results.append(_Result(
                p.src, p.dst, p.category, p.total_count,
                "high", f"Auto-classified: {p.category}",
            ))
            continue
        results.append(None)  # placeholder
        to_classify.append(p)

    if not to_classify:
        return results

    # Build batch prompt with all patterns
    lines = []
    for i, p in enumerate(to_classify, 1):
        lines.append(f"{i}. Category: {p.category} | Reason: {p.reason} | "
                     f"Source: {p.src[:120]} | Dest: {p.dst[:120]}")
    prompt = "\n".join(lines) + "\n\nOutput risk level (low/medium/high) for each pattern, one per line, in order:"

    try:
        reply = chat_ollama(
            [{"role": "system", "content": _RISK_SYSTEM},
             {"role": "user", "content": prompt}],
            model=model,
            temperature=0.0,
            num_predict=max(20, len(to_classify) * 5),
        )
    except Exception:
        reply = ""

    # Parse per-line responses
    risk_lines = [ln.strip().lower() for ln in reply.splitlines() if ln.strip()]
    risk_map = {}
    for ln in risk_lines:
        m = re.match(r"^(\d+)[\s.:\)\-]*\s*(low|medium|high)", ln)
        if m:
            idx = int(m.group(1)) - 1
            risk_map[idx] = m.group(2)
    # Fallback: if all lines are just risk words, map by position
    if not risk_map and len(risk_lines) == len(to_classify):
        for i, ln in enumerate(risk_lines):
            if ln in ("low", "medium", "high"):
                risk_map[i] = ln

    final_results: list[_Result] = []
    classify_idx = 0
    for r in results:
        if r is None:
            p = to_classify[classify_idx]
            classify_idx += 1
            risk = risk_map.get(classify_idx - 1, p.risk)
            final_results.append(_Result(
                p.src, p.dst, p.category, p.total_count,
                risk, p.reason,
            ))
        else:
            final_results.append(r)
    return final_results
