"""Model for tracking external API usage and estimated costs."""

import uuid
from datetime import datetime, timezone

from sqlmodel import Field, SQLModel


class ApiUsage(SQLModel, table=True):
    __tablename__ = "api_usage"

    id: str = Field(default_factory=lambda: uuid.uuid4().hex, primary_key=True)
    service: str = Field(index=True)           # "anthropic", "google_ai", "replicate", "elevenlabs"
    operation: str = ""                         # "chat", "image_gen", "tts", "voice_clone", etc.
    model: str = ""                             # model name used
    input_tokens: int = 0                       # for LLMs
    output_tokens: int = 0                      # for LLMs
    characters: int = 0                         # for TTS
    images: int = 0                             # for image gen
    cost_estimate: float = 0.0                  # estimated USD cost
    metadata_json: str = ""                     # optional extra info as JSON
    script_id: str | None = Field(default=None, index=True)  # attribute cost to a video
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
