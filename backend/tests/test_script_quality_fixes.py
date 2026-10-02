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
    stat = Scene.model_validate({"id": "s", "narration": "85 percent quit.", "visual_prompt": "",
                                 "visual_mode": "stat_card", "stat_value": 85})
    assert stat.stat_value == "85"


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
    scriptwriter._PROGRESS_DIR.mkdir(parents=True, exist_ok=True)
    for stale in scriptwriter._PROGRESS_DIR.glob("*.json"):
        stale.unlink()  # each run starts fresh rather than resuming the previous one
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


def test_standalone_formats_re_introduce_instead_of_referring_back(isolated_progress, monkeypatch):
    # The listicle prompts require re-introducing people in every segment; telling
    # stand-alone segments "do not re-introduce" would contradict them.
    users = _run(monkeypatch, stand_alone=True)
    assert "must stand alone as a Short" in users[1]
    assert "re-introduce briefly anyone" in users[1]
    assert "do not re-introduce" not in users[1]


def test_local_engines_see_only_the_most_recent_sections(isolated_progress, monkeypatch):
    # A local model shares a 16k context between prompt and reply.
    monkeypatch.setattr(scriptwriter, "_resolve_provider", lambda task: "ollama")
    users = _run(monkeypatch, stand_alone=False)
    monkeypatch.setattr(scriptwriter, "_LOCAL_STORY_SO_FAR_SEGMENTS", 1)
    users_capped = _run(monkeypatch, stand_alone=False)
    assert "Walter hands you the matches." in users[2]
    assert "Walter hands you the matches." not in users_capped[2]
    assert "Walter's hip is worse." in users_capped[2]


def test_resumed_segments_still_feed_the_story_so_far(isolated_progress, monkeypatch):
    outline = _outline(2)
    key = scriptwriter._progress_key("sys", "user", None, scriptwriter._OUTLINE_INSTRUCTIONS,
                                     scriptwriter._SEGMENT_SCENES_INSTRUCTIONS)
    cached = [Scene.model_validate(s).model_dump(mode="json")
              for s in json.loads(_scenes("Walter hands you the matches."))["scenes"]]
    scriptwriter._save_progress(key, outline, [cached])
    users: list[str] = []

    def fake_chat(system, user, **kwargs):
        users.append(user)
        return _scenes("Spring.")

    monkeypatch.setattr(scriptwriter, "chat", fake_chat)
    scriptwriter._generate_segmented("sys", "user", "topic", "", "", None)
    assert len(users) == 1, "segment 1 should come from the cache"
    assert "Walter hands you the matches." in users[0]


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


def test_life_as_a_never_names_invented_characters():
    # An invented first name ("Elena") reads as someone the listener should
    # already know; recurring people are carried by a relationship label instead.
    system = LIFE_AS_A_SCRIPT_SYSTEM.template
    outline = LIFE_AS_A_OUTLINE_INSTRUCTIONS.template
    level = LIFE_AS_A_LEVEL_SCENES_INSTRUCTIONS.template
    for text in (system, level):
        assert "Never give an invented person a name" in text
        assert "Recurring named characters" not in text
    assert '"label": "how narration always refers to them' in outline
    assert '"name": "First name"' not in outline
    assert "plant a named character" not in level


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


def test_listicle_endings_are_concrete_and_concessions_are_not_templated():
    # A/B on the same outline: the old "Mic Drop on every sub-topic" and copyable
    # steel-man example produced aphorism closers and a repeated "the skeptics had
    # a point" line; softened, judged human-sounding went 5 -> 6-7, majors 1 -> 0.
    text = SCRIPT_SYSTEM.template
    assert "End every sub-topic with an absolute, highly quotable" not in text
    assert "Never end on an abstract moral or generalization" in text
    assert "X actually makes a lot of sense when you look at it from Z angle" not in text
    assert "at most once per segment, in your own words each time" in text
