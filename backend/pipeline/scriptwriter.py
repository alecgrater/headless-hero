"""Script generation pipeline — uses the routed LLM provider to write segmented video scripts."""

import json
import logging
import re
import time
from collections.abc import Callable

from config import DEFAULT_ACCENT_COLOR, SEGMENT_COUNT, parse_json_array_response, strip_markdown_fences
from integrations.llm_client import chat
from models.script import FrameDirective, LevelMeta, MainCharacter, Scene, ScriptContent, Segment
from prompts import SCRIPT_OUTLINE_INSTRUCTIONS, SCRIPT_SEGMENT_SCENES_INSTRUCTIONS, SCRIPT_SYSTEM

logger = logging.getLogger(__name__)

# Base system prompt — title card instructions are injected separately.
BASE_SYSTEM_PROMPT = SCRIPT_SYSTEM.template


def build_main_character_instructions() -> str:
    """Instructions appended to the system prompt when Eli is disabled.

    Tells Claude to invent one project-wide main character and to set
    contains_person=true on scenes where that character would naturally appear.
    """
    return (
        "\n\n## Main Character (Eli is disabled for this project)\n"
        "Invent ONE recurring main character that fits this video's topic. "
        "Output a top-level `main_character` object with three fields:\n"
        "  - name: the character's name\n"
        "  - appearance: detailed visual description (face, hair, build, "
        "    clothing, distinguishing features) — written so an image "
        "    generator could draw them consistently\n"
        "  - vibe: 1-2 sentences on personality / energy\n\n"
        "For each scene, set `contains_person: true` ONLY when this main "
        "character should appear in that scene's visual. Set "
        "`contains_person: false` for landscapes, abstract concepts, "
        "object close-ups, or any shot where forcing a person in would "
        "feel awkward. Aim for a balance — not every scene needs a "
        "person.\n"
    )


def build_outline_main_character_addendum() -> str:
    """Addendum appended to outline instructions when Eli is disabled.

    The format-level outline schemas explicitly enumerate the JSON fields
    they expect, which causes Claude to omit `main_character` even though
    the system prompt asks for it. This addendum re-asserts the schema
    requirement at the outline phase so segmented generation propagates
    the main character through.
    """
    return (
        "\n\nADDITIONAL OUTLINE FIELD (Eli is disabled for this project):\n"
        "The outline JSON MUST also include a top-level `main_character` "
        "object with this exact shape:\n"
        '  "main_character": {\n'
        '    "name": "Character Name",\n'
        '    "appearance": "Detailed visual description (face, hair, build, clothing, distinguishing features) so an image generator could draw them consistently.",\n'
        '    "vibe": "1-2 sentences on personality / energy."\n'
        "  }\n"
        "This is REQUIRED — do not omit it. Add it alongside the existing "
        "outline fields.\n"
    )


def build_script_outline_instructions(eli_enabled: bool, base_template: str = SCRIPT_OUTLINE_INSTRUCTIONS.template) -> str:
    """Build outline instructions, conditionally including main_character schema.

    When eli_enabled is False, the outline must include a `main_character`
    block so segmented generation can propagate it into ScriptContent.
    """
    if eli_enabled:
        return base_template
    return base_template + build_outline_main_character_addendum()


def _normalize_opening_text(value: str) -> str:
    """Normalize opening narration for conservative selected-opening matching."""
    return re.sub(r"[^a-z0-9]+", " ", value.lower()).strip()


def _selected_opening_scene_count(content: ScriptContent, cold_open_text: str | None) -> int:
    """Count leading non-title scenes that came from a selected long-form opening.

    Life-as-a openings are intentionally substantive role-entry scenes, so the
    generic hook detector can mistake them for segment content. This deterministic
    match is used only when the selected opening text is present in the first
    segment narration.
    """
    if not cold_open_text or not content.segments:
        return 0

    selected = _normalize_opening_text(cold_open_text)
    if not selected:
        return 0

    scenes = [scene for scene in content.segments[0].scenes if not scene.is_title_card]
    if len(scenes) <= 1:
        return 0

    count = 0
    for scene in scenes[:5]:
        narration = _normalize_opening_text(scene.narration or "")
        if not narration:
            break
        if narration not in selected:
            break
        count += 1

    return min(count, max(0, len(scenes) - 1))


