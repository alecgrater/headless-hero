"""Endpoints for thumbnail generation."""

import json

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlmodel import Session

from api.database import get_session
from models.script import Script, ScriptContent
from pipeline.thumbnail import generate_concepts, generate_thumbnail

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
