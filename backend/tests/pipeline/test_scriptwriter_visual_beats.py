"""Tests for scriptwriter visual beat post-processing."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from models.script import Scene, ScriptContent, Segment
from pipeline.formats.base import VisualBeatRules
from pipeline.formats.life_as_a import LIFE_AS_A_BEAT_RULES
from pipeline.scriptwriter import _ensure_visual_beat_directives, _fix_visual_monotony
from prompts import script as script_prompt


def _static_scene(scene_id: str) -> Scene:
    return Scene(
        id=scene_id,
        narration="You wait through another identical hour.",
        visual_prompt="[ESTABLISHING] A quiet institutional hallway under flat lights.",
        visual_beat="static",
        frame_directives=[
            {
                "prompt": "[ESTABLISHING] A quiet institutional hallway under flat lights.",
                "source": "ai_generated",
                "transition": "cut",
                "reference_previous": False,
                "search_query": "",
                "contains_person": False,
            }
        ],
    )


def test_life_as_a_monotony_fix_creates_multi_frame_directives():
    content = ScriptContent(
        title="Your Life As A Test",
        format_id="life-as-a",
        segments=[
            Segment(
                name="Level 1, the waiting",
                scenes=[_static_scene(f"scene_{i:03d}") for i in range(1, 7)],
            ),
        ],
    )

    fixes = _fix_visual_monotony(content, LIFE_AS_A_BEAT_RULES)

    changed = [scene for scene in content.all_scenes() if scene.visual_beat != "static"]
    assert fixes > 0
    assert changed
    assert all(len(scene.frame_directives) > 1 for scene in changed)


def test_monotony_fix_normalizes_legacy_alternatives_to_multi_frame():
    content = ScriptContent(
        title="Your Life As A Test",
        format_id="youtube-listicle",
        segments=[
            Segment(
                name="Segment 1",
                scenes=[_static_scene(f"scene_{i:03d}") for i in range(1, 5)],
            ),
        ],
    )
    rules = VisualBeatRules(
        allowed_beats=frozenset({"static", "quick_cuts", "montage"}),
        monotony_threshold=3,
    )

    _fix_visual_monotony(content, rules)

    beats = [scene.visual_beat for scene in content.all_scenes()]
    assert "quick_cuts" not in beats
    assert "montage" not in beats
    assert "multi_frame" in beats


def test_non_static_beats_without_directives_are_repaired():
    scene = _static_scene("scene_001")
    scene.visual_beat = "continuous"
    scene.frame_directives = []
    scene.duration_estimate_seconds = 10.0
    content = ScriptContent(
        title="Your Life As A Test",
        format_id="life-as-a",
        segments=[Segment(name="Level 1, the waiting", scenes=[scene])],
    )

    _ensure_visual_beat_directives(content)

    assert len(scene.frame_directives) == 3
    assert scene.frame_directives[1].reference_previous is True


def test_script_prompt_no_longer_requests_quick_cuts_or_montage():
    prompt_text = script_prompt.SCRIPT_SYSTEM.template

    assert '"quick_cuts"' not in prompt_text
    assert '"montage"' not in prompt_text
    assert '"multi_frame"' in prompt_text


def test_script_prompt_includes_captions_mode_without_extra_renderer_detail():
    prompt_text = script_prompt.SCRIPT_SYSTEM.template

    assert '"captions"' in prompt_text
    assert "caption_text" in prompt_text
    assert "caption_emphasis" in prompt_text
    assert "renderer handles" in prompt_text
    assert "Do not put readable caption text into visual_prompt" in prompt_text


def test_multi_frame_mode_without_directives_is_repaired():
    scene = _static_scene("scene_001")
    scene.visual_mode = "multi_frame"
    scene.visual_beat = "multi_frame"
    scene.frame_directives = []
    content = ScriptContent(
        title="Your Life As A Test",
        format_id="life-as-a",
        segments=[Segment(name="Level 1, the waiting", scenes=[scene])],
    )

    _ensure_visual_beat_directives(content)

    assert scene.visual_mode == "multi_frame"
    assert len(scene.frame_directives) == 4
    assert all(frame.reference_previous is False for frame in scene.frame_directives)
    assert all(frame.transition == "cut" for frame in scene.frame_directives)


def test_continuous_mode_without_directives_is_repaired():
    scene = _static_scene("scene_001")
    scene.visual_mode = "continuous"
    scene.visual_beat = "continuous"
    scene.frame_directives = []
    content = ScriptContent(
        title="Your Life As A Test",
        format_id="life-as-a",
        segments=[Segment(name="Level 1, the waiting", scenes=[scene])],
    )

    _ensure_visual_beat_directives(content)

    assert scene.visual_mode == "continuous"
    assert len(scene.frame_directives) == 3
    assert scene.frame_directives[0].reference_previous is False
    assert all(frame.reference_previous is True for frame in scene.frame_directives[1:])
    assert all(frame.transition == "crossfade" for frame in scene.frame_directives[1:])


def test_aha_subtitle_mode_with_stale_beat_is_repaired():
    scene = _static_scene("scene_001")
    content = ScriptContent(
        title="Your Life As A Test",
        format_id="youtube-listicle",
        segments=[Segment(name="Level 1, the waiting", scenes=[scene])],
    )
    scene = content.segments[0].scenes[0]
    object.__setattr__(scene, "visual_mode", "aha_subtitle")
    object.__setattr__(scene, "visual_beat", "static")
    object.__setattr__(scene, "frame_directives", [])

    _ensure_visual_beat_directives(content)

    assert scene.visual_mode == "aha_subtitle"
    assert len(scene.frame_directives) == 1
    assert scene.frame_directives[0].source == "subtitle"
    assert scene.frame_directives[0].prompt == scene.narration
    assert scene.frame_directives[0].contains_person is False
