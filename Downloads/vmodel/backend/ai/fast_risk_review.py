"""Fast risk review for high-risk patterns — uses Ollama LLM suggestion."""
from __future__ import annotations

import json
import os
import urllib.error
import urllib.request

from backend.ai.ollama_client import chat_ollama, get_status

OLLAMA_HOST = os.environ.get("OLLAMA_HOST", "http://localhost:11434")

_REVIEW_SYSTEM = """You review a single text-cleaning pattern change (src → dst).

Classify the risk of APPLYING this change:
- "low"  = safe change (accent removal, mojibake fix, emoji removal, punctuation cleanup, symbol folding)
- "medium" = mostly safe but could be slightly aggressive
- "high" = could lose meaning, change language, or destroy data (CJK removal, replacing replacement char, removing proper nouns)

Respond with ONLY: low, medium, or high"""


def review_high_risk_pattern(src, dst, category, total_count, reason, model="gemma2:2b"):
    """Return dict with risk and reason for a high-risk pattern, using Ollama."""
    status = get_status()
    if status.offline_available and status.offline_model:
        model = status.offline_model

    try:
        prompt = f"""Classify this cleaning pattern's risk:

Category: {category}
Reason: {reason}
Source: {src[:200]}
Destination: {dst[:200]}

Risk level (low/medium/high):"""
        reply = chat_ollama(
            [{"role": "system", "content": _REVIEW_SYSTEM},
             {"role": "user", "content": prompt}],
            model=model,
            temperature=0.0,
            num_predict=10,
        )
        reply = reply.strip().lower()
        if "high" in reply:
            risk = "high"
        elif "medium" in reply:
            risk = "medium"
        elif "low" in reply:
            risk = "low"
        else:
            risk = "high"
    except Exception:
        risk = "high"

    return {
        "risk": risk,
        "reason": reason or f"{category} pattern ({total_count} cells)",
    }
