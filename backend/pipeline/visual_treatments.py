"""Static-canvas animation type analysis and assignment helpers."""

from __future__ import annotations

import logging
import re

from pydantic import BaseModel, Field, model_validator

from models.script import ScriptContent, Scene, VISUAL_MODES, VisualLayer, VisualMode
from pipeline.fallback_observability import record_fallback
from pipeline.blink_actions import (
    build_blink_state_prompt,
    has_human_blink_subject,
    normalize_blink_action,
    normalize_production_blink_action,
)
from pipeline.renderer_context import infer_renderer_context, normalize_renderer_context
from pipeline.render_jobs import UserFacingJobError

logger = logging.getLogger(__name__)

LAYERED_LEGACY_TREATMENTS = {"full_frame", "popup_sequence", "blink", "comparison_board"}
LIST_MARKERS = {
    "first",
    "second",
    "third",
    "fourth",
    "1",
    "2",
    "3",
    "4",
}
MICRO_ACTION_SUBJECT_MARKERS = {
    "arm",
    "arms",
    "body",
    "character",
    "eye",
    "eyes",
    "face",
    "finger",
    "fingers",
    "hand",
    "hands",
    "head",
    "person",
    "shoulder",
    "shoulders",
}
MICRO_ACTION_MOTION_MARKERS = {
    "close",
    "closes",
    "closing",
    "gesture",
    "gestures",
    "gesturing",
    "grip",
    "grips",
    "handle",
    "handles",
    "handling",
    "lean",
    "leans",
    "leaning",
    "nod",
    "nods",
    "nodding",
    "open",
    "opens",
    "opening",
    "pace",
    "paces",
    "pacing",
    "point",
    "points",
    "pointing",
    "sort",
    "sorts",
    "sorting",
    "stir",
    "stirs",
    "stirring",
    "talk",
    "talking",
    "tap",
    "taps",
    "tapping",
    "type",
    "types",
    "typing",
}
MICRO_ACTION_PHRASES = (
    "back and forth",
    "open and close",
    "opens and closes",
    "while he talks",
    "while she talks",
    "while they talk",
    "while talking",
)
NATURAL_LIST_CONTRAST_CONNECTORS = {
    "but",
    "however",
    "instead",
    "versus",
    "vs",
    "whereas",
}
COMPARISON_PAIR_PHRASES = (
    ("before", "after"),
    ("then", "now"),
    ("myth", "reality"),
    ("rich", "poor"),
    ("success", "failure"),
    ("human", "neanderthal"),
    ("prisoner", "guard"),
    ("guard", "prisoner"),
)
PROGRESSION_MARKERS = {
    "builds",
    "crawl",
    "crawls",
    "expand",
    "expands",
    "grow",
    "grows",
    "pour",
    "pours",
    "spread",
    "spreads",
    "transform",
    "transforms",
}
REPETITION_STOPWORDS = {
    "a",
    "an",
    "and",
    "are",
    "as",
    "at",
    "but",
    "for",
    "in",
    "is",
    "it",
    "of",
    "on",
    "or",
    "the",
    "to",
}
VARIETY_PRIORITY_MODES = {"full_frame", "multi_frame", "continuous", "blink"}
CLEAR_IMPROVEMENT_MODES = {
    "comparison_board",
    "stat_card",
    "popup_sequence",
    "video",
    "captions",
}
NON_REPEATABLE_MODES = (VARIETY_PRIORITY_MODES | CLEAR_IMPROVEMENT_MODES) - {"full_frame"}
CAPTION_PUNCH_MARKERS = {
    "cost",
    "truth",
    "real",
    "never",
    "nothing",
    "everything",
    "gone",
    "point",
    "secret",
    "mistake",
    "trap",
}
STAT_VALUE_RE = re.compile(
    r"(?<!\w)(?:[$#]?\d+(?:[,.]\d+)*(?:\.\d+)?%?|(?:one|two|three|four|five|six|seven|eight|nine|ten)\s+in\s+\d+)(?!\w)",
    re.IGNORECASE,
)


