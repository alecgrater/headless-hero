"""Endpoints for AI-powered FX generation."""

import json
import logging

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlmodel import Session

from database import get_session
from models.script import Script, ScriptContent
from pipeline.fx_generator import generate_scene_fx

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/fx", tags=["fx"])


class GenerateFXRequest(BaseModel):
    script_id: str


class GenerateFXResponse(BaseModel):
    script_id: str
    scenes_updated: int


class RegenerateFXRequest(BaseModel):
    script_id: str
    scene_id: str


class RegenerateFXResponse(BaseModel):
    scene_id: str
    fx: dict


@router.post("/generate", response_model=GenerateFXResponse)
def generate_all_fx(body: GenerateFXRequest, session: Session = Depends(get_session)):
    """Generate FX assignments for all scenes by calling per-scene generation."""
    logger.info("Generating FX for all scenes in script %s", body.script_id)
    record = session.get(Script, body.script_id)
    if not record:
        raise HTTPException(status_code=404, detail="Script not found")

    content = ScriptContent.model_validate(json.loads(record.script_json))
    total_scenes = sum(len(seg.scenes) for seg in content.segments)

    updated = 0
    global_idx = 0
    for seg_idx, seg in enumerate(content.segments):
        for sc_idx, scene in enumerate(seg.scenes):
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
                "media_type": scene.media_type or "ai_generated",
                "narration": scene.narration,
                "duration_seconds": duration,
                "duration_frames": int(duration * 30),
                "has_multiple_frames": bool(scene.frame_urls and len(scene.frame_urls) > 1),
            }
            if scene.word_timestamps:
                scene_data["word_timestamps"] = scene.word_timestamps

            try:
                result = generate_scene_fx(scene_data)
                scene.fx = result["fx"]
                updated += 1
                logger.info("Generated FX for scene %d/%d (%s)", global_idx + 1, total_scenes, scene.id)
            except Exception as e:
                logger.warning("Failed FX for scene %s: %s", scene.id, e)

            global_idx += 1

    # Save back to DB
    record.script_json = content.model_dump_json()
    session.add(record)
    session.commit()

    logger.info("Applied FX to %d/%d scenes for script %s", updated, total_scenes, body.script_id)
    return GenerateFXResponse(script_id=body.script_id, scenes_updated=updated)


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
        "media_type": target_scene.media_type or "ai_generated",
        "narration": target_scene.narration[:200],
        "visual_prompt": target_scene.visual_prompt[:100],
        "text_overlay": target_scene.text_overlay,
        "duration_seconds": duration,
        "duration_frames": round(duration * 30),
        "has_multiple_frames": bool(target_scene.frame_urls and len(target_scene.frame_urls) > 1),
    }
    if target_scene.word_timestamps:
        scene_data["word_timestamps"] = target_scene.word_timestamps

    result = generate_scene_fx(scene_data)

    # Apply to the scene
    target_scene.fx = result["fx"]

    # Save back to DB
    record.script_json = content.model_dump_json()
    session.add(record)
    session.commit()

    logger.info("Regenerated FX for scene %s", body.scene_id)
    return RegenerateFXResponse(scene_id=body.scene_id, fx=result["fx"])
