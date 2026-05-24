"""Preset-scoped main character models."""

from datetime import datetime, timezone

from pydantic import BaseModel
from sqlmodel import Field, SQLModel


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


class StylePresetCharacter(SQLModel, table=True):
    __tablename__ = "style_preset_characters"

    id: str = Field(primary_key=True)
    style_preset_id: str = Field(index=True)
    name: str = Field(default="")
    appearance: str = Field(default="")
    vibe: str = Field(default="")
    reference_image_url: str = Field(default="")
    cutout_image_url: str = Field(default="")
    created_at: datetime = Field(default_factory=_utcnow)


class CreateStylePresetCharacterRequest(BaseModel):
    name: str
    appearance: str
    vibe: str = ""


class StylePresetCharacterResponse(BaseModel):
    id: str
    style_preset_id: str
    name: str
    appearance: str
    vibe: str
    reference_image_url: str
    cutout_image_url: str = ""
    created_at: datetime
    active: bool = False
