"""Cold open A/B testing models — transient (no SQLModel table)."""

from pydantic import BaseModel, Field


class ColdOpenScores(BaseModel):
    """Quality scores for a cold open variant."""

    tension: int = Field(ge=0, le=100)
    specificity: int = Field(ge=0, le=100)
    drop_rate_risk: int = Field(ge=0, le=100)
    overall: float = 0.0
    reasoning: str = ""


class ColdOpenVariant(BaseModel):
    """A single cold open variant with hook text and scores."""

    id: str
    style: str
    intro_hook: str
    opening_narration: str
    scores: ColdOpenScores


class ColdOpenResult(BaseModel):
    """Result of generating cold open variants."""

    variants: list[ColdOpenVariant]
    winner_id: str = ""


class GenerateColdOpensRequest(BaseModel):
    """Request body for cold open generation."""

    topic: str = Field(..., min_length=1)
    description: str = ""
    brand_id: str | None = None
    model: str | None = None
    format_id: str = Field(default="youtube-listicle")
