"""Regression tests for scene transition defaults."""

from models.script import Scene
from pipeline import fx_generator


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
