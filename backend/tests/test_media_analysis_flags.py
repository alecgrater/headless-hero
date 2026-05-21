"""Tests for manual media analysis source fallback behavior."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from api.media import (
    media_analysis_source_flags,
    normalize_media_assignments_for_sources,
    preserve_media_analysis_source_flags,
)
from models.script import ScriptContent
from pipeline.media_analyzer import MediaAssignment, _resolve_scene_id


def test_media_analysis_flags_default_old_scripts_to_manual_sources():
    assert media_analysis_source_flags({"segments": []}) == (True, True, False)


def test_media_analysis_flags_preserve_explicit_source_settings():
    assert media_analysis_source_flags({
        "segments": [],
        "gameplay_enabled": False,
        "stock_photo_enabled": True,
    }) == (False, True, False)


def test_preserve_media_analysis_flags_writes_inferred_legacy_defaults():
    content = ScriptContent(title="Legacy script", segments=[])

    preserve_media_analysis_source_flags(
        content,
        script_json={"segments": []},
        gameplay_enabled=True,
        stock_photo_enabled=True,
        ai_video_enabled=False,
    )

    dumped = content.model_dump()
    assert dumped["gameplay_enabled"] is True
    assert dumped["stock_photo_enabled"] is True


def test_preserve_media_analysis_flags_does_not_overwrite_explicit_final_settings():
    content = ScriptContent(
        title="Updated script",
        segments=[],
        gameplay_enabled=False,
        stock_photo_enabled=False,
    )

    preserve_media_analysis_source_flags(
        content,
        script_json={
            "segments": [],
            "gameplay_enabled": False,
            "stock_photo_enabled": False,
        },
        gameplay_enabled=True,
        stock_photo_enabled=True,
        ai_video_enabled=True,
    )

    dumped = content.model_dump()
    assert dumped["gameplay_enabled"] is False
    assert dumped["stock_photo_enabled"] is False


def test_normalize_media_assignments_coerces_disabled_sources_to_ai():
    assignments = [
        MediaAssignment("s1", "gameplay_video", "Minecraft", None, "gameplay fits"),
        MediaAssignment("s2", "stock_photo", None, "city skyline", "stock fits"),
        MediaAssignment("s3", "ai_video", None, None, "motion fits"),
        MediaAssignment("s4", "ai", None, None, "ai fits"),
    ]

    normalized = normalize_media_assignments_for_sources(
        assignments,
        gameplay_enabled=False,
        stock_photo_enabled=False,
        ai_video_enabled=False,
    )

    assert [a.media_source for a in normalized] == ["ai", "ai", "ai", "ai"]
    assert normalized[0].game_name is None
    assert normalized[1].search_query is None
    assert normalized[3].reasoning == "ai fits"


def test_resolve_scene_id_handles_unpadded_llm_ids():
    valid_scene_ids = {"scene_001", "scene_003", "scene_010"}

    assert _resolve_scene_id("scene_3", valid_scene_ids) == "scene_003"
    assert _resolve_scene_id("scene_010", valid_scene_ids) == "scene_010"
    assert _resolve_scene_id("scene_99", valid_scene_ids) is None
