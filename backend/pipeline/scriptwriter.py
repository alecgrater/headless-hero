"""Script generation pipeline — uses Claude to write segmented video scripts."""

import json
import logging
import os
import re
import time
from collections.abc import Callable
from pathlib import Path

from config import strip_markdown_fences
from integrations.claude_client import chat
from models.script import Scene, ScriptContent, Segment

logger = logging.getLogger(__name__)

_GUIDE_PATH = Path(__file__).resolve().parent.parent / "prompts" / "scriptwriting_guide.md"
_STYLE_GUIDE = _GUIDE_PATH.read_text() if _GUIDE_PATH.exists() else ""

_SYSTEM_PROMPT_PATH = Path(__file__).resolve().parent.parent / "prompts" / "script_system.md"
_SYSTEM_PROMPT_BODY = _SYSTEM_PROMPT_PATH.read_text() if _SYSTEM_PROMPT_PATH.exists() else ""

# Base system prompt — title card instructions are injected separately.
BASE_SYSTEM_PROMPT = (_STYLE_GUIDE + "\n\n" if _STYLE_GUIDE else "") + _SYSTEM_PROMPT_BODY


def _warn_visual_monotony(content: "ScriptContent") -> None:
    """Log a warning if 3+ consecutive scenes share the same [SHOT_TYPE] prefix.

    Advisory only — does not block script generation.
    """
    _SHOT_LABEL_RE = re.compile(r"^\[([A-Z\-]+)\]")

    all_scenes = [scene for seg in content.segments for scene in seg.scenes]
    shot_types: list[str] = []
    for scene in all_scenes:
        if scene.is_title_card:
            shot_types.append("TITLE_CARD")
            continue
        m = _SHOT_LABEL_RE.match(scene.visual_prompt or "")
        shot_types.append(m.group(1) if m else "UNLABELED")

    run_type = shot_types[0] if shot_types else None
    run_len = 1
    for i in range(1, len(shot_types)):
        if shot_types[i] == run_type and run_type not in ("TITLE_CARD", "UNLABELED"):
            run_len += 1
            if run_len >= 3:
                logger.warning(
                    "Visual monotony detected: shot type [%s] used in %d+ consecutive "
                    "scenes (scenes %d–%d). Consider varying the visual storytelling arc.",
                    run_type,
                    run_len,
                    i - run_len + 2,
                    i + 1,
                )
        else:
            run_type = shot_types[i]
            run_len = 1

    # Also check visual_beat monotony (3+ consecutive same beat type)
    beat_types: list[str] = []
    for scene in all_scenes:
        if scene.is_title_card:
            beat_types.append("TITLE_CARD")
        else:
            beat_types.append(scene.visual_beat or "static")

    run_beat = beat_types[0] if beat_types else None
    run_len = 1
    for i in range(1, len(beat_types)):
        if beat_types[i] == run_beat and run_beat != "TITLE_CARD":
            run_len += 1
            if run_len >= 3:
                logger.warning(
                    "Visual beat monotony detected: beat type '%s' used in %d+ consecutive "
                    "scenes (scenes %d–%d). Consider varying visual beat types.",
                    run_beat,
                    run_len,
                    i - run_len + 2,
                    i + 1,
                )
        else:
            run_beat = beat_types[i]
            run_len = 1


