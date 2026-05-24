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


def test_scene_accepts_explicit_multi_frame_visual_mode():
    scene = Scene(
        id="scene_001",
        narration="Three images land fast.",
        visual_prompt="Several examples.",
        visual_mode="multi_frame",
        frame_urls=["/static/projects/script/images/scene_001_0.png"],
    )

    assert scene.visual_mode == "multi_frame"
    assert scene.media_source == "ai"
    assert scene.visual_treatment == "full_frame"
    assert scene.frame_urls == ["/static/projects/script/images/scene_001_0.png"]


def test_scene_accepts_explicit_continuous_visual_mode():
    scene = Scene(
        id="scene_001",
        narration="A plant grows across the scene.",
        visual_prompt="A sprout growing.",
        visual_mode="continuous",
        frame_urls=["/static/projects/script/images/scene_001_0.png"],
    )

    assert scene.visual_mode == "continuous"
    assert scene.media_source == "ai"
    assert scene.visual_treatment == "full_frame"
    assert scene.frame_urls == ["/static/projects/script/images/scene_001_0.png"]


def test_scene_derives_multi_frame_from_legacy_quick_cuts_beat():
    scene = Scene(
        id="scene_001",
        narration="First this, then that.",
        visual_prompt="Multiple examples.",
        visual_beat="quick_cuts",
        frame_urls=["/static/projects/script/images/scene_001_0.png"],
    )

    assert scene.visual_mode == "multi_frame"
    assert scene.media_source == "ai"
    assert scene.visual_treatment == "full_frame"
    assert scene.frame_urls == ["/static/projects/script/images/scene_001_0.png"]


def test_scene_derives_multi_frame_from_legacy_montage_beat():
    scene = Scene(
        id="scene_001",
        narration="Several places flash by.",
        visual_prompt="Several related places.",
        visual_beat="montage",
    )

    assert scene.visual_mode == "multi_frame"
    assert scene.media_source == "ai"
    assert scene.visual_treatment == "full_frame"


def test_scene_derives_multi_frame_from_legacy_multi_frame_beat():
    scene = Scene(
        id="scene_001",
        narration="Several examples appear in sequence.",
        visual_prompt="Multiple examples.",
        visual_beat="multi_frame",
    )

    assert scene.visual_mode == "multi_frame"
    assert scene.media_source == "ai"
    assert scene.visual_treatment == "full_frame"


def test_scene_derives_continuous_from_legacy_continuous_beat():
    scene = Scene(
        id="scene_001",
        narration="The machine assembles itself.",
        visual_prompt="A machine being assembled.",
        visual_beat="continuous",
    )

    assert scene.visual_mode == "continuous"
    assert scene.media_source == "ai"
    assert scene.visual_treatment == "full_frame"
