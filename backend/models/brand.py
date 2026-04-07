"""Brand profile data models."""

import uuid
from datetime import datetime, timezone

from pydantic import BaseModel
from sqlmodel import Field, SQLModel

class BrandProfileBase(SQLModel):
    """Shared fields for brand profiles."""

    name: str = Field(index=True)
    voice_id: str = Field(default="")  # ElevenLabs voice ID
    content_modifiers: str = Field(default="")  # JSON array of modifier IDs
    youtube_channel_id: str = Field(default="")

class BrandProfile(BrandProfileBase, table=True):
    """Persistent brand profile stored in SQLite."""

    __tablename__ = "brand_profiles"

    id: str = Field(default_factory=lambda: uuid.uuid4().hex, primary_key=True)
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

class BrandProfileCreate(BaseModel):
    """Request body for creating a brand profile."""

    name: str
    voice_id: str = ""
    content_modifiers: str = ""
    youtube_channel_id: str = ""

class BrandProfileUpdate(BaseModel):
    """Request body for updating a brand profile. All fields optional."""

    name: str | None = None
    voice_id: str | None = None
    content_modifiers: str | None = None
    youtube_channel_id: str | None = None

class BrandProfileRead(BrandProfileBase):
    """Response body for a brand profile."""

    id: str
    created_at: datetime
    updated_at: datetime
