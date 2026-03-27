"""Publish record models — tracks upload history to platforms."""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Optional

from pydantic import BaseModel
from sqlmodel import Column, Field, SQLModel, Text


class PublishRecord(SQLModel, table=True):
    """Tracks each publish/upload to a platform."""

    __tablename__ = "publish_records"

    id: str = Field(default_factory=lambda: uuid.uuid4().hex, primary_key=True)
    script_id: str = Field(index=True)
    brand_id: str = Field(index=True)
    platform: str = Field(default="youtube")  # youtube | tiktok | instagram
    status: str = Field(default="pending")  # pending | uploading | scheduled | published | failed
    platform_content_id: str = Field(default="")
    platform_url: str = Field(default="")
    file_path: str = Field(default="", sa_column=Column(Text))
    metadata_json: str = Field(default="{}", sa_column=Column(Text))
    schedule_at: Optional[datetime] = Field(default=None)
    published_at: Optional[datetime] = Field(default=None)
    error: str = Field(default="", sa_column=Column(Text))
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class PublishRecordRead(BaseModel):
    """Public-facing publish record."""

    id: str
    script_id: str
    brand_id: str
    platform: str
    status: str
    platform_content_id: str
    platform_url: str
    schedule_at: Optional[datetime]
    published_at: Optional[datetime]
    error: str
    created_at: datetime
