"""Tests for image-generation prompt boundary guards."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from pipeline import image_gen


def test_image_generation_rejects_caption_typography_prompt_before_model_call(monkeypatch):
    called = False

    def fake_generate_scene_image(*args, **kwargs):
        nonlocal called
        called = True
        return "/static/projects/test/images/bad.png", "prompt", None

    monkeypatch.setattr(image_gen, "generate_scene_image", fake_generate_scene_image)

    result = image_gen.generate_scene_visual(
        {
            "scene_id": "scene_089",
            "visual_mode": "full_frame",
            "visual_prompt": (
                "[METAPHOR] Bold flat caption text on a dark background -- no imagery, "
                "just the words in clean sans-serif against near-black."
            ),
            "frame_directives": [],
            "contains_person": False,
        },
        script_id="test-script",
    )

    assert called is False
    assert result["image_url"] is None
    assert "renderer-owned caption text" in str(result["error"])
