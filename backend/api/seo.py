"""Endpoints for SEO metadata generation."""

import json

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlmodel import Session

from api.database import get_session
from models.script import Script, ScriptContent
from pipeline.seo import SEOMetadata, ShortformSEOMetadata, generate_seo, generate_shortform_seo

router = APIRouter(prefix="/api/seo", tags=["seo"])

class GenerateSEORequest(BaseModel):
    script_id: str

class GenerateSEOResponse(BaseModel):
    metadata: SEOMetadata

class GenerateShortformSEORequest(BaseModel):
    script_id: str
    platforms: list[str] = ["youtube_shorts", "tiktok", "instagram_reels"]

class GenerateShortformSEOResponse(BaseModel):
    metadata: ShortformSEOMetadata

@router.post("/generate", response_model=GenerateSEOResponse)
def generate_seo_metadata(body: GenerateSEORequest, session: Session = Depends(get_session)):
    """Generate SEO metadata for all platforms."""
    record = session.get(Script, body.script_id)
    if not record:
        raise HTTPException(status_code=404, detail="Script not found")

    content = ScriptContent.model_validate(json.loads(record.script_json))
    segment_names = [seg.name for seg in content.segments]

    metadata = generate_seo(
        video_title=content.title,
        segments=segment_names,
        video_description=record.topic_description,
    )

    return GenerateSEOResponse(metadata=metadata)

@router.post("/generate-shortform", response_model=GenerateShortformSEOResponse)
def generate_shortform_seo_metadata(body: GenerateShortformSEORequest, session: Session = Depends(get_session)):
    """Generate short-form SEO metadata for selected platforms."""
    record = session.get(Script, body.script_id)
    if not record:
        raise HTTPException(status_code=404, detail="Script not found")

    content = ScriptContent.model_validate(json.loads(record.script_json))

    # Collect all narration text
    narration = " ".join(
        scene.narration
        for seg in content.segments
        for scene in seg.scenes
        if scene.narration
    )

    metadata = generate_shortform_seo(
        title=content.title,
        narration_text=narration,
        platforms=body.platforms,
    )

    return GenerateShortformSEOResponse(metadata=metadata)
