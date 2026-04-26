"""Smart ideation pipeline — generates video ideas from trending data + optional profile."""

import json
import logging

from config import parse_json_response
from integrations.claude_client import chat
from prompts import SMART_IDEATION_SYSTEM

logger = logging.getLogger(__name__)


def generate_smart_ideas(
    trending_topics: list[dict],
    count: int = 40,
    profile: dict | None = None,
    script_titles: list[str] | None = None,
) -> list[dict]:
    """Generate video ideas combining trending data with optional creator context.

    When profile is provided, full personalization is applied.
    Script titles are always sent when available (additive with profile).
    Trending data is enrichment, not a requirement.
    Returns ideas sorted by idea_score within categories, categories sorted by top score.
    """
    payload: dict = {}

    if profile:
        payload["creator_profile"] = {
            "common_topics": profile.get("common_topics", []),
            "narration_style": profile.get("narration_style", ""),
            "visual_approach": profile.get("visual_approach", ""),
            "audience_profile": profile.get("audience_profile", ""),
            "typical_keywords": profile.get("typical_keywords", []),
            "avg_segments": profile.get("avg_segment_count", 8),
        }

    if script_titles:
        payload["past_video_titles"] = script_titles

    if trending_topics:
        payload["trending_topics"] = [
            {
                "title": t["title"],
                "source": t["source"],
                "score": t.get("score", 0),
                "evidence": t.get("evidence", ""),
                "breakout": t.get("is_breakout", False),
            }
            for t in trending_topics[:20]
        ]

    payload["count"] = count

    user_msg = json.dumps(payload, indent=2)

    logger.info(
        "Generating %d ideas (profile=%s, titles=%d, trending=%d)",
        count,
        "yes" if profile else "no",
        len(script_titles or []),
        len(trending_topics),
    )

    raw = chat(
        SMART_IDEATION_SYSTEM.template,
        f"Generate {count} video ideas:\n{user_msg}",
        max_tokens=16384,
    )

    try:
        ideas = parse_json_response(raw)
    except (json.JSONDecodeError, ValueError):
        logger.error("Failed to parse smart ideas response")
        return []

    has_profile = profile is not None
    validated = []
    for idea in ideas:
        score_raw = idea.get("style_match_score")
        style_match_score = (
            max(0, min(100, float(score_raw)))
            if score_raw is not None and has_profile
            else None
        )

        idea_score_raw = idea.get("idea_score")
        idea_score = (
            max(0, min(100, float(idea_score_raw)))
            if idea_score_raw is not None
            else 50
        )

        validated.append({
            "category": idea.get("category", "Other"),
            "title": idea.get("title", "Untitled"),
            "description": idea.get("description", ""),
            "segments_est": idea.get("segments_est", 8),
            "keywords": idea.get("keywords", [])[:5],
            "trending_source": idea.get("trending_source", ""),
            "style_match_score": style_match_score,
            "idea_score": idea_score,
            "recommended": bool(idea.get("recommended", False)),
            "reasoning": idea.get("reasoning", ""),
            "angle": idea.get("angle", ""),
            "signals": idea.get("signals", [])[:3],
        })

    validated = _sort_by_category_and_score(validated)

    logger.info("Generated %d ideas", len(validated))
    return validated[:count]


def _sort_by_category_and_score(ideas: list[dict]) -> list[dict]:
    """Sort ideas by score within each category, then sort categories by top score."""
    by_category: dict[str, list[dict]] = {}
    for idea in ideas:
        cat = idea["category"]
        by_category.setdefault(cat, []).append(idea)

    for cat_ideas in by_category.values():
        cat_ideas.sort(key=lambda x: x["idea_score"], reverse=True)

    sorted_cats = sorted(
        by_category.items(),
        key=lambda item: item[1][0]["idea_score"] if item[1] else 0,
        reverse=True,
    )

    result = []
    for _, cat_ideas in sorted_cats:
        result.extend(cat_ideas)
    return result
