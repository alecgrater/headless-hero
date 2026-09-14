"""Tests for Remotion render input helpers."""

import json
import subprocess

import pytest

from models.script import Scene, ScriptContent, Segment, VisualLayer, WordTimestamp
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


def test_scene_to_input_props_ignores_stale_images_for_text_only_captions_scene(tmp_path, monkeypatch):
    monkeypatch.setattr(remotion_render, "DATA_DIR", tmp_path)
    script_id = "script"
    image_dir = tmp_path / "projects" / script_id / "images"
    image_dir.mkdir(parents=True)
    (image_dir / "scene_001.png").write_bytes(b"stale caption prompt leak")
    (image_dir / "scene_001_f0.png").write_bytes(b"stale caption prompt leak")
    scene = Scene(
        id="scene_001",
        narration="The temporary job became the whole life.",
        visual_prompt="",
        visual_mode="captions",
        caption_text="The temporary job became the whole life",
        caption_emphasis="temporary",
        audio_duration_seconds=2.0,
    )

    props = remotion_render._scene_to_input_props(scene, script_id)

    assert props["visual_mode"] == "captions"
    assert props["image_path"] is None
    assert props["frame_paths"] is None


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
                    Scene(id="scene-2", narration="Punch.", visual_prompt="", subtitle_style="kinetic"),
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
            "full_frame_blink": None,
        },
        {
            "id": "scene-2",
            "subtitle_style": "kinetic",
            "visual_mode": "full_frame",
            "renderer_context": "",
            "stat_value": "",
            "stat_label": "",
            "stat_card_icon": None,
            "full_frame_blink": None,
        },
    ]


def test_render_fingerprint_tracks_full_frame_blink_metadata_changes():
    scene = Scene(
        id="scene-1",
        narration="Blink.",
        visual_prompt="Worker.",
        visual_mode="full_frame",
    )
    content = ScriptContent(title="Test", segments=[Segment(name="One", scenes=[scene])])
    baseline = remotion_render.subtitle_render_fingerprint(content)

    scene.visual_source_metadata = {
        "full_frame_blink": {
            "enabled": True,
            "action": "blink",
            "fingerprint": "abc",
            "anchor": {"detected": True, "eye_left": {"x": 0.4, "y": 0.3}},
            "review": {"status": "enabled", "reviewed_at": "2026-06-21T00:00:00+00:00"},
        }
    }
    enabled = remotion_render.subtitle_render_fingerprint(content)
    scene.visual_source_metadata = {
        "full_frame_blink": {
            "enabled": True,
            "action": "blink",
            "fingerprint": "def",
            "anchor": {"detected": True, "eye_left": {"x": 0.5, "y": 0.3}},
            "review": {"status": "enabled", "reviewed_at": "2026-06-21T00:00:00+00:00"},
        }
    }
    moved = remotion_render.subtitle_render_fingerprint(content)

    assert baseline["scenes"][0]["full_frame_blink"] is None
    assert enabled["scenes"][0]["full_frame_blink"]["anchor"]["eye_left"]["x"] == 0.4
    assert enabled != baseline
    assert moved != enabled


def test_scene_input_props_include_renderer_context():
    scene = Scene(
        id="s1",
        narration="He blinks at the whiteboard.",
        visual_prompt="Teacher character.",
        visual_mode="blink",
        blink_action="blink",
        renderer_context="indoor",
    )

    props = remotion_render._scene_to_input_props(scene, "script-1")

    assert props["renderer_context"] == "indoor"


def test_scene_input_props_include_blink_action():
    scene = Scene(
        id="s1",
        narration="He speaks.",
        visual_prompt="Teacher character.",
        visual_mode="full_frame",
    )

    props = remotion_render._scene_to_input_props(scene, "script-1")

    assert props["blink_action"] == ""


