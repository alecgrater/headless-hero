"""Script generation pipeline — uses Claude to write segmented video scripts."""

from __future__ import annotations

import json
from typing import Optional

from integrations.claude_client import chat
from models.script import ScriptContent


SYSTEM_PROMPT = """\
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
          "is_title_card": false
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
"""


def generate_script(
    topic: str,
    description: str = "",
    brand_context: str = "",
    segment_count: Optional[int] = None,
) -> ScriptContent:
    """Generate a segmented video script via Claude.

    Args:
        topic: The video title/topic.
        description: Optional angle or description for the video.
        brand_context: Brand name + art style for tone/visual context.
        segment_count: Desired number of segments (Claude chooses if None).

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

    user_message = "\n".join(user_parts)

    raw = chat(SYSTEM_PROMPT, user_message, max_tokens=8192)

    # Strip markdown fences if present
    text = raw.strip()
    if text.startswith("```"):
        text = text.split("\n", 1)[1]
        text = text.rsplit("```", 1)[0]

    data = json.loads(text)
    return ScriptContent.model_validate(data)
