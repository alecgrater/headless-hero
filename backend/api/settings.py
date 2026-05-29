"""Settings endpoints for managing API keys."""

import logging
import os

from fastapi import APIRouter, Depends, HTTPException
from sqlmodel import Session, select

from database import get_session
from config import DEFAULT_CLAUDE_MODEL, DEFAULT_EXPORTS_DIR
from integrations.llm_client import ALLOWED_PROVIDERS, LLM_TASKS, VALID_OPENAI_REASONING_EFFORTS
from integrations import llm_client as _llm_client_module
from integrations import elevenlabs_client as _elevenlabs_client_module
from models.settings import AppSetting

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/settings", tags=["settings"])

VISUAL_CANVAS_COLOR_PALETTE_KEY = "VISUAL_CANVAS_COLOR_PALETTE"
SUBTITLE_COVERAGE_MODE_KEY = "SUBTITLE_COVERAGE_MODE"
SUBTITLE_STYLE_KEYS = {
    "clean": "SUBTITLE_STYLE_CLEAN_ENABLED",
    "kinetic": "SUBTITLE_STYLE_KINETIC_ENABLED",
    "burst": "SUBTITLE_STYLE_BURST_ENABLED",
}

RANGED_INTEGER_SETTINGS = {
    "LIFE_AS_A_TARGET_SCENE_SECONDS": (5, 12),
    "LIFE_AS_A_MAX_SCENE_SECONDS": (8, 18),
    "LIFE_AS_A_SINGLE_VISUAL_MAX_SECONDS": (5, 12),
}

RANGED_FLOAT_SETTINGS = {
    "ELEVENLABS_STABILITY": (0.0, 1.0),
    "ELEVENLABS_STYLE": (0.0, 1.0),
    "ELEVENLABS_SPEED": (0.7, 1.2),
}

# Keys that can be managed through the settings UI
ALLOWED_KEYS = {
    "ANTHROPIC_API_KEY",
    "OPENAI_API_KEY",
    "GOOGLE_AI_KEY",
    "ELEVENLABS_API_KEY",
    "ELEVENLABS_TTS_MODEL",
    "ELEVENLABS_STABILITY",
    "ELEVENLABS_STYLE",
    "ELEVENLABS_SPEED",
    "GOOGLE_CLIENT_ID",
    "GOOGLE_CLIENT_SECRET",
    "DOWNLOADS_DIR",
    "IMAGE_PROVIDER",
    "AI_VIDEO_ENABLED",
    "AI_VIDEO_PROVIDER",
    "AI_VIDEO_SCENES_PER_SEGMENT",
    "LIFE_AS_A_SCENE_CHUNKING_ENABLED",
    "LIFE_AS_A_TARGET_SCENE_SECONDS",
    "LIFE_AS_A_MAX_SCENE_SECONDS",
    "LIFE_AS_A_SINGLE_VISUAL_MAX_SECONDS",
    "RUNWAYML_API_SECRET",
    "FAL_API_KEY",
    "FAL_VIDEO_MODEL",
    "IMAGE_SCRAPER_FALLBACK_ENABLED",
    "IMAGE_RATE_LIMIT_MS",
    "SCRIPT_MODEL",
    "YOUTUBE_API_KEY",
    "NEWS_API_KEY",
    "TIKTOK_CLIENT_KEY",
    "TIKTOK_CLIENT_SECRET",
    "META_APP_ID",
    "META_APP_SECRET",
    "AUDIO_FILTER_HIGHPASS",
    "AUDIO_FILTER_NOISE_REDUCTION",
    "AUDIO_FILTER_COMPRESSOR",
    "LLM_PROVIDER",
    "QWEN_MODEL",
    "HOOK_REFINEMENT_ENABLED",
    "SHOW_SPEED_RENDER_BUTTON",
    "ELI_ENABLED_DEFAULT",
    "STYLE_PRESET_ENABLED_DEFAULT",
    "ACTIVE_STYLE_PRESET_ID",
    SUBTITLE_COVERAGE_MODE_KEY,
    *SUBTITLE_STYLE_KEYS.values(),
    VISUAL_CANVAS_COLOR_PALETTE_KEY,
}

for _task_id, _task_config in LLM_TASKS.items():
    ALLOWED_KEYS.add(_task_config["provider_key"])
    ALLOWED_KEYS.add(_task_config["model_key"])
    ALLOWED_KEYS.add(f"OPENAI_REASONING_EFFORT_{_task_id.upper()}")