def test_scene_input_props_include_visual_layer_source_metadata():
    scene = Scene(
        id="s1",
        narration="Before versus after.",
        visual_prompt="Comparison.",
        visual_mode="comparison_board",
        visual_layers=[
            VisualLayer(
                id="s1_base",
                asset_kind="cutout",
                image_url="/static/projects/script-1/cutouts/s1/base.png",
                visual_source_metadata={
                    "source_type": "comparison_cutout",
                    "crop_box": {"x": 0.5, "y": 0.46},
                },
            )
        ],
    )

    props = remotion_render._scene_to_input_props(scene, "script-1")

    assert props["visual_layers"][0]["visual_source_metadata"]["source_type"] == "comparison_cutout"
    assert props["visual_layers"][0]["visual_source_metadata"]["crop_box"] == {"x": 0.5, "y": 0.46}


def test_scene_input_props_include_full_frame_blink_metadata():
    scene = Scene(
        id="s1",
        narration="He blinks.",
        visual_prompt="Worker.",
        visual_mode="full_frame",
        visual_source_metadata={
            "full_frame_blink": {
                "enabled": True,
                "action": "blink",
                "anchor": {"detected": True, "skin_fill": "#F0D2B4"},
                "review": {"status": "enabled", "reviewed_at": "2026-06-21T00:00:00+00:00"},
            }
        },
    )

    props = remotion_render._scene_to_input_props(scene, "script-1")

    assert props["full_frame_blink"]["enabled"] is True
    assert props["full_frame_blink"]["action"] == "blink"


def test_scene_input_props_suppresses_unreviewed_full_frame_blink():
    scene = Scene(
        id="scene_001",
        narration="A worker waits.",
        visual_prompt="Worker",
        image_url="/static/projects/script-1/images/scene_001.png",
        visual_source_metadata={
            "full_frame_blink": {
                "enabled": False,
                "action": "blink",
                "fingerprint": "abc",
                "anchor": {"detected": True},
                "review": {"status": "unreviewed"},
            }
        },
    )

    props = remotion_render._scene_to_input_props(scene, "script-1")

    assert props["full_frame_blink"] is None


def test_scene_input_props_includes_manually_enabled_full_frame_blink():
    scene = Scene(
        id="scene_001",
        narration="A worker waits.",
        visual_prompt="Worker",
        image_url="/static/projects/script-1/images/scene_001.png",
        visual_source_metadata={
            "full_frame_blink": {
                "enabled": True,
                "action": "blink",
                "fingerprint": "abc",
                "anchor": {"detected": True, "eye_left": {"x": 0.4, "y": 0.3}},
                "review": {"status": "enabled", "reviewed_at": "2026-06-21T00:00:00+00:00"},
            }
        },
    )

    props = remotion_render._scene_to_input_props(scene, "script-1")

    assert props["full_frame_blink"]["enabled"] is True
    assert props["full_frame_blink"]["anchor"]["eye_left"]["x"] == 0.4


def test_scene_input_props_suppresses_stale_non_full_frame_blink_metadata():
    scene = Scene(
        id="scene_001",
        narration="A worker waits.",
        visual_prompt="Worker",
        visual_mode="multi_frame",
        image_url="/static/projects/script-1/images/scene_001_f0.png",
        frame_urls=[
            "/static/projects/script-1/images/scene_001_f0.png",
            "/static/projects/script-1/images/scene_001_f1.png",
        ],
        visual_source_metadata={
            "full_frame_blink": {
                "enabled": True,
                "action": "blink",
                "fingerprint": "stale",
                "anchor": {"detected": True, "eye_left": {"x": 0.4, "y": 0.3}},
                "review": {"status": "enabled", "reviewed_at": "2026-06-21T00:00:00+00:00"},
            }
        },
    )

    props = remotion_render._scene_to_input_props(scene, "script-1")

    assert props["full_frame_blink"] is None
    assert remotion_render._full_frame_blink_fingerprint(scene) is None


