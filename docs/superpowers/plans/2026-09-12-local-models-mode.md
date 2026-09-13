# Local Models Mode Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a Settings-configurable Local Mode that routes text, image, and voice generation to local models on this machine, leaving AI video on the cloud.

**Architecture:** A declarative registry of local models plus a mode resolver decide, per modality, whether a call goes local or cloud. Three existing seams absorb the local path — `llm_client` (text, already speaks Ollama), `image_client` (image, gains a ComfyUI backend), and a new TTS client matching the ElevenLabs contract exactly. A runtime supervisor keeps at most one heavy model resident, because the three models plus Electron and Remotion exceed 48 GB.

**Tech Stack:** Python 3.12 / FastAPI / SQLModel backend, React 19 + TS + Tailwind 4 frontend, Ollama (text), ComfyUI on PyTorch MPS (image), mlx-audio (voice), faster-whisper (word timestamps, already present).

**Spec:** `docs/superpowers/specs/2026-09-12-local-models-mode-design.md`

## Global Constraints

- Python is run **only** through `uv`. Backend tests: `uv run --project backend pytest` from repo root. Never `python`, `pip`, or bare `uv run pytest` from root.
- Backend module boundaries: `api/` routers validate and delegate only; `pipeline/` holds business logic with no FastAPI imports; `integrations/` are thin wrappers that raise `RuntimeError` on missing configuration; `models/` hold no logic.
- Modern type syntax only: `list[str]`, `dict[str, Any]`, `str | None`.
- Frontend: Tailwind 4 utilities only, no CSS files. Double quotes, trailing commas, 2-space indent. Interactive elements get `hover:` plus `transition-colors`.
- Forward-only: no migration shims, no compatibility branches for cloud-generated assets.
- Dev-dashboard logging is plain `logging` — `backend/dev/log_handler.py` intercepts records. Use `logger.info` / `logger.warning` / `logger.error`.
- AI video stays cloud-only. No task in this plan touches `pipeline/video_gen.py` behaviour.
- Higgs attribution is **not** user-toggleable. It is a registry property enforced in code.
- Every task ends with a commit. Per repo convention, commit messages are imperative present tense: `{Add|Fix|Update|Remove|Refactor} {what} {context}`.

---

### Task 1: Local model registry and mode resolver

**Files:**
- Create: `backend/integrations/local_models.py`
- Test: `backend/tests/test_local_models.py`

**Interfaces:**
- Consumes: nothing.
- Produces: `LocalModel` dataclass; `REGISTRY: dict[str, LocalModel]`; `models_for(modality: str) -> list[LocalModel]`; `get_model(model_id: str) -> LocalModel`; `modality_source(modality: str) -> str` returning `"local"` or `"cloud"`; `active_model(modality: str) -> LocalModel`; `attribution_for(model_id: str) -> str`.

- [ ] **Step 1: Write the failing test**

```python
# backend/tests/test_local_models.py
import pytest

from integrations import local_models


def test_registry_entries_are_internally_consistent():
    for model_id, model in local_models.REGISTRY.items():
        assert model.id == model_id
        assert model.modality in {"text", "image", "voice"}
        assert model.backend in {"ollama", "comfyui", "mlx-audio"}
        assert model.weights
        assert model.approx_resident_gb > 0
        assert model.license
        if model.requires_attribution:
            assert model.attribution_text


def test_modality_source_defaults_to_cloud(monkeypatch):
    monkeypatch.delenv("LOCAL_MODELS_ENABLED", raising=False)
    monkeypatch.delenv("LOCAL_TEXT_MODE", raising=False)
    assert local_models.modality_source("text") == "cloud"


def test_master_switch_turns_every_modality_local(monkeypatch):
    monkeypatch.setenv("LOCAL_MODELS_ENABLED", "true")
    for modality in ("text", "image", "voice"):
        monkeypatch.delenv(f"LOCAL_{modality.upper()}_MODE", raising=False)
        assert local_models.modality_source(modality) == "local"


def test_modality_override_beats_master_switch(monkeypatch):
    monkeypatch.setenv("LOCAL_MODELS_ENABLED", "true")
    monkeypatch.setenv("LOCAL_IMAGE_MODE", "cloud")
    assert local_models.modality_source("image") == "cloud"
    assert local_models.modality_source("text") == "local"


def test_modality_override_works_with_master_switch_off(monkeypatch):
    monkeypatch.setenv("LOCAL_MODELS_ENABLED", "false")
    monkeypatch.setenv("LOCAL_VOICE_MODE", "local")
    assert local_models.modality_source("voice") == "local"


def test_unknown_mode_value_falls_back_to_auto(monkeypatch):
    monkeypatch.setenv("LOCAL_MODELS_ENABLED", "true")
    monkeypatch.setenv("LOCAL_TEXT_MODE", "banana")
    assert local_models.modality_source("text") == "local"


def test_active_model_reads_env_and_falls_back_to_default(monkeypatch):
    monkeypatch.delenv("LOCAL_VOICE_MODEL", raising=False)
    assert local_models.active_model("voice").id == local_models.DEFAULT_MODEL_IDS["voice"]
    monkeypatch.setenv("LOCAL_VOICE_MODEL", "kokoro-82m")
    assert local_models.active_model("voice").id == "kokoro-82m"


def test_active_model_ignores_wrong_modality_id(monkeypatch):
    monkeypatch.setenv("LOCAL_VOICE_MODEL", "flux2-klein-4b")
    assert local_models.active_model("voice").id == local_models.DEFAULT_MODEL_IDS["voice"]


def test_higgs_requires_attribution_and_others_do_not():
    assert local_models.attribution_for("higgs-tts-3-4b")
    assert local_models.attribution_for("kokoro-82m") == ""
    assert local_models.attribution_for("chatterbox") == ""


def test_get_model_rejects_unknown_id():
    with pytest.raises(KeyError):
        local_models.get_model("nope")
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run --project backend pytest tests/test_local_models.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'integrations.local_models'`

- [ ] **Step 3: Write minimal implementation**

```python
# backend/integrations/local_models.py
"""Declarative registry of local models plus Local Mode resolution.

This module is the single source of truth for which local models exist, how
they are served, and whether a given modality should run locally right now.
Settings pickers, the provisioning script, and the attribution logic all read
from here, so adding a model means adding one REGISTRY entry.
"""

import logging
import os
from dataclasses import dataclass

logger = logging.getLogger(__name__)

MODALITIES = ("text", "image", "voice")
VALID_MODES = ("auto", "local", "cloud")


@dataclass(frozen=True)
class LocalModel:
    """One installable local model.

    weights is the pull spec for the model's backend: an Ollama model
    reference for `ollama`, a Hugging Face repo (optionally `:QUANT`) for
    `comfyui` and `mlx-audio`. The provisioning script consumes it verbatim.
    """

    id: str
    modality: str
    backend: str
    weights: str
    approx_resident_gb: float
    license: str
    label: str
    description: str
    requires_attribution: bool = False
    attribution_text: str = ""


REGISTRY: dict[str, LocalModel] = {
    "qwen3.8-27b": LocalModel(
        id="qwen3.8-27b",
        modality="text",
        backend="ollama",
        weights="hf.co/unsloth/Qwen3.8-27B-GGUF:Q4_K_M",
        approx_resident_gb=17.0,
        license="Apache-2.0",
        label="Qwen3.8 27B (Q4_K_M)",
        description="Dense 27B with 262k context. Narrative quality workhorse for scripts and ideas.",
    ),
    "qwen-image-edit-2511": LocalModel(
        id="qwen-image-edit-2511",
        modality="image",
        backend="comfyui",
        weights="unsloth/Qwen-Image-Edit-2511-GGUF:Q4_K_M",
        approx_resident_gb=13.2,
        license="Apache-2.0",
        label="Qwen-Image-Edit 2511 (Q4_K_M)",
        description="20B editor tuned for character consistency across references. Slower, highest fidelity to your character.",
    ),
    "flux2-klein-4b": LocalModel(
        id="flux2-klein-4b",
        modality="image",
        backend="comfyui",
        weights="black-forest-labs/FLUX.2-klein-4B",
        approx_resident_gb=13.0,
        license="Apache-2.0",
        label="FLUX.2 klein 4B",
        description="4-step distilled multi-reference model. Much faster per image, less character lock-in.",
    ),
    "higgs-tts-3-4b": LocalModel(
        id="higgs-tts-3-4b",
        modality="voice",
        backend="mlx-audio",
        weights="whitelabel/mlx-q6-higgs-tts-3-4b",
        approx_resident_gb=4.0,
        license="Boson research/non-commercial + Creator Use Grant",
        label="Higgs TTS 3 (4B)",
        description="Expressive narration with zero-shot cloning. Its licence requires crediting Boson AI, which is appended to SEO descriptions automatically.",
        requires_attribution=True,
        attribution_text="Voice: Boson AI Higgs Audio",
    ),
    "kokoro-82m": LocalModel(
        id="kokoro-82m",
        modality="voice",
        backend="mlx-audio",
        weights="hexgrad/Kokoro-82M",
        approx_resident_gb=0.5,
        license="Apache-2.0",
        label="Kokoro 82M",
        description="Very fast, clean, neutral narration with fixed voices. No attribution required.",
    ),
    "chatterbox": LocalModel(
        id="chatterbox",
        modality="voice",
        backend="mlx-audio",
        weights="ResembleAI/chatterbox",
        approx_resident_gb=2.0,
        license="MIT",
        label="Chatterbox",
        description="Mid-weight expressive model with voice cloning. No attribution required.",
    ),
}

DEFAULT_MODEL_IDS: dict[str, str] = {
    "text": "qwen3.8-27b",
    "image": "qwen-image-edit-2511",
    "voice": "higgs-tts-3-4b",
}

MODEL_ENV_KEYS: dict[str, str] = {
    "text": "LOCAL_TEXT_MODEL",
    "image": "LOCAL_IMAGE_MODEL",
    "voice": "LOCAL_VOICE_MODEL",
}


def models_for(modality: str) -> list[LocalModel]:
    """Every registered model for one modality, in registry order."""
    return [m for m in REGISTRY.values() if m.modality == modality]


def get_model(model_id: str) -> LocalModel:
    """Look up a model by id. Raises KeyError for unknown ids."""
    return REGISTRY[model_id]


def _master_enabled() -> bool:
    return (os.environ.get("LOCAL_MODELS_ENABLED", "false") or "false").strip().lower() == "true"


def modality_source(modality: str) -> str:
    """Return "local" or "cloud" for one modality.

    The per-modality key pins the answer; "auto" (or anything unrecognised)
    defers to the LOCAL_MODELS_ENABLED master switch.
    """
    if modality not in MODALITIES:
        raise ValueError(f"Unknown modality: {modality!r}")
    raw = (os.environ.get(f"LOCAL_{modality.upper()}_MODE", "auto") or "auto").strip().lower()
    if raw not in VALID_MODES:
        logger.warning(
            "Ignoring unsupported LOCAL_%s_MODE=%r; falling back to auto",
            modality.upper(), raw,
        )
        raw = "auto"
    if raw == "auto":
        return "local" if _master_enabled() else "cloud"
    return raw


def active_model(modality: str) -> LocalModel:
    """The local model configured for one modality, falling back to the default."""
    default_id = DEFAULT_MODEL_IDS[modality]
    configured = (os.environ.get(MODEL_ENV_KEYS[modality], "") or "").strip()
    if not configured:
        return REGISTRY[default_id]
    model = REGISTRY.get(configured)
    if model is None or model.modality != modality:
        logger.warning(
            "Ignoring %s=%r (not a registered %s model); using %s",
            MODEL_ENV_KEYS[modality], configured, modality, default_id,
        )
        return REGISTRY[default_id]
    return model


def attribution_for(model_id: str) -> str:
    """The licence credit a model requires, or "" when it requires none."""
    model = REGISTRY.get(model_id)
    if model is None or not model.requires_attribution:
        return ""
    return model.attribution_text
```

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run --project backend pytest tests/test_local_models.py -v`
Expected: PASS, 10 tests

- [ ] **Step 5: Commit**

```bash
git add backend/integrations/local_models.py backend/tests/test_local_models.py
git commit -m "Add local model registry and Local Mode resolver"
```

---

### Task 2: Route text generation to local models

**Files:**
- Modify: `backend/integrations/llm_client.py` (`_resolve_provider` at :242, `_resolve_model` at :283)
- Test: `backend/tests/test_local_text_routing.py`

**Interfaces:**
- Consumes: `local_models.modality_source`, `local_models.active_model`.
- Produces: no new public names. `chat()` keeps its signature; only resolution changes.

Local Mode forces `provider="ollama"`. Narrative tasks use `LOCAL_TEXT_MODEL`; tasks whose `LLM_TASKS[...]["openai_reasoning_effort"]` is `"minimal"` use `LOCAL_TEXT_FAST_MODEL`, which defaults to the same value.

- [ ] **Step 1: Write the failing test**

```python
# backend/tests/test_local_text_routing.py
from integrations import llm_client


