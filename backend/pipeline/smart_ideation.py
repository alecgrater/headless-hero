"""Smart ideation pipeline — generates video ideas from trending data + optional profile."""

import json
import logging

from config import strip_markdown_fences
from integrations.claude_client import chat
from prompts import SMART_IDEATION_SYSTEM

logger = logging.getLogger(__name__)


def generate_smart_ideas(
    trending_topics: list[dict],
    count: int = 10,
    profile: dict | None = None,
    script_titles: list[str] | None = None,
) -> list[dict]:
    """Generate video ideas combining trending data with optional creator context.

    When profile is provided, full personalization is applied.
    When only script_titles are provided, lighter context is used.
    When neither is provided, ideas are based purely on trending data + strategies.
    """
    if not trending_topics:
        return []

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

    has_profile = profile is not None

    if has_profile:
        creator_context = {
            "creator_profile": {
                "common_topics": profile.get("common_topics", []),
                "narration_style": profile.get("narration_style", ""),
                "visual_approach": profile.get("visual_approach", ""),
                "audience_profile": profile.get("audience_profile", ""),
                "typical_keywords": profile.get("typical_keywords", []),
                "avg_segments": profile.get("avg_segment_count", 8),
            },
        }
    elif script_titles:
        creator_context = {
            "past_video_titles": script_titles,
        }
    else:
        creator_context = {}

    user_msg = json.dumps({
        **creator_context,
        "trending_topics": trending_context,
        "count": count,
    }, indent=2)

    logger.info(
        "Generating %d ideas (profile=%s, titles=%d, trending=%d)",
        count,
        "yes" if has_profile else "no",
        len(script_titles or []),
        len(trending_context),
    )

    raw = chat(
        SMART_IDEATION_SYSTEM.template,
        f"Generate {count} video ideas:\n{user_msg}",
        max_tokens=4096,
    )

    try:
        ideas = json.loads(strip_markdown_fences(raw))
    except json.JSONDecodeError:
        logger.error("Failed to parse smart ideas response")
        return []

    validated = []
    for idea in ideas:
        score_raw = idea.get("style_match_score")
        style_match_score = (
            max(0, min(100, float(score_raw)))
            if score_raw is not None and has_profile
            else None
        )

        validated.append({
            "title": idea.get("title", "Untitled"),
            "description": idea.get("description", ""),
            "segments_est": idea.get("segments_est", 8),
            "keywords": idea.get("keywords", [])[:5],
            "trending_source": idea.get("trending_source", ""),
            "style_match_score": style_match_score,
            "reasoning": idea.get("reasoning", ""),
            "angle": idea.get("angle", ""),
            "signals": idea.get("signals", [])[:3],
        })

    logger.info("Generated %d ideas", len(validated))
    return validated[:count]
