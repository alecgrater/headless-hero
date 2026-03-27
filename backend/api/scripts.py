"""Endpoints for AI-powered script generation."""

from __future__ import annotations

import json

from fastapi import APIRouter, Depends, HTTPException
from sqlmodel import Session

from api.database import get_session
from models.brand import BrandProfile
from models.script import (
    GenerateScriptRequest,
    GenerateScriptResponse,
    Script,
    ScriptContent,
    ScriptRead,
    UpdateScriptRequest,
)
from pipeline.scriptwriter import generate_script

router = APIRouter(prefix="/api/scripts", tags=["scripts"])


@router.post("/generate", response_model=GenerateScriptResponse)
def generate(body: GenerateScriptRequest, session: Session = Depends(get_session)):
    brand = session.get(BrandProfile, body.brand_id)
    if not brand:
        raise HTTPException(status_code=404, detail="Brand not found")

    # Build brand context string
    parts = [brand.name]
    if brand.art_style:
        parts.append(f"Art style: {brand.art_style}")
    brand_context = ". ".join(parts)

    script_content = generate_script(
        topic=body.topic,
        description=body.description,
        brand_context=brand_context,
        segment_count=body.segment_count,
    )

    # Persist to SQLite
    record = Script(
        brand_id=body.brand_id,
        topic_title=body.topic,
        topic_description=body.description,
        script_json=script_content.model_dump_json(),
    )
    session.add(record)
    session.commit()
    session.refresh(record)

    return GenerateScriptResponse(id=record.id, script=script_content)


@router.put("/{script_id}", response_model=ScriptRead)
def update_script(script_id: str, body: UpdateScriptRequest, session: Session = Depends(get_session)):
    record = session.get(Script, script_id)
    if not record:
        raise HTTPException(status_code=404, detail="Script not found")

    record.script_json = body.script.model_dump_json()
    session.add(record)
    session.commit()
    session.refresh(record)

    return ScriptRead(
        id=record.id,
        brand_id=record.brand_id,
        topic_title=record.topic_title,
        topic_description=record.topic_description,
        script=body.script,
        created_at=record.created_at,
    )


@router.get("/{script_id}", response_model=ScriptRead)
def get_script(script_id: str, session: Session = Depends(get_session)):
    record = session.get(Script, script_id)
    if not record:
        raise HTTPException(status_code=404, detail="Script not found")

    script_content = ScriptContent.model_validate(json.loads(record.script_json))
    return ScriptRead(
        id=record.id,
        brand_id=record.brand_id,
        topic_title=record.topic_title,
        topic_description=record.topic_description,
        script=script_content,
        created_at=record.created_at,
    )