def test_scene_input_props_resolves_style_preset_visual_layer_paths(tmp_path, monkeypatch):
    monkeypatch.setattr(remotion_render, "DATA_DIR", tmp_path)
    preset_id = "preset-billy"
    character_id = "character-billy"
    cutout_path = tmp_path / "style" / "presets" / preset_id / "characters" / f"{character_id}.cutout.png"
    cutout_path.parent.mkdir(parents=True)
    cutout_path.write_bytes(b"not a real png")
    scene = Scene(
        id="s1",
        narration="Billy contrasts two outcomes.",
        visual_prompt="Billy.",
        visual_mode="comparison_board",
        visual_layers=[
            VisualLayer(
                id="billy_base",
                asset_kind="cutout",
                image_url=f"/static/style/presets/{preset_id}/characters/{character_id}.cutout.png",
            )
        ],
    )

    props = remotion_render._scene_to_input_props(scene, "style-preset")

    assert props["visual_layers"][0]["image_path"].endswith(
        "/static/style/presets/preset-billy/characters/character-billy.cutout.png"
    )


def test_subtitle_render_fingerprint_includes_renderer_context_for_canvas_modes():
    scene = Scene(
        id="s1",
        narration="A small set of tools on the bench.",
        visual_prompt="Tools laid out.",
        visual_mode="popup_sequence",
        renderer_context="indoor",
    )
    content = ScriptContent(title="T", segments=[Segment(name="S", scenes=[scene])])

    fingerprint = remotion_render.subtitle_render_fingerprint(content)

    assert fingerprint["renderer_context_stage_version"] == "renderer-context-stage-v4"
    assert fingerprint["blink_renderer_version"] == "full-frame-blink-v1"
    assert fingerprint["scenes"][0]["renderer_context"] == "indoor"


def test_subtitle_settings_from_env_normalize_values(monkeypatch):
    monkeypatch.setenv("SUBTITLE_COVERAGE_MODE", "punchy")
    monkeypatch.setenv("SUBTITLE_STYLE_KINETIC_ENABLED", "true")

    settings = remotion_render.subtitle_settings_from_env()

    assert settings == {
        "coverage": "punchy",
        "enabled_styles": ["clean", "kinetic"],
        "kinetic_max_words": remotion_render.KINETIC_MAX_WORDS,
        "kinetic_max_span_seconds": remotion_render.KINETIC_MAX_SPAN_SECONDS,
    }


def test_subtitle_settings_keep_clean_when_kinetic_is_disabled(monkeypatch):
    """Clean is the floor of the catalogue — it has no toggle and can never drop out."""
    monkeypatch.delenv("SUBTITLE_COVERAGE_MODE", raising=False)
    monkeypatch.setenv("SUBTITLE_STYLE_KINETIC_ENABLED", "false")

    settings = remotion_render.subtitle_settings_from_env()

    assert settings["coverage"] == "all"
    assert settings["enabled_styles"] == ["clean"]


def test_apply_subtitle_coverage_limits_punchy_scenes(monkeypatch):
    monkeypatch.setenv("SUBTITLE_COVERAGE_MODE", "punchy")
    monkeypatch.setenv("SUBTITLE_STYLE_KINETIC_ENABLED", "true")
    content = ScriptContent(
        title="Test",
        segments=[
            Segment(
                name="One",
                scenes=[
                    Scene(id="title", narration="Title.", visual_prompt="", is_title_card=True),
                    Scene(id="plain-1", narration="A calm explanatory line.", visual_prompt=""),
                    Scene(id="plain-2", narration="Another calm explanatory line.", visual_prompt=""),
                    # Carries a figure — the strongest coverage signal. Deliberately a
                    # long scene, so this also pins that coverage does not rank on
                    # brevity (which is the style router's job, not coverage's).
                    Scene(
                        id="figure",
                        narration="In 1978 researchers tracked 22 lottery winners for a year.",
                        visual_prompt="",
                    ),
                    Scene(id="caption", narration="The real cost.", visual_prompt="", visual_mode="captions"),
                ],
            )
        ],
    )

    styles = remotion_render._subtitle_styles_for_render(content)

    assert styles["figure"] == "auto"
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


