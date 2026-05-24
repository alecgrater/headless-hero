import pytest
from fastapi import HTTPException
from fastapi.testclient import TestClient
from sqlalchemy.pool import StaticPool
from sqlmodel import Session, SQLModel, create_engine

from api.settings import (
    ALLOWED_KEYS,
    RANGED_INTEGER_SETTINGS,
    _DEFAULTS,
    _PLAINTEXT_KEYS,
    _validate_ranged_integer_settings,
)
from models.settings import AppSetting


@pytest.fixture
def settings_client(monkeypatch):
    import database as database_module
    from api import app

    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    SQLModel.metadata.create_all(engine)
    monkeypatch.delenv("ELI_ENABLED_DEFAULT", raising=False)
    monkeypatch.delenv("STYLE_PRESET_ENABLED_DEFAULT", raising=False)

    def _override_get_session():
        with Session(engine) as session:
            yield session

    app.dependency_overrides[database_module.get_session] = _override_get_session
    try:
        yield TestClient(app), engine
    finally:
        app.dependency_overrides.pop(database_module.get_session, None)


def test_eli_enabled_default_is_allowed():
    assert "ELI_ENABLED_DEFAULT" in ALLOWED_KEYS


def test_eli_enabled_default_has_default_false():
    assert _DEFAULTS.get("ELI_ENABLED_DEFAULT") == "false"


def test_eli_enabled_default_is_plaintext():
    assert "ELI_ENABLED_DEFAULT" in _PLAINTEXT_KEYS


def test_style_preset_enabled_default_is_allowed():
    from api.settings import ALLOWED_KEYS
    assert "STYLE_PRESET_ENABLED_DEFAULT" in ALLOWED_KEYS


def test_style_preset_enabled_default_has_default_true():
    from api.settings import _DEFAULTS
    assert _DEFAULTS.get("STYLE_PRESET_ENABLED_DEFAULT") == "true"


def test_settings_api_returns_new_project_defaults(settings_client):
    client, _ = settings_client

    response = client.get("/api/settings/keys")

    assert response.status_code == 200
    data = response.json()
    assert data["ELI_ENABLED_DEFAULT"]["masked"] == "false"
    assert data["STYLE_PRESET_ENABLED_DEFAULT"]["masked"] == "true"


def test_settings_api_persists_saved_new_project_defaults(settings_client):
    client, engine = settings_client

    response = client.put(
        "/api/settings/keys",
        json={
            "ELI_ENABLED_DEFAULT": "true",
            "STYLE_PRESET_ENABLED_DEFAULT": "false",
        },
    )
    assert response.status_code == 200

    followup = client.get("/api/settings/keys")
    assert followup.status_code == 200
    data = followup.json()
    assert data["ELI_ENABLED_DEFAULT"]["masked"] == "true"
    assert data["ELI_ENABLED_DEFAULT"]["source"] == "db"
    assert data["STYLE_PRESET_ENABLED_DEFAULT"]["masked"] == "false"
    assert data["STYLE_PRESET_ENABLED_DEFAULT"]["source"] == "db"

    with Session(engine) as session:
        eli_row = session.get(AppSetting, "ELI_ENABLED_DEFAULT")
        style_row = session.get(AppSetting, "STYLE_PRESET_ENABLED_DEFAULT")

    assert eli_row is not None
    assert eli_row.value == "true"
    assert style_row is not None
    assert style_row.value == "false"


def test_active_style_preset_id_is_allowed():
    from api.settings import ALLOWED_KEYS
    assert "ACTIVE_STYLE_PRESET_ID" in ALLOWED_KEYS


def test_active_style_preset_id_default_empty():
    from api.settings import _DEFAULTS
    assert _DEFAULTS.get("ACTIVE_STYLE_PRESET_ID") == ""


def test_life_as_a_chunking_settings_are_allowed_plaintext_and_defaulted():
    expected_defaults = {
        "LIFE_AS_A_SCENE_CHUNKING_ENABLED": "true",
        "LIFE_AS_A_TARGET_SCENE_SECONDS": "8",
        "LIFE_AS_A_MAX_SCENE_SECONDS": "12",
        "LIFE_AS_A_SINGLE_VISUAL_MAX_SECONDS": "8",
    }

    for key, default in expected_defaults.items():
        assert key in ALLOWED_KEYS
        assert key in _PLAINTEXT_KEYS
        assert _DEFAULTS.get(key) == default


def test_life_as_a_chunking_range_validation_accepts_and_normalizes_values():
    keys = {
        "LIFE_AS_A_TARGET_SCENE_SECONDS": " 9 ",
        "LIFE_AS_A_MAX_SCENE_SECONDS": "14",
        "LIFE_AS_A_SINGLE_VISUAL_MAX_SECONDS": "7",
    }

    _validate_ranged_integer_settings(keys)

    assert keys == {
        "LIFE_AS_A_TARGET_SCENE_SECONDS": "9",
        "LIFE_AS_A_MAX_SCENE_SECONDS": "14",
        "LIFE_AS_A_SINGLE_VISUAL_MAX_SECONDS": "7",
    }


@pytest.mark.parametrize(
    ("key", "value"),
    [
        ("LIFE_AS_A_TARGET_SCENE_SECONDS", "4"),
        ("LIFE_AS_A_TARGET_SCENE_SECONDS", "13"),
        ("LIFE_AS_A_MAX_SCENE_SECONDS", "7"),
        ("LIFE_AS_A_MAX_SCENE_SECONDS", "19"),
        ("LIFE_AS_A_SINGLE_VISUAL_MAX_SECONDS", "4"),
        ("LIFE_AS_A_SINGLE_VISUAL_MAX_SECONDS", "13"),
        ("LIFE_AS_A_SINGLE_VISUAL_MAX_SECONDS", "soon"),
    ],
)
def test_life_as_a_chunking_range_validation_rejects_invalid_values(key, value):
    with pytest.raises(HTTPException) as exc_info:
        _validate_ranged_integer_settings({key: value})

    minimum, maximum = RANGED_INTEGER_SETTINGS[key]
    assert exc_info.value.status_code == 400
    assert f"integer from {minimum} to {maximum}" in exc_info.value.detail
