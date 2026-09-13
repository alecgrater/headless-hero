"""Supervises the local model daemons and enforces single-model residency.

Three daemons serve Local Mode: ollama (text), ComfyUI (image), and
mlx-audio (voice). Their combined resident memory plus Electron, Vite, and
Remotion's Chromium exceeds this machine's 48 GB, so only one heavy model is
allowed in memory at a time. Pipeline phases are already sequential, so the
arena costs ordering, not capability.

A model stays resident after its hold is released — it is evicted only when a
different modality claims the arena, or when unload_all() runs before a render.
Unloading eagerly on every release would thrash the model cache between calls.
"""

import logging
import os
import threading
from contextlib import contextmanager
from dataclasses import dataclass
from typing import Iterator

import httpx

from integrations.local_models import active_model, modality_source

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class Daemon:
    backend: str
    url_env_key: str
    default_url: str
    health_path: str


DAEMONS: dict[str, Daemon] = {
    "ollama": Daemon("ollama", "OLLAMA_URL", "http://127.0.0.1:11434", "/api/tags"),
    "comfyui": Daemon("comfyui", "LOCAL_COMFYUI_URL", "http://127.0.0.1:8188", "/system_stats"),
    "mlx-audio": Daemon("mlx-audio", "LOCAL_TTS_URL", "http://127.0.0.1:8770", "/v1/models"),
}

MODALITY_BACKEND: dict[str, str] = {"text": "ollama", "image": "comfyui", "voice": "mlx-audio"}

_ARENA_LOCK = threading.RLock()
_OCCUPANT: str | None = None


def reset_for_testing() -> None:
    """Drop arena state between tests."""
    global _OCCUPANT
    with _ARENA_LOCK:
        _OCCUPANT = None


def daemon_url(backend: str) -> str:
    daemon = DAEMONS[backend]
    return (os.environ.get(daemon.url_env_key, "") or daemon.default_url).rstrip("/")


def _probe(url: str) -> bool:
    try:
        response = httpx.get(url, timeout=3.0)
        return response.status_code < 500
    except Exception:
        return False


def daemon_health() -> dict[str, bool]:
    """Health of every local daemon, keyed by backend name."""
    return {
        backend: _probe(f"{daemon_url(backend)}{daemon.health_path}")
        for backend, daemon in DAEMONS.items()
    }


def ensure_daemon(backend: str) -> None:
    """Raise a clear error when a required daemon is not answering.

    Starting daemons is the provisioning script's job; this is the guard that
    turns a connection refused deep inside a generation run into an actionable
    message.
    """
    if _probe(f"{daemon_url(backend)}{DAEMONS[backend].health_path}"):
        return
    raise RuntimeError(
        f"Local Mode needs the {backend} daemon at {daemon_url(backend)}, but it is not responding. "
        f"Run scripts/install-local-models.sh, or switch this modality back to cloud in Settings."
    )


def _unload(modality: str) -> None:
    """Free the resident model for one modality. Best effort, never raises."""
    backend = MODALITY_BACKEND[modality]
    try:
        if backend == "ollama":
            httpx.post(
                f"{daemon_url('ollama')}/api/generate",
                json={"model": active_model("text").weights, "keep_alive": 0},
                timeout=10.0,
            )
        elif backend == "comfyui":
            httpx.post(
                f"{daemon_url('comfyui')}/free",
                json={"unload_models": True, "free_memory": True},
                timeout=10.0,
            )
        elif backend == "mlx-audio":
            httpx.post(f"{daemon_url('mlx-audio')}/unload", timeout=10.0)
        logger.info("Unloaded local %s model to free memory for the next stage", modality)
    except Exception as exc:
        logger.warning("Could not unload local %s model (%s); continuing", modality, exc)


def current_occupant() -> str | None:
    """The modality whose model is currently resident, if any."""
    return _OCCUPANT


@contextmanager
def hold(modality: str) -> Iterator[None]:
    """Claim the memory arena for one modality.

    Re-entrant for the same modality. Claiming for a different modality
    unloads the previous occupant first.
    """
    global _OCCUPANT
    if modality not in MODALITY_BACKEND:
        raise ValueError(f"Unknown modality: {modality!r}")
    _ARENA_LOCK.acquire()
    try:
        if _OCCUPANT is not None and _OCCUPANT != modality:
            _unload(_OCCUPANT)
            _OCCUPANT = None
        _OCCUPANT = modality
        yield
    finally:
        _ARENA_LOCK.release()


def unload_all() -> None:
    """Unload every resident local model. Called before Remotion renders."""
    global _OCCUPANT
    with _ARENA_LOCK:
        if _OCCUPANT is not None:
            _unload(_OCCUPANT)
            _OCCUPANT = None


def ollama_keep_alive() -> str:
    """Keep-alive to send to Ollama. Short in Local Mode so the arena can evict."""
    return "60s" if modality_source("text") == "local" else "30m"
