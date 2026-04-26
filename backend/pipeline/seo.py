"""SEO metadata generation pipeline — Claude generates YouTube metadata."""

import json
import logging

from pydantic import BaseModel

from config import strip_markdown_fences
from integrations.claude_client import chat
from prompts import SEO_SYSTEM

logger = logging.getLogger(__name__)

class YouTubeSEO(BaseModel):
    title: str
    description: str
    tags: list[str]

class SEOMetadata(BaseModel):
    youtube: YouTubeSEO


def format_timestamp(total_seconds: float) -> str:
    """Format seconds as M:SS (or H:MM:SS if >= 1 hour)."""
    total = int(total_seconds)
    hours, remainder = divmod(total, 3600)
    minutes, seconds = divmod(remainder, 60)
    if hours:
        return f"{hours}:{minutes:02d}:{seconds:02d}"
    return f"{minutes}:{seconds:02d}"

def generate_seo(
    video_title: str,
    segments: list[tuple[str, str]],
    video_description: str = "",
    brand_context: str = "",
    script_id: str | None = None,
) -> SEOMetadata:
    """Generate SEO metadata for YouTube via Claude.

    segments: list of (name, timestamp) tuples, e.g. [("Intro", "0:00"), ("Caffeine", "1:23")].
    """
    segment_list = "\n".join(f"- {ts} {name}" for name, ts in segments)
    user_msg = (
        f"Generate SEO metadata for this video:\n\n"
        f"Title: {video_title}\n"
        f"Segments:\n{segment_list}"
    )
    if video_description:
        user_msg += f"\n\nAdditional context: {video_description}"
    if brand_context:
        user_msg += f"\n\nBrand: {brand_context}"

    logger.info("[%s] Generating SEO metadata for %r (%d segments)", script_id or "no-id", video_title, len(segments))
    raw = chat(SEO_SYSTEM.template, user_msg, max_tokens=4096, script_id=script_id)
    text = strip_markdown_fences(raw)

    data = json.loads(text)
    result = SEOMetadata.model_validate(data)
    yt = result.youtube

    # Trim tags to fit YouTube's 500-character limit
    trimmed: list[str] = []
    total_len = 0
    for tag in yt.tags:
        separator_len = 2 if trimmed else 0  # ", " between tags
        if total_len + separator_len + len(tag) >= 500:
            break
        trimmed.append(tag)
        total_len += separator_len + len(tag)
    yt.tags = trimmed

    logger.info("[%s] SEO metadata generated for %r (title=%d chars, %d tags, %d tag chars)", script_id or "no-id", video_title, len(yt.title), len(yt.tags), total_len)
    return result