class VisualTreatmentAssignment(BaseModel):
    scene_id: str
    visual_mode: str = "full_frame"
    reasoning: str = ""
    visual_layers: list[VisualLayer] = Field(default_factory=list)
    caption_text: str = ""
    caption_emphasis: str = ""
    stat_value: str = ""
    stat_label: str = ""

    @model_validator(mode="before")
    @classmethod
    def normalize_legacy_visual_treatment(_cls, data: object) -> object:
        if not isinstance(data, dict):
            return data
        normalized = dict(data)
        if not normalized.get("visual_mode") and isinstance(normalized.get("visual_treatment"), str):
            normalized["visual_mode"] = normalized["visual_treatment"]
        return normalized

    @property
    def visual_treatment(self) -> str:
        return (
            self.visual_mode
            if self.visual_mode in {"popup_sequence", "blink", "comparison_board", "stat_card"}
            else "full_frame"
        )


def missing_visual_treatment_voiceover_scene_ids(content: ScriptContent) -> tuple[list[str], list[str]]:
    """Return non-title scene IDs missing audio duration and word-level timing."""

    missing_audio: list[str] = []
    missing_words: list[str] = []
    for scene in content.all_scenes():
        if scene.is_title_card:
            continue
        if scene.audio_duration_seconds <= 0:
            missing_audio.append(scene.id)
        if not scene.word_timestamps:
            missing_words.append(scene.id)
    return missing_audio, missing_words


def visual_treatment_voiceover_required_message(audio_count: int, word_count: int) -> str:
    return (
        "Generate voiceover first so animation types can sync to words. "
        f"{audio_count} scene(s) are missing audio duration and "
        f"{word_count} scene(s) are missing word timing."
    )


def require_visual_treatment_voiceover(content: ScriptContent) -> None:
    missing_audio, missing_words = missing_visual_treatment_voiceover_scene_ids(content)
    if not missing_audio and not missing_words:
        return

    scene_ids = sorted(set(missing_audio) | set(missing_words))
    logger.info(
        "[ANIMATION_TYPE] blocked; missing_audio=%d missing_word_timing=%d scene_ids=%s",
        len(missing_audio),
        len(missing_words),
        scene_ids,
    )
    raise UserFacingJobError(
        visual_treatment_voiceover_required_message(len(missing_audio), len(missing_words))
    )


def analyze_visual_treatments(
    content: ScriptContent,
    *,
    script_id: str,
) -> list[VisualTreatmentAssignment]:
    require_visual_treatment_voiceover(content)
    scenes = content.all_scenes()
    logger.info(
        "[ANIMATION_TYPE] analysis requested; script=%s scenes=%d format=%s",
        script_id,
        len(scenes),
        content.format_id,
    )

    assignments: list[VisualTreatmentAssignment] = []
    for scene in scenes:
        assignment = _analyze_scene(scene, script_id=script_id)
        logger.info(
            "[ANIMATION_TYPE] scene=%s animation_type=%s layers=%d reason=%s",
            scene.id,
            assignment.visual_mode,
            len(assignment.visual_layers),
            assignment.reasoning,
        )
        assignments.append(assignment)
    return _space_non_repeatable_modes(assignments, scenes)


def analyze_visual_treatment_scene(
    scene: Scene,
    *,
    script_id: str,
) -> VisualTreatmentAssignment:
    """Plan renderer-owned fields for one scene without whole-script spacing enforcement."""
    return _analyze_scene(scene, script_id=script_id)


def apply_visual_treatment_assignments(
    content: ScriptContent,
    assignments: list[VisualTreatmentAssignment],
) -> None:
    scenes_by_id = {scene.id: scene for scene in content.all_scenes()}
    for assignment in assignments:
        scene = scenes_by_id.get(assignment.scene_id)
        if scene is None:
            continue
        mode = _normalize_visual_mode(assignment.visual_mode)
        if mode == "video" and scene.visual_mode != "video" and not scene.video_url:
            mode = "full_frame"
        scene.set_visual_mode(mode)
        if mode == "captions":
            caption_text, caption_emphasis = _caption_assignment_fields(scene, assignment)
            scene.caption_text = caption_text
            scene.caption_emphasis = caption_emphasis
        if mode == "stat_card":
            scene.stat_value = assignment.stat_value
            scene.stat_label = assignment.stat_label
        scene.visual_layers = (
            list(assignment.visual_layers)
            if mode in {"popup_sequence", "blink", "comparison_board", "stat_card"}
            else []
        )
    _enforce_content_non_repeatable_spacing(content)


