"""Tests for image provider routing."""

import pytest


@pytest.fixture(autouse=True)
def _cloud_by_default(monkeypatch):
    """Every test starts in cloud mode unless it opts into Local Mode."""
    monkeypatch.setenv("LOCAL_MODELS_ENABLED", "false")
    for modality in ("TEXT", "IMAGE", "VOICE"):
        monkeypatch.delenv(f"LOCAL_{modality}_MODE", raising=False)


def _enable_local_images(monkeypatch):
    monkeypatch.setenv("LOCAL_MODELS_ENABLED", "true")
    monkeypatch.delenv("LOCAL_IMAGE_MODE", raising=False)


def test_google_provider_routes_to_gemini(monkeypatch):
    from integrations import image_client
    from integrations import google_image_client

    captured = {}

    def fake_generate_image(prompt, **kwargs):
        captured["prompt"] = prompt
        captured["kwargs"] = kwargs
        return "/tmp/generated.png"

    monkeypatch.setenv("IMAGE_PROVIDER", "google")
    monkeypatch.setattr(google_image_client, "generate_image", fake_generate_image)

    result = image_client.generate_image(
        "a scene",
        width=123,
        height=456,
        reference_image_path="/tmp/character.png",
        style_reference_path="/tmp/style.png",
        original_prompt="raw scene",
        script_id="script-1",
    )

    assert result == "/tmp/generated.png"
    assert captured == {
        "prompt": "a scene",
        "kwargs": {
            "width": 123,
            "height": 456,
            "reference_image_path": "/tmp/character.png",
            "style_reference_path": "/tmp/style.png",
            "original_prompt": "raw scene",
            "script_id": "script-1",
        },
    }


def test_removed_replicate_provider_falls_back_to_gemini(monkeypatch):
    from integrations import image_client
    from integrations import google_image_client

    captured = {}

    def fake_generate_image(prompt, **kwargs):
        captured["kwargs"] = kwargs
        return "/tmp/fallback.png"

    monkeypatch.setenv("IMAGE_PROVIDER", "replicate")
    monkeypatch.setattr(google_image_client, "generate_image", fake_generate_image)

    result = image_client.generate_image(
        "a scene",
        style_reference_path="/tmp/style.png",
        original_prompt="raw scene",
    )

    assert result == "/tmp/fallback.png"
    assert captured["kwargs"]["style_reference_path"] == "/tmp/style.png"
    assert captured["kwargs"]["original_prompt"] == "raw scene"


def test_local_mode_routes_generate_image_to_comfyui(monkeypatch):
    _enable_local_images(monkeypatch)
    from integrations import image_client, local_image_client

    called: dict[str, object] = {}

    def fake(prompt, **kwargs):
        called["prompt"] = prompt
        called["kwargs"] = kwargs
        return "/tmp/local.png"

    monkeypatch.setattr(local_image_client, "generate_image", fake)

    assert image_client.generate_image("hello", width=64, height=64) == "/tmp/local.png"
    assert called["prompt"] == "hello"


def test_local_mode_beats_a_stale_image_provider_setting(monkeypatch):
    _enable_local_images(monkeypatch)
    monkeypatch.setenv("IMAGE_PROVIDER", "google")
    from integrations import image_client, local_image_client

    monkeypatch.setattr(local_image_client, "generate_image", lambda *a, **k: "/tmp/local.png")
    assert image_client.generate_image("hello", width=64, height=64) == "/tmp/local.png"


def test_image_pinned_cloud_still_uses_google(monkeypatch):
    monkeypatch.setenv("LOCAL_MODELS_ENABLED", "true")
    monkeypatch.setenv("LOCAL_IMAGE_MODE", "cloud")
    from integrations import google_image_client, image_client

    monkeypatch.setattr(google_image_client, "generate_image", lambda *a, **k: "/tmp/google.png")
    assert image_client.generate_image("hello", width=64, height=64) == "/tmp/google.png"


