"""TrendingTopic model for storing discovered trending topics."""

import uuid
from datetime import datetime, timezone

from sqlalchemy import Column, Text
from sqlmodel import Field, SQLModel


class TrendingTopic(SQLModel, table=True):
    __tablename__ = "trending_topics"

    id: str = Field(default_factory=lambda: uuid.uuid4().hex, primary_key=True)
    title: str
    source: str  # comma-separated: "youtube,reddit,google_trends"
    score: float = Field(default=0.0)
    score_breakdown: str = Field(default="{}", sa_column=Column(Text))  # JSON
    format_fit_rationale: str = Field(default="")
    raw_data: str = Field(default="{}", sa_column=Column(Text))  # JSON per-source evidence
    fetched_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    status: str = Field(default="new")  # new | dismissed | used
    is_breakout: bool = Field(default=False)
    is_first_mover: bool = Field(default=False)
    evidence_snippet: str = Field(default="")  # Human-readable trending evidence