def _stat_fields_for_scene(scene: Scene) -> tuple[str, str] | None:
    text = scene.narration.strip()
    matches = [match.group(0).strip() for match in STAT_VALUE_RE.finditer(text)]
    if len(matches) != 1:
        return None
    stat_value = matches[0]
    label = re.sub(re.escape(stat_value), "", text, count=1, flags=re.IGNORECASE)
    label = re.sub(r"^\s*(?:by|in|after|before|around|about|nearly|almost|roughly)\b\s*", "", label, flags=re.IGNORECASE)
    label = re.sub(r"\s+", " ", label.strip(" .,:;—–-"))
    words = label.split()
    if len(words) > 10:
        label = " ".join(words[-10:])
    return stat_value, label


def _caption_fields_for_scene(scene: Scene) -> tuple[str, str] | None:
    text = _caption_text_from_narration(scene.narration)
    if not text:
        return None
    words = [_normalize_word(word) for word in text.split()]
    content_words = [word for word in words if word and word not in REPETITION_STOPWORDS]
    if not 3 <= len(content_words) <= 10:
        return None
    emphasis = next((word for word in reversed(content_words) if word in CAPTION_PUNCH_MARKERS), "")
    if not emphasis:
        return None
    return text, emphasis


def _caption_text_from_narration(narration: str) -> str:
    return re.sub(r"\s+", " ", narration.strip(" ."))


def _caption_text_matches_narration(caption_text: str, narration_text: str) -> bool:
    caption = re.sub(r"\s+", " ", caption_text.strip(" .")).casefold()
    narration = re.sub(r"\s+", " ", narration_text.strip(" .")).casefold()
    return bool(caption) and caption in narration


def _fallback_caption_emphasis(caption_text: str) -> str:
    content_words = [
        _normalize_word(word)
        for word in caption_text.split()
        if _normalize_word(word) and _normalize_word(word) not in REPETITION_STOPWORDS
    ]
    marker = next((word for word in reversed(content_words) if word in CAPTION_PUNCH_MARKERS), "")
    return marker or (content_words[-1] if content_words else "")


def _caption_assignment_fields(scene: Scene, assignment: VisualTreatmentAssignment) -> tuple[str, str]:
    caption_text = assignment.caption_text.strip()
    caption_emphasis = assignment.caption_emphasis.strip()
    narration_text = _caption_text_from_narration(scene.narration)
    if caption_text and not _caption_text_matches_narration(caption_text, narration_text):
        caption_text = ""
    if caption_text and caption_emphasis and _caption_text_matches_narration(caption_emphasis, caption_text):
        return caption_text, caption_emphasis

    inferred = _caption_fields_for_scene(scene)
    if inferred is not None:
        inferred_text, inferred_emphasis = inferred
        resolved_text = caption_text or inferred_text
        resolved_emphasis = (
            caption_emphasis
            if caption_emphasis and _caption_text_matches_narration(caption_emphasis, resolved_text)
            else inferred_emphasis
        )
        return resolved_text, resolved_emphasis

    fallback_text = narration_text
    resolved_text = caption_text or fallback_text
    fallback_emphasis = _fallback_caption_emphasis(resolved_text)
    resolved_emphasis = (
        caption_emphasis
        if caption_emphasis and _caption_text_matches_narration(caption_emphasis, resolved_text)
        else fallback_emphasis
    )
    return resolved_text, resolved_emphasis


