"""Script generation pipeline — uses Claude to write segmented video scripts."""

import json
import logging
from pathlib import Path

from integrations.claude_client import chat
from models.script import Scene, ScriptContent, TextOverlayConfig

logger = logging.getLogger(__name__)

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
          "visual_prompt_b": "",
          "media_type": "ai_generated",
          "search_query": ""
        }
      ]
    }
  ]
}

Writing guidelines:
- The first scene of each segment MUST be a title card (is_title_card: true) \
  with the segment name as text_overlay and a short (2-3s) intro line.
- Title card scenes MUST have visual_prompt set to "" (empty string) — their \
  visuals are generated programmatically from brand colors, not by AI image gen.
- Title card scenes MUST have text_overlay_config with style "title_card", \
  position "center", and animation "fade_in".
- Each segment MUST have at least 5 scenes (including the title card).
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

Real media guidelines (gaming/hardware content):
- Each scene has a "media_type" field: "ai_generated" (default), "gameplay_clip", or "hardware_image".
- Each scene has a "search_query" field (empty string by default).
- When the video topic involves gaming, video games, consoles, or gaming hardware:
  - Tag scenes showing actual gameplay footage as "gameplay_clip" with a specific YouTube \
    search query (e.g. "Halo Infinite gameplay 4K", "GTA V PC gameplay 60fps"). The search \
    query should be specific enough to find relevant footage.
  - Tag scenes showing physical hardware (consoles, controllers, headsets, GPUs) as \
    "hardware_image" with a search query (e.g. "PlayStation 5 console close up review", \
    "RTX 4090 unboxing"). These will extract a still frame from a YouTube video.
  - All other scenes (conceptual, explanatory, metaphorical, title cards) should remain \
    "ai_generated" with an empty search_query — AI illustration is better for abstract concepts.
- Only use real media types when showing specific, recognizable games or hardware. If a scene \
  is about a general concept (e.g. "the evolution of gaming"), keep it as ai_generated.
- Include "media_type" and "search_query" in each scene object in the JSON output.
"""

def _enforce_title_cards_and_min_scenes(content: ScriptContent) -> ScriptContent:
    """Post-process script to ensure title card consistency and minimum scene counts.

    - Ensures first scene of every segment is is_title_card: true
    - Clears visual_prompt on all title cards (programmatic generation)
    - Sets text_overlay to segment name if empty
    - Sets text_overlay_config to title_card defaults if missing
    - Logs warning if segment has fewer than 5 scenes
    """
    scene_counter = 0
    for seg in content.segments:
        # Count existing scenes for ID generation
        for sc in seg.scenes:
            num = int(sc.id.replace("scene_", "")) if sc.id.startswith("scene_") else 0
            scene_counter = max(scene_counter, num)

    for seg in content.segments:
        # Ensure first scene is a title card
        if not seg.scenes or not seg.scenes[0].is_title_card:
            scene_counter += 1
            title_scene = Scene(
                id=f"scene_{scene_counter:03d}",
                narration=f"Welcome to {seg.name}.",
                visual_prompt="",
                text_overlay=seg.name,
                duration_estimate_seconds=3.0,
                is_title_card=True,
                text_overlay_config=TextOverlayConfig(
                    position="center",
                    style="title_card",
                    animation="fade_in",
                ),
            )
            seg.scenes.insert(0, title_scene)

        # Enforce title card properties on all title cards in this segment
        for sc in seg.scenes:
            if sc.is_title_card:
                sc.visual_prompt = ""
                sc.visual_prompt_b = ""
                sc.is_animated = False
                if not sc.text_overlay:
                    sc.text_overlay = seg.name
                if not sc.text_overlay_config or sc.text_overlay_config.style != "title_card":
                    sc.text_overlay_config = TextOverlayConfig(
                        position="center",
                        style="title_card",
                        animation="fade_in",
                    )

        if len(seg.scenes) < 5:
            logger.warning(
                "Segment %r has only %d scenes (minimum recommended: 5)",
                seg.name,
                len(seg.scenes),
            )

    return content


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
    content = ScriptContent.model_validate(data)
    return _enforce_title_cards_and_min_scenes(content)
