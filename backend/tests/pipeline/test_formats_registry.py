"""Tests for the format registry resolution + defensive fallback."""

import logging
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from pipeline.formats import (
    DEFAULT_FORMAT_ID,
    get_format,
    list_formats,
    resolve_format,
)


def test_default_format_resolves():
    fmt = resolve_format(None)
    assert fmt.id == DEFAULT_FORMAT_ID


def test_resolve_format_falls_back_for_unknown(caplog):
    with caplog.at_level(logging.WARNING):
        fmt = resolve_format("does-not-exist")
    assert fmt.id == DEFAULT_FORMAT_ID
    assert any("does-not-exist" in r.message for r in caplog.records)


def test_get_format_raises_for_unknown():
    with pytest.raises(KeyError):
        get_format("does-not-exist")


def test_list_formats_returns_registered_formats():
    formats = list_formats()
    ids = [f.id for f in formats]
    assert "youtube-listicle" in ids
    assert "life-as-a" in ids


def test_youtube_listicle_flags():
    fmt = get_format("youtube-listicle")
    assert fmt.supports_cold_open is True
    assert fmt.supports_hook_scoring is True
    assert fmt.title_card_strategy.kind == "composite-grid"
    assert fmt.level_label == "segment"


def test_life_as_a_flags():
    fmt = get_format("life-as-a")
    assert fmt.supports_cold_open is False
    assert fmt.supports_hook_scoring is False
    assert fmt.supports_segmented_generation is True
    assert fmt.title_card_strategy.kind == "cinematic-chapters"
    assert fmt.level_label == "level"
    assert fmt.visual_beat_rules.monotony_threshold == 3
    assert fmt.visual_beat_rules.target_distribution["static"] == (0.45, 0.60)
    assert fmt.visual_beat_rules.target_distribution["quick_cuts"] == (0.15, 0.25)


def test_generate_script_dispatches_to_format(monkeypatch):
    """Smoke test: generate_script() routes to the right system prompt per format."""
    import json

    from pipeline import scriptwriter

    captured = {}

    def fake_chat(system: str, user: str, **kwargs):
        captured["system"] = system
        captured["user"] = user
        return json.dumps({
            "title": "Your Life As A Test",
            "segments": [{"name": "Level 1, the entry", "scenes": [
                {"id": "s1", "narration": "you walk in", "visual_prompt": "[ESTABLISHING] door"}
            ]}],
            "intro_hook": "",
            "outro_cta": "",
            "card_title": "TEST",
            "card_title_highlight_word": "TEST",
            "card_subtitle": "",
            "format_id": "life-as-a",
            "levels": [{"number": 1, "descriptor": "entry"}],
            "cinematic_thumbnail_prompt": "a door at dawn",
        })

    monkeypatch.setattr(scriptwriter, "chat", fake_chat)
    content = scriptwriter.generate_script(
        topic="Your Life As A Test",
        format_id="life-as-a",
        segmented=False,
    )
    assert content.format_id == "life-as-a"
    assert "Level" in captured["user"] or "level" in captured["user"]


def test_segmented_life_as_a_preserves_outline_fields(monkeypatch):
    """Segmented life-as-a generation must forward cinematic_thumbnail_prompt and levels[] from the outline."""
    import json

    from pipeline import scriptwriter

    outline_json = json.dumps({
        "title": "Your Life As A Test",
        "intro_hook": "",
        "outro_cta": "",
        "card_title": "TEST",
        "card_title_highlight_word": "TEST",
        "card_subtitle": "",
        "cinematic_thumbnail_prompt": "a door at dawn",
        "levels": [
            {"number": 1, "descriptor": "entry"},
            {"number": 2, "descriptor": "drift", "image_prompt": "a hallway"},
        ],
        "segments": [
            {"name": "Level 1, the entry", "topic_summary": "you arrive"},
            {"name": "Level 2, the drift", "topic_summary": "things shift"},
        ],
    })
    scene_json = json.dumps({"scenes": [
        {"id": "s1", "narration": "you walk in", "visual_prompt": "[ESTABLISHING] door"}
    ]})

    call_index = {"n": 0}

    def fake_chat(system: str, user: str, **kwargs):
        idx = call_index["n"]
        call_index["n"] += 1
        # First call = outline, subsequent = per-segment scenes
        return outline_json if idx == 0 else scene_json

    monkeypatch.setattr(scriptwriter, "chat", fake_chat)

    content = scriptwriter.generate_script(
        topic="Your Life As A Test",
        format_id="life-as-a",
        segmented=True,
    )

    assert content.format_id == "life-as-a"
    assert content.cinematic_thumbnail_prompt == "a door at dawn"
    assert content.levels is not None
    assert len(content.levels) == 2
    assert content.levels[0].descriptor == "entry"
    assert content.levels[0].image_prompt == ""  # Level 1's chapter image comes from cinematic_thumbnail_prompt.
    assert content.levels[1].descriptor == "drift"
    assert content.levels[1].image_prompt == "a hallway"


def test_enforce_life_as_a_falls_back_to_cinematic_prompt_for_level_1():
    """When levels[0].image_prompt is empty, the level-1 chapter scene should
    use cinematic_thumbnail_prompt as its visual_prompt fallback."""
    from models.script import LevelMeta, Scene, ScriptContent, Segment
    from pipeline.formats.life_as_a import enforce_life_as_a_constraints

    content = ScriptContent(
        title="Your Life As A Test",
        format_id="life-as-a",
        cinematic_thumbnail_prompt="a door at dawn",
        levels=[
            LevelMeta(number=1, descriptor="entry", image_prompt=""),
            LevelMeta(number=2, descriptor="drift", image_prompt="a hallway"),
        ],
        segments=[
            Segment(name="Level 1, the entry", scenes=[
                Scene(id="s1", narration="walking", visual_prompt="[ESTABLISHING] something",
                      duration_estimate_seconds=10, is_title_card=False),
            ]),
            Segment(name="Level 2, the drift", scenes=[
                Scene(id="s2", narration="drifting", visual_prompt="[ESTABLISHING] something",
                      duration_estimate_seconds=10, is_title_card=False),
            ]),
        ],
    )

    enforce_life_as_a_constraints(content)

    # Level 1 chapter card scene was inserted at index 0 of segment 0
    level_1_chapter = content.segments[0].scenes[0]
    assert level_1_chapter.is_title_card is True
    assert "a door at dawn" in level_1_chapter.visual_prompt

    # Level 2 chapter card uses its own image_prompt
    level_2_chapter = content.segments[1].scenes[0]
    assert level_2_chapter.is_title_card is True
    assert "a hallway" in level_2_chapter.visual_prompt
