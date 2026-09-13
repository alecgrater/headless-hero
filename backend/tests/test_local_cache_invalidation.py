from integrations import image_client
from models.script import Scene, ScriptContent, Segment
from pipeline import remotion_render


def _content() -> ScriptContent:
    return ScriptContent(
        title="T",
        segments=[
            Segment(
                name="Intro",
                scenes=[Scene(id="s1", narration="hi", visual_prompt="p", visual_mode="full_frame")],
            )
        ],
    )


def test_image_fingerprint_differs_between_modes(monkeypatch):
    monkeypatch.setenv("LOCAL_MODELS_ENABLED", "false")
    monkeypatch.delenv("LOCAL_IMAGE_MODE", raising=False)
    cloud = image_client.provider_fingerprint()
    monkeypatch.setenv("LOCAL_MODELS_ENABLED", "true")
    local = image_client.provider_fingerprint()
    assert cloud == "google"
    assert local.startswith("local:")
    assert cloud != local


def test_image_fingerprint_differs_between_local_models(monkeypatch):
    monkeypatch.setenv("LOCAL_MODELS_ENABLED", "true")
    monkeypatch.delenv("LOCAL_IMAGE_MODE", raising=False)
    monkeypatch.setenv("LOCAL_IMAGE_MODEL", "qwen-image-edit-2511")
    first = image_client.provider_fingerprint()
    monkeypatch.setenv("LOCAL_IMAGE_MODEL", "flux2-klein-4b")
    assert image_client.provider_fingerprint() != first


def test_voice_fingerprint_differs_between_modes(monkeypatch):
    monkeypatch.setenv("LOCAL_MODELS_ENABLED", "false")
    monkeypatch.delenv("LOCAL_VOICE_MODE", raising=False)
    cloud = remotion_render.voice_engine_fingerprint()
    assert cloud == "elevenlabs"
    monkeypatch.setenv("LOCAL_MODELS_ENABLED", "true")
    assert remotion_render.voice_engine_fingerprint() != cloud


def test_voice_fingerprint_differs_between_local_voices(monkeypatch):
    monkeypatch.setenv("LOCAL_MODELS_ENABLED", "true")
    monkeypatch.delenv("LOCAL_VOICE_MODE", raising=False)
    monkeypatch.setenv("LOCAL_VOICE_MODEL", "higgs-tts-3-4b")
    first = remotion_render.voice_engine_fingerprint()
    monkeypatch.setenv("LOCAL_VOICE_MODEL", "kokoro-82m")
    assert remotion_render.voice_engine_fingerprint() != first


def test_subtitle_render_fingerprint_includes_the_voice_engine(monkeypatch):
    content = _content()
    monkeypatch.setenv("LOCAL_MODELS_ENABLED", "false")
    monkeypatch.delenv("LOCAL_VOICE_MODE", raising=False)
    cloud = remotion_render.subtitle_render_fingerprint(content)
    monkeypatch.setenv("LOCAL_MODELS_ENABLED", "true")
    local = remotion_render.subtitle_render_fingerprint(content)
    assert cloud["voice_engine"] == "elevenlabs"
    assert local["voice_engine"] != cloud["voice_engine"]
    assert cloud != local


def test_image_markers_record_the_local_engine(monkeypatch):
    """Image cache markers must carry the local model id, not a stale env value."""
    monkeypatch.setenv("LOCAL_MODELS_ENABLED", "true")
    monkeypatch.delenv("LOCAL_IMAGE_MODE", raising=False)
    monkeypatch.setenv("LOCAL_IMAGE_MODEL", "flux2-klein-4b")
    monkeypatch.setenv("IMAGE_PROVIDER", "google")

    from pipeline import image_gen

    assert image_gen.provider_fingerprint() == "local:flux2-klein-4b"


def test_image_gen_no_longer_reads_image_provider_for_markers():
    """Guard against a regression reintroducing the raw env read in cache markers."""
    from pathlib import Path

    source = (Path(__file__).resolve().parent.parent / "pipeline" / "image_gen.py").read_text(
        encoding="utf-8"
    )
    assert 'os.environ.get("IMAGE_PROVIDER"' not in source


def test_cached_image_is_regenerated_after_switching_to_local_mode(monkeypatch, tmp_path):
    """The real invalidation test: a cloud-generated image must not be reused.

    Asserting only that the fingerprint string differs would pass even if the
    fingerprint were never consulted during the cache-hit check.
    """
    from pipeline import image_gen

    monkeypatch.setenv("LOCAL_MODELS_ENABLED", "false")
    monkeypatch.delenv("LOCAL_IMAGE_MODE", raising=False)
    monkeypatch.setattr(image_gen, "DATA_DIR", tmp_path)
    monkeypatch.setattr(image_gen, "record_usage", lambda **kwargs: None, raising=False)

    calls: list[str] = []

    def fake_generate(prompt, **kwargs):
        calls.append(prompt)
        out = tmp_path / f"gen_{len(calls)}.png"
        out.write_bytes(b"\x89PNG\r\n\x1a\n")
        return str(out)

    monkeypatch.setattr(image_gen, "generate_image", fake_generate)

    images_dir = tmp_path / "projects" / "p1" / "images"
    images_dir.mkdir(parents=True)
    marker = images_dir / "s1.prompt"
    (images_dir / "s1.png").write_bytes(b"\x89PNG\r\n\x1a\n")

    marker.write_text(image_gen._marker_payload("a prompt"), encoding="utf-8")
    assert image_gen._marker_matches(marker, "a prompt")

    monkeypatch.setenv("LOCAL_MODELS_ENABLED", "true")
    assert not image_gen._marker_matches(marker, "a prompt"), (
        "a cloud-generated image was still treated as a cache hit in Local Mode"
    )

    monkeypatch.setenv("LOCAL_IMAGE_MODEL", "flux2-klein-4b")
    marker.write_text(image_gen._marker_payload("a prompt"), encoding="utf-8")
    monkeypatch.setenv("LOCAL_IMAGE_MODEL", "qwen-image-edit-2511")
    assert not image_gen._marker_matches(marker, "a prompt"), (
        "an image from a different local model was treated as a cache hit"
    )
