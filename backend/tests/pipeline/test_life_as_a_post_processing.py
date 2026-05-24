"""Tests for the life-as-a format post-processor."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from models.script import FrameDirective, LevelMeta, MainCharacter, Scene, ScriptContent, Segment
from pipeline.formats.life_as_a import enforce_life_as_a_constraints
from pipeline.scriptwriter import _ensure_visual_beat_directives


def _scene(
    scene_id: str,
    beat: str = "static",
    title_card: bool = False,
    duration_estimate_seconds: float = 8.0,
) -> Scene:
    return Scene(
        id=scene_id,
        narration="x",
        visual_prompt="[ESTABLISHING] x",
        visual_beat=beat,
        is_title_card=title_card,
        duration_estimate_seconds=duration_estimate_seconds,
    )


def test_disallowed_and_legacy_beats_normalized():
    content = ScriptContent(
        title="Your Life As A Test",
        format_id="life-as-a",
        segments=[
            Segment(name="Level 1, the entry", scenes=[
                _scene("s1", beat="aha_subtitle"),
                _scene("s2", beat="montage"),
                _scene("s3", beat="continuous", duration_estimate_seconds=10.0),
            ]),
        ],
    )
    out = enforce_life_as_a_constraints(content)
    beats = [s.visual_beat for s in out.all_scenes() if not s.is_title_card]
    assert "aha_subtitle" not in beats
    assert "static" in beats
    assert "montage" not in beats
    assert "multi_frame" in beats
    assert "continuous" in beats


def test_life_as_a_preserves_canonical_multi_frame_through_directive_repair():
    scene = _scene("s2", beat="multi_frame")
    scene.frame_directives = []
    content = ScriptContent(
        title="Your Life As A Test",
        format_id="life-as-a",
        segments=[
            Segment(name="Level 1, the entry", scenes=[
                _scene("s1", title_card=True),
                scene,
            ]),
        ],
    )

    enforce_life_as_a_constraints(content)
    _ensure_visual_beat_directives(content)

    repaired = content.segments[0].scenes[1]
    assert repaired.visual_mode == "multi_frame"
    assert repaired.visual_beat == "multi_frame"
    assert len(repaired.frame_directives) == 4
    assert all(frame.reference_previous is False for frame in repaired.frame_directives)


def test_life_as_a_coerces_aha_subtitle_visual_mode_to_static():
    scene = _scene("s2", beat="static")
    object.__setattr__(scene, "visual_mode", "aha_subtitle")
    object.__setattr__(
        scene,
        "frame_directives",
        [
            FrameDirective(
                prompt="A hard truth.",
                source="subtitle",
                transition="cut",
                reference_previous=False,
                search_query="",
                contains_person=False,
            )
        ],
    )
    content = ScriptContent(
        title="Your Life As A Test",
        format_id="life-as-a",
        segments=[
            Segment(name="Level 1, the entry", scenes=[
                _scene("s1", title_card=True),
                scene,
            ]),
        ],
    )
    scene = content.segments[0].scenes[1]
    object.__setattr__(scene, "visual_mode", "aha_subtitle")

    enforce_life_as_a_constraints(content)

    coerced = content.segments[0].scenes[1]
    assert coerced.visual_mode == "full_frame"
    assert coerced.visual_beat == "static"
    assert all(frame.source != "subtitle" for frame in coerced.frame_directives)


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
    assert out.segments[0].scenes[0].id == "scene_001"
    assert out.segments[0].scenes[0].narration == "The entry."


def test_existing_chapter_card_narration_normalized_to_descriptor():
    content = ScriptContent(
        title="Your Life As A Test",
        format_id="life-as-a",
        levels=[LevelMeta(number=1, descriptor="entry")],
        segments=[
            Segment(name="Level 1, the entry", scenes=[
                _scene("s1", title_card=True),
                _scene("s2"),
            ]),
        ],
    )
    content.segments[0].scenes[0].narration = "Level 1, the entry."

    out = enforce_life_as_a_constraints(content)

    assert out.segments[0].scenes[0].narration == "The entry."


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


def test_life_as_a_eli_disabled_marks_role_scenes_as_main_character():
    content = ScriptContent(
        title="Your Life As A Prison Guard",
        format_id="life-as-a",
        main_character=MainCharacter(
            name="Darnell",
            appearance="Black male guard with close-cropped hair and a navy uniform",
            vibe="Steady and observant.",
        ),
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

    out = enforce_life_as_a_constraints(content, eli_enabled=False)
    scene = out.segments[0].scenes[1]

    assert scene.contains_person is True
    assert scene.visual_prompt.startswith("[ESTABLISHING] Darnell is the main subject")
    assert "Depict Darnell as Prison Guard" in scene.visual_prompt
    assert "Eli" not in scene.visual_prompt
    assert scene.frame_directives[0].contains_person is True
    assert scene.frame_directives[0].prompt.startswith("[ESTABLISHING] Darnell is the main subject")
    assert "Eli" not in scene.frame_directives[0].prompt


def test_life_as_a_eli_disabled_replaces_existing_eli_prompt_without_duplication():
    content = ScriptContent(
        title="Your Life As A Prison Guard",
        format_id="life-as-a",
        main_character=MainCharacter(
            name="Darnell",
            appearance="Black male guard with close-cropped hair and a navy uniform",
            vibe="Steady and observant.",
        ),
        segments=[
            Segment(name="Level 1, the entry", scenes=[
                Scene(
                    id="s1",
                    narration="You stand at the entry door.",
                    visual_prompt=(
                        "[REACTION] Eli, the recurring character, is the main subject and protagonist in this scene. "
                        "Depict Eli as Prison Guard; any other people are secondary and visually distinct from Eli. "
                        "A guard standing at a heavy steel door"
                    ),
                ),
            ]),
        ],
    )

    out = enforce_life_as_a_constraints(content, eli_enabled=False)
    scene = out.segments[0].scenes[1]

    assert scene.visual_prompt.startswith("[REACTION] Darnell is the main subject")
    assert scene.visual_prompt.count("Darnell is the main subject") == 1
    assert "A guard standing at a heavy steel door" in scene.visual_prompt
    assert "Eli" not in scene.visual_prompt


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


def test_life_as_a_splits_overlong_scene_into_short_static_chunks(monkeypatch):
    monkeypatch.setenv("LIFE_AS_A_SCENE_CHUNKING_ENABLED", "true")
    monkeypatch.setenv("LIFE_AS_A_TARGET_SCENE_SECONDS", "8")
    monkeypatch.setenv("LIFE_AS_A_MAX_SCENE_SECONDS", "12")
    monkeypatch.setenv("LIFE_AS_A_SINGLE_VISUAL_MAX_SECONDS", "8")
    content = ScriptContent(
        title="Your Life As A Prison Guard",
        format_id="life-as-a",
        segments=[
            Segment(name="Level 1, the entry", scenes=[
                Scene(
                    id="s1",
                    narration=(
                        "You sign the clipboard before sunrise. "
                        "The keys feel heavier than you expected. "
                        "A senior guard points without looking up. "
                        "You learn which doors make the loudest sound. "
                        "By lunch, the hallway already feels familiar."
                    ),
                    visual_prompt="[ESTABLISHING] A prison guard entering a corridor before sunrise",
                    duration_estimate_seconds=40.0,
                    visual_beat="quick_cuts",
                    contains_person=True,
                    frame_directives=[
                        {
                            "prompt": "[ESTABLISHING] A prison guard entering a corridor before sunrise",
                            "source": "ai_generated",
                            "transition": "cut",
                            "reference_previous": False,
                            "search_query": "",
                            "contains_person": True,
                        },
                        {
                            "prompt": "[CLOSE-UP] A key ring in a hand",
                            "source": "ai_generated",
                            "transition": "cut",
                            "reference_previous": False,
                            "search_query": "",
                            "contains_person": True,
                        },
                    ],
                ),
            ]),
        ],
    )

    out = enforce_life_as_a_constraints(content)
    scenes = out.segments[0].scenes

    assert scenes[0].is_title_card is True
    assert [scene.id for scene in scenes] == [
        "scene_001",
        "scene_002",
        "scene_003",
        "scene_004",
        "scene_005",
        "scene_006",
    ]
    split_scenes = scenes[1:]
    assert [scene.narration for scene in split_scenes] == [
        "You sign the clipboard before sunrise.",
        "The keys feel heavier than you expected.",
        "A senior guard points without looking up.",
        "You learn which doors make the loudest sound.",
        "By lunch, the hallway already feels familiar.",
    ]
    assert all(scene.visual_beat == "static" for scene in split_scenes)
    assert all(len(scene.frame_directives) == 1 for scene in split_scenes)
    assert all(scene.media_source == "ai" for scene in split_scenes)


def test_life_as_a_chapter_card_is_not_split(monkeypatch):
    monkeypatch.setenv("LIFE_AS_A_SCENE_CHUNKING_ENABLED", "true")
    content = ScriptContent(
        title="Your Life As A Prison Guard",
        format_id="life-as-a",
        segments=[
            Segment(name="Level 1, the entry", scenes=[
                Scene(
                    id="chapter",
                    narration=(
                        "The entry. The keys. The corridor. The first hour. "
                        "The first mistake. The locked door."
                    ),
                    visual_prompt="[ESTABLISHING] A heavy prison door",
                    duration_estimate_seconds=40.0,
                    is_title_card=True,
                ),
                _scene("s1"),
            ]),
        ],
    )

    out = enforce_life_as_a_constraints(content)

    assert len(out.segments[0].scenes) == 2
    assert out.segments[0].scenes[0].is_title_card is True
    assert out.segments[0].scenes[0].narration == "The entry."


def test_life_as_a_short_scene_preserves_multi_frame_directives(monkeypatch):
    monkeypatch.setenv("LIFE_AS_A_SINGLE_VISUAL_MAX_SECONDS", "8")
    content = ScriptContent(
        title="Your Life As A Prison Guard",
        format_id="life-as-a",
        segments=[
            Segment(name="Level 1, the entry", scenes=[
                Scene(
                    id="s1",
                    narration="You hear the lock click.",
                    visual_prompt="[CLOSE-UP] A guard listening to a lock click",
                    duration_estimate_seconds=6.0,
                    visual_beat="continuous",
                    contains_person=True,
                    frame_directives=[
                        {
                            "prompt": "[CLOSE-UP] A guard listening to a lock click",
                            "source": "ai_generated",
                            "transition": "crossfade",
                            "reference_previous": True,
                            "search_query": "",
                            "contains_person": True,
                        },
                        {
                            "prompt": "[REACTION] A guard turning toward the door",
                            "source": "ai_generated",
                            "transition": "crossfade",
                            "reference_previous": True,
                            "search_query": "",
                            "contains_person": True,
                        },
                    ],
                ),
            ]),
        ],
    )

    out = enforce_life_as_a_constraints(content)
    scene = out.segments[0].scenes[1]

    assert scene.visual_beat == "continuous"
    assert len(scene.frame_directives) == 2
    assert [frame.transition for frame in scene.frame_directives] == ["crossfade", "crossfade"]
    assert [frame.reference_previous for frame in scene.frame_directives] == [True, True]


def test_life_as_a_sentence_count_splits_when_default_duration_masks_long_scene(monkeypatch):
    monkeypatch.setenv("LIFE_AS_A_TARGET_SCENE_SECONDS", "8")
    monkeypatch.setenv("LIFE_AS_A_MAX_SCENE_SECONDS", "12")
    content = ScriptContent(
        title="Your Life As A Prison Guard",
        format_id="life-as-a",
        segments=[
            Segment(name="Level 1, the entry", scenes=[
                Scene(
                    id="s1",
                    narration=(
                        "You wake before the alarm. "
                        "The uniform waits on the chair. "
                        "The shoes still hurt. "
                        "The radio keeps hissing."
                    ),
                    visual_prompt="[ESTABLISHING] A guard uniform on a chair",
                ),
            ]),
        ],
    )

    out = enforce_life_as_a_constraints(content)

    assert len(out.segments[0].scenes) == 5


def test_life_as_a_split_scenes_preserve_segment_order(monkeypatch):
    monkeypatch.setenv("LIFE_AS_A_TARGET_SCENE_SECONDS", "8")
    monkeypatch.setenv("LIFE_AS_A_MAX_SCENE_SECONDS", "12")
    content = ScriptContent(
        title="Your Life As A Prison Guard",
        format_id="life-as-a",
        segments=[
            Segment(name="Level 1, the entry", scenes=[
                Scene(
                    id="a",
                    narration="You arrive early. You check the door. You touch the cold key.",
                    visual_prompt="[CLOSE-UP] A cold key",
                    duration_estimate_seconds=24.0,
                ),
            ]),
            Segment(name="Level 2, the routine", scenes=[
                Scene(
                    id="b",
                    narration="You know the hallway. You know the voices. You know the silences.",
                    visual_prompt="[ESTABLISHING] A prison hallway",
                    duration_estimate_seconds=24.0,
                ),
            ]),
        ],
    )

    out = enforce_life_as_a_constraints(content)

    assert [segment.name for segment in out.segments] == ["Level 1, the entry", "Level 2, the routine"]
    assert [scene.narration for scene in out.segments[0].scenes[1:]] == [
        "You arrive early.",
        "You check the door.",
        "You touch the cold key.",
    ]
    assert [scene.narration for scene in out.segments[1].scenes[1:]] == [
        "You know the hallway.",
        "You know the voices.",
        "You know the silences.",
    ]
