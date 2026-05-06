"""Eli pose generation API — background job that picks one pose per scene."""

import json
import logging

from fastapi import APIRouter, Depends
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
        return {"detail": "Script not found"}, 404

    content = ScriptContent.model_validate(json.loads(record.script_json))
    scenes = [
        sc for seg in content.segments for sc in seg.scenes
        if not sc.is_title_card and sc.narration and not sc.contains_person
    ]

    if req.missing_only:
        scenes = [sc for sc in scenes if not sc.eli_overlay]

    job = create_job(f"eli_{req.script_id}")

    import threading
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
        return {"status": "not_found", "error": "Job not found"}
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
        return {"detail": "Script not found"}, 404

    content = ScriptContent.model_validate(json.loads(record.script_json))
    scene = find_scene_in_content(content, req.scene_id)
    if not scene:
        return {"detail": "Scene not found"}, 404

    previous_corner = None
    all_scenes = content.all_scenes()
    idx = next((i for i, s in enumerate(all_scenes) if s.id == req.scene_id), -1)
    if idx > 0:
        prev = all_scenes[idx - 1]
        if prev.eli_overlay and isinstance(prev.eli_overlay, dict):
            previous_corner = prev.eli_overlay.get("corner")

    eli_result = generate_scene_eli(scene.narration, previous_corner=previous_corner)
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

                sc = scene_map.get(scene_id)
                if not sc:
                    continue

                try:
                    eli_result = generate_scene_eli(sc.narration, previous_corner=previous_corner)
                    sc.eli_overlay = eli_result
                    previous_corner = eli_result.get("corner")
                except Exception as e:
                    logger.warning("Eli failed for scene %s: %s", scene_id, e)

            record.script_json = content.model_dump_json()
            session.add(record)
            session.commit()

        update_job(job_id, status="completed", progress=1.0, current_step="Done")
    except Exception as e:
        logger.error("Eli generation failed: %s", e, exc_info=True)
        update_job(job_id, status="failed", error=str(e)[:500])
