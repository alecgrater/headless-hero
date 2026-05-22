"""Tests for scriptwriter visual beat post-processing."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from models.script import Scene, ScriptContent, Segment
from pipeline.formats.life_as_a import LIFE_AS_A_BEAT_RULES
from pipeline.scriptwriter import _ensure_visual_beat_directives, _fix_visual_monotony


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


def test_non_static_beats_without_directives_are_repaired():
    scene = _static_scene("scene_001")
    scene.visual_beat = "continuous"
    scene.frame_directives = []
    content = ScriptContent(
        title="Your Life As A Test",
        format_id="life-as-a",
        segments=[Segment(name="Level 1, the waiting", scenes=[scene])],
    )

    _ensure_visual_beat_directives(content)

    assert len(scene.frame_directives) == 3
    assert scene.frame_directives[1].reference_previous is True