def _analyze_scene(scene: Scene, *, script_id: str | None = None) -> VisualTreatmentAssignment:
    if scene.is_title_card:
        return _full_frame_assignment(scene.id, "Title-card scenes keep their existing full-frame animation type.")
    if scene.visual_mode == "captions":
        return VisualTreatmentAssignment(
            scene_id=scene.id,
            visual_mode="captions",
            reasoning="Scene is explicitly marked for captions rendering.",
            visual_layers=[],
        )
    if scene.visual_mode == "stat_card":
        return VisualTreatmentAssignment(
            scene_id=scene.id,
            visual_mode="stat_card",
            reasoning="Scene is explicitly marked for stat-card rendering; preserved.",
            visual_layers=list(scene.visual_layers),
            stat_value=scene.stat_value,
            stat_label=scene.stat_label,
        )
    if _is_video_or_photo_backed(scene):
        return VisualTreatmentAssignment(
            scene_id=scene.id,
            visual_mode="video",
            reasoning="Video scenes keep their generated clip as the scene mode.",
            visual_layers=[],
        )

    if scene.visual_mode == "popup_sequence":
        layers = list(scene.visual_layers) or _popup_layers_for_scene(scene)
        return VisualTreatmentAssignment(
            scene_id=scene.id,
            visual_mode="popup_sequence",
            reasoning="Scene is explicitly marked for popup-sequence rendering.",
            visual_layers=layers,
        )
    if scene.visual_mode == "blink":
        action = normalize_production_blink_action(scene.blink_action)
        if not action or not has_human_blink_subject(scene.narration, scene.visual_prompt):
            previous_action = scene.blink_action
            scene.set_visual_mode("full_frame")
            scene.visual_layers = []
            scene.blink_action = ""
            record_fallback(
                category="visual_mode",
                event="blink_invalid_micro_action_downgraded",
                reason="Blink scene missing valid human micro-action during analyzer pass",
                severity="warn",
                script_id=script_id,
                scene_id=scene.id,
                from_value="blink",
                to_value="full_frame",
                metadata={"blink_action": previous_action} if previous_action else None,
            )
            return _full_frame_assignment(
                scene.id,
                "Invalid blink request; missing valid human micro-action.",
            )
        scene.blink_action = action
        return VisualTreatmentAssignment(
            scene_id=scene.id,
            visual_mode="blink",
            reasoning=f"Explicit human micro-action blink: {action}.",
            visual_layers=_blink_layers(scene),
        )
    if scene.visual_mode == "comparison_board":
        return VisualTreatmentAssignment(
            scene_id=scene.id,
            visual_mode="comparison_board",
            reasoning="Scene is explicitly marked for comparison-board rendering.",
            visual_layers=list(scene.visual_layers) or _comparison_layers_for_scene(scene),
        )
    if scene.visual_mode == "multi_frame" or scene.visual_beat in {"quick_cuts", "montage", "multi_frame"}:
        return VisualTreatmentAssignment(
            scene_id=scene.id,
            visual_mode="multi_frame",
            reasoning="Scene is explicitly marked for independent multi-frame rendering.",
            visual_layers=[],
        )
    if scene.visual_mode == "continuous" or scene.visual_beat == "continuous":
        return VisualTreatmentAssignment(
            scene_id=scene.id,
            visual_mode="continuous",
            reasoning="Scene is explicitly marked for same-scene progression.",
            visual_layers=[],
        )

    layers = _popup_layers_for_scene(scene, marker_only=True)
    if layers:
        return VisualTreatmentAssignment(
            scene_id=scene.id,
            visual_mode="popup_sequence",
            reasoning=f"Detected {len(layers)} list markers in narration.",
            visual_layers=layers,
        )

    if _looks_like_blink_micro_action(scene):
        action = _infer_blink_action(scene)
        if action and has_human_blink_subject(scene.narration, scene.visual_prompt):
            scene.set_visual_mode("blink")
            scene.blink_action = action
            return VisualTreatmentAssignment(
                scene_id=scene.id,
                visual_mode="blink",
                reasoning=f"Detected human micro-action suitable for blink: {action}.",
                visual_layers=_blink_layers(scene),
            )

    comparison_layers = _comparison_layers_for_scene(scene)
    if comparison_layers:
        return VisualTreatmentAssignment(
            scene_id=scene.id,
            visual_mode="comparison_board",
            reasoning=f"Detected {len(comparison_layers)} contrasted subjects in narration.",
            visual_layers=comparison_layers,
        )

    stat_fields = _stat_fields_for_scene(scene)
    if stat_fields is not None:
        stat_value, stat_label = stat_fields
        return VisualTreatmentAssignment(
            scene_id=scene.id,
            visual_mode="stat_card",
            reasoning=f"Detected one decisive statistic: {stat_value}.",
            stat_value=stat_value,
            stat_label=stat_label,
        )

    caption_fields = _caption_fields_for_scene(scene)
    if caption_fields is not None:
        caption_text, caption_emphasis = caption_fields
        return VisualTreatmentAssignment(
            scene_id=scene.id,
            visual_mode="captions",
            reasoning="Detected short editorial text beat.",
            caption_text=caption_text,
            caption_emphasis=caption_emphasis,
        )

    layers = _popup_layers_for_scene(scene, natural_only=True)
    if layers:
        return VisualTreatmentAssignment(
            scene_id=scene.id,
            visual_mode="popup_sequence",
            reasoning=f"Detected {len(layers)} list items in narration.",
            visual_layers=layers,
        )

    if _looks_like_continuous_progression(scene):
        return VisualTreatmentAssignment(
            scene_id=scene.id,
            visual_mode="continuous",
            reasoning="Detected same-scene visual progression in narration.",
            visual_layers=[],
        )

    return _full_frame_assignment(scene.id, "No list or micro-action pattern detected.")


