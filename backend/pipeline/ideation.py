"""Idea generation pipeline — uses Claude to brainstorm video topics."""

import json

from pydantic import BaseModel

from integrations.claude_client import chat

class VideoIdea(BaseModel):
    """A single video topic idea returned by the generator."""

    title: str
    segments_est: int
    description: str
    keywords: list[str]

SYSTEM_PROMPT = """\
You are a YouTube content strategist specializing in educational/explainer \
channels (like "Everything Professor"). Your job is to generate compelling \
video topic ideas that are optimized for YouTube search and viewer engagement.

Rules:
- Every title should follow proven YouTube patterns: listicles, "Every X Explained", \
  comparisons, "What happens when…", etc.
- Estimate how many named segments (sub-topics) each video would have.
- Provide a brief angle/hook description (1-2 sentences).
- Suggest 3-5 relevant YouTube search keywords per idea.
- Avoid generic or overly broad topics — be specific and clickable.
- Return ONLY valid JSON — no markdown fences, no commentary.

Return a JSON array of objects with keys: title, segments_est, description, keywords.
"""

def generate_ideas(
    niche: str,
    count: int = 10,
    brand_context: str | None = None,
) -> list[VideoIdea]:
    """Generate video topic ideas for the given niche via Claude.

    Args:
        niche: The broad topic area (e.g. "psychology", "gaming", "history").
        count: How many ideas to generate (10-20).
        brand_context: Optional brand art style / description for context.

    Returns:
        A list of VideoIdea objects.
    """
    user_parts = [f"Generate {count} video topic ideas for the niche: \"{niche}\"."]
    if brand_context:
        user_parts.append(
            f"\nBrand context (for tone/style reference, not content): {brand_context}"
        )
    user_message = "\n".join(user_parts)

    raw = chat(SYSTEM_PROMPT, user_message)

    # Claude may wrap JSON in markdown fences — strip them
    text = raw.strip()
    if text.startswith("```"):
        text = text.split("\n", 1)[1]  # drop first ``` line
        text = text.rsplit("```", 1)[0]  # drop closing ```

    ideas_data = json.loads(text)
    return [VideoIdea.model_validate(item) for item in ideas_data]
