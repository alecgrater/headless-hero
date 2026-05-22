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


def test_video_scene_duration_caps_to_shorter_clip_metadata(tmp_path, monkeypatch):
    monkeypatch.setattr(remotion_render, "DATA_DIR", tmp_path)
    monkeypatch.setattr(remotion_render, "_probe_video_duration", lambda _path: None)
    script_id = "script-1"
    _write_video_metadata(tmp_path, script_id, "scene-1", 5.0)
    scene = Scene(
        id="scene-1",
        narration="Long narration.",
        visual_prompt="Animated explainer.",
        media_source="ai_video",
        audio_duration_seconds=12.0,
    )

    props = remotion_render._scene_to_input_props(scene, script_id)

    assert props["duration_seconds"] == 5.0
    assert props["media_type"] == "video"
    assert props["video_path"].endswith("/static/projects/script-1/videos/scene-1.mp4")


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


def test_chapter_marker_total_frames_use_capped_video_duration(tmp_path, monkeypatch):
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

    assert total_frames == 150
