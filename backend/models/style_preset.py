"""StylePreset SQLModel + Pydantic schemas.

A style preset is a single 16:9 reference image generated from a free-form
user prompt. The image lives on disk at data/style/presets/<id>.png and is
attached as a multi-modal Part to Gemini image-generation calls when the
active project has Eli disabled and style_preset_enabled set to True.
"""

from datetime import datetime, timezone

from pydantic import BaseModel
from sqlmodel import Field, SQLModel


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


class StylePreset(SQLModel, table=True):
    __tablename__ = "style_presets"

    id: str = Field(primary_key=True)
    name: str = Field(default="")
    prompt: str = Field(default="")
    created_at: datetime = Field(default_factory=_utcnow)


class StylePresetResponse(BaseModel):
    id: str
    name: str
    prompt: str
    image_url: str
    created_at: datetime


class CreateStylePresetRequest(BaseModel):
    prompt: str
    name: str = ""


class GeneratePresetJobResponse(BaseModel):
    job_id: str


class SetActivePresetRequest(BaseModel):
    preset_id: str | None = None
