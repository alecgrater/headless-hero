"""Endpoints for AI-powered script generation."""

import json
import shutil
import time
from pathlib import Path

from datetime import datetime, timezone, timedelta

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlmodel import Session, select

from api.database import get_session
from models.brand import BrandProfile
from models.generation_duration import GenerationDuration
from models.script import (
    GenerateScriptRequest,
    GenerateScriptResponse,
    GenerateShortformScriptRequest,
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
from pipeline.shortform_scriptwriter import generate_shortform_script

DATA_DIR = Path(__file__).resolve().parent.parent.parent / "data"

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
        content_format=record.content_format or "youtube",
    )


@router.get("", response_model=list[ScriptSummary])
def list_scripts(
    brand_id: str = Query(..., description="Filter by brand ID"),
    session: Session = Depends(get_session),
):
    statement = select(Script).where(Script.brand_id == brand_id).order_by(Script.created_at.desc())  # type: ignore[arg-type]
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

    return {"ok": True}


@router.post("/generate", response_model=GenerateScriptResponse)
def generate(body: GenerateScriptRequest, session: Session = Depends(get_session)):
    brand = session.get(BrandProfile, body.brand_id)
    if not brand:
        raise HTTPException(status_code=404, detail="Brand not found")

    # Dedup: if an identical script was created in the last 60 seconds, return it
    cutoff = datetime.now(timezone.utc) - timedelta(seconds=60)
    existing = session.exec(
        select(Script)
        .where(Script.brand_id == body.brand_id, Script.topic_title == body.topic, Script.created_at >= cutoff)
        .order_by(Script.created_at.desc())  # type: ignore[arg-type]
    ).first()
    if existing:
        return GenerateScriptResponse(
            id=existing.id,
            script=ScriptContent.model_validate(json.loads(existing.script_json)),
        )

    # Build brand context string
    parts = [brand.name]
    if brand.art_style:
        parts.append(f"Art style: {brand.art_style}")
    brand_context = ". ".join(parts)

    # Parse modifier IDs from brand (default to title_cards for backward compat)
    modifier_ids: list[str] = []
    try:
        import json as _json
        parsed = _json.loads(brand.content_modifiers) if brand.content_modifiers else []
        modifier_ids = parsed if isinstance(parsed, list) else []
    except Exception:
        pass
    if not modifier_ids:
        modifier_ids = ["title_cards"]

    brand_dict = {
        "name": brand.name,
        "art_style": brand.art_style,
        "color_palette": brand.color_palette,
        "font": brand.font,
    }

    t0 = time.monotonic()
    script_content = generate_script(
        topic=body.topic,
        description=body.description,
        brand_context=brand_context,
        segment_count=body.segment_count,
        animated_scene_count=body.animated_scene_count,
        modifier_ids=modifier_ids,
        brand=brand_dict,
    )
    duration = time.monotonic() - t0
    session.add(GenerationDuration(operation_type="script_generation_youtube", duration_seconds=duration))

    # Persist to SQLite
    record = Script(
        brand_id=body.brand_id,
        topic_title=body.topic,
        topic_description=body.description,
        script_json=script_content.model_dump_json(),
    )
    session.add(record)
    session.commit()
    session.refresh(record)

    return GenerateScriptResponse(id=record.id, script=script_content)


@router.post("/generate-shortform", response_model=GenerateScriptResponse)
def generate_shortform(body: GenerateShortformScriptRequest, session: Session = Depends(get_session)):
    brand = session.get(BrandProfile, body.brand_id)
    if not brand:
        raise HTTPException(status_code=404, detail="Brand not found")

    # Dedup: if an identical script was created in the last 60 seconds, return it
    cutoff = datetime.now(timezone.utc) - timedelta(seconds=60)
    existing = session.exec(
        select(Script)
        .where(Script.brand_id == body.brand_id, Script.topic_title == body.topic, Script.created_at >= cutoff)
        .order_by(Script.created_at.desc())  # type: ignore[arg-type]
    ).first()
    if existing:
        return GenerateScriptResponse(
            id=existing.id,
            script=ScriptContent.model_validate(json.loads(existing.script_json)),
        )

    parts = [brand.name]
    if brand.art_style:
        parts.append(f"Art style: {brand.art_style}")
    brand_context = ". ".join(parts)

    modifier_ids: list[str] = []
    try:
        import json as _json
        parsed = _json.loads(brand.content_modifiers) if brand.content_modifiers else []
        modifier_ids = parsed if isinstance(parsed, list) else []
    except Exception:
        pass
    if not modifier_ids:
        modifier_ids = ["title_cards"]

    brand_dict = {
        "name": brand.name,
        "art_style": brand.art_style,
        "color_palette": brand.color_palette,
        "font": brand.font,
    }

    t0 = time.monotonic()
    script_content = generate_shortform_script(
        topic=body.topic,
        description=body.description,
        brand_context=brand_context,
        platforms=body.platforms,
        target_duration_seconds=body.target_duration_seconds,
        modifier_ids=modifier_ids,
        brand=brand_dict,
    )
    duration = time.monotonic() - t0
    session.add(GenerationDuration(operation_type="script_generation_shortform", duration_seconds=duration))

    record = Script(
        brand_id=body.brand_id,
        topic_title=body.topic,
        topic_description=body.description,
        script_json=script_content.model_dump_json(),
        content_format="shortform",
        shortform_platforms=json.dumps(body.platforms),
    )
    session.add(record)
    session.commit()
    session.refresh(record)

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

    return ScriptRead(
        id=record.id,
        brand_id=record.brand_id,
        topic_title=record.topic_title,
        topic_description=record.topic_description,
        script=body.script,
        created_at=record.created_at,
        content_format=record.content_format or "youtube",
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
        content_format=record.content_format or "youtube",
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

    refined = refine_scene(script_content, body.segment_index, body.scene_id)
    return RefineSceneResponse(scene=refined)
