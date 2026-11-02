"""Ollama client — checks/starts Ollama server and lists available models."""
from __future__ import annotations

import os
import subprocess
import time
import urllib.error
import urllib.request
from dataclasses import dataclass

OLLAMA_HOST = os.environ.get("OLLAMA_HOST", "http://localhost:11434")
OLLAMA_EXE = os.environ.get(
    "OLLAMA_EXE",
    r"C:\Users\vinut\AppData\Local\Programs\Ollama\ollama.exe",
)


@dataclass
class Status:
    offline_available: bool = False
    offline_model: str | None = None


def _http_get(path: str, timeout: float = 3.0) -> dict | None:
    """GET an Ollama API endpoint, return parsed JSON or None on failure."""
    url = OLLAMA_HOST.rstrip("/") + path
    try:
        req = urllib.request.Request(url, headers={"Accept": "application/json"})
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            import json

            return json.loads(resp.read().decode("utf-8"))
    except Exception:
        return None


def _ollama_running() -> bool:
    """Check if Ollama server is responding."""
    return _http_get("/api/tags") is not None


def _start_ollama_server() -> bool:
    """Try to start 'ollama serve' in the background."""
    if not os.path.exists(OLLAMA_EXE):
        return False
    try:
        subprocess.Popen(
            [OLLAMA_EXE, "serve"],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            creationflags=subprocess.CREATE_NEW_PROCESS_GROUP
            if hasattr(subprocess, "CREATE_NEW_PROCESS_GROUP")
            else 0,
        )
    except Exception:
        return False
    # Wait up to ~10s for server to come up
    for _ in range(20):
        time.sleep(0.5)
        if _ollama_running():
            return True
    return False


def _list_models() -> list[str]:
    """Return list of model names available on Ollama server."""
    data = _http_get("/api/tags")
    if not data:
        return []
    models = data.get("models", [])
    return [m.get("name", "") for m in models if m.get("name")]


def get_status() -> Status:
    """Return whether Ollama is available and which model to use."""
    if not _ollama_running():
        if not _start_ollama_server():
            return Status(offline_available=False, offline_model=None)
    models = _list_models()
    if not models:
        return Status(offline_available=True, offline_model=None)
    # Prefer common small/fast models for risk pre-filtering
    preferred = ["gemma2:2b", "gemma:2b", "phi3", "llama3.2:1b", "qwen2.5:0.5b"]
    for p in preferred:
        for m in models:
            if m.startswith(p):
                return Status(offline_available=True, offline_model=m)
    # Fall back to first available model
    return Status(offline_available=True, offline_model=models[0])


def chat_ollama(messages, model=None, temperature=0.1, num_predict=4096):
    """Send a chat completion to Ollama and return the assistant text."""
    import json

    payload = {
        "model": model or "gemma2:2b",
        "messages": messages,
        "stream": False,
        "options": {
            "temperature": temperature,
            "num_predict": num_predict,
        },
    }
    data = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(
        OLLAMA_HOST.rstrip("/") + "/api/chat",
        data=data,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=120) as resp:
            body = json.loads(resp.read().decode("utf-8"))
            return body.get("message", {}).get("content", "")
    except Exception:
        return ""
