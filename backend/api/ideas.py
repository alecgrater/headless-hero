"""Endpoints for AI-powered idea generation."""

import logging
import time

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field
from sqlmodel import Session

from database import get_default_brand_id, get_session
from models.brand import BrandProfile
from models.generation_duration import GenerationDuration
from pipeline.ideation import VideoIdea, generate_ideas

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/ideas", tags=["ideas"])

class GenerateIdeasRequest(BaseModel):
    niche: str = Field(..., min_length=1, description="Topic area to brainstorm")
    guide: str | None = Field(default=None, description="Optional creator guidance for the idea angle")
    count: int = Field(default=10, ge=1, le=20)
    exclude_titles: list[str] = Field(default=[], description="Titles to exclude for dedup on Load More")
    format_id: str = Field(default="youtube-listicle", description="Video format ID (e.g. youtube-listicle, life-as-a)")

class GenerateIdeasResponse(BaseModel):
    ideas: list[VideoIdea]

@router.post("/generate", response_model=GenerateIdeasResponse)
def generate(body: GenerateIdeasRequest, session: Session = Depends(get_session)):
    logger.info("Idea generation requested: niche=%r, count=%d", body.niche, body.count)
    brand_id = get_default_brand_id(session)
    brand = session.get(BrandProfile, brand_id)
    brand_context = brand.name if brand else None

    logger.info("Generating %d ideas for niche %s", body.count, body.niche)
    t0 = time.monotonic()
    ideas = generate_ideas(
        niche=body.niche,
        guide=body.guide,
        count=body.count,
        brand_context=brand_context,
        exclude_titles=body.exclude_titles,
        format_id=body.format_id,
    )
    duration = time.monotonic() - t0
    session.add(GenerationDuration(operation_type="idea_generation", duration_seconds=duration))
    session.commit()

    logger.info("Generated %d ideas in %.1fs", len(ideas), duration)
    return GenerateIdeasResponse(ideas=ideas)
