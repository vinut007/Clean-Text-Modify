"""Ollama client (stub)."""
from __future__ import annotations

from dataclasses import dataclass


@dataclass
class Status:
    offline_available: bool = False
    offline_model: str | None = None


def get_status() -> Status:
    return Status(offline_available=False, offline_model=None)


def chat_ollama(messages, model=None, temperature=0.1, num_predict=4096):
    """Stub — returns empty string when Ollama not available."""
    return ""