class _FakeProc:
    """Minimal Popen stand-in that exits 0 after emitting merged output lines."""

    def __init__(self, lines: list[str]) -> None:
        self.stdout = iter(f"{line}\n" for line in lines)
        self.returncode = 0

    def wait(self, timeout: float | None = None) -> int:  # noqa: ARG002
        return self.returncode


def _patch_remotion_subprocess(monkeypatch, lines: list[str], on_run=None) -> dict:
    """Replace Popen with a fake, returning the kwargs it was called with."""
    captured: dict = {}

    def fake_popen(*_args, **kwargs):
        captured.update(kwargs)
        if on_run is not None:
            on_run()
        return _FakeProc(lines)

    monkeypatch.setattr(remotion_render.subprocess, "Popen", fake_popen)
    monkeypatch.setattr(remotion_render, "register_process", lambda *_a, **_k: None)
    monkeypatch.setattr(remotion_render, "unregister_process", lambda *_a, **_k: None)
    return captured


def test_run_remotion_raises_when_process_exits_zero_without_output(tmp_path, monkeypatch):
    """Remotion can exit 0 having written nothing; that must fail loudly here."""
    captured = _patch_remotion_subprocess(monkeypatch, ["Bundling...", "gave up"])

    with pytest.raises(RuntimeError, match="without writing 0_raw.mkv"):
        remotion_render._run_remotion(
            composition_id="ShortFormVideo",
            props_path=tmp_path / "props.json",
            output_path=tmp_path / "0_raw.mkv",
        )

    # Both streams must land in the one reader: an unread pipe deadlocks the render.
    assert captured["stdout"] is subprocess.PIPE
    assert captured["stderr"] is subprocess.STDOUT


def test_run_remotion_discards_stale_output_from_a_previous_run(tmp_path, monkeypatch):
    """A leftover file from a killed render must not pass as this run's output."""
    output_path = tmp_path / "0_raw.mkv"
    output_path.write_bytes(b"stale render")
    seen: dict[str, bool] = {}
    _patch_remotion_subprocess(
        monkeypatch,
        ["gave up"],
        on_run=lambda: seen.__setitem__("existed_at_launch", output_path.exists()),
    )

    with pytest.raises(RuntimeError, match="without writing 0_raw.mkv"):
        remotion_render._run_remotion(
            composition_id="ShortFormVideo",
            props_path=tmp_path / "props.json",
            output_path=output_path,
        )

    assert seen["existed_at_launch"] is False


def test_run_remotion_succeeds_when_output_is_written(tmp_path, monkeypatch):
    output_path = tmp_path / "0_raw.mkv"
    _patch_remotion_subprocess(
        monkeypatch,
        ["Rendered 100%"],
        on_run=lambda: output_path.write_bytes(b"rendered video"),
    )

    remotion_render._run_remotion(
        composition_id="ShortFormVideo",
        props_path=tmp_path / "props.json",
        output_path=output_path,
    )


# --- Two-router invariant -----------------------------------------------------
#
# resolve_subtitle_style (Python, drives the dev-dashboard split log) and
# resolveSubtitleStyle (TS, drives the actual render) must agree. This table is the
# literal mirror of the cases in frontend/src/remotion/SubtitleRouting.test.ts — when
# one side changes, the other fails here rather than in a rendered MP4.

def _timed_scene(word_count: int, span_ms: int, **kwargs) -> Scene:
    step = span_ms / word_count
    return Scene(
        id=kwargs.pop("id", "scene"),
        narration=kwargs.pop("narration", " ".join(f"w{i}" for i in range(word_count))),
        visual_prompt="",
        word_timestamps=[
            WordTimestamp(word=f"w{i}", start_ms=round(i * step), end_ms=round((i + 1) * step))
            for i in range(word_count)
        ],
        **kwargs,
    )


