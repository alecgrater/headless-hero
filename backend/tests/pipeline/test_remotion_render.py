"""Tests for Remotion render input helpers."""

import json

from models.script import Scene, ScriptContent, Segment
from pipeline import remotion_render


def _write_video_metadata(tmp_path, script_id: str, scene_id: str, duration_seconds: float) -> None:
    video_dir = tmp_path / "projects" / script_id / "videos"
    video_dir.mkdir(parents=True)
    (video_dir / f"{scene_id}.mp4").write_bytes(b"not a real mp4")
    (video_dir / f"{scene_id}.source.json").write_text(
        json.dumps({"duration_seconds": duration_seconds}),
        encoding="utf-8",
    )


def test_ai_video_scene_slows_clip_when_short_by_25_percent_or_less(tmp_path, monkeypatch):
    monkeypatch.setattr(remotion_render, "DATA_DIR", tmp_path)
    monkeypatch.setattr(remotion_render, "_probe_video_duration", lambda _path: None)
    script_id = "script-1"
    _write_video_metadata(tmp_path, script_id, "scene-1", 10.0)
    scene = Scene(
        id="scene-1",
        narration="Long narration.",
        visual_prompt="Animated explainer.",
        visual_mode="video",
        audio_duration_seconds=12.0,
    )

    props = remotion_render._scene_to_input_props(scene, script_id)

    assert props["duration_seconds"] == 12.0
    assert props["media_type"] == "video"
    assert props["video_playback_rate"] == 10.0 / 12.0
    assert props["video_path"].endswith("/static/projects/script-1/videos/scene-1.mp4")


def test_video_visual_mode_resolves_video_scene_props(tmp_path, monkeypatch):
    monkeypatch.setattr(remotion_render, "DATA_DIR", tmp_path)
    monkeypatch.setattr(remotion_render, "_probe_video_duration", lambda _path: None)
    script_id = "script-1"
    _write_video_metadata(tmp_path, script_id, "scene-1", 10.0)
    scene = Scene(
        id="scene-1",
        narration="Long narration.",
        visual_prompt="Animated explainer.",
        visual_mode="video",
        audio_duration_seconds=12.0,
    )

    props = remotion_render._scene_to_input_props(scene, script_id)

    assert props["visual_mode"] == "video"
    assert props["media_type"] == "video"
    assert props["video_path"].endswith("/static/projects/script-1/videos/scene-1.mp4")


def test_scene_to_input_props_include_caption_fields_for_captions_scene(tmp_path, monkeypatch):
    monkeypatch.setattr(remotion_render, "DATA_DIR", tmp_path)
    scene = Scene(
        id="scene_001",
        narration="This was the real cost.",
        visual_prompt="",
        visual_mode="captions",
        caption_text="The real cost",
        caption_emphasis="real",
        audio_duration_seconds=2.0,
        word_timestamps=[
            {"word": "This", "start_ms": 0, "end_ms": 120},
            {"word": "was", "start_ms": 140, "end_ms": 220},
            {"word": "the", "start_ms": 240, "end_ms": 310},
            {"word": "real", "start_ms": 330, "end_ms": 480},
            {"word": "cost", "start_ms": 500, "end_ms": 650},
        ],
    )

    props = remotion_render._scene_to_input_props(scene, "script")

    assert props["visual_mode"] == "captions"
    assert props["caption_text"] == "The real cost"
    assert props["caption_emphasis"] == "real"


def test_scene_to_input_props_includes_subtitle_style(tmp_path, monkeypatch):
    monkeypatch.setattr(remotion_render, "DATA_DIR", tmp_path)
    scene = Scene(
        id="scene_subtitle_style",
        narration="Fast words hit hard.",
        visual_prompt="A stylized brain lighting up.",
        subtitle_style="kinetic",
        word_timestamps=[{"word": "Fast", "start_ms": 0, "end_ms": 200}],
    )

    props = remotion_render._scene_to_input_props(scene, "script")

    assert props["subtitle_style"] == "kinetic"


def test_subtitle_render_fingerprint_tracks_style_and_router_version():
    content = ScriptContent(
        title="Test",
        segments=[
            Segment(
                name="One",
                scenes=[
                    Scene(id="scene-1", narration="Clean.", visual_prompt="", subtitle_style="clean"),
                    Scene(id="scene-2", narration="Burst.", visual_prompt="", subtitle_style="burst"),
                ],
            )
        ],
    )

    fingerprint = remotion_render.subtitle_render_fingerprint(content)

    assert fingerprint["subtitle_router_version"] == remotion_render.SUBTITLE_ROUTER_VERSION
    assert fingerprint["renderer_context_stage_version"] == remotion_render.RENDERER_CONTEXT_STAGE_VERSION
    assert fingerprint["scenes"] == [
        {
            "id": "scene-1",
            "subtitle_style": "clean",
            "visual_mode": "full_frame",
            "renderer_context": "",
            "stat_value": "",
            "stat_label": "",
            "stat_card_icon": None,
        },
        {
            "id": "scene-2",
            "subtitle_style": "burst",
            "visual_mode": "full_frame",
            "renderer_context": "",
            "stat_value": "",
            "stat_label": "",
            "stat_card_icon": None,
        },
    ]


