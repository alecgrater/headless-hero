"""Endpoints for SEO metadata generation."""

import json
import logging
import time

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlmodel import Session

from database import get_session
from models.brand import BrandProfile
from models.generation_duration import GenerationDuration
from models.script import Script, ScriptContent
from pipeline.seo import SEOMetadata, generate_seo, format_timestamp

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/seo", tags=["seo"])

class GenerateSEORequest(BaseModel):
    script_id: str

class GenerateSEOResponse(BaseModel):
    metadata: SEOMetadata

@router.post("/generate", response_model=GenerateSEOResponse)
def generate_seo_metadata(body: GenerateSEORequest, session: Session = Depends(get_session)):
    """Generate SEO metadata for all platforms."""
    t0 = time.monotonic()
    logger.info("Generating SEO metadata for script %s", body.script_id)
    record = session.get(Script, body.script_id)
    if not record:
        raise HTTPException(status_code=404, detail="Script not found")

    content = ScriptContent.model_validate(json.loads(record.script_json))

    # Compute cumulative timestamps from scene audio durations
    segments: list[tuple[str, str]] = []
    elapsed = 0.0
    for seg in content.segments:
        segments.append((seg.name, format_timestamp(elapsed)))
        for scene in seg.scenes:
            elapsed += scene.audio_duration_seconds

    # Build brand context for SEO generation
    brand = session.get(BrandProfile, record.brand_id)
    brand_context = ""
    if brand:
        brand_context = brand.name

    metadata = generate_seo(
        video_title=content.title,
        segments=segments,
        video_description=record.topic_description,
        brand_context=brand_context,
        script_id=body.script_id,
    )

    # Persist SEO metadata in the script JSON blob
    content.seo_metadata = metadata.model_dump()
    record.script_json = content.model_dump_json()
    session.add(record)
    session.commit()

    logger.info("SEO metadata generated for script %s", body.script_id)

    duration = time.monotonic() - t0
    session.add(GenerationDuration(operation_type="seo_generation", duration_seconds=duration))
    session.commit()

    return GenerateSEOResponse(metadata=metadata)
