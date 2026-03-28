"""Endpoints for AI image generation via Google Gemini."""

import json
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlmodel import Session

from api.database import get_session
from models.script import Script, ScriptContent
from pipeline.image_gen import generate_batch, generate_scene_image

router = APIRouter(prefix="/api/visuals", tags=["visuals"])

# Load shortform style guide once
_SHORTFORM_GUIDE_PATH = Path(__file__).resolve().parent.parent / "prompts" / "shortform_image_gen_guide.md"
_SHORTFORM_STYLE_GUIDE = _SHORTFORM_GUIDE_PATH.read_text() if _SHORTFORM_GUIDE_PATH.exists() else ""

# --- Request / Response schemas ---

class GenerateVisualRequest(BaseModel):
    script_id: str
    scene_id: str
    visual_prompt: str
    brand_style: str = ""
    width: int = 1344
    height: int = 768
    is_animated: bool = False
    visual_prompt_b: str = ""

class GenerateVisualResponse(BaseModel):
    image_url: str
    prompt_used: str
    image_url_b: str | None = None

class BatchScene(BaseModel):
    scene_id: str
    visual_prompt: str
    is_animated: bool = False
    visual_prompt_b: str = ""

class GenerateBatchRequest(BaseModel):
    script_id: str
    scenes: list[BatchScene]
    brand_style: str = ""
    width: int = 1344
    height: int = 768

class BatchResultItem(BaseModel):
    scene_id: str
    image_url: str | None = None
    image_url_b: str | None = None
    prompt_used: str | None = None
    error: str | None = None

class GenerateBatchResponse(BaseModel):
    results: list[BatchResultItem]

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

def _update_scene_image_url_b(
    session: Session, script_id: str, scene_id: str, image_url_b: str
) -> None:
    """Persist image_url_b into the scene inside script_json."""
    record = session.get(Script, script_id)
    if not record:
        return
    content = ScriptContent.model_validate(json.loads(record.script_json))
    for seg in content.segments:
        for scene in seg.scenes:
            if scene.id == scene_id:
                scene.image_url_b = image_url_b
                break
    record.script_json = content.model_dump_json()
    session.add(record)
    session.commit()

# --- Endpoints ---

@router.post("/generate", response_model=GenerateVisualResponse)
def generate_visual(body: GenerateVisualRequest, session: Session = Depends(get_session)):
    """Generate an image for a single scene."""
    record = session.get(Script, body.script_id)
    if not record:
        raise HTTPException(status_code=404, detail="Script not found")

    # Detect shortform format → use portrait dims and shortform style guide
    is_shortform = (record.content_format or "youtube") == "shortform"
    width = body.width if not is_shortform else 768
    height = body.height if not is_shortform else 1344
    style_guide = _SHORTFORM_STYLE_GUIDE if is_shortform else ""

    image_url, prompt_used = generate_scene_image(
        scene_id=body.scene_id,
        visual_prompt=body.visual_prompt,
        brand_style=body.brand_style,
        script_id=body.script_id,
        width=width,
        height=height,
        style_guide=style_guide,
    )

    _update_scene_image_url(session, body.script_id, body.scene_id, image_url)

    image_url_b = None
    if body.is_animated and body.visual_prompt_b:
        image_url_b, _ = generate_scene_image(
            scene_id=body.scene_id,
            visual_prompt=body.visual_prompt_b,
            brand_style=body.brand_style,
            script_id=body.script_id,
            width=width,
            height=height,
            variant="b",
            style_guide=style_guide,
        )
        _update_scene_image_url_b(session, body.script_id, body.scene_id, image_url_b)

    return GenerateVisualResponse(image_url=image_url, prompt_used=prompt_used, image_url_b=image_url_b)

@router.post("/generate-batch", response_model=GenerateBatchResponse)
def generate_visual_batch(body: GenerateBatchRequest, session: Session = Depends(get_session)):
    """Generate images for multiple scenes sequentially."""
    record = session.get(Script, body.script_id)
    if not record:
        raise HTTPException(status_code=404, detail="Script not found")

    # Detect shortform format
    is_shortform = (record.content_format or "youtube") == "shortform"
    width = body.width if not is_shortform else 768
    height = body.height if not is_shortform else 1344
    style_guide = _SHORTFORM_STYLE_GUIDE if is_shortform else ""

    scenes = [
        {
            "scene_id": s.scene_id,
            "visual_prompt": s.visual_prompt,
            "is_animated": s.is_animated,
            "visual_prompt_b": s.visual_prompt_b,
        }
        for s in body.scenes
    ]

    results = generate_batch(
        scenes=scenes,
        brand_style=body.brand_style,
        script_id=body.script_id,
        width=width,
        height=height,
        style_guide=style_guide,
    )

    # Persist successful image URLs
    for r in results:
        if r["image_url"]:
            _update_scene_image_url(session, body.script_id, r["scene_id"], r["image_url"])
        if r.get("image_url_b"):
            _update_scene_image_url_b(session, body.script_id, r["scene_id"], r["image_url_b"])

    return GenerateBatchResponse(results=[BatchResultItem(**r) for r in results])