# Keys that should NOT be masked (non-secret settings)
_PLAINTEXT_KEYS = {
    "DOWNLOADS_DIR",
    "IMAGE_PROVIDER",
    "AI_VIDEO_ENABLED",
    "AI_VIDEO_PROVIDER",
    "AI_VIDEO_SCENES_PER_SEGMENT",
    "LIFE_AS_A_SCENE_CHUNKING_ENABLED",
    "LIFE_AS_A_TARGET_SCENE_SECONDS",
    "LIFE_AS_A_MAX_SCENE_SECONDS",
    "LIFE_AS_A_SINGLE_VISUAL_MAX_SECONDS",
    "FAL_VIDEO_MODEL",
    "IMAGE_SCRAPER_FALLBACK_ENABLED",
    "IMAGE_RATE_LIMIT_MS",
    "SCRIPT_MODEL",
    "AUDIO_FILTER_HIGHPASS",
    "AUDIO_FILTER_NOISE_REDUCTION",
    "AUDIO_FILTER_COMPRESSOR",
    "ELEVENLABS_TTS_MODEL",
    "ELEVENLABS_STABILITY",
    "ELEVENLABS_STYLE",
    "ELEVENLABS_SPEED",
    "LLM_PROVIDER",
    "QWEN_MODEL",
    "HOOK_REFINEMENT_ENABLED",
    "SHOW_SPEED_RENDER_BUTTON",
    "ELI_ENABLED_DEFAULT",
    "STYLE_PRESET_ENABLED_DEFAULT",
    "ACTIVE_STYLE_PRESET_ID",
    SUBTITLE_COVERAGE_MODE_KEY,
    *SUBTITLE_STYLE_KEYS.values(),
    VISUAL_CANVAS_COLOR_PALETTE_KEY,
}

for _task_id, _task_config in LLM_TASKS.items():
    _PLAINTEXT_KEYS.add(_task_config["provider_key"])
    _PLAINTEXT_KEYS.add(_task_config["model_key"])
    _PLAINTEXT_KEYS.add(f"OPENAI_REASONING_EFFORT_{_task_id.upper()}")

# Default values for settings that have sensible defaults
_DEFAULTS: dict[str, str] = {
    "DOWNLOADS_DIR": str(DEFAULT_EXPORTS_DIR),
    "IMAGE_RATE_LIMIT_MS": "10000",  # 6 req/min to stay under free-tier limits
    "IMAGE_SCRAPER_FALLBACK_ENABLED": "false",
    "AI_VIDEO_ENABLED": "false",
    "AI_VIDEO_PROVIDER": "runway",
    "AI_VIDEO_SCENES_PER_SEGMENT": "2",
    "LIFE_AS_A_SCENE_CHUNKING_ENABLED": "true",
    "LIFE_AS_A_TARGET_SCENE_SECONDS": "8",
    "LIFE_AS_A_MAX_SCENE_SECONDS": "12",
    "LIFE_AS_A_SINGLE_VISUAL_MAX_SECONDS": "8",
    "FAL_VIDEO_MODEL": "fal-ai/wan/v2.2-a14b/image-to-video/turbo",
    "SCRIPT_MODEL": DEFAULT_CLAUDE_MODEL,
    "AUDIO_FILTER_HIGHPASS": "true",
    "AUDIO_FILTER_NOISE_REDUCTION": "true",
    "AUDIO_FILTER_COMPRESSOR": "true",
    "ELEVENLABS_TTS_MODEL": "eleven_multilingual_v2",
    "ELEVENLABS_STABILITY": "0.5",
    "ELEVENLABS_STYLE": "0.0",
    "ELEVENLABS_SPEED": "1.0",
    "LLM_PROVIDER": "ollama",
    "QWEN_MODEL": "qwen3:14b",
    "HOOK_REFINEMENT_ENABLED": "true",
    "SHOW_SPEED_RENDER_BUTTON": "true",
    "ELI_ENABLED_DEFAULT": "false",
    "STYLE_PRESET_ENABLED_DEFAULT": "true",
    "ACTIVE_STYLE_PRESET_ID": "",
    SUBTITLE_COVERAGE_MODE_KEY: "all",
    "SUBTITLE_STYLE_CLEAN_ENABLED": "true",
    "SUBTITLE_STYLE_KINETIC_ENABLED": "true",
    "SUBTITLE_STYLE_BURST_ENABLED": "true",
    VISUAL_CANVAS_COLOR_PALETTE_KEY: '["#F6C54A"]',
}

