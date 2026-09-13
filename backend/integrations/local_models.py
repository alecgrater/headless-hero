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
        weights="hf.co/unsloth/Qwen3.8-27B-GGUF:UD-Q4_K_M",
        approx_resident_gb=16.5,
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
        description=(
            "20B editor tuned for character consistency across references. "
            "Slower, highest fidelity to your character."
        ),
    ),
    "flux2-klein-4b": LocalModel(
        id="flux2-klein-4b",
        modality="image",
        backend="comfyui",
        weights="black-forest-labs/FLUX.2-klein-4B",
        approx_resident_gb=13.0,
        license="Apache-2.0",
        label="FLUX.2 klein 4B",
        description=(
            "4-step distilled multi-reference model. Much faster per image, "
            "less character lock-in."
        ),
    ),
    "higgs-tts-3-4b": LocalModel(
        id="higgs-tts-3-4b",
        modality="voice",
        backend="mlx-audio",
        weights="whitelabel/mlx-q6-higgs-tts-3-4b",
        approx_resident_gb=4.0,
        license="Boson research/non-commercial + Creator Use Grant",
        label="Higgs TTS 3 (4B)",
        description=(
            "Expressive narration with zero-shot cloning. Its licence requires "
            "crediting Boson AI, which is appended to SEO descriptions automatically."
        ),
        requires_attribution=True,
        attribution_text="Voice: Boson AI Higgs Audio",
    ),
    "kokoro-82m": LocalModel(
        id="kokoro-82m",
        modality="voice",
        backend="mlx-audio",
        weights="mlx-community/Kokoro-82M-bf16",
        approx_resident_gb=0.5,
        license="Apache-2.0",
        label="Kokoro 82M",
        description="Very fast, clean, neutral narration with fixed voices. No attribution required.",
    ),
    "chatterbox": LocalModel(
        id="chatterbox",
        modality="voice",
        backend="mlx-audio",
        weights="mlx-community/Chatterbox-TTS-8bit",
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