def generate_script(
    topic: str,
    description: str = "",
    brand_context: str = "",
    segment_count: int | None = None,
    animated_scene_count: int = 5,
    brand: dict | None = None,
    model: str | None = None,
    segmented: bool = False,
    progress_callback: Callable[[int, int, str], None] | None = None,
) -> ScriptContent:
    """Generate a segmented video script via Claude.

    Args:
        topic: The video title/topic.
        description: Optional angle or description for the video.
        brand_context: Brand name + art style for tone/visual context.
        segment_count: Desired number of segments (Claude chooses if None).
        animated_scene_count: Number of scenes to mark as animated A/B flip.
        brand: Brand profile dict for modifier hooks.
        model: Override SCRIPT_MODEL setting for this request.
        segmented: Use two-phase segmented generation (one API call per segment).

    Returns:
        A validated ScriptContent object.
    """
    resolved_model = model or os.environ.get("SCRIPT_MODEL", "anthropic.claude-opus-4-6-v1")

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
            "Use exactly 6 or 8 segments (pick the most appropriate count for the topic)."
        )
    if brand_context:
        user_parts.append(f"Brand context (use for visual style and tone): {brand_context}")
    user_parts.append(
        "For each scene, set visual_beat and provide matching frame_directives "
        "following the Visual Beat System guidelines. Use varied beat types "
        "across the video for maximum visual energy. "
        "Every visual_prompt must begin with a [SHOT_TYPE] label from the Visual "
        "storytelling arc palette."
    )

    system_prompt = BASE_SYSTEM_PROMPT
    user_message = "\n".join(user_parts)

    # Always apply title card instructions (title cards are always active)
    from pipeline.modifiers.title_cards import TITLE_CARD_PROMPT_INSTRUCTIONS
    system_prompt += TITLE_CARD_PROMPT_INSTRUCTIONS

    if segmented:
        logger.info("Using SEGMENTED generation for topic %r (model=%s)", topic, resolved_model)
        content = _generate_segmented(
            system_prompt=system_prompt,
            user_message=user_message,
            topic=topic,
            description=description,
            brand_context=brand_context,
            segment_count=segment_count,
            model=resolved_model,
            progress_callback=progress_callback,
        )
    else:
        logger.info("Generating script for topic %r using model=%s (segments=%s)", topic, resolved_model, segment_count)
        raw = chat(system_prompt, user_message, model=resolved_model, max_tokens=16384, timeout=900.0)

        # Strip markdown fences if present
        text = strip_markdown_fences(raw)

        if not text.endswith("}"):
            raise RuntimeError(
                "Script generation failed: Claude response was truncated. "
                "The generated script was too long to fit within the token limit. "
                "Try a simpler topic or fewer segments."
            )

        data = json.loads(text)
        content = ScriptContent.model_validate(data)

    # Always enforce title card constraints
    from pipeline.modifiers.title_cards import enforce_title_cards_and_min_scenes
    content = enforce_title_cards_and_min_scenes(content)

    logger.info("Script generated for topic %r: %s segments, %s total scenes",
                topic, len(content.segments), sum(len(s.scenes) for s in content.segments))
    _warn_visual_monotony(content)
    return content


# ---------------------------------------------------------------------------
# Segmented generation (two-phase)
# ---------------------------------------------------------------------------

_OUTLINE_INSTRUCTIONS = """\
IMPORTANT: Return ONLY the script outline — NO scenes, NO narration.
Return valid JSON with this structure:
{
  "title": "Video Title",
  "card_title": "SHORT TITLE",
  "card_title_highlight_word": "KEYWORD",
  "intro_hook": "A punchy 1-2 sentence hook.",
  "outro_cta": "A call-to-action for the end.",
  "segments": [
    {
      "name": "Segment Name",
      "circle_color": "#e91e63",
      "title_card_image_prompt": "Visual description for the segment circle image.",
      "topic_summary": "2-3 sentences describing what this segment covers — key points, narrative arc, what the viewer learns."
    }
  ]
}
Do NOT include any scenes. Only segment metadata and topic summaries.
"""

_SEGMENT_SCENES_INSTRUCTIONS = """\
You are writing scenes for ONE segment of a larger video script.
The full script outline is provided below for narrative context — write ONLY \
the scenes for the specified segment.

Return ONLY a valid JSON array of scene objects. Example:
[
  {
    "id": "scene_001",
    "narration": "...",
    "visual_prompt": "[SHOT_TYPE] ...",
    "duration_estimate_seconds": 8,
    "is_title_card": false,
    "visual_beat": "quick_cuts",
    "frame_directives": [
      {"prompt": "...", "source": "ai_generated", "transition": "cut", "reference_previous": false, "search_query": ""},
      {"prompt": "...", "source": "ai_generated", "transition": "cut", "reference_previous": false, "search_query": ""}
    ]
  }
]

RULES:
- The FIRST scene of EVERY segment MUST be a title card (is_title_card: true, visual_beat: "static", frame_directives: []).
- After the title card, write 4-7 content scenes.
- Scene IDs should start at scene_001 within this segment (they will be renumbered globally later).
- Follow all visual storytelling arc, Visual Beat System, and shot type guidelines from the system prompt.
- Return ONLY the JSON array — no markdown fences, no commentary.
"""


def _generate_outline(
    system_prompt: str,
    user_message: str,
    model: str,
) -> dict:
    """Phase 1: Generate script outline (no scenes) via a single small Claude call."""
    t0 = time.monotonic()
    logger.info("SEGMENTED: Phase 1 — generating outline (model=%s)", model)

    outline_msg = user_message + "\n\n" + _OUTLINE_INSTRUCTIONS
    raw = chat(system_prompt, outline_msg, model=model, max_tokens=4096, timeout=180.0)
    text = strip_markdown_fences(raw)

    if not text.endswith("}"):
        raise RuntimeError(
            "SEGMENTED: Outline generation failed — response was truncated."
        )

    outline = json.loads(text)
    elapsed = time.monotonic() - t0

    seg_count = len(outline.get("segments", []))
    logger.info(
        "SEGMENTED: Outline generated in %.1fs — %d segments, title=%r",
        elapsed, seg_count, outline.get("title", "?"),
    )
    for i, seg in enumerate(outline.get("segments", [])):
        logger.info(
            "SEGMENTED:   Segment %d: %r — %s",
            i + 1, seg.get("name", "?"), seg.get("topic_summary", "")[:80],
        )

    return outline


