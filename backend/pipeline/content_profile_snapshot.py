"""Build a GitHub Actions-friendly input snapshot for remote profile refresh."""

from __future__ import annotations

import json
import logging
from datetime import datetime, timezone
from typing import Any

from sqlmodel import Session, select

from database import engine
from models.script import Script, ScriptContent

logger = logging.getLogger(__name__)


def _scene_payload(scene: Any) -> dict[str, Any]:
    return {
        "id": scene.id,
        "narration": scene.narration,
        "visual_prompt": scene.visual_prompt,
        "visual_mode": scene.visual_mode,
        "is_title_card": scene.is_title_card,
        "caption_text": scene.caption_text,
        "caption_emphasis": scene.caption_emphasis,
        "stat_value": scene.stat_value,
        "stat_label": scene.stat_label,
    }


def _script_payload(script: Script, content: ScriptContent) -> dict[str, Any]:
    return {
        "id": script.id,
        "title": script.topic_title or content.title,
        "script_title": content.title,
        "format_id": script.format_id or content.format_id,
        "topic_description": script.topic_description,
        "created_at": script.created_at.isoformat(),
        "segments": [
            {
                "name": segment.name,
                "short_name": segment.short_name,
                "scenes": [_scene_payload(scene) for scene in segment.scenes],
            }
            for segment in content.segments
        ],
    }


def build_content_profile_input_snapshot(now: datetime | None = None) -> dict[str, Any]:
    """Return script inputs that a remote GitHub Action can analyze without SQLite."""
    generated_at = now or datetime.now(timezone.utc)
    scripts: list[dict[str, Any]] = []

    with Session(engine) as session:
        records = session.exec(
            select(Script).where(Script.is_test_lab == False).order_by(Script.created_at.asc())  # noqa: E712
        ).all()
        for record in records:
            try:
                content = ScriptContent.model_validate(json.loads(record.script_json))
            except Exception:
                logger.debug("Skipping unparseable script %s in remote profile snapshot", record.id)
                continue
            scripts.append(_script_payload(record, content))

    return {
        "version": 1,
        "generated_at": generated_at.isoformat(),
        "source": "headless-hero-content-profile-input",
        "script_count": len(scripts),
        "scripts": scripts,
    }
