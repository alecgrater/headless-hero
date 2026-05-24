"""Tests for style-preset-scoped main characters."""

from datetime import datetime, timezone
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.pool import StaticPool
from sqlmodel import SQLModel, Session, create_engine


@pytest.fixture
def style_character_engine():
    from models.project_config import ProjectConfig  # noqa: F401
    from models.script import Script  # noqa: F401
    from models.settings import AppSetting  # noqa: F401
    from models.style_preset import StylePreset  # noqa: F401
    from models.style_preset_character import StylePresetCharacter  # noqa: F401

    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    SQLModel.metadata.create_all(engine)
    return engine


@pytest.fixture
def client(style_character_engine):
    from api import app
    from api import style as style_api

    def override_get_session():
        with Session(style_character_engine) as session:
            yield session

    app.dependency_overrides[style_api.get_session] = override_get_session
    try:
        yield TestClient(app)
    finally:
        app.dependency_overrides.pop(style_api.get_session, None)


def _insert_preset(engine, tmp_path, preset_id: str, name: str):
    from models.style_preset import StylePreset

    preset_dir = tmp_path / "style" / "presets"
    preset_dir.mkdir(parents=True, exist_ok=True)
    (preset_dir / f"{preset_id}.png").write_bytes(f"preset:{preset_id}".encode())
    with Session(engine) as session:
        session.add(
            StylePreset(
                id=preset_id,
                name=name,
                prompt=f"{name} prompt",
                created_at=datetime.now(timezone.utc),
            )
        )
        session.commit()


def test_create_character_scopes_it_to_the_requested_preset(
    client,
    style_character_engine,
    tmp_path,
    monkeypatch,
):
    from api import style as style_api
    from pipeline import main_character

    monkeypatch.setattr(style_api, "DATA_DIR", tmp_path)
    monkeypatch.setattr(main_character, "DATA_DIR", tmp_path)
    _insert_preset(style_character_engine, tmp_path, "preset-a", "Preset A")
    _insert_preset(style_character_engine, tmp_path, "preset-b", "Preset B")

    fake_tmp = tmp_path / "generated-character.png"
    fake_tmp.write_bytes(b"generated")
    calls: list[dict[str, object]] = []

    def fake_generate(prompt, script_id, style_reference_path):
        calls.append(
            {
                "prompt": prompt,
                "script_id": script_id,
                "style_reference_path": style_reference_path,
            }
        )
        return str(fake_tmp)

    with patch.object(
        main_character,
        "_call_style_character_image_generator",
        side_effect=fake_generate,
    ):
        response = client.post(
            "/api/style/presets/preset-a/characters",
            json={
                "name": "Mara",
                "appearance": "short black hair, teal jacket",
                "vibe": "calm and sharp",
            },
        )

    assert response.status_code == 200
    created = response.json()
    assert created["style_preset_id"] == "preset-a"
    assert created["name"] == "Mara"
    assert created["active"] is True
    assert calls[0]["style_reference_path"] == str(
        tmp_path / "style" / "presets" / "preset-a.png"
    )
    assert (tmp_path / "style" / "presets" / "preset-a" / "characters" / f"{created['id']}.png").exists()

    preset_a = client.get("/api/style/presets/preset-a/characters")
    preset_b = client.get("/api/style/presets/preset-b/characters")

    assert [item["id"] for item in preset_a.json()] == [created["id"]]
    assert preset_b.json() == []


