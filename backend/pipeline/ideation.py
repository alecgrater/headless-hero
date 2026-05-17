"""Idea generation pipeline — uses the routed LLM provider to brainstorm video topics."""

import logging

from pydantic import BaseModel, field_validator

from config import SEGMENT_COUNT, parse_json_array_response
from integrations.llm_client import chat
from prompts import IDEATION_SYSTEM

logger = logging.getLogger(__name__)

class VideoIdea(BaseModel):
    """A single video topic idea returned by the generator."""

    title: str
    segments_est: int
    description: str
    keywords: list[str]

    @field_validator("segments_est", mode="before")
    @classmethod
    def coerce_segments(cls, v: object) -> int:
        return SEGMENT_COUNT

def generate_ideas(
    niche: str,
    guide: str | None = None,
    count: int = 10,
    brand_context: str | None = None,
    exclude_titles: list[str] | None = None,
) -> list[VideoIdea]:
    """Generate video topic ideas for the given niche via the routed LLM provider.

    Args:
        niche: The broad topic area (e.g. "psychology", "gaming", "history").
        guide: Optional creator guidance for the desired angle, constraints, or examples.
        count: How many ideas to generate (10-20).
        brand_context: Optional brand art style / description for context.
        exclude_titles: Titles to avoid repeating (for "Load More" dedup).

    Returns:
        A list of VideoIdea objects.
    """
    user_parts = [f"Generate {count} video topic ideas for the niche: \"{niche}\"."]
    normalized_guide = guide.strip() if guide else ""
    if normalized_guide:
        user_parts.append(
            "\nCreator guidance: Treat this as the user's intent, constraints, examples, and "
            f"quality bar for the generated ideas. Do not include examples unless the guidance explicitly asks for them.\n{normalized_guide}"
        )
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

    logger.info("Generating %s ideas for niche %r", count, niche)
    raw = chat(IDEATION_SYSTEM.build(str(SEGMENT_COUNT)), user_message, json_mode=True, task="idea")

    ideas_data = parse_json_array_response(raw, key="ideas")
    ideas = [VideoIdea.model_validate(item) for item in ideas_data]
    logger.info("Generated %s ideas for niche %r", len(ideas), niche)
    return ideas
