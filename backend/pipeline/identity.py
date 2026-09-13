"""Portable visual identity snapshot.

Style presets, preset-scoped main characters, the brand profile, and non-secret
app settings live partly in SQLite and partly on disk. The on-disk assets are
tracked in git directly (see the `data/` block in .gitignore); the DB rows
travel in `data/identity.json`, written through on every identity mutation and
seeded back on startup so a fresh clone can generate a video immediately.

Secrets never enter the snapshot. `app_settings` mixes ~14 live credentials with
the settings worth syncing, and this repo is public, so setting export is a
strict allowlist: anything not named here is excluded, which makes a credential
added later safe by default.
"""

from __future__ import annotations

import json
import logging
import os
import tempfile
import threading
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from sqlmodel import Session, select

from config import DATA_DIR
from models.brand import BrandProfile
from models.settings import AppSetting
from models.style_preset import StylePreset
from models.style_preset_character import StylePresetCharacter

logger = logging.getLogger(__name__)

SNAPSHOT_VERSION = 1

# Serializes snapshot writes; preset generation writes from a background thread.
_WRITE_LOCK = threading.Lock()


def identity_path() -> Path:
    return DATA_DIR / "identity.json"


# --- Settings allowlist ---
#
# Exact keys first. Note GOOGLE_CLIENT_ID is a credential while
# ACTIVE_STYLE_PRESET_ID is not, and both end in _ID — which is why membership is
# explicit rather than pattern-inferred.
_EXPORTED_KEYS: frozenset[str] = frozenset(
    {
        "ACTIVE_STYLE_PRESET_ID",
        "LLM_PROVIDER",
        # Subtitles
        "SUBTITLE_COVERAGE_MODE",
        "SUBTITLE_STYLE_BURST_ENABLED",
        "SUBTITLE_STYLE_CLEAN_ENABLED",
        "SUBTITLE_STYLE_KINETIC_ENABLED",
        # Voice
        "ELEVENLABS_STABILITY",
        "ELEVENLABS_STYLE",
        "ELEVENLABS_SPEED",
        # Imagery
        "IMAGE_PROVIDER",
        "IMAGE_RATE_LIMIT_MS",
        "IMAGE_SCRAPER_FALLBACK_ENABLED",
        "GOOGLE_IMAGE_BATCH_ENABLED",
        "VISUAL_CANVAS_COLOR_PALETTE",
        "REPLICATE_OUTPUT_FORMAT",
        "REPLICATE_PROMPT_UPSAMPLING",
        "REPLICATE_SAFETY_TOLERANCE",
        # Feature defaults
        "ELI_ENABLED_DEFAULT",
        "STYLE_PRESET_ENABLED_DEFAULT",
        "HOOK_REFINEMENT_ENABLED",
        "SHOW_SPEED_RENDER_BUTTON",
        "AI_VIDEO_ENABLED",
        "AI_VIDEO_PROVIDER",
        "AI_VIDEO_SCENES_PER_SEGMENT",
        "LIFE_AS_A_MAX_SCENE_SECONDS",
        "LIFE_AS_A_SCENE_CHUNKING_ENABLED",
        "LIFE_AS_A_SINGLE_VISUAL_MAX_SECONDS",
        "LIFE_AS_A_TARGET_SCENE_SECONDS",
    }
)

_EXPORTED_PREFIXES: tuple[str, ...] = (
    "ACTIVE_STYLE_PRESET_CHARACTER_ID_",
    "OPENAI_REASONING_EFFORT_",
)

_EXPORTED_SUFFIXES: tuple[str, ...] = (
    "_LLM_PROVIDER",
    "_MODEL",
)

# Final safety net. The allowlist above is the real boundary; this catches a
# credential accidentally added to it during a future edit.
_SECRET_MARKERS: tuple[str, ...] = ("KEY", "SECRET", "TOKEN", "PASSWORD", "CREDENTIAL")

