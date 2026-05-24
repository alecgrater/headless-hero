"""life-as-a format — literary second-person level-by-level walk-through."""

from __future__ import annotations

import logging
import math
import os
import re

from models.script import LevelMeta, Scene, ScriptContent, Segment
from prompts import (
    LIFE_AS_A_IDEATION_SYSTEM,
    LIFE_AS_A_LEVEL_SCENES_INSTRUCTIONS,
    LIFE_AS_A_OUTLINE_INSTRUCTIONS,
    LIFE_AS_A_SCRIPT_SYSTEM,
)

from . import _register
from .base import VideoFormat, VisualBeatRules
from .title_cards.cinematic_chapters import CINEMATIC_CHAPTERS

logger = logging.getLogger(__name__)

_ELI_PREFIX_RE = re.compile(
    r"^(?:\[[A-Z\-]+\]\s*)?Eli, the recurring character, is the main subject\b",
    re.IGNORECASE,
)
_ELI_PROTAGONIST_INSTRUCTION_RE = re.compile(
    r"^Eli, the recurring character, is the main subject and protagonist in this scene\.\s*"
    r"Depict Eli as .*?; any other people are secondary and visually distinct from Eli\.\s*",
    re.IGNORECASE,
)
_SECONDARY_PEOPLE_INSTRUCTION_RE = re.compile(
    r"; any other people are secondary and visually distinct from (?:Eli|[^.]+)",
    re.IGNORECASE,
)
_ROLE_PREFIX_RE = re.compile(r"^your life as an?\s+", re.IGNORECASE)
_SHOT_PREFIX_RE = re.compile(r"^(\[[A-Z\-]+\]\s*)(.*)$")
_LEVEL_NAME_PREFIX_RE = re.compile(
    r"^level\s+(?:\d+|one|two|three|four|five|six|seven|eight|nine|ten)\b[\s,.:;!?\-—–]*",
    re.IGNORECASE,
)
_SENTENCE_SPLIT_RE = re.compile(r"(?<=[.!?])\s+")
_SOLO_AI_VIDEO_BLOCKER_RE = re.compile(
    r"\b("
    r"crowd|crowds|group|groups|audience|classmates?|colleagues?|"
    r"family|friends?|partners?|"
    r"line of people|room full of people|another person|second person|"
    r"two people|three people|other guards?|other workers?"
    r")\b",
    re.IGNORECASE,
)
_SOLO_AI_VIDEO_INSTRUCTION = "Only the active protagonist/main character appears; no other people are visible."
_NAMED_SECONDARY_INTERACTION_RE = re.compile(
    r"\b(?:with|beside|next to|argues? with|talks? to|speaks? to|faces|meets)\s+(?!Eli\b)[A-Z][a-z]{2,}\b"
)
_SOLO_AI_VIDEO_PERSON_TERMS = {
    "guard",
    "officer",
    "inmate",
    "prisoner",
    "student",
    "teacher",
    "manager",
    "coworker",
    "customer",
    "patient",
    "worker",
    "person",
}

_HUMAN_SUBJECT_TERMS = {
    "person",
    "people",
    "human",
    "figure",
    "character",
    "worker",
    "employee",
    "guard",
    "officer",
    "prisoner",
    "inmate",
    "soldier",
    "teacher",
    "nurse",
    "doctor",
    "driver",
    "cashier",
    "chef",
    "parent",
    "student",
    "artist",
    "player",
    "gambler",
    "manager",
    "detective",
    "pilot",
    "farmer",
    "mechanic",
    "engineer",
}


LIFE_AS_A_BEAT_RULES = VisualBeatRules(
    allowed_beats=frozenset({"static", "continuous", "multi_frame"}),
    target_distribution={
        "static": (0.45, 0.60),
        "continuous": (0.25, 0.35),
        "multi_frame": (0.15, 0.25),
        "quick_cuts": (0.15, 0.25),  # legacy compatibility alias
    },
    max_consecutive_same_beat=2,
    monotony_threshold=3,
)


def _setting_bool(name: str, default: bool) -> bool:
    value = os.environ.get(name)
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


