"""Pins the script-quality fixes measured in the 2026-09-30 script investigation.

Each fix here moved a judged score or removed a crash in a side-by-side run; the
wording is measured, not stylistic. See CLAUDE.md "Script generation" before
rewording any of it.
"""

import json

import pytest

from models.script import Scene
from pipeline import scriptwriter
from pipeline.formats import get_format
from prompts import (
    COLD_OPEN_ADDENDUM,
    LIFE_AS_A_LEVEL_SCENES_INSTRUCTIONS,
    LIFE_AS_A_OUTLINE_INSTRUCTIONS,
    LIFE_AS_A_SCRIPT_SYSTEM,
    SCRIPT_OUTLINE_INSTRUCTIONS,
    SCRIPT_SEGMENT_SCENES_INSTRUCTIONS,
    SCRIPT_SYSTEM,
)


@pytest.fixture
def isolated_progress(tmp_path, monkeypatch):
    monkeypatch.setattr(scriptwriter, "_PROGRESS_DIR", tmp_path / "script-progress")


# ------------------------------------------------------------------ crashes

def test_list_valued_caption_fields_take_the_first_phrase():
    # Sonnet 5.5 returned caption_emphasis as a list, which failed validation for the
    # whole life-as-a level in 3 of 4 measured runs.
    scene = Scene.model_validate({
        "id": "s", "narration": "Nobody will ever learn your name.", "visual_prompt": "",
        "visual_mode": "captions", "caption_text": "Nobody will ever learn your name",
        "caption_emphasis": ["ever", "your name"],
    })
    assert scene.caption_emphasis == "ever"
    assert Scene.model_validate({"id": "s", "narration": "x", "visual_prompt": "",
                                 "caption_emphasis": None}).caption_emphasis == ""


def test_outline_budget_leaves_room_for_adaptive_thinking():
    # Thinking shares max_tokens; at 8192 every Sonnet 5.5 outline was truncated.
    assert scriptwriter._OUTLINE_MAX_TOKENS >= 32000


# ------------------------------------------------------------------ continuity between segment calls

def _outline(n: int) -> dict:
    return {"title": "T", "segments": [{"name": f"Level {i + 1}", "topic_summary": "x"} for i in range(n)]}


def _scenes(*texts: str) -> str:
    return json.dumps({"scenes": [
        {"id": "t", "narration": "The descriptor.", "visual_prompt": "", "is_title_card": True},
        *({"id": "s", "narration": t, "visual_prompt": "[CLOSE-UP] x"} for t in texts),
    ]})


def _run(monkeypatch, *, stand_alone: bool, cold_open: str | None = None) -> list[str]:
    monkeypatch.setattr(scriptwriter, "_generate_outline", lambda *a, **k: _outline(3))
    replies = [_scenes("Walter hands you the matches."), _scenes("Walter's hip is worse."), _scenes("Spring.")]
    users: list[str] = []

    def fake_chat(system, user, **kwargs):
        users.append(user)
        return replies[len(users) - 1]

    monkeypatch.setattr(scriptwriter, "chat", fake_chat)
    scriptwriter._generate_segmented("sys", "user", "topic", "", "", None, level_label="level",
                                     segments_stand_alone=stand_alone, cold_open_text=cold_open)
    return users


def test_later_segment_calls_see_the_narration_already_written(isolated_progress, monkeypatch):
    users = _run(monkeypatch, stand_alone=False)

    assert "STORY SO FAR" not in users[0]
    assert "Walter hands you the matches." in users[1]
    assert "Walter hands you the matches." in users[2] and "Walter's hip is worse." in users[2]
    assert "The descriptor." not in users[2], "chapter cards are not story"
    assert "do not re-introduce anyone already introduced" in users[1]
    assert "stand alone as a Short" not in users[1]


def test_standalone_formats_are_told_not_to_refer_back(isolated_progress, monkeypatch):
    users = _run(monkeypatch, stand_alone=True)
    assert "must still stand alone as a Short" in users[1]


def test_listicle_segments_stand_alone_and_life_as_a_levels_do_not():
    assert get_format("youtube-listicle").segments_stand_alone is True
    assert get_format("life-as-a").segments_stand_alone is False


def test_first_segment_continues_from_the_cold_open_instead_of_retelling_it(isolated_progress, monkeypatch):
    users = _run(monkeypatch, stand_alone=True, cold_open="Hook. Opening.")
    assert "Hook. Opening." in users[0]
    assert scriptwriter._OPENING_CONTINUATION_RULE in users[0]
    assert scriptwriter._OPENING_CONTINUATION_RULE not in users[1]


# ------------------------------------------------------------------ prompt wording

def test_outlines_fix_characters_and_claims_before_scenes_are_written():
    assert '"story_bible"' in LIFE_AS_A_OUTLINE_INSTRUCTIONS.template
    assert "introduced_in_level" in LIFE_AS_A_OUTLINE_INSTRUCTIONS.template
    assert "Follow the story_bible" in LIFE_AS_A_LEVEL_SCENES_INSTRUCTIONS.template
    assert '"segment_plan"' in SCRIPT_OUTLINE_INSTRUCTIONS.template
    assert "Follow the segment_plan" in SCRIPT_SEGMENT_SCENES_INSTRUCTIONS.template


def test_both_formats_carry_the_flow_and_clarity_rules():
    for prompt in (SCRIPT_SYSTEM, LIFE_AS_A_SCRIPT_SYSTEM):
        text = prompt.template
        assert "## FLOW AND CLARITY" in text
        assert "Never refer to someone or something the listener has not met yet" in text
        assert "Never describe the image, the shot, or the camera in narration" in text
        assert "Do not narrate the protagonist or main character by name" in text
    assert "introduced once, the first time they appear" in LIFE_AS_A_SCRIPT_SYSTEM.template


def test_listicle_no_longer_asks_for_hooks_across_segments():
    # "cliffhangers between segments" and cross-segment callbacks produced a tease at
    # the end of segment 1 and a whole-video recap in the final segment.
    text = SCRIPT_SYSTEM.template
    assert "cliffhangers between segments" not in text
    assert "Think of the script as a braid" not in text
    assert "Remember that cereal aisle?" not in text
    assert "Never call back to an earlier segment" in text


def test_listicle_cold_open_sets_up_the_first_story_without_resolving_it():
    text = COLD_OPEN_ADDENDUM.template
    assert "do not reveal how it ends" in text
    assert 'never "the first of eight times"' in text


def test_life_as_a_does_not_tell_eli_off_scripts_to_draw_eli():
    for prompt in (LIFE_AS_A_SCRIPT_SYSTEM, LIFE_AS_A_LEVEL_SCENES_INSTRUCTIONS):
        assert "make Eli the visually dominant" not in prompt.template
        assert "MUST be Eli in that role" not in prompt.template


def test_main_character_block_asks_for_a_placeholder_not_a_face():
    text = scriptwriter.build_main_character_instructions()
    assert "Never use it in narration" in text
    assert "detailed visual description (face, hair, build" not in text
    addendum = scriptwriter.build_outline_main_character_addendum()
    assert "never in narration" in addendum
