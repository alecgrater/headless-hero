"""SEO metadata generation pipeline — uses the routed LLM provider for YouTube metadata."""

import json
import logging

from pydantic import BaseModel

from config import strip_markdown_fences
from integrations.llm_client import chat
from models.script import ScriptContent
from prompts import SEO_SYSTEM, SHORT_FORM_SEO_SYSTEM

logger = logging.getLogger(__name__)

class YouTubeSEO(BaseModel):
    title: str
    description: str
    tags: list[str]

class SEOMetadata(BaseModel):
    youtube: YouTubeSEO

class ShortFormSEO(BaseModel):
    index: int
    title: str
    description: str
    hashtags: list[str]
    tags: list[str]

class ShortFormSEOMetadata(BaseModel):
    shorts: list[ShortFormSEO]


def format_timestamp(total_seconds: float) -> str:
    """Format seconds as M:SS (or H:MM:SS if >= 1 hour)."""
    total = int(total_seconds)
    hours, remainder = divmod(total, 3600)
    minutes, seconds = divmod(remainder, 60)
    if hours:
        return f"{hours}:{minutes:02d}:{seconds:02d}"
    return f"{minutes}:{seconds:02d}"

def _trim_tags(tags: list[str], max_chars: int = 500) -> list[str]:
    """Trim comma-joined tags to fit platform limits."""
    trimmed: list[str] = []
    total_len = 0
    for tag in tags:
        clean = tag.strip()
        if not clean:
            continue
        separator_len = 2 if trimmed else 0
        if total_len + separator_len + len(clean) >= max_chars:
            break
        trimmed.append(clean)
        total_len += separator_len + len(clean)
    return trimmed

def _normalize_hashtags(hashtags: list[str]) -> list[str]:
    """Normalize hashtags for short-form captions."""
    normalized: list[str] = []
    seen: set[str] = set()
    for raw in hashtags:
        tag = raw.strip()
        if not tag:
            continue
        if not tag.startswith("#"):
            tag = f"#{tag}"
        tag = tag.replace(" ", "")
        key = tag.lower()
        if key in seen:
            continue
        seen.add(key)
        normalized.append(tag)
    return normalized[:10]

def build_short_form_seo_contexts(content: ScriptContent) -> list[dict]:
    """Build one transcript summary per rendered short."""
    shorts: list[dict] = []
    total = len(content.segments)
    for segment_idx, segment in enumerate(content.segments):
        scenes = list(segment.scenes)
        if segment_idx == 0 and content.hook_scene_count:
            skip = min(content.hook_scene_count, max(0, len(scenes) - 2))
            if skip > 0:
                scenes = [scenes[0]] + scenes[1 + skip:]

        narration_parts = [
            scene.narration.strip()
            for scene in scenes
            if not scene.is_title_card and scene.narration.strip()
        ]
        duration_seconds = sum(scene.audio_duration_seconds for scene in scenes)
        transcript = " ".join(narration_parts)
        shorts.append({
            "index": segment_idx + 1,
            "total": total,
            "segment_name": segment.name,
            "duration_seconds": round(duration_seconds, 1),
            "transcript": transcript[:2500],
        })
    return shorts

def generate_seo(
    video_title: str,
    segments: list[tuple[str, str]],
    video_description: str = "",
    brand_context: str = "",
    script_id: str | None = None,
) -> SEOMetadata:
    """Generate SEO metadata for YouTube via the routed LLM provider.

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
    raw = chat(SEO_SYSTEM.template, user_msg, max_tokens=4096, script_id=script_id, json_mode=True, task="seo")
    text = strip_markdown_fences(raw)

    data = json.loads(text)
    yt_data = data.get("youtube", {})
    if isinstance(yt_data.get("tags"), str):
        yt_data["tags"] = [t.strip() for t in yt_data["tags"].split(",") if t.strip()]
    result = SEOMetadata.model_validate(data)
    yt = result.youtube

    yt.tags = _trim_tags(yt.tags)
    total_len = len(", ".join(yt.tags))

    logger.info("[%s] SEO metadata generated for %r (title=%d chars, %d tags, %d tag chars)", script_id or "no-id", video_title, len(yt.title), len(yt.tags), total_len)
    return result

def generate_short_form_seo(
    video_title: str,
    shorts: list[dict],
    video_description: str = "",
    brand_context: str = "",
    script_id: str | None = None,
) -> ShortFormSEOMetadata:
    """Generate one short-form SEO metadata set per rendered short."""
    user_msg = (
        f"Generate short-form metadata for every short from this long-form video.\n\n"
        f"Long-form title: {video_title}\n"
        f"Shorts JSON:\n{json.dumps(shorts, ensure_ascii=False, indent=2)}"
    )
    if video_description:
        user_msg += f"\n\nAdditional context: {video_description}"
    if brand_context:
        user_msg += f"\n\nBrand: {brand_context}"

    logger.info(
        "[%s] Generating short-form SEO metadata for %r (%d shorts)",
        script_id or "no-id",
        video_title,
        len(shorts),
    )
    raw = chat(
        SHORT_FORM_SEO_SYSTEM.template,
        user_msg,
        max_tokens=8192,
        script_id=script_id,
        json_mode=True,
        task="short_form_seo",
    )
    text = strip_markdown_fences(raw)
    data = json.loads(text)
    result = ShortFormSEOMetadata.model_validate(data)

    expected = {int(short["index"]) for short in shorts}
    found = {short.index for short in result.shorts}
    if expected != found:
        logger.warning(
            "[%s] Short-form SEO returned indices %s, expected %s",
            script_id or "no-id",
            sorted(found),
            sorted(expected),
        )

    for short in result.shorts:
        short.title = short.title[:70].strip()
        short.tags = _trim_tags(short.tags)
        short.hashtags = _normalize_hashtags(short.hashtags)

    logger.info(
        "[%s] Short-form SEO metadata generated for %d shorts",
        script_id or "no-id",
        len(result.shorts),
    )
    return result
