"""Idea generation pipeline — uses Claude to brainstorm video topics."""

import json
import logging

from pydantic import BaseModel, field_validator

from config import ALLOWED_SEGMENT_COUNTS, DEFAULT_CLAUDE_MODEL, snap_segment_count, strip_markdown_fences
from integrations.claude_client import chat
from prompts import IDEATION_SYSTEM

logger = logging.getLogger(__name__)

class VideoIdea(BaseModel):
    """A single video topic idea returned by the generator."""

    title: str
    segments_est: int
    description: str
    keywords: list[str]

    @field_validator("segments_est")
    @classmethod
    def cap_segments(cls, v: int) -> int:
        return snap_segment_count(v)

_ALLOWED_SEGMENTS_STR = " or ".join(str(n) for n in ALLOWED_SEGMENT_COUNTS)

def generate_ideas(
    niche: str,
    count: int = 10,
    brand_context: str | None = None,
    exclude_titles: list[str] | None = None,
) -> list[VideoIdea]:
    """Generate video topic ideas for the given niche via Claude.

    Args:
        niche: The broad topic area (e.g. "psychology", "gaming", "history").
        count: How many ideas to generate (10-20).
        brand_context: Optional brand art style / description for context.
        exclude_titles: Titles to avoid repeating (for "Load More" dedup).

    Returns:
        A list of VideoIdea objects.
    """
    user_parts = [f"Generate {count} video topic ideas for the niche: \"{niche}\"."]
    if brand_context:
        user_parts.append(
            f"\nBrand context (for tone/style reference, not content): {brand_context}"
        )
    if exclude_titles:
        titles_str = "; ".join(exclude_titles)
        user_parts.append(
            f"\nDo NOT repeat or closely paraphrase these existing titles: {titles_str}"
        )
    user_message = "\n".join(user_parts)

    model = DEFAULT_CLAUDE_MODEL
    logger.info("Generating %s ideas for niche %r using model=%s", count, niche, model)
    raw = chat(IDEATION_SYSTEM.builder(_ALLOWED_SEGMENTS_STR), user_message, model=model)

    # Claude may wrap JSON in markdown fences — strip them
    text = strip_markdown_fences(raw)

    ideas_data = json.loads(text)
    ideas = [VideoIdea.model_validate(item) for item in ideas_data]
    logger.info("Generated %s ideas for niche %r", len(ideas), niche)
    return ideas
