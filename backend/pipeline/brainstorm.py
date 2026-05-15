"""Brainstorm recommendation pipeline — Claude-powered niche prompt generation."""

import json
import logging

from integrations.llm_client import chat
from prompts import BRAINSTORM_SYSTEM

logger = logging.getLogger(__name__)


def generate_brainstorm_recommendations(
    script_titles: list[str],
    trending_topics: list[dict[str, str | float]],
    count: int = 8,
) -> list[dict]:
    titles_block = "\n".join(f"- {t}" for t in script_titles) if script_titles else "(no past videos)"
    topics_block = "\n".join(
        f"- {t['title']} (score: {t.get('score', 0):.0f})"
        for t in trending_topics
    ) if trending_topics else "(no trending topics available)"

    user_message = (
        f"## Past Video Titles\n{titles_block}\n\n"
        f"## Current Trending Topics\n{topics_block}\n\n"
        f"Generate {count} niche prompt recommendations."
    )

    response_text = chat(
        system=BRAINSTORM_SYSTEM.template,
        user_message=user_message,
        json_mode=True,
        task="idea",
    )

    text = response_text.strip()
    if text.startswith("```"):
        text = text.split("\n", 1)[1] if "\n" in text else text[3:]
        if text.endswith("```"):
            text = text[:-3]

    recommendations = json.loads(text)
    if not isinstance(recommendations, list):
        raise ValueError("Expected JSON array from Claude")

    return recommendations[:count]
