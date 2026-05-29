"""Tests for duration variance diagnostics."""

import json
from pathlib import Path
import sys
from unittest.mock import MagicMock

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from models.script import ScriptContent
from pipeline.duration_variance import (
    MAX_DURATION_SECONDS,
    _flag_overlong_scenes,
    check_and_tighten,
)


def _make_script_content(scenes_data: list[dict]) -> ScriptContent:
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


def _make_script_record(scenes_data: list[dict]) -> MagicMock:
    content = _make_script_content(scenes_data)
    record = MagicMock()
    record.script_json = content.model_dump_json()
    return record


def test_static_and_continuous_scenes_are_not_flagged():
    content = _make_script_content([
        {"visual_beat": "static", "audio_duration_seconds": 15.0},
        {"visual_beat": "continuous", "audio_duration_seconds": 12.0},
    ])

    assert _flag_overlong_scenes(content) == []


def test_canonical_high_energy_scenes_over_threshold_are_flagged():
    content = _make_script_content([
        {"id": "scene_001", "visual_beat": "multi_frame", "audio_duration_seconds": MAX_DURATION_SECONDS + 0.1},
        {"id": "scene_002", "visual_beat": "captions", "audio_duration_seconds": MAX_DURATION_SECONDS + 1.0},
        {"id": "scene_003", "visual_beat": "static", "audio_duration_seconds": 15.0},
    ])

    flagged = _flag_overlong_scenes(content)

    assert [scene.id for scene in flagged] == ["scene_001", "scene_002"]


def test_legacy_high_energy_labels_normalize_before_diagnostics():
    content = _make_script_content([
        {"visual_beat": "quick_cuts", "audio_duration_seconds": MAX_DURATION_SECONDS + 1.0},
        {"visual_beat": "aha_subtitle", "audio_duration_seconds": MAX_DURATION_SECONDS + 1.0},
    ])

    flagged = _flag_overlong_scenes(content)

    assert [scene.visual_beat for scene in flagged] == ["multi_frame", "captions"]


def test_check_and_tighten_is_diagnostic_only():
    record = _make_script_record([
        {
            "id": "scene_001",
            "visual_beat": "multi_frame",
            "narration": "This narration stays exactly as written.",
            "audio_duration_seconds": MAX_DURATION_SECONDS + 2.0,
        },
    ])
    session = MagicMock()
    session.get.return_value = record
    before = record.script_json

    result = check_and_tighten(
        script_id="test-script",
        session=session,
        voice_id="voice-123",
        model_id="eleven_v3",
    )

    assert result == []
    assert record.script_json == before
    session.add.assert_not_called()
    session.commit.assert_not_called()
    content = ScriptContent.model_validate(json.loads(record.script_json))
    assert content.segments[0].scenes[0].narration == "This narration stays exactly as written."


def test_script_not_found_returns_empty():
    session = MagicMock()
    session.get.return_value = None

    assert check_and_tighten(script_id="missing", session=session, voice_id="voice-123") == []