def _local(monkeypatch):
    monkeypatch.setenv("LOCAL_MODELS_ENABLED", "true")
    monkeypatch.delenv("LOCAL_TEXT_MODE", raising=False)
    monkeypatch.delenv("LOCAL_TEXT_MODEL", raising=False)
    monkeypatch.delenv("LOCAL_TEXT_FAST_MODEL", raising=False)


def test_local_mode_forces_ollama_even_when_task_prefers_anthropic(monkeypatch):
    _local(monkeypatch)
    monkeypatch.setenv("SCRIPT_LLM_PROVIDER", "anthropic")
    assert llm_client._resolve_provider("script") == "ollama"


def test_cloud_mode_leaves_task_provider_alone(monkeypatch):
    monkeypatch.setenv("LOCAL_MODELS_ENABLED", "false")
    monkeypatch.delenv("LOCAL_TEXT_MODE", raising=False)
    monkeypatch.setenv("SCRIPT_LLM_PROVIDER", "anthropic")
    assert llm_client._resolve_provider("script") == "anthropic"


def test_text_pinned_cloud_overrides_master_switch(monkeypatch):
    _local(monkeypatch)
    monkeypatch.setenv("LOCAL_TEXT_MODE", "cloud")
    monkeypatch.setenv("SCRIPT_LLM_PROVIDER", "anthropic")
    assert llm_client._resolve_provider("script") == "anthropic"


def test_narrative_task_uses_local_text_model(monkeypatch):
    _local(monkeypatch)
    monkeypatch.setenv("LOCAL_TEXT_MODEL", "qwen3.8-27b")
    assert llm_client._resolve_model("ollama", "script", None) == "hf.co/unsloth/Qwen3.8-27B-GGUF:Q4_K_M"


def test_minimal_effort_task_uses_fast_model_when_set(monkeypatch):
    _local(monkeypatch)
    monkeypatch.setenv("LOCAL_TEXT_FAST_MODEL", "qwen3.8-27b")
    # "fx" is declared with openai_reasoning_effort="minimal"
    assert llm_client._resolve_model("ollama", "fx", None) == "hf.co/unsloth/Qwen3.8-27B-GGUF:Q4_K_M"


def test_local_mode_ignores_stale_cloud_model_setting(monkeypatch):
    _local(monkeypatch)
    monkeypatch.setenv("SCRIPT_MODEL", "claude-opus-4-7")
    resolved = llm_client._resolve_model("ollama", "script", None)
    assert resolved.startswith("hf.co/")


def test_explicit_model_argument_still_wins_outside_local_mode(monkeypatch):
    monkeypatch.setenv("LOCAL_MODELS_ENABLED", "false")
    monkeypatch.delenv("LOCAL_TEXT_MODE", raising=False)
    assert llm_client._resolve_model("anthropic", "script", "claude-sonnet-4-6") == "claude-sonnet-4-6"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run --project backend pytest tests/test_local_text_routing.py -v`
Expected: FAIL — `test_local_mode_forces_ollama_even_when_task_prefers_anthropic` returns `"anthropic"`

- [ ] **Step 3: Write minimal implementation**

Add the import near the other `integrations` import at the top of `backend/integrations/llm_client.py`:

```python
from integrations.local_models import active_model as _active_local_model, modality_source as _modality_source
```

Add this helper directly above `_resolve_provider`:

```python
def _text_is_local() -> bool:
    """True when Local Mode owns text generation for this call."""
    return _modality_source("text") == "local"


def _local_text_model(task: str | None) -> str:
    """The Ollama model reference Local Mode should use for one task.

    Tasks declared with openai_reasoning_effort="minimal" are the cheap
    structured-JSON calls, so they read LOCAL_TEXT_FAST_MODEL. That key
    defaults to the narrative model, because under the single-resident memory
    arena a second text model costs an unload/reload cycle per alternation.
    """
    task_config = LLM_TASKS.get(task or "")
    is_fast_tier = bool(task_config) and task_config.get("openai_reasoning_effort") == "minimal"
    if is_fast_tier:
        configured = (os.environ.get("LOCAL_TEXT_FAST_MODEL", "") or "").strip()
        if configured:
            from integrations.local_models import REGISTRY
            model = REGISTRY.get(configured)
            if model is not None and model.modality == "text":
                return model.weights
    return _active_local_model("text").weights
```

Insert at the top of `_resolve_provider`, before the existing body:

```python
    if _text_is_local():
        return "ollama"
```

Insert at the top of `_resolve_model`, before the existing `if model:` branch:

```python
    if _text_is_local() and provider == "ollama":
        return _local_text_model(task)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run --project backend pytest tests/test_local_text_routing.py tests/test_llm_routing.py -v`
Expected: PASS, including the pre-existing routing suite

- [ ] **Step 5: Commit**

```bash
git add backend/integrations/llm_client.py backend/tests/test_local_text_routing.py
git commit -m "Route text generation through local models in Local Mode"
```

---

### Task 3: Local runtime supervisor and single-resident memory arena

**Files:**
- Create: `backend/pipeline/local_runtime.py`
- Test: `backend/tests/test_local_runtime.py`

**Interfaces:**
- Consumes: `local_models.active_model`.
- Produces: `DAEMONS: dict[str, Daemon]`; `daemon_health() -> dict[str, bool]`; `ensure_daemon(backend: str) -> None`; `hold(modality: str)` context manager; `unload_all() -> None`; `ollama_keep_alive() -> str`.

The arena is a module-level `threading.Lock` plus a record of the current occupant. Acquiring for a different modality unloads the previous one first. `unload_all` is called before Remotion renders.

- [ ] **Step 1: Write the failing test**

```python
# backend/tests/test_local_runtime.py
import threading

import pytest

from pipeline import local_runtime


@pytest.fixture(autouse=True)
def _reset():
    local_runtime.reset_for_testing()
    yield
    local_runtime.reset_for_testing()


def test_hold_records_the_current_occupant():
    with local_runtime.hold("image"):
        assert local_runtime.current_occupant() == "image"
    assert local_runtime.current_occupant() is None


def test_switching_modality_unloads_the_previous_one(monkeypatch):
    unloaded: list[str] = []
    monkeypatch.setattr(local_runtime, "_unload", lambda modality: unloaded.append(modality))
    with local_runtime.hold("text"):
        pass
    with local_runtime.hold("image"):
        pass
    assert unloaded == ["text"]


def test_reentrant_hold_of_same_modality_does_not_unload(monkeypatch):
    unloaded: list[str] = []
    monkeypatch.setattr(local_runtime, "_unload", lambda modality: unloaded.append(modality))
    with local_runtime.hold("text"):
        with local_runtime.hold("text"):
            pass
    assert unloaded == []


def test_hold_serializes_across_threads(monkeypatch):
    monkeypatch.setattr(local_runtime, "_unload", lambda modality: None)
    order: list[str] = []
    started = threading.Event()

    def worker():
        started.wait(timeout=5)
        with local_runtime.hold("image"):
            order.append("image")

    thread = threading.Thread(target=worker)
    with local_runtime.hold("text"):
        thread.start()
        started.set()
        thread.join(timeout=0.5)
        order.append("text")
    thread.join(timeout=5)
    assert order == ["text", "image"]


def test_unload_all_clears_the_occupant(monkeypatch):
    unloaded: list[str] = []
    monkeypatch.setattr(local_runtime, "_unload", lambda modality: unloaded.append(modality))
    with local_runtime.hold("voice"):
        pass
    local_runtime.unload_all()
    assert unloaded == ["voice"]
    assert local_runtime.current_occupant() is None


def test_ollama_keep_alive_is_short_in_local_mode(monkeypatch):
    monkeypatch.setenv("LOCAL_MODELS_ENABLED", "true")
    monkeypatch.delenv("LOCAL_TEXT_MODE", raising=False)
    assert local_runtime.ollama_keep_alive() == "60s"
    monkeypatch.setenv("LOCAL_MODELS_ENABLED", "false")
    assert local_runtime.ollama_keep_alive() == "30m"


