"""Endpoints for thumbnail generation."""

import json

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlmodel import Session

from api.database import get_session
from models.brand import BrandProfile
from models.script import Script, ScriptContent
from pipeline.thumbnail import generate_concepts, generate_shortform_thumbnail, generate_thumbnail, get_composite_thumbnail

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
            results = [ThumbnailConceptResult(
                idx=0,
                title_text=content.card_title or content.title,
                visual_description="Composite grid title card (auto-generated from segments)",
                image_url=composite_url,
            )]
            return GenerateThumbnailResponse(concepts=results)

    # Load brand font for thumbnail text rendering
    font_family = brand.font if brand else ""

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
            results.append(ThumbnailConceptResult(
                idx=i,
                title_text=concept.title_text,
                visual_description=concept.visual_description,
                error=str(exc),
            ))

    return GenerateThumbnailResponse(concepts=results)


@router.post("/generate-shortform", response_model=GenerateThumbnailResponse)
def generate_shortform_thumbnails(body: GenerateThumbnailRequest, session: Session = Depends(get_session)):
    """Generate portrait 9:16 thumbnail concepts for short-form video."""
    record = session.get(Script, body.script_id)
    if not record:
        raise HTTPException(status_code=404, detail="Script not found")

    content = ScriptContent.model_validate(json.loads(record.script_json))

    concepts = generate_concepts(
        video_title=content.title,
        video_description="Short-form vertical video. Generate portrait-optimized 9:16 thumbnail concepts.",
        count=body.count,
    )

    results: list[ThumbnailConceptResult] = []
    for i, concept in enumerate(concepts):
        try:
            image_url = generate_shortform_thumbnail(
                script_id=body.script_id,
                idx=i,
                visual_description=concept.visual_description,
                title_text=concept.title_text,
                brand_style=body.brand_style,
                bar_color=body.bar_color,
                title=body.title,
            )
            results.append(ThumbnailConceptResult(
                idx=i,
                title_text=concept.title_text,
                visual_description=concept.visual_description,
                image_url=image_url,
            ))
        except Exception as exc:
            results.append(ThumbnailConceptResult(
                idx=i,
                title_text=concept.title_text,
                visual_description=concept.visual_description,
                error=str(exc),
            ))

    return GenerateThumbnailResponse(concepts=results)
