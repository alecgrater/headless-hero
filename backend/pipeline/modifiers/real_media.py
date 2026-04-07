"""Real media content modifier (gaming clips + hardware images).

Injects real media guidelines into script generation prompts and
overrides scene rendering for gameplay clip scenes.
"""

import logging

from models.script import Scene, ScriptContent
from pipeline.modifiers.base import ContentModifier, ModifierMeta

logger = logging.getLogger(__name__)

# Instructions previously hardcoded in scriptwriter.SYSTEM_PROMPT lines 76-90
_REAL_MEDIA_PROMPT_INSTRUCTIONS = """\

Real media guidelines — mix real footage with AI art for visual variety:
- Each scene has a "media_type" field: "ai_generated" (default), "gameplay_clip", or "hardware_image".
- Each scene has a "search_query" field (empty string by default).
- Use a MIX of real media and AI-generated art throughout the video. Aim for visual variety \
by alternating between real footage and AI illustrations rather than using only one type.
- When to use "gameplay_clip": a scene references a **specific, recognizable game** by name \
(e.g. Halo, GTA V, Minecraft). Provide a specific YouTube search query like "Halo Infinite \
gameplay 4K" or "GTA V PC gameplay 60fps".
- When to use "hardware_image": a scene references a **specific, recognizable console or \
hardware product** by name (e.g. PlayStation 5, RTX 4090). Provide a search query like \
"PlayStation 5 console close up review" or "RTX 4090 unboxing". These extract a still frame \
from a YouTube video.
- When to use "ai_generated": everything else — general concepts, metaphors, transitions, \
explanations, historical overviews, abstract ideas, or any scene not about a specific named \
game or hardware product. Leave search_query as an empty string. AI illustration is better \
for abstract and conceptual visuals.
- A typical gaming video should have roughly 40-60% real media scenes and 40-60% AI scenes, \
depending on how many specific games/products are discussed.
- Include "media_type" and "search_query" in each scene object in the JSON output."""

# JSON schema fields to add when real media is active
_REAL_MEDIA_SCHEMA_ADDITION = """\
          "media_type": "ai_generated",
          "search_query": \"\""""


class RealMediaModifier(ContentModifier):
    meta = ModifierMeta(
        id="real_media",
        name="Real Media (Gaming)",
        description="Mix real gameplay clips and hardware images from YouTube with AI art.",
        icon="🎮",
    )

    def modify_script_prompt(self, system_prompt: str, user_message: str) -> tuple[str, str]:
        logger.info("Injecting real media guidelines into script prompt")
        return system_prompt + _REAL_MEDIA_PROMPT_INSTRUCTIONS, user_message

    def get_router(self):
        from api.media import router
        return router