# Settings that describe this machine, not the visual identity. Local Models
# Mode depends on weights and daemons installed here, so carrying it to another
# machine would point generation at models that do not exist there. Checked
# before the allowlist so the _MODEL suffix cannot pull LOCAL_*_MODEL through.
_MACHINE_SPECIFIC_PREFIXES: tuple[str, ...] = ("LOCAL_",)


def is_exportable_setting(key: str) -> bool:
    """True when an app_settings key may be committed to a public repo."""
    if any(marker in key.upper() for marker in _SECRET_MARKERS):
        return False
    if key.startswith(_MACHINE_SPECIFIC_PREFIXES):
        return False
    if key in _EXPORTED_KEYS:
        return True
    if key.startswith(_EXPORTED_PREFIXES):
        return True
    return key.endswith(_EXPORTED_SUFFIXES)


# --- Building the snapshot ---

def _iso_utc(value: datetime) -> str:
    """Serialize with an explicit UTC offset.

    SQLite columns are naive, so a datetime written as aware comes back naive.
    Timestamps in this project are always UTC, so treat a naive value as UTC
    rather than letting the committed snapshot carry ambiguous strings.
    """
    if value.tzinfo is None:
        value = value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc).isoformat()


def build_snapshot(session: Session) -> dict[str, Any]:
    """Serialize the identity rows currently in the database."""
    presets = session.exec(select(StylePreset)).all()
    characters = session.exec(select(StylePresetCharacter)).all()
    brand = session.exec(select(BrandProfile)).first()
    settings = session.exec(select(AppSetting)).all()

    return {
        "version": SNAPSHOT_VERSION,
        "style_presets": [
            {
                "id": p.id,
                "name": p.name,
                "prompt": p.prompt,
                "created_at": _iso_utc(p.created_at),
            }
            for p in sorted(presets, key=lambda p: p.id)
        ],
        "style_preset_characters": [
            {
                "id": c.id,
                "style_preset_id": c.style_preset_id,
                "name": c.name,
                "appearance": c.appearance,
                "vibe": c.vibe,
                "reference_image_url": c.reference_image_url,
                "cutout_image_url": c.cutout_image_url,
                "created_at": _iso_utc(c.created_at),
            }
            for c in sorted(characters, key=lambda c: c.id)
        ],
        "brand_profile": (
            {
                "name": brand.name,
                "voice_id": brand.voice_id,
                "youtube_channel_id": brand.youtube_channel_id,
                "eli_position_json": brand.eli_position_json,
            }
            if brand
            else None
        ),
        "settings": {
            s.key: s.value
            for s in sorted(settings, key=lambda s: s.key)
            if is_exportable_setting(s.key)
        },
    }


def write_snapshot(session: Session | None = None) -> None:
    """Rewrite data/identity.json from the database.

    Best-effort: an identity mutation must not fail because the snapshot could
    not be written. Never call this from startup seeding — a partially seeded
    database would overwrite a good snapshot.

    Serialized, because preset generation calls this from a background thread
    while request threads can be writing too. Two unsynchronized writers
    sharing one temp path could interleave and publish a corrupt file into a
    tracked, public artifact.
    """
    try:
        if session is not None:
            payload = build_snapshot(session)
        else:
            from database import engine

            with Session(engine) as own_session:
                payload = build_snapshot(own_session)

        path = identity_path()
        path.parent.mkdir(parents=True, exist_ok=True)
        body = json.dumps(payload, indent=2) + "\n"

        with _WRITE_LOCK:
            # Unique temp name so concurrent writers never share a handle and
            # a crashed writer can't leave one the next writer collides with.
            fd, tmp_name = tempfile.mkstemp(dir=path.parent, suffix=".json.tmp")
            tmp = Path(tmp_name)
            try:
                with os.fdopen(fd, "w", encoding="utf-8") as handle:
                    handle.write(body)
                # mkstemp creates 0600; this file is committed and read back.
                tmp.chmod(0o644)
                tmp.replace(path)
            except BaseException:
                tmp.unlink(missing_ok=True)
                raise
        logger.debug("Wrote identity snapshot to %s", path)
    except Exception:
        logger.warning("Failed to write identity snapshot", exc_info=True)