def _setting_int(name: str, default: int, minimum: int, maximum: int) -> int:
    raw = os.environ.get(name, str(default)).strip()
    try:
        value = int(raw)
    except ValueError:
        logger.warning("[LIFE_AS_A_CHUNKING] invalid %s=%r; using default=%d", name, raw, default)
        return default
    return max(minimum, min(value, maximum))


def life_as_a_chunking_settings() -> dict[str, int | bool]:
    return {
        "enabled": _setting_bool("LIFE_AS_A_SCENE_CHUNKING_ENABLED", True),
        "target": _setting_int("LIFE_AS_A_TARGET_SCENE_SECONDS", 8, 5, 12),
        "max": _setting_int("LIFE_AS_A_MAX_SCENE_SECONDS", 12, 8, 18),
        "single_visual_max": _setting_int("LIFE_AS_A_SINGLE_VISUAL_MAX_SECONDS", 8, 5, 12),
    }


def life_as_a_role(content: ScriptContent) -> str:
    role = _ROLE_PREFIX_RE.sub("", content.title.strip()).strip(" .,:;!?")
    return role or "the protagonist"


def _chapter_card_narration(descriptor: str) -> str:
    cleaned = _LEVEL_NAME_PREFIX_RE.sub("", descriptor.strip()).strip(" .,:;!?")
    if not cleaned:
        return "The beginning."
    if cleaned.lower().startswith("the "):
        return f"The {cleaned[4:].strip().lower()}."
    return f"The {cleaned.lower()}."


def _role_terms(role: str) -> set[str]:
    terms = {role.lower()} if role else set()
    words = [word for word in re.split(r"[^a-zA-Z]+", role.lower()) if len(word) > 2]
    if words:
        terms.add(words[-1])
    return terms


def _contains_any_term(text: str, terms: set[str]) -> bool:
    lowered = text.lower()
    return any(re.search(rf"\b{re.escape(term)}\b", lowered) for term in terms if term)


def _scene_text(scene: Scene) -> str:
    pieces = [scene.visual_prompt, scene.narration]
    pieces.extend(frame.prompt for frame in scene.frame_directives or [])
    return "\n".join(piece for piece in pieces if piece)


def is_life_as_a_eli_scene(scene: Scene, role: str = "") -> bool:
    """Return True when a life-as-a scene should depict Eli as the protagonist."""
    if scene.is_title_card:
        return False
    text = _scene_text(scene)
    if _ELI_PREFIX_RE.search(text) or re.search(r"\bEli\b", text):
        return True
    terms = _HUMAN_SUBJECT_TERMS | _role_terms(role)
    return scene.contains_person or _contains_any_term(text, terms)


def _solo_ai_video_candidate_text(scene: Scene) -> str:
    text = _scene_text(scene)
    return _SECONDARY_PEOPLE_INSTRUCTION_RE.sub("", text)


def is_life_as_a_solo_ai_video_scene(scene: Scene, role: str = "") -> bool:
    """Return True when an AI-video scene can sensibly show only the protagonist."""
    if scene.is_title_card:
        return False
    text = _solo_ai_video_candidate_text(scene)
    if _SOLO_AI_VIDEO_BLOCKER_RE.search(text):
        return False
    if _NAMED_SECONDARY_INTERACTION_RE.search(text):
        return False
    role_terms = _role_terms(role)
    for term in _SOLO_AI_VIDEO_PERSON_TERMS | role_terms:
        if term in role_terms:
            pattern = rf"\b(?:another|other|second|two|three)\s+{re.escape(term)}s?\b"
        else:
            pattern = rf"\b{re.escape(term)}s?\b"
        if re.search(pattern, text, re.IGNORECASE):
            return False
    return True


def _solo_ai_video_prompt(prompt: str) -> str:
    stripped = prompt.strip()
    if not stripped:
        return prompt
    stripped = _SECONDARY_PEOPLE_INSTRUCTION_RE.sub("; no other people are visible", stripped)
    if "no other people are visible" in stripped.lower():
        return stripped
    shot_match = _SHOT_PREFIX_RE.match(stripped)
    if not shot_match:
        return f"{_SOLO_AI_VIDEO_INSTRUCTION} {stripped}"
    shot_tag, rest = shot_match.groups()
    return f"{shot_tag}{_SOLO_AI_VIDEO_INSTRUCTION} {rest}".strip()


