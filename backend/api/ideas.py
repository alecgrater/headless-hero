"""Endpoints for AI-powered idea generation."""

import logging
import time

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlmodel import Session

from api.database import get_session
from models.brand import BrandProfile
from models.generation_duration import GenerationDuration
from pipeline.ideation import VideoIdea, generate_ideas

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/ideas", tags=["ideas"])

class GenerateIdeasRequest(BaseModel):
    niche: str = Field(..., min_length=1, description="Topic area to brainstorm")
    count: int = Field(default=10, ge=1, le=20)
    brand_id: str | None = Field(default=None, description="Optional brand for context")
    exclude_titles: list[str] = Field(default=[], description="Titles to exclude for dedup on Load More")

class GenerateIdeasResponse(BaseModel):
    ideas: list[VideoIdea]

@router.post("/generate", response_model=GenerateIdeasResponse)
def generate(body: GenerateIdeasRequest, session: Session = Depends(get_session)):
    brand_context = None
    if body.brand_id:
        brand = session.get(BrandProfile, body.brand_id)
        if not brand:
            raise HTTPException(status_code=404, detail="Brand not found")
        parts = [brand.name]
        if brand.art_style:
            parts.append(f"Art style: {brand.art_style}")
        brand_context = ". ".join(parts)

    logger.info("Generating %d ideas for niche %s", body.count, body.niche)
    t0 = time.monotonic()
    ideas = generate_ideas(
        niche=body.niche,
        count=body.count,
        brand_context=brand_context,
        exclude_titles=body.exclude_titles,
    )
    duration = time.monotonic() - t0
    session.add(GenerationDuration(operation_type="idea_generation", duration_seconds=duration))
    session.commit()

    logger.info("Generated %d ideas in %.1fs", len(ideas), duration)
    return GenerateIdeasResponse(ideas=ideas)
