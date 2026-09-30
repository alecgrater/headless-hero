"""The Gemini image model is a Setting, priced per model, and part of the cache key."""

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.pool import StaticPool
from sqlmodel import Session, SQLModel, create_engine

from config import DEFAULT_IMAGE_MODEL, GOOGLE_IMAGE_MODEL_PRICES
from integrations import image_client
from integrations.google_image_client import active_image_model, image_price


def test_unset_or_unknown_model_falls_back_to_the_default(monkeypatch):
    monkeypatch.delenv("GOOGLE_IMAGE_MODEL", raising=False)
    assert active_image_model() == DEFAULT_IMAGE_MODEL
    monkeypatch.setenv("GOOGLE_IMAGE_MODEL", "gemini-9-imaginary")
    assert active_image_model() == DEFAULT_IMAGE_MODEL


def test_a_listed_model_is_used(monkeypatch):
    monkeypatch.setenv("GOOGLE_IMAGE_MODEL", "gemini-3.1-flash-image")
    assert active_image_model() == "gemini-3.1-flash-image"


def test_every_selectable_model_is_priced_and_batch_is_half():
    for model, price in GOOGLE_IMAGE_MODEL_PRICES.items():
        assert price > 0
        assert image_price(model, batch=True) == pytest.approx(price / 2)
    assert image_price(DEFAULT_IMAGE_MODEL) == pytest.approx(0.039)


def test_default_model_keeps_the_existing_cache_fingerprint(monkeypatch):
    """Images cached before the model became selectable must not regenerate."""
    monkeypatch.setattr(image_client, "resolved_provider", lambda purpose=None: "google")
    monkeypatch.delenv("GOOGLE_IMAGE_MODEL", raising=False)
    assert image_client.provider_fingerprint() == "google"


def test_switching_model_changes_the_cache_fingerprint(monkeypatch):
    monkeypatch.setattr(image_client, "resolved_provider", lambda purpose=None: "google")
    monkeypatch.setenv("GOOGLE_IMAGE_MODEL", "gemini-3.1-flash-image")
    assert image_client.provider_fingerprint() == "google:gemini-3.1-flash-image"


@pytest.fixture
def settings_client(monkeypatch):
    import database as database_module
    from api import app

    engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    SQLModel.metadata.create_all(engine)
    # The settings PUT writes os.environ directly; setenv first so monkeypatch
    # records the original state and restores it after the test.
    monkeypatch.setenv("GOOGLE_IMAGE_MODEL", DEFAULT_IMAGE_MODEL)

    def _override_get_session():
        with Session(engine) as session:
            yield session

    app.dependency_overrides[database_module.get_session] = _override_get_session
    try:
        yield TestClient(app)
    finally:
        app.dependency_overrides.pop(database_module.get_session, None)


def test_settings_rejects_an_unlisted_image_model(settings_client):
    res = settings_client.put("/api/settings/keys", json={"GOOGLE_IMAGE_MODEL": "gemini-9-imaginary"})
    assert res.status_code == 400


def test_settings_accepts_a_listed_image_model(settings_client):
    res = settings_client.put("/api/settings/keys", json={"GOOGLE_IMAGE_MODEL": "gemini-3.1-flash-image"})
    assert res.status_code == 200
    keys = settings_client.get("/api/settings/keys").json()
    assert keys["GOOGLE_IMAGE_MODEL"]["masked"] == "gemini-3.1-flash-image"


def test_image_model_travels_with_the_identity_snapshot():
    from pipeline.identity import is_exportable_setting

    assert is_exportable_setting("GOOGLE_IMAGE_MODEL")
