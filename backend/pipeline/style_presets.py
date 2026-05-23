"""Style preset generation pipeline.

Orchestrates Gemini image generation for user-defined style reference images
and persists them as files on disk plus rows in the style_presets table.

Background-job tracking mirrors backend/pipeline/render_jobs.py.
"""

from __future__ import annotations

import logging
import shutil
import threading
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path

from sqlmodel import Session

from config import DATA_DIR
from database import engine
from integrations.image_client import generate_image
from models.style_preset import StylePreset

logger = logging.getLogger(__name__)


_PRESET_IMAGE_WIDTH = 1920
_PRESET_IMAGE_HEIGHT = 1080


def _presets_dir() -> Path:
    p = DATA_DIR / "style" / "presets"
    p.mkdir(parents=True, exist_ok=True)
    return p


def generate_preset(prompt: str, name: str) -> str:
    """Generate a style preset image and persist it. Returns the new preset id.

    The user's prompt is sent to Gemini as-is. No programmatic wrapping.
    Raises RuntimeError if generation fails.
    """
    preset_id = str(uuid.uuid4())
    logger.info("Generating style preset id=%s name=%r", preset_id, name)

    tmp_path = generate_image(
        prompt=prompt,
        width=_PRESET_IMAGE_WIDTH,
        height=_PRESET_IMAGE_HEIGHT,
    )

    final_path = _presets_dir() / f"{preset_id}.png"
    shutil.move(tmp_path, str(final_path))

    with Session(engine) as session:
        row = StylePreset(
            id=preset_id,
            name=name or "Untitled",
            prompt=prompt,
            created_at=datetime.now(timezone.utc),
        )
        session.add(row)
        session.commit()

    logger.info("Style preset saved id=%s path=%s", preset_id, final_path)
    return preset_id


# --- Background job tracking ---

@dataclass
class PresetJob:
    job_id: str
    status: str = "pending"  # pending | running | completed | failed
    preset_id: str | None = None
    error: str | None = None
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))


_jobs: dict[str, PresetJob] = {}
_jobs_lock = threading.Lock()


def submit_preset_job(prompt: str, name: str) -> str:
    """Spawn a background thread to generate a preset; return job_id immediately."""
    job_id = str(uuid.uuid4())
    job = PresetJob(job_id=job_id)
    with _jobs_lock:
        _jobs[job_id] = job

    def _worker() -> None:
        with _jobs_lock:
            job.status = "running"
        try:
            preset_id = generate_preset(prompt=prompt, name=name)
            with _jobs_lock:
                job.preset_id = preset_id
                job.status = "completed"
        except Exception as exc:
            logger.error("Preset generation job %s failed: %s", job_id, exc, exc_info=True)
            with _jobs_lock:
                job.error = str(exc)[:500]
                job.status = "failed"

    threading.Thread(target=_worker, name=f"style-preset-{job_id[:8]}", daemon=True).start()
    return job_id


def get_job(job_id: str) -> PresetJob | None:
    with _jobs_lock:
        return _jobs.get(job_id)
