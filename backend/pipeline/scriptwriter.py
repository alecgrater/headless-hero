"""Script generation pipeline — uses the routed LLM provider to write segmented video scripts."""

import json
import logging
import re
import time
from collections.abc import Callable

from config import DEFAULT_ACCENT_COLOR, SEGMENT_COUNT, strip_markdown_fences
from integrations.llm_client import chat
from models.script import Scene, ScriptContent, Segment
from prompts import SCRIPT_OUTLINE_INSTRUCTIONS, SCRIPT_SEGMENT_SCENES_INSTRUCTIONS, SCRIPT_SYSTEM

logger = logging.getLogger(__name__)

# Base system prompt — title card instructions are injected separately.
BASE_SYSTEM_PROMPT = SCRIPT_SYSTEM.template

ALL_BEAT_TYPES = ["static", "continuous", "quick_cuts", "aha_subtitle", "montage"]

_SHOT_LABEL_RE = re.compile(r"^\[([A-Z\-]+)\]")


def _find_runs(labels: list[str], skip: set[str], threshold: int = 3) -> list[tuple[str, int, int, int]]:
    """Find runs of consecutive identical labels that meet or exceed *threshold*.

    Returns a list of (label, run_length, start_1indexed, end_1indexed) — one
    entry per run, emitted only once when the run ends (or at list end).
    """
    runs: list[tuple[str, int, int, int]] = []
    if not labels:
        return runs

    cur = labels[0]
    run_start = 0
    run_len = 1

    for i in range(1, len(labels)):
        if labels[i] == cur:
            run_len += 1
        else:
            if run_len >= threshold and cur not in skip:
                runs.append((cur, run_len, run_start + 1, run_start + run_len))
            cur = labels[i]
            run_start = i
            run_len = 1

    if run_len >= threshold and cur not in skip:
        runs.append((cur, run_len, run_start + 1, run_start + run_len))

    return runs


def _fix_visual_monotony(content: "ScriptContent") -> int:
    """Detect and fix monotonous runs of beat types in-place.

    Breaks up runs of 3+ consecutive identical beat types by reassigning
    every 3rd scene in a run to an alternative beat type. This preserves
    narration and flow while ensuring visual variety.

    Returns the number of scenes that were reassigned.
    """
    all_scenes = content.all_scenes()
    if not all_scenes:
        return 0

    fixes = 0

    # Build beat type list (skip title cards)
    beat_types: list[str] = []
    for scene in all_scenes:
        if scene.is_title_card:
            beat_types.append("TITLE_CARD")
        else:
            beat_types.append(scene.visual_beat or "static")

    for label, length, start_1, end_1 in _find_runs(beat_types, {"TITLE_CARD"}):
        # start_1/end_1 are 1-indexed; convert to 0-indexed
        start = start_1 - 1
        # Reassign every 3rd scene in the run to break it up
        # (keeps the rhythm: original-original-variety-original-original-variety)
        for i in range(start + 2, start + length, 3):
            scene = all_scenes[i]
            if scene.is_title_card:
                continue
            alternatives = [b for b in ALL_BEAT_TYPES if b != label]
            # Pick based on position for determinism — cycle through alternatives
            new_beat = alternatives[i % len(alternatives)]
            logger.info(
                "Monotony fix: scene %d beat '%s' → '%s' (was in run of %d)",
                i + 1, label, new_beat, length,
            )
            scene.visual_beat = new_beat
            fixes += 1

    if fixes:
        logger.info("Fixed %d scene(s) to break visual monotony", fixes)

    return fixes


