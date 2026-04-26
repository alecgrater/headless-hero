"""Idea model for persistent video idea notes with priority ranking and hook scoring."""

import uuid
from datetime import datetime, timezone

from sqlmodel import Field, SQLModel


VALID_STATUSES = {"idea", "in_progress", "scripted", "published"}
VALID_SOURCES = {"manual", "for_you", "trending"}
VALID_COLD_OPEN_STATUSES = {"pending", "generating", "ready", "refining", "scored", "failed"}


class Idea(SQLModel, table=True):
    __tablename__ = "ideas"

    id: str = Field(default_factory=lambda: uuid.uuid4().hex, primary_key=True)
    text: str
    description: str = Field(default="")
    category: str = Field(default="")
    rank: int = Field(default=50)
    status: str = Field(default="idea")
    source: str = Field(default="manual")
    cold_open_status: str = Field(default="pending")
    cold_open_job_id: str = Field(default="")
    cold_open_variants_json: str = Field(default="")
    selected_hook_json: str = Field(default="")
    hook_score: int | None = Field(default=None)
    hook_score_json: str = Field(default="")
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
