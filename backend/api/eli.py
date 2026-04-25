"""Endpoints for Eli character animation generation."""

import json
import logging

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlmodel import Session

from config import FPS
from database import get_session
from models.script import Script, ScriptContent
from pipeline.eli_animator import generate_scene_eli
from pipeline.render_jobs import create_job, get_job, is_cancelled, run_in_background, update_job

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/eli", tags=["eli"])


class GenerateEliRequest(BaseModel):
    script_id: str
    missing_only: bool = False


class GenerateEliJobResponse(BaseModel):
    job_id: str


class RegenerateEliRequest(BaseModel):
    script_id: str
    scene_id: str


class RegenerateEliResponse(BaseModel):
    scene_id: str
    eli_overlay: dict


@router.post("/generate", response_model=GenerateEliJobResponse)
def generate_all_eli(body: GenerateEliRequest, session: Session = Depends(get_session)):
    """Generate Eli animation keyframes for all non-title-card scenes (background job)."""
    logger.info("Generating Eli overlays for script %s", body.script_id)
    record = session.get(Script, body.script_id)
    if not record:
        raise HTTPException(status_code=404, detail="Script not found")

    content = ScriptContent.model_validate(json.loads(record.script_json))
    eligible = sum(
        1
        for seg in content.segments
        for sc in seg.scenes
        if not sc.is_title_card and not sc.contains_person and (not body.missing_only or not sc.eli_overlay)
    )

    job = create_job(scene_count=eligible)
    script_id = body.script_id
    missing_only = body.missing_only

    def _run():
        from database import engine
        from sqlmodel import Session as BgSession

        with BgSession(engine) as bg_session:
            rec = bg_session.get(Script, script_id)
            if not rec:
                raise RuntimeError(f"Script {script_id} not found")

            c = ScriptContent.model_validate(json.loads(rec.script_json))
            total_scenes = sum(len(seg.scenes) for seg in c.segments)

            updated = 0
            processed = 0
            global_idx = 0
            previous_corner: str | None = None
            for seg_idx, seg in enumerate(c.segments):
                for sc_idx, scene in enumerate(seg.scenes):
                    if is_cancelled(job.id):
                        return

                    if scene.is_title_card or scene.contains_person:
                        global_idx += 1
                        continue
                    if missing_only and scene.eli_overlay:
                        global_idx += 1
                        continue

                    processed += 1
                    update_job(
                        job.id,
                        progress=processed / eligible if eligible > 0 else 0,
                        current_step=f"Scene {global_idx + 1}/{total_scenes}",
                    )

                    duration = scene.audio_duration_seconds or scene.duration_estimate_seconds
                    scene_data = {
                        "id": scene.id,
                        "segment": seg.name,
                        "segment_index": seg_idx,
                        "scene_index_in_segment": sc_idx,
                        "global_index": global_idx,
                        "is_title_card": False,
                        "narration": scene.narration,
                        "duration_seconds": duration,
                        "duration_frames": int(duration * FPS),
                    }
                    if scene.word_timestamps:
                        scene_data["word_timestamps"] = scene.word_timestamps

                    try:
                        result = generate_scene_eli(scene_data, script_id=script_id, previous_corner=previous_corner)
                        scene.eli_overlay = result["eli_overlay"]
                        previous_corner = result["eli_overlay"].get("corner", "BR")
                        updated += 1
                        logger.info("Generated Eli overlay for scene %d/%d (%s)", global_idx + 1, total_scenes, scene.id)
                    except Exception as e:
                        logger.warning("Failed Eli overlay for scene %s: %s", scene.id, e)

                    global_idx += 1

            rec.script_json = c.model_dump_json()
            bg_session.add(rec)
            bg_session.commit()
            logger.info("Applied Eli overlays to %d scenes for script %s", updated, script_id)

    run_in_background(job.id, _run)
    return GenerateEliJobResponse(job_id=job.id)


@router.get("/generate-status/{job_id}")
def eli_generate_status(job_id: str):
    """Poll Eli generation job status."""
    job = get_job(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    return job.to_dict()


@router.post("/regenerate", response_model=RegenerateEliResponse)
def regenerate_scene_eli_endpoint(body: RegenerateEliRequest, session: Session = Depends(get_session)):
    """Regenerate Eli animation for a single scene."""
    logger.info("Regenerating Eli overlay for scene %s in script %s", body.scene_id, body.script_id)
    record = session.get(Script, body.script_id)
    if not record:
        raise HTTPException(status_code=404, detail="Script not found")

    content = ScriptContent.model_validate(json.loads(record.script_json))

    # Find the scene and determine previous scene's corner
    target_scene = None
    seg_idx = -1
    sc_idx = -1
    global_idx = 0
    previous_corner: str | None = None

    for si, seg in enumerate(content.segments):
        for sci, scene in enumerate(seg.scenes):
            if scene.id == body.scene_id:
                target_scene = scene
                seg_idx = si
                sc_idx = sci
                break
            # Track previous non-title-card scene's corner
            if not scene.is_title_card and not scene.contains_person and scene.eli_overlay:
                previous_corner = scene.eli_overlay.get("corner")
            global_idx += 1
        if target_scene:
            break

    if not target_scene:
        raise HTTPException(status_code=404, detail="Scene not found")

    if target_scene.is_title_card:
        raise HTTPException(status_code=400, detail="Cannot add Eli overlay to title card scenes")

    duration = target_scene.audio_duration_seconds or target_scene.duration_estimate_seconds
    scene_data = {
        "id": target_scene.id,
        "segment": content.segments[seg_idx].name,
        "segment_index": seg_idx,
        "scene_index_in_segment": sc_idx,
        "global_index": global_idx,
        "is_title_card": False,
        "narration": target_scene.narration,
        "duration_seconds": duration,
        "duration_frames": int(duration * FPS),
    }
    if target_scene.word_timestamps:
        scene_data["word_timestamps"] = target_scene.word_timestamps

    result = generate_scene_eli(scene_data, script_id=body.script_id, previous_corner=previous_corner)

    target_scene.eli_overlay = result["eli_overlay"]

    # Save back to DB
    record.script_json = content.model_dump_json()
    session.add(record)
    session.commit()

    logger.info("Regenerated Eli overlay for scene %s", body.scene_id)
    return RegenerateEliResponse(scene_id=body.scene_id, eli_overlay=result["eli_overlay"])
