"""AI risk review module (stubbed — uses heuristics when no LLM available)."""
from __future__ import annotations


def ai_review(patterns, provider="llama", model=None, online=False):
    """Review high-risk patterns. Returns list with .risk attribute set.

    Without a real LLM, all patterns keep their heuristic risk level.
    """
    results = []
    for p in patterns:
        class _Result:
            def __init__(self, src, dst, category, count, risk, reason):
                self.src = src
                self.dst = dst
                self.category = category
                self.count = count
                self.risk = risk
                self.reason = reason
        results.append(_Result(
            p.src, p.dst, p.category, p.total_count, p.risk, p.reason,
        ))
    return results
