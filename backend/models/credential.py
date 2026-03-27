"""Platform OAuth credential models."""

import uuid
from datetime import datetime, timezone

from pydantic import BaseModel
from sqlmodel import Column, Field, SQLModel, Text

class PlatformCredential(SQLModel, table=True):
    """Stores OAuth tokens for connected platforms (e.g. YouTube)."""

    __tablename__ = "platform_credentials"

    id: str = Field(default_factory=lambda: uuid.uuid4().hex, primary_key=True)
    brand_id: str = Field(index=True)
    platform: str = Field(index=True)  # "youtube"
    access_token: str = Field(default="", sa_column=Column(Text))
    refresh_token: str = Field(default="", sa_column=Column(Text))
    token_expiry: datetime | None = Field(default=None)
    scope: str = Field(default="")
    platform_user_id: str = Field(default="")
    platform_user_name: str = Field(default="")
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

class PlatformCredentialRead(BaseModel):
    """Public-facing credential info (omits tokens)."""

    platform: str
    platform_user_id: str
    platform_user_name: str
    connected: bool