def test_transform_with_references_routes_by_mode(monkeypatch):
    from integrations import google_image_client, image_client, local_image_client

    monkeypatch.setattr(google_image_client, "transform_with_references", lambda *a, **k: "/tmp/google.png")
    monkeypatch.setattr(local_image_client, "transform_with_references", lambda *a, **k: "/tmp/local.png")

    assert image_client.transform_with_references("p", ["/tmp/a.png"]) == "/tmp/google.png"

    _enable_local_images(monkeypatch)
    assert image_client.transform_with_references("p", ["/tmp/a.png"]) == "/tmp/local.png"


def test_local_batch_falls_back_to_sequential_calls(monkeypatch):
    _enable_local_images(monkeypatch)
    from integrations import image_client, local_image_client
    from integrations.google_image_client import GoogleBatchImageRequest

    seen: list[str] = []

    def fake(prompt, **kwargs):
        seen.append(prompt)
        return f"/tmp/{prompt}.png"

    monkeypatch.setattr(local_image_client, "generate_image", fake)

    results = image_client.generate_images_batch(
        requests=[
            GoogleBatchImageRequest(key="a", prompt="one", aspect_ratio="16:9"),
            GoogleBatchImageRequest(key="b", prompt="two", aspect_ratio="16:9"),
        ]
    )
    assert seen == ["one", "two"]
    assert [r.key for r in results] == ["a", "b"]
    assert all(r.image_path and not r.error for r in results)


def test_local_batch_forwards_reference_paths(monkeypatch):
    _enable_local_images(monkeypatch)
    from integrations import image_client, local_image_client
    from integrations.google_image_client import GoogleBatchImageRequest

    captured: dict = {}

    def fake(prompt, **kwargs):
        captured.update(kwargs)
        return "/tmp/ok.png"

    monkeypatch.setattr(local_image_client, "generate_image", fake)
    image_client.generate_images_batch(
        requests=[
            GoogleBatchImageRequest(
                key="a",
                prompt="one",
                aspect_ratio="16:9",
                reference_image_path="/tmp/char.png",
                style_reference_path="/tmp/style.png",
            ),
        ]
    )
    assert captured["reference_image_path"] == "/tmp/char.png"
    assert captured["style_reference_path"] == "/tmp/style.png"


def test_local_batch_records_per_request_errors(monkeypatch):
    _enable_local_images(monkeypatch)
    from integrations import image_client, local_image_client
    from integrations.google_image_client import GoogleBatchImageRequest

    def fake(prompt, **kwargs):
        if prompt == "bad":
            raise RuntimeError("comfy exploded")
        return "/tmp/ok.png"

    monkeypatch.setattr(local_image_client, "generate_image", fake)
    results = image_client.generate_images_batch(
        requests=[
            GoogleBatchImageRequest(key="a", prompt="good", aspect_ratio="16:9"),
            GoogleBatchImageRequest(key="b", prompt="bad", aspect_ratio="16:9"),
        ]
    )
    by_key = {r.key: r for r in results}
    assert by_key["a"].image_path == "/tmp/ok.png"
    assert "comfy exploded" in (by_key["b"].error or "")


def test_empty_batch_short_circuits(monkeypatch):
    from integrations import image_client

    assert image_client.generate_images_batch(requests=[]) == []


def test_provider_fingerprint_distinguishes_modes_and_models(monkeypatch):
    from integrations import image_client

    assert image_client.provider_fingerprint() == "google"

    _enable_local_images(monkeypatch)
    monkeypatch.setenv("LOCAL_IMAGE_MODEL", "qwen-image-edit-2511")
    first = image_client.provider_fingerprint()
    monkeypatch.setenv("LOCAL_IMAGE_MODEL", "flux2-klein-4b")
    second = image_client.provider_fingerprint()

    assert first.startswith("local:")
    assert first != second != "google"
