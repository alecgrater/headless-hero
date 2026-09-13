import json
from pathlib import Path

import pytest

from integrations import local_image_client


class _Response:
    def __init__(self, status_code, payload=None, content=b""):
        self.status_code = status_code
        self._payload = payload
        self.content = content

    def json(self):
        return self._payload

    def raise_for_status(self):
        if self.status_code >= 400:
            raise RuntimeError(f"HTTP {self.status_code}")


class _FakeComfy:
    """Minimal ComfyUI stand-in: accepts a prompt, then serves history and the image."""

    def __init__(self, png_bytes: bytes):
        self.png_bytes = png_bytes
        self.submitted: list[dict] = []

    def post(self, url, json=None, timeout=None, files=None, data=None):
        self.submitted.append(json)
        return _Response(200, {"prompt_id": "p1"})

    def get(self, url, timeout=None):
        if "/history/" in url:
            return _Response(200, {
                "p1": {
                    "status": {"completed": True},
                    "outputs": {
                        "9": {"images": [{"filename": "out.png", "subfolder": "", "type": "output"}]}
                    },
                }
            })
        return _Response(200, None, content=self.png_bytes)


@pytest.fixture
def fake_comfy(monkeypatch, tmp_path):
    png = tmp_path / "src.png"
    png.write_bytes(b"\x89PNG\r\n\x1a\nFAKE")
    fake = _FakeComfy(png.read_bytes())
    monkeypatch.setattr(local_image_client, "_http", lambda: fake)
    monkeypatch.setattr(local_image_client, "ensure_daemon", lambda backend: None)
    monkeypatch.setattr(local_image_client, "_upload_image", lambda path: Path(path).name)
    monkeypatch.setattr(local_image_client, "POLL_INTERVAL_SECONDS", 0.0)
    return fake


def test_generate_image_returns_a_written_png(fake_comfy, monkeypatch):
    monkeypatch.setenv("LOCAL_IMAGE_MODEL", "flux2-klein-4b")
    out = local_image_client.generate_image("a cat", width=1920, height=1080)
    assert Path(out).exists()
    assert Path(out).read_bytes().startswith(b"\x89PNG")


def test_prompt_and_dimensions_are_substituted(fake_comfy, monkeypatch):
    monkeypatch.setenv("LOCAL_IMAGE_MODEL", "flux2-klein-4b")
    local_image_client.generate_image("a lighthouse at dusk", width=1920, height=1080)
    payload = json.dumps(fake_comfy.submitted[0])
    assert "a lighthouse at dusk" in payload
    assert "1920" in payload and "1080" in payload
    assert "__PROMPT__" not in payload and "__WIDTH__" not in payload
    assert "__SEED__" not in payload


def test_quotes_in_a_prompt_do_not_corrupt_the_graph(fake_comfy, monkeypatch):
    monkeypatch.setenv("LOCAL_IMAGE_MODEL", "flux2-klein-4b")
    local_image_client.generate_image('a sign reading "OPEN" at night', width=64, height=64)
    graph = fake_comfy.submitted[0]["prompt"]
    assert graph["6"]["inputs"]["text"] == 'a sign reading "OPEN" at night'


def test_references_are_uploaded_and_referenced(fake_comfy, tmp_path, monkeypatch):
    monkeypatch.setenv("LOCAL_IMAGE_MODEL", "qwen-image-edit-2511")
    char = tmp_path / "char.png"
    char.write_bytes(b"\x89PNG\r\n\x1a\n")
    style = tmp_path / "style.png"
    style.write_bytes(b"\x89PNG\r\n\x1a\n")
    local_image_client.generate_image(
        "hero in a workshop",
        width=1920,
        height=1080,
        reference_image_path=str(char),
        style_reference_path=str(style),
    )
    payload = json.dumps(fake_comfy.submitted[0])
    assert "char.png" in payload
    assert "style.png" in payload


def test_transform_with_references_accepts_a_list(fake_comfy, tmp_path, monkeypatch):
    monkeypatch.setenv("LOCAL_IMAGE_MODEL", "qwen-image-edit-2511")
    paths = []
    for name in ("a.png", "b.png"):
        p = tmp_path / name
        p.write_bytes(b"\x89PNG\r\n\x1a\n")
        paths.append(str(p))
    out = local_image_client.transform_with_references("merge these", paths, width=1280, height=720)
    assert Path(out).exists()
    payload = json.dumps(fake_comfy.submitted[0])
    assert "a.png" in payload and "b.png" in payload


def test_seeds_differ_between_calls(fake_comfy, monkeypatch):
    monkeypatch.setenv("LOCAL_IMAGE_MODEL", "flux2-klein-4b")
    local_image_client.generate_image("x", width=64, height=64)
    local_image_client.generate_image("x", width=64, height=64)
    first = fake_comfy.submitted[0]["prompt"]["3"]["inputs"]["seed"]
    second = fake_comfy.submitted[1]["prompt"]["3"]["inputs"]["seed"]
    assert first != second


def test_seed_and_dimensions_are_numbers_not_strings(fake_comfy, monkeypatch):
    monkeypatch.setenv("LOCAL_IMAGE_MODEL", "flux2-klein-4b")
    local_image_client.generate_image("x", width=1920, height=1080)
    graph = fake_comfy.submitted[0]["prompt"]
    assert isinstance(graph["3"]["inputs"]["seed"], int)
    assert graph["5"]["inputs"]["width"] == 1920
    assert isinstance(graph["5"]["inputs"]["width"], int)


def test_missing_daemon_raises_actionable_error(monkeypatch):
    def boom(backend):
        raise RuntimeError("comfyui daemon is not responding")

    monkeypatch.setattr(local_image_client, "ensure_daemon", boom)
    with pytest.raises(RuntimeError, match="not responding"):
        local_image_client.generate_image("x", width=64, height=64)


def test_unregistered_model_raises(fake_comfy, monkeypatch):
    monkeypatch.setattr(local_image_client, "WORKFLOW_FILES", {})
    monkeypatch.setenv("LOCAL_IMAGE_MODEL", "flux2-klein-4b")
    with pytest.raises(RuntimeError, match="workflow"):
        local_image_client.generate_image("x", width=64, height=64)


def test_timeout_raises_rather_than_hanging(fake_comfy, monkeypatch):
    class _NeverDone(_FakeComfy):
        def get(self, url, timeout=None):
            if "/history/" in url:
                return _Response(200, {})
            return _Response(200, None, content=b"")

    monkeypatch.setattr(local_image_client, "_http", lambda: _NeverDone(b""))
    monkeypatch.setenv("LOCAL_IMAGE_MODEL", "flux2-klein-4b")
    monkeypatch.setenv("LOCAL_IMAGE_TIMEOUT_SECONDS", "0.05")
    with pytest.raises(RuntimeError, match="did not return an image"):
        local_image_client.generate_image("x", width=64, height=64)
