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
from .base import VideoFormat, VisualBeatRules
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
))