for _task_id, _task_config in LLM_TASKS.items():
    _default_provider = _task_config["default_provider"]
    _DEFAULTS.setdefault(_task_config["provider_key"], _default_provider)
    _DEFAULTS.setdefault(_task_config["model_key"], _task_config[f"default_{_default_provider}_model"] if _default_provider != "ollama" else "qwen3:14b")
    if _task_config.get("openai_reasoning_effort"):
        _DEFAULTS.setdefault(
            f"OPENAI_REASONING_EFFORT_{_task_id.upper()}",
            _task_config["openai_reasoning_effort"],
        )


def _mask(value: str) -> str:
    """Mask an API key for display: show first 6 and last 4 chars."""
    if len(value) <= 12:
        return "*" * len(value)
    return value[:6] + "..." + value[-4:]


def load_keys_into_env(session: Session) -> None:
    """Load all saved API keys from DB into os.environ, plus defaults for any
    allowed keys that don't have a DB row yet (so e.g. LLM_PROVIDER='ollama'
    is active out of the box without the user clicking Save)."""
    settings = session.exec(select(AppSetting)).all()
    saved = {s.key: s.value for s in settings if s.key in ALLOWED_KEYS}

    loaded: list[str] = []
    for key, value in saved.items():
        if value:
            os.environ[key] = value
            loaded.append(key)

    applied_defaults: list[str] = []
    for key, default in _DEFAULTS.items():
        if key in saved and saved[key]:
            continue
        if os.environ.get(key):
            continue
        os.environ[key] = default
        applied_defaults.append(key)

    if loaded:
        logger.info("Loaded %d API keys from DB into env: %s", len(loaded), ", ".join(loaded))
    if applied_defaults:
        logger.info("Applied %d default values for unset keys: %s", len(applied_defaults), ", ".join(applied_defaults))


def _validate_ranged_integer_settings(keys: dict[str, str]) -> None:
    for key, (minimum, maximum) in RANGED_INTEGER_SETTINGS.items():
        if key not in keys:
            continue
        raw_value = (keys[key] or "").strip()
        try:
            value = int(raw_value)
        except ValueError:
            raise HTTPException(
                status_code=400,
                detail=f"Invalid {key}: must be an integer from {minimum} to {maximum}.",
            )
        if value < minimum or value > maximum:
            raise HTTPException(
                status_code=400,
                detail=f"Invalid {key}: must be an integer from {minimum} to {maximum}.",
            )
        keys[key] = str(value)


def _validate_ranged_float_settings(keys: dict[str, str]) -> None:
    for key, (minimum, maximum) in RANGED_FLOAT_SETTINGS.items():
        if key not in keys:
            continue
        raw_value = (keys[key] or "").strip()
        try:
            value = float(raw_value)
        except ValueError:
            raise HTTPException(
                status_code=400,
                detail=f"Invalid {key}: must be a number from {minimum:g} to {maximum:g}.",
            )
        if value < minimum or value > maximum:
            raise HTTPException(
                status_code=400,
                detail=f"Invalid {key}: must be a number from {minimum:g} to {maximum:g}.",
            )
        keys[key] = f"{value:g}"


@router.get("/keys")
async def get_keys(session: Session = Depends(get_session)):
    """Return which API keys are configured (masked values)."""
    settings = session.exec(select(AppSetting)).all()
    saved = {s.key: s.value for s in settings if s.key in ALLOWED_KEYS}

    result: dict[str, dict[str, str | bool]] = {}
    for key in ALLOWED_KEYS:
        value = saved.get(key, "") or os.environ.get(key, "") or _DEFAULTS.get(key, "")
        result[key] = {
            "configured": bool(value),
            "masked": value if key in _PLAINTEXT_KEYS else (_mask(value) if value else ""),
            "source": "db" if key in saved and saved[key] else ("env" if value else "none"),
        }
    return result


