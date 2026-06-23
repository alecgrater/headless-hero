"""Regression tests for scene transition defaults."""

from api.fx import _build_scene_fx_data, _count_fx_generation_targets
from models.script import Scene, ScriptContent
from pipeline import fx_generator
from pipeline.render_phases import _apply_fx_results


def test_scene_defaults_null_transition_to_cut():
    scene = Scene.model_validate(
        {
            "id": "scene_001",
            "narration": "A test scene.",
            "visual_prompt": "A simple image.",
            "transition_in": None,
        }
    )

    assert scene.transition_in == "cut"


def test_scene_defaults_unknown_transition_to_cut():
    scene = Scene.model_validate(
        {
            "id": "scene_001",
            "narration": "A test scene.",
            "visual_prompt": "A simple image.",
            "transition_in": "spin",
        }
    )

    assert scene.transition_in == "cut"


def test_fx_generator_defaults_null_transition_to_cut(monkeypatch):
    def fake_chat(**_kwargs):
        return """
        {
          "scenes": [
            {
              "id": "scene_001",
              "fx": { "drift": null, "zoom_punch": null },
              "transition_in": null
            }
          ]
        }
        """

    monkeypatch.setattr(fx_generator, "chat", fake_chat)

    result = fx_generator.generate_scene_fx(
        {
            "id": "scene_001",
            "visual_beat": "aha_subtitle",
            "duration_seconds": 5,
        },
        script_id="test_script",
    )

    assert result["transition_in"] == "cut"


def test_fx_generator_suppresses_camera_fx_for_comparison_and_popup_modes(monkeypatch):
    def fake_chat(**_kwargs):
        return """
        {
          "scenes": [
            {
              "id": "scene_001",
              "fx": {
                "drift": { "motion": "zoom_in", "intensity": 0.07, "anchor": "center" },
                "zoom_punch": { "trigger_frame": 12, "scale": 1.06 }
              },
              "transition_in": "wipe"
            }
          ]
        }
        """

    monkeypatch.setattr(fx_generator, "chat", fake_chat)

    for visual_mode in ("comparison_board", "popup_sequence"):
        result = fx_generator.generate_scene_fx(
            {
                "id": "scene_001",
                "visual_mode": visual_mode,
                "visual_beat": visual_mode,
                "duration_seconds": 18,
            },
            script_id="test_script",
        )

        assert result["fx"] == {"drift": None, "zoom_punch": None}
        assert result["transition_in"] == "cut"


def test_scene_fx_payload_includes_visual_mode():
    scene = Scene(
        id="scene_001",
        narration="Two outcomes sit side by side.",
        visual_prompt="A comparison.",
        visual_mode="comparison_board",
    )

    data = _build_scene_fx_data(scene, type("Segment", (), {"name": "Segment"})(), 0, 0, 0, 1)

    assert data["visual_mode"] == "comparison_board"
    assert data["visual_beat"] == "comparison_board"


def test_export_fx_persistence_updates_sanitized_transition_in():
    content = ScriptContent.model_validate(
        {
            "title": "Test",
            "segments": [
                {
                    "name": "Segment",
                    "scenes": [
                        {
                            "id": "scene_001",
                            "narration": "Two choices split the screen.",
                            "visual_prompt": "A comparison.",
                            "visual_mode": "comparison_board",
                            "transition_in": "wipe",
                        },
                    ],
                }
            ],
        }
    )

    _apply_fx_results(
        content,
        {
            "scene_001": {
                "fx": {"drift": None, "zoom_punch": None},
                "transition_in": "cut",
            }
        },
    )

    scene = content.segments[0].scenes[0]
    assert scene.fx is not None
    assert scene.fx.drift is None
    assert scene.fx.zoom_punch is None
    assert scene.transition_in == "cut"


def test_missing_fx_targets_only_missing_non_title_scenes():
    content = ScriptContent.model_validate(
        {
            "title": "Test",
            "segments": [
                {
                    "name": "Segment",
                    "scenes": [
                        {
                            "id": "title_001",
                            "narration": "Title",
                            "visual_prompt": "",
                            "is_title_card": True,
                        },
                        {
                            "id": "scene_001",
                            "narration": "Already has FX.",
                            "visual_prompt": "Image",
                            "fx": {"drift": None, "zoom_punch": None},
                        },
                        {
                            "id": "scene_002",
                            "narration": "Needs FX.",
                            "visual_prompt": "Image",
                        },
                    ],
                }
            ],
        }
    )

    assert _count_fx_generation_targets(content, missing_only=True) == 1
    assert _count_fx_generation_targets(content, missing_only=False) == 3