def test_daemon_health_reports_every_backend(monkeypatch):
    monkeypatch.setattr(local_runtime, "_probe", lambda url: url.endswith("11434"))
    health = local_runtime.daemon_health()
    assert set(health) == {"ollama", "comfyui", "mlx-audio"}
    assert health["ollama"] is True
    assert health["comfyui"] is False
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run --project backend pytest tests/test_local_runtime.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'pipeline.local_runtime'`

- [ ] **Step 3: Write minimal implementation**

```python
# backend/pipeline/local_runtime.py
"""Supervises the local model daemons and enforces single-model residency.

Three daemons serve Local Mode: ollama (text), ComfyUI (image), and
mlx-audio (voice). Their combined resident memory plus Electron, Vite, and
Remotion's Chromium exceeds this machine's 48 GB, so only one heavy model is
allowed in memory at a time. Pipeline phases are already sequential, so the
arena costs ordering, not capability.
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
_DEPTH = 0


def reset_for_testing() -> None:
    """Drop arena state between tests."""
    global _OCCUPANT, _DEPTH
    with _ARENA_LOCK:
        _OCCUPANT = None
        _DEPTH = 0


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
            httpx.post(f"{daemon_url('comfyui')}/free", json={"unload_models": True, "free_memory": True}, timeout=10.0)
        elif backend == "mlx-audio":
            httpx.post(f"{daemon_url('mlx-audio')}/unload", timeout=10.0)
        logger.info("Unloaded local %s model to free memory for the next stage", modality)
    except Exception as exc:
        logger.warning("Could not unload local %s model (%s); continuing", modality, exc)


def current_occupant() -> str | None:
    return _OCCUPANT


@contextmanager
def hold(modality: str) -> Iterator[None]:
    """Claim the memory arena for one modality.

    Re-entrant for the same modality. Claiming for a different modality
    unloads the previous occupant first.
    """
    global _OCCUPANT, _DEPTH
    _ARENA_LOCK.acquire()
    try:
        if _OCCUPANT is not None and _OCCUPANT != modality:
            _unload(_OCCUPANT)
            _OCCUPANT = None
        _OCCUPANT = modality
        _DEPTH += 1
        yield
    finally:
        _DEPTH -= 1
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
```

Then wire the keep-alive into `backend/integrations/llm_client.py:504`, replacing the hardcoded value inside `_chat_ollama`'s `kwargs`:

```python
        "extra_body": {"keep_alive": _ollama_keep_alive(), "options": {"num_ctx": num_ctx}},
```

with this import added at the top of `_chat_ollama` (local import avoids a circular import between `integrations` and `pipeline`):

```python
    from pipeline.local_runtime import ollama_keep_alive as _ollama_keep_alive
```

and update the log line just below it so `keep_alive=30m` is no longer hardcoded in the message:

```python
    logger.info(
        "Calling Ollama task=%s model=%s max_tokens=%d num_ctx=%d timeout=%.0fs json_mode=%s keep_alive=%s",
        task or "default", qwen_model, max_tokens, num_ctx, timeout, json_mode, _ollama_keep_alive(),
    )
```

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run --project backend pytest tests/test_local_runtime.py tests/test_llm_routing.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add backend/pipeline/local_runtime.py backend/integrations/llm_client.py backend/tests/test_local_runtime.py
git commit -m "Add local runtime supervisor with single-resident memory arena"
```

---

### Task 4: ComfyUI-backed local image client

**Files:**
- Create: `backend/integrations/local_image_client.py`
- Create: `backend/comfy_workflows/qwen_image_edit_2511.json`
- Create: `backend/comfy_workflows/flux2_klein_4b.json`
- Test: `backend/tests/test_local_image_client.py`

**Interfaces:**
- Consumes: `local_models.active_model`, `local_runtime.ensure_daemon`, `local_runtime.hold`, `local_runtime.daemon_url`.
- Produces: `generate_image(prompt, *, width, height, reference_image_path, style_reference_path, original_prompt, script_id) -> str` returning a temp PNG path; `transform_with_references(prompt, image_paths, *, width, height, script_id) -> str`.

Both signatures mirror `google_image_client` so `image_client` can dispatch without adapters. `generate_image` is `transform_with_references` with the character and style references as its image list, so the implementation has one code path.

The workflow JSON files are ComfyUI API-format graphs with placeholder tokens (`__PROMPT__`, `__WIDTH__`, `__HEIGHT__`, `__REF_IMAGES__`, `__SEED__`) substituted at call time. They are produced in Task 11 against the installed ComfyUI, because a workflow graph must match the installed node set; this task creates them as committed fixtures with the node ids the client addresses, and Task 11 replaces their contents with graphs verified against the real server.

- [ ] **Step 1: Write the failing test**

```python
# backend/tests/test_local_image_client.py
import json
from pathlib import Path

import pytest

from integrations import local_image_client


class _FakeComfy:
    """Minimal ComfyUI stand-in: accepts a prompt, then serves history and the image."""

    def __init__(self, png_bytes: bytes):
        self.png_bytes = png_bytes
        self.submitted: list[dict] = []

    def post(self, url, json=None, timeout=None):
        self.submitted.append(json)
        return _Response(200, {"prompt_id": "p1"})

    def get(self, url, timeout=None):
        if "/history/" in url:
            return _Response(200, {
                "p1": {
                    "status": {"completed": True},
                    "outputs": {"9": {"images": [{"filename": "out.png", "subfolder": "", "type": "output"}]}},
                }
            })
        return _Response(200, None, content=self.png_bytes)


class _Response:
    def __init__(self, status_code, payload, content=b""):
        self.status_code = status_code
        self._payload = payload
        self.content = content

    def json(self):
        return self._payload

    def raise_for_status(self):
        if self.status_code >= 400:
            raise RuntimeError(f"HTTP {self.status_code}")


@pytest.fixture
def fake_comfy(monkeypatch, tmp_path):
    png = (tmp_path / "src.png")
    png.write_bytes(b"\x89PNG\r\n\x1a\nFAKE")
    fake = _FakeComfy(png.read_bytes())
    monkeypatch.setattr(local_image_client, "_http", lambda: fake)
    monkeypatch.setattr(local_image_client, "ensure_daemon", lambda backend: None)
    monkeypatch.setattr(local_image_client, "_upload_image", lambda path: Path(path).name)
    return fake


def test_generate_image_returns_a_written_png(fake_comfy, monkeypatch):
    monkeypatch.setenv("LOCAL_IMAGE_MODEL", "flux2-klein-4b")
    out = local_image_client.generate_image("a cat", width=1920, height=1080)
    assert Path(out).exists()
    assert Path(out).read_bytes().startswith(b"\x89PNG")


def test_prompt_and_dimensions_are_substituted(fake_comfy, monkeypatch):
    monkeypatch.setenv("LOCAL_IMAGE_MODEL", "flux2-klein-4b")
    local_image_client.generate_image("a lighthouse at dusk", width=1920, height=1080)
    payload = json.dumps(fake_comfy.submitted[0])
    assert "a lighthouse at dusk" in payload
    assert "1920" in payload and "1080" in payload
    assert "__PROMPT__" not in payload and "__WIDTH__" not in payload


def test_references_are_uploaded_and_referenced(fake_comfy, tmp_path, monkeypatch):
    monkeypatch.setenv("LOCAL_IMAGE_MODEL", "qwen-image-edit-2511")
    char = tmp_path / "char.png"
    char.write_bytes(b"\x89PNG\r\n\x1a\n")
    style = tmp_path / "style.png"
    style.write_bytes(b"\x89PNG\r\n\x1a\n")
    local_image_client.generate_image(
        "hero in a workshop",
        width=1920,
        height=1080,
        reference_image_path=str(char),
        style_reference_path=str(style),
    )
    payload = json.dumps(fake_comfy.submitted[0])
    assert "char.png" in payload
    assert "style.png" in payload


def test_transform_with_references_accepts_a_list(fake_comfy, tmp_path, monkeypatch):
    monkeypatch.setenv("LOCAL_IMAGE_MODEL", "qwen-image-edit-2511")
    paths = []
    for name in ("a.png", "b.png"):
        p = tmp_path / name
        p.write_bytes(b"\x89PNG\r\n\x1a\n")
        paths.append(str(p))
    out = local_image_client.transform_with_references("merge these", paths, width=1280, height=720)
    assert Path(out).exists()
    payload = json.dumps(fake_comfy.submitted[0])
    assert "a.png" in payload and "b.png" in payload


def test_seeds_differ_between_calls(fake_comfy, monkeypatch):
    monkeypatch.setenv("LOCAL_IMAGE_MODEL", "flux2-klein-4b")
    local_image_client.generate_image("x", width=64, height=64)
    local_image_client.generate_image("x", width=64, height=64)
    first = json.dumps(fake_comfy.submitted[0])
    second = json.dumps(fake_comfy.submitted[1])
    assert first != second


def test_missing_daemon_raises_actionable_error(monkeypatch):
    def boom(backend):
        raise RuntimeError("comfyui daemon is not responding")

    monkeypatch.setattr(local_image_client, "ensure_daemon", boom)
    with pytest.raises(RuntimeError, match="not responding"):
        local_image_client.generate_image("x", width=64, height=64)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run --project backend pytest tests/test_local_image_client.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'integrations.local_image_client'`

- [ ] **Step 3: Write minimal implementation**

Create the two workflow fixtures. Both use the same placeholder contract; node `"9"` is the `SaveImage` node the client reads outputs from.

```json
// backend/comfy_workflows/flux2_klein_4b.json
{
  "6": {"class_type": "CLIPTextEncode", "inputs": {"text": "__PROMPT__", "clip": ["11", 0]}},
  "5": {"class_type": "EmptyLatentImage", "inputs": {"width": "__WIDTH__", "height": "__HEIGHT__", "batch_size": 1}},
  "3": {"class_type": "KSampler", "inputs": {"seed": "__SEED__", "steps": 4, "cfg": 1.0, "sampler_name": "euler", "scheduler": "simple", "denoise": 1.0, "model": ["10", 0], "positive": ["6", 0], "negative": ["6", 0], "latent_image": ["5", 0]}},
  "8": {"class_type": "VAEDecode", "inputs": {"samples": ["3", 0], "vae": ["12", 0]}},
  "9": {"class_type": "SaveImage", "inputs": {"filename_prefix": "headless-hero", "images": ["8", 0]}},
  "10": {"class_type": "UNETLoader", "inputs": {"unet_name": "__MODEL__", "weight_dtype": "default"}},
  "11": {"class_type": "CLIPLoader", "inputs": {"clip_name": "__CLIP__", "type": "flux2"}},
  "12": {"class_type": "VAELoader", "inputs": {"vae_name": "__VAE__"}},
  "__REF_IMAGES__": []
}
```

```json
// backend/comfy_workflows/qwen_image_edit_2511.json
{
  "6": {"class_type": "CLIPTextEncode", "inputs": {"text": "__PROMPT__", "clip": ["11", 0]}},
  "5": {"class_type": "EmptyLatentImage", "inputs": {"width": "__WIDTH__", "height": "__HEIGHT__", "batch_size": 1}},
  "3": {"class_type": "KSampler", "inputs": {"seed": "__SEED__", "steps": 20, "cfg": 4.0, "sampler_name": "euler", "scheduler": "simple", "denoise": 1.0, "model": ["10", 0], "positive": ["6", 0], "negative": ["6", 0], "latent_image": ["5", 0]}},
  "8": {"class_type": "VAEDecode", "inputs": {"samples": ["3", 0], "vae": ["12", 0]}},
  "9": {"class_type": "SaveImage", "inputs": {"filename_prefix": "headless-hero", "images": ["8", 0]}},
  "10": {"class_type": "UnetLoaderGGUF", "inputs": {"unet_name": "__MODEL__"}},
  "11": {"class_type": "CLIPLoader", "inputs": {"clip_name": "__CLIP__", "type": "qwen_image"}},
  "12": {"class_type": "VAELoader", "inputs": {"vae_name": "__VAE__"}},
  "__REF_IMAGES__": []
}
```

```python
# backend/integrations/local_image_client.py
"""Local image generation through a ComfyUI server.

