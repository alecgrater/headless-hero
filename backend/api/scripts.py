"""Endpoints for AI-powered script generation."""

import json
import logging
import shutil
import time
from pathlib import Path

from datetime import datetime, timezone, timedelta

from fastapi import APIRouter, Depends, HTTPException
from sqlmodel import Session, select

from database import get_default_brand_id, get_session
from models.brand import BrandProfile
from models.generation_duration import GenerationDuration
from models.script import (
    GenerateScriptRequest,
    GenerateScriptResponse,
    RefineSceneRequest,
    RefineSceneResponse,
    Script,
    ScriptContent,
    ScriptRead,
    ScriptSummary,
    UpdateScriptRequest,
)
from pipeline.refine import refine_scene
from pipeline.scriptwriter import generate_script

DATA_DIR = Path(__file__).resolve().parent.parent.parent / "data"

_PROMPTS_DIR = Path(__file__).resolve().parent.parent / "prompts"
_VISUAL_STYLE = (_PROMPTS_DIR / "visual_style.md").read_text() if (_PROMPTS_DIR / "visual_style.md").exists() else ""
_CHARACTER = (_PROMPTS_DIR / "character.md").read_text() if (_PROMPTS_DIR / "character.md").exists() else ""

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/scripts", tags=["scripts"])


def _build_summary(record: Script) -> ScriptSummary:
    """Build a ScriptSummary from a Script record."""
    content = ScriptContent.model_validate(json.loads(record.script_json))
    scenes = [s for seg in content.segments for s in seg.scenes]
    image_count = sum(1 for s in scenes if s.image_url)
    audio_count = sum(1 for s in scenes if s.audio_url)

    renders_dir = DATA_DIR / "projects" / record.id / "renders"
    has_renders = renders_dir.exists() and any(renders_dir.iterdir())

    # Use first scene with an image as thumbnail
    thumbnail_url = ""
    for s in scenes:
        if s.image_url:
            thumbnail_url = s.image_url
            break

    # Derive status
    if has_renders:
        status = "exported"
    elif audio_count > 0:
        status = "audio"
    elif image_count > 0:
        status = "images"
    else:
        status = "script"

    return ScriptSummary(
        id=record.id,
        brand_id=record.brand_id,
        topic_title=record.topic_title,
        topic_description=record.topic_description,
        created_at=record.created_at,
        segment_count=len(content.segments),
        scene_count=len(scenes),
        image_count=image_count,
        audio_count=audio_count,
        has_renders=has_renders,
        thumbnail_url=thumbnail_url,
        status=status,
    )


@router.get("", response_model=list[ScriptSummary])
def list_scripts(session: Session = Depends(get_session)):
    statement = select(Script).order_by(Script.created_at.desc())  # type: ignore[arg-type]
    records = session.exec(statement).all()
    return [_build_summary(r) for r in records]


@router.delete("/{script_id}")
def delete_script(script_id: str, session: Session = Depends(get_session)):
    record = session.get(Script, script_id)
    if not record:
        raise HTTPException(status_code=404, detail="Script not found")

    session.delete(record)
    session.commit()

    # Clean up project files
    project_dir = DATA_DIR / "projects" / script_id
    if project_dir.exists():
        shutil.rmtree(project_dir)

    logger.info("Deleted script %s", script_id)
    return {"ok": True}


