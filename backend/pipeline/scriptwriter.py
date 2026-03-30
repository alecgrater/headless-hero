"""Script generation pipeline — uses Claude to write segmented video scripts."""

import json
import logging
from pathlib import Path

from integrations.claude_client import chat
from models.script import ScriptContent

logger = logging.getLogger(__name__)

_GUIDE_PATH = Path(__file__).resolve().parent.parent / "prompts" / "scriptwriting_guide.md"
_STYLE_GUIDE = _GUIDE_PATH.read_text() if _GUIDE_PATH.exists() else ""

# Base system prompt — modifier-specific instructions (title cards, real media)
# are injected dynamically via ContentModifier.modify_script_prompt().
BASE_SYSTEM_PROMPT = (_STYLE_GUIDE + "\n\n" if _STYLE_GUIDE else "") + """\
You are an expert YouTube scriptwriter specializing in educational/explainer \
content (like "Everything Professor" or "Kurzgesagt" style). Your job is to \
write a full, production-ready script broken into named segments with per-scene \
visual direction notes.

Output rules:
- Return ONLY valid JSON — no markdown fences, no commentary.
- Follow this exact structure:
{
  "title": "Video Title",
  "card_title": "SHORT TITLE",
  "card_title_highlight_word": "KEYWORD",
  "intro_hook": "A punchy 1-2 sentence hook that grabs the viewer in the first 5 seconds.",
  "outro_cta": "A call-to-action for the end of the video.",
  "segments": [
    {
      "name": "Segment Name",
      "circle_color": "#e91e63",
      "title_card_image_prompt": "A vivid visual description for the segment's circle image.",
      "scenes": [
        {
          "id": "scene_001",
          "narration": "The narration text the voiceover artist reads.",
          "visual_prompt": "Primary/summary description of what the illustration should depict.",
          "text_overlay": "Key text to display on screen (short phrase).",
          "duration_estimate_seconds": 8,
          "is_title_card": false,
          "frame_count": 3,
          "frame_prompts": [
            "Frame 1: Wide establishing shot of the subject...",
            "Frame 2: Closer view showing detail...",
            "Frame 3: Final state with result..."
          ],
          "media_type": "ai_generated",
          "search_query": ""
        }
      ]
    }
  ]
}

Writing guidelines:
- Each non-title scene should be 6-15 seconds of narration.
- Write narration in a conversational, engaging tone — not dry or academic.
- Use hooks, cliffhangers between segments, and smooth transitions.
- Visual prompts should be detailed enough for an AI image generator: describe \
the subject, composition, style, and mood. Include "flat illustration, dark \
background" unless the brand style says otherwise.
- Text overlays should be short key phrases (1-6 words) that reinforce the narration.
- Scene IDs must be unique and sequential: scene_001, scene_002, etc.

Multi-frame scene guidelines:
- Each scene gets a "frame_count" (1-8) and a "frame_prompts" array with that \
many entries. Multiple frames create smooth visual flow via crossfade transitions.
- Budget guidelines for frame_count:
  - Title/hook scenes (opening, segment intros): 6-8 frames
  - Key stat or dramatic reveal scenes: 4-5 frames
  - Standard explanation scenes: 2-3 frames
  - Filler/transition scenes: 1-2 frames
- Frame prompts should describe a visual PROGRESSION — e.g. zoom levels, \
before/after states, building diagrams step by step, cause then effect.
- All frames for a scene should depict the SAME subject — only the state, \
angle, or detail level changes between frames.
- Title card scenes (is_title_card: true) should have frame_count: 0 and \
empty frame_prompts — they use the programmatic title card system.
- The "visual_prompt" field remains as the primary/summary description of the scene."""


def generate_script(
    topic: str,
    description: str = "",
    brand_context: str = "",
    segment_count: int | None = None,
    animated_scene_count: int = 5,
    modifier_ids: list[str] | None = None,
    brand: dict | None = None,
) -> ScriptContent:
    """Generate a segmented video script via Claude.

    Args:
        topic: The video title/topic.
        description: Optional angle or description for the video.
        brand_context: Brand name + art style for tone/visual context.
        segment_count: Desired number of segments (Claude chooses if None).
        animated_scene_count: Number of scenes to mark as animated A/B flip.
        modifier_ids: Active content modifier IDs from the brand.
        brand: Brand profile dict for modifier hooks.

    Returns:
        A validated ScriptContent object.
    """
    user_parts = [f'Write a full segmented video script for: "{topic}"']
    if description:
        user_parts.append(f"Angle/description: {description}")
    if segment_count:
        # Constrain to even numbers for balanced grid layouts
        if segment_count % 2 != 0:
            segment_count = segment_count + 1
        user_parts.append(f"Target segment count: {segment_count}")
    else:
        user_parts.append(
            "Use exactly 6, 8, 10, or 12 segments (pick the most appropriate count for the topic)."
        )
    if brand_context:
        user_parts.append(f"Brand context (use for visual style and tone): {brand_context}")
    user_parts.append(
        "For each scene, set frame_count and provide that many frame_prompts "
        "describing a visual progression. Use the budget guidelines from the system prompt."
    )

    system_prompt = BASE_SYSTEM_PROMPT
    user_message = "\n".join(user_parts)

    # Apply modifier prompt hooks
    if modifier_ids:
        import pipeline.modifiers  # noqa: F401 — ensure registration
        from pipeline.modifiers.registry import get_active

        for mod in get_active(modifier_ids):
            system_prompt, user_message = mod.modify_script_prompt(system_prompt, user_message)

    raw = chat(system_prompt, user_message, max_tokens=8192)

    # Strip markdown fences if present
    text = raw.strip()
    if text.startswith("```"):
        text = text.split("\n", 1)[1]
        text = text.rsplit("```", 1)[0]

    data = json.loads(text)
    content = ScriptContent.model_validate(data)

    # Apply modifier post-processing hooks
    if modifier_ids:
        from pipeline.modifiers.registry import get_active

        brand_dict = brand or {}
        for mod in get_active(modifier_ids):
            content = mod.modify_script_post(content, brand_dict)

    return content
