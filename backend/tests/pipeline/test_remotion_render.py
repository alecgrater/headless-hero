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
        media_source="ai_video",
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
        media_source="ai_video",
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
        media_source="ai_video",
        audio_duration_seconds=7.0,
    )

    props = remotion_render._scene_to_input_props(scene, script_id)

    assert props["duration_seconds"] == 7.0


def test_scene_to_input_props_includes_visual_treatment_layers(tmp_path, monkeypatch):
    monkeypatch.setattr(remotion_render, "DATA_DIR", tmp_path)
    image_dir = tmp_path / "projects" / "script" / "images"
    image_dir.mkdir(parents=True)
    (image_dir / "scene_layered_layer_panel_1.png").write_bytes(b"fake image")
    scene = Scene(
        id="scene_layered",
        narration="A list appears.",
        visual_prompt="x",
        audio_duration_seconds=2.0,
        visual_treatment="popup_sequence",
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
    assert props["visual_treatment"] == "popup_sequence"
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
        visual_treatment="popup_sequence",
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
                        media_source="ai_video",
                        audio_duration_seconds=12.0,
                    ),
                ],
            ),
        ],
    )

    _markers, total_frames = remotion_render._compute_chapter_markers(content, script_id, fps=30)

    assert total_frames == 360
