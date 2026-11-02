"""Fast risk review for high-risk patterns (LLM suggestion stub)."""
from __future__ import annotations


def review_high_risk_pattern(src, dst, category, total_count, reason, model="gemma-2-2b"):
    """Return dict with risk and reason for a high-risk pattern."""
    return {
        "risk": "high",
        "reason": reason or f"{category} pattern ({total_count} cells)",
    }