ALL_BEAT_TYPES = ["static", "continuous", "multi_frame", "aha_subtitle"]
LEGACY_BEAT_ALIASES = {
    "full_frame": "static",
    "quick_cuts": "multi_frame",
    "montage": "multi_frame",
}

_SHOT_LABEL_RE = re.compile(r"^\[([A-Z\-]+)\]")


def _directive_prompt(scene: Scene, suffix: str = "") -> str:
    prompt = scene.visual_prompt.strip() or scene.narration.strip()
    return f"{prompt} {suffix}".strip()


def _canonical_visual_beat(beat: str) -> str:
    return LEGACY_BEAT_ALIASES.get(beat, beat)


def _directive_mode(scene: Scene, beat: str) -> str:
    if scene.visual_mode in {"multi_frame", "continuous", "aha_subtitle"}:
        return scene.visual_mode
    if _canonical_visual_beat(beat) == "multi_frame":
        return "multi_frame"
    if beat == "continuous":
        return "continuous"
    if beat == "aha_subtitle":
        return "aha_subtitle"
    return "full_frame"


def _synthesize_frame_directives(scene: Scene, beat: str) -> None:
    """Ensure post-processed non-static beats actually generate multiple frames."""
    if scene.is_title_card:
        return
    if scene.frame_directives and len(scene.frame_directives) > 1:
        return

    mode = _directive_mode(scene, beat)
    contains_person = bool(scene.contains_person)
    if mode == "continuous":
        scene.frame_directives = [
            {
                "prompt": _directive_prompt(scene),
                "source": "ai_generated",
                "transition": "cut",
                "reference_previous": False,
                "search_query": "",
                "contains_person": contains_person,
            },
            {
                "prompt": "A subtle time-passage progression in the same composition.",
                "source": "ai_generated",
                "transition": "crossfade",
                "reference_previous": True,
                "search_query": "",
                "contains_person": contains_person,
            },
            {
                "prompt": "A later quiet progression of the same moment, preserving the composition.",
                "source": "ai_generated",
                "transition": "crossfade",
                "reference_previous": True,
                "search_query": "",
                "contains_person": contains_person,
            },
        ]
    elif mode == "multi_frame":
        scene.frame_directives = [
            {
                "prompt": _directive_prompt(scene),
                "source": "ai_generated",
                "transition": "cut",
                "reference_previous": False,
                "search_query": "",
                "contains_person": contains_person,
            },
            {
                "prompt": _directive_prompt(scene, "A different angle from the same lived situation."),
                "source": "ai_generated",
                "transition": "cut",
                "reference_previous": False,
                "search_query": "",
                "contains_person": contains_person,
            },
            {
                "prompt": _directive_prompt(scene, "A close detail that compresses time and consequence."),
                "source": "ai_generated",
                "transition": "cut",
                "reference_previous": False,
                "search_query": "",
                "contains_person": contains_person,
            },
            {
                "prompt": _directive_prompt(scene, "A final contrasting shot that completes the beat."),
                "source": "ai_generated",
                "transition": "cut",
                "reference_previous": False,
                "search_query": "",
                "contains_person": contains_person,
            },
        ]
    elif mode == "aha_subtitle":
        object.__setattr__(
            scene,
            "frame_directives",
            [
                FrameDirective(
                    prompt=scene.narration.strip(),
                    source="subtitle",
                    transition="cut",
                    reference_previous=False,
                    search_query="",
                    contains_person=False,
                )
            ],
        )


def _ensure_visual_beat_directives(content: ScriptContent) -> None:
    for scene in content.all_scenes():
        _synthesize_frame_directives(scene, scene.visual_beat or "static")
    if content.format_id == "life-as-a":
        from pipeline.formats.life_as_a import enforce_life_as_a_visual_complexity

        enforce_life_as_a_visual_complexity(content)


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


