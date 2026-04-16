"""Endpoints for AI-powered script generation."""

import json
import logging
import shutil
import time
from pathlib import Path

from datetime import datetime, timezone, timedelta

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlmodel import Session, select

from database import get_default_brand_id, get_session, engine
from models.brand import BrandProfile
from models.generation_duration import GenerationDuration
from models.script import (
    GenerateScriptRequest,
    GenerateScriptResponse,
    RefineSceneRequest,
    RefineSceneResponse,
    Scene,
    Script,
    ScriptContent,
    ScriptRead,
    ScriptSummary,
    UpdateScriptRequest,
)
from pipeline.refine import refine_scene
from pipeline.render_jobs import create_job, get_job, run_in_background, update_job
from pipeline.scriptwriter import generate_script
from pipeline.audio_split import split_scene_audio
from api._helpers import read_prompt

DATA_DIR = Path(__file__).resolve().parent.parent.parent / "data"

_VISUAL_STYLE = read_prompt("visual_style.md")
_CHARACTER = read_prompt("character.md")

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/scripts", tags=["scripts"])


def _build_summary(record: Script) -> ScriptSummary:
    """Build a ScriptSummary from a Script record."""
    content = ScriptContent.model_validate(json.loads(record.script_json))
    scenes = content.all_scenes()
    image_count = sum(1 for s in scenes if s.image_url)
    audio_count = sum(1 for s in scenes if s.audio_url)

    renders_dir = DATA_DIR / "projects" / record.id / "renders"
    has_renders = renders_dir.exists() and any(renders_dir.iterdir())

    # Prefer composite title card thumbnail, fall back to first scene image
    thumbnail_url = ""
    composite = DATA_DIR / "projects" / record.id / "images" / "composite_title_card.png"
    if composite.exists():
        thumbnail_url = f"/static/projects/{record.id}/images/composite_title_card.png"
    else:
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


class GenerateJobResponse(BaseModel):
    job_id: str


@router.post("/generate", response_model=GenerateJobResponse)
def generate(body: GenerateScriptRequest, session: Session = Depends(get_session)):
    # Auto-resolve brand_id from default brand
    brand_id = body.brand_id or get_default_brand_id(session)
    brand = session.get(BrandProfile, brand_id)
    if not brand:
        raise HTTPException(status_code=404, detail="Brand not found")

    logger.info("Script generation requested: topic=%r, brand_id=%s", body.topic, brand_id)

    # Dedup: if an identical script was created in the last 60 seconds, return it as a completed job
    cutoff = datetime.now(timezone.utc) - timedelta(seconds=60)
    existing = session.exec(
        select(Script)
        .where(Script.brand_id == brand_id, Script.topic_title == body.topic, Script.created_at >= cutoff)
        .order_by(Script.created_at.desc())  # type: ignore[arg-type]
    ).first()
    if existing:
        # Create an already-completed job pointing to the existing script
        job = create_job()
        update_job(job.id, status="completed", progress=1.0, current_step="Complete", output_urls=[existing.id])
        return GenerateJobResponse(job_id=job.id)

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

    # Capture request params for the background thread
    topic = body.topic
    description = body.description
    segment_count = body.segment_count
    animated_scene_count = body.animated_scene_count
    model = body.model
    segmented = body.segmented
    cold_open_text = body.cold_open_text

    job = create_job()
    job_id = job.id

    def _run_generation() -> list[str]:
        def _progress(segment: int, total: int, name: str) -> None:
            update_job(job_id, current_step=json.dumps({
                "segment": segment,
                "total": total,
                "name": name,
            }))

        logger.info("Background script gen started: job=%s, topic=%r", job_id, topic)
        t0 = time.monotonic()
        script_content = generate_script(
            topic=topic,
            description=description,
            brand_context=brand_context,
            segment_count=segment_count,
            animated_scene_count=animated_scene_count,
            brand=brand_dict,
            model=model,
            segmented=segmented,
            cold_open_text=cold_open_text,
            progress_callback=_progress,
        )
        duration = time.monotonic() - t0

        # Persist to SQLite using a fresh session (background thread)
        from sqlmodel import Session as SqlSession
        with SqlSession(engine) as bg_session:
            bg_session.add(GenerationDuration(operation_type="script_generation_youtube", duration_seconds=duration))
            record = Script(
                brand_id=brand_id,
                topic_title=topic,
                topic_description=description,
                script_json=script_content.model_dump_json(),
            )
            bg_session.add(record)
            bg_session.commit()
            bg_session.refresh(record)
            script_id = record.id

        logger.info("Script generated: %s (%d segments) in %.1fs", script_id, len(script_content.segments), duration)
        return [script_id]

    run_in_background(job_id, _run_generation)
    return GenerateJobResponse(job_id=job_id)


@router.get("/generate-status/{job_id}")
def generate_status(job_id: str):
    job = get_job(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    result = job.to_dict()
    # If completed, include script_id for convenience
    if job.status == "completed" and job.output_urls:
        result["script_id"] = job.output_urls[0]
    return result


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


class ScriptCostResponse(BaseModel):
    script_id: str
    total_cost: float


@router.get("/{script_id}/cost", response_model=ScriptCostResponse)
def get_script_cost(script_id: str, session: Session = Depends(get_session)):
    """Return the total estimated cost for a script based on API usage records."""
    from sqlmodel import func
    from models.api_usage import ApiUsage

    result = session.exec(
        select(func.coalesce(func.sum(ApiUsage.cost_estimate), 0.0)).where(ApiUsage.script_id == script_id)
    ).one()
    return ScriptCostResponse(script_id=script_id, total_cost=round(float(result), 4))

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


class SplitSceneRequest(BaseModel):
    scene_id: str
    split_time_ms: int


@router.post("/{script_id}/split-scene", response_model=ScriptRead)
def split_scene_endpoint(
    script_id: str,
    body: SplitSceneRequest,
    session: Session = Depends(get_session),
):
    record = session.get(Script, script_id)
    if not record:
        raise HTTPException(status_code=404, detail="Script not found")

    script_content = ScriptContent.model_validate(json.loads(record.script_json))

    # Find the scene and its segment
    target_seg_idx = None
    target_scene_idx = None
    target_scene = None
    for si, seg in enumerate(script_content.segments):
        for sci, sc in enumerate(seg.scenes):
            if sc.id == body.scene_id:
                target_seg_idx = si
                target_scene_idx = sci
                target_scene = sc
                break
        if target_scene is not None:
            break

    if target_scene is None:
        raise HTTPException(status_code=404, detail="Scene not found")

    if not target_scene.audio_url:
        raise HTTPException(status_code=422, detail="Scene has no audio to split")

    # Perform the split
    scene_dict = target_scene.model_dump()
    scene_a, scene_b = split_scene_audio(script_id, scene_dict, body.split_time_ms)

    # Splice into the segment: replace original with [A, B]
    segment = script_content.segments[target_seg_idx]
    new_scenes = list(segment.scenes)
    new_scenes[target_scene_idx:target_scene_idx + 1] = [
        Scene.model_validate(scene_a),
        Scene.model_validate(scene_b),
    ]
    segment.scenes = new_scenes

    # Persist
    record.script_json = script_content.model_dump_json()
    session.add(record)
    session.commit()
    session.refresh(record)

    logger.info("Split scene %s in script %s at %dms", body.scene_id, script_id, body.split_time_ms)

    return ScriptRead(
        id=record.id,
        brand_id=record.brand_id,
        topic_title=record.topic_title,
        topic_description=record.topic_description,
        script=script_content,
        created_at=record.created_at,
    )
