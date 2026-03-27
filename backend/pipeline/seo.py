"""SEO metadata generation pipeline — Claude generates per-platform metadata."""

import json

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

SYSTEM_PROMPT = """\
You are a social media SEO expert. Generate optimized metadata for video \
content across multiple platforms.

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

    raw = chat(SYSTEM_PROMPT, user_msg, max_tokens=4096)
    text = raw.strip()
    if text.startswith("```"):
        text = text.split("\n", 1)[1]
        text = text.rsplit("```", 1)[0]

    data = json.loads(text)
    return SEOMetadata.model_validate(data)