def test_scene_input_props_include_renderer_context():
    scene = Scene(
        id="s1",
        narration="He blinks at the whiteboard.",
        visual_prompt="Teacher character.",
        visual_mode="flipflop",
        flipflop_action="blink",
        renderer_context="classroom",
    )

    props = remotion_render._scene_to_input_props(scene, "script-1")

    assert props["renderer_context"] == "classroom"


def test_subtitle_render_fingerprint_includes_renderer_context_for_canvas_modes():
    scene = Scene(
        id="s1",
        narration="He blinks at the whiteboard.",
        visual_prompt="Teacher character.",
        visual_mode="flipflop",
        flipflop_action="blink",
        renderer_context="classroom",
    )
    content = ScriptContent(title="T", segments=[Segment(name="S", scenes=[scene])])

    fingerprint = remotion_render.subtitle_render_fingerprint(content)

    assert fingerprint["renderer_context_stage_version"] == "renderer-context-stage-v1"
    assert fingerprint["scenes"][0]["renderer_context"] == "classroom"


def test_subtitle_settings_from_env_normalize_values(monkeypatch):
    monkeypatch.setenv("SUBTITLE_COVERAGE_MODE", "punchy")
    monkeypatch.setenv("SUBTITLE_STYLE_CLEAN_ENABLED", "false")
    monkeypatch.setenv("SUBTITLE_STYLE_KINETIC_ENABLED", "true")
    monkeypatch.setenv("SUBTITLE_STYLE_BURST_ENABLED", "false")

    settings = remotion_render.subtitle_settings_from_env()

    assert settings == {
        "coverage": "punchy",
        "enabled_styles": ["kinetic"],
    }


def test_apply_subtitle_coverage_limits_punchy_scenes(monkeypatch):
    monkeypatch.setenv("SUBTITLE_COVERAGE_MODE", "punchy")
    monkeypatch.setenv("SUBTITLE_STYLE_CLEAN_ENABLED", "true")
    monkeypatch.setenv("SUBTITLE_STYLE_KINETIC_ENABLED", "true")
    monkeypatch.setenv("SUBTITLE_STYLE_BURST_ENABLED", "true")
    content = ScriptContent(
        title="Test",
        segments=[
            Segment(
                name="One",
                scenes=[
                    Scene(id="title", narration="Title.", visual_prompt="", is_title_card=True),
                    Scene(id="plain-1", narration="A calm explanatory line.", visual_prompt=""),
                    Scene(id="plain-2", narration="Another calm explanatory line.", visual_prompt=""),
                    Scene(id="fast", narration="One two three four five six.", visual_prompt="", word_timestamps=[
                        {"word": "One", "start_ms": 0, "end_ms": 120},
                        {"word": "two", "start_ms": 130, "end_ms": 250},
                        {"word": "three", "start_ms": 260, "end_ms": 380},
                        {"word": "four", "start_ms": 390, "end_ms": 510},
                        {"word": "five", "start_ms": 520, "end_ms": 640},
                        {"word": "six", "start_ms": 650, "end_ms": 770},
                    ]),
                    Scene(id="caption", narration="The real cost.", visual_prompt="", visual_mode="captions"),
                ],
            )
        ],
    )

    styles = remotion_render._subtitle_styles_for_render(content)

    assert styles["fast"] == "auto"
    assert styles["plain-1"] == "none"
    assert styles["plain-2"] == "none"
    assert "caption" not in styles
    assert "title" not in styles


def test_ai_video_scene_falls_back_to_image_when_slowdown_would_exceed_25_percent(tmp_path, monkeypatch):
    monkeypatch.setattr(remotion_render, "DATA_DIR", tmp_path)
    monkeypatch.setattr(remotion_render, "_probe_video_duration", lambda _path: None)
    script_id = "script-1"
    _write_video_metadata(tmp_path, script_id, "scene-1", 5.0)
    image_dir = tmp_path / "projects" / script_id / "images"
    image_dir.mkdir(parents=True)
    (image_dir / "scene-1.png").write_bytes(b"fake image")
    scene = Scene(
        id="scene-1",
        narration="Long narration.",
        visual_prompt="Animated explainer.",
        visual_mode="video",
        audio_duration_seconds=12.0,
    )

    props = remotion_render._scene_to_input_props(scene, script_id)

    assert props["duration_seconds"] == 12.0
    assert props["media_type"] is None
    assert props["video_path"] is None
    assert props["image_path"].endswith("/static/projects/script-1/images/scene-1.png")


