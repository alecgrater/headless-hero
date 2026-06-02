"""youtube-listicle format — preserves existing 8-segment educational behavior."""

from __future__ import annotations

from pipeline.modifiers.title_cards import enforce_title_cards_and_min_scenes
from prompts import (
    IDEATION_SYSTEM,
    SCRIPT_OUTLINE_INSTRUCTIONS,
    SCRIPT_SEGMENT_SCENES_INSTRUCTIONS,
    SCRIPT_SYSTEM,
)

from . import _register
from .base import FULL_VISUAL_MODE_VOCABULARY, FormatNote, VideoFormat, VisualBeatRules
from .title_cards.composite_grid import COMPOSITE_GRID

YOUTUBE_LISTICLE_BEAT_RULES = VisualBeatRules(
    allowed_beats=frozenset({"static", "continuous", "multi_frame"}),
    target_distribution={},  # current implementation is run-driven, not target-driven
    max_consecutive_same_beat=3,
    monotony_threshold=3,
)


YOUTUBE_LISTICLE = _register(VideoFormat(
    id="youtube-listicle",
    display_name="Educational Listicle",
    short_description='"8 things you didn\'t know about X" — staccato, viral-tuned, 8 segments.',
    level_count=8,
    level_label="segment",
    ideation_prompt=IDEATION_SYSTEM,
    script_system_prompt=SCRIPT_SYSTEM,
    outline_prompt=SCRIPT_OUTLINE_INSTRUCTIONS,
    segment_scenes_prompt=SCRIPT_SEGMENT_SCENES_INSTRUCTIONS,
    supports_cold_open=True,
    supports_hook_scoring=True,
    supports_segmented_generation=True,
    title_card_strategy=COMPOSITE_GRID,
    visual_beat_rules=YOUTUBE_LISTICLE_BEAT_RULES,
    enforce_post_processing=enforce_title_cards_and_min_scenes,
    supported_visual_modes=FULL_VISUAL_MODE_VOCABULARY,
    reference_notes=(
        FormatNote(category="Openings",
                   text="Cold-open candidates are generated, hook-scored, and refined before the full script is written."),
        FormatNote(category="Narration",
                   text="Every segment must stand alone as a short. Keep whole-video recaps, subscribe requests, and 'come back next week' CTAs out of scene narration; outro_cta is editor metadata only."),
        FormatNote(category="Visuals",
                   text="The full visual-mode vocabulary is available. Each scene chooses the single best-fit mode from its narration and visual intent; full_frame is the fallback when no specialized mode clearly helps."),
        FormatNote(category="Scene length",
                   text="Scene length follows the universal visual-mode policy, so comparison boards, captions, popup sequences, stat cards, and planned video scenes can be longer than normal full-frame beats."),
        FormatNote(category="Short-form",
                   text="Any segment can be exported as a standalone short; short-form upload titles are deterministic '{project title} - {segment title}'."),
    ),
))
