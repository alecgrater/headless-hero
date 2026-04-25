"""PostIt model for persistent video idea notes with priority ranking."""

import uuid
from datetime import datetime, timezone

from sqlmodel import Field, SQLModel


class PostIt(SQLModel, table=True):
    __tablename__ = "postits"

    id: str = Field(default_factory=lambda: uuid.uuid4().hex, primary_key=True)
    text: str
    rank: int = Field(default=50)
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
