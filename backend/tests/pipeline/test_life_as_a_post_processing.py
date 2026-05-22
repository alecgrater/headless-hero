"""Tests for the life-as-a format post-processor."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from models.script import LevelMeta, Scene, ScriptContent, Segment
from pipeline.formats.life_as_a import enforce_life_as_a_constraints


def _scene(scene_id: str, beat: str = "static", title_card: bool = False) -> Scene:
    return Scene(
        id=scene_id,
        narration="x",
        visual_prompt="[ESTABLISHING] x",
        visual_beat=beat,
        is_title_card=title_card,
    )


def test_disallowed_beats_coerced_to_static():
    content = ScriptContent(
        title="Your Life As A Test",
        format_id="life-as-a",
        segments=[
            Segment(name="Level 1, the entry", scenes=[
                _scene("s1", beat="aha_subtitle"),
                _scene("s2", beat="montage"),
                _scene("s3", beat="continuous"),
            ]),
        ],
    )
    out = enforce_life_as_a_constraints(content)
    beats = [s.visual_beat for s in out.all_scenes() if not s.is_title_card]
    assert "aha_subtitle" not in beats
    assert "montage" not in beats
    assert "continuous" in beats


def test_chapter_card_inserted_when_missing():
    content = ScriptContent(
        title="Your Life As A Test",
        format_id="life-as-a",
        segments=[
            Segment(name="Level 1, the entry", title_card_image_prompt="a door", scenes=[
                _scene("s1"),
            ]),
        ],
    )
    out = enforce_life_as_a_constraints(content)
    assert out.segments[0].scenes[0].is_title_card is True
    assert out.segments[0].scenes[0].id == "chapter_01"


def test_levels_synthesized_when_missing():
    content = ScriptContent(
        title="Your Life As A Test",
        format_id="life-as-a",
        segments=[
            Segment(name="Level 1", short_name="entry", title_card_image_prompt="a door", scenes=[
                _scene("s1", title_card=True),
            ]),
        ],
    )
    out = enforce_life_as_a_constraints(content)
    assert out.levels is not None
    assert out.levels[0].number == 1
    assert out.levels[0].descriptor == "entry"


def test_existing_levels_preserved():
    levels = [LevelMeta(number=1, descriptor="naive", image_prompt="x")]
    content = ScriptContent(
        title="Your Life As A Test",
        format_id="life-as-a",
        levels=levels,
        segments=[
            Segment(name="Level 1, the naive", scenes=[_scene("s1", title_card=True)]),
        ],
    )
    out = enforce_life_as_a_constraints(content)
    assert out.levels[0].descriptor == "naive"


def test_life_as_a_marks_role_scenes_as_eli_protagonist():
    content = ScriptContent(
        title="Your Life As A Prison Guard",
        format_id="life-as-a",
        segments=[
            Segment(name="Level 1, the entry", scenes=[
                Scene(
                    id="s1",
                    narration="You walk the corridor before dawn.",
                    visual_prompt="[ESTABLISHING] A prison guard walking down a narrow corridor",
                    frame_directives=[
                        {
                            "prompt": "[ESTABLISHING] A prison guard walking down a narrow corridor",
                            "source": "ai_generated",
                            "transition": "cut",
                            "reference_previous": False,
                            "search_query": "",
                            "contains_person": False,
                        }
                    ],
                ),
            ]),
        ],
    )

    out = enforce_life_as_a_constraints(content)
    scene = out.segments[0].scenes[1]

    assert scene.contains_person is True
    assert scene.visual_prompt.startswith("[ESTABLISHING] Eli, the recurring character")
    assert "Depict Eli as Prison Guard" in scene.visual_prompt
    assert scene.frame_directives[0].contains_person is True
    assert scene.frame_directives[0].prompt.startswith("[ESTABLISHING] Eli, the recurring character")


def test_life_as_a_leaves_non_person_object_scenes_unmarked():
    content = ScriptContent(
        title="Your Life As A Prison Guard",
        format_id="life-as-a",
        segments=[
            Segment(name="Level 1, the entry", scenes=[
                Scene(
                    id="s1",
                    narration="The keys sit on the metal desk.",
                    visual_prompt="[CLOSE-UP] A ring of keys on a dented metal desk",
                ),
            ]),
        ],
    )

    out = enforce_life_as_a_constraints(content)
    scene = out.segments[0].scenes[1]

    assert scene.contains_person is False
    assert not scene.visual_prompt.startswith("Eli, the recurring character")


def test_life_as_a_role_adjective_does_not_mark_object_scene():
    content = ScriptContent(
        title="Your Life As A Prison Guard",
        format_id="life-as-a",
        segments=[
            Segment(name="Level 1, the entry", scenes=[
                Scene(
                    id="s1",
                    narration="The corridor is empty before the shift starts.",
                    visual_prompt="[ESTABLISHING] An empty prison corridor before dawn",
                ),
            ]),
        ],
    )

    out = enforce_life_as_a_constraints(content)
    scene = out.segments[0].scenes[1]

    assert scene.contains_person is False
    assert scene.visual_prompt == "[ESTABLISHING] An empty prison corridor before dawn"


def test_life_as_a_unknown_role_head_noun_marks_protagonist_scene():
    content = ScriptContent(
        title="Your Life As A Medieval Knight",
        format_id="life-as-a",
        segments=[
            Segment(name="Level 1, the entry", scenes=[
                Scene(
                    id="s1",
                    narration="You stand outside the hall before sunrise.",
                    visual_prompt="[REACTION] A knight holding a dented helmet in both hands",
                ),
            ]),
        ],
    )

    out = enforce_life_as_a_constraints(content)
    scene = out.segments[0].scenes[1]

    assert scene.contains_person is True
    assert scene.visual_prompt.startswith("[REACTION] Eli, the recurring character")
    assert "Depict Eli as Medieval Knight" in scene.visual_prompt
