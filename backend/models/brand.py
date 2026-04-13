"""Brand profile data models."""

import json
import uuid
from datetime import datetime, timezone

from pydantic import BaseModel
from sqlmodel import Field, SQLModel


class EliPosition(BaseModel):
    """Position of the Eli overlay in 1920×1080 pixel space (top-left origin)."""

    x: int = 1410  # 1920 - 480 - 30
    y: int = 720   # 1080 - 270 - 90


class BrandProfileBase(SQLModel):
    """Shared fields for brand profiles."""

    name: str = Field(index=True)
    voice_id: str = Field(default="")  # ElevenLabs voice ID
    eli_position_json: str = Field(default="")  # JSON-serialized EliPosition
    # DEPRECATED fields — kept for DB compat with existing tables, unused
    art_style: str | None = Field(default=None)
    color_palette: str = Field(default="")
    font: str = Field(default="")
    style_string: str | None = Field(default=None)
    content_modifiers: str = Field(default="")
    youtube_channel_id: str = Field(default="")

class BrandProfile(BrandProfileBase, table=True):
    """Persistent brand profile stored in SQLite."""

    __tablename__ = "brand_profiles"

    id: str = Field(default_factory=lambda: uuid.uuid4().hex, primary_key=True)
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

class BrandProfileUpdate(BaseModel):
    """Request body for updating the default brand. All fields optional."""

    name: str | None = None
    voice_id: str | None = None
    youtube_channel_id: str | None = None
    eli_position: EliPosition | None = None

class BrandProfileRead(BaseModel):
    """Response body for a brand profile."""

    id: str
    name: str
    voice_id: str
    youtube_channel_id: str
    eli_position: EliPosition | None = None
    created_at: datetime
    updated_at: datetime
