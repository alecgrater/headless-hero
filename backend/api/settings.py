"""Settings endpoints for managing API keys."""

import os

from fastapi import APIRouter, Depends
from sqlmodel import Session, select

from api.database import get_session
from models.settings import AppSetting

router = APIRouter(prefix="/api/settings", tags=["settings"])

# Keys that can be managed through the settings UI
ALLOWED_KEYS = {
    "ANTHROPIC_API_KEY",
    "GOOGLE_AI_KEY",
    "ELEVENLABS_API_KEY",
    "GOOGLE_CLIENT_ID",
    "GOOGLE_CLIENT_SECRET",
    "DOWNLOADS_DIR",
    "REPLICATE_API_TOKEN",
    "IMAGE_PROVIDER",
}

# Keys that should NOT be masked (non-secret settings)
_PLAINTEXT_KEYS = {"DOWNLOADS_DIR", "IMAGE_PROVIDER"}


def _mask(value: str) -> str:
    """Mask an API key for display: show first 6 and last 4 chars."""
    if len(value) <= 12:
        return "*" * len(value)
    return value[:6] + "..." + value[-4:]


def load_keys_into_env(session: Session) -> None:
    """Load all saved API keys from DB into os.environ."""
    settings = session.exec(select(AppSetting)).all()
    for s in settings:
        if s.key in ALLOWED_KEYS and s.value:
            os.environ[s.key] = s.value


@router.get("/keys")
async def get_keys(session: Session = Depends(get_session)):
    """Return which API keys are configured (masked values)."""
    settings = session.exec(select(AppSetting)).all()
    saved = {s.key: s.value for s in settings if s.key in ALLOWED_KEYS}

    result: dict[str, dict[str, str | bool]] = {}
    for key in ALLOWED_KEYS:
        value = saved.get(key, "") or os.environ.get(key, "")
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
    saved_keys: list[str] = []
    skipped_keys: list[str] = []

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

    session.commit()
    return {"status": "ok", "saved": saved_keys, "skipped": skipped_keys}