_TWO_STYLE_SETTINGS = {
    "coverage": "all",
    "enabled_styles": ["clean", "kinetic"],
    "kinetic_max_words": remotion_render.KINETIC_MAX_WORDS,
    "kinetic_max_span_seconds": remotion_render.KINETIC_MAX_SPAN_SECONDS,
}


@pytest.mark.parametrize(
    "scene,expected",
    [
        (_timed_scene(2, 1000), "kinetic"),
        (_timed_scene(6, 3000), "kinetic"),          # both boundaries inclusive
        (_timed_scene(7, 1500), "clean"),            # one word over the cap
        (_timed_scene(6, 3100), "clean"),            # just over the span cap
        (_timed_scene(4, 7200), "clean"),            # short but drawn out
        (_timed_scene(20, 2400), "clean"),           # fast delivery is not a term
        (_timed_scene(12, 5000), "clean"),
        (_timed_scene(2, 1000, subtitle_style="clean"), "clean"),
        (_timed_scene(12, 5000, subtitle_style="kinetic"), "kinetic"),
        (_timed_scene(2, 1000, subtitle_style="none"), "none"),
        (_timed_scene(2, 1000, is_title_card=True), "none"),
        (_timed_scene(2, 1000, visual_mode="stat_card"), "none"),
        (_timed_scene(2, 1000, visual_mode="captions"), "none"),
    ],
)
def test_resolve_subtitle_style_matches_the_ts_router_table(scene, expected):
    assert remotion_render.resolve_subtitle_style(scene, _TWO_STYLE_SETTINGS) == expected


def test_resolve_subtitle_style_without_timings_is_clean():
    scene = Scene(id="scene", narration="No timings here.", visual_prompt="")
    assert remotion_render.resolve_subtitle_style(scene, _TWO_STYLE_SETTINGS) == "clean"


def test_resolve_subtitle_style_falls_back_to_clean_when_kinetic_disabled():
    settings = {**_TWO_STYLE_SETTINGS, "enabled_styles": ["clean"]}
    assert remotion_render.resolve_subtitle_style(_timed_scene(2, 1000), settings) == "clean"
    # An explicit kinetic override is clamped too.
    assert remotion_render.resolve_subtitle_style(
        _timed_scene(12, 5000, subtitle_style="kinetic"), settings,
    ) == "clean"


def test_resolve_subtitle_style_suppresses_when_no_styles_enabled():
    settings = {**_TWO_STYLE_SETTINGS, "enabled_styles": []}
    assert remotion_render.resolve_subtitle_style(_timed_scene(2, 1000), settings) == "none"


def test_resolve_subtitle_style_honors_backend_supplied_thresholds():
    loosened = {**_TWO_STYLE_SETTINGS, "kinetic_max_words": 8, "kinetic_max_span_seconds": 3.0}
    assert remotion_render.resolve_subtitle_style(_timed_scene(8, 2000), _TWO_STYLE_SETTINGS) == "clean"
    assert remotion_render.resolve_subtitle_style(_timed_scene(8, 2000), loosened) == "kinetic"


def test_legacy_burst_scenes_load_as_auto_and_reroute():
    """Stored burst JSON must re-route, not pin to a style.

    Re-adding "burst" to models.script.SUBTITLE_STYLES, or changing the validator
    fallback to "clean", would silently pin every legacy punch beat.
    """
    scene = Scene.model_validate(
        {"id": "s", "narration": "Trophy.", "visual_prompt": "", "subtitle_style": "burst"}
    )
    assert scene.subtitle_style == "auto"

    punchy = _timed_scene(2, 1000)
    punchy.subtitle_style = "burst"
    assert punchy.subtitle_style == "auto"
    assert remotion_render.resolve_subtitle_style(punchy, _TWO_STYLE_SETTINGS) == "kinetic"


