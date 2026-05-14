"""Endpoints for AI-powered FX generation."""

import json
import logging
import threading
import time

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlmodel import Session

from config import FPS
from database import get_session, engine
from models.generation_duration import GenerationDuration
from models.script import Script, ScriptContent
from pipeline.fx_generator import generate_scene_fx
from pipeline.render_jobs import create_job, get_job, update_job

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/fx", tags=["fx"])


class GenerateFXRequest(BaseModel):
    script_id: str
    missing_only: bool = False


class RegenerateFXRequest(BaseModel):
    script_id: str
    scene_id: str


class RegenerateFXResponse(BaseModel):
    scene_id: str
    fx: dict
    transition_in: str = "cut"


@router.post("/generate")
def generate_all_fx(body: GenerateFXRequest, session: Session = Depends(get_session)):
    """Kick off a background job to generate FX for all scenes.

    Returns immediately with a job_id. The client polls /generate-status/{job_id}.
    This avoids holding a multi-minute idle HTTP connection for large scripts.
    """
    record = session.get(Script, body.script_id)
    if not record:
        raise HTTPException(status_code=404, detail="Script not found")

    content = ScriptContent.model_validate(json.loads(record.script_json))
    total_scenes = sum(len(seg.scenes) for seg in content.segments)

    job = create_job(scene_count=total_scenes)

    t = threading.Thread(
        target=_run_fx_generation,
        args=(body.script_id, body.missing_only, job.id),
        daemon=True,
    )
    t.start()

    return {"job_id": job.id}


@router.get("/generate-status/{job_id}")
async def fx_status(job_id: str):
    job = get_job(job_id)
    if not job:
        return {"status": "not_found", "error": "Job not found"}
    return {
        "status": job.status,
        "progress": job.progress,
        "current_step": job.current_step,
        "error": job.error,
    }


@router.post("/regenerate", response_model=RegenerateFXResponse)
def regenerate_scene_fx(body: RegenerateFXRequest, session: Session = Depends(get_session)):
    """Regenerate FX for a single scene using Claude."""
    logger.info("Regenerating FX for scene %s in script %s", body.scene_id, body.script_id)
    record = session.get(Script, body.script_id)
    if not record:
        raise HTTPException(status_code=404, detail="Script not found")

    content = ScriptContent.model_validate(json.loads(record.script_json))

    # Find the scene and its context
    target_scene = None
    seg_idx = -1
    sc_idx = -1
    global_idx = 0
    total_scenes = sum(len(seg.scenes) for seg in content.segments)

    for si, seg in enumerate(content.segments):
        for sci, scene in enumerate(seg.scenes):
            if scene.id == body.scene_id:
                target_scene = scene
                seg_idx = si
                sc_idx = sci
                break
            global_idx += 1
        if target_scene:
            break

    if not target_scene:
        raise HTTPException(status_code=404, detail="Scene not found")

    # Build scene summary for Claude
    duration = target_scene.audio_duration_seconds or target_scene.duration_estimate_seconds
    scene_data = {
        "id": target_scene.id,
        "segment": content.segments[seg_idx].name,
        "segment_index": seg_idx,
        "scene_index_in_segment": sc_idx,
        "global_index": global_idx,
        "is_first_scene": global_idx == 0,
        "is_last_scene": global_idx == total_scenes - 1,
        "is_first_in_segment": sc_idx == 0,
        "is_title_card": target_scene.is_title_card,
        "narration": target_scene.narration[:200],
        "visual_prompt": target_scene.visual_prompt[:100],
        "duration_seconds": duration,
        "duration_frames": round(duration * FPS),
        "has_multiple_frames": bool(target_scene.frame_urls and len(target_scene.frame_urls) > 1),
        "visual_beat": target_scene.visual_beat or "static",
    }
    if target_scene.word_timestamps:
        scene_data["word_timestamps"] = target_scene.word_timestamps

    # Find neighboring scene's drift and transition for context
    all_scenes = content.all_scenes()
    if global_idx > 0:
        prev_scene = all_scenes[global_idx - 1]
        prev_fx = prev_scene.fx if isinstance(prev_scene.fx, dict) else {}
        if prev_fx.get("drift"):
            scene_data["previous_drift"] = prev_fx["drift"]
        if prev_scene.transition_in and prev_scene.transition_in != "cut":
            scene_data["previous_transition"] = prev_scene.transition_in

    result = generate_scene_fx(scene_data)

    # Apply to the scene
    target_scene.fx = result["fx"]
    target_scene.transition_in = result.get("transition_in", "cut")

    # Save back to DB
    record.script_json = content.model_dump_json()
    session.add(record)
    session.commit()

    logger.info("Regenerated FX for scene %s", body.scene_id)
    return RegenerateFXResponse(scene_id=body.scene_id, fx=result["fx"], transition_in=target_scene.transition_in)


