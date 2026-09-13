import os

import pytest
from fastapi.testclient import TestClient
from sqlmodel import Session, SQLModel, create_engine
from sqlmodel.pool import StaticPool

from api import app
from api import settings as settings_module

_LOCAL_ENV_PREFIX = "LOCAL_"


@pytest.fixture(autouse=True)
def _restore_local_env():
    """Saving keys through the real endpoint mutates os.environ.

    Snapshot and restore every LOCAL_* key so a saved value cannot leak into
    unrelated tests and silently flip them into Local Mode.
    """
    before = {k: v for k, v in os.environ.items() if k.startswith(_LOCAL_ENV_PREFIX)}
    yield
    for key in [k for k in os.environ if k.startswith(_LOCAL_ENV_PREFIX)]:
        if key not in before:
            del os.environ[key]
    os.environ.update(before)


@pytest.fixture
def client():
    """A client backed by an in-memory database.

    PUT /api/settings/keys persists rows, so without this override the suite
    would write settings into the developer's real data/db.sqlite.
    """
    from database import get_session

    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    SQLModel.metadata.create_all(engine)

    def _override_get_session():
        with Session(engine) as session:
            yield session

    app.dependency_overrides[get_session] = _override_get_session
    try:
        yield TestClient(app)
    finally:
        app.dependency_overrides.pop(get_session, None)
        engine.dispose()


def test_new_keys_are_allowed_and_plaintext():
    for key in (
        "LOCAL_MODELS_ENABLED", "LOCAL_TEXT_MODE", "LOCAL_IMAGE_MODE", "LOCAL_VOICE_MODE",
        "LOCAL_TEXT_MODEL", "LOCAL_TEXT_FAST_MODEL", "LOCAL_IMAGE_MODEL", "LOCAL_VOICE_MODEL",
        "LOCAL_COMFYUI_URL", "LOCAL_TTS_URL",
    ):
        assert key in settings_module.ALLOWED_KEYS
        assert key in settings_module._PLAINTEXT_KEYS


def test_defaults_are_conservative():
    assert settings_module._DEFAULTS["LOCAL_MODELS_ENABLED"] == "false"
    assert settings_module._DEFAULTS["LOCAL_TEXT_MODE"] == "auto"
    assert settings_module._DEFAULTS["LOCAL_IMAGE_MODE"] == "auto"
    assert settings_module._DEFAULTS["LOCAL_VOICE_MODE"] == "auto"
    assert settings_module._DEFAULTS["LOCAL_VOICE_MODEL"] == "higgs-tts-3-4b"


def test_fast_text_model_defaults_to_the_narrative_model():
    assert settings_module._DEFAULTS["LOCAL_TEXT_FAST_MODEL"] == settings_module._DEFAULTS["LOCAL_TEXT_MODEL"]


def test_save_rejects_an_invalid_mode(client):
    response = client.put("/api/settings/keys", json={"LOCAL_IMAGE_MODE": "sideways"})
    assert response.status_code == 400
    assert "LOCAL_IMAGE_MODE" in response.json()["detail"]


def test_save_rejects_a_model_id_from_the_wrong_modality(client):
    response = client.put("/api/settings/keys", json={"LOCAL_VOICE_MODEL": "flux2-klein-4b"})
    assert response.status_code == 400
    assert "LOCAL_VOICE_MODEL" in response.json()["detail"]


def test_save_rejects_an_unknown_model_id(client):
    response = client.put("/api/settings/keys", json={"LOCAL_IMAGE_MODEL": "not-a-model"})
    assert response.status_code == 400
    assert "LOCAL_IMAGE_MODEL" in response.json()["detail"]


def test_save_accepts_valid_values(client):
    response = client.put("/api/settings/keys", json={
        "LOCAL_IMAGE_MODE": "local",
        "LOCAL_IMAGE_MODEL": "flux2-klein-4b",
    })
    assert response.status_code == 200


def test_status_endpoint_reports_catalog_and_daemons(client, monkeypatch):
    from pipeline import local_runtime

    monkeypatch.setattr(local_runtime, "_probe", lambda url: False)
    response = client.get("/api/local-models")
    assert response.status_code == 200
    body = response.json()
    assert set(body["catalog"]) == {"text", "image", "voice"}
    assert any(m["id"] == "higgs-tts-3-4b" for m in body["catalog"]["voice"])
    assert set(body["daemons"]) == {"ollama", "comfyui", "mlx-audio"}
    assert body["daemons"]["comfyui"]["healthy"] is False


def test_status_reports_per_modality_source(client, monkeypatch):
    from pipeline import local_runtime

    monkeypatch.setattr(local_runtime, "_probe", lambda url: True)
    monkeypatch.setenv("LOCAL_MODELS_ENABLED", "true")
    monkeypatch.setenv("LOCAL_IMAGE_MODE", "cloud")
    monkeypatch.delenv("LOCAL_TEXT_MODE", raising=False)
    monkeypatch.delenv("LOCAL_VOICE_MODE", raising=False)

    body = client.get("/api/local-models").json()
    assert body["modalities"]["text"]["source"] == "local"
    assert body["modalities"]["image"]["source"] == "cloud"
    assert body["enabled"] is True


def test_status_marks_attribution_requiring_models(client, monkeypatch):
    from pipeline import local_runtime

    monkeypatch.setattr(local_runtime, "_probe", lambda url: True)
    body = client.get("/api/local-models").json()
    higgs = next(m for m in body["catalog"]["voice"] if m["id"] == "higgs-tts-3-4b")
    kokoro = next(m for m in body["catalog"]["voice"] if m["id"] == "kokoro-82m")
    assert higgs["requires_attribution"] is True
    assert higgs["attribution_text"]
    assert kokoro["requires_attribution"] is False