def generate_script(
    topic: str,
    description: str = "",
    brand_context: str = "",
    animated_scene_count: int = 5,
    brand: dict | None = None,
    model: str | None = None,
    segmented: bool = False,
    cold_open_text: str | None = None,
    progress_callback: Callable[[int, int, str], None] | None = None,
    gameplay_enabled: bool = False,
    stock_photo_enabled: bool = False,
) -> ScriptContent:
    """Generate a segmented video script via the routed LLM provider.

    Args:
        topic: The video title/topic.
        description: Optional angle or description for the video.
        brand_context: Brand name + art style for tone/visual context.
        animated_scene_count: Number of scenes to mark as animated A/B flip.
        brand: Brand profile dict for modifier hooks.
        model: Override SCRIPT_MODEL setting for this request.
        segmented: Use two-phase segmented generation (one API call per segment).

    Returns:
        A validated ScriptContent object.
    """
    from pipeline.modifiers.title_cards import TITLE_CARD_PROMPT_INSTRUCTIONS, enforce_title_cards_and_min_scenes
    from pipeline.script_reviewer import review_script

    resolved_model = model

    user_parts = [f'Write a full segmented video script for: "{topic}"']
    if description:
        user_parts.append(f"Angle/description: {description}")
    user_parts.append(f"Use exactly {SEGMENT_COUNT} segments.")
    if brand_context:
        user_parts.append(f"Brand context (use for visual style and tone): {brand_context}")
    user_parts.append(
        "For each scene, set visual_beat and provide matching frame_directives "
        "following the Visual Beat System guidelines. Use varied beat types "
        "across the video for maximum visual energy. "
        "Every visual_prompt must begin with a [SHOT_TYPE] label from the Visual "
        "storytelling arc palette."
    )
    if cold_open_text:
        user_parts.append(
            "MANDATORY COLD OPEN — use this EXACT opening for the video.\n"
            "The intro_hook and first 2-3 content scenes MUST use this text verbatim "
            "or with minimal polish. Build the rest of the script to flow naturally "
            "from this opening:\n\n"
            f"{cold_open_text}"
        )

    system_prompt = BASE_SYSTEM_PROMPT
    base_user_message = "\n".join(user_parts)

    # Constrain media_source options based on enabled flags
    media_source_constraint = ""
    allowed_sources = ["ai"]
    if gameplay_enabled:
        allowed_sources.append("gameplay_video")
    if stock_photo_enabled:
        allowed_sources.append("stock_photo")
    if len(allowed_sources) < 3:
        media_source_constraint = (
            f"MEDIA SOURCE CONSTRAINT: Only use these media_source values: "
            f"{', '.join(allowed_sources)}. Set all scenes to one of these options.\n\n"
        )
        base_user_message += f"\n\n{media_source_constraint.strip()}"

    # Always apply title card instructions (title cards are always active)
    system_prompt += TITLE_CARD_PROMPT_INSTRUCTIONS

    # --- Single generation pass (no retry loop) ---
    if segmented:
        logger.info("Using SEGMENTED generation for topic %r, description=%r (model=%s)", topic, description, resolved_model or "configured")
        content = _generate_segmented(
            system_prompt=system_prompt,
            user_message=base_user_message,
            topic=topic,
            description=description,
            brand_context=brand_context,
            model=resolved_model,
            progress_callback=progress_callback,
            media_source_constraint=media_source_constraint,
        )
    else:
        logger.info("Generating script for topic %r, description=%r using model=%s (segments=%d)", topic, description, resolved_model or "configured", SEGMENT_COUNT)
        raw = chat(
            system_prompt,
            base_user_message,
            model=resolved_model,
            max_tokens=16384,
            timeout=900.0,
            json_mode=True,
            task="script",
        )

        text = strip_markdown_fences(raw)

        if not text.endswith("}"):
            raise RuntimeError(
                "Script generation failed: LLM response was truncated. "
                "The generated script was too long to fit within the token limit. "
                "Try a simpler topic or fewer segments."
            )

        data = json.loads(text)
        content = ScriptContent.model_validate(data)

    # Always enforce title card constraints
    content = enforce_title_cards_and_min_scenes(content)

    # Fix visual monotony in-place (no regeneration needed)
    _fix_visual_monotony(content)

    # Run Gemini quality review for logging/metrics only (non-blocking)
    if progress_callback:
        progress_callback(0, 0, "Reviewing script quality...")
    try:
        review = review_script(content)
        pass_count = review.pass_count()
        if review.overall_pass:
            logger.info("Script quality review passed (%d/5 skillsets)", pass_count)
        else:
            logger.warning(
                "Script quality review: %d/5 skillsets passed (non-blocking). Issues: %s",
                pass_count, review.critique_summary(),
            )
    except Exception:
        logger.warning("Script quality review failed — continuing", exc_info=True)

    # Persist multi-source media settings on the script
    content.gameplay_enabled = gameplay_enabled
    content.stock_photo_enabled = stock_photo_enabled

    logger.info("Script generated for topic %r: %s segments, %s total scenes",
                topic, len(content.segments), sum(len(s.scenes) for s in content.segments))
    return content


# ---------------------------------------------------------------------------
# Segmented generation (two-phase)
# ---------------------------------------------------------------------------

_OUTLINE_INSTRUCTIONS = SCRIPT_OUTLINE_INSTRUCTIONS.template

_SEGMENT_SCENES_INSTRUCTIONS = SCRIPT_SEGMENT_SCENES_INSTRUCTIONS.template


