"""Script generation pipeline — uses Claude to write segmented video scripts."""

import json
import logging
import os
import re
import time
from collections.abc import Callable

from config import DEFAULT_ACCENT_COLOR, DEFAULT_CLAUDE_MODEL, SEGMENT_COUNT, strip_markdown_fences
from integrations.claude_client import chat
from models.script import Scene, ScriptContent, Segment
from prompts import SCRIPT_OUTLINE_INSTRUCTIONS, SCRIPT_RETRY_CRITIQUE, SCRIPT_SEGMENT_SCENES_INSTRUCTIONS, SCRIPT_SYSTEM

logger = logging.getLogger(__name__)

# Base system prompt — title card instructions are injected separately.
BASE_SYSTEM_PROMPT = SCRIPT_SYSTEM.template

# Maximum number of generation attempts (initial + retries on review failure)
MAX_ATTEMPTS = 3

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


def _check_visual_monotony(content: "ScriptContent") -> list[str]:
    """Detect monotonous runs of shot types or beat types.

    Returns a list of human-readable critique strings (empty = no issues).
    Also logs each issue as a warning for dev dashboard visibility.
    """
    issues: list[str] = []
    all_scenes = content.all_scenes()

    shot_types: list[str] = []
    for scene in all_scenes:
        if scene.is_title_card:
            shot_types.append("TITLE_CARD")
            continue
        m = _SHOT_LABEL_RE.match(scene.visual_prompt or "")
        shot_types.append(m.group(1) if m else "UNLABELED")

    for label, length, start, end in _find_runs(shot_types, {"TITLE_CARD", "UNLABELED"}):
        msg = f"Shot type [{label}] repeated {length} consecutive scenes ({start}–{end})"
        logger.warning("Visual monotony: %s", msg)
        issues.append(msg)

    beat_types: list[str] = []
    for scene in all_scenes:
        if scene.is_title_card:
            beat_types.append("TITLE_CARD")
        else:
            beat_types.append(scene.visual_beat or "static")

    for label, length, start, end in _find_runs(beat_types, {"TITLE_CARD"}):
        msg = f"Beat type '{label}' repeated {length} consecutive scenes ({start}–{end})"
        logger.warning("Visual beat monotony: %s", msg)
        issues.append(msg)

    return issues


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
) -> ScriptContent:
    """Generate a segmented video script via Claude.

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

    resolved_model = model or os.environ.get("SCRIPT_MODEL", DEFAULT_CLAUDE_MODEL)

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

    # Always apply title card instructions (title cards are always active)
    system_prompt += TITLE_CARD_PROMPT_INSTRUCTIONS

    # --- Generation + review loop (up to MAX_ATTEMPTS) ---
    content: ScriptContent | None = None
    user_message = base_user_message

    for attempt in range(1, MAX_ATTEMPTS + 1):
        if segmented:
            logger.info("Using SEGMENTED generation for topic %r, description=%r (model=%s, attempt %d/%d)", topic, description, resolved_model, attempt, MAX_ATTEMPTS)
            content = _generate_segmented(
                system_prompt=system_prompt,
                user_message=user_message,
                topic=topic,
                description=description,
                brand_context=brand_context,
                model=resolved_model,
                progress_callback=progress_callback,
            )
        else:
            logger.info("Generating script for topic %r, description=%r using model=%s (segments=%d, attempt %d/%d)", topic, description, resolved_model, SEGMENT_COUNT, attempt, MAX_ATTEMPTS)
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
        content = enforce_title_cards_and_min_scenes(content)

        # --- Quality review ---
        if attempt == MAX_ATTEMPTS:
            # Final attempt — accept regardless of review
            logger.info("Final attempt (%d/%d) — accepting script without review gate", attempt, MAX_ATTEMPTS)
            break

        if progress_callback:
            progress_callback(0, 0, "Reviewing script quality...")

        review = review_script(content)
        pass_count = review.pass_count()

        # Check visual monotony independently of Gemini review
        monotony_issues = _check_visual_monotony(content)

        if review.overall_pass and not monotony_issues:
            logger.info("Script quality review passed (%d/5 skillsets, no monotony)", pass_count)
            if progress_callback:
                progress_callback(0, 0, "Script quality review passed")
            break

        # Build combined critique from review failures + monotony issues
        critique_parts: list[str] = []
        if not review.overall_pass:
            critique_parts.append(review.critique_summary())
        if monotony_issues:
            monotony_critique = (
                "- Visual Variety: The script violates the beat distribution rules. "
                "After every 2 consecutive static scenes, the next scene MUST use a "
                "different beat type. Fix these runs: " + "; ".join(monotony_issues)
            )
            critique_parts.append(monotony_critique)

        critique = "\n".join(critique_parts)

        logger.info(
            "Script quality review: %d/5 skillsets passed, %d monotony issues (attempt %d/%d). Regenerating...",
            pass_count, len(monotony_issues), attempt, MAX_ATTEMPTS,
        )
        if progress_callback:
            progress_callback(
                0, 0,
                f"Review: {pass_count}/5 skillsets passed, {len(monotony_issues)} monotony issues. "
                f"Regenerating (attempt {attempt + 1}/{MAX_ATTEMPTS})...",
            )

        user_message = (
            SCRIPT_RETRY_CRITIQUE.build(critique)
            + base_user_message
        )

    assert content is not None

    logger.info("Script generated for topic %r: %s segments, %s total scenes",
                topic, len(content.segments), sum(len(s.scenes) for s in content.segments))
    _check_visual_monotony(content)
    return content


# ---------------------------------------------------------------------------
# Segmented generation (two-phase)
# ---------------------------------------------------------------------------

_OUTLINE_INSTRUCTIONS = SCRIPT_OUTLINE_INSTRUCTIONS.template

_SEGMENT_SCENES_INSTRUCTIONS = SCRIPT_SEGMENT_SCENES_INSTRUCTIONS.template


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
    trailing_context: str = "",
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
    trailing_context = ""

    for i, seg_outline in enumerate(outline["segments"]):
        seg_name = seg_outline.get("name", f"Segment {i + 1}")
        if progress_callback:
            progress_callback(i + 1, len(outline["segments"]), seg_name)
        try:
            scenes = _generate_segment_scenes(system_prompt, outline, i, model, trailing_context)
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
