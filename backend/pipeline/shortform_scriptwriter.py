"""Short-form script generation pipeline — produces hook-first, single-segment scripts."""

import json
import logging
from pathlib import Path

from integrations.claude_client import chat
from models.script import ScriptContent

logger = logging.getLogger(__name__)

_GUIDE_PATH = Path(__file__).resolve().parent.parent / "prompts" / "shortform_scriptwriting_guide.md"
_STYLE_GUIDE = _GUIDE_PATH.read_text() if _GUIDE_PATH.exists() else ""

_SYSTEM_PROMPT = (_STYLE_GUIDE + "\n\n" if _STYLE_GUIDE else "") + """\
You are an expert short-form video scriptwriter specializing in YouTube Shorts, \
TikTok, and Instagram Reels. Your job is to write a single-segment, hook-first \
script optimized for maximum retention under 60 seconds.

Output rules:
- Return ONLY valid JSON — no markdown fences, no commentary.
- Follow this exact structure:
{
  "title": "Video Title",
  "format": "shortform",
  "target_duration_seconds": 40,
  "intro_hook": "",
  "outro_cta": "",
  "segments": [
    {
      "name": "Main",
      "scenes": [
        {
          "id": "scene_001",
          "narration": "Hook narration — 2-3 seconds max.",
          "visual_prompt": "Vertically composed 9:16 portrait image description.",
          "text_overlay": "BOLD TEXT (5 words max)",
          "duration_estimate_seconds": 3,
          "is_title_card": false,
          "is_animated": false,
          "visual_prompt_b": "",
          "media_type": "ai_generated",
          "search_query": ""
        }
      ]
    }
  ]
}

Writing guidelines:
- 5-8 scenes total in a SINGLE segment named "Main".
- Total narration: 75-110 words (~30-45 seconds).
- Scene 1 is the HOOK — provocative, shocking, or curiosity-inducing.
- Final scene is the PAYOFF — most satisfying information.
- Every visual prompt must describe a vertically composed 9:16 portrait image.
- Text overlays: short, punchy, 1-5 words. CAPS for emphasis.
- No greetings, no filler, no transitions between scenes.
- Scene IDs must be unique and sequential: scene_001, scene_002, etc."""


def generate_shortform_script(
    topic: str,
    description: str = "",
    brand_context: str = "",
    platforms: list[str] | None = None,
    target_duration_seconds: int = 40,
    modifier_ids: list[str] | None = None,
    brand: dict | None = None,
) -> ScriptContent:
    """Generate a short-form video script via Claude.

    Returns a validated ScriptContent with format="shortform".
    """
    platform_names = {
        "youtube_shorts": "YouTube Shorts",
        "tiktok": "TikTok",
        "instagram_reels": "Instagram Reels",
    }
    platform_list = ", ".join(
        platform_names.get(p, p) for p in (platforms or ["youtube_shorts", "tiktok", "instagram_reels"])
    )

    user_parts = [f'Write a short-form video script for: "{topic}"']
    if description:
        user_parts.append(f"Angle/description: {description}")
    user_parts.append(f"Target platforms: {platform_list}")
    user_parts.append(f"Target duration: {target_duration_seconds} seconds")
    if brand_context:
        user_parts.append(f"Brand context (use for visual style and tone): {brand_context}")

    system_prompt = _SYSTEM_PROMPT
    user_message = "\n".join(user_parts)

    # Apply modifier prompt hooks
    if modifier_ids:
        import pipeline.modifiers  # noqa: F401 — ensure registration
        from pipeline.modifiers.registry import get_active

        for mod in get_active(modifier_ids):
            system_prompt, user_message = mod.modify_script_prompt(
                system_prompt, user_message
            )

    raw = chat(system_prompt, user_message, max_tokens=4096)

    # Strip markdown fences if present
    text = raw.strip()
    if text.startswith("```"):
        text = text.split("\n", 1)[1]
        text = text.rsplit("```", 1)[0]

    data = json.loads(text)
    # Ensure format fields are set
    data["format"] = "shortform"
    data["target_duration_seconds"] = target_duration_seconds
    content = ScriptContent.model_validate(data)

    # Apply modifier post-processing hooks
    if modifier_ids:
        from pipeline.modifiers.registry import get_active

        brand_dict = brand or {}
        for mod in get_active(modifier_ids):
            content = mod.modify_script_post(content, brand_dict)

    # Validate: warn if word count suggests >60s
    total_words = sum(
        len(scene.narration.split())
        for seg in content.segments
        for scene in seg.scenes
    )
    estimated_duration = total_words / 2.5  # ~2.5 words/sec
    if estimated_duration > 60:
        logger.warning(
            "Short-form script has %d words (~%.0fs) — may exceed 60s target",
            total_words,
            estimated_duration,
        )

    return content