def _generate_outline(
    system_prompt: str,
    user_message: str,
    model: str | None,
) -> dict:
    """Phase 1: Generate script outline (no scenes) via a single small LLM call."""
    t0 = time.monotonic()
    logger.info("SEGMENTED: Phase 1 — generating outline (model=%s)", model)

    outline_msg = user_message + "\n\n" + _OUTLINE_INSTRUCTIONS
    raw = chat(system_prompt, outline_msg, model=model, max_tokens=4096, timeout=180.0, json_mode=True, task="script")
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
    model: str | None,
    trailing_context: str = "",
    media_source_constraint: str = "",
) -> list[Scene]:
    """Phase 2: Generate scenes for a single segment."""
    segment = outline["segments"][segment_index]
    seg_name = segment.get("name", f"Segment {segment_index + 1}")
    total = len(outline["segments"])

    t0 = time.monotonic()
    logger.info(
        "SEGMENTED: Phase 2 — generating scenes for segment %d/%d: %r (model=%s)",
        segment_index + 1, total, seg_name, model,
    )

    # Build the per-segment user message with full outline context
    outline_json = json.dumps(outline, indent=2)
    user_msg = (
        f"FULL SCRIPT OUTLINE (for context — do NOT write scenes for other segments):\n"
        f"```json\n{outline_json}\n```\n\n"
        f"WRITE SCENES FOR SEGMENT {segment_index + 1}/{total}: \"{seg_name}\"\n"
        f"Topic summary: {segment.get('topic_summary', '')}\n"
        f"Circle color: {segment.get('circle_color', DEFAULT_ACCENT_COLOR)}\n"
        f"Title card image prompt: {segment.get('title_card_image_prompt', '')}\n\n"
        f"{trailing_context}"
        f"{media_source_constraint}"
        f"{_SEGMENT_SCENES_INSTRUCTIONS}"
    )

    raw = chat(system_prompt, user_msg, model=model, max_tokens=16384, timeout=300.0, json_mode=True, task="script")
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
    model: str | None,
    progress_callback: Callable[[int, int, str], None] | None = None,
    media_source_constraint: str = "",
) -> ScriptContent:
    """Orchestrate two-phase segmented script generation."""
    total_t0 = time.monotonic()

    # Phase 1: outline
    outline = _generate_outline(system_prompt, user_message, model)

    # Phase 2: per-segment scene generation (sequential for coherence)
    segments: list[Segment] = []
    global_scene_id = 1
    trailing_context = ""

    for i, seg_outline in enumerate(outline["segments"]):
        seg_name = seg_outline.get("name", f"Segment {i + 1}")
        if progress_callback:
            progress_callback(i + 1, len(outline["segments"]), seg_name)
        try:
            scenes = _generate_segment_scenes(system_prompt, outline, i, model, trailing_context, media_source_constraint)
        except Exception as e:
            seg_name = seg_outline.get("name", f"Segment {i + 1}")
            raise RuntimeError(
                f"Segmented script generation failed on segment {i + 1}/{len(outline['segments'])} "
                f"(\"{seg_name}\"): {e}"
            ) from e

        # Build cross-segment continuity context for the next segment
        if i < len(outline["segments"]) - 1:
            tail = scenes[-3:]
            trail_parts: list[str] = []
            for s in tail:
                if s.is_title_card:
                    trail_parts.append("title_card")
                else:
                    shot_m = _SHOT_LABEL_RE.match(s.visual_prompt or "")
                    shot = shot_m.group(1) if shot_m else "UNLABELED"
                    beat = s.visual_beat or "static"
                    trail_parts.append(f"{beat} / [{shot}]")
            trailing_context = (
                "CROSS-SEGMENT CONTINUITY — the previous segment ended with these scenes "
                f"(most recent last): {', '.join(trail_parts)}. "
                "Vary the opening beat and shot types of THIS segment to avoid monotony "
                "across the segment boundary.\n\n"
            )

        # Re-number scene IDs globally
        for scene in scenes:
            scene.id = f"scene_{global_scene_id:03d}"
            global_scene_id += 1

        segments.append(Segment(
            name=seg_outline.get("name", f"Segment {i + 1}"),
            short_name=seg_outline.get("short_name", ""),
            scenes=scenes,
            circle_color=seg_outline.get("circle_color", DEFAULT_ACCENT_COLOR),
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
        card_subtitle=outline.get("card_subtitle", ""),
    )

    total_elapsed = time.monotonic() - total_t0
    total_scenes = sum(len(s.scenes) for s in segments)
    logger.info(
        "SEGMENTED: Assembly complete — %d segments, %d total scenes, total time %.1fs",
        len(segments), total_scenes, total_elapsed,
    )

    return content
