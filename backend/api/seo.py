"""Endpoints for SEO metadata generation."""

from __future__ import annotations

import json
from typing import List

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlmodel import Session

from api.database import get_session
from models.script import Script, ScriptContent
from pipeline.seo import SEOMetadata, generate_seo

router = APIRouter(prefix="/api/seo", tags=["seo"])


class GenerateSEORequest(BaseModel):
    script_id: str


class GenerateSEOResponse(BaseModel):
    metadata: SEOMetadata


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
