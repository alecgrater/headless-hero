"""Eli pose generation API — background job that picks one pose per scene."""

import json
import logging
import threading

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlmodel import Session

from api._helpers import find_scene_in_content
from database import get_session
from models.script import Script, ScriptContent
from pipeline.eli_animator import generate_scene_eli
from pipeline.render_jobs import create_job, update_job, get_job

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/eli", tags=["eli"])


class GenerateEliRequest(BaseModel):
    script_id: str
    missing_only: bool = False


class RegenerateEliRequest(BaseModel):
    script_id: str
    scene_id: str


@router.post("/generate")
async def generate_eli(req: GenerateEliRequest, session: Session = Depends(get_session)):
    record = session.get(Script, req.script_id)
    if not record:
        raise HTTPException(status_code=404, detail="Script not found")

    content = ScriptContent.model_validate(json.loads(record.script_json))
    scenes = [
        sc for seg in content.segments for sc in seg.scenes
        if not sc.is_title_card and sc.narration and not sc.contains_person
    ]

    if req.missing_only:
        scenes = [sc for sc in scenes if not sc.eli_overlay]

    job = create_job(scene_count=len(scenes))

    t = threading.Thread(
        target=_run_eli_generation,
        args=(req.script_id, [sc.id for sc in scenes], job.id),
        daemon=True,
    )
    t.start()

    return {"job_id": job.id}


@router.get("/generate-status/{job_id}")
async def eli_status(job_id: str):
    job = get_job(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    return {
        "status": job.status,
        "progress": job.progress,
        "current_step": job.current_step,
        "error": job.error,
    }


@router.post("/regenerate")
async def regenerate_eli(req: RegenerateEliRequest, session: Session = Depends(get_session)):
    record = session.get(Script, req.script_id)
    if not record:
        raise HTTPException(status_code=404, detail="Script not found")

    content = ScriptContent.model_validate(json.loads(record.script_json))
    scene = find_scene_in_content(content, req.scene_id)
    if not scene:
        raise HTTPException(status_code=404, detail="Scene not found")

    previous_corner = None
    all_scenes = content.all_scenes()
    idx = next((i for i, s in enumerate(all_scenes) if s.id == req.scene_id), -1)
    if idx > 0:
        prev = all_scenes[idx - 1]
        if prev.eli_overlay and isinstance(prev.eli_overlay, dict):
            previous_corner = prev.eli_overlay.get("corner")

    eli_result = generate_scene_eli(scene.narration, previous_corner=previous_corner, script_id=req.script_id)
    scene.eli_overlay = eli_result

    record.script_json = content.model_dump_json()
    session.add(record)
    session.commit()

    return {"eli_overlay": eli_result}


def _run_eli_generation(script_id: str, scene_ids: list[str], job_id: str) -> None:
    """Background thread: generate Eli poses for listed scenes."""
    from database import engine

    try:
        total = len(scene_ids)
        logger.info("[ELI] Starting generation for %d scenes (job=%s)", total, job_id)
        previous_corner: str | None = None

        with Session(engine) as session:
            record = session.get(Script, script_id)
            if not record:
                update_job(job_id, status="failed", error="Script not found")
                return
            content = ScriptContent.model_validate(json.loads(record.script_json))

            all_scenes = content.all_scenes()
            scene_map = {sc.id: sc for sc in all_scenes}

            for i, scene_id in enumerate(scene_ids):
                job = get_job(job_id)
                if job and job.status == "cancelled":
                    return

                update_job(job_id, progress=i / total, current_step=f"Scene {i+1}/{total}")
                logger.info("[ELI] Scene %d/%d (%s): generating pose", i + 1, total, scene_id)

                sc = scene_map.get(scene_id)
                if not sc:
                    continue

                try:
                    eli_result = generate_scene_eli(sc.narration, previous_corner=previous_corner, script_id=script_id)
                    sc.eli_overlay = eli_result
                    previous_corner = eli_result.get("corner")
                    logger.info(
                        "[ELI] Scene %d/%d complete (frame=%s, corner=%s)",
                        i + 1, total, eli_result.get("frame_id"), eli_result.get("corner"),
                    )
                except Exception as e:
                    logger.warning("[ELI] Scene %d/%d failed (%s): %s", i + 1, total, scene_id, e)

            record.script_json = content.model_dump_json()
            session.add(record)
            session.commit()

        update_job(job_id, status="completed", progress=1.0, current_step="Done")
        logger.info("[ELI] Generation complete for %d scenes (job=%s)", total, job_id)
    except Exception as e:
        logger.error("[ELI] Generation failed: %s", e, exc_info=True)
        update_job(job_id, status="failed", error=str(e)[:500])
