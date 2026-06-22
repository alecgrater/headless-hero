from pathlib import Path

from PIL import Image

from integrations.google_image_client import GoogleBatchImageResult
from pipeline import image_gen


def _write_png(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    Image.new("RGB", (2, 2), "red").save(path)


def test_generate_batch_with_google_batch_routes_eligible_scene(monkeypatch, tmp_path):
    monkeypatch.setattr(image_gen, "DATA_DIR", tmp_path)
    generated = tmp_path / "generated.png"
    _write_png(generated)
    captured_requests = []

    def fake_batch(requests, script_id):
        captured_requests.extend(requests)
        return [GoogleBatchImageResult(key=requests[0].key, image_path=str(generated))]

    monkeypatch.setattr(image_gen, "generate_images_batch", fake_batch)

    results = image_gen.generate_batch_with_google_batch(
        scenes=[
            {
                "scene_id": "scene_001",
                "visual_prompt": "A bright classroom",
                "visual_mode": "full_frame",
                "contains_person": False,
            }
        ],
        script_id="script-1",
    )

    assert len(captured_requests) == 1
    assert captured_requests[0].key == "scene_001"
    assert captured_requests[0].prompt
    assert results[0]["image_url"] == "/static/projects/script-1/images/scene_001.png"
    assert (tmp_path / "projects" / "script-1" / "images" / "scene_001.png").exists()
    assert (tmp_path / "projects" / "script-1" / "images" / "scene_001.prompt").exists()


def test_generate_batch_with_google_batch_keeps_layered_mode_standard(monkeypatch, tmp_path):
    monkeypatch.setattr(image_gen, "DATA_DIR", tmp_path)
    calls = {"batch": 0, "standard": 0}

    def fake_batch(*_args, **_kwargs):
        calls["batch"] += 1
        return []

    def fake_standard(scene, script_id, width, height, style_guide):
        calls["standard"] += 1
        return {
            "scene_id": scene["scene_id"],
            "image_url": None,
            "frame_urls": [],
            "video_url": "",
            "prompt_used": None,
            "error": None,
        }

    monkeypatch.setattr(image_gen, "generate_images_batch", fake_batch)
    monkeypatch.setattr(image_gen, "_generate_one_scene", fake_standard)

    results = image_gen.generate_batch_with_google_batch(
        scenes=[
            {
                "scene_id": "scene_001",
                "visual_prompt": "A popup sequence",
                "visual_mode": "popup_sequence",
                "visual_layers": [{"id": "item_1", "prompt": "An object"}],
            }
        ],
        script_id="script-1",
    )

    assert calls == {"batch": 0, "standard": 1}
    assert results[0]["scene_id"] == "scene_001"

