"""A failed-generation placeholder must never be reused as if it were an image.

It used to be written with a prompt marker, so every later attempt was a cache
hit, completion checks counted the scene as done, and the "Image generation
failed" card could ship in the video.
"""

import json

from PIL import Image

from models.script import Scene, ScriptContent, Script, Segment
from pipeline import image_gen, remotion_render


def _isolate(monkeypatch, tmp_path, calls):
    monkeypatch.setattr(image_gen, "DATA_DIR", tmp_path)
    monkeypatch.delenv("IMAGE_SCRAPER_FALLBACK_ENABLED", raising=False)
    monkeypatch.setattr(image_gen, "record_fallback", lambda **_kwargs: None)
    monkeypatch.setattr(
        image_gen, "_compose_image_prompt_context",
        lambda *, visual_prompt, script_id, style_guide, contains_person: (f"P:{visual_prompt}", None, None),
    )

    def flaky_generate_image(prompt, **_kwargs):
        calls.append(prompt)
        if len(calls) == 1:
            raise RuntimeError("provider down")
        out = tmp_path / f"gen_{len(calls)}.png"
        Image.new("RGB", (2, 2), "green").save(out)
        return str(out)

    monkeypatch.setattr(image_gen, "generate_image", flaky_generate_image)


def test_a_failed_generation_is_not_cached_and_the_next_attempt_regenerates(monkeypatch, tmp_path):
    calls = []
    _isolate(monkeypatch, tmp_path, calls)
    images = tmp_path / "projects" / "s1" / "images"

    _, _, first = image_gen.generate_scene_image("scene_001", "A radar room", "s1")
    assert first["source_type"] == "placeholder"
    assert not (images / "scene_001.prompt").exists()

    _, _, second = image_gen.generate_scene_image("scene_001", "A radar room", "s1")
    assert len(calls) == 2
    assert second["source_type"] == "ai_generated"
    assert (images / "scene_001.prompt").exists()


def test_an_old_placeholder_with_a_marker_is_regenerated(monkeypatch, tmp_path):
    # Placeholders written before this fix still carry a matching marker.
    calls = ["already failed once"]
    _isolate(monkeypatch, tmp_path, calls)
    images = tmp_path / "projects" / "s1" / "images"
    images.mkdir(parents=True)
    Image.new("RGB", (2, 2), "gray").save(images / "scene_001.png")
    (images / "scene_001.source.json").write_text(json.dumps({"source_type": "placeholder"}))
    (images / "scene_001.prompt").write_text(image_gen._marker_payload("P:A radar room"))

    _, _, metadata = image_gen.generate_scene_image("scene_001", "A radar room", "s1")
    assert metadata["source_type"] == "ai_generated"
    assert len(calls) == 2


def test_the_render_net_regenerates_a_placeholder_scene(monkeypatch):
    content = ScriptContent(title="T", segments=[Segment(name="S", scenes=[
        Scene(
            id="scene_001", narration="A radar room.", visual_prompt="A radar room", visual_mode="full_frame",
            image_url="/static/projects/s/images/scene_001.png",
            visual_source_metadata={"source_type": "placeholder", "fallback": True},
        ),
    ])])
    generated = []

    def fake_generate_scene_image(*, scene_id, visual_prompt, script_id, **_kwargs):
        generated.append(scene_id)
        return (f"/static/projects/{script_id}/images/{scene_id}.png", visual_prompt, {"source_type": "ai_generated"})

    monkeypatch.setattr("pipeline.image_gen.generate_scene_image", fake_generate_scene_image)
    monkeypatch.setattr(remotion_render, "_persist_repaired_scene_images", lambda *_args: None)

    assert remotion_render.ensure_renderable_scene_images("s", content) == 1
    assert generated == ["scene_001"]
    assert content.all_scenes()[0].visual_source_metadata == {"source_type": "ai_generated"}
