"""Idea generation pipeline — uses the routed LLM provider to brainstorm video topics."""

import logging

from pydantic import BaseModel

from config import parse_json_array_response
from integrations.llm_client import chat

logger = logging.getLogger(__name__)

class VideoIdea(BaseModel):
    """A single video topic idea returned by the generator."""

    title: str
    segments_est: int
    description: str
    keywords: list[str] = []
    cold_open_text: str | None = None
    format_id: str = "youtube-listicle"
    closing_image: str | None = None  # life-as-a only
    creator_guidance: str | None = None

def generate_ideas(
    niche: str,
    guide: str | None = None,
    count: int = 10,
    brand_context: str | None = None,
    exclude_titles: list[str] | None = None,
    format_id: str = "youtube-listicle",
) -> list[VideoIdea]:
    """Generate video topic ideas for the given niche via the routed LLM provider.

    Args:
        niche: The broad topic area (e.g. "psychology", "gaming", "history").
        guide: Optional creator guidance for the desired angle, constraints, or examples.
        count: How many ideas to generate (10-20).
        brand_context: Optional brand art style / description for context.
        exclude_titles: Titles to avoid repeating (for "Load More" dedup).
        format_id: Which video format's ideation prompt to use.

    Returns:
        A list of VideoIdea objects, each tagged with the format_id used.
    """
    from pipeline.formats import get_format

    fmt = get_format(format_id)

    # Build system prompt from the format-supplied PromptDef.
    if fmt.ideation_prompt.builder is not None:
        # Listicle ideation expects a segments string (e.g. "8") as the builder input.
        if isinstance(fmt.level_count, int):
            system_prompt = fmt.ideation_prompt.build(str(fmt.level_count))
        else:
            lo, hi = fmt.level_count
            system_prompt = fmt.ideation_prompt.build(f"{lo}–{hi}")
    else:
        system_prompt = fmt.ideation_prompt.template

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

    logger.info("Generating %s ideas for niche %r (format=%s)", count, niche, fmt.id)
    raw = chat(system_prompt, user_message, json_mode=True, task="idea")

    ideas_data = parse_json_array_response(raw, key="ideas")
    ideas = [VideoIdea.model_validate(item) for item in ideas_data]
    for idea in ideas:
        idea.format_id = fmt.id
        idea.creator_guidance = normalized_guide or None
    logger.info("Generated %s ideas for niche %r (format=%s)", len(ideas), niche, fmt.id)
    return ideas
