import json
import logging
from datetime import datetime, timezone

from pipeline import fallback_observability as fallback


def test_record_fallback_emits_parseable_json(caplog):
    caplog.set_level(logging.WARNING)

    fallback.record_fallback(
        category="image_generation",
        event="image_placeholder_created",
        reason="AI image generation failed",
        from_value="google",
        to_value="placeholder",
        script_id="script-1",
        scene_id="scene-2",
        severity="fail",
        metadata={
            "provider": "google",
            "asset_path": "~/git/headless-hero/data/projects/script-1/images/scene-2.png",
            "prompt": "do not leak prompt text",
            "duration_seconds": 4.2,
        },
    )

    assert len(caplog.records) == 1
    record = caplog.records[0]
    assert record.levelname == "ERROR"
    assert record.message.startswith("[FALLBACK] ")

    payload = json.loads(record.message.removeprefix("[FALLBACK] "))
    assert payload == {
        "category": "image_generation",
        "event": "image_placeholder_created",
        "reason": "AI image generation failed",
        "from": "google",
        "to": "placeholder",
        "script_id": "script-1",
        "scene_id": "scene-2",
        "severity": "fail",
        "metadata": {
            "asset_basename": "scene-2.png",
            "duration_seconds": 4.2,
            "provider": "google",
        },
    }


def test_parse_fallback_message_ignores_non_fallback_and_malformed_rows():
    assert fallback.parse_fallback_message("ordinary log") is None
    assert fallback.parse_fallback_message("[FALLBACK] not-json") is None


def test_summarize_fallback_events_counts_and_hot_events():
    events = [
        {
            "id": 1,
            "timestamp": datetime(2026, 6, 5, tzinfo=timezone.utc).isoformat(),
            "logger_name": "pipeline.image_gen",
            "category": "image_generation",
            "event": "image_placeholder_created",
            "reason": "AI failed",
            "severity": "fail",
        },
        {
            "id": 2,
            "timestamp": datetime(2026, 6, 5, tzinfo=timezone.utc).isoformat(),
            "logger_name": "pipeline.media_analyzer",
            "category": "visual_mode",
            "event": "ai_video_downgraded",
            "reason": "Adjacent video",
            "severity": "warn",
        },
        {
            "id": 3,
            "timestamp": datetime(2026, 6, 5, tzinfo=timezone.utc).isoformat(),
            "logger_name": "pipeline.media_analyzer",
            "category": "visual_mode",
            "event": "ai_video_downgraded",
            "reason": "Adjacent video",
            "severity": "warn",
        },
        {
            "id": 4,
            "timestamp": datetime(2026, 6, 5, tzinfo=timezone.utc).isoformat(),
            "logger_name": "pipeline.media_analyzer",
            "category": "visual_mode",
            "event": "ai_video_downgraded",
            "reason": "Adjacent video",
            "severity": "warn",
        },
    ]

    summary = fallback.summarize_fallback_events(events, window_hours=24, malformed_count=1)

    assert summary["total"] == 4
    assert summary["malformed_count"] == 1
    assert summary["by_severity"] == {"fail": 1, "warn": 3}
    assert summary["by_category"][0] == {"category": "visual_mode", "count": 3}
    assert summary["by_event"][0] == {
        "category": "visual_mode",
        "event": "ai_video_downgraded",
        "count": 3,
        "severity": "warn",
    }
    assert summary["by_reason"][0] == {"reason": "Adjacent video", "count": 3}
    assert {item["event"] for item in summary["hot_events"]} == {
        "image_placeholder_created",
        "ai_video_downgraded",
    }
