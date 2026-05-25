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
    _rewrite_narrations,
    check_and_tighten,
)
from config import DEFAULT_TTS_MODEL
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


class TestRewriteNarrations:
    @patch("pipeline.duration_variance.chat")
    def test_returns_mapping_from_claude_response(self, mock_chat):
        mock_chat.return_value = json.dumps({
            "scene_001": "Shorter version.",
            "scene_003": "Punchy fact.",
        })
        scenes = [
            MagicMock(id="scene_001", visual_beat="quick_cuts", narration="Long narration here.", audio_duration_seconds=12.5),
            MagicMock(id="scene_003", visual_beat="aha_subtitle", narration="Another long narration.", audio_duration_seconds=11.0),
        ]
        result = _rewrite_narrations(scenes, script_id="test-script")
        assert result == {"scene_001": "Shorter version.", "scene_003": "Punchy fact."}
        mock_chat.assert_called_once()
        call_kwargs = mock_chat.call_args
        assert "script_id" in call_kwargs.kwargs or call_kwargs[1].get("script_id")

    @patch("pipeline.duration_variance.chat")
    def test_returns_empty_on_claude_failure(self, mock_chat):
        mock_chat.side_effect = RuntimeError("API error")
        scenes = [
            MagicMock(id="scene_001", visual_beat="quick_cuts", narration="Long.", audio_duration_seconds=12.0),
        ]
        result = _rewrite_narrations(scenes, script_id="test-script")
        assert result == {}

    @patch("pipeline.duration_variance.chat")
    def test_returns_empty_on_invalid_json(self, mock_chat):
        mock_chat.return_value = "not valid json"
        scenes = [
            MagicMock(id="scene_001", visual_beat="quick_cuts", narration="Long.", audio_duration_seconds=12.0),
        ]
        result = _rewrite_narrations(scenes, script_id="test-script")
        assert result == {}


def _make_script_record(scenes_data: list[dict]) -> tuple:
    """Build a Script record and ScriptContent for testing."""
    content = _make_script_content(scenes_data)
    record = MagicMock()
    record.script_json = content.model_dump_json()
    return record, content


class TestCheckAndTighten:
    @patch("pipeline.duration_variance.generate_scene_audio")
    @patch("pipeline.duration_variance.chat")
    def test_no_overlong_scenes_returns_empty(self, mock_chat, mock_audio):
        record, _ = _make_script_record([
            {"id": "scene_001", "visual_beat": "quick_cuts", "audio_duration_seconds": 8.0},
        ])
        session = MagicMock()
        session.get.return_value = record

        result = check_and_tighten(
            script_id="test-script",
            session=session,
            voice_id="voice-123",
        )
        assert result == []
        mock_chat.assert_not_called()
        mock_audio.assert_not_called()

    @patch("pipeline.duration_variance.generate_scene_audio")
    @patch("pipeline.duration_variance.chat")
    def test_rewrites_and_revoices_overlong_scenes(self, mock_chat, mock_audio):
        record, _ = _make_script_record([
            {"id": "scene_001", "visual_beat": "quick_cuts", "narration": "Too long narration.", "audio_duration_seconds": 12.5},
            {"id": "scene_002", "visual_beat": "static", "narration": "Normal scene.", "audio_duration_seconds": 8.0},
        ])
        session = MagicMock()
        session.get.return_value = record

        mock_chat.return_value = json.dumps({"scene_001": "Short version."})
        mock_audio.return_value = ("/static/projects/test/audio/scene_001.mp3", 7.5, [{"word": "Short", "start_ms": 0, "end_ms": 500}], [{"start_ms": 0, "end_ms": 500}])

        result = check_and_tighten(
            script_id="test-script",
            session=session,
            voice_id="voice-123",
        )
        assert result == ["scene_001"]
        mock_audio.assert_called_once_with(
            scene_id="scene_001",
            narration="Short version.",
            voice_id="voice-123",
            script_id="test-script",
            model_id=DEFAULT_TTS_MODEL,
            voice_settings=None,
        )
        # Verify DB persistence
        session.add.assert_called_once_with(record)
        session.commit.assert_called_once()

        # Verify updated script_json
        updated_content = ScriptContent.model_validate(json.loads(record.script_json))
        scene_001 = updated_content.segments[0].scenes[0]
        assert scene_001.narration == "Short version."
        assert scene_001.audio_duration_seconds == 7.5

    @patch("pipeline.duration_variance.generate_scene_audio")
    @patch("pipeline.duration_variance.chat")
    def test_rewrite_revoice_uses_hidden_v3_tags(self, mock_chat, mock_audio):
        record, _ = _make_script_record([
            {"id": "scene_001", "visual_beat": "quick_cuts", "narration": "Too long narration.", "audio_duration_seconds": 12.5},
        ])
        session = MagicMock()
        session.get.return_value = record

        mock_chat.return_value = json.dumps({"scene_001": "Short version."})
        mock_audio.return_value = ("/static/projects/test/audio/scene_001.mp3", 7.5, [], [])

        result = check_and_tighten(
            script_id="test-script",
            session=session,
            voice_id="voice-123",
            model_id="eleven_v3",
        )

        assert result == ["scene_001"]
        mock_audio.assert_called_once_with(
            scene_id="scene_001",
            narration="[curious] Short version.",
            voice_id="voice-123",
            script_id="test-script",
            model_id="eleven_v3",
            voice_settings=None,
        )

    @patch("pipeline.duration_variance.generate_scene_audio")
    @patch("pipeline.duration_variance.chat")
    def test_skips_scene_if_revoice_fails(self, mock_chat, mock_audio):
        record, _ = _make_script_record([
            {"id": "scene_001", "visual_beat": "aha_subtitle", "narration": "Long fact.", "audio_duration_seconds": 11.0},
        ])
        session = MagicMock()
        session.get.return_value = record

        mock_chat.return_value = json.dumps({"scene_001": "Short fact."})
        mock_audio.side_effect = RuntimeError("ElevenLabs down")

        result = check_and_tighten(
            script_id="test-script",
            session=session,
            voice_id="voice-123",
        )
        # Scene was not successfully re-voiced, so not in result
        assert result == []

    @patch("pipeline.duration_variance.generate_scene_audio")
    @patch("pipeline.duration_variance.chat")
    def test_script_not_found_returns_empty(self, mock_chat, mock_audio):
        session = MagicMock()
        session.get.return_value = None

        result = check_and_tighten(
            script_id="nonexistent",
            session=session,
            voice_id="voice-123",
        )
        assert result == []
        mock_chat.assert_not_called()
        mock_audio.assert_not_called()

    @patch("pipeline.duration_variance.generate_scene_audio")
    @patch("pipeline.duration_variance.chat")
    def test_ignores_unknown_scene_id_from_claude(self, mock_chat, mock_audio):
        record, _ = _make_script_record([
            {"id": "scene_001", "visual_beat": "quick_cuts", "narration": "Long.", "audio_duration_seconds": 12.0},
        ])
        session = MagicMock()
        session.get.return_value = record

        # Claude returns a rewrite for a scene_id that doesn't exist
        mock_chat.return_value = json.dumps({"scene_999": "Ghost scene."})

        result = check_and_tighten(
            script_id="test-script",
            session=session,
            voice_id="voice-123",
        )
        assert result == []
        mock_audio.assert_not_called()
        # No DB write since nothing was tightened
        session.commit.assert_not_called()
