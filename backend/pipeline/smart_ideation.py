"""Smart ideation pipeline — generates video ideas from trending data + optional profile."""

import json
import logging
from concurrent.futures import ThreadPoolExecutor, as_completed

from config import parse_json_response
from integrations.llm_client import chat
from prompts import SMART_IDEATION_SYSTEM

logger = logging.getLogger(__name__)

BATCH_SIZE = 10
MAX_TOKENS_PER_BATCH = 4096


def _generate_batch(
    batch_index: int,
    batch_count: int,
    payload: dict,
) -> list[dict]:
    """Generate a single batch of ideas."""
    user_msg = json.dumps(payload, indent=2)
    raw = chat(
        SMART_IDEATION_SYSTEM.template,
        f"Generate {batch_count} video ideas (batch {batch_index + 1}):\n{user_msg}",
        max_tokens=MAX_TOKENS_PER_BATCH,
        cache=True,
        json_mode=True,
        task="idea",
    )
    try:
        return parse_json_response(raw)
    except (json.JSONDecodeError, ValueError):
        logger.error("Failed to parse smart ideas batch %d", batch_index + 1)
        return []


def generate_smart_ideas(
    trending_topics: list[dict],
    count: int = 40,
    profile: dict | None = None,
    script_titles: list[str] | None = None,
) -> list[dict]:
    """Generate video ideas combining trending data with optional creator context.

    Splits into parallel batches to stay within proxy timeout limits.
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

    num_batches = max(1, (count + BATCH_SIZE - 1) // BATCH_SIZE)
    batch_sizes = []
    remaining = count
    for _ in range(num_batches):
        batch_size = min(BATCH_SIZE, remaining)
        batch_sizes.append(batch_size)
        remaining -= batch_size

    logger.info(
        "Generating %d ideas in %d batches (profile=%s, titles=%d, trending=%d)",
        count,
        num_batches,
        "yes" if profile else "no",
        len(script_titles or []),
        len(trending_topics),
    )

    all_ideas: list[dict] = []

    with ThreadPoolExecutor(max_workers=num_batches) as executor:
        futures = []
        for i, batch_size in enumerate(batch_sizes):
            batch_payload = {**payload, "count": batch_size}
            futures.append(executor.submit(_generate_batch, i, batch_size, batch_payload))

        for future in as_completed(futures):
            try:
                batch_result = future.result()
                all_ideas.extend(batch_result)
            except Exception:
                logger.error("Smart ideas batch failed", exc_info=True)

    has_profile = profile is not None
    validated = []
    for idea in all_ideas:
        score_raw = idea.get("style_match_score")
        style_match_score = (
            max(0, min(100, float(score_raw)))
            if score_raw is not None and has_profile
            else None
        )

        validated.append({
            "category": idea.get("category", "Other"),
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

    logger.info("Generated %d ideas across %d batches", len(validated), num_batches)
    return validated[:count]