def _space_non_repeatable_modes(
    assignments: list[VisualTreatmentAssignment],
    scenes: list[Scene],
) -> list[VisualTreatmentAssignment]:
    spaced: list[VisualTreatmentAssignment] = []
    scenes_by_id = {scene.id: scene for scene in scenes}
    previous_non_title_mode = "full_frame"
    for assignment in assignments:
        scene = scenes_by_id.get(assignment.scene_id)
        mode = _normalize_visual_mode(assignment.visual_mode)
        if (
            scene is not None
            and not scene.is_title_card
            and mode in NON_REPEATABLE_MODES
            and previous_non_title_mode in NON_REPEATABLE_MODES
        ):
            spaced_assignment = _full_frame_assignment(
                assignment.scene_id,
                f"Separated from adjacent {previous_non_title_mode} scene; full frame keeps non-full modes from running back to back.",
            )
        else:
            spaced_assignment = assignment

        spaced.append(spaced_assignment)
        if scene is not None and not scene.is_title_card:
            previous_non_title_mode = _normalize_visual_mode(spaced_assignment.visual_mode)
    return spaced


def _enforce_content_non_repeatable_spacing(content: ScriptContent) -> None:
    previous_non_title_mode = "full_frame"
    for scene in content.all_scenes():
        if scene.is_title_card:
            continue
        mode = _normalize_visual_mode(scene.visual_mode)
        if mode in NON_REPEATABLE_MODES and previous_non_title_mode in NON_REPEATABLE_MODES:
            logger.info(
                "[ANIMATION_TYPE] scene=%s forced full_frame to separate adjacent %s/%s modes",
                scene.id,
                previous_non_title_mode,
                mode,
            )
            scene.set_visual_mode("full_frame")
            scene.visual_layers = []
            mode = "full_frame"
        previous_non_title_mode = mode


def _full_frame_assignment(scene_id: str, reasoning: str) -> VisualTreatmentAssignment:
    return VisualTreatmentAssignment(
        scene_id=scene_id,
        visual_mode="full_frame",
        reasoning=reasoning,
        visual_layers=[],
    )


def _is_video_or_photo_backed(scene: Scene) -> bool:
    return (
        scene.visual_mode == "video"
        or bool(scene.video_url)
    )


def _normalize_visual_mode(value: str) -> VisualMode:
    if value in VISUAL_MODES:
        return value  # type: ignore[return-value]
    if value in {"quick_cuts", "montage"}:
        return "multi_frame"
    if value in LAYERED_LEGACY_TREATMENTS:
        return value  # type: ignore[return-value]
    return "full_frame"


def _looks_like_continuous_progression(scene: Scene) -> bool:
    words = {_normalize_word(word.word) for word in scene.word_timestamps or []}
    text = scene.narration.lower()
    progression_phrases = (
        "over time",
        "slowly turns",
        "slowly becomes",
        "slowly spreads",
        "slowly grows",
        "slowly expands",
        "step by step",
        "piece by piece",
    )
    if any(phrase in text for phrase in progression_phrases):
        return True
    return bool(words & PROGRESSION_MARKERS) and any(
        cue in words
        for cue in {"slowly", "gradually", "across", "through", "outward"}
    )


def _looks_like_blink_micro_action(scene: Scene) -> bool:
    words = {_normalize_word(word.word) for word in scene.word_timestamps or []}
    text = scene.narration.lower()
    has_subject = bool(words & MICRO_ACTION_SUBJECT_MARKERS)
    has_motion = bool(words & MICRO_ACTION_MOTION_MARKERS)
    has_strong_phrase = any(phrase in text for phrase in MICRO_ACTION_PHRASES)
    return (has_subject and (has_motion or has_strong_phrase)) or bool(
        _infer_blink_action(scene)
        and has_human_blink_subject(scene.narration, scene.visual_prompt)
    )