def enforce_life_as_a_ai_video_solo_subject(scene: Scene) -> None:
    """Strengthen AI-video prompts so animation never introduces extra people."""
    scene.visual_prompt = _solo_ai_video_prompt(scene.visual_prompt)
    scene.contains_person = True
    for frame in scene.frame_directives or []:
        if frame.source != "ai_generated":
            continue
        frame.prompt = _solo_ai_video_prompt(frame.prompt)
        frame.contains_person = True


def _eli_scene_prompt(prompt: str, role: str) -> str:
    stripped = prompt.strip()
    if not stripped or _ELI_PREFIX_RE.match(stripped) or re.search(r"\bEli\b", stripped):
        return prompt
    role_phrase = role if role != "the protagonist" else "the protagonist"
    eli_instruction = (
        "Eli, the recurring character, is the main subject and protagonist in this scene. "
        f"Depict Eli as {role_phrase}; any other people are secondary and visually distinct from Eli."
    )
    shot_match = _SHOT_PREFIX_RE.match(stripped)
    if not shot_match:
        return f"{eli_instruction} {stripped}"
    shot_tag, rest = shot_match.groups()
    return f"{shot_tag}{eli_instruction} {rest}".strip()


def _main_character_scene_prompt(prompt: str, content: ScriptContent, role: str) -> str:
    stripped = prompt.strip()
    character = content.main_character
    character_name = character.name.strip() if character and character.name.strip() else "the main character"
    if not stripped:
        return prompt

    shot_tag = ""
    shot_match = _SHOT_PREFIX_RE.match(stripped)
    if shot_match:
        shot_tag, stripped = shot_match.groups()

    stripped = _ELI_PROTAGONIST_INSTRUCTION_RE.sub("", stripped).strip()
    stripped = re.sub(r"\bEli\b", character_name, stripped)
    character_instruction = (
        f"{character_name} is the main subject and protagonist in this scene. "
        f"Depict {character_name} as {role}; any other people are secondary and visually distinct from {character_name}."
    )
    if stripped.startswith(character_instruction):
        return f"{shot_tag}{stripped}".strip()
    return f"{shot_tag}{character_instruction} {stripped}".strip()


def _split_sentences(narration: str) -> list[str]:
    sentences = [part.strip() for part in _SENTENCE_SPLIT_RE.split(narration.strip()) if part.strip()]
    return sentences or ([narration.strip()] if narration.strip() else [])


def _single_frame_directives(scene: Scene) -> list[dict]:
    contains_person = bool(scene.contains_person)
    prompt = scene.visual_prompt.strip() or scene.narration.strip()
    return [{
        "prompt": prompt,
        "source": "ai_generated",
        "transition": "cut",
        "reference_previous": False,
        "search_query": "",
        "contains_person": contains_person,
    }]


def _scene_estimated_duration(scene: Scene, *, target_seconds: int) -> float:
    sentence_count = len(_split_sentences(scene.narration))
    if scene.duration_estimate_seconds > 0:
        if scene.duration_estimate_seconds <= target_seconds and sentence_count > 2:
            return sentence_count * float(target_seconds)
        return float(scene.duration_estimate_seconds)
    return max(float(target_seconds), sentence_count * float(target_seconds))


def _chunk_sentences(sentences: list[str], chunk_count: int) -> list[list[str]]:
    if chunk_count <= 1 or len(sentences) <= 1:
        return [sentences]
    chunk_count = min(chunk_count, len(sentences))
    chunks: list[list[str]] = []
    for index in range(chunk_count):
        start = round(index * len(sentences) / chunk_count)
        end = round((index + 1) * len(sentences) / chunk_count)
        chunks.append(sentences[start:end] or [sentences[min(index, len(sentences) - 1)]])
    return chunks