Mirrors the google_image_client surface so integrations.image_client can
dispatch to either backend without adapters. Reference images are uploaded to
ComfyUI, then injected into a workflow graph loaded from backend/comfy_workflows.
"""

import json
import logging
import os
import random
import tempfile
import time
from pathlib import Path

import httpx

from config import IMAGE_HEIGHT, IMAGE_WIDTH
from integrations.local_models import active_model
from integrations.usage_tracker import record_usage
from pipeline.local_runtime import daemon_url, ensure_daemon, hold

logger = logging.getLogger(__name__)

WORKFLOW_DIR = Path(__file__).resolve().parent.parent / "comfy_workflows"
WORKFLOW_FILES: dict[str, str] = {
    "qwen-image-edit-2511": "qwen_image_edit_2511.json",
    "flux2-klein-4b": "flux2_klein_4b.json",
}
POLL_INTERVAL_SECONDS = 1.0
DEFAULT_TIMEOUT_SECONDS = 900.0


def _http() -> httpx.Client:
    return httpx.Client(timeout=60.0)


def _upload_image(path: str) -> str:
    """Upload one reference image to ComfyUI and return its server-side name."""
    name = Path(path).name
    with open(path, "rb") as handle:
        response = _http().post(
            f"{daemon_url('comfyui')}/upload/image",
            files={"image": (name, handle, "image/png")},
            data={"overwrite": "true"},
        )
    response.raise_for_status()
    return response.json().get("name", name)


def _load_workflow(model_id: str) -> dict:
    filename = WORKFLOW_FILES.get(model_id)
    if filename is None:
        raise RuntimeError(f"No ComfyUI workflow registered for local image model {model_id!r}")
    path = WORKFLOW_DIR / filename
    if not path.exists():
        raise RuntimeError(f"ComfyUI workflow file is missing: {path}")
    return json.loads(path.read_text(encoding="utf-8"))


def _substitute(workflow: dict, *, prompt: str, width: int, height: int, seed: int, reference_names: list[str]) -> dict:
    """Replace placeholder tokens in a workflow graph."""
    raw = json.dumps(workflow)
    raw = raw.replace("__PROMPT__", json.dumps(prompt)[1:-1])
    raw = raw.replace('"__WIDTH__"', str(width))
    raw = raw.replace('"__HEIGHT__"', str(height))
    raw = raw.replace('"__SEED__"', str(seed))
    graph = json.loads(raw)
    graph["__REF_IMAGES__"] = reference_names
    for index, name in enumerate(reference_names):
        node_id = f"ref_{index}"
        graph[node_id] = {"class_type": "LoadImage", "inputs": {"image": name}}
    return graph


def _await_image(prompt_id: str, timeout_seconds: float) -> bytes:
    """Poll ComfyUI history until the prompt completes, then fetch the PNG."""
    deadline = time.monotonic() + timeout_seconds
    client = _http()
    while time.monotonic() < deadline:
        response = client.get(f"{daemon_url('comfyui')}/history/{prompt_id}")
        response.raise_for_status()
        history = response.json() or {}
        entry = history.get(prompt_id)
        if entry:
            outputs = entry.get("outputs", {})
            for node_output in outputs.values():
                images = node_output.get("images") or []
                if images:
                    image = images[0]
                    fetched = client.get(
                        f"{daemon_url('comfyui')}/view"
                        f"?filename={image['filename']}&subfolder={image.get('subfolder', '')}&type={image.get('type', 'output')}"
                    )
                    fetched.raise_for_status()
                    return fetched.content
        time.sleep(POLL_INTERVAL_SECONDS)
    raise RuntimeError(f"ComfyUI did not return an image within {timeout_seconds:.0f}s (prompt_id={prompt_id})")


def transform_with_references(
    prompt: str,
    image_paths: list[str],
    width: int = IMAGE_WIDTH,
    height: int = IMAGE_HEIGHT,
    script_id: str | None = None,
) -> str:
    """Generate one image locally, optionally conditioned on reference images.

    Returns the path to a temp PNG, matching google_image_client's contract.
    """
    ensure_daemon("comfyui")
    model = active_model("image")
    timeout_seconds = float(os.environ.get("LOCAL_IMAGE_TIMEOUT_SECONDS", DEFAULT_TIMEOUT_SECONDS))

    with hold("image"):
        reference_names = [_upload_image(path) for path in image_paths]
        graph = _substitute(
            _load_workflow(model.id),
            prompt=prompt,
            width=width,
            height=height,
            seed=random.randint(1, 2**31 - 1),
            reference_names=reference_names,
        )
        logger.info(
            "Generating image via local ComfyUI (model=%s, %dx%d, refs=%d)",
            model.id, width, height, len(reference_names),
        )
        started = time.monotonic()
        response = _http().post(f"{daemon_url('comfyui')}/prompt", json={"prompt": graph})
        response.raise_for_status()
        prompt_id = response.json()["prompt_id"]
        png_bytes = _await_image(prompt_id, timeout_seconds)
        elapsed = time.monotonic() - started

    handle = tempfile.NamedTemporaryFile(suffix=".png", delete=False)
    handle.write(png_bytes)
    handle.close()

    record_usage(
        service="local_image",
        operation="generate",
        model=model.id,
        cost_estimate=0.0,
        script_id=script_id,
    )
    logger.info("Local image generated in %.1fs via %s -> %s", elapsed, model.id, handle.name)
    return handle.name


def generate_image(
    prompt: str,
    width: int = IMAGE_WIDTH,
    height: int = IMAGE_HEIGHT,
    reference_image_path: str | None = None,
    style_reference_path: str | None = None,
    original_prompt: str | None = None,
    script_id: str | None = None,
) -> str:
    """Generate one scene image locally.

    original_prompt exists for signature parity with the Google client, which
    uses it to retry past content filters. Local models have no such filter, so
    it is accepted and ignored.
    """
    references = [p for p in (reference_image_path, style_reference_path) if p]
    return transform_with_references(
        prompt,
        references,
        width=width,
        height=height,
        script_id=script_id,
    )
```

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run --project backend pytest tests/test_local_image_client.py -v`
Expected: PASS, 6 tests

- [ ] **Step 5: Commit**

```bash
git add backend/integrations/local_image_client.py backend/comfy_workflows backend/tests/test_local_image_client.py
git commit -m "Add ComfyUI-backed local image client"
```

---

### Task 5: Make image_client the single image provider seam

**Files:**
- Modify: `backend/integrations/image_client.py` (whole file)
- Modify: `backend/pipeline/thumbnail.py:181`, `:439`
- Modify: `backend/pipeline/main_character.py:19`
- Modify: `backend/pipeline/image_gen.py:15`
- Test: `backend/tests/test_image_client_provider_routing.py` (extend existing)

**Interfaces:**
- Consumes: `local_models.modality_source`, `local_image_client.generate_image`, `local_image_client.transform_with_references`, the existing `google_image_client` functions.
- Produces: `image_client.generate_image(...)` (unchanged signature), `image_client.transform_with_references(prompt, image_paths, width, height, script_id) -> str`, `image_client.generate_images_batch(*, requests, script_id, ...) -> list[GoogleBatchImageResult]`, `image_client.resolved_provider() -> str`.

Three call sites currently import `google_image_client` directly and would silently stay on Gemini in Local Mode. They move behind the router.

- [ ] **Step 1: Write the failing test**

Append to `backend/tests/test_image_client_provider_routing.py`:

```python
def test_local_mode_routes_generate_image_to_comfyui(monkeypatch):
    monkeypatch.setenv("LOCAL_MODELS_ENABLED", "true")
    monkeypatch.delenv("LOCAL_IMAGE_MODE", raising=False)
    called: dict[str, object] = {}

    from integrations import local_image_client

    def fake(prompt, width, height, reference_image_path, style_reference_path, original_prompt, script_id):
        called["prompt"] = prompt
        return "/tmp/local.png"

    monkeypatch.setattr(local_image_client, "generate_image", fake)
    from integrations import image_client

    assert image_client.generate_image("hello", width=64, height=64) == "/tmp/local.png"
    assert called["prompt"] == "hello"


def test_image_pinned_cloud_still_uses_google(monkeypatch):
    monkeypatch.setenv("LOCAL_MODELS_ENABLED", "true")
    monkeypatch.setenv("LOCAL_IMAGE_MODE", "cloud")
    from integrations import google_image_client, image_client

    monkeypatch.setattr(google_image_client, "generate_image", lambda *a, **k: "/tmp/google.png")
    assert image_client.generate_image("hello", width=64, height=64) == "/tmp/google.png"


def test_transform_with_references_routes_by_mode(monkeypatch):
    from integrations import google_image_client, image_client, local_image_client

    monkeypatch.setattr(google_image_client, "transform_with_references", lambda *a, **k: "/tmp/google.png")
    monkeypatch.setattr(local_image_client, "transform_with_references", lambda *a, **k: "/tmp/local.png")

    monkeypatch.setenv("LOCAL_MODELS_ENABLED", "false")
    monkeypatch.delenv("LOCAL_IMAGE_MODE", raising=False)
    assert image_client.transform_with_references("p", ["/tmp/a.png"]) == "/tmp/google.png"

    monkeypatch.setenv("LOCAL_MODELS_ENABLED", "true")
    assert image_client.transform_with_references("p", ["/tmp/a.png"]) == "/tmp/local.png"


def test_local_batch_falls_back_to_sequential_calls(monkeypatch):
    monkeypatch.setenv("LOCAL_MODELS_ENABLED", "true")
    monkeypatch.delenv("LOCAL_IMAGE_MODE", raising=False)
    from integrations import image_client, local_image_client

    seen: list[str] = []

    def fake(prompt, width, height, reference_image_path, style_reference_path, original_prompt, script_id):
        seen.append(prompt)
        return f"/tmp/{prompt}.png"

    monkeypatch.setattr(local_image_client, "generate_image", fake)
    from integrations.google_image_client import GoogleBatchImageRequest

    results = image_client.generate_images_batch(
        requests=[
            GoogleBatchImageRequest(key="a", prompt="one", aspect_ratio="16:9"),
            GoogleBatchImageRequest(key="b", prompt="two", aspect_ratio="16:9"),
        ]
    )
    assert seen == ["one", "two"]
    assert [r.key for r in results] == ["a", "b"]
    assert all(r.image_path and not r.error for r in results)


def test_local_batch_records_per_request_errors(monkeypatch):
    monkeypatch.setenv("LOCAL_MODELS_ENABLED", "true")
    monkeypatch.delenv("LOCAL_IMAGE_MODE", raising=False)
    from integrations import image_client, local_image_client
    from integrations.google_image_client import GoogleBatchImageRequest

    def fake(prompt, width, height, reference_image_path, style_reference_path, original_prompt, script_id):
        if prompt == "bad":
            raise RuntimeError("comfy exploded")
        return "/tmp/ok.png"

    monkeypatch.setattr(local_image_client, "generate_image", fake)
    results = image_client.generate_images_batch(
        requests=[
            GoogleBatchImageRequest(key="a", prompt="good", aspect_ratio="16:9"),
            GoogleBatchImageRequest(key="b", prompt="bad", aspect_ratio="16:9"),
        ]
    )
    by_key = {r.key: r for r in results}
    assert by_key["a"].image_path == "/tmp/ok.png"
    assert "comfy exploded" in (by_key["b"].error or "")
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run --project backend pytest tests/test_image_client_provider_routing.py -v`
Expected: FAIL — `image_client` has no `transform_with_references`

- [ ] **Step 3: Write minimal implementation**

Replace the body of `backend/integrations/image_client.py`:

```python
"""Image generation provider router.

The only module allowed to name an image provider. Local Mode routes to
ComfyUI; otherwise calls go to Google Gemini. Every image entry point in the
pipeline goes through here so a mode switch can never leave one path on the
cloud.
"""

import logging

from config import IMAGE_HEIGHT, IMAGE_WIDTH
from integrations.google_image_client import GoogleBatchImageRequest, GoogleBatchImageResult
from integrations.local_models import active_model, modality_source

logger = logging.getLogger(__name__)


def resolved_provider() -> str:
    """"local" or "google" for the current mode."""
    return "local" if modality_source("image") == "local" else "google"


def provider_fingerprint() -> str:
    """Stable identity of the active image engine, for cache markers."""
    if resolved_provider() == "local":
        return f"local:{active_model('image').id}"
    return "google"


def generate_image(
    prompt: str,
    width: int = IMAGE_WIDTH,
    height: int = IMAGE_HEIGHT,
    reference_image_path: str | None = None,
    style_reference_path: str | None = None,
    original_prompt: str | None = None,
    script_id: str | None = None,
) -> str:
    """Generate an image using the configured provider.

    reference_image_path and style_reference_path are passed to the provider as
    visual references for character and global-style consistency.
    original_prompt is the raw visual description before the style guide was
    prepended; the Google provider uses it to retry content-filter blocks.
    """
    provider = resolved_provider()
    logger.info(
        "Image generation via %s (width=%d, height=%d, has_reference=%s, has_style_ref=%s)",
        provider, width, height, reference_image_path is not None, style_reference_path is not None,
    )

    if provider == "local":
        from integrations.local_image_client import generate_image as _gen
    else:
        from integrations.google_image_client import generate_image as _gen

    return _gen(
        prompt,
        width=width,
        height=height,
        reference_image_path=reference_image_path,
        style_reference_path=style_reference_path,
        original_prompt=original_prompt,
        script_id=script_id,
    )


def transform_with_references(
    prompt: str,
    image_paths: list[str],
    width: int = IMAGE_WIDTH,
    height: int = IMAGE_HEIGHT,
    script_id: str | None = None,
) -> str:
    """Transform an image using multiple reference images via the active provider."""
    provider = resolved_provider()
    logger.info("Image transform via %s with %d reference images", provider, len(image_paths))

    if provider == "local":
        from integrations.local_image_client import transform_with_references as _transform
    else:
        from integrations.google_image_client import transform_with_references as _transform

    return _transform(prompt, image_paths, width=width, height=height, script_id=script_id)


def generate_images_batch(
    *,
    requests: list[GoogleBatchImageRequest],
    script_id: str | None = None,
    poll_interval_seconds: float = 10.0,
    timeout_seconds: float = 24 * 60 * 60,
) -> list[GoogleBatchImageResult]:
    """Generate independent images through the active provider.

    Batching exists to amortise cloud round-trips and discounts, neither of
    which applies locally, so the local path runs the same requests
    sequentially and reports per-request errors rather than failing the batch.
    """
    if not requests:
        return []

    if resolved_provider() != "local":
        from integrations.google_image_client import generate_images_batch as _batch

        return _batch(
            requests=requests,
            script_id=script_id,
            poll_interval_seconds=poll_interval_seconds,
            timeout_seconds=timeout_seconds,
        )

    from integrations.local_image_client import generate_image as _gen

    logger.info("Running %d image requests sequentially on the local provider", len(requests))
    results: list[GoogleBatchImageResult] = []
    for request in requests:
        try:
            path = _gen(
                request.prompt,
                width=IMAGE_WIDTH,
                height=IMAGE_HEIGHT,
                reference_image_path=request.reference_image_path,
                style_reference_path=request.style_reference_path,
                original_prompt=None,
                script_id=script_id,
            )
            results.append(GoogleBatchImageResult(key=request.key, image_path=path))
        except Exception as exc:
            logger.error("Local image request %s failed: %s", request.key, exc, exc_info=True)
            results.append(GoogleBatchImageResult(key=request.key, error=str(exc)))
    return results
```

Then repoint the three bypassing call sites:

- `backend/pipeline/thumbnail.py:181` and `:439` — change `from integrations.google_image_client import transform_with_references` to `from integrations.image_client import transform_with_references`.
- `backend/pipeline/main_character.py:19` — change `from integrations.google_image_client import generate_image` to `from integrations.image_client import generate_image`.
- `backend/pipeline/image_gen.py:15` — change `from integrations.google_image_client import GoogleBatchImageRequest, generate_images_batch` to `from integrations.google_image_client import GoogleBatchImageRequest` plus `from integrations.image_client import generate_image, generate_images_batch`, and delete the now-duplicated `from integrations.image_client import generate_image` on line 16.

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run --project backend pytest tests/test_image_client_provider_routing.py -v && uv run --project backend pytest -q`
Expected: PASS, and no regressions in the full backend suite

- [ ] **Step 5: Commit**

```bash
git add backend/integrations/image_client.py backend/pipeline/thumbnail.py backend/pipeline/main_character.py backend/pipeline/image_gen.py backend/tests/test_image_client_provider_routing.py
git commit -m "Route every image entry point through the image_client provider seam"
```

---

### Task 6: Local TTS client matching the ElevenLabs contract

**Files:**
- Create: `backend/integrations/local_tts_client.py`
- Test: `backend/tests/test_local_tts_client.py`

**Interfaces:**
- Consumes: `local_models.active_model`, `local_runtime.ensure_daemon`, `local_runtime.hold`, `local_runtime.daemon_url`, `pipeline.audio_alignment.align_audio`.
- Produces: `generate_speech(text, voice_id, model_id, output_format, voice_settings, script_id) -> tuple[bytes, list[dict]]` — byte-identical contract to `elevenlabs_client.generate_speech`, returning MP3 bytes and `[{word, start_ms, end_ms}]`.

mlx-audio serves OpenAI-compatible `/v1/audio/speech` and returns WAV. The client transcodes to MP3 with ffmpeg (already a project dependency) and derives word timestamps from the existing faster-whisper aligner rather than inventing a second timing source.

- [ ] **Step 1: Write the failing test**

```python
# backend/tests/test_local_tts_client.py
from pathlib import Path

import pytest

from integrations import local_tts_client


@pytest.fixture
def stub_backend(monkeypatch):
    monkeypatch.setattr(local_tts_client, "ensure_daemon", lambda backend: None)
    monkeypatch.setattr(local_tts_client, "_post_speech", lambda **kwargs: b"RIFFFAKEWAVDATA")
    monkeypatch.setattr(local_tts_client, "_wav_to_mp3", lambda data: b"ID3FAKEMP3")
    monkeypatch.setattr(
        local_tts_client,
        "align_audio",
        lambda path, text: [
            {"word": "hello", "start_ms": 0, "end_ms": 400},
            {"word": "world", "start_ms": 400, "end_ms": 900},
        ],
    )


def test_returns_mp3_bytes_and_word_timestamps(stub_backend):
    audio, words = local_tts_client.generate_speech(text="hello world", voice_id="narrator")
    assert audio == b"ID3FAKEMP3"
    assert [w["word"] for w in words] == ["hello", "world"]
    assert words[-1]["end_ms"] == 900


def test_word_timestamps_match_elevenlabs_key_shape(stub_backend):
    _, words = local_tts_client.generate_speech(text="hello world", voice_id="narrator")
    for word in words:
        assert set(word) == {"word", "start_ms", "end_ms"}


def test_request_carries_the_active_voice_model(stub_backend, monkeypatch):
    monkeypatch.setenv("LOCAL_VOICE_MODEL", "kokoro-82m")
    captured: dict = {}
    monkeypatch.setattr(
        local_tts_client,
        "_post_speech",
        lambda **kwargs: captured.update(kwargs) or b"RIFFFAKEWAVDATA",
    )
    local_tts_client.generate_speech(text="hi", voice_id="af_heart")
    assert captured["model"] == "hexgrad/Kokoro-82M"
    assert captured["voice"] == "af_heart"
    assert captured["text"] == "hi"


def test_empty_text_returns_empty_result(stub_backend):
    audio, words = local_tts_client.generate_speech(text="   ", voice_id="narrator")
    assert audio == b""
    assert words == []


def test_alignment_failure_degrades_to_empty_timestamps(stub_backend, monkeypatch):
    monkeypatch.setattr(local_tts_client, "align_audio", lambda path, text: [])
    audio, words = local_tts_client.generate_speech(text="hello world", voice_id="narrator")
    assert audio == b"ID3FAKEMP3"
    assert words == []


def test_temp_wav_is_cleaned_up(stub_backend, monkeypatch):
    seen: list[Path] = []

    def spy(path, text):
        seen.append(Path(path))
        return []

    monkeypatch.setattr(local_tts_client, "align_audio", spy)
    local_tts_client.generate_speech(text="hello", voice_id="narrator")
    assert seen and not seen[0].exists()


def test_missing_daemon_raises_actionable_error(monkeypatch):
    def boom(backend):
        raise RuntimeError("mlx-audio daemon is not responding")

    monkeypatch.setattr(local_tts_client, "ensure_daemon", boom)
    with pytest.raises(RuntimeError, match="not responding"):
        local_tts_client.generate_speech(text="hi", voice_id="narrator")
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run --project backend pytest tests/test_local_tts_client.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'integrations.local_tts_client'`

- [ ] **Step 3: Write minimal implementation**

```python
# backend/integrations/local_tts_client.py
"""Local text-to-speech through an mlx-audio server.

