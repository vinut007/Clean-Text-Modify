"""Edge translate (stub)."""
from __future__ import annotations


def is_reachable(timeout=5):
    return False


def translate_batch(texts, source="", target="en"):
    """Stub — returns texts unchanged."""
    return [{"text": t, "ok": True} for t in texts]
