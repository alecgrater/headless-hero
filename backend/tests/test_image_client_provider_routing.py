"""Tests for image provider routing."""


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
