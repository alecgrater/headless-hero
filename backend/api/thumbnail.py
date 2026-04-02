"""Endpoints for thumbnail generation."""

import json
import logging

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlmodel import Session

from database import get_session
from models.brand import BrandProfile
from models.script import Script, ScriptContent
from pipeline.thumbnail import generate_concepts, generate_thumbnail, get_composite_thumbnail

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/thumbnail", tags=["thumbnail"])

class GenerateThumbnailRequest(BaseModel):
    script_id: str
    brand_style: str = ""
    bar_color: str = "0x9333EA"
    count: int = 3
    title: str = ""

class ThumbnailConceptResult(BaseModel):
    idx: int
    title_text: str
    visual_description: str
    image_url: str | None = None
    error: str | None = None

class GenerateThumbnailResponse(BaseModel):
    concepts: list[ThumbnailConceptResult]

@router.post("/generate", response_model=GenerateThumbnailResponse)
def generate_thumbnails(body: GenerateThumbnailRequest, session: Session = Depends(get_session)):
    """Generate thumbnail concepts via Claude, render them via Gemini + FFmpeg."""
    logger.info("Generating thumbnails for script %s (count=%d)", body.script_id, body.count)
    record = session.get(Script, body.script_id)
    if not record:
        raise HTTPException(status_code=404, detail="Script not found")

    content = ScriptContent.model_validate(json.loads(record.script_json))

    # Check if a composite title card exists (from title_cards modifier)
    # If so, use it as the primary thumbnail
    brand = session.get(BrandProfile, record.brand_id)
    modifier_ids = json.loads(brand.content_modifiers) if brand and brand.content_modifiers else []
    if "title_cards" in modifier_ids:
        composite_url = get_composite_thumbnail(body.script_id)
        if composite_url:
            logger.info("Using composite title card thumbnail for script %s", body.script_id)
            results = [ThumbnailConceptResult(
                idx=0,
                title_text=content.card_title or content.title,
                visual_description="Composite grid title card (auto-generated from segments)",
                image_url=composite_url,
            )]
            return GenerateThumbnailResponse(concepts=results)

    # Use default system font for thumbnail text rendering
    font_family = ""

    # Generate concepts from Claude
    concepts = generate_concepts(
        video_title=content.title,
        count=body.count,
    )

    # Render each concept
    results: list[ThumbnailConceptResult] = []
    for i, concept in enumerate(concepts):
        try:
            image_url = generate_thumbnail(
                script_id=body.script_id,
                idx=i,
                visual_description=concept.visual_description,
                title_text=concept.title_text,
                brand_style=body.brand_style,
                bar_color=body.bar_color,
                title=body.title,
                font_family=font_family,
            )
            results.append(ThumbnailConceptResult(
                idx=i,
                title_text=concept.title_text,
                visual_description=concept.visual_description,
                image_url=image_url,
            ))
        except Exception as exc:
            logger.exception("Failed to render thumbnail concept %d for script %s", i, body.script_id)
            results.append(ThumbnailConceptResult(
                idx=i,
                title_text=concept.title_text,
                visual_description=concept.visual_description,
                error=str(exc),
            ))

    logger.info("Thumbnail generation complete for script %s: %d concepts rendered", body.script_id, len(results))
    return GenerateThumbnailResponse(concepts=results)
