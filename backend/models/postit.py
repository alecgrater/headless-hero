"""PostIt model for persistent video idea notes with priority ranking."""

import uuid
from datetime import datetime, timezone

from sqlmodel import Field, SQLModel


VALID_STATUSES = {"idea", "in_progress", "scripted", "published"}
VALID_SOURCES = {"manual", "for_you", "trending"}


class PostIt(SQLModel, table=True):
    __tablename__ = "postits"

    id: str = Field(default_factory=lambda: uuid.uuid4().hex, primary_key=True)
    text: str
    rank: int = Field(default=50)
    status: str = Field(default="idea")
    source: str = Field(default="manual")
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
