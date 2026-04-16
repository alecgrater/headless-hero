"""Endpoints for Eli character animation generation."""

import json
import logging

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlmodel import Session

from config import FPS
from database import get_session
from models.brand import BrandProfile
from models.script import Script, ScriptContent
from pipeline.eli_animator import generate_scene_eli

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/eli", tags=["eli"])


class GenerateEliRequest(BaseModel):
    script_id: str
    missing_only: bool = False


class GenerateEliResponse(BaseModel):
    script_id: str
    scenes_updated: int


class RegenerateEliRequest(BaseModel):
    script_id: str
    scene_id: str


class RegenerateEliResponse(BaseModel):
    scene_id: str
    eli_overlay: dict


@router.post("/generate", response_model=GenerateEliResponse)
def generate_all_eli(body: GenerateEliRequest, session: Session = Depends(get_session)):
    """Generate Eli animation keyframes for all non-title-card scenes."""
    logger.info("Generating Eli overlays for script %s", body.script_id)
    record = session.get(Script, body.script_id)
    if not record:
        raise HTTPException(status_code=404, detail="Script not found")

    content = ScriptContent.model_validate(json.loads(record.script_json))
    total_scenes = sum(len(seg.scenes) for seg in content.segments)

    # Resolve Eli position: script override > brand default > None
    eli_position = content.eli_position
    if not eli_position:
        brand = session.get(BrandProfile, record.brand_id)
        if brand and brand.eli_position_json:
            try:
                eli_position = json.loads(brand.eli_position_json)
            except (ValueError, TypeError):
                pass

    updated = 0
    global_idx = 0
    for seg_idx, seg in enumerate(content.segments):
        for sc_idx, scene in enumerate(seg.scenes):
            # Skip title cards and scenes where Eli is in the main image
            if scene.is_title_card or scene.contains_person:
                global_idx += 1
                continue
            if body.missing_only and scene.eli_overlay:
                global_idx += 1
                continue

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
                result = generate_scene_eli(scene_data, script_id=body.script_id, eli_position=eli_position)
                scene.eli_overlay = result["eli_overlay"]
                updated += 1
                logger.info("Generated Eli overlay for scene %d/%d (%s)", global_idx + 1, total_scenes, scene.id)
            except Exception as e:
                logger.warning("Failed Eli overlay for scene %s: %s", scene.id, e)

            global_idx += 1

    # Save back to DB
    record.script_json = content.model_dump_json()
    session.add(record)
    session.commit()

    logger.info("Applied Eli overlays to %d scenes for script %s", updated, body.script_id)
    return GenerateEliResponse(script_id=body.script_id, scenes_updated=updated)


@router.post("/regenerate", response_model=RegenerateEliResponse)
def regenerate_scene_eli_endpoint(body: RegenerateEliRequest, session: Session = Depends(get_session)):
    """Regenerate Eli animation for a single scene."""
    logger.info("Regenerating Eli overlay for scene %s in script %s", body.scene_id, body.script_id)
    record = session.get(Script, body.script_id)
    if not record:
        raise HTTPException(status_code=404, detail="Script not found")

    content = ScriptContent.model_validate(json.loads(record.script_json))

    # Resolve Eli position: script override > brand default > None
    eli_position = content.eli_position
    if not eli_position:
        brand = session.get(BrandProfile, record.brand_id)
        if brand and brand.eli_position_json:
            try:
                eli_position = json.loads(brand.eli_position_json)
            except (ValueError, TypeError):
                pass

    # Find the scene
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

    result = generate_scene_eli(scene_data, script_id=body.script_id, eli_position=eli_position)

    target_scene.eli_overlay = result["eli_overlay"]

    # Save back to DB
    record.script_json = content.model_dump_json()
    session.add(record)
    session.commit()

    logger.info("Regenerated Eli overlay for scene %s", body.scene_id)
    return RegenerateEliResponse(scene_id=body.scene_id, eli_overlay=result["eli_overlay"])
