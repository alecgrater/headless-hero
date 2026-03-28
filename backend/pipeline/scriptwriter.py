"""Script generation pipeline — uses Claude to write segmented video scripts."""

import json
from pathlib import Path

from integrations.claude_client import chat
from models.script import ScriptContent

_GUIDE_PATH = Path(__file__).resolve().parent.parent / "prompts" / "scriptwriting_guide.md"
_STYLE_GUIDE = _GUIDE_PATH.read_text() if _GUIDE_PATH.exists() else ""

SYSTEM_PROMPT = (_STYLE_GUIDE + "\n\n" if _STYLE_GUIDE else "") + """\
You are an expert YouTube scriptwriter specializing in educational/explainer \
content (like "Everything Professor" or "Kurzgesagt" style). Your job is to \
write a full, production-ready script broken into named segments with per-scene \
visual direction notes.

Output rules:
- Return ONLY valid JSON — no markdown fences, no commentary.
- Follow this exact structure:
{
  "title": "Video Title",
  "intro_hook": "A punchy 1-2 sentence hook that grabs the viewer in the first 5 seconds.",
  "outro_cta": "A call-to-action for the end of the video.",
  "segments": [
    {
      "name": "Segment Name",
      "scenes": [
        {
          "id": "scene_001",
          "narration": "The narration text the voiceover artist reads.",
          "visual_prompt": "Detailed description of what the illustration should depict.",
          "text_overlay": "Key text to display on screen (short phrase).",
          "duration_estimate_seconds": 8,
          "is_title_card": false,
          "is_animated": false,
          "visual_prompt_b": ""
        }
      ]
    }
  ]
}

Writing guidelines:
- The first scene of each segment should be a title card (is_title_card: true) \
  with the segment name as text_overlay and a short (2-3s) intro line.
- Each non-title scene should be 6-15 seconds of narration.
- Write narration in a conversational, engaging tone — not dry or academic.
- Use hooks, cliffhangers between segments, and smooth transitions.
- Visual prompts should be detailed enough for an AI image generator: describe \
  the subject, composition, style, and mood. Include "flat illustration, dark \
  background" unless the brand style says otherwise.
- Text overlays should be short key phrases (1-6 words) that reinforce the narration.
- Scene IDs must be unique and sequential: scene_001, scene_002, etc.

Animated scene guidelines:
- Some scenes should be marked as "animated" (is_animated: true) with a second \
  visual prompt (visual_prompt_b). These scenes will alternate between two images \
  (A/B flip) for added visual interest.
- For animated scenes, visual_prompt describes state A and visual_prompt_b describes \
  state B — they should depict the SAME subject in two distinct states (e.g., \
  before/after, cause/effect, open/closed, lit/dark, full/empty).
- Do NOT animate title card scenes (is_title_card: true).
- For non-animated scenes, leave is_animated as false and visual_prompt_b as "".
"""

def generate_script(
    topic: str,
    description: str = "",
    brand_context: str = "",
    segment_count: int | None = None,
    animated_scene_count: int = 5,
) -> ScriptContent:
    """Generate a segmented video script via Claude.

    Args:
        topic: The video title/topic.
        description: Optional angle or description for the video.
        brand_context: Brand name + art style for tone/visual context.
        segment_count: Desired number of segments (Claude chooses if None).
        animated_scene_count: Number of scenes to mark as animated A/B flip.

    Returns:
        A validated ScriptContent object.
    """
    user_parts = [f'Write a full segmented video script for: "{topic}"']
    if description:
        user_parts.append(f"Angle/description: {description}")
    if segment_count:
        user_parts.append(f"Target segment count: {segment_count}")
    else:
        user_parts.append(
            "Choose an appropriate number of segments (typically 8-15 for a long-form video)."
        )
    if brand_context:
        user_parts.append(f"Brand context (use for visual style and tone): {brand_context}")
    if animated_scene_count > 0:
        user_parts.append(
            f"Mark approximately {animated_scene_count} non-title-card scenes as animated "
            f"(is_animated: true) with a visual_prompt_b describing a second visual state."
        )
    else:
        user_parts.append("Do not mark any scenes as animated (all is_animated: false).")

    user_message = "\n".join(user_parts)

    raw = chat(SYSTEM_PROMPT, user_message, max_tokens=8192)

    # Strip markdown fences if present
    text = raw.strip()
    if text.startswith("```"):
        text = text.split("\n", 1)[1]
        text = text.rsplit("```", 1)[0]

    data = json.loads(text)
    return ScriptContent.model_validate(data)
