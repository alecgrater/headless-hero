"""Smart ideation pipeline — generates personalized video ideas from profile + trending data."""

import json
import logging

from config import strip_markdown_fences
from integrations.claude_client import chat

logger = logging.getLogger(__name__)

SMART_IDEATION_SYSTEM = """\
You are a YouTube content strategist. You have:
1. A creator's content profile — their established style, topics, audience, and narration voice.
2. Current trending topics from multiple sources (Hacker News, Wikipedia, Reddit, YouTube, news, etc.).

Generate video ideas that blend trending topics with the creator's established style. Each idea should \
feel natural for the creator's audience while capitalizing on trending search interest.

For each idea return a JSON object with these exact fields:
- title: compelling YouTube title (50-70 chars)
- description: 2-3 sentence video description
- segments_est: estimated segment count (8 or 10)
- keywords: list of 3-5 SEO keywords
- trending_source: which trending topic(s) inspired this idea
- style_match_score: 0-100 how well this fits the creator's style
- reasoning: 1-2 sentences on why this suits the creator's audience
- angle: the unique hook or perspective

Return ONLY a JSON array of objects — no markdown fences, no commentary.
"""


def generate_smart_ideas(
    profile: dict,
    trending_topics: list[dict],
    count: int = 10,
) -> list[dict]:
    """Generate personalized video ideas combining creator profile with trending data."""
    if not profile or not trending_topics:
        return []

    # Build context for Claude
    profile_context = {
        "common_topics": profile.get("common_topics", []),
        "narration_style": profile.get("narration_style", ""),
        "visual_approach": profile.get("visual_approach", ""),
        "audience_profile": profile.get("audience_profile", ""),
        "typical_keywords": profile.get("typical_keywords", []),
        "avg_segments": profile.get("avg_segment_count", 8),
    }

    trending_context = [
        {
            "title": t["title"],
            "source": t["source"],
            "score": t.get("score", 0),
            "evidence": t.get("evidence", ""),
            "breakout": t.get("is_breakout", False),
        }
        for t in trending_topics[:20]
    ]

    user_msg = json.dumps({
        "creator_profile": profile_context,
        "trending_topics": trending_context,
        "count": count,
    }, indent=2)

    logger.info("Generating %d smart ideas from %d trending topics", count, len(trending_context))
    raw = chat(
        SMART_IDEATION_SYSTEM,
        f"Generate {count} video ideas:\n{user_msg}",
        model="anthropic.claude-sonnet-4-6-v1",
        max_tokens=4096,
    )

    try:
        ideas = json.loads(strip_markdown_fences(raw))
    except json.JSONDecodeError:
        logger.error("Failed to parse smart ideas response")
        return []

    # Validate and normalize each idea
    validated = []
    for idea in ideas:
        validated.append({
            "title": idea.get("title", "Untitled"),
            "description": idea.get("description", ""),
            "segments_est": idea.get("segments_est", 8),
            "keywords": idea.get("keywords", [])[:5],
            "trending_source": idea.get("trending_source", ""),
            "style_match_score": max(0, min(100, float(idea.get("style_match_score", 50)))),
            "reasoning": idea.get("reasoning", ""),
            "angle": idea.get("angle", ""),
        })

    logger.info("Generated %d smart ideas", len(validated))
    return validated[:count]