def _fix_visual_monotony(content: "ScriptContent", rules: "VisualBeatRules | None" = None) -> int:
    """Detect and fix monotonous runs of beat types in-place.

    When `rules` is provided, only beats in `rules.allowed_beats` are considered
    candidates for reassignment, and the run threshold is `rules.monotony_threshold`.
    When None, falls back to legacy listicle behavior (threshold=3, all ALL_BEAT_TYPES allowed).
    """
    from pipeline.formats.base import VisualBeatRules  # noqa: F401  (referenced in type hint)

    all_scenes = content.all_scenes()
    if not all_scenes:
        return 0

    if rules is None:
        allowed_alts = ALL_BEAT_TYPES
        threshold = 3
    else:
        allowed_alts = sorted({_canonical_visual_beat(beat) for beat in rules.allowed_beats})
        threshold = rules.monotony_threshold

    if threshold > len(all_scenes):
        return 0  # rule effectively disables run-breaking

    fixes = 0
    beat_types: list[str] = []
    for scene in all_scenes:
        if scene.is_title_card:
            beat_types.append("TITLE_CARD")
        else:
            beat_types.append(_canonical_visual_beat(scene.visual_beat or "static"))

    for label, length, start_1, _end_1 in _find_runs(beat_types, {"TITLE_CARD"}, threshold=threshold):
        start = start_1 - 1
        for i in range(start + 2, start + length, 3):
            scene = all_scenes[i]
            if scene.is_title_card:
                continue
            alternatives = [b for b in allowed_alts if b != label]
            if not alternatives:
                continue
            new_beat = alternatives[i % len(alternatives)]
            logger.info("Monotony fix: scene %d beat '%s' → '%s' (run=%d)", i + 1, label, new_beat, length)
            scene.visual_beat = new_beat
            _synthesize_frame_directives(scene, new_beat)
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
    script_id: str | None = None,
    format_id: str = "youtube-listicle",
    eli_enabled: bool = True,
) -> ScriptContent:
    """Generate a video script for the given format. Dispatches via the format registry.

    Args:
        topic: The video title/topic.
        description: Optional angle or description for the video.
        brand_context: Brand name + art style for tone/visual context.
        animated_scene_count: Number of scenes to mark as animated A/B flip.
        brand: Brand profile dict for modifier hooks.
        model: Override SCRIPT_MODEL setting for this request.
        segmented: Use two-phase segmented generation (one API call per segment).
        format_id: Video format ID (registered in pipeline.formats).

    Returns:
        A validated ScriptContent object.
    """
    from pipeline.formats import get_format
    from pipeline.modifiers.title_cards import TITLE_CARD_PROMPT_INSTRUCTIONS

    fmt = get_format(format_id)
    resolved_model = model

    # --- Build the user message ---
    user_parts = [f'Write a full segmented video script for: "{topic}"']
    if description:
        user_parts.append(f"Angle/description: {description}")

    if isinstance(fmt.level_count, int):
        user_parts.append(f"Use exactly {fmt.level_count} {fmt.level_label}s.")
    else:
        lo, hi = fmt.level_count
        user_parts.append(
            f"Use between {lo} and {hi} {fmt.level_label}s — pick the count that best fits the topic."
        )

    if brand_context:
        user_parts.append(f"Brand context (use for visual style and tone): {brand_context}")

    user_parts.append(
        "For each scene, set visual_mode, compatibility visual_beat, and matching frame_directives "
        "following the Visual Mode System guidelines. "
        "Every visual_prompt must begin with a [SHOT_TYPE] label."
    )

    if cold_open_text and fmt.supports_cold_open:
        user_parts.append(
            "MANDATORY COLD OPEN — use this EXACT opening for the video.\n"
            "The intro_hook and first 2-3 content scenes MUST use this text verbatim "
            "or with minimal polish:\n\n"
            f"{cold_open_text}"
        )

    base_user_message = "\n".join(user_parts)

    # --- Build the system prompt ---
    system_prompt = fmt.script_system_prompt.template
    # Title-card instructions: only inject for composite-grid (life-as-a uses cinematic chapter cards
    # whose instructions are baked into the format's script_system_prompt).
    if fmt.title_card_strategy.kind == "composite-grid":
        system_prompt += TITLE_CARD_PROMPT_INSTRUCTIONS

    # When Eli is disabled, instruct Claude to invent a project-wide main character
    # and to set per-scene contains_person flags accordingly. This applies to both
    # single-pass and segmented generation paths (the system prompt is reused for
    # both the outline and per-segment scene calls).
    if not eli_enabled:
        system_prompt = system_prompt + build_main_character_instructions()

    # --- Generation ---
    use_segmented = segmented and fmt.supports_segmented_generation
    if use_segmented:
        if fmt.outline_prompt is None or fmt.segment_scenes_prompt is None:
            raise RuntimeError(
                f"Format {fmt.id!r} declared supports_segmented_generation=True "
                f"but missing outline_prompt or segment_scenes_prompt"
            )
        logger.info(
            "Format %s — SEGMENTED generation for topic %r, description=%r (model=%s)",
            fmt.id, topic, description, resolved_model or "configured",
        )
        content = _generate_segmented(
            system_prompt=system_prompt,
            user_message=base_user_message,
            topic=topic,
            description=description,
            brand_context=brand_context,
            model=resolved_model,
            progress_callback=progress_callback,
            script_id=script_id,
            outline_instructions=fmt.outline_prompt.template,
            segment_scenes_instructions=fmt.segment_scenes_prompt.template,
            eli_enabled=eli_enabled,
            cold_open_text=cold_open_text if fmt.supports_cold_open else None,
        )
    else:
        logger.info(
            "Format %s — single-pass generation for topic %r, description=%r (model=%s)",
            fmt.id, topic, description, resolved_model or "configured",
        )
        raw = chat(
            system_prompt,
            base_user_message,
            model=resolved_model,
            max_tokens=16384,
            timeout=900.0,
            json_mode=True,
            task="script",
            script_id=script_id,
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

    content.format_id = fmt.id
    content = fmt.enforce_post_processing(content, eli_enabled=eli_enabled)
    _fix_visual_monotony(content, rules=fmt.visual_beat_rules)
    _ensure_visual_beat_directives(content)
    if cold_open_text and fmt.supports_cold_open and not fmt.supports_hook_scoring:
        selected_opening_count = _selected_opening_scene_count(content, cold_open_text)
        if selected_opening_count > 0:
            content.hook_scene_count = selected_opening_count
            content.short_form_seo_metadata = None
            logger.info(
                "Selected long-form opening matched %d leading scene(s) for format %s",
                selected_opening_count,
                fmt.id,
            )

    logger.info(
        "Script generated for topic %r [format=%s]: %s segments, %s total scenes",
        topic, fmt.id, len(content.segments), sum(len(s.scenes) for s in content.segments),
    )
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
    script_id: str | None,
    outline_instructions: str = _OUTLINE_INSTRUCTIONS,
) -> dict:
    """Phase 1: Generate script outline (no scenes) via a single small LLM call."""
    t0 = time.monotonic()
    logger.info("SEGMENTED: Phase 1 — generating outline (model=%s)", model)

    outline_msg = user_message + "\n\n" + outline_instructions
    raw = chat(
        system_prompt,
        outline_msg,
        model=model,
        max_tokens=4096,
        timeout=180.0,
        json_mode=True,
        task="script",
        script_id=script_id,
        cache=True,
    )
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
    script_id: str | None = None,
    segment_scenes_instructions: str = _SEGMENT_SCENES_INSTRUCTIONS,
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
        f"{segment_scenes_instructions}"
    )

    raw = chat(
        system_prompt,
        user_msg,
        model=model,
        max_tokens=32768,
        timeout=300.0,
        json_mode=True,
        task="script",
        script_id=script_id,
        cache=True,
    )
    text = strip_markdown_fences(raw)

    try:
        scenes_data = parse_json_array_response(text, key="scenes")
    except (json.JSONDecodeError, ValueError) as e:
        # Best-effort shape sniff so the dev dashboard log shows the actual JSON
        # structure the model returned (helps diagnose new dict-wrapping variants).
        shape_hint = "unparseable"
        try:
            preview = json.loads(strip_markdown_fences(text))
            if isinstance(preview, dict):
                shape_hint = f"dict keys={list(preview.keys())[:20]}"
            else:
                shape_hint = f"{type(preview).__name__}"
        except Exception:
            pass
        logger.error(
            "SEGMENTED: Segment %d/%d (%r) response failed to parse — %d chars, shape=%s\n"
            "FULL RESPONSE:\n%s",
            segment_index + 1, total, seg_name, len(text), shape_hint, text,
        )
        raise RuntimeError(
            f"SEGMENTED: Segment {segment_index + 1}/{total} (\"{seg_name}\") "
            f"response could not be parsed (likely truncated or malformed): {e}"
        ) from e

    # Some models return segment-shaped wrappers ({"name": "...", "scenes": [...]})
    # instead of a flat scene array, despite explicit prompting. Flatten by extracting
    # the inner `scenes` lists when items lack scene-required fields.
    if scenes_data and all(
        isinstance(s, dict)
        and isinstance(s.get("scenes"), list)
        and "narration" not in s
        and "visual_prompt" not in s
        for s in scenes_data
    ):
        flat: list = []
        for seg in scenes_data:
            flat.extend(seg["scenes"])
        logger.warning(
            "SEGMENTED: Segment %d/%d (%r) returned segment-shaped wrapper — flattened %d nested scenes from %d wrapper(s)",
            segment_index + 1, total, seg_name, len(flat), len(scenes_data),
        )
        scenes_data = flat

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
    script_id: str | None = None,
    outline_instructions: str = _OUTLINE_INSTRUCTIONS,
    segment_scenes_instructions: str = _SEGMENT_SCENES_INSTRUCTIONS,
    eli_enabled: bool = True,
    cold_open_text: str | None = None,
) -> ScriptContent:
    """Orchestrate two-phase segmented script generation."""
    total_t0 = time.monotonic()

    # When Eli is disabled, the format-level outline schema explicitly enumerates
    # the JSON fields it expects, which causes Claude to omit `main_character`
    # even though the system prompt asks for it. Re-assert the schema requirement
    # at the outline phase so segmented generation propagates the main character.
    if not eli_enabled:
        outline_instructions = outline_instructions + build_outline_main_character_addendum()

    # Phase 1: outline
    outline = _generate_outline(
        system_prompt, user_message, model, script_id,
        outline_instructions=outline_instructions,
    )

    # Phase 2: per-segment scene generation (sequential for coherence)
    segments: list[Segment] = []
    global_scene_id = 1
    trailing_context = ""

    for i, seg_outline in enumerate(outline["segments"]):
        seg_name = seg_outline.get("name", f"Segment {i + 1}")
        if progress_callback:
            progress_callback(i + 1, len(outline["segments"]), seg_name)
        try:
            first_level_opening = ""
            if i == 0 and cold_open_text:
                first_level_opening = (
                    "MANDATORY LONG-FORM OPENING — begin this first segment's non-title "
                    "content scenes with this exact selected opening. These opening scenes "
                    "are for the long-form video and may be skipped from short #1:\n\n"
                    f"{cold_open_text}\n\n"
                )

            scenes = _generate_segment_scenes(
                system_prompt,
                outline,
                i,
                model,
                first_level_opening + trailing_context,
                script_id=script_id,
                segment_scenes_instructions=segment_scenes_instructions,
            )
        except Exception as e:
            seg_name = seg_outline.get("name", f"Segment {i + 1}")
            logger.exception(
                "Segmented script generation failed on segment %d/%d (%r)",
                i + 1, len(outline["segments"]), seg_name,
            )
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
    raw_levels = outline.get("levels") or []
    levels = [LevelMeta.model_validate(lv) for lv in raw_levels] if raw_levels else None

    raw_main_character = outline.get("main_character")
    main_character = (
        MainCharacter.model_validate(raw_main_character)
        if raw_main_character and isinstance(raw_main_character, dict)
        else None
    )

    content = ScriptContent(
        title=outline.get("title", topic),
        segments=segments,
        intro_hook=outline.get("intro_hook", ""),
        outro_cta=outline.get("outro_cta", ""),
        card_title=outline.get("card_title", ""),
        card_title_highlight_word=outline.get("card_title_highlight_word", ""),
        card_subtitle=outline.get("card_subtitle", ""),
        cinematic_thumbnail_prompt=outline.get("cinematic_thumbnail_prompt"),
        levels=levels,
        main_character=main_character,
    )

    total_elapsed = time.monotonic() - total_t0
    total_scenes = sum(len(s.scenes) for s in segments)
    logger.info(
        "SEGMENTED: Assembly complete — %d segments, %d total scenes, total time %.1fs",
        len(segments), total_scenes, total_elapsed,
    )

    return content
