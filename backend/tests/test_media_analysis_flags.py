"""Tests for manual media analysis source fallback behavior."""

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from api.media import (
    missing_voiceover_scene_ids,
    media_analysis_source_flags,
    normalize_media_assignments_for_sources,
    preserve_media_analysis_source_flags,
    require_media_analysis_voiceover,
)
from models.script import ScriptContent
from models.script import Scene, Segment
from pipeline import media_analyzer
from pipeline.media_analyzer import MediaAssignment, _resolve_scene_id, analyze_media_sources
from pipeline.render_jobs import UserFacingJobError


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


def test_normalize_media_assignments_preserves_stale_ai_video_for_final_duration():
    content = ScriptContent(
        title="Final duration",
        segments=[
            Segment(
                name="Segment",
                scenes=[
                    Scene(
                        id="scene_001",
                        narration="Longer than the AI video routing cap.",
                        visual_prompt="[ESTABLISHING] A guard walks down a hallway",
                        audio_duration_seconds=7.2,
                    ),
                ],
            ),
        ],
    )
    assignments = [
        MediaAssignment("scene_001", "ai_video", None, None, "Was eligible before voiceover changed"),
    ]

    normalized = normalize_media_assignments_for_sources(
        assignments,
        script_content=content,
        gameplay_enabled=False,
        stock_photo_enabled=False,
        ai_video_enabled=True,
    )

    assert normalized[0].media_source == "ai_video"
    assert normalized[0].reasoning == "Was eligible before voiceover changed"


def test_normalize_media_assignments_preserves_protected_current_source():
    content = ScriptContent(
        title="User upload race",
        segments=[
            Segment(
                name="Segment",
                scenes=[
                    Scene(
                        id="scene_001",
                        narration="Short enough for AI video.",
                        visual_prompt="[ESTABLISHING] A guard walks down a hallway",
                        audio_duration_seconds=4.2,
                        media_source="user_upload",
                    ),
                ],
            ),
        ],
    )
    assignments = [
        MediaAssignment("scene_001", "ai_video", None, None, "Was eligible before user upload"),
    ]

    normalized = normalize_media_assignments_for_sources(
        assignments,
        script_content=content,
        gameplay_enabled=False,
        stock_photo_enabled=False,
        ai_video_enabled=True,
    )

    assert normalized == []


def test_missing_voiceover_scene_ids_requires_audio_duration_for_every_scene():
    content = ScriptContent(
        title="Voiceover gate",
        segments=[
            Segment(
                name="Segment",
                scenes=[
                    Scene(id="scene_001", narration="Ready.", visual_prompt="Ready", audio_duration_seconds=4.2),
                    Scene(id="scene_002", narration="Missing.", visual_prompt="Missing", audio_duration_seconds=0),
                ],
            ),
        ],
    )

    assert missing_voiceover_scene_ids(content) == ["scene_002"]


def test_require_media_analysis_voiceover_raises_user_facing_error():
    content = ScriptContent(
        title="Voiceover gate",
        segments=[
            Segment(
                name="Segment",
                scenes=[
                    Scene(id="scene_001", narration="Ready.", visual_prompt="Ready", audio_duration_seconds=4.2),
                    Scene(id="scene_002", narration="Missing.", visual_prompt="Missing", audio_duration_seconds=0),
                ],
            ),
        ],
    )

    with pytest.raises(UserFacingJobError, match="1 scene\\(s\\) are missing"):
        require_media_analysis_voiceover(content)


def test_resolve_scene_id_handles_unpadded_llm_ids():
    valid_scene_ids = {"scene_001", "scene_003", "scene_010"}

    assert _resolve_scene_id("scene_3", valid_scene_ids) == "scene_003"
    assert _resolve_scene_id("scene_010", valid_scene_ids) == "scene_010"
    assert _resolve_scene_id("scene_99", valid_scene_ids) is None


