"""ContentProfile model for storing analyzed creator content style."""

import uuid
from datetime import datetime, timezone

from sqlalchemy import Column, Text
from sqlmodel import Field, SQLModel


class ContentProfile(SQLModel, table=True):
    __tablename__ = "content_profiles"

    id: str = Field(default_factory=lambda: uuid.uuid4().hex, primary_key=True)
    script_count: int = Field(default=0)
    common_topics: str = Field(default="[]", sa_column=Column(Text))  # JSON list[str]
    narration_style: str = Field(default="")
    visual_approach: str = Field(default="")
    typical_keywords: str = Field(default="[]", sa_column=Column(Text))  # JSON list[str]
    audience_profile: str = Field(default="")
    avg_segment_count: float = Field(default=0.0)
    analyzed_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