def _split_life_as_a_scenes(content: ScriptContent) -> int:
    settings = life_as_a_chunking_settings()
    enabled = bool(settings["enabled"])
    target_seconds = int(settings["target"])
    max_seconds = int(settings["max"])
    effective_max_seconds = min(max_seconds, 14)
    logger.info(
        "[LIFE_AS_A_CHUNKING] settings: enabled=%s target=%d max=%d ai_video_max=%d",
        str(enabled).lower(),
        target_seconds,
        max_seconds,
        int(settings["single_visual_max"]),
    )
    if not enabled:
        return 0

    split_count = 0
    for segment in content.segments:
        rewritten: list[Scene] = []
        for scene in segment.scenes:
            if scene.is_title_card:
                rewritten.append(scene)
                continue
            estimated_duration = _scene_estimated_duration(scene, target_seconds=target_seconds)
            sentences = _split_sentences(scene.narration)
            if estimated_duration <= effective_max_seconds or len(sentences) <= 1:
                logger.info(
                    "[LIFE_AS_A_CHUNKING] kept scene %s; reason=duration %.1fs within target",
                    scene.id,
                    estimated_duration,
                )
                rewritten.append(scene)
                continue

            chunk_count = min(len(sentences), max(2, math.ceil(estimated_duration / target_seconds)))
            chunks = _chunk_sentences(sentences, chunk_count)
            logger.info(
                "[LIFE_AS_A_CHUNKING] split scene %s into %d chunks; reason=estimated_duration %.1fs > max %.1fs",
                scene.id,
                len(chunks),
                estimated_duration,
                float(effective_max_seconds),
            )
            for chunk_index, chunk in enumerate(chunks):
                chunk_scene = scene.model_copy(deep=True)
                chunk_scene.narration = " ".join(chunk).strip()
                chunk_scene.duration_estimate_seconds = max(
                    1.0,
                    round(estimated_duration * len(chunk) / len(sentences), 2),
                )
                chunk_scene.visual_beat = "static"
                chunk_scene.frame_directives = _single_frame_directives(chunk_scene)
                chunk_scene.image_url = ""
                chunk_scene.audio_url = ""
                chunk_scene.audio_duration_seconds = 0.0
                chunk_scene.word_timestamps = None
                chunk_scene.phrase_timestamps = None
                chunk_scene.frame_urls = []
                chunk_scene.media_source = "ai"
                chunk_scene.video_url = ""
                chunk_scene.visual_source_metadata = None
                if chunk_index > 0:
                    chunk_scene.fx = None
                    chunk_scene.eli_overlay = None
                rewritten.append(chunk_scene)
            split_count += 1
        segment.scenes = rewritten

    _renumber_scenes(content)
    return split_count


def _renumber_scenes(content: ScriptContent) -> None:
    next_id = 1
    for scene in content.all_scenes():
        scene.id = f"scene_{next_id:03d}"
        next_id += 1


def enforce_life_as_a_visual_complexity(content: ScriptContent) -> int:
    return 0


def _mark_protagonist_scenes(content: ScriptContent, *, eli_enabled: bool = True) -> int:
    role = life_as_a_role(content)
    updated = 0
    for scene in content.all_scenes():
        if not is_life_as_a_eli_scene(scene, role):
            continue
        original_prompt = scene.visual_prompt
        scene.visual_prompt = (
            _eli_scene_prompt(scene.visual_prompt, role)
            if eli_enabled
            else _main_character_scene_prompt(scene.visual_prompt, content, role)
        )
        scene.contains_person = True
        if scene.visual_prompt != original_prompt:
            updated += 1

        for frame in scene.frame_directives or []:
            if frame.source != "ai_generated":
                continue
            frame_prompt = frame.prompt
            new_prompt = (
                _eli_scene_prompt(frame_prompt, role)
                if eli_enabled
                else _main_character_scene_prompt(frame_prompt, content, role)
            )
            if new_prompt != frame_prompt:
                frame.prompt = new_prompt
                updated += 1
            frame.contains_person = True

    if updated:
        protagonist = "Eli" if eli_enabled else "main-character"
        logger.info("life-as-a: marked %d visual prompt(s) as %s protagonist scenes", updated, protagonist)
    return updated