def test_analyze_media_sources_fills_ai_video_per_segment_slots(monkeypatch):
    content = ScriptContent(
        title="Motion routing",
        segments=[
            Segment(
                name="Level 1",
                scenes=[
                    Scene(id="scene_001", narration="Level one.", visual_prompt="[ESTABLISHING] title", is_title_card=True),
                    Scene(
                        id="scene_002",
                        narration="You walk down the corridor and the light shifts.",
                        visual_prompt="[ESTABLISHING] A guard walking down a corridor as shadows move",
                    ),
                    Scene(
                        id="scene_007",
                        narration="The door opens and the alarm light turns red.",
                        visual_prompt="[CLOSE-UP] A security door opening as a red alarm light turns on",
                    ),
                ],
            ),
            Segment(
                name="Level 2",
                scenes=[
                    Scene(id="scene_003", narration="Level two.", visual_prompt="[ESTABLISHING] title", is_title_card=True),
                    Scene(
                        id="scene_004",
                        narration="A hand slides the tray through the slot.",
                        visual_prompt="[CLOSE-UP] A meal tray sliding through a narrow slot",
                    ),
                ],
            ),
            Segment(
                name="Level 3",
                scenes=[
                    Scene(id="scene_005", narration="Level three.", visual_prompt="[ESTABLISHING] title", is_title_card=True),
                    Scene(
                        id="scene_006",
                        narration="The room changes across the year.",
                        visual_prompt="[CONTINUOUS] A break room slowly emptying as months pass",
                        visual_beat="continuous",
                    ),
                ],
            ),
        ],
    )

    monkeypatch.setattr(media_analyzer, "chat", lambda **_: """{
      "assignments": [
        {"scene_id": "scene_001", "media_source": "ai_video", "game_name": null, "search_query": null, "reasoning": "bad title choice"},
        {"scene_id": "scene_002", "media_source": "ai_video", "game_name": null, "search_query": null, "reasoning": "good model choice"},
        {"scene_id": "scene_007", "media_source": "ai", "game_name": null, "search_query": null, "reasoning": "missed second candidate"},
        {"scene_id": "scene_003", "media_source": "ai", "game_name": null, "search_query": null, "reasoning": "title"},
        {"scene_id": "scene_004", "media_source": "ai", "game_name": null, "search_query": null, "reasoning": "missed candidate"},
        {"scene_id": "scene_005", "media_source": "ai", "game_name": null, "search_query": null, "reasoning": "title"},
        {"scene_id": "scene_006", "media_source": "ai", "game_name": null, "search_query": null, "reasoning": "missed candidate"}
      ]
    }""")

    assignments = analyze_media_sources(
        content,
        gameplay_enabled=False,
        stock_photo_enabled=False,
        ai_video_enabled=True,
        animated_scene_count=1,
        ai_video_scenes_per_segment=2,
        script_id="test-script",
    )

    sources = {assignment.scene_id: assignment.media_source for assignment in assignments}
    assert sources == {
        "scene_001": "ai",
        "scene_002": "ai_video",
        "scene_007": "ai",
        "scene_003": "ai",
        "scene_004": "ai_video",
        "scene_005": "ai",
        "scene_006": "ai_video",
    }


def test_analyze_media_sources_does_not_assign_back_to_back_ai_video(monkeypatch):
    content = ScriptContent(
        title="Spaced motion routing",
        segments=[
            Segment(
                name="Segment 1",
                scenes=[
                    Scene(id="scene_001", narration="Title.", visual_prompt="[ESTABLISHING] title", is_title_card=True),
                    Scene(
                        id="scene_002",
                        narration="You walk into the hallway as the light changes.",
                        visual_prompt="[ESTABLISHING] A person walking into a hallway as the light shifts",
                    ),
                    Scene(
                        id="scene_003",
                        narration="The door opens and smoke rolls across the floor.",
                        visual_prompt="[CLOSE-UP] A door opening as smoke rolls across the floor",
                    ),
                    Scene(
                        id="scene_004",
                        narration="The camera drifts across a control room.",
                        visual_prompt="[ESTABLISHING] A camera drifting across a control room",
                    ),
                ],
            ),
        ],
    )

    monkeypatch.setattr(media_analyzer, "chat", lambda **_: """{
      "assignments": [
        {"scene_id": "scene_001", "media_source": "ai", "game_name": null, "search_query": null, "reasoning": "title"},
        {"scene_id": "scene_002", "media_source": "ai_video", "game_name": null, "search_query": null, "reasoning": "model choice"},
        {"scene_id": "scene_003", "media_source": "ai_video", "game_name": null, "search_query": null, "reasoning": "adjacent model choice"},
        {"scene_id": "scene_004", "media_source": "ai", "game_name": null, "search_query": null, "reasoning": "missed candidate"}
      ]
    }""")

    assignments = analyze_media_sources(
        content,
        gameplay_enabled=False,
        stock_photo_enabled=False,
        ai_video_enabled=True,
        animated_scene_count=3,
        ai_video_scenes_per_segment=3,
        script_id="test-script",
    )

    sources = [assignment.media_source for assignment in assignments]
    assert sources == ["ai", "ai_video", "ai", "ai_video"]
    assert all(
        left != "ai_video" or right != "ai_video"
        for left, right in zip(sources, sources[1:])
    )


