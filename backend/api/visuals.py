"""Endpoints for AI image generation via fal.ai Flux."""

from __future__ import annotations

import json
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlmodel import Session

from api.database import get_session
from models.script import Script, ScriptContent
from pipeline.image_gen import generate_batch, generate_scene_image

router = APIRouter(prefix="/api/visuals", tags=["visuals"])


# --- Request / Response schemas ---


class GenerateVisualRequest(BaseModel):
    script_id: str
    scene_id: str
    visual_prompt: str
    brand_style: str = ""
    width: int = 1344
    height: int = 768


class GenerateVisualResponse(BaseModel):
    image_url: str
    prompt_used: str


class BatchScene(BaseModel):
    scene_id: str
    visual_prompt: str


class GenerateBatchRequest(BaseModel):
    script_id: str
    scenes: List[BatchScene]
    brand_style: str = ""
    width: int = 1344
    height: int = 768


class BatchResultItem(BaseModel):
    scene_id: str
    image_url: Optional[str] = None
    prompt_used: Optional[str] = None
    error: Optional[str] = None


class GenerateBatchResponse(BaseModel):
    results: List[BatchResultItem]


# --- Helpers ---


def _update_scene_image_url(
    session: Session, script_id: str, scene_id: str, image_url: str
) -> None:
    """Persist image_url into the scene inside script_json."""
    record = session.get(Script, script_id)
    if not record:
        return
    content = ScriptContent.model_validate(json.loads(record.script_json))
    for seg in content.segments:
        for scene in seg.scenes:
            if scene.id == scene_id:
                scene.image_url = image_url
                break
    record.script_json = content.model_dump_json()
    session.add(record)
    session.commit()


# --- Endpoints ---


@router.post("/generate", response_model=GenerateVisualResponse)
def generate_visual(body: GenerateVisualRequest, session: Session = Depends(get_session)):
    """Generate an image for a single scene."""
    # Verify script exists
    record = session.get(Script, body.script_id)
    if not record:
        raise HTTPException(status_code=404, detail="Script not found")

    image_url, prompt_used = generate_scene_image(
        scene_id=body.scene_id,
        visual_prompt=body.visual_prompt,
        brand_style=body.brand_style,
        script_id=body.script_id,
        width=body.width,
        height=body.height,
    )

    _update_scene_image_url(session, body.script_id, body.scene_id, image_url)

    return GenerateVisualResponse(image_url=image_url, prompt_used=prompt_used)


@router.post("/generate-batch", response_model=GenerateBatchResponse)
def generate_visual_batch(body: GenerateBatchRequest, session: Session = Depends(get_session)):
    """Generate images for multiple scenes sequentially."""
    record = session.get(Script, body.script_id)
    if not record:
        raise HTTPException(status_code=404, detail="Script not found")

    scenes = [{"scene_id": s.scene_id, "visual_prompt": s.visual_prompt} for s in body.scenes]

    results = generate_batch(
        scenes=scenes,
        brand_style=body.brand_style,
        script_id=body.script_id,
        width=body.width,
        height=body.height,
    )

    # Persist successful image URLs
    for r in results:
        if r["image_url"]:
            _update_scene_image_url(session, body.script_id, r["scene_id"], r["image_url"])

    return GenerateBatchResponse(results=[BatchResultItem(**r) for r in results])
