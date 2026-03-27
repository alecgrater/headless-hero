"""Brand profile data models."""

import uuid
from datetime import datetime, timezone
from typing import Optional

from pydantic import BaseModel
from sqlmodel import Column, Field, SQLModel, Text


class BrandProfileBase(SQLModel):
    """Shared fields for brand profiles."""

    name: str = Field(index=True)
    art_style: str = Field(default="", sa_column=Column(Text))
    color_palette: str = Field(default="")  # comma-separated hex codes
    font: str = Field(default="")
    voice_id: str = Field(default="")  # ElevenLabs voice ID
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

    name: Optional[str] = None
    art_style: Optional[str] = None
    color_palette: Optional[str] = None
    font: Optional[str] = None
    voice_id: Optional[str] = None
    youtube_channel_id: Optional[str] = None
    tiktok_handle: Optional[str] = None
    instagram_handle: Optional[str] = None


class BrandProfileRead(BrandProfileBase):
    """Response body for a brand profile."""

    id: str
    created_at: datetime
    updated_at: datetime
