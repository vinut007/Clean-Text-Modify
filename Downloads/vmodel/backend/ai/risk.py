"""AI risk review — uses Ollama to classify high-risk patterns.

Patterns that are obviously safe (accent folding, mojibake fix, emoji removal)
are auto-approved (risk → "low"). Patterns that might be destructive
(CJK transliteration, removing important chars) stay "high" for human review.
"""
from __future__ import annotations

import json
import os
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
SAFE_CATEGORIES = {"mojibake", "replacement", "invalid_utf8", "accent", "invisible",
                   "emoji", "symbol", "punctuation"}

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

Respond with ONLY: low, medium, or high"""


def _llm_classify(src: str, dst: str, category: str, reason: str, model: str, original_risk: str = "high") -> str:
    """Ask Ollama to classify a pattern's risk level. Returns 'low'/'medium'/'high'.

    On any error, falls back to original_risk (safe default: keep heuristic level).
    """
    prompt = f"""Classify this cleaning pattern:

Category: {category}
Reason: {reason}
Source: {src[:200]}
Destination: {dst[:200]}

Risk level (low/medium/high):"""
    try:
        reply = chat_ollama(
            [{"role": "system", "content": _RISK_SYSTEM},
             {"role": "user", "content": prompt}],
            model=model,
            temperature=0.0,
            num_predict=10,
        )
        reply = reply.strip().lower()
        if "high" in reply:
            return "high"
        if "medium" in reply:
            return "medium"
        if "low" in reply:
            return "low"
    except Exception:
        pass
    return original_risk


def ai_review(patterns, provider="llama", model=None, online=False):
    """Review high-risk patterns using Ollama LLM.

    Auto-approves obviously-safe patterns (low risk), keeps truly risky ones
    (high risk) for human review.
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
    results = []
    for p in patterns:
        # Fast-track: obviously safe categories don't need LLM
        if p.category in SAFE_CATEGORIES and p.risk == "low":
            results.append(_Result(
                p.src, p.dst, p.category, p.total_count,
                "low", f"Auto-approved: {p.category}",
            ))
            continue

        risk = _llm_classify(p.src, p.dst, p.category, p.reason, model, original_risk=p.risk)
        results.append(_Result(
            p.src, p.dst, p.category, p.total_count,
            risk, p.reason,
        ))
    return results
