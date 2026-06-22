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


def test_generate_scene_image_rejects_caption_typography_prompt_before_model_call(monkeypatch):
    called = False

    def fake_generate_image(*args, **kwargs):
        nonlocal called
        called = True
        raise AssertionError("generate_image should not be called")

    monkeypatch.setattr(image_gen, "generate_image", fake_generate_image)

    try:
        image_gen.generate_scene_image(
            scene_id="scene_089",
            visual_prompt=(
                "[METAPHOR] Bold flat caption text on a dark background -- no imagery, "
                "just the words in clean sans-serif against near-black."
            ),
            script_id="test-script",
            force=True,
        )
    except RuntimeError as exc:
        assert "renderer-owned caption text" in str(exc)
    else:
        raise AssertionError("Expected caption typography prompt to be rejected")

    assert called is False


def test_generate_scene_frames_v2_rejects_caption_typography_search_query(monkeypatch):
    called = False

    def fake_generate_image(*args, **kwargs):
        nonlocal called
        called = True
        raise AssertionError("generate_image should not be called")

    monkeypatch.setattr(image_gen, "generate_image", fake_generate_image)

    try:
        image_gen.generate_scene_frames_v2(
            scene_id="scene_091",
            visual_prompt="",
            frame_directives=[
                {
                    "prompt": "",
                    "search_query": "caption text on a dark background",
                    "source": "ai_generated",
                }
            ],
            script_id="test-script",
            force=True,
        )
    except RuntimeError as exc:
        assert "renderer-owned caption text" in str(exc)
    else:
        raise AssertionError("Expected caption typography search_query to be rejected")

    assert called is False
