"""Scene refinement pipeline — polishes human-edited scenes to match script tone."""

import json
import logging

from config import strip_markdown_fences
from integrations.claude_client import chat
from models.script import Scene, ScriptContent

logger = logging.getLogger(__name__)

SYSTEM_PROMPT = """\
You are an expert YouTube scriptwriter. A human editor has revised one scene in \
a video script. Your job is to polish the edited text so it matches the tone, \
style, pacing, and vocabulary of the surrounding script — while preserving the \
human's intended meaning and content changes.

Rules:
- Maintain the same conversational, engaging tone as the rest of the script.
- Keep the narration length roughly the same (do not drastically expand or shrink).
- Preserve any new facts, angles, or emphasis the human introduced.
- If the text_overlay was edited, polish it to be punchy (1-6 words).
- Keep the visual_prompt and other fields unchanged unless they conflict with the \
  edited narration (in which case, update the visual_prompt to match).
- Return ONLY valid JSON — no markdown fences, no commentary.
- Return a single scene object with the same keys as the input.
"""


def refine_scene(
    script: ScriptContent,
    segment_index: int,
    scene_id: str,
) -> Scene:
    """Refine a human-edited scene to match the surrounding script's tone.

    Args:
        script: The full script content for context.
        segment_index: Index of the segment containing the scene.
        scene_id: ID of the scene to refine.

    Returns:
        A refined Scene object.
    """
    segment = script.segments[segment_index]
    target_scene = next(s for s in segment.scenes if s.id == scene_id)

    logger.info("Refining scene %s in segment %d", scene_id, segment_index)

    # Build context: surrounding scenes for tone reference
    context_scenes: list[dict] = []
    for seg in script.segments:
        for sc in seg.scenes:
            context_scenes.append({
                "id": sc.id,
                "narration": sc.narration,
                "text_overlay": sc.text_overlay,
            })

    user_message = json.dumps({
        "script_title": script.title,
        "intro_hook": script.intro_hook,
        "surrounding_context": context_scenes,
        "segment_name": segment.name,
        "scene_to_refine": target_scene.model_dump(),
    })

    raw = chat(SYSTEM_PROMPT, user_message, max_tokens=2048)

    text = strip_markdown_fences(raw)

    data = json.loads(text)
    # Preserve fields that shouldn't change
    data["id"] = target_scene.id
    data["is_title_card"] = target_scene.is_title_card
    data["image_url"] = target_scene.image_url
    data["audio_url"] = target_scene.audio_url
    data["audio_duration_seconds"] = target_scene.audio_duration_seconds

    refined = Scene.model_validate(data)
    logger.info("Scene %s refined successfully", scene_id)
    return refined