def enforce_life_as_a_constraints(content: ScriptContent, *, eli_enabled: bool = True) -> ScriptContent:
    """Post-process a life-as-a script.

    - Coerce disallowed visual_beat values ('aha_subtitle') back to 'static'.
    - Normalize legacy multi-frame aliases to the canonical 'multi_frame' beat.
    - Ensure each segment has a chapter-card scene at index 0 (is_title_card=True).
    - Synthesize content.levels[] from segments if Claude omitted it (defensive).
    - Split long paragraph scenes into short single-beat render scenes.
    - Mark visible protagonist scenes so the active protagonist reference is used.
    """
    allowed = LIFE_AS_A_BEAT_RULES.allowed_beats
    coerced = 0
    for scene in content.all_scenes():
        if scene.is_title_card:
            continue
        if scene.visual_mode == "multi_frame" or scene.visual_beat in {"quick_cuts", "montage", "multi_frame"}:
            scene.visual_beat = "multi_frame"
        elif scene.visual_beat not in allowed:
            scene.visual_beat = "static"
            coerced += 1
    if coerced:
        logger.info("life-as-a: coerced %d disallowed visual_beat values to 'static'", coerced)

    # Ensure chapter-card scene at start of each segment
    for seg_idx, segment in enumerate(content.segments):
        if not segment.scenes or not segment.scenes[0].is_title_card:
            level_num = seg_idx + 1
            level = (
                content.levels[seg_idx]
                if content.levels and seg_idx < len(content.levels)
                else None
            )
            descriptor = level.descriptor if level else segment.name
            # Prefer levels[].image_prompt (populated by segmented assembly) over
            # segment.title_card_image_prompt (which the segmented outline does not set).
            image_prompt = (
                (level.image_prompt if level and level.image_prompt else None)
                or (content.cinematic_thumbnail_prompt if level_num == 1 else None)
                or segment.title_card_image_prompt
                or descriptor
            )
            chapter_scene = Scene(
                id=f"chapter_{level_num:02d}",
                narration=_chapter_card_narration(descriptor),
                visual_prompt=f"[ESTABLISHING] {image_prompt}",
                duration_estimate_seconds=4.0,
                is_title_card=True,
                visual_beat="static",
            )
            segment.scenes.insert(0, chapter_scene)
            logger.info("life-as-a: inserted chapter card for level %d", level_num)

    # Synthesize levels[] if missing
    if not content.levels:
        content.levels = [
            LevelMeta(
                number=i + 1,
                descriptor=seg.short_name or seg.name,
                image_prompt=seg.title_card_image_prompt,
            )
            for i, seg in enumerate(content.segments)
        ]
        logger.info("life-as-a: synthesized levels[] from segments")

    # Normalize model-provided chapter cards too. The prompt asks for descriptor-
    # only narration, but older scripts and occasional model drift may include
    # the level prefix; TTS is the only layer that should add it back.
    for seg_idx, segment in enumerate(content.segments):
        if not segment.scenes or not segment.scenes[0].is_title_card:
            continue
        level = (
            content.levels[seg_idx]
            if content.levels and seg_idx < len(content.levels)
            else None
        )
        descriptor = level.descriptor if level else segment.short_name or segment.name
        normalized = _chapter_card_narration(descriptor)
        if segment.scenes[0].narration != normalized:
            segment.scenes[0].narration = normalized
            logger.info("life-as-a: normalized chapter card narration for level %d", seg_idx + 1)

    _split_life_as_a_scenes(content)
    _mark_protagonist_scenes(content, eli_enabled=eli_enabled)
    enforce_life_as_a_visual_complexity(content)

    return content


LIFE_AS_A = _register(VideoFormat(
    id="life-as-a",
    display_name="Your Life As A...",
    short_description='A walk through the stages of being something — literary, 4–7 levels, second-person.',
    level_count=(4, 7),
    level_label="level",
    ideation_prompt=LIFE_AS_A_IDEATION_SYSTEM,
    script_system_prompt=LIFE_AS_A_SCRIPT_SYSTEM,
    outline_prompt=LIFE_AS_A_OUTLINE_INSTRUCTIONS,
    segment_scenes_prompt=LIFE_AS_A_LEVEL_SCENES_INSTRUCTIONS,
    supports_cold_open=False,
    supports_hook_scoring=False,
    supports_segmented_generation=True,
    title_card_strategy=CINEMATIC_CHAPTERS,
    visual_beat_rules=LIFE_AS_A_BEAT_RULES,
    enforce_post_processing=enforce_life_as_a_constraints,
))
