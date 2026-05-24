from models.script import Scene


def test_scene_defaults_to_full_frame_visual_mode():
    scene = Scene(id="scene_001", narration="Hello.", visual_prompt="A simple scene")

    assert scene.visual_mode == "full_frame"
    assert scene.media_source == "ai"
    assert scene.visual_treatment == "full_frame"


def test_scene_derives_video_visual_mode_from_legacy_ai_video_source():
    scene = Scene(
        id="scene_001",
        narration="Hello.",
        visual_prompt="A simple scene",
        media_source="ai_video",
    )

    assert scene.visual_mode == "video"
    assert scene.media_source == "ai_video"
    assert scene.visual_treatment == "full_frame"


def test_scene_derives_popup_visual_mode_from_legacy_treatment():
    scene = Scene(
        id="scene_001",
        narration="Hello.",
        visual_prompt="A simple scene",
        visual_treatment="popup_sequence",
    )

    assert scene.visual_mode == "popup_sequence"
    assert scene.media_source == "ai"
    assert scene.visual_treatment == "popup_sequence"


def test_scene_derives_video_when_legacy_source_and_treatment_conflict():
    scene = Scene(
        id="scene_001",
        narration="Hello.",
        visual_prompt="A simple scene",
        media_source="ai_video",
        visual_treatment="popup_sequence",
    )

    assert scene.visual_mode == "video"
    assert scene.media_source == "ai_video"
    assert scene.visual_treatment == "full_frame"


def test_scene_synchronizes_legacy_fields_from_explicit_visual_mode():
    scene = Scene(
        id="scene_001",
        narration="Hello.",
        visual_prompt="A simple scene",
        visual_mode="flipflop",
        media_source="ai_video",
        visual_treatment="full_frame",
    )

    assert scene.visual_mode == "flipflop"
    assert scene.media_source == "ai"
    assert scene.visual_treatment == "flipflop"
