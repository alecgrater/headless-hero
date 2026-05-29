from models.script import Scene


def test_scene_defaults_to_full_frame_visual_mode():
    scene = Scene(id="scene_001", narration="Hello.", visual_prompt="A simple scene")

    assert scene.visual_mode == "full_frame"
    dumped = scene.model_dump()
    assert "media_source" not in dumped
    assert "visual_treatment" not in dumped


def test_scene_normalizes_legacy_mirror_fields_without_reserializing_them():
    scene = Scene(
        id="scene_001",
        narration="Hello.",
        visual_prompt="A simple scene",
        media_source="ai_video",
        visual_treatment="popup_sequence",
    )

    assert scene.visual_mode == "video"
    dumped = scene.model_dump()
    assert "media_source" not in dumped
    assert "visual_treatment" not in dumped


def test_scene_derives_video_visual_mode_from_legacy_ai_video_source():
    scene = Scene(
        id="scene_001",
        narration="Hello.",
        visual_prompt="A simple scene",
        media_source="ai_video",
    )

    assert scene.visual_mode == "video"
    assert "media_source" not in scene.model_dump()
    assert "visual_treatment" not in scene.model_dump()


def test_scene_derives_popup_visual_mode_from_legacy_treatment():
    scene = Scene(
        id="scene_001",
        narration="Hello.",
        visual_prompt="A simple scene",
        visual_treatment="popup_sequence",
    )

    assert scene.visual_mode == "popup_sequence"
    assert "media_source" not in scene.model_dump()
    assert "visual_treatment" not in scene.model_dump()


def test_scene_derives_video_when_legacy_source_and_treatment_conflict():
    scene = Scene(
        id="scene_001",
        narration="Hello.",
        visual_prompt="A simple scene",
        media_source="ai_video",
        visual_treatment="popup_sequence",
    )

    assert scene.visual_mode == "video"
    assert "media_source" not in scene.model_dump()
    assert "visual_treatment" not in scene.model_dump()


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
    assert "media_source" not in scene.model_dump()
    assert "visual_treatment" not in scene.model_dump()


def test_scene_accepts_explicit_multi_frame_visual_mode():
    scene = Scene(
        id="scene_001",
        narration="Three images land fast.",
        visual_prompt="Several examples.",
        visual_mode="multi_frame",
        frame_urls=["/static/projects/script/images/scene_001_0.png"],
    )

    assert scene.visual_mode == "multi_frame"
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
    assert scene.frame_urls == ["/static/projects/script/images/scene_001_0.png"]


def test_scene_accepts_explicit_comparison_board_visual_mode_and_clears_frames():
    scene = Scene(
        id="scene_001",
        narration="The prisoner has nothing, while the guard has every key.",
        visual_prompt="Prisoner versus guard comparison.",
        visual_mode="comparison_board",
        frame_urls=["/static/projects/script/images/scene_001_0.png"],
    )

    assert scene.visual_mode == "comparison_board"
    assert scene.visual_beat == "comparison_board"
    assert scene.frame_urls == []


def test_scene_derives_multi_frame_from_legacy_quick_cuts_beat():
    scene = Scene(
        id="scene_001",
        narration="First this, then that.",
        visual_prompt="Multiple examples.",
        visual_beat="quick_cuts",
        frame_urls=["/static/projects/script/images/scene_001_0.png"],
    )

    assert scene.visual_mode == "multi_frame"
    assert scene.frame_urls == ["/static/projects/script/images/scene_001_0.png"]


def test_scene_derives_multi_frame_from_legacy_montage_beat():
    scene = Scene(
        id="scene_001",
        narration="Several places flash by.",
        visual_prompt="Several related places.",
        visual_beat="montage",
    )

    assert scene.visual_mode == "multi_frame"


def test_scene_derives_multi_frame_from_legacy_multi_frame_beat():
    scene = Scene(
        id="scene_001",
        narration="Several examples appear in sequence.",
        visual_prompt="Multiple examples.",
        visual_beat="multi_frame",
    )

    assert scene.visual_mode == "multi_frame"


def test_scene_derives_continuous_from_legacy_continuous_beat():
    scene = Scene(
        id="scene_001",
        narration="The machine assembles itself.",
        visual_prompt="A machine being assembled.",
        visual_beat="continuous",
    )

    assert scene.visual_mode == "continuous"


