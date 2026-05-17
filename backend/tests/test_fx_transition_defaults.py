"""Regression tests for scene transition defaults."""

from api.fx import _count_fx_generation_targets
from models.script import Scene, ScriptContent
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