_BLINK_INFER_RULES: tuple[tuple[str, tuple[str, ...]], ...] = (
    ("blink", ("blink", "blinks", "blinking")),
)


def _phrase_matches(text: str, phrase: str) -> bool:
    return re.search(rf"\b{re.escape(phrase)}\b", text) is not None


def _infer_blink_action(scene: Scene) -> str:
    text = f"{scene.narration} {scene.visual_prompt}".casefold()
    for action, phrases in _BLINK_INFER_RULES:
        if any(_phrase_matches(text, phrase) for phrase in phrases):
            return normalize_production_blink_action(action)
    return ""


def _popup_layers_for_scene(
    scene: Scene,
    *,
    marker_only: bool = False,
    natural_only: bool = False,
) -> list[VisualLayer]:
    if not natural_only:
        marker_list_items = _matching_words(scene, LIST_MARKERS)
        if len(marker_list_items) >= 2:
            layer_count = min(len(marker_list_items), 4)
            return _popup_layers(scene, marker_list_items[:layer_count])

    if not marker_only:
        natural_list_items = _natural_list_items(scene)
        if len(natural_list_items) >= 2:
            layer_count = min(len(natural_list_items), 4)
            return _popup_layers(scene, natural_list_items[:layer_count])

    return []


def _popup_layers(scene: Scene, list_items: list[tuple[str, float]]) -> list[VisualLayer]:
    placements_by_count = {
        2: ["left", "right"],
        3: ["left", "center", "right"],
        4: ["top-left", "top-right", "bottom-left", "bottom-right"],
    }
    placements = placements_by_count.get(len(list_items), placements_by_count[2])
    fallback_step = max(scene.audio_duration_seconds / max(len(list_items), 1), 0.5)
    layers: list[VisualLayer] = []
    for index, (item, enter_at) in enumerate(list_items):
        fallback_enter_at = round(index * fallback_step, 2)
        layers.append(
            VisualLayer(
                id=f"{scene.id}_popup_{index + 1}",
                prompt=_panel_prompt(scene, item),
                placement=placements[index],
                enter_at_seconds=round(enter_at if enter_at >= 0 else fallback_enter_at, 2),
                animation="pop_in",
            )
        )
    return layers


def _blink_layers(scene: Scene) -> list[VisualLayer]:
    action = normalize_production_blink_action(scene.blink_action)
    _ensure_renderer_context(scene)
    return [
        VisualLayer(
            id=f"{scene.id}_state_a",
            asset_kind="cutout",
            prompt=blink_cutout_prompt(scene.visual_prompt, scene.narration, "state A", action=action),
            placement="center",
            enter_at_seconds=0.0,
            animation="none",
        ),
        VisualLayer(
            id=f"{scene.id}_state_b",
            asset_kind="cutout",
            prompt=blink_cutout_prompt(scene.visual_prompt, scene.narration, "state B", action=action),
            placement="center",
            enter_at_seconds=0.0,
            animation="none",
        ),
    ]


def _ensure_renderer_context(scene: Scene) -> None:
    context = normalize_renderer_context(scene.renderer_context)
    if not scene.renderer_context:
        context = infer_renderer_context(narration=scene.narration, visual_prompt=scene.visual_prompt)
    scene.renderer_context = context


def _comparison_layers_for_scene(scene: Scene) -> list[VisualLayer]:
    subjects = _comparison_subjects(scene)
    if len(subjects) < 2:
        return []
    subjects = subjects[:3]
    labels = _comparison_display_labels(scene, subjects)
    placements_by_count = {
        2: ["left", "right"],
        3: ["left", "center", "right"],
    }
    placements = placements_by_count[len(subjects)]
    fallback_step = max(scene.audio_duration_seconds / max(len(subjects), 1), 0.5)
    return [
        VisualLayer(
            id=f"{scene.id}_compare_{index + 1}",
            asset_kind="cutout",
            prompt=comparison_cutout_prompt(scene.visual_prompt, scene.narration, subject),
            label=labels[index] if index < len(labels) else "",
            placement=placements[index],
            enter_at_seconds=round(_phrase_start_seconds(scene, subject, index, len(subjects)) or index * fallback_step, 2),
            animation="pop_in",
        )
        for index, subject in enumerate(subjects)
    ]


