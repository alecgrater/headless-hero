"""Script data models — matches PRD section 7.2 JSON structure."""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import List, Optional

from pydantic import BaseModel, Field as PydanticField
from sqlmodel import Column, Field, SQLModel, Text


# --- Pydantic models for the script JSON structure ---


class Scene(BaseModel):
    """A single scene within a segment."""

    id: str
    narration: str
    visual_prompt: str
    text_overlay: str = ""
    duration_estimate_seconds: float = 8.0
    is_title_card: bool = False
    image_url: str = ""


class Segment(BaseModel):
    """A named segment (e.g. "Caffeine") containing multiple scenes."""

    name: str
    scenes: List[Scene]


class ScriptContent(BaseModel):
    """The full script payload matching PRD section 7.2."""

    title: str
    segments: List[Segment]
    intro_hook: str = ""
    outro_cta: str = ""


# --- SQLModel table for persistence ---


class Script(SQLModel, table=True):
    """Persisted script stored in SQLite."""

    __tablename__ = "scripts"

    id: str = Field(default_factory=lambda: uuid.uuid4().hex, primary_key=True)
    brand_id: str = Field(index=True)
    topic_title: str = Field(default="")
    topic_description: str = Field(default="", sa_column=Column(Text))
    script_json: str = Field(default="{}", sa_column=Column(Text))  # serialised ScriptContent
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


# --- Request / response schemas ---


class GenerateScriptRequest(BaseModel):
    topic: str = PydanticField(..., min_length=1, description="Video topic / title")
    description: str = PydanticField(default="", description="Optional topic description or angle")
    brand_id: str = PydanticField(..., description="Brand profile ID for style context")
    segment_count: Optional[int] = PydanticField(
        default=None, ge=2, le=30, description="Desired number of segments (Claude decides if omitted)"
    )


class GenerateScriptResponse(BaseModel):
    id: str
    script: ScriptContent


class UpdateScriptRequest(BaseModel):
    script: ScriptContent


class ScriptRead(BaseModel):
    id: str
    brand_id: str
    topic_title: str
    topic_description: str
    script: ScriptContent
    created_at: datetime
