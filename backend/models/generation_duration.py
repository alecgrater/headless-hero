"""Model for tracking AI generation durations."""

import uuid
from datetime import datetime, timezone

from pydantic import BaseModel
from sqlmodel import Field, SQLModel


class GenerationDuration(SQLModel, table=True):
    __tablename__ = "generation_durations"

    id: str = Field(default_factory=lambda: uuid.uuid4().hex, primary_key=True)
    operation_type: str = Field(index=True)
    duration_seconds: float
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class GenerationEstimateResponse(BaseModel):
    operation_type: str
    average_seconds: float | None
    sample_count: int
