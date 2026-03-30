"""Endpoints for AI image generation via Google Gemini."""

import json
import time
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlmodel import Session

from api.database import get_session
from models.brand import BrandProfile
from models.script import Script, ScriptContent
from pipeline.image_gen import generate_batch, generate_scene_frames, generate_scene_image
from pipeline.title_card import ensure_title_card_images

router = APIRouter(prefix="/api/visuals", tags=["visuals"])

# Load shortform style guide once
_SHORTFORM_GUIDE_PATH = Path(__file__).resolve().parent.parent / "prompts" / "shortform_image_gen_guide.md"
_SHORTFORM_STYLE_GUIDE = _SHORTFORM_GUIDE_PATH.read_text() if _SHORTFORM_GUIDE_PATH.exists() else ""

# --- Request / Response schemas ---

class GenerateVisualRequest(BaseModel):
    script_id: str
    scene_id: str
    visual_prompt: str
    width: int = 1344
    height: int = 768
    is_animated: bool = False
    visual_prompt_b: str = ""
    frame_prompts: list[str] = []
    frame_seed: int | None = None

class GenerateVisualResponse(BaseModel):
    image_url: str
    prompt_used: str
    image_url_b: str | None = None
    frame_urls: list[str] = []

class BatchScene(BaseModel):
    scene_id: str
    visual_prompt: str
    is_animated: bool = False
    visual_prompt_b: str = ""
    frame_prompts: list[str] = []
    frame_seed: int | None = None

class GenerateBatchRequest(BaseModel):
    script_id: str
    scenes: list[BatchScene]
    width: int = 1344
    height: int = 768

class BatchResultItem(BaseModel):
    scene_id: str
    image_url: str | None = None
    image_url_b: str | None = None
    frame_urls: list[str] = []
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

def _update_scene_frame_urls(
    session: Session, script_id: str, scene_id: str, frame_urls: list[str]
) -> None:
    """Persist frame_urls into the scene inside script_json."""
    record = session.get(Script, script_id)
    if not record:
        return
    content = ScriptContent.model_validate(json.loads(record.script_json))
    for seg in content.segments:
        for scene in seg.scenes:
            if scene.id == scene_id:
                scene.frame_urls = frame_urls
                # Also set image_url to first frame for backward compat
                if frame_urls:
                    scene.image_url = frame_urls[0]
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

    # Load brand style_string
    brand = session.get(BrandProfile, record.brand_id)
    brand_style_string = brand.style_string if brand else ""

    # Multi-frame path
    if body.frame_prompts:
        frame_results = generate_scene_frames(
            scene_id=body.scene_id,
            frame_prompts=body.frame_prompts,
            script_id=body.script_id,
            visual_prompt=body.visual_prompt,
            width=width,
            height=height,
            style_guide=style_guide,
            seed=body.frame_seed,
            style_string=brand_style_string,
        )
        frame_urls = [url for url, _ in frame_results]
        _update_scene_frame_urls(session, body.script_id, body.scene_id, frame_urls)
        return GenerateVisualResponse(
            image_url=frame_urls[0] if frame_urls else "",
            prompt_used=frame_results[0][1] if frame_results else "",
            frame_urls=frame_urls,
        )

    # Legacy single-image path
    image_url, prompt_used = generate_scene_image(
        scene_id=body.scene_id,
        visual_prompt=body.visual_prompt,
        script_id=body.script_id,
        width=width,
        height=height,
        style_guide=style_guide,
        style_string=brand_style_string,
    )

    _update_scene_image_url(session, body.script_id, body.scene_id, image_url)

    image_url_b = None
    if body.is_animated and body.visual_prompt_b:
        image_url_b, _ = generate_scene_image(
            scene_id=body.scene_id,
            visual_prompt=body.visual_prompt_b,
            script_id=body.script_id,
            width=width,
            height=height,
            variant="b",
            style_guide=style_guide,
            style_string=brand_style_string,
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

    # Load brand style_string
    brand = session.get(BrandProfile, record.brand_id)
    brand_style_string = brand.style_string if brand else ""

    scenes = [
        {
            "scene_id": s.scene_id,
            "visual_prompt": s.visual_prompt,
            "is_animated": s.is_animated,
            "visual_prompt_b": s.visual_prompt_b,
            "frame_prompts": s.frame_prompts,
            "frame_seed": s.frame_seed,
        }
        for s in body.scenes
    ]

    results = generate_batch(
        scenes=scenes,
        script_id=body.script_id,
        width=width,
        height=height,
        style_guide=style_guide,
        style_string=brand_style_string,
    )

    # Persist successful image URLs
    for r in results:
        frame_urls = r.get("frame_urls", [])
        if frame_urls:
            _update_scene_frame_urls(session, body.script_id, r["scene_id"], frame_urls)
        elif r["image_url"]:
            _update_scene_image_url(session, body.script_id, r["scene_id"], r["image_url"])
        if r.get("image_url_b"):
            _update_scene_image_url_b(session, body.script_id, r["scene_id"], r["image_url_b"])

    return GenerateBatchResponse(results=[BatchResultItem(**r) for r in results])


# --- Title card generation ---

class GenerateTitleCardsRequest(BaseModel):
    script_id: str
    force: bool = False

class GenerateTitleCardsResponse(BaseModel):
    generated_scene_ids: list[str]
    image_urls: dict[str, str]

@router.post("/generate-title-cards", response_model=GenerateTitleCardsResponse)
def generate_title_cards(body: GenerateTitleCardsRequest, session: Session = Depends(get_session)):
    """Generate programmatic title card images for all title card scenes in a script."""
    record = session.get(Script, body.script_id)
    if not record:
        raise HTTPException(status_code=404, detail="Script not found")

    content = ScriptContent.model_validate(json.loads(record.script_json))

    # Load brand style_string for title card image generation
    brand = session.get(BrandProfile, record.brand_id)
    brand_style_string = brand.style_string if brand else ""

    # Detect shortform dimensions
    is_shortform = (record.content_format or "youtube") == "shortform"
    width = 768 if is_shortform else 1920
    height = 1344 if is_shortform else 1080

    generated_ids = ensure_title_card_images(
        script_id=body.script_id,
        content=content,
        style_string=brand_style_string,
        force=body.force,
    )

    # Persist updated image_urls back to script_json (with cache-buster for frontend)
    cache_buster = f"?t={int(time.time())}"
    image_urls: dict[str, str] = {}
    for seg in content.segments:
        for scene in seg.scenes:
            if scene.is_title_card and scene.image_url:
                image_urls[scene.id] = scene.image_url + cache_buster

    record.script_json = content.model_dump_json()
    session.add(record)
    session.commit()

    return GenerateTitleCardsResponse(
        generated_scene_ids=generated_ids,
        image_urls=image_urls,
    )