def test_punchy_coverage_scorer_stays_orthogonal_to_the_style_router():
    """Coverage must not rank on the kinetic rule.

    When it did, every punch beat outranked every other scene, so punchy mode filled
    almost entirely with kinetic and "the exception" became 83% of subtitled scenes
    (against 17% under coverage="all"). The scorer therefore carries no word-count or
    span term: two scenes that differ only in length must score identically.
    """
    short = _timed_scene(3, 1200, narration="Her finding.")
    long_ = _timed_scene(24, 9000, narration="Her finding.")
    assert remotion_render._subtitle_punch_score(short) == remotion_render._subtitle_punch_score(long_)

    punch_beat = _timed_scene(3, 1200, narration="Her finding.")
    figure_scene = _timed_scene(20, 7000, narration="Roughly 40 percent of them never recover.")
    assert remotion_render._subtitle_punch_score(figure_scene) > remotion_render._subtitle_punch_score(punch_beat)


def test_punchy_coverage_kinetic_share_tracks_the_all_coverage_share(monkeypatch):
    """Punchy must neither sweep up every punch beat nor exclude them all.

    Both are real failure modes and a one-sided assertion misses one of them: the
    original scorer swept them up (83% kinetic), while a corpus where a digit-bearing
    scene wins every single window excludes them entirely (0%). The bounds below are
    absolute rather than a ratio of a ratio — with a 20% budget one scene moves the
    share by ~8 points, so a tight ratio band is false precision.
    """
    monkeypatch.setenv("SUBTITLE_STYLE_KINETIC_ENABLED", "true")
    # 30 scenes -> 6 windows of 5. Every window holds one punch beat; only the first
    # four also hold a figure-bearing scene, so figures win those and punch beats win
    # the last two. That exercises both sides of the band.
    scenes = []
    for i in range(30):
        window = i // 5
        if i % 5 == 0:
            scenes.append(_timed_scene(3, 1200, id=f"punch-{i}", narration="Her finding?"))
        elif i % 5 == 1 and window < 4:
            scenes.append(
                _timed_scene(20, 8000, id=f"figure-{i}", narration=f"In 19{70 + i} they tracked the cohort.")
            )
        else:
            scenes.append(
                _timed_scene(20, 8000, id=f"plain-{i}", narration="A calm explanatory line follows.")
            )
    content = ScriptContent(title="T", segments=[Segment(name="One", scenes=scenes)])

    def kinetic_count(mode: str) -> tuple[int, int]:
        monkeypatch.setenv("SUBTITLE_COVERAGE_MODE", mode)
        styles = remotion_render._subtitle_styles_for_render(content)
        chosen = [sc for sc in scenes if styles.get(sc.id) != "none"]
        assert chosen, f"{mode} coverage selected nothing"
        kinetic = [
            sc for sc in chosen
            if remotion_render.resolve_subtitle_style(sc, _TWO_STYLE_SETTINGS) == "kinetic"
        ]
        return len(kinetic), len(chosen)

    all_kinetic, all_total = kinetic_count("all")
    punchy_kinetic, punchy_total = kinetic_count("punchy")

    assert (all_kinetic, all_total) == (6, 30)
    # Lower bound: punchy must still reach punch beats at all.
    assert punchy_kinetic > 0
    # Upper bound: kinetic stays a minority of the subtitled scenes.
    assert punchy_kinetic / punchy_total <= 0.5
    # And punchy must never select more punch beats than exist under full coverage.
    assert punchy_kinetic <= all_kinetic


