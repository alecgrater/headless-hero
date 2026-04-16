"""Tests for the duration variance check-and-tighten pipeline."""

import json
from unittest.mock import patch, MagicMock

import pytest

# Add backend to path so imports resolve
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from pipeline.duration_variance import (
    HIGH_ENERGY_BEATS,
    MAX_DURATION_SECONDS,
    _flag_overlong_scenes,
)
from models.script import ScriptContent


def _make_script_content(scenes_data: list[dict]) -> ScriptContent:
    """Build a minimal ScriptContent with one segment containing given scenes."""
    scenes = []
    for i, sd in enumerate(scenes_data):
        scenes.append({
            "id": sd.get("id", f"scene_{i:03d}"),
            "narration": sd.get("narration", "Test narration."),
            "visual_prompt": "",
            "visual_beat": sd.get("visual_beat", "static"),
            "audio_duration_seconds": sd.get("audio_duration_seconds", 0.0),
        })
    return ScriptContent(
        title="Test Video",
        segments=[{"name": "Test Segment", "scenes": scenes}],
    )


class TestFlagOverlongScenes:
    def test_no_high_energy_scenes_returns_empty(self):
        content = _make_script_content([
            {"visual_beat": "static", "audio_duration_seconds": 15.0},
            {"visual_beat": "continuous", "audio_duration_seconds": 12.0},
        ])
        flagged = _flag_overlong_scenes(content)
        assert flagged == []

    def test_high_energy_under_threshold_returns_empty(self):
        content = _make_script_content([
            {"visual_beat": "quick_cuts", "audio_duration_seconds": 8.0},
            {"visual_beat": "aha_subtitle", "audio_duration_seconds": 6.0},
        ])
        flagged = _flag_overlong_scenes(content)
        assert flagged == []

    def test_high_energy_over_threshold_flagged(self):
        content = _make_script_content([
            {"id": "scene_001", "visual_beat": "quick_cuts", "audio_duration_seconds": 12.5},
            {"id": "scene_002", "visual_beat": "static", "audio_duration_seconds": 15.0},
            {"id": "scene_003", "visual_beat": "aha_subtitle", "audio_duration_seconds": 11.0},
        ])
        flagged = _flag_overlong_scenes(content)
        assert len(flagged) == 2
        assert flagged[0].id == "scene_001"
        assert flagged[1].id == "scene_003"

    def test_exactly_at_threshold_not_flagged(self):
        content = _make_script_content([
            {"visual_beat": "quick_cuts", "audio_duration_seconds": 10.0},
        ])
        flagged = _flag_overlong_scenes(content)
        assert flagged == []

    def test_high_energy_no_audio_not_flagged(self):
        content = _make_script_content([
            {"visual_beat": "quick_cuts", "audio_duration_seconds": 0.0},
        ])
        flagged = _flag_overlong_scenes(content)
        assert flagged == []
