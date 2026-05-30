from models.script import Scene, VisualLayer


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


def test_scene_derives_dossier_visual_mode_from_legacy_treatment():
    scene = Scene(
        id="scene_001",
        narration="The case file has three clues.",
        visual_prompt="Dossier board with evidence cutouts.",
        visual_treatment="dossier",
        dossier_title="CASE #1989-04",
    )

    assert scene.visual_mode == "dossier"
    assert scene.visual_beat == "dossier"
    assert scene.dossier_title == "CASE #1989-04"
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
    assert scene.visual_beat == "popup_sequence"
    assert scene.frame_urls == []


def test_scene_assignment_syncs_layered_visual_beats():
    for visual_mode in ("flipflop", "comparison_board", "stat_card", "dossier"):
        scene = Scene(
            id="scene_001",
            narration="Hello.",
            visual_prompt="A simple scene",
        )

        scene.visual_mode = visual_mode

        assert scene.visual_mode == visual_mode
        assert scene.visual_beat == visual_mode


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


def test_scene_accepts_explicit_stat_card_visual_mode_and_clears_media():
    scene = Scene(
        id="scene_001",
        narration="Eighty-five percent of new users churn in week one.",
        visual_prompt="",
        visual_mode="stat_card",
        stat_value="85%",
        stat_label="of new users churn in week 1",
        image_url="/static/projects/script/images/scene_001.png",
        frame_urls=["/static/projects/script/images/scene_001_0.png"],
        video_url="/static/projects/script/videos/scene_001.mp4",
    )

    assert scene.visual_mode == "stat_card"
    assert scene.visual_beat == "stat_card"
    assert scene.stat_value == "85%"
    assert scene.stat_label == "of new users churn in week 1"
    assert scene.image_url == ""
    assert scene.frame_urls == []
    assert scene.video_url == ""


def test_scene_stat_card_preserves_visual_layers():
    scene = Scene(
        id="scene_001",
        narration="Two million dollars lost to fraud every hour.",
        visual_prompt="A padlock icon.",
        visual_mode="stat_card",
        stat_value="$2M",
        stat_label="lost to fraud every hour",
        visual_layers=[
            {
                "id": "scene_001_icon",
                "type": "image",
                "asset_kind": "cutout",
                "prompt": "A padlock icon.",
                "placement": "center",
            }
        ],
    )

    assert scene.visual_mode == "stat_card"
    assert len(scene.visual_layers) == 1
    assert scene.visual_layers[0].asset_kind == "cutout"


def test_scene_leaving_stat_card_clears_stat_fields():
    scene = Scene(
        id="scene_001",
        narration="Eighty-five percent of new users churn in week one.",
        visual_prompt="",
        visual_mode="stat_card",
        stat_value="85%",
        stat_label="of new users churn in week 1",
    )

    scene.visual_mode = "full_frame"

    assert scene.visual_mode == "full_frame"
    assert scene.stat_value == ""
    assert scene.stat_label == ""


def test_scene_entering_stat_card_clears_caption_and_media():
    scene = Scene(
        id="scene_001",
        narration="Eighty-five percent.",
        visual_prompt="[REACTION] Worried face",
        visual_mode="captions",
        caption_text="The real cost",
        caption_emphasis="real",
        image_url="/static/projects/script/images/scene_001.png",
    )

    scene.visual_mode = "stat_card"

    assert scene.visual_mode == "stat_card"
    assert scene.caption_text == ""
    assert scene.caption_emphasis == ""
    assert scene.image_url == ""


def test_scene_normalizes_stat_card_from_raw_dict():
    raw = {
        "id": "scene_001",
        "narration": "Eighty-five percent of new users churn in week one.",
        "visual_prompt": "",
        "visual_mode": "stat_card",
        "stat_value": "85%",
        "stat_label": "of new users churn in week 1",
        "image_url": "/static/projects/script/images/scene_001.png",
        "frame_urls": ["/static/projects/script/images/scene_001_0.png"],
        "video_url": "/static/projects/script/videos/scene_001.mp4",
        "caption_text": "leftover caption",
        "caption_emphasis": "leftover",
    }

    scene = Scene.model_validate(raw)

    assert scene.visual_mode == "stat_card"
    assert scene.stat_value == "85%"
    assert scene.stat_label == "of new users churn in week 1"
    assert scene.image_url == ""
    assert scene.frame_urls == []
    assert scene.video_url == ""
    assert scene.caption_text == ""
    assert scene.caption_emphasis == ""


def test_scene_normalizes_dossier_visual_mode_clears_conflicting_fields():
    raw = {
        "id": "scene_001",
        "narration": "The investigators built the case slowly.",
        "visual_prompt": "Dossier scene with anchor and evidence cutouts.",
        "visual_mode": "dossier",
        "dossier_layout": "anchor",
        "dossier_title": "CASE #1989-04",
        "image_url": "/static/projects/script/images/scene_001.png",
        "frame_urls": ["/static/projects/script/images/scene_001_0.png"],
        "video_url": "/static/projects/script/videos/scene_001.mp4",
        "caption_text": "leftover caption",
        "caption_emphasis": "leftover",
        "stat_value": "99%",
        "stat_label": "of cases unsolved",
    }

    scene = Scene.model_validate(raw)

    assert scene.visual_mode == "dossier"
    assert scene.dossier_layout == "anchor"
    assert scene.dossier_title == "CASE #1989-04"
    assert scene.image_url == ""
    assert scene.video_url == ""
    assert scene.frame_urls == []
    assert scene.caption_text == ""
    assert scene.caption_emphasis == ""
    assert scene.stat_value == ""
    assert scene.stat_label == ""


def test_scene_assignment_to_dossier_clears_conflicting_fields_and_back():
    scene = Scene(
        id="scene_001",
        narration="Three conspirators connected.",
        visual_prompt="Test",
        visual_mode="full_frame",
        image_url="/static/projects/script/images/scene_001.png",
        caption_text="leftover",
        caption_emphasis="leftover",
    )

    scene.visual_mode = "dossier"
    assert scene.visual_mode == "dossier"
    assert scene.image_url == ""
    assert scene.caption_text == ""
    assert scene.dossier_layout == "anchor"

    scene.dossier_title = "OPERATION NIGHTSHADE"
    scene.visual_mode = "full_frame"
    assert scene.visual_mode == "full_frame"
    assert scene.dossier_title == ""


def test_visual_layer_round_trips_label_field():
    layer = VisualLayer(id="layer_1", label="SUSPECT")
    payload = layer.model_dump()
    assert payload["label"] == "SUSPECT"
    rebuilt = VisualLayer.model_validate(payload)
    assert rebuilt.label == "SUSPECT"


def test_dossier_layout_validator_falls_back_to_anchor_for_invalid_value():
    raw = {
        "id": "scene_001",
        "narration": "x",
        "visual_prompt": "x",
        "visual_mode": "dossier",
        "dossier_layout": "weird",
    }

    scene = Scene.model_validate(raw)
    assert scene.dossier_layout == "anchor"
