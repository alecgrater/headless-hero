"""SEO metadata generation pipeline — Claude generates per-platform metadata."""

import json
from pathlib import Path

from pydantic import BaseModel

from integrations.claude_client import chat

class YouTubeSEO(BaseModel):
    title: str
    description: str
    tags: list[str]

class TikTokSEO(BaseModel):
    caption: str
    hashtags: list[str]

class InstagramSEO(BaseModel):
    caption: str
    hashtags: list[str]

class SEOMetadata(BaseModel):
    youtube: YouTubeSEO
    tiktok: list[TikTokSEO]
    instagram: InstagramSEO

# --- Short-form SEO models ---

class YouTubeShortsSEO(BaseModel):
    title: str
    description: str
    tags: list[str]

class ShortformSEOMetadata(BaseModel):
    youtube_shorts: YouTubeShortsSEO | None = None
    tiktok: TikTokSEO | None = None
    instagram_reels: InstagramSEO | None = None
    thumbnail_text: str = ""
    hook_preview_text: str = ""

SYSTEM_PROMPT = """\
You are a social media SEO expert. Generate optimized metadata for video \
content across multiple platforms. Tailor the metadata to match the brand's \
voice, identity, and style when brand context is provided.

Rules:
- YouTube title: max 70 chars, include primary keyword, use power words.
- YouTube description: 2-3 paragraphs, include timestamps if segments provided, \
  natural keyword usage, call to action.
- YouTube tags: 30+ relevant tags, mix of broad and specific.
- TikTok caption: max 150 chars per segment, punchy and engaging.
- TikTok hashtags: 5-8 trending/relevant per segment.
- Instagram caption: engaging, storytelling tone, 2-3 paragraphs.
- Instagram hashtags: 20-30 mix of popular and niche.
- Return ONLY valid JSON — no markdown fences, no commentary.

Return a JSON object with keys: youtube, tiktok (array), instagram.
"""

def generate_seo(
    video_title: str,
    segments: list[str],
    video_description: str = "",
    brand_context: str = "",
) -> SEOMetadata:
    """Generate SEO metadata for all platforms via Claude."""
    segment_list = "\n".join(f"- {name}" for name in segments)
    user_msg = (
        f"Generate SEO metadata for this video:\n\n"
        f"Title: {video_title}\n"
        f"Segments:\n{segment_list}"
    )
    if video_description:
        user_msg += f"\n\nAdditional context: {video_description}"
    if brand_context:
        user_msg += f"\n\nBrand: {brand_context}"

    raw = chat(SYSTEM_PROMPT, user_msg, max_tokens=4096)
    text = raw.strip()
    if text.startswith("```"):
        text = text.split("\n", 1)[1]
        text = text.rsplit("```", 1)[0]

    data = json.loads(text)
    return SEOMetadata.model_validate(data)


# --- Short-form SEO ---

_SHORTFORM_GUIDE_PATH = Path(__file__).resolve().parent.parent / "prompts" / "shortform_seo_guide.md"
_SHORTFORM_SEO_GUIDE = _SHORTFORM_GUIDE_PATH.read_text() if _SHORTFORM_GUIDE_PATH.exists() else ""

_SHORTFORM_SEO_SYSTEM = (_SHORTFORM_SEO_GUIDE + "\n\n" if _SHORTFORM_SEO_GUIDE else "") + """\
You are a short-form video SEO expert specializing in YouTube Shorts, TikTok, \
and Instagram Reels.
- Return ONLY valid JSON — no markdown fences, no commentary.
- Only include platforms that are listed in the user's request."""


def generate_shortform_seo(
    title: str,
    narration_text: str,
    brand_context: str = "",
    platforms: list[str] | None = None,
) -> ShortformSEOMetadata:
    """Generate platform-specific SEO metadata for short-form content."""
    platform_names = {
        "youtube_shorts": "YouTube Shorts",
        "tiktok": "TikTok",
        "instagram_reels": "Instagram Reels",
    }
    plats = platforms or ["youtube_shorts", "tiktok", "instagram_reels"]
    platform_list = ", ".join(platform_names.get(p, p) for p in plats)

    user_msg = (
        f"Generate short-form SEO metadata for this video:\n\n"
        f"Title: {title}\n"
        f"Narration: {narration_text}\n"
        f"Target platforms: {platform_list}"
    )
    if brand_context:
        user_msg += f"\nBrand context: {brand_context}"

    raw = chat(_SHORTFORM_SEO_SYSTEM, user_msg, max_tokens=4096)
    text = raw.strip()
    if text.startswith("```"):
        text = text.split("\n", 1)[1]
        text = text.rsplit("```", 1)[0]

    data = json.loads(text)
    return ShortformSEOMetadata.model_validate(data)