def test_analyze_media_sources_does_not_promote_stock_or_text_only(monkeypatch):
    content = ScriptContent(
        title="Mixed routing",
        segments=[
            Segment(
                name="Segment 1",
                scenes=[
                    Scene(id="scene_001", narration="Segment title.", visual_prompt="[ESTABLISHING] title", is_title_card=True),
                    Scene(
                        id="scene_002",
                        narration="A real courthouse exterior appears.",
                        visual_prompt="[ESTABLISHING] County courthouse exterior",
                    ),
                    Scene(
                        id="scene_003",
                        narration="A guard turns toward the corridor.",
                        visual_prompt="[REACTION] A guard turning toward a corridor",
                    ),
                ],
            ),
            Segment(
                name="Segment 2",
                scenes=[
                    Scene(id="scene_004", narration="Segment title.", visual_prompt="[ESTABLISHING] title", is_title_card=True),
                    Scene(
                        id="scene_005",
                        narration="A stark sentence appears.",
                        visual_prompt="",
                        visual_beat="aha_subtitle",
                        frame_directives=[{"source": "subtitle", "prompt": "TEXT", "transition": "cut"}],
                    ),
                    Scene(
                        id="scene_006",
                        narration="A figure walks back into the kitchen.",
                        visual_prompt="[ESTABLISHING] A figure walking back into a kitchen",
                    ),
                ],
            ),
        ],
    )

    monkeypatch.setattr(media_analyzer, "chat", lambda **_: """{
      "assignments": [
        {"scene_id": "scene_001", "media_source": "ai", "game_name": null, "search_query": null, "reasoning": "title"},
        {"scene_id": "scene_002", "media_source": "stock_photo", "game_name": null, "search_query": "courthouse exterior", "reasoning": "real place"},
        {"scene_id": "scene_003", "media_source": "ai", "game_name": null, "search_query": null, "reasoning": "ai art"},
        {"scene_id": "scene_004", "media_source": "ai", "game_name": null, "search_query": null, "reasoning": "title"},
        {"scene_id": "scene_005", "media_source": "ai", "game_name": null, "search_query": null, "reasoning": "text only"},
        {"scene_id": "scene_006", "media_source": "ai", "game_name": null, "search_query": null, "reasoning": "ai art"}
      ]
    }""")

    assignments = analyze_media_sources(
        content,
        gameplay_enabled=False,
        stock_photo_enabled=True,
        ai_video_enabled=True,
        animated_scene_count=2,
        script_id="test-script",
    )

    sources = {assignment.scene_id: assignment.media_source for assignment in assignments}
    assert sources["scene_002"] == "stock_photo"
    assert sources["scene_003"] == "ai_video"
    assert sources["scene_005"] == "ai"
    assert sources["scene_006"] == "ai_video"