def test_subtitle_style_split_log_separates_every_suppression_reason(monkeypatch, caplog):
    """The four buckets are the point of the line — an author pin, a coverage drop,
    and a structurally ineligible scene are different facts."""
    monkeypatch.setenv("SUBTITLE_COVERAGE_MODE", "all")
    monkeypatch.setenv("SUBTITLE_STYLE_KINETIC_ENABLED", "true")
    scenes = [
        _timed_scene(20, 8000, id="clean-1", narration="A calm explanatory line follows."),
        _timed_scene(3, 1200, id="kinetic-1", narration="Her finding."),
        _timed_scene(20, 8000, id="pinned", narration="Author said no.", subtitle_style="none"),
        Scene(id="title", narration="Title.", visual_prompt="", is_title_card=True),
        Scene(id="cap", narration="The real cost.", visual_prompt="", visual_mode="captions"),
    ]
    settings = remotion_render.subtitle_settings_from_env()
    styles = {"clean-1": "auto", "kinetic-1": "auto", "pinned": "none", "dropped": "none"}

    with caplog.at_level("INFO", logger=remotion_render.logger.name):
        remotion_render._log_subtitle_style_split("script-1", scenes, styles, settings)

    line = caplog.text
    assert "1 clean, 1 kinetic (50% of 2 subtitled)" in line
    assert "0 coverage-suppressed" in line
    assert "1 author-suppressed" in line
    assert "2 ineligible" in line


def test_subtitle_style_split_log_counts_coverage_drops_only_under_punchy(monkeypatch, caplog):
    monkeypatch.setenv("SUBTITLE_COVERAGE_MODE", "punchy")
    monkeypatch.setenv("SUBTITLE_STYLE_KINETIC_ENABLED", "true")
    scenes = [
        _timed_scene(20, 8000, id="kept", narration="A calm explanatory line follows."),
        _timed_scene(20, 8000, id="dropped", narration="Another calm explanatory line."),
    ]
    settings = remotion_render.subtitle_settings_from_env()

    with caplog.at_level("INFO", logger=remotion_render.logger.name):
        remotion_render._log_subtitle_style_split(
            "script-1", scenes, {"kept": "auto", "dropped": "none"}, settings,
        )

    assert "1 coverage-suppressed" in caplog.text
    assert "0 author-suppressed" in caplog.text


def test_punchy_coverage_spreads_across_the_script(monkeypatch):
    """The budget must reach the end of the video.

    Ranking the whole script and taking the top N put every selection in the first
    half, because the scorer's terms are sparse and most slots were ties broken by
    array position. On a real 59-scene script the back 45% got nothing.
    """
    monkeypatch.setenv("SUBTITLE_COVERAGE_MODE", "punchy")
    # Deliberately flat: every scene scores 0, so only the windowing can spread these.
    scenes = [
        _timed_scene(20, 8000, id=f"s{i:02d}", narration="A calm explanatory line follows.")
        for i in range(60)
    ]
    content = ScriptContent(title="T", segments=[Segment(name="One", scenes=scenes)])

    styles = remotion_render._subtitle_styles_for_render(content)
    picked = [i for i, sc in enumerate(scenes) if styles.get(sc.id) != "none"]

    assert len(picked) == 12
    # Every window contributes, so the selection reaches the final tenth of the script.
    assert max(picked) >= len(scenes) * 0.9
    assert min(picked) <= len(scenes) * 0.1
    # And neither half is starved.
    first_half = [i for i in picked if i < len(scenes) / 2]
    assert 4 <= len(first_half) <= 8


def test_punchy_coverage_prefers_the_best_scene_inside_each_window(monkeypatch):
    """Score decides which scene wins a window; position only decides the window."""
    monkeypatch.setenv("SUBTITLE_COVERAGE_MODE", "punchy")
    scenes = [
        _timed_scene(20, 8000, id=f"s{i:02d}", narration="A calm explanatory line follows.")
        for i in range(10)
    ]
    # The figure-bearing scene is last in the script, where the old global ranking's
    # position tie-break would have put it dead last. It must still win its window.
    scenes[-1] = _timed_scene(20, 8000, id="s09", narration="Exactly 40 percent never recover.")
    content = ScriptContent(title="T", segments=[Segment(name="One", scenes=scenes)])

    styles = remotion_render._subtitle_styles_for_render(content)
    assert styles["s09"] == "auto"
