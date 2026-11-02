"""Llama.cpp server manager — checks/starts a local llama.cpp HTTP server."""
from __future__ import annotations

import os
import subprocess
import time
import urllib.error
import urllib.request

LLAMA_HOST = os.environ.get("LLAMA_HOST", "http://localhost:8081")
LLAMA_EXE = os.environ.get("LLAMA_EXE", "llama-server")
LLAMA_MODEL = os.environ.get("LLAMA_MODEL", "")


def _http_get(path: str, timeout: float = 2.0) -> bool:
    """GET a llama.cpp endpoint, return True if server responds."""
    url = LLAMA_HOST.rstrip("/") + path
    try:
        req = urllib.request.Request(url, headers={"Accept": "application/json"})
        with urllib.request.urlopen(req, timeout=timeout):
            return True
    except Exception:
        return False


def _llama_running() -> bool:
    """Check if llama.cpp server is responding (health or /completion)."""
    return _http_get("/health") or _http_get("/")


def _start_llama_server() -> bool:
    """Try to start 'llama-server' in the background."""
    import shutil

    exe = shutil.which(LLAMA_EXE)
    if not exe:
        return False
    cmd = [exe, "--host", "127.0.0.1", "--port", "8081"]
    if LLAMA_MODEL:
        cmd += ["--model", LLAMA_MODEL]
    try:
        subprocess.Popen(
            cmd,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            creationflags=subprocess.CREATE_NEW_PROCESS_GROUP
            if hasattr(subprocess, "CREATE_NEW_PROCESS_GROUP")
            else 0,
        )
    except Exception:
        return False
    # Wait up to ~15s for server to come up (llama.cpp loads model into RAM)
    for _ in range(30):
        time.sleep(0.5)
        if _llama_running():
            return True
    return False


def ensure_ai_available(provider="llama"):
    """Try to ensure a local AI server is available. Returns bool."""
    if _llama_running():
        return True
    return _start_llama_server()


def stop_llama_server():
    """Stop the local AI server if running."""
    pass