def test_scene_assignment_syncs_quick_cuts_visual_beat_to_multi_frame():
    scene = Scene(
        id="scene_001",
        narration="First this, then that.",
        visual_prompt="Multiple examples.",
        frame_urls=["/static/projects/script/images/scene_001_0.png"],
    )

    scene.visual_beat = "quick_cuts"

    assert scene.visual_mode == "multi_frame"
    assert scene.frame_urls == ["/static/projects/script/images/scene_001_0.png"]


def test_scene_assignment_syncs_continuous_visual_beat():
    scene = Scene(
        id="scene_001",
        narration="The machine assembles itself.",
        visual_prompt="A machine being assembled.",
    )

    scene.visual_beat = "continuous"

    assert scene.visual_mode == "continuous"


def test_scene_assignment_syncs_video_visual_mode_and_clears_frames():
    scene = Scene(
        id="scene_001",
        narration="Hello.",
        visual_prompt="A simple scene",
        frame_urls=["/static/projects/script/images/scene_001_0.png"],
    )

    scene.visual_mode = "video"

    assert scene.visual_mode == "video"
    assert scene.frame_urls == []


def test_scene_assignment_syncs_popup_visual_mode_and_clears_frames():
    scene = Scene(
        id="scene_001",
        narration="Hello.",
        visual_prompt="A simple scene",
        frame_urls=["/static/projects/script/images/scene_001_0.png"],
    )

    scene.visual_mode = "popup_sequence"

    assert scene.visual_mode == "popup_sequence"
    assert scene.frame_urls == []


def test_scene_visual_beat_assignment_does_not_demote_video_mode():
    scene = Scene(
        id="scene_001",
        narration="Hello.",
        visual_prompt="A simple scene",
        visual_mode="video",
        frame_urls=["/static/projects/script/images/scene_001_0.png"],
    )

    scene.visual_beat = "quick_cuts"

    assert scene.visual_mode == "video"
    assert scene.frame_urls == []


def test_scene_visual_beat_assignment_does_not_demote_popup_mode():
    scene = Scene(
        id="scene_001",
        narration="Hello.",
        visual_prompt="A simple scene",
        visual_mode="popup_sequence",
        frame_urls=["/static/projects/script/images/scene_001_0.png"],
    )

    scene.visual_beat = "continuous"

    assert scene.visual_mode == "popup_sequence"
    assert scene.frame_urls == []


def test_scene_visual_beat_assignment_does_not_demote_flipflop_mode():
    scene = Scene(
        id="scene_001",
        narration="Hello.",
        visual_prompt="A simple scene",
        visual_mode="flipflop",
        frame_urls=["/static/projects/script/images/scene_001_0.png"],
    )

    scene.visual_beat = "quick_cuts"

    assert scene.visual_mode == "flipflop"
    assert scene.frame_urls == []


def test_scene_accepts_explicit_captions_visual_mode():
    scene = Scene(
        id="scene_001",
        narration="Spending big in one area while falling behind in another.",
        visual_prompt="[REACTION] A worried cartoon shopper holding a receipt.",
        visual_mode="captions",
        caption_text="Spending big while falling behind",
        caption_emphasis="falling behind",
        image_url="/static/projects/script/images/scene_001.png",
        frame_urls=["/static/projects/script/images/scene_001_0.png"],
    )

    assert scene.visual_mode == "captions"
    assert scene.visual_beat == "captions"
    assert scene.caption_text == "Spending big while falling behind"
    assert scene.caption_emphasis == "falling behind"
    assert scene.image_url == "/static/projects/script/images/scene_001.png"
    assert scene.frame_urls == ["/static/projects/script/images/scene_001_0.png"]


def test_scene_derives_captions_from_legacy_visual_beat():
    scene = Scene(
        id="scene_001",
        narration="This was the real cost.",
        visual_prompt="",
        visual_beat="captions",
        caption_text="The real cost",
        caption_emphasis="real",
    )

    assert scene.visual_mode == "captions"
    assert scene.visual_beat == "captions"


def test_scene_assignment_syncs_captions_visual_mode_without_clearing_media():
    scene = Scene(
        id="scene_001",
        narration="You were never behind.",
        visual_prompt="[CLOSE-UP] A character staring at a calendar.",
        image_url="/static/projects/script/images/scene_001.png",
        frame_urls=["/static/projects/script/images/scene_001_0.png"],
    )

    scene.visual_mode = "captions"

    assert scene.visual_mode == "captions"
    assert scene.visual_beat == "captions"
    assert scene.image_url == "/static/projects/script/images/scene_001.png"
    assert scene.frame_urls == ["/static/projects/script/images/scene_001_0.png"]