def test_video_scene_duration_keeps_audio_when_clip_is_long_enough(tmp_path, monkeypatch):
    monkeypatch.setattr(remotion_render, "DATA_DIR", tmp_path)
    monkeypatch.setattr(remotion_render, "_probe_video_duration", lambda _path: None)
    script_id = "script-1"
    _write_video_metadata(tmp_path, script_id, "scene-1", 10.0)
    scene = Scene(
        id="scene-1",
        narration="Short narration.",
        visual_prompt="Animated explainer.",
        visual_mode="video",
        audio_duration_seconds=7.0,
    )

    props = remotion_render._scene_to_input_props(scene, script_id)

    assert props["duration_seconds"] == 7.0


def test_scene_to_input_props_uses_visual_mode_for_layered_scenes(tmp_path, monkeypatch):
    monkeypatch.setattr(remotion_render, "DATA_DIR", tmp_path)
    image_dir = tmp_path / "projects" / "script" / "images"
    image_dir.mkdir(parents=True)
    (image_dir / "scene_layered_layer_panel_1.png").write_bytes(b"fake image")
    scene = Scene(
        id="scene_layered",
        narration="A list appears.",
        visual_prompt="x",
        audio_duration_seconds=2.0,
        visual_mode="popup_sequence",
        visual_layers=[
            {
                "id": "panel_1",
                "type": "image",
                "asset_kind": "panel",
                "image_url": "/static/projects/script/images/scene_layered_layer_panel_1.png",
                "placement": "left",
                "enter_at_seconds": 0.5,
                "animation": "pop_in",
            }
        ],
    )
    props = remotion_render._scene_to_input_props(scene, "script")
    assert props["visual_mode"] == "popup_sequence"
    assert "visual_treatment" not in props
    assert props["visual_layers"][0]["placement"] == "left"
    assert props["visual_layers"][0]["image_path"].endswith("scene_layered_layer_panel_1.png")


def test_scene_to_input_props_resolves_popup_crop_layer_urls(tmp_path, monkeypatch):
    monkeypatch.setattr(remotion_render, "DATA_DIR", tmp_path)
    popup_dir = tmp_path / "projects" / "script" / "popup_crops" / "scene_layered"
    image_dir = tmp_path / "projects" / "script" / "images"
    popup_dir.mkdir(parents=True)
    image_dir.mkdir(parents=True)
    (popup_dir / "crop_02_chat_bubble.png").write_bytes(b"fake crop")
    (image_dir / "scene_layered.png").write_bytes(b"wrong fallback image")
    scene = Scene(
        id="scene_layered",
        narration="A list appears.",
        visual_prompt="x",
        audio_duration_seconds=2.0,
        visual_mode="popup_sequence",
        visual_layers=[
            {
                "id": "chat_bubble",
                "type": "image",
                "asset_kind": "cutout",
                "image_url": "/static/projects/script/popup_crops/scene_layered/crop_02_chat_bubble.png",
                "placement": "left",
                "enter_at_seconds": 0.5,
                "animation": "pop_in",
            }
        ],
    )

    props = remotion_render._scene_to_input_props(scene, "script")

    assert props["visual_layers"][0]["image_path"].endswith(
        "/popup_crops/scene_layered/crop_02_chat_bubble.png"
    )


def test_multi_frame_scene_props_include_mode_and_frame_paths(tmp_path, monkeypatch):
    monkeypatch.setattr(remotion_render, "DATA_DIR", tmp_path)
    image_dir = tmp_path / "projects" / "script-1" / "images"
    image_dir.mkdir(parents=True)
    (image_dir / "scene-1_0.png").write_bytes(b"fake image 1")
    (image_dir / "scene-1_1.png").write_bytes(b"fake image 2")
    scene = Scene(
        id="scene-1",
        narration="First this, then that.",
        visual_prompt="Several examples.",
        visual_mode="multi_frame",
        frame_urls=[
            "/static/projects/script-1/images/scene-1_0.png",
            "/static/projects/script-1/images/scene-1_1.png",
        ],
        audio_duration_seconds=4.0,
    )

    props = remotion_render._scene_to_input_props(scene, "script-1")

    assert props["visual_mode"] == "multi_frame"
    assert props["frame_paths"]
    assert len(props["frame_paths"]) == 2