def _run_fx_generation(script_id: str, missing_only: bool, job_id: str) -> None:
    """Background thread: generate FX for all scenes in a script."""
    t0 = time.monotonic()
    try:
        with Session(engine) as session:
            record = session.get(Script, script_id)
            if not record:
                update_job(job_id, status="failed", error="Script not found")
                return

            content = ScriptContent.model_validate(json.loads(record.script_json))
            total_scenes = sum(len(seg.scenes) for seg in content.segments)
            logger.info("Generating FX for all scenes in script %s", script_id)

            updated = 0
            global_idx = 0
            previous_drift = None
            previous_transition = None
            for seg_idx, seg in enumerate(content.segments):
                for sc_idx, scene in enumerate(seg.scenes):
                    job = get_job(job_id)
                    if job and job.status == "cancelled":
                        return

                    if missing_only and scene.fx:
                        fx_data = scene.fx if isinstance(scene.fx, dict) else {}
                        if fx_data.get("drift"):
                            previous_drift = fx_data["drift"]
                        previous_transition = scene.transition_in if scene.transition_in != "cut" else None
                        global_idx += 1
                        continue

                    update_job(
                        job_id,
                        progress=global_idx / total_scenes if total_scenes else 0.0,
                        current_step=f"Scene {global_idx + 1}/{total_scenes}",
                    )

                    duration = scene.audio_duration_seconds or scene.duration_estimate_seconds
                    scene_data = {
                        "id": scene.id,
                        "segment": seg.name,
                        "segment_index": seg_idx,
                        "scene_index_in_segment": sc_idx,
                        "global_index": global_idx,
                        "is_first_scene": global_idx == 0,
                        "is_last_scene": global_idx == total_scenes - 1,
                        "is_first_in_segment": sc_idx == 0,
                        "is_title_card": scene.is_title_card,
                        "narration": scene.narration,
                        "duration_seconds": duration,
                        "duration_frames": int(duration * FPS),
                        "has_multiple_frames": bool(scene.frame_urls and len(scene.frame_urls) > 1),
                        "visual_beat": scene.visual_beat or "static",
                    }
                    if scene.word_timestamps:
                        scene_data["word_timestamps"] = scene.word_timestamps
                    if previous_drift:
                        scene_data["previous_drift"] = previous_drift
                    if previous_transition:
                        scene_data["previous_transition"] = previous_transition

                    try:
                        result = generate_scene_fx(scene_data, script_id=script_id)
                        scene.fx = result["fx"]
                        scene.transition_in = result.get("transition_in", "cut")
                        fx_result = result["fx"] if isinstance(result["fx"], dict) else {}
                        if fx_result.get("drift"):
                            previous_drift = fx_result["drift"]
                        previous_transition = scene.transition_in if scene.transition_in != "cut" else None
                        updated += 1
                        logger.info("Generated FX for scene %d/%d (%s)", global_idx + 1, total_scenes, scene.id)
                    except Exception as e:
                        logger.warning("Failed FX for scene %s: %s", scene.id, e)

                    global_idx += 1

            record.script_json = content.model_dump_json()
            session.add(record)
            session.commit()

            logger.info("Applied FX to %d/%d scenes for script %s", updated, total_scenes, script_id)

            duration_seconds = time.monotonic() - t0
            session.add(GenerationDuration(
                operation_type="fx_generation",
                duration_seconds=duration_seconds,
                scene_count=total_scenes,
            ))
            session.commit()

        update_job(job_id, status="completed", progress=1.0, current_step="Done")
    except Exception as e:
        logger.error("FX generation failed: %s", e, exc_info=True)
        update_job(job_id, status="failed", error=str(e)[:500])