@router.post("/generate", response_model=GenerateScriptResponse)
def generate(body: GenerateScriptRequest, session: Session = Depends(get_session)):
    # Auto-resolve brand_id from default brand
    brand_id = body.brand_id or get_default_brand_id(session)
    brand = session.get(BrandProfile, brand_id)
    if not brand:
        raise HTTPException(status_code=404, detail="Brand not found")

    logger.info("Script generation requested: topic=%r, brand_id=%s", body.topic, brand_id)

    # Dedup: if an identical script was created in the last 60 seconds, return it
    cutoff = datetime.now(timezone.utc) - timedelta(seconds=60)
    existing = session.exec(
        select(Script)
        .where(Script.brand_id == brand_id, Script.topic_title == body.topic, Script.created_at >= cutoff)
        .order_by(Script.created_at.desc())  # type: ignore[arg-type]
    ).first()
    if existing:
        return GenerateScriptResponse(
            id=existing.id,
            script=ScriptContent.model_validate(json.loads(existing.script_json)),
        )

    # Build brand context string with universal style + character
    parts = [brand.name]
    if _VISUAL_STYLE:
        parts.append(f"Visual Style:\n{_VISUAL_STYLE}")
    if _CHARACTER:
        parts.append(f"Character:\n{_CHARACTER}")
    brand_context = "\n\n".join(parts)

    brand_dict = {
        "name": brand.name,
    }

    logger.info("Generating script for brand %s, topic: %s", brand_id, body.topic)
    t0 = time.monotonic()
    script_content = generate_script(
        topic=body.topic,
        description=body.description,
        brand_context=brand_context,
        segment_count=body.segment_count,
        animated_scene_count=body.animated_scene_count,
        modifier_ids=[],
        brand=brand_dict,
        model=body.model,
        segmented=body.segmented,
    )
    duration = time.monotonic() - t0
    session.add(GenerationDuration(operation_type="script_generation_youtube", duration_seconds=duration))

    # Persist to SQLite
    record = Script(
        brand_id=brand_id,
        topic_title=body.topic,
        topic_description=body.description,
        script_json=script_content.model_dump_json(),
    )
    session.add(record)
    session.commit()
    session.refresh(record)

    logger.info("Script generated: %s (%d segments) in %.1fs", record.id, len(script_content.segments), duration)
    return GenerateScriptResponse(id=record.id, script=script_content)


@router.put("/{script_id}", response_model=ScriptRead)
def update_script(script_id: str, body: UpdateScriptRequest, session: Session = Depends(get_session)):
    record = session.get(Script, script_id)
    if not record:
        raise HTTPException(status_code=404, detail="Script not found")

    record.script_json = body.script.model_dump_json()
    session.add(record)
    session.commit()
    session.refresh(record)

    logger.info("Updated script %s", script_id)
    return ScriptRead(
        id=record.id,
        brand_id=record.brand_id,
        topic_title=record.topic_title,
        topic_description=record.topic_description,
        script=body.script,
        created_at=record.created_at,
    )

@router.get("/{script_id}", response_model=ScriptRead)
def get_script(script_id: str, session: Session = Depends(get_session)):
    record = session.get(Script, script_id)
    if not record:
        raise HTTPException(status_code=404, detail="Script not found")

    return ScriptRead(
        id=record.id,
        brand_id=record.brand_id,
        topic_title=record.topic_title,
        topic_description=record.topic_description,
        script=ScriptContent.model_validate(json.loads(record.script_json)),
        created_at=record.created_at,
    )

@router.post("/{script_id}/refine-scene", response_model=RefineSceneResponse)
def refine_scene_endpoint(
    script_id: str,
    body: RefineSceneRequest,
    session: Session = Depends(get_session),
):
    record = session.get(Script, script_id)
    if not record:
        raise HTTPException(status_code=404, detail="Script not found")

    script_content = ScriptContent.model_validate(json.loads(record.script_json))

    if body.segment_index < 0 or body.segment_index >= len(script_content.segments):
        raise HTTPException(status_code=400, detail="Invalid segment index")

    segment = script_content.segments[body.segment_index]
    if not any(s.id == body.scene_id for s in segment.scenes):
        raise HTTPException(status_code=400, detail="Scene not found in segment")

    logger.info("Refining scene %s in script %s", body.scene_id, script_id)
    refined = refine_scene(script_content, body.segment_index, body.scene_id)
    return RefineSceneResponse(scene=refined)