def test_continuous_scene_props_include_mode_and_frame_paths(tmp_path, monkeypatch):
    monkeypatch.setattr(remotion_render, "DATA_DIR", tmp_path)
    image_dir = tmp_path / "projects" / "script-1" / "images"
    image_dir.mkdir(parents=True)
    (image_dir / "scene-1_0.png").write_bytes(b"fake image 1")
    (image_dir / "scene-1_1.png").write_bytes(b"fake image 2")
    scene = Scene(
        id="scene-1",
        narration="The crack spreads.",
        visual_prompt="A spreading crack.",
        visual_mode="continuous",
        frame_urls=[
            "/static/projects/script-1/images/scene-1_0.png",
            "/static/projects/script-1/images/scene-1_1.png",
        ],
        audio_duration_seconds=4.0,
    )

    props = remotion_render._scene_to_input_props(scene, "script-1")

    assert props["visual_mode"] == "continuous"
    assert props["frame_paths"]
    assert len(props["frame_paths"]) == 2


def test_single_frame_multi_frame_scene_props_include_frame_path(tmp_path, monkeypatch):
    monkeypatch.setattr(remotion_render, "DATA_DIR", tmp_path)
    image_dir = tmp_path / "projects" / "script-1" / "images"
    image_dir.mkdir(parents=True)
    (image_dir / "scene-1_0.png").write_bytes(b"fake image")
    scene = Scene(
        id="scene-1",
        narration="One clear example.",
        visual_prompt="A single example.",
        visual_mode="multi_frame",
        frame_urls=[
            "/static/projects/script-1/images/scene-1_0.png",
        ],
        audio_duration_seconds=4.0,
    )

    props = remotion_render._scene_to_input_props(scene, "script-1")

    assert props["visual_mode"] == "multi_frame"
    assert props["frame_paths"]
    assert len(props["frame_paths"]) == 1
    assert props["frame_paths"][0].endswith("/static/projects/script-1/images/scene-1_0.png")
    assert props["image_path"].endswith("/static/projects/script-1/images/scene-1_0.png")


def test_single_frame_continuous_scene_props_include_frame_path(tmp_path, monkeypatch):
    monkeypatch.setattr(remotion_render, "DATA_DIR", tmp_path)
    image_dir = tmp_path / "projects" / "script-1" / "images"
    image_dir.mkdir(parents=True)
    (image_dir / "scene-1_0.png").write_bytes(b"fake image")
    scene = Scene(
        id="scene-1",
        narration="The first crack appears.",
        visual_prompt="A single progression frame.",
        visual_mode="continuous",
        frame_urls=[
            "/static/projects/script-1/images/scene-1_0.png",
        ],
        audio_duration_seconds=4.0,
    )

    props = remotion_render._scene_to_input_props(scene, "script-1")

    assert props["visual_mode"] == "continuous"
    assert props["frame_paths"]
    assert len(props["frame_paths"]) == 1
    assert props["frame_paths"][0].endswith("/static/projects/script-1/images/scene-1_0.png")
    assert props["image_path"].endswith("/static/projects/script-1/images/scene-1_0.png")


def test_chapter_marker_total_frames_use_full_ai_video_audio_duration(tmp_path, monkeypatch):
    monkeypatch.setattr(remotion_render, "DATA_DIR", tmp_path)
    monkeypatch.setattr(remotion_render, "_probe_video_duration", lambda _path: None)
    script_id = "script-1"
    _write_video_metadata(tmp_path, script_id, "scene-1", 5.0)
    content = ScriptContent(
        title="Test",
        segments=[
            Segment(
                name="Segment",
                scenes=[
                    Scene(
                        id="scene-1",
                        narration="Long narration.",
                        visual_prompt="Animated explainer.",
                        visual_mode="video",
                        audio_duration_seconds=12.0,
                    ),
                ],
            ),
        ],
    )

    _markers, total_frames = remotion_render._compute_chapter_markers(content, script_id, fps=30)

    assert total_frames == 360


def test_subtitle_render_fingerprint_has_no_removed_dossier_field():
    scene = Scene(
        id="scene-1",
        narration="A plain scene.",
        visual_prompt="A plain scene.",
        visual_mode="full_frame",
    )
    content = ScriptContent(
        title="Test",
        segments=[Segment(name="Segment", scenes=[scene])],
    )

    fingerprint = remotion_render.subtitle_render_fingerprint(content)
    assert "dossier" not in fingerprint["scenes"][0]
