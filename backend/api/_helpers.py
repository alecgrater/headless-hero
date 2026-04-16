"""Shared helpers for API endpoints."""

import json
from pathlib import Path

from sqlmodel import Session

from models.script import Scene, Script, ScriptContent

_PROMPTS_DIR = Path(__file__).resolve().parent.parent / "prompts"


def read_prompt(name: str) -> str:
    """Read a prompt file from the backend/prompts/ directory. Returns '' if missing."""
    p = _PROMPTS_DIR / name
    return p.read_text() if p.exists() else ""


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


def find_scene_in_content(content: ScriptContent, scene_id: str) -> Scene:
    """Find a scene by ID across all segments.

    Raises RuntimeError if the scene is not found.
    """
    for seg in content.segments:
        for sc in seg.scenes:
            if sc.id == scene_id:
                return sc
    raise RuntimeError(f"Scene {scene_id} not found in content")