def test_life_as_a_ai_video_only_promotes_eli_scenes(monkeypatch):
    content = ScriptContent(
        title="Your Life As A Prison Guard",
        format_id="life-as-a",
        segments=[
            Segment(
                name="Level 1",
                scenes=[
                    Scene(id="scene_001", narration="Level one.", visual_prompt="[ESTABLISHING] title", is_title_card=True),
                    Scene(
                        id="scene_002",
                        narration="The fluorescent lights flicker over the empty break room.",
                        visual_prompt="[ESTABLISHING] An empty break room with chairs stacked by the wall",
                        visual_beat="continuous",
                    ),
                    Scene(
                        id="scene_003",
                        narration="You walk the corridor and learn the rhythm of the doors.",
                        visual_prompt=(
                            "Eli, the recurring character, is the main subject and protagonist in this scene. "
                            "Depict Eli as Prison Guard; any other people are secondary and visually distinct from Eli. "
                            "[ESTABLISHING] A prison guard walking down a corridor"
                        ),
                        contains_person=True,
                    ),
                ],
            ),
            Segment(
                name="Level 2",
                scenes=[
                    Scene(id="scene_004", narration="Level two.", visual_prompt="[ESTABLISHING] title", is_title_card=True),
                    Scene(
                        id="scene_005",
                        narration="A plastic tray slides through the slot.",
                        visual_prompt="[CLOSE-UP] A plastic tray sliding through a narrow slot",
                    ),
                ],
            ),
        ],
    )

    monkeypatch.setattr(media_analyzer, "chat", lambda **_: """{
      "assignments": [
        {"scene_id": "scene_001", "media_source": "ai", "game_name": null, "search_query": null, "reasoning": "title"},
        {"scene_id": "scene_002", "media_source": "ai_video", "game_name": null, "search_query": null, "reasoning": "moving but no eli"},
        {"scene_id": "scene_003", "media_source": "ai", "game_name": null, "search_query": null, "reasoning": "missed eli"},
        {"scene_id": "scene_004", "media_source": "ai", "game_name": null, "search_query": null, "reasoning": "title"},
        {"scene_id": "scene_005", "media_source": "ai", "game_name": null, "search_query": null, "reasoning": "object"}
      ]
    }""")

    assignments = analyze_media_sources(
        content,
        gameplay_enabled=False,
        stock_photo_enabled=False,
        ai_video_enabled=True,
        animated_scene_count=1,
        script_id="test-script",
    )

    sources = {assignment.scene_id: assignment.media_source for assignment in assignments}
    assert sources["scene_002"] == "ai"
    assert sources["scene_003"] == "ai_video"
    assert sources["scene_005"] == "ai"


def test_analyze_media_sources_respects_zero_ai_video_count(monkeypatch):
    content = ScriptContent(
        title="Disabled animation",
        segments=[
            Segment(
                name="Segment 1",
                scenes=[
                    Scene(id="scene_001", narration="Title.", visual_prompt="[ESTABLISHING] title", is_title_card=True),
                    Scene(
                        id="scene_002",
                        narration="A guard walks down the hallway.",
                        visual_prompt="[ESTABLISHING] A guard walking down a hallway",
                    ),
                ],
            ),
        ],
    )

    monkeypatch.setattr(media_analyzer, "chat", lambda **_: """{
      "assignments": [
        {"scene_id": "scene_001", "media_source": "ai", "game_name": null, "search_query": null, "reasoning": "title"},
        {"scene_id": "scene_002", "media_source": "ai_video", "game_name": null, "search_query": null, "reasoning": "model wanted motion"}
      ]
    }""")

    assignments = analyze_media_sources(
        content,
        gameplay_enabled=True,
        stock_photo_enabled=False,
        ai_video_enabled=True,
        animated_scene_count=0,
        script_id="test-script",
    )

    assert all(assignment.media_source != "ai_video" for assignment in assignments)


def test_analyze_media_sources_ignores_duplicate_resolved_scene_ids(monkeypatch):
    content = ScriptContent(
        title="Duplicate ids",
        segments=[
            Segment(
                name="Segment 1",
                scenes=[
                    Scene(id="scene_001", narration="Title.", visual_prompt="[ESTABLISHING] title", is_title_card=True),
                    Scene(
                        id="scene_002",
                        narration="A guard walks down the hallway.",
                        visual_prompt="[ESTABLISHING] A guard walking down a hallway",
                    ),
                ],
            ),
        ],
    )

    monkeypatch.setattr(media_analyzer, "chat", lambda **_: """{
      "assignments": [
        {"scene_id": "scene_2", "media_source": "ai_video", "game_name": null, "search_query": null, "reasoning": "accepted"},
        {"scene_id": "scene_002", "media_source": "ai", "game_name": null, "search_query": null, "reasoning": "duplicate downgrade"},
        {"scene_id": "scene_001", "media_source": "ai", "game_name": null, "search_query": null, "reasoning": "title"}
      ]
    }""")

    assignments = analyze_media_sources(
        content,
        gameplay_enabled=False,
        stock_photo_enabled=False,
        ai_video_enabled=True,
        animated_scene_count=1,
        script_id="test-script",
    )

    sources = {assignment.scene_id: assignment.media_source for assignment in assignments}
    assert sources["scene_001"] == "ai"
    assert sources["scene_002"] == "ai_video"