@router.put("/keys")
async def save_keys(
    keys: dict[str, str],
    session: Session = Depends(get_session),
):
    """Save API keys to DB and set them in os.environ."""
    logger.info("Saving settings keys: %s", list(keys.keys()))

    # Validate provider settings before any writes.
    provider_keys = {"LLM_PROVIDER", *(task["provider_key"] for task in LLM_TASKS.values())}
    reasoning_keys = {f"OPENAI_REASONING_EFFORT_{task_id.upper()}" for task_id in LLM_TASKS}
    if "AI_VIDEO_PROVIDER" in keys:
        ai_video_provider = (keys["AI_VIDEO_PROVIDER"] or "").strip().lower()
        if ai_video_provider and ai_video_provider not in {"runway", "fal"}:
            raise HTTPException(
                status_code=400,
                detail="Invalid AI_VIDEO_PROVIDER: "
                f"{ai_video_provider!r}. Must be one of ['fal', 'runway'].",
            )
        keys["AI_VIDEO_PROVIDER"] = ai_video_provider
    if "AI_VIDEO_SCENES_PER_SEGMENT" in keys:
        raw_count = (keys["AI_VIDEO_SCENES_PER_SEGMENT"] or "").strip()
        try:
            scenes_per_segment = int(raw_count)
        except ValueError:
            raise HTTPException(
                status_code=400,
                detail="Invalid AI_VIDEO_SCENES_PER_SEGMENT: must be an integer from 0 to 5.",
            )
        if scenes_per_segment < 0 or scenes_per_segment > 5:
            raise HTTPException(
                status_code=400,
                detail="Invalid AI_VIDEO_SCENES_PER_SEGMENT: must be an integer from 0 to 5.",
            )
        keys["AI_VIDEO_SCENES_PER_SEGMENT"] = str(scenes_per_segment)
    if "ELEVENLABS_TTS_MODEL" in keys:
        tts_model = (keys["ELEVENLABS_TTS_MODEL"] or "").strip()
        if tts_model and tts_model not in {"eleven_multilingual_v2", "eleven_v3"}:
            raise HTTPException(
                status_code=400,
                detail="Invalid ELEVENLABS_TTS_MODEL: must be 'eleven_multilingual_v2' or 'eleven_v3'.",
            )
        keys["ELEVENLABS_TTS_MODEL"] = tts_model
    if SUBTITLE_COVERAGE_MODE_KEY in keys:
        coverage_mode = (keys[SUBTITLE_COVERAGE_MODE_KEY] or "").strip().lower()
        if coverage_mode and coverage_mode not in {"all", "punchy"}:
            raise HTTPException(
                status_code=400,
                detail="Invalid SUBTITLE_COVERAGE_MODE: must be 'all' or 'punchy'.",
            )
        keys[SUBTITLE_COVERAGE_MODE_KEY] = coverage_mode or "all"
    for style_key in SUBTITLE_STYLE_KEYS.values():
        if style_key in keys:
            keys[style_key] = "false" if (keys[style_key] or "").strip().lower() in {"", "0", "false", "no", "off"} else "true"
    _validate_ranged_integer_settings(keys)
    _validate_ranged_float_settings(keys)
    for provider_key in provider_keys.intersection(keys):
        provider = (keys[provider_key] or "").strip().lower()
        if provider and provider not in ALLOWED_PROVIDERS:
            raise HTTPException(
                status_code=400,
                detail=f"Invalid {provider_key}: {provider!r}. Must be one of {sorted(ALLOWED_PROVIDERS)}.",
            )
        keys[provider_key] = provider
    for reasoning_key in reasoning_keys.intersection(keys):
        effort = (keys[reasoning_key] or "").strip().lower()
        if effort and effort not in VALID_OPENAI_REASONING_EFFORTS:
            raise HTTPException(
                status_code=400,
                detail=f"Invalid {reasoning_key}: {effort!r}. Must be one of {sorted(VALID_OPENAI_REASONING_EFFORTS)}.",
            )
        keys[reasoning_key] = effort

    saved_keys: list[str] = []
    skipped_keys: list[str] = []
    llm_credential_changed = False
    elevenlabs_credential_changed = False

    for key, value in keys.items():
        if key not in ALLOWED_KEYS:
            skipped_keys.append(key)
            continue
        # Upsert
        existing = session.get(AppSetting, key)
        if existing:
            existing.value = value
            session.add(existing)
        else:
            session.add(AppSetting(key=key, value=value))
        # Also set in env immediately
        if value:
            os.environ[key] = value
        elif key in os.environ:
            del os.environ[key]
        saved_keys.append(key)
        if key in {"ANTHROPIC_API_KEY", "OPENAI_API_KEY"}:
            llm_credential_changed = True
        elif key == "ELEVENLABS_API_KEY":
            elevenlabs_credential_changed = True

    session.commit()
    # Invalidate cached SDK clients so they pick up the new credentials
    # without a backend restart.
    if llm_credential_changed:
        _llm_client_module.reset_clients()
    if elevenlabs_credential_changed:
        _elevenlabs_client_module.reset_clients()
    logger.info("Settings saved: %s, skipped: %s", saved_keys, skipped_keys)
    return {"status": "ok", "saved": saved_keys, "skipped": skipped_keys}