def _generate_segment_scenes(
    system_prompt: str,
    outline: dict,
    segment_index: int,
    model: str,
) -> list[Scene]:
    """Phase 2: Generate scenes for a single segment."""
    segment = outline["segments"][segment_index]
    seg_name = segment.get("name", f"Segment {segment_index + 1}")
    total = len(outline["segments"])

    t0 = time.monotonic()
    logger.info(
        "SEGMENTED: Phase 2 — generating scenes for segment %d/%d: %r",
        segment_index + 1, total, seg_name,
    )

    # Build the per-segment user message with full outline context
    outline_json = json.dumps(outline, indent=2)
    user_msg = (
        f"FULL SCRIPT OUTLINE (for context — do NOT write scenes for other segments):\n"
        f"```json\n{outline_json}\n```\n\n"
        f"WRITE SCENES FOR SEGMENT {segment_index + 1}/{total}: \"{seg_name}\"\n"
        f"Topic summary: {segment.get('topic_summary', '')}\n"
        f"Circle color: {segment.get('circle_color', '#e91e63')}\n"
        f"Title card image prompt: {segment.get('title_card_image_prompt', '')}\n\n"
        f"{_SEGMENT_SCENES_INSTRUCTIONS}"
    )

    raw = chat(system_prompt, user_msg, model=model, max_tokens=8192, timeout=300.0)
    text = strip_markdown_fences(raw)

    if not text.rstrip().endswith("]"):
        raise RuntimeError(
            f"SEGMENTED: Segment {segment_index + 1}/{total} (\"{seg_name}\") "
            f"response was truncated. The segment may have too many scenes."
        )

    scenes_data = json.loads(text)
    scenes = [Scene.model_validate(s) for s in scenes_data]

    elapsed = time.monotonic() - t0
    logger.info(
        "SEGMENTED: Segment %d/%d (%r) complete in %.1fs — %d scenes",
        segment_index + 1, total, seg_name, elapsed, len(scenes),
    )

    return scenes


def _generate_segmented(
    system_prompt: str,
    user_message: str,
    topic: str,
    description: str,
    brand_context: str,
    segment_count: int | None,
    model: str,
    progress_callback: Callable[[int, int, str], None] | None = None,
) -> ScriptContent:
    """Orchestrate two-phase segmented script generation."""
    total_t0 = time.monotonic()

    # Phase 1: outline
    outline = _generate_outline(system_prompt, user_message, model)

    # Phase 2: per-segment scene generation (sequential for coherence)
    segments: list[Segment] = []
    global_scene_id = 1

    for i, seg_outline in enumerate(outline["segments"]):
        seg_name = seg_outline.get("name", f"Segment {i + 1}")
        if progress_callback:
            progress_callback(i + 1, len(outline["segments"]), seg_name)
        try:
            scenes = _generate_segment_scenes(system_prompt, outline, i, model)
        except Exception as e:
            seg_name = seg_outline.get("name", f"Segment {i + 1}")
            raise RuntimeError(
                f"Segmented script generation failed on segment {i + 1}/{len(outline['segments'])} "
                f"(\"{seg_name}\"): {e}"
            ) from e

        # Re-number scene IDs globally
        for scene in scenes:
            scene.id = f"scene_{global_scene_id:03d}"
            global_scene_id += 1

        segments.append(Segment(
            name=seg_outline.get("name", f"Segment {i + 1}"),
            scenes=scenes,
            circle_color=seg_outline.get("circle_color", "#e91e63"),
            title_card_image_prompt=seg_outline.get("title_card_image_prompt", ""),
        ))

    # Assemble final ScriptContent
    content = ScriptContent(
        title=outline.get("title", topic),
        segments=segments,
        intro_hook=outline.get("intro_hook", ""),
        outro_cta=outline.get("outro_cta", ""),
        card_title=outline.get("card_title", ""),
        card_title_highlight_word=outline.get("card_title_highlight_word", ""),
    )

    total_elapsed = time.monotonic() - total_t0
    total_scenes = sum(len(s.scenes) for s in segments)
    logger.info(
        "SEGMENTED: Assembly complete — %d segments, %d total scenes, total time %.1fs",
        len(segments), total_scenes, total_elapsed,
    )

    return content