def comparison_cutout_prompt(visual_prompt: str, narration: str, subject: str) -> str:
    base_prompt = visual_prompt.strip() or narration.strip()
    return (
        f"Comparison board transparent cutout for {subject}: {base_prompt}. "
        "Generate only this subject as an isolated transparent cutout candidate with a clear silhouette. "
        "No full background scene, no split-screen baked into the image, no decorative border, no picture frame, "
        "no mat, no white margin, no inset panel, no UI chrome, no caption box, no poster edge. "
        "No text in image."
    )


def blink_cutout_prompt(visual_prompt: str, narration: str, focus: str, *, action: str = "") -> str:
    normalized_focus = focus.strip().casefold()
    normalized_action = normalize_blink_action(action)
    if normalized_action:
        base_prompt = build_blink_state_prompt(
            visual_prompt=visual_prompt,
            narration=narration,
            action=normalized_action,
            state="a" if normalized_focus.endswith("a") else "b",
        )
    else:
        base_scene = visual_prompt.strip() or narration.strip()
        state_direction = (
            "Initial pose or expression before the small movement changes."
            if normalized_focus.endswith("a")
            else "Next compatible pose or expression; keep identity, scale, camera angle, and style consistent with State A."
        )
        base_prompt = f"Blink transparent cutout for {focus}: {base_scene}. {state_direction}"
    return (
        f"{base_prompt} "
        "Generate one isolated human or character subject whenever possible, waist-up or full-body depending on the action. "
        "Use a solid chroma background color that does not appear in the subject. "
        "Keep a clean closed silhouette for automatic cropping. "
        "No full background scene, scenery, split-screen, decorative border, picture frame, mat, white margin, "
        "inset panel, UI chrome, caption box, poster edge, speech bubble, labels, or text."
    )


def blink_panel_prompt(visual_prompt: str, narration: str, focus: str) -> str:
    return blink_cutout_prompt(visual_prompt, narration, focus)


def _panel_prompt(scene: Scene, focus: str) -> str:
    base_prompt = scene.visual_prompt.strip() or scene.narration.strip()
    return (
        f"Popup item cutout prompt for {focus}: {base_prompt}. "
        "Generate only the named popup item as a clean isolated cartoon cutout candidate. "
        "No decorative border, picture frame, mat, white margin, inset panel, UI chrome, caption box, or poster edge. "
        "No text in image."
    )


def _matching_words(scene: Scene, markers: set[str]) -> list[tuple[str, float]]:
    matches: list[tuple[str, float]] = []
    for word in scene.word_timestamps or []:
        normalized = _normalize_word(word.word)
        if normalized in markers:
            matches.append((normalized, word.start_ms / 1000))
    return matches


def _state_b_enter_at(scene: Scene, cue_words: list[tuple[str, float]]) -> float:
    if cue_words:
        return cue_words[0][1]
    midpoint = scene.audio_duration_seconds / 2 if scene.audio_duration_seconds > 0 else 0.5
    return max(midpoint, 0.5)


def _natural_list_items(scene: Scene) -> list[tuple[str, float]]:
    text = scene.narration.strip()
    if not text:
        return []
    words = {_normalize_word(word) for word in text.split()}
    if words & NATURAL_LIST_CONTRAST_CONNECTORS:
        return []

    normalized_text = re.sub(r"\s+", " ", text)
    normalized_text = _list_candidate_text(normalized_text)
    pieces = [
        _trim_list_item_phrase(piece.strip(" .,:;-"))
        for piece in re.split(r"\s*;\s*|\s*,\s*|\s+\b(?:and|or)\b\s+", normalized_text, flags=re.IGNORECASE)
    ]
    items = [piece for piece in pieces if _is_list_item_phrase(piece)]
    if not 2 <= len(items) <= 6:
        return []

    return [(item, _phrase_start_seconds(scene, item, index, len(items))) for index, item in enumerate(items[:4])]


