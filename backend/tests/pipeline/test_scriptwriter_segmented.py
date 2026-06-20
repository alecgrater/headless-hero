import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from pipeline.scriptwriter import (
    _build_segment_scene_user_message,
    _generate_outline,
    _visual_opportunity_summary,
)


def test_segment_scene_message_includes_segment_visual_opportunities():
    outline = {
        "segments": [
            {
                "name": "Segment One",
                "topic_summary": "A segment about drift.",
                "circle_color": "#38bdf8",
                "title_card_image_prompt": "A bright blue racing circle.",
                "visual_opportunities": [
                    {
                        "mode": "captions",
                        "beat": "This is the road.",
                        "why": "A realization lands as text.",
                        "duration_profile": "extended",
                        "priority": "strong",
                    }
                ],
            }
        ]
    }

    message = _build_segment_scene_user_message(
        outline=outline,
        segment_index=0,
        trailing_context="",
        segment_scenes_instructions="SEGMENT INSTRUCTIONS",
        level_label="segment",
    )

    assert json.dumps(outline, indent=2) in message
    assert "VISUAL OPPORTUNITIES FOR THIS SEGMENT" in message
    assert "This is the road." in message
    assert "captions" in message
    assert "SEGMENT INSTRUCTIONS" in message

    outline_index = message.index("FULL SCRIPT OUTLINE")
    metadata_index = message.index('WRITE SCENES FOR SEGMENT 1/1: "Segment One"')
    opportunities_index = message.index("VISUAL OPPORTUNITIES FOR THIS SEGMENT")
    instructions_index = message.index("SEGMENT INSTRUCTIONS")

    assert outline_index < metadata_index
    assert "Topic summary: A segment about drift." in message
    assert "Circle color: #38bdf8" in message
    assert "Title card image prompt: A bright blue racing circle." in message
    assert metadata_index < opportunities_index < instructions_index


def test_segment_scene_message_preserves_trailing_context_order():
    outline = {
        "segments": [
            {
                "name": "Segment One",
                "topic_summary": "A segment about drift.",
                "visual_opportunities": [],
            }
        ]
    }

    message = _build_segment_scene_user_message(
        outline=outline,
        segment_index=0,
        trailing_context="TRAILING CONTEXT\n\n",
        segment_scenes_instructions="SEGMENT INSTRUCTIONS",
        level_label="segment",
    )

    opportunities_index = message.index("VISUAL OPPORTUNITIES FOR THIS SEGMENT")
    trailing_context_index = message.index("TRAILING CONTEXT")
    instructions_index = message.index("SEGMENT INSTRUCTIONS")

    assert opportunities_index < trailing_context_index < instructions_index


def test_visual_opportunity_summary_counts_planned_modes():
    outline = {
        "segments": [
            {"visual_opportunities": [{"mode": "captions"}, {"mode": "blink"}]},
            {"visual_opportunities": [{"mode": "captions"}, {"mode": "stat_card"}]},
        ]
    }

    assert _visual_opportunity_summary(outline) == {
        "captions": 2,
        "blink": 1,
        "stat_card": 1,
    }


def test_visual_opportunity_summary_skips_malformed_entries():
    outline = {
        "segments": [
            {"visual_opportunities": ["captions", {"mode": "blink"}, None]},
            {"visual_opportunities": {"mode": "stat_card"}},
        ]
    }

    assert _visual_opportunity_summary(outline) == {"blink": 1}


def test_generate_outline_allows_visual_opportunity_metadata_room(monkeypatch):
    captured = {}

    def fake_chat(*_args, **kwargs):
        captured.update(kwargs)
        return json.dumps(
            {
                "title": "Video Title",
                "card_title": "TITLE",
                "card_title_highlight_word": "TITLE",
                "card_subtitle": "",
                "intro_hook": "A hook.",
                "outro_cta": "A close.",
                "segments": [
                    {
                        "name": "Segment One",
                        "short_name": "One",
                        "circle_color": "#38bdf8",
                        "title_card_image_prompt": "A scene.",
                        "topic_summary": "A compact summary.",
                        "visual_opportunities": [
                            {
                                "mode": "captions",
                                "beat": "A realization lands.",
                                "why": "Text reinforces the point.",
                                "duration_profile": "extended",
                                "priority": "strong",
                            }
                        ],
                    }
                ],
            }
        )

    monkeypatch.setattr("pipeline.scriptwriter.chat", fake_chat)

    outline = _generate_outline(
        system_prompt="system",
        user_message="user",
        model=None,
        script_id="script-1",
        outline_instructions="Return JSON.",
    )

    assert outline["segments"][0]["visual_opportunities"][0]["mode"] == "captions"
    assert captured["max_tokens"] >= 8192