Returns exactly what elevenlabs_client.generate_speech returns — MP3 bytes and
word-level timestamps — so pipeline.voiceover and everything downstream are
unchanged. mlx-audio emits WAV and no timestamps, so this module transcodes
with ffmpeg and reuses the faster-whisper aligner the project already ships.
"""

import logging
import os
import subprocess
import tempfile
import time
from pathlib import Path

import httpx

from integrations.local_models import active_model
from integrations.usage_tracker import record_usage
from pipeline.audio_alignment import align_audio
from pipeline.local_runtime import daemon_url, ensure_daemon, hold

logger = logging.getLogger(__name__)

DEFAULT_TIMEOUT_SECONDS = 600.0


def _post_speech(*, model: str, voice: str, text: str, speed: float, timeout: float) -> bytes:
    """Call the mlx-audio OpenAI-compatible speech endpoint and return WAV bytes."""
    response = httpx.post(
        f"{daemon_url('mlx-audio')}/v1/audio/speech",
        json={
            "model": model,
            "voice": voice,
            "input": text,
            "response_format": "wav",
            "speed": speed,
        },
        timeout=timeout,
    )
    response.raise_for_status()
    return response.content


def _wav_to_mp3(wav_bytes: bytes) -> bytes:
    """Transcode WAV to MP3 with ffmpeg, matching the ElevenLabs output format."""
    process = subprocess.run(
        ["ffmpeg", "-hide_banner", "-loglevel", "error", "-f", "wav", "-i", "pipe:0",
         "-codec:a", "libmp3lame", "-b:a", "128k", "-ar", "44100", "-f", "mp3", "pipe:1"],
        input=wav_bytes,
        capture_output=True,
        check=False,
    )
    if process.returncode != 0:
        raise RuntimeError(f"ffmpeg failed to transcode local TTS audio: {process.stderr.decode()[:400]}")
    return process.stdout


def generate_speech(
    text: str,
    voice_id: str,
    model_id: str = "",
    output_format: str = "mp3_44100_128",
    voice_settings: dict | None = None,
    script_id: str | None = None,
) -> tuple[bytes, list[dict]]:
    """Generate speech locally and return (MP3 bytes, word_timestamps).

    model_id and output_format exist for signature parity with the ElevenLabs
    client. The local engine is chosen by LOCAL_VOICE_MODEL, and output is
    always MP3 44.1 kHz 128 kbps.
    """
    ensure_daemon("mlx-audio")
    clean_text = (text or "").strip()
    if not clean_text:
        return b"", []

    model = active_model("voice")
    speed = float((voice_settings or {}).get("speed", 1.0))
    timeout = float(os.environ.get("LOCAL_TTS_TIMEOUT_SECONDS", DEFAULT_TIMEOUT_SECONDS))

    logger.info(
        "Calling local TTS model=%s voice=%s chars=%d",
        model.id, voice_id, len(clean_text),
    )
    started = time.monotonic()

    with hold("voice"):
        wav_bytes = _post_speech(
            model=model.weights,
            voice=voice_id,
            text=clean_text,
            speed=speed,
            timeout=timeout,
        )

    mp3_bytes = _wav_to_mp3(wav_bytes)

    handle = tempfile.NamedTemporaryFile(suffix=".wav", delete=False)
    handle.write(wav_bytes)
    handle.close()
    wav_path = Path(handle.name)
    try:
        word_timestamps = align_audio(wav_path, clean_text)
    finally:
        wav_path.unlink(missing_ok=True)

    if not word_timestamps:
        logger.warning("Local alignment produced no word timestamps for a %d-char scene", len(clean_text))

    elapsed = time.monotonic() - started
    record_usage(
        service="local_voice",
        operation="tts",
        model=model.id,
        characters=len(clean_text),
        cost_estimate=0.0,
        script_id=script_id,
    )
    logger.info(
        "Local TTS complete in %.1fs — %d bytes MP3, %d words (model=%s)",
        elapsed, len(mp3_bytes), len(word_timestamps), model.id,
    )
    return mp3_bytes, word_timestamps
```

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run --project backend pytest tests/test_local_tts_client.py -v`
Expected: PASS, 7 tests

- [ ] **Step 5: Commit**

```bash
git add backend/integrations/local_tts_client.py backend/tests/test_local_tts_client.py
git commit -m "Add local TTS client matching the ElevenLabs speech contract"
```

---

### Task 7: Route voiceover to the local TTS client

**Files:**
- Modify: `backend/pipeline/voiceover.py:11` (import), `:250` (call site in `generate_scene_audio`)
- Test: `backend/tests/test_voiceover_local_routing.py`

**Interfaces:**
- Consumes: `local_models.modality_source`, `local_tts_client.generate_speech`.
- Produces: `voiceover.active_speech_client() -> Callable`; `generate_scene_audio` keeps its four-tuple return.

`generate_scene_audio` currently comments that the duration comes "from ElevenLabs timestamps". Locally it comes from the whisper aligner, so the log wording is corrected to name the source generically.

- [ ] **Step 1: Write the failing test**

```python
# backend/tests/test_voiceover_local_routing.py
from pipeline import voiceover


def test_cloud_mode_selects_elevenlabs(monkeypatch):
    monkeypatch.setenv("LOCAL_MODELS_ENABLED", "false")
    monkeypatch.delenv("LOCAL_VOICE_MODE", raising=False)
    from integrations import elevenlabs_client

    assert voiceover.active_speech_client() is elevenlabs_client.generate_speech


def test_local_mode_selects_local_client(monkeypatch):
    monkeypatch.setenv("LOCAL_MODELS_ENABLED", "true")
    monkeypatch.delenv("LOCAL_VOICE_MODE", raising=False)
    from integrations import local_tts_client

    assert voiceover.active_speech_client() is local_tts_client.generate_speech


def test_voice_pinned_cloud_overrides_master_switch(monkeypatch):
    monkeypatch.setenv("LOCAL_MODELS_ENABLED", "true")
    monkeypatch.setenv("LOCAL_VOICE_MODE", "cloud")
    from integrations import elevenlabs_client

    assert voiceover.active_speech_client() is elevenlabs_client.generate_speech


def test_generate_scene_audio_uses_the_local_client(monkeypatch, tmp_path):
    monkeypatch.setenv("LOCAL_MODELS_ENABLED", "true")
    monkeypatch.delenv("LOCAL_VOICE_MODE", raising=False)
    monkeypatch.setattr(voiceover, "DATA_DIR", tmp_path)

    calls: list[str] = []

    def fake(text, voice_id, model_id=None, voice_settings=None, script_id=None):
        calls.append(text)
        return b"ID3FAKE", [{"word": "hi", "start_ms": 0, "end_ms": 500}]

    monkeypatch.setattr(voiceover, "active_speech_client", lambda: fake)

    web_path, duration, words, phrases = voiceover.generate_scene_audio(
        scene_id="s1", narration="hi", voice_id="narrator", script_id="proj1",
    )
    assert calls == ["hi"]
    assert duration == 0.5
    assert web_path == "/static/projects/proj1/audio/s1.mp3"
    assert (tmp_path / "projects" / "proj1" / "audio" / "s1.mp3").read_bytes() == b"ID3FAKE"
    assert words[0]["word"] == "hi"
    assert phrases
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run --project backend pytest tests/test_voiceover_local_routing.py -v`
Expected: FAIL with `AttributeError: module 'pipeline.voiceover' has no attribute 'active_speech_client'`

- [ ] **Step 3: Write minimal implementation**

In `backend/pipeline/voiceover.py`, replace the line-11 import with:

```python
from integrations.elevenlabs_client import generate_speech as _elevenlabs_generate_speech
from integrations.local_models import modality_source as _modality_source
```

Add below the imports:

```python
def active_speech_client():
    """The TTS function for the current mode.

    Both clients return (MP3 bytes, [{word, start_ms, end_ms}]), so callers do
    not branch on which one is active.
    """
    if _modality_source("voice") == "local":
        from integrations.local_tts_client import generate_speech as _local_generate_speech

        return _local_generate_speech
    return _elevenlabs_generate_speech
```

In `generate_scene_audio`, replace the `generate_speech(` call at :250 with:

```python
    audio_bytes, word_timestamps = active_speech_client()(
```

and change the three duration log messages so they no longer claim ElevenLabs as the source: `"(from ElevenLabs timestamps)"` becomes `"(from word timestamps)"`, and the comment above them becomes:

```python
    # Prefer the reported word timings (last word end_ms) as they are more
    # accurate than MP3 frame parsing. Fall back to MP3 parsing when the active
    # TTS engine returned no timestamps.
```

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run --project backend pytest tests/test_voiceover_local_routing.py -v && uv run --project backend pytest -q`
Expected: PASS with no regressions

- [ ] **Step 5: Commit**

```bash
git add backend/pipeline/voiceover.py backend/tests/test_voiceover_local_routing.py
git commit -m "Route voiceover through the local TTS client in Local Mode"
```

---

### Task 8: Append the licence credit required by the active voice model

**Files:**
- Modify: `backend/pipeline/seo.py` (after `generate_seo` builds its result, around :232)
- Test: `backend/tests/test_seo_attribution.py`

**Interfaces:**
- Consumes: `local_models.modality_source`, `local_models.active_model`, `local_models.attribution_for`.
- Produces: `seo.required_voice_attribution() -> str`; `seo.apply_voice_attribution(description: str) -> str`.

Higgs TTS 3's Creator Use Grant permits monetized video only with a visible credit, so this is enforced in code and has no off switch.

- [ ] **Step 1: Write the failing test**

```python
# backend/tests/test_seo_attribution.py
from pipeline import seo


def _local_higgs(monkeypatch):
    monkeypatch.setenv("LOCAL_MODELS_ENABLED", "true")
    monkeypatch.delenv("LOCAL_VOICE_MODE", raising=False)
    monkeypatch.setenv("LOCAL_VOICE_MODEL", "higgs-tts-3-4b")


def test_no_attribution_in_cloud_mode(monkeypatch):
    monkeypatch.setenv("LOCAL_MODELS_ENABLED", "false")
    monkeypatch.delenv("LOCAL_VOICE_MODE", raising=False)
    assert seo.required_voice_attribution() == ""
    assert seo.apply_voice_attribution("body") == "body"


def test_higgs_attribution_is_appended(monkeypatch):
    _local_higgs(monkeypatch)
    credit = seo.required_voice_attribution()
    assert credit
    result = seo.apply_voice_attribution("body")
    assert result.startswith("body")
    assert result.endswith(credit)


def test_attribution_is_not_duplicated(monkeypatch):
    _local_higgs(monkeypatch)
    once = seo.apply_voice_attribution("body")
    assert seo.apply_voice_attribution(once) == once


def test_no_attribution_for_permissive_local_models(monkeypatch):
    monkeypatch.setenv("LOCAL_MODELS_ENABLED", "true")
    monkeypatch.delenv("LOCAL_VOICE_MODE", raising=False)
    monkeypatch.setenv("LOCAL_VOICE_MODEL", "kokoro-82m")
    assert seo.required_voice_attribution() == ""
    assert seo.apply_voice_attribution("body") == "body"


def test_generate_seo_applies_attribution(monkeypatch):
    _local_higgs(monkeypatch)
    payload = '{"youtube": {"title": "T", "description": "D", "tags": ["a"]}}'
    monkeypatch.setattr(seo, "chat", lambda *a, **k: payload)
    result = seo.generate_seo("T", [("Intro", "0:00")])
    assert seo.required_voice_attribution() in result.youtube.description


def test_empty_description_still_gets_the_credit(monkeypatch):
    _local_higgs(monkeypatch)
    assert seo.apply_voice_attribution("") == seo.required_voice_attribution()
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run --project backend pytest tests/test_seo_attribution.py -v`
Expected: FAIL with `AttributeError: module 'pipeline.seo' has no attribute 'required_voice_attribution'`

- [ ] **Step 3: Write minimal implementation**

Add to the imports in `backend/pipeline/seo.py`:

```python
from integrations.local_models import active_model, attribution_for, modality_source
```

Add above `generate_seo`:

```python
def required_voice_attribution() -> str:
    """The licence credit the active voice model requires, or "".

    Higgs TTS 3 permits monetized video under a Creator Use Grant only when the
    work credits Boson AI, so the credit is a property of the model rather than
    a user preference. There is deliberately no setting to disable this.
    """
    if modality_source("voice") != "local":
        return ""
    return attribution_for(active_model("voice").id)


def apply_voice_attribution(description: str) -> str:
    """Append the required voice credit to a description, idempotently."""
    credit = required_voice_attribution()
    if not credit or credit in description:
        return description
    if not description:
        return credit
    return f"{description}\n\n{credit}"
```

In `generate_seo`, immediately after `yt.tags = _trim_tags(yt.tags)`:

```python
    yt.description = apply_voice_attribution(yt.description)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run --project backend pytest tests/test_seo_attribution.py -v`
Expected: PASS, 6 tests

- [ ] **Step 5: Commit**

```bash
git add backend/pipeline/seo.py backend/tests/test_seo_attribution.py
git commit -m "Append required voice-model licence credit to SEO descriptions"
```

---

### Task 9: Invalidate caches across a mode switch

**Files:**
- Modify: `backend/pipeline/image_gen.py` (the `"provider"` marker fields at :510, :1537, :1567, :1587, :1762, :1965, :2325)
- Modify: `backend/pipeline/remotion_render.py` (`subtitle_render_fingerprint`)
- Test: `backend/tests/test_local_cache_invalidation.py`

**Interfaces:**
- Consumes: `image_client.provider_fingerprint`, `local_models.modality_source`, `local_models.active_model`.
- Produces: `remotion_render.voice_engine_fingerprint() -> str`.

Cloud and local assets are not interchangeable. Without this, a Local Mode run silently reuses Gemini images and an ElevenLabs narrator.

- [ ] **Step 1: Write the failing test**

```python
# backend/tests/test_local_cache_invalidation.py
from integrations import image_client
from pipeline import remotion_render


def test_image_fingerprint_differs_between_modes(monkeypatch):
    monkeypatch.setenv("LOCAL_MODELS_ENABLED", "false")
    monkeypatch.delenv("LOCAL_IMAGE_MODE", raising=False)
    cloud = image_client.provider_fingerprint()
    monkeypatch.setenv("LOCAL_MODELS_ENABLED", "true")
    local = image_client.provider_fingerprint()
    assert cloud == "google"
    assert local.startswith("local:")
    assert cloud != local


def test_image_fingerprint_differs_between_local_models(monkeypatch):
    monkeypatch.setenv("LOCAL_MODELS_ENABLED", "true")
    monkeypatch.delenv("LOCAL_IMAGE_MODE", raising=False)
    monkeypatch.setenv("LOCAL_IMAGE_MODEL", "qwen-image-edit-2511")
    first = image_client.provider_fingerprint()
    monkeypatch.setenv("LOCAL_IMAGE_MODEL", "flux2-klein-4b")
    assert image_client.provider_fingerprint() != first


def test_voice_fingerprint_differs_between_modes(monkeypatch):
    monkeypatch.setenv("LOCAL_MODELS_ENABLED", "false")
    monkeypatch.delenv("LOCAL_VOICE_MODE", raising=False)
    cloud = remotion_render.voice_engine_fingerprint()
    monkeypatch.setenv("LOCAL_MODELS_ENABLED", "true")
    assert remotion_render.voice_engine_fingerprint() != cloud


def test_voice_fingerprint_differs_between_local_voices(monkeypatch):
    monkeypatch.setenv("LOCAL_MODELS_ENABLED", "true")
    monkeypatch.delenv("LOCAL_VOICE_MODE", raising=False)
    monkeypatch.setenv("LOCAL_VOICE_MODEL", "higgs-tts-3-4b")
    first = remotion_render.voice_engine_fingerprint()
    monkeypatch.setenv("LOCAL_VOICE_MODEL", "kokoro-82m")
    assert remotion_render.voice_engine_fingerprint() != first


def test_subtitle_render_fingerprint_includes_the_voice_engine(monkeypatch):
    monkeypatch.setenv("LOCAL_MODELS_ENABLED", "false")
    monkeypatch.delenv("LOCAL_VOICE_MODE", raising=False)
    cloud = remotion_render.subtitle_render_fingerprint()
    monkeypatch.setenv("LOCAL_MODELS_ENABLED", "true")
    assert remotion_render.subtitle_render_fingerprint() != cloud
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run --project backend pytest tests/test_local_cache_invalidation.py -v`
Expected: FAIL — `provider_fingerprint` exists from Task 5 but `voice_engine_fingerprint` does not

- [ ] **Step 3: Write minimal implementation**

In `backend/pipeline/image_gen.py`, replace every `os.environ.get("IMAGE_PROVIDER", "google")` used as a cache-marker `"provider"` value (lines 510, 1537, 1567, 1587, 1762, 1965, 2325) with `provider_fingerprint()`, importing it at the top:

```python
from integrations.image_client import generate_image, generate_images_batch, provider_fingerprint
```

In `backend/pipeline/remotion_render.py`, add near the other fingerprint helpers:

```python
def voice_engine_fingerprint() -> str:
    """Stable identity of the active TTS engine, for render cache markers.

    A video voiced locally must not reuse renders produced from ElevenLabs
    audio, and switching local voices must re-render too.
    """
    from integrations.local_models import active_model, modality_source

    if modality_source("voice") != "local":
        return "elevenlabs"
    return f"local:{active_model('voice').id}"
```

and include its value in the string `subtitle_render_fingerprint` hashes, alongside the existing `BLINK_RENDERER_VERSION` and `CAMERA_DRIFT_RENDERER_VERSION` components.

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run --project backend pytest tests/test_local_cache_invalidation.py -v && uv run --project backend pytest -q`
Expected: PASS with no regressions

- [ ] **Step 5: Commit**

```bash
git add backend/pipeline/image_gen.py backend/pipeline/remotion_render.py backend/tests/test_local_cache_invalidation.py
git commit -m "Invalidate image and render caches when the local model engine changes"
```

---

### Task 10: Settings API keys, validation, and status endpoint

**Files:**
- Modify: `backend/api/settings.py` (`ALLOWED_KEYS` :41, `_PLAINTEXT_KEYS` :96, `_DEFAULTS` :136, `save_keys` validation)
- Create: `backend/api/local_models.py`
- Modify: `backend/api/__init__.py` (register the router)
- Test: `backend/tests/test_local_models_api.py`

**Interfaces:**
- Consumes: `local_models.REGISTRY`, `local_models.models_for`, `local_models.modality_source`, `local_models.active_model`, `local_runtime.daemon_health`.
- Produces: `GET /api/local-models` returning `{"enabled": bool, "modalities": {...}, "catalog": {...}, "daemons": {...}}`.

- [ ] **Step 1: Write the failing test**

```python
# backend/tests/test_local_models_api.py
import pytest
from fastapi.testclient import TestClient

from api import app
from api import settings as settings_module


@pytest.fixture
def client():
    return TestClient(app)


def test_new_keys_are_allowed_and_plaintext():
    for key in (
        "LOCAL_MODELS_ENABLED", "LOCAL_TEXT_MODE", "LOCAL_IMAGE_MODE", "LOCAL_VOICE_MODE",
        "LOCAL_TEXT_MODEL", "LOCAL_TEXT_FAST_MODEL", "LOCAL_IMAGE_MODEL", "LOCAL_VOICE_MODEL",
        "LOCAL_COMFYUI_URL", "LOCAL_TTS_URL",
    ):
        assert key in settings_module.ALLOWED_KEYS
        assert key in settings_module._PLAINTEXT_KEYS


def test_defaults_are_conservative():
    assert settings_module._DEFAULTS["LOCAL_MODELS_ENABLED"] == "false"
    assert settings_module._DEFAULTS["LOCAL_TEXT_MODE"] == "auto"
    assert settings_module._DEFAULTS["LOCAL_VOICE_MODEL"] == "higgs-tts-3-4b"


def test_save_rejects_an_invalid_mode(client):
    response = client.put("/api/settings/keys", json={"LOCAL_IMAGE_MODE": "sideways"})
    assert response.status_code == 400
    assert "LOCAL_IMAGE_MODE" in response.json()["detail"]


def test_save_rejects_a_model_id_from_the_wrong_modality(client):
    response = client.put("/api/settings/keys", json={"LOCAL_VOICE_MODEL": "flux2-klein-4b"})
    assert response.status_code == 400
    assert "LOCAL_VOICE_MODEL" in response.json()["detail"]


def test_save_accepts_valid_values(client):
    response = client.put("/api/settings/keys", json={
        "LOCAL_IMAGE_MODE": "local",
        "LOCAL_IMAGE_MODEL": "flux2-klein-4b",
    })
    assert response.status_code == 200


def test_status_endpoint_reports_catalog_and_daemons(client, monkeypatch):
    from pipeline import local_runtime

    monkeypatch.setattr(local_runtime, "_probe", lambda url: False)
    response = client.get("/api/local-models")
    assert response.status_code == 200
    body = response.json()
    assert set(body["catalog"]) == {"text", "image", "voice"}
    assert any(m["id"] == "higgs-tts-3-4b" for m in body["catalog"]["voice"])
    assert set(body["daemons"]) == {"ollama", "comfyui", "mlx-audio"}
    assert body["daemons"]["comfyui"]["healthy"] is False


def test_status_marks_attribution_requiring_models(client, monkeypatch):
    from pipeline import local_runtime

    monkeypatch.setattr(local_runtime, "_probe", lambda url: True)
    body = client.get("/api/local-models").json()
    higgs = next(m for m in body["catalog"]["voice"] if m["id"] == "higgs-tts-3-4b")
    kokoro = next(m for m in body["catalog"]["voice"] if m["id"] == "kokoro-82m")
    assert higgs["requires_attribution"] is True
    assert higgs["attribution_text"]
    assert kokoro["requires_attribution"] is False
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run --project backend pytest tests/test_local_models_api.py -v`
Expected: FAIL — keys missing from `ALLOWED_KEYS`, and `/api/local-models` returns 404

- [ ] **Step 3: Write minimal implementation**

In `backend/api/settings.py`, add to `ALLOWED_KEYS` and `_PLAINTEXT_KEYS`:

```python
    "LOCAL_MODELS_ENABLED",
    "LOCAL_TEXT_MODE",
    "LOCAL_IMAGE_MODE",
    "LOCAL_VOICE_MODE",
    "LOCAL_TEXT_MODEL",
    "LOCAL_TEXT_FAST_MODEL",
    "LOCAL_IMAGE_MODEL",
    "LOCAL_VOICE_MODEL",
    "LOCAL_COMFYUI_URL",
    "LOCAL_TTS_URL",
```

Add to `_DEFAULTS`:

```python
    "LOCAL_MODELS_ENABLED": "false",
    "LOCAL_TEXT_MODE": "auto",
    "LOCAL_IMAGE_MODE": "auto",
    "LOCAL_VOICE_MODE": "auto",
    "LOCAL_TEXT_MODEL": "qwen3.8-27b",
    "LOCAL_TEXT_FAST_MODEL": "qwen3.8-27b",
    "LOCAL_IMAGE_MODEL": "qwen-image-edit-2511",
    "LOCAL_VOICE_MODEL": "higgs-tts-3-4b",
    "LOCAL_COMFYUI_URL": "http://127.0.0.1:8188",
    "LOCAL_TTS_URL": "http://127.0.0.1:8770",
```

Add this validation inside `save_keys`, beside the other provider checks:

```python
    for modality in ("TEXT", "IMAGE", "VOICE"):
        mode_key = f"LOCAL_{modality}_MODE"
        if mode_key in keys:
            mode = (keys[mode_key] or "").strip().lower()
            if mode and mode not in {"auto", "local", "cloud"}:
                raise HTTPException(
                    status_code=400,
                    detail=f"Invalid {mode_key}: {mode!r}. Must be one of ['auto', 'cloud', 'local'].",
                )
            keys[mode_key] = mode

    for modality, model_key in (
        ("text", "LOCAL_TEXT_MODEL"),
        ("text", "LOCAL_TEXT_FAST_MODEL"),
        ("image", "LOCAL_IMAGE_MODEL"),
        ("voice", "LOCAL_VOICE_MODEL"),
    ):
        if model_key not in keys:
            continue
        model_id = (keys[model_key] or "").strip()
        if not model_id:
            continue
        model = _local_models_registry.REGISTRY.get(model_id)
        if model is None or model.modality != modality:
            valid = sorted(m.id for m in _local_models_registry.models_for(modality))
            raise HTTPException(
                status_code=400,
                detail=f"Invalid {model_key}: {model_id!r}. Must be one of {valid}.",
            )
        keys[model_key] = model_id
```

with this import added at the top of the file:

```python
from integrations import local_models as _local_models_registry
```

Create the status router:

```python
# backend/api/local_models.py
"""Read-only status for Local Mode: catalog, active selections, daemon health."""

from fastapi import APIRouter

from integrations.local_models import MODALITIES, active_model, modality_source, models_for
from pipeline.local_runtime import DAEMONS, daemon_health, daemon_url

router = APIRouter(prefix="/api/local-models", tags=["local-models"])


@router.get("")
async def get_local_models() -> dict:
    """Everything the Settings panel needs to render Local Mode in one call."""
    health = daemon_health()
    return {
        "enabled": modality_source("text") == "local"
        or modality_source("image") == "local"
        or modality_source("voice") == "local",
        "modalities": {
            modality: {
                "source": modality_source(modality),
                "active_model": active_model(modality).id,
            }
            for modality in MODALITIES
        },
        "catalog": {
            modality: [
                {
                    "id": model.id,
                    "label": model.label,
                    "description": model.description,
                    "backend": model.backend,
                    "license": model.license,
                    "approx_resident_gb": model.approx_resident_gb,
                    "requires_attribution": model.requires_attribution,
                    "attribution_text": model.attribution_text,
                }
                for model in models_for(modality)
            ]
            for modality in MODALITIES
        },
        "daemons": {
            backend: {"healthy": health[backend], "url": daemon_url(backend)}
            for backend in DAEMONS
        },
    }
```

Register it in `backend/api/__init__.py` alongside the other routers:

```python
from api.local_models import router as local_models_router
app.include_router(local_models_router)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run --project backend pytest tests/test_local_models_api.py -v && uv run --project backend pytest -q`
Expected: PASS with no regressions

- [ ] **Step 5: Commit**

```bash
git add backend/api/settings.py backend/api/local_models.py backend/api/__init__.py backend/tests/test_local_models_api.py
git commit -m "Add Local Mode settings keys, validation, and status endpoint"
```

---

### Task 11: Settings UI — Local Models section

**Files:**
- Create: `frontend/src/components/settings/LocalModelsSection.tsx`
- Create: `frontend/src/components/settings/LocalModelsSection.test.tsx`
- Modify: `frontend/src/components/settings/SettingsPage.tsx:22-29` (nav entry), render switch near `:132`
- Modify: `frontend/src/api.ts` (add `getLocalModels`)

**Interfaces:**
- Consumes: `GET /api/local-models`, `GET /api/settings/keys`, `PUT /api/settings/keys`, `useDebouncedAutosave`.
- Produces: a `local-models` section id in `SettingsPage`'s nav under the `AI & Generation` group.

Follow `GeneralSection.tsx`'s conventions: `KeyInfo` shape from `/api/settings/keys`, debounced autosave, framed purple title box for the section header, `text-sm` labels for controls, hint text on non-obvious controls.

- [ ] **Step 1: Write the failing test**

```tsx
// frontend/src/components/settings/LocalModelsSection.test.tsx
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";
import LocalModelsSection from "./LocalModelsSection";
import api from "../../api";

vi.mock("../../api");

const CATALOG = {
  enabled: false,
  modalities: {
    text: { source: "cloud", active_model: "qwen3.8-27b" },
    image: { source: "cloud", active_model: "qwen-image-edit-2511" },
    voice: { source: "cloud", active_model: "higgs-tts-3-4b" },
  },
  catalog: {
    text: [{ id: "qwen3.8-27b", label: "Qwen3.8 27B (Q4_K_M)", description: "d", backend: "ollama", license: "Apache-2.0", approx_resident_gb: 17, requires_attribution: false, attribution_text: "" }],
    image: [
      { id: "qwen-image-edit-2511", label: "Qwen-Image-Edit 2511 (Q4_K_M)", description: "d", backend: "comfyui", license: "Apache-2.0", approx_resident_gb: 13.2, requires_attribution: false, attribution_text: "" },
      { id: "flux2-klein-4b", label: "FLUX.2 klein 4B", description: "d", backend: "comfyui", license: "Apache-2.0", approx_resident_gb: 13, requires_attribution: false, attribution_text: "" },
    ],
    voice: [
      { id: "higgs-tts-3-4b", label: "Higgs TTS 3 (4B)", description: "d", backend: "mlx-audio", license: "Boson", approx_resident_gb: 4, requires_attribution: true, attribution_text: "Voice: Boson AI Higgs Audio" },
      { id: "kokoro-82m", label: "Kokoro 82M", description: "d", backend: "mlx-audio", license: "Apache-2.0", approx_resident_gb: 0.5, requires_attribution: false, attribution_text: "" },
    ],
  },
  daemons: {
    ollama: { healthy: true, url: "http://127.0.0.1:11434" },
    comfyui: { healthy: false, url: "http://127.0.0.1:8188" },
    "mlx-audio": { healthy: true, url: "http://127.0.0.1:8770" },
  },
};

beforeEach(() => {
  vi.mocked(api.getLocalModels).mockResolvedValue(CATALOG);
  vi.mocked(api.getSettingsKeys).mockResolvedValue({
    LOCAL_MODELS_ENABLED: { configured: true, masked: "false", source: "db" },
    LOCAL_TEXT_MODE: { configured: true, masked: "auto", source: "db" },
    LOCAL_IMAGE_MODE: { configured: true, masked: "auto", source: "db" },
    LOCAL_VOICE_MODE: { configured: true, masked: "auto", source: "db" },
    LOCAL_TEXT_MODEL: { configured: true, masked: "qwen3.8-27b", source: "db" },
    LOCAL_IMAGE_MODEL: { configured: true, masked: "qwen-image-edit-2511", source: "db" },
    LOCAL_VOICE_MODEL: { configured: true, masked: "higgs-tts-3-4b", source: "db" },
  });
  vi.mocked(api.saveSettingsKeys).mockResolvedValue({ ok: true });
});

describe("LocalModelsSection", () => {
  it("renders daemon health for each backend", async () => {
    render(<LocalModelsSection />);
    await waitFor(() => expect(screen.getByText(/ComfyUI/i)).toBeInTheDocument());
    expect(screen.getByTestId("daemon-ollama")).toHaveTextContent(/healthy/i);
    expect(screen.getByTestId("daemon-comfyui")).toHaveTextContent(/not running/i);
  });

  it("saves the master switch when toggled", async () => {
    render(<LocalModelsSection />);
    const toggle = await screen.findByRole("switch", { name: /use local models/i });
    await userEvent.click(toggle);
    await waitFor(() =>
      expect(api.saveSettingsKeys).toHaveBeenCalledWith(
        expect.objectContaining({ LOCAL_MODELS_ENABLED: "true" }),
      ),
    );
  });

  it("warns that the selected voice model requires attribution", async () => {
    render(<LocalModelsSection />);
    await waitFor(() => expect(screen.getByTestId("voice-attribution-note")).toBeInTheDocument());
    expect(screen.getByTestId("voice-attribution-note")).toHaveTextContent(/Boson AI Higgs Audio/);
  });

  it("hides the attribution note for a permissive voice model", async () => {
    render(<LocalModelsSection />);
    const select = await screen.findByLabelText(/voice model/i);
    await userEvent.selectOptions(select, "kokoro-82m");
    await waitFor(() => expect(screen.queryByTestId("voice-attribution-note")).not.toBeInTheDocument());
  });

  it("states that AI video stays on the cloud", async () => {
    render(<LocalModelsSection />);
    await waitFor(() => expect(screen.getByTestId("video-cloud-note")).toBeInTheDocument());
  });
});
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd frontend && npx vitest run src/components/settings/LocalModelsSection.test.tsx`
Expected: FAIL — module `./LocalModelsSection` not found

- [ ] **Step 3: Write minimal implementation**

Add to `frontend/src/api.ts`, beside the other settings helpers:

```ts
  getLocalModels: () => request<LocalModelsStatus>("/api/local-models"),
```

with the type declared in the same file:

```ts
export interface LocalModelInfo {
  id: string;
  label: string;
  description: string;
  backend: string;
  license: string;
  approx_resident_gb: number;
  requires_attribution: boolean;
  attribution_text: string;
}

export interface LocalModelsStatus {
  enabled: boolean;
  modalities: Record<string, { source: string; active_model: string }>;
  catalog: Record<string, LocalModelInfo[]>;
  daemons: Record<string, { healthy: boolean; url: string }>;
}
```

Create `LocalModelsSection.tsx` following `GeneralSection.tsx`'s structure: load `/api/local-models` and `/api/settings/keys` on mount, hold values in `useState`, persist through `useDebouncedAutosave` calling `api.saveSettingsKeys`. Required elements, keyed by the test's queries:

- A `role="switch"` labelled "Use local models" bound to `LOCAL_MODELS_ENABLED`.
- Three modality rows (Text / Images / Voice), each with an `auto | local | cloud` segmented control bound to `LOCAL_{MODALITY}_MODE` and a model `<select>` bound to `LOCAL_{MODALITY}_MODEL`, labelled so `getByLabelText(/voice model/i)` resolves.
- A daemon panel rendering one `data-testid={`daemon-${backend}`}` row per entry in `daemons`, with the text "Healthy" or "Not running" plus the URL.
- A `data-testid="voice-attribution-note"` block, rendered only when the selected voice model has `requires_attribution`, quoting `attribution_text` and explaining it is appended to SEO descriptions automatically and cannot be turned off.
- A `data-testid="video-cloud-note"` line stating that AI video always uses the cloud provider configured in Visuals, because local video generation is impractically slow on this hardware.
- Hint text under the master switch noting that only one local model stays in memory at a time, so local runs are slower end to end.

Styling: the section header uses the framed purple title box (`-ml-4 rounded-2xl border border-violet-500/40 bg-violet-500/5 px-4 py-3`) with `text-xl font-semibold tracking-tight`; sub-labels are `text-sm`; every interactive element gets `hover:` plus `transition-colors`.

Register the section in `SettingsPage.tsx` by adding to the nav array at :22-29:

```tsx
  { id: "local-models", label: "Local Models", description: "Run generation on local models instead of cloud APIs.", icon: Cpu, group: "AI & Generation" },
```

importing `Cpu` from `lucide-react`, and adding the render branch beside the others near :132:

```tsx
          {activeSection === "local-models" && <LocalModelsSection />}
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd frontend && npx vitest run src/components/settings/ && npm run build`
Expected: PASS, and a clean production build

- [ ] **Step 5: Commit**

```bash
git add frontend/src/components/settings/LocalModelsSection.tsx frontend/src/components/settings/LocalModelsSection.test.tsx frontend/src/components/settings/SettingsPage.tsx frontend/src/api.ts
git commit -m "Add Local Models settings section"
```

---

### Task 12: Provisioning script and launcher health checks

**Files:**
- Create: `scripts/install-local-models.sh`
- Modify: `scripts/mac-app-launcher.sh` (near the existing ollama block at :240)
- Modify: `backend/integrations/local_models.py` (correct `weights` values if the installer finds different repo ids)

**Interfaces:**
- Consumes: `REGISTRY` entries' `weights` fields.
- Produces: an installed and verified local stack; a `scripts/install-local-models.sh --check` mode that exits non-zero when anything is missing.

**This is the task where registry `weights` values are verified against reality.** `unsloth/Qwen-Image-Edit-2511-GGUF` and the Higgs MLX repos were confirmed to exist; the Ollama pull spec for Qwen3.8-27B was not. If a pull fails, find the correct repo on Hugging Face, update the registry entry, and note the change in the commit message. Do not leave a registry entry pointing at a repo that failed to resolve.

- [ ] **Step 1: Write the script**

`scripts/install-local-models.sh`, `set -euo pipefail`, idempotent, with a `--check` flag that verifies without installing. Sections, each printing what it is about to do and skipping cleanly when already satisfied:

1. **Domain allowlist.** Append any missing host to `~/.claude/apple/dangerous_allowed_domains.csv` with a dated comment, matching the existing file's format. Hosts needed: `ollama.com`, `registry.ollama.ai`, `pypi.org`, `files.pythonhosted.org`, `formulae.brew.sh`, `ghcr.io`, `objects.githubusercontent.com`. Print every line added. `huggingface.co` and its CDN hosts are already present.
2. **Ollama.** `brew install ollama` when `command -v ollama` fails; start `ollama serve` if `curl -s localhost:11434/api/tags` fails; `ollama pull` the text model's `weights`.
3. **ComfyUI.** Clone to `${HEADLESS_HERO_LOCAL_ROOT:-$HOME/.headless-hero-local}/ComfyUI`, create a venv with `uv venv`, install requirements with `uv pip install`, install the `ComfyUI-GGUF` custom node, and download the image weights into `models/unet`, `models/clip`, and `models/vae` using `huggingface-cli download`.
4. **mlx-audio.** `uv tool install --force mlx-audio --prerelease=allow`, then pre-fetch the voice model weights with `huggingface-cli download`.
5. **Verify.** Probe all three daemons, print a table of daemon, URL, status, and on-disk model sizes, and exit non-zero if any check fails.

- [ ] **Step 2: Run the script and verify it installs cleanly**

Run: `bash scripts/install-local-models.sh`
Expected: every section reports success; the final table shows three healthy daemons.

If a `brew`, `pip`, or `ollama pull` step fails because the ACC proxy still blocks a host after the allowlist edit, that is a sandbox block, not a script bug: follow `~/.claude/reference/sandbox-escape-protocol.md` — retry with `dangerouslyDisableSandbox: true`, then hand the user a single `&&`-chained one-liner for a fresh terminal. Never report the install as complete without the verification table passing.

- [ ] **Step 3: Run the check mode twice to prove idempotency**

Run: `bash scripts/install-local-models.sh && bash scripts/install-local-models.sh --check`
Expected: the second run installs nothing and exits 0.

- [ ] **Step 4: Add launcher health checks**

In `scripts/mac-app-launcher.sh`, extend the existing ollama block at :240 to also start ComfyUI and `mlx_audio.server` when `LOCAL_MODELS_ENABLED` is true in the app database and the daemon is not already answering. Follow the file's existing rules: never kill a listener the launcher does not own, log to `~/Library/Logs/HeadlessHero.log`, and surface a startup failure as a macOS notification rather than blocking the app.

Then reinstall the bundle copy, since the `.app` holds its own copy:

Run: `bash scripts/install-mac-launcher.sh`
Expected: the script reports copy plus verification success.

- [ ] **Step 5: Commit**

```bash
git add scripts/install-local-models.sh scripts/mac-app-launcher.sh backend/integrations/local_models.py
git commit -m "Add local model provisioning script and launcher daemon health checks"
```

---

### Task 13: Benchmark the image models and set the measured default

**Files:**
- Create: `scripts/benchmark-local-images.py`
- Modify: `backend/integrations/local_models.py` (`DEFAULT_MODEL_IDS["image"]`, if the measurement says so)
- Modify: `backend/api/settings.py` (`_DEFAULTS["LOCAL_IMAGE_MODEL"]`, to match)
- Create: `docs/local-models-benchmarks.md`

**Interfaces:**
- Consumes: `local_image_client.generate_image`.
- Produces: `docs/local-models-benchmarks.md` with measured numbers; possibly updated defaults.

The spec commits to choosing the image default from measurement rather than preference. This task performs that measurement.

- [ ] **Step 1: Write the benchmark script**

`scripts/benchmark-local-images.py`, run with `uv run --project backend python scripts/benchmark-local-images.py`. For each of `qwen-image-edit-2511` and `flux2-klein-4b`, it sets `LOCAL_IMAGE_MODEL`, generates the same five prompts at 1920×1080 — three plain scene prompts and two with a character reference image — records per-image wall-clock seconds, and writes the PNGs to `data/test-lab/local-benchmarks/{model_id}/`.

- [ ] **Step 2: Run the benchmark**

Run: `uv run --project backend python scripts/benchmark-local-images.py`
Expected: ten images and a printed table of per-model median and worst-case seconds per image.

- [ ] **Step 3: Judge character consistency**

Open the two character-reference outputs per model and compare them against the reference. Record in the doc whether each model preserved the character's identity, and note any failure mode plainly.

- [ ] **Step 4: Write the results and set the default**

Create `docs/local-models-benchmarks.md` with the hardware, date, prompts, per-model timings, the character-consistency judgement, and the resulting decision. Set `DEFAULT_MODEL_IDS["image"]` and `_DEFAULTS["LOCAL_IMAGE_MODEL"]` to the winner. State the rule used: prefer `qwen-image-edit-2511` unless it fails character consistency or is more than three times slower per image, in which case prefer `flux2-klein-4b`.

- [ ] **Step 5: Commit**

```bash
git add scripts/benchmark-local-images.py docs/local-models-benchmarks.md backend/integrations/local_models.py backend/api/settings.py
git commit -m "Benchmark local image models and set the measured default"
```

---

### Task 14: End-to-end local run, documentation, and Test Lab coverage

**Files:**
- Modify: `CLAUDE.md` (new Local Models section)
- Modify: `frontend/src/components/docs/DocsPage.tsx` plus a new `LocalModelsDocSection.tsx`
- Modify: `backend/api/test_lab.py` and the Test Lab UI, so a Test Lab run honours Local Mode
- Create: `docs/local-models-run-report.md`

**Interfaces:**
- Consumes: everything built above.
- Produces: the acceptance evidence for this feature.

- [ ] **Step 1: Add Test Lab coverage**

Test Lab already routes through the production pipeline functions, so local image generation flows through automatically once Task 5 lands. Verify that, and add a read-only banner to the Test Lab UI naming the active engine per modality when any modality is local, so a tester is never confused about which stack produced a result. Per project convention, Test Lab must not gain per-run local/cloud controls — it mirrors Settings.

- [ ] **Step 2: Run one complete project end to end in Local Mode**

Enable Local Mode in Settings, then generate one short project from idea through script, images, voiceover, and render. Record per-stage wall-clock timings.

Run: `npm run dev`, then drive the app.
Expected: a rendered MP4 whose images came from ComfyUI, whose narration came from the local TTS engine, and whose SEO description carries the Boson credit.

- [ ] **Step 3: Write the run report**

Create `docs/local-models-run-report.md` with the date, hardware, model ids, per-stage timings, total wall-clock, peak memory observed, and an honest list of anything that failed or degraded. If a stage failed, say so in the report and fix it before claiming the feature is done.

- [ ] **Step 4: Update the documentation**

Add a `## Local Models Mode` section to `CLAUDE.md` covering: the master switch and per-modality overrides; the registry as the single source of truth for adding a model; the single-resident memory arena and why it exists; that AI video is deliberately cloud-only; that attribution is enforced in code and not user-toggleable; and that local model identity is part of the image and render cache fingerprints.

Create `frontend/src/components/docs/LocalModelsDocSection.tsx` describing the workflow change for a user — what Local Mode changes, what stays cloud, the speed trade-off, and the credit line — and register it in `DocsPage.tsx`.

- [ ] **Step 5: Run the full suite and commit**

Run: `npm run test && cd frontend && npx vitest run && npm run build`
Expected: all green

```bash
git add CLAUDE.md frontend/src/components/docs backend/api/test_lab.py docs/local-models-run-report.md
git commit -m "Add Local Mode Test Lab coverage, docs, and end-to-end run report"
```

---

## Self-Review

**Spec coverage:**

| Spec section | Task |
|---|---|
| §2 decisions | Encoded throughout; video untouched (Global Constraints), attribution non-toggleable (Task 8), arena (Task 3) |
| §3 model selection | Task 1 registry; Task 12 verifies weights; Task 13 sets the measured image default |
| §3.2 fast tier defaults to the same model | Task 2 |
| §3.3 attribution enforced in code | Task 8 |
| §4 runtime topology | Task 3 (supervisor), Task 12 (install and launcher) |
| §4.1 memory arena | Task 3 |
| §5 settings surface and keys | Task 10 (API), Task 11 (UI) |
| §5.1 model registry | Task 1 |
| §6 text seam | Task 2 |
| §6 image seam, including the three bypassing call sites | Tasks 4 and 5 |
| §6 voice seam | Tasks 6 and 7 |
| §6 attribution in SEO | Task 8 |
| §6 video unchanged | No task touches `video_gen.py` |
| §7 cache invalidation | Task 9 |
| §8 observability and zero-cost usage | `record_usage` in Tasks 4 and 6; logging throughout |
| §9 provisioning | Task 12 |
| §10 verification | Tests in every task; Task 14 is the end-to-end gate |
| §11 documentation | Task 14 |

No spec requirement is unassigned.

**Placeholder scan:** No "TBD" or "handle edge cases" steps. The two places with genuine unknowns — the Ollama pull spec for the text model, and the ComfyUI workflow graphs — are explicit, assigned tasks with instructions for resolving them against the real installation (Tasks 12 and 4/11 respectively) rather than silent gaps.

**Type consistency:** `generate_speech` returns `tuple[bytes, list[dict]]` in Tasks 6 and 7. `generate_image` and `transform_with_references` return `str` temp paths in Tasks 4 and 5, matching `google_image_client`. `modality_source` returns `"local" | "cloud"` and is used that way in Tasks 2, 5, 7, 8, 9, 10. `active_model` returns `LocalModel` throughout; `.weights` is used for backend pull specs and `.id` for fingerprints and settings values, consistently.
