"""Shared helpers for API endpoints."""

import json

from sqlmodel import Session

from models.script import Script, ScriptContent
from pipeline.render_cache import mark_render_inputs_changed


def update_scene(
    session: Session, script_id: str, scene_id: str, **fields: object
) -> None:
    """Persist one or more field updates into a scene inside script_json."""
    record = session.get(Script, script_id)
    if not record:
        return
    content = ScriptContent.model_validate(json.loads(record.script_json))
    for seg in content.segments:
        for scene in seg.scenes:
            if scene.id == scene_id:
                for key, value in fields.items():
                    setattr(scene, key, value)
                break
    record.script_json = content.model_dump_json()
    session.add(record)
    session.commit()
    mark_render_inputs_changed(script_id)