def test_selecting_character_under_wrong_preset_fails(
    client,
    style_character_engine,
    tmp_path,
    monkeypatch,
):
    from api import style as style_api
    from models.style_preset_character import StylePresetCharacter
    from pipeline import main_character

    monkeypatch.setattr(style_api, "DATA_DIR", tmp_path)
    monkeypatch.setattr(main_character, "DATA_DIR", tmp_path)
    _insert_preset(style_character_engine, tmp_path, "preset-a", "Preset A")
    _insert_preset(style_character_engine, tmp_path, "preset-b", "Preset B")

    character_id = "char-a"
    character_path = tmp_path / "style" / "presets" / "preset-a" / "characters" / f"{character_id}.png"
    character_path.parent.mkdir(parents=True, exist_ok=True)
    character_path.write_bytes(b"char")
    with Session(style_character_engine) as session:
        session.add(
            StylePresetCharacter(
                id=character_id,
                style_preset_id="preset-a",
                name="Mara",
                appearance="short black hair",
                vibe="calm",
                reference_image_url=f"/static/style/presets/preset-a/characters/{character_id}.png",
                created_at=datetime.now(timezone.utc),
            )
        )
        session.commit()

    response = client.post(
        f"/api/style/presets/preset-b/characters/{character_id}/select"
    )

    assert response.status_code == 404


def test_create_character_rejects_missing_preset_image(
    client,
    style_character_engine,
    tmp_path,
    monkeypatch,
):
    from api import style as style_api
    from models.style_preset import StylePreset
    from pipeline import main_character

    monkeypatch.setattr(style_api, "DATA_DIR", tmp_path)
    monkeypatch.setattr(main_character, "DATA_DIR", tmp_path)
    with Session(style_character_engine) as session:
        session.add(
            StylePreset(
                id="fileless",
                name="Fileless",
                prompt="missing image",
                created_at=datetime.now(timezone.utc),
            )
        )
        session.commit()

    response = client.post(
        "/api/style/presets/fileless/characters",
        json={
            "name": "Mara",
            "appearance": "short black hair",
            "vibe": "calm",
        },
    )

    assert response.status_code == 404


def test_sync_active_preset_character_to_project(
    style_character_engine,
    tmp_path,
    monkeypatch,
):
    from models.project_config import ProjectConfig
    from models.script import Script, ScriptContent
    from models.settings import AppSetting
    from models.style_preset_character import StylePresetCharacter
    from pipeline import main_character

    monkeypatch.setattr(main_character, "DATA_DIR", tmp_path)
    _insert_preset(style_character_engine, tmp_path, "preset-a", "Preset A")

    character_id = "char-a"
    source_ref = tmp_path / "style" / "presets" / "preset-a" / "characters" / f"{character_id}.png"
    source_ref.parent.mkdir(parents=True, exist_ok=True)
    source_ref.write_bytes(b"preset-character")

    with Session(style_character_engine) as session:
        session.add(
            StylePresetCharacter(
                id=character_id,
                style_preset_id="preset-a",
                name="Mara",
                appearance="short black hair",
                vibe="calm",
                reference_image_url=f"/static/style/presets/preset-a/characters/{character_id}.png",
                created_at=datetime.now(timezone.utc),
            )
        )
        session.add(AppSetting(key="ACTIVE_STYLE_PRESET_ID", value="preset-a"))
        session.add(
            AppSetting(
                key=main_character.active_style_preset_character_key("preset-a"),
                value=character_id,
            )
        )
        session.add(
            Script(
                id="script-a",
                brand_id="default",
                topic_title="Test",
                topic_description="",
                script_json=ScriptContent(title="Test", segments=[]).model_dump_json(),
            )
        )
        session.add(ProjectConfig(script_id="script-a", eli_enabled=False))
        session.commit()

    with Session(style_character_engine) as session:
        changed = main_character.sync_global_main_character_to_project(session, "script-a")
        session.commit()

        assert changed is True
        cfg = session.get(ProjectConfig, "script-a")
        script = session.get(Script, "script-a")

    project_ref = tmp_path / "projects" / "script-a" / "character" / "reference.png"
    assert project_ref.read_bytes() == b"preset-character"
    assert cfg.main_character_reference_url == "/static/projects/script-a/character/reference.png"
    content = ScriptContent.model_validate_json(script.script_json)
    assert content.main_character is not None
    assert content.main_character.name == "Mara"