# --- Seeding from the snapshot ---

def _parse_datetime(raw: Any) -> datetime | None:
    if not isinstance(raw, str) or not raw:
        return None
    try:
        return datetime.fromisoformat(raw)
    except ValueError:
        return None


def read_snapshot() -> dict[str, Any] | None:
    """Load data/identity.json, or None when absent or unusable."""
    path = identity_path()
    if not path.exists():
        return None
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        logger.warning("Could not read identity snapshot at %s", path, exc_info=True)
        return None

    if not isinstance(payload, dict):
        logger.warning("Identity snapshot is not an object; ignoring")
        return None

    version = payload.get("version")
    if version != SNAPSHOT_VERSION:
        logger.warning(
            "Identity snapshot version %r is not supported (expected %d); ignoring",
            version,
            SNAPSHOT_VERSION,
        )
        return None

    return payload


def seed_from_snapshot(session: Session) -> None:
    """Apply data/identity.json to the database.

    The snapshot wins on conflict, so pulling another machine's identity takes
    effect on the next start. Seeding is non-destructive: rows present locally
    but absent from the snapshot are left alone.
    """
    payload = read_snapshot()
    if payload is None:
        return

    seeded_presets = 0
    for entry in payload.get("style_presets") or []:
        preset_id = entry.get("id")
        if not preset_id:
            continue
        row = session.get(StylePreset, preset_id)
        if row is None:
            row = StylePreset(id=preset_id)
        row.name = entry.get("name", "")
        row.prompt = entry.get("prompt", "")
        created = _parse_datetime(entry.get("created_at"))
        if created is not None:
            row.created_at = created
        session.add(row)
        seeded_presets += 1

    seeded_characters = 0
    for entry in payload.get("style_preset_characters") or []:
        character_id = entry.get("id")
        if not character_id:
            continue
        row = session.get(StylePresetCharacter, character_id)
        if row is None:
            row = StylePresetCharacter(
                id=character_id,
                style_preset_id=entry.get("style_preset_id", ""),
            )
        row.style_preset_id = entry.get("style_preset_id", "")
        row.name = entry.get("name", "")
        row.appearance = entry.get("appearance", "")
        row.vibe = entry.get("vibe", "")
        row.reference_image_url = entry.get("reference_image_url", "")
        row.cutout_image_url = entry.get("cutout_image_url", "")
        created = _parse_datetime(entry.get("created_at"))
        if created is not None:
            row.created_at = created
        session.add(row)
        seeded_characters += 1

    brand_entry = payload.get("brand_profile")
    if isinstance(brand_entry, dict):
        brand = session.exec(select(BrandProfile)).first()
        if brand is not None:
            # Empty values are skipped rather than applied: a snapshot taken
            # before a field was filled in would otherwise blank the name
            # ensure_default_brand() just created on a fresh clone.
            for field in ("name", "voice_id", "youtube_channel_id", "eli_position_json"):
                value = brand_entry.get(field)
                if isinstance(value, str) and value:
                    setattr(brand, field, value)
            session.add(brand)

    seeded_settings = 0
    for key, value in (payload.get("settings") or {}).items():
        if not is_exportable_setting(key):
            logger.warning("Ignoring non-exportable setting %r in identity snapshot", key)
            continue
        row = session.get(AppSetting, key)
        if row is None:
            row = AppSetting(key=key, value=str(value))
        else:
            row.value = str(value)
        session.add(row)
        seeded_settings += 1

    session.commit()
    logger.info(
        "Seeded identity: %d presets, %d characters, %d settings",
        seeded_presets,
        seeded_characters,
        seeded_settings,
    )
