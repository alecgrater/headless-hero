"""Brand profile data models."""

import uuid
from datetime import datetime, timezone

from pydantic import BaseModel
from sqlmodel import Column, Field, SQLModel, Text

class BrandProfileBase(SQLModel):
    """Shared fields for brand profiles."""

    name: str = Field(index=True)
    art_style: str = Field(default="", sa_column=Column(Text))
    color_palette: str = Field(default="")  # comma-separated hex codes
    font: str = Field(default="")
    voice_id: str = Field(default="")  # ElevenLabs voice ID
    content_modifiers: str = Field(default="")  # JSON array of modifier IDs
    shortform_voice_settings: str = Field(default="")  # JSON blob for ElevenLabs overrides
    youtube_channel_id: str = Field(default="")
    tiktok_handle: str = Field(default="")
    instagram_handle: str = Field(default="")

class BrandProfile(BrandProfileBase, table=True):
    """Persistent brand profile stored in SQLite."""

    __tablename__ = "brand_profiles"

    id: str = Field(default_factory=lambda: uuid.uuid4().hex, primary_key=True)
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

class BrandProfileCreate(BrandProfileBase):
    """Request body for creating a brand profile."""

    pass

class BrandProfileUpdate(BaseModel):
    """Request body for updating a brand profile. All fields optional."""

    name: str | None = None
    art_style: str | None = None
    color_palette: str | None = None
    font: str | None = None
    voice_id: str | None = None
    content_modifiers: str | None = None
    shortform_voice_settings: str | None = None
    youtube_channel_id: str | None = None
    tiktok_handle: str | None = None
    instagram_handle: str | None = None

class BrandProfileRead(BrandProfileBase):
    """Response body for a brand profile."""

    id: str
    created_at: datetime
    updated_at: datetime
