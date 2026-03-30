"""Endpoints for SEO metadata generation."""

import json
import logging

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlmodel import Session

from api.database import get_session
from models.brand import BrandProfile
from models.script import Script, ScriptContent
from pipeline.seo import SEOMetadata, generate_seo

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/seo", tags=["seo"])

class GenerateSEORequest(BaseModel):
    script_id: str

class GenerateSEOResponse(BaseModel):
    metadata: SEOMetadata

@router.post("/generate", response_model=GenerateSEOResponse)
def generate_seo_metadata(body: GenerateSEORequest, session: Session = Depends(get_session)):
    """Generate SEO metadata for all platforms."""
    logger.info("Generating SEO metadata for script %s", body.script_id)
    record = session.get(Script, body.script_id)
    if not record:
        raise HTTPException(status_code=404, detail="Script not found")

    content = ScriptContent.model_validate(json.loads(record.script_json))
    segment_names = [seg.name for seg in content.segments]

    # Build brand context for SEO generation
    brand = session.get(BrandProfile, record.brand_id)
    brand_context = ""
    if brand:
        parts = [brand.name]
        if brand.art_style:
            parts.append(f"Art style: {brand.art_style}")
        brand_context = ". ".join(parts)

    metadata = generate_seo(
        video_title=content.title,
        segments=segment_names,
        video_description=record.topic_description,
        brand_context=brand_context,
    )

    logger.info("SEO metadata generated for script %s", body.script_id)
    return GenerateSEOResponse(metadata=metadata)