def _comparison_subjects(scene: Scene) -> list[str]:
    text = scene.narration.strip()
    lower = text.lower()
    words = {_normalize_word(word) for word in text.split()}
    if "good choice" in lower and "bad choice" in lower:
        return ["good choice", "bad choice"]

    label_matches = re.findall(
        r"\b(myth|reality|outcome|before|after|then|now|success|failure)\b\s+(?:says|is|means|looks like)?\s*([^,.;]+)",
        text,
        flags=re.IGNORECASE,
    )
    if len(label_matches) >= 2:
        return [_trim_comparison_subject(label or phrase) for label, phrase in label_matches[:3]]

    for left, right in COMPARISON_PAIR_PHRASES:
        if left in words and right in words:
            return [left, right]

    connector_match = re.search(r"\b(versus|vs\.?|whereas|while|but)\b", text, flags=re.IGNORECASE)
    if not connector_match:
        return []
    left = _trim_comparison_subject(text[:connector_match.start()])
    right = _trim_comparison_subject(text[connector_match.end():])
    if left and right:
        return [left, right]
    return []


def _comparison_display_labels(scene: Scene, subjects: list[str]) -> list[str]:
    text = scene.narration.strip()
    lower = text.lower()
    words = {_normalize_word(word) for word in text.split()}
    if "good choice" in lower and "bad choice" in lower:
        return ["good choice", "bad choice"][:len(subjects)]

    label_matches = re.findall(
        r"\b(myth|reality|outcome|before|after|then|now|success|failure)\b\s+(?:says|is|means|looks like)?\s*([^,.;]+)",
        text,
        flags=re.IGNORECASE,
    )
    if len(label_matches) >= 2:
        return [_trim_comparison_subject(label or phrase) for label, phrase in label_matches[:len(subjects)]]

    for left, right in COMPARISON_PAIR_PHRASES:
        if left in words and right in words:
            return [left, right][:len(subjects)]

    return [""] * len(subjects)


def _trim_comparison_subject(value: str) -> str:
    cleaned = re.sub(r"^[^a-zA-Z0-9]*(?:at first|first|the|a|an)\s+", "", value.strip(), flags=re.IGNORECASE)
    cleaned = re.sub(r"\s+", " ", cleaned.strip(" .,:;-"))
    words = cleaned.split()
    if len(words) > 5:
        cleaned = " ".join(words[-5:])
    return cleaned.lower()


def _list_candidate_text(text: str) -> str:
    match = re.search(r"\bbetween\s+(.+)", text, flags=re.IGNORECASE)
    if match:
        text = match.group(1)
    elif ":" in text:
        text = text.split(":", 1)[1]

    trailing_clause = re.search(
        r",?\s+\b(?:and|or)\b\s+(?:you|it|this|that|they|he|she|we)\b",
        text,
        flags=re.IGNORECASE,
    )
    if trailing_clause:
        text = text[:trailing_clause.start()]
    return text


def _trim_list_item_phrase(text: str) -> str:
    trimmed = re.sub(
        r"^(?:you|they|we|he|she|it)\s+"
        r"(?:(?:learned|learn|needed|need|needs|tried|try|tries|started|start|starts)\s+to\s+|"
        r"(?:could|can|would|will|should|must|had to|has to|have to)\s+)",
        "",
        text,
        flags=re.IGNORECASE,
    ).strip()
    return trimmed or text


def _is_list_item_phrase(value: str) -> bool:
    words = [_normalize_word(word) for word in value.split()]
    content_words = [word for word in words if word and word not in REPETITION_STOPWORDS]
    return bool(content_words)


def _phrase_start_seconds(scene: Scene, phrase: str, index: int, total: int) -> float:
    phrase_words = [_normalize_word(word) for word in phrase.split()]
    first_content_word = next(
        (word for word in phrase_words if word and word not in REPETITION_STOPWORDS),
        phrase_words[0] if phrase_words else "",
    )
    if first_content_word:
        for word in scene.word_timestamps or []:
            if _normalize_word(word.word) == first_content_word:
                return word.start_ms / 1000

    fallback_step = max(scene.audio_duration_seconds / max(total, 1), 0.5)
    return index * fallback_step


def _has_repeated_content_word(scene: Scene) -> bool:
    seen: set[str] = set()
    for word in scene.word_timestamps or []:
        normalized = _normalize_word(word.word)
        if len(normalized) < 4 or normalized in REPETITION_STOPWORDS:
            continue
        if normalized in seen:
            return True
        seen.add(normalized)
    return False


def _normalize_word(value: str) -> str:
    return re.sub(r"[^a-z0-9]", "", value.lower())
