"""Shared short-form hook detection/persistence helpers."""

import json
import logging

from sqlmodel import Session

from models.script import Script, ScriptContent
from pipeline.hook_detector import detect_hook_scene_count

logger = logging.getLogger(__name__)


def ensure_short_form_hook_scene_count(
    session: Session,
    script_id: str,
    content: ScriptContent | None = None,
    record: Script | None = None,
) -> ScriptContent:
    """Populate hook_scene_count before short-form render/export/SEO work."""
    record = record or session.get(Script, script_id)
    if not record:
        raise RuntimeError("Script not found")

    content = content or ScriptContent.model_validate(json.loads(record.script_json))
    if content.hook_scene_count is not None:
        return content

    count = detect_hook_scene_count(content, script_id=script_id)
    content.hook_scene_count = count
    if count > 0:
        content.short_form_seo_metadata = None

    record.script_json = content.model_dump_json()
    session.add(record)
    session.commit()
    logger.info("Persisted hook_scene_count=%d for script %s", count, script_id)
    return content
