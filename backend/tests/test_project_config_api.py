"""Tests for /api/projects/{script_id}/config endpoints."""

import json
from sqlmodel import Session, SQLModel, create_engine
from sqlmodel.pool import StaticPool


def _build_inmemory_engine():
    # Import all models so SQLModel.metadata is fully populated before create_all.
    import models.brand  # noqa: F401
    import models.script  # noqa: F401
    import models.project_config  # noqa: F401
    import models.publish  # noqa: F401
    import models.credential  # noqa: F401
    import models.settings  # noqa: F401
    import models.api_usage  # noqa: F401
    import models.generation_duration  # noqa: F401
    import models.style_preset_character  # noqa: F401

    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    SQLModel.metadata.create_all(engine)
    return engine


def _setup_app(monkeypatch):
    """Common setup: in-memory DB engine + dependency override + default brand."""
    engine = _build_inmemory_engine()

    from models.brand import BrandProfile

    with Session(engine) as session:
        session.add(
            BrandProfile(id="default", name="Default", description="d", is_default=True)
        )
        session.commit()

    import database
    import api.scripts as scripts_module
    monkeypatch.setattr(database, "engine", engine)
    monkeypatch.setattr(scripts_module, "engine", engine)

    from api import app
    from database import get_session

    def _override_get_session():
        with Session(engine) as s:
            yield s

    app.dependency_overrides[get_session] = _override_get_session
    return engine, app


def _seed_script(engine, script_id: str, *, eli_enabled: bool, main_character_dict=None):
    from models.project_config import ProjectConfig
    from models.script import MainCharacter, Script, ScriptContent

    main_character = None
    if main_character_dict is not None:
        main_character = MainCharacter(**main_character_dict)
    content = ScriptContent(title="t", segments=[], main_character=main_character)
    with Session(engine) as session:
        session.add(
            Script(
                id=script_id,
                brand_id="default",
                format_id="youtube-listicle",
                topic_title="t",
                topic_description="",
                script_json=content.model_dump_json(),
            )
        )
        session.add(ProjectConfig(script_id=script_id, eli_enabled=eli_enabled))
        session.commit()


def test_get_project_config_returns_full_payload(monkeypatch):
    engine, app = _setup_app(monkeypatch)
    _seed_script(
        engine,
        "test-cfg-1",
        eli_enabled=False,
        main_character_dict={"name": "N", "appearance": "A", "vibe": "V"},
    )

    from fastapi.testclient import TestClient
    client = TestClient(app)
    res = client.get("/api/projects/test-cfg-1/config")
    assert res.status_code == 200
    data = res.json()
    assert data["script_id"] == "test-cfg-1"
    assert data["eli_enabled"] is False
    assert data["main_character"]["name"] == "N"

    from database import get_session
    app.dependency_overrides.pop(get_session, None)


def test_get_project_config_legacy_script_returns_default(monkeypatch):
    """Script with no ProjectConfig row gets eli_enabled=True default."""
    engine, app = _setup_app(monkeypatch)

    from models.script import Script, ScriptContent
    with Session(engine) as session:
        session.add(
            Script(
                id="legacy-1",
                brand_id="default",
                format_id="youtube-listicle",
                topic_title="t",
                topic_description="",
                script_json=ScriptContent(title="t", segments=[]).model_dump_json(),
            )
        )
        session.commit()

    from fastapi.testclient import TestClient
    client = TestClient(app)
    res = client.get("/api/projects/legacy-1/config")
    assert res.status_code == 200
    assert res.json()["eli_enabled"] is True

    from database import get_session
    app.dependency_overrides.pop(get_session, None)


def test_get_project_config_404_for_unknown_script(monkeypatch):
    _, app = _setup_app(monkeypatch)
    from fastapi.testclient import TestClient
    client = TestClient(app)
    res = client.get("/api/projects/does-not-exist/config")
    assert res.status_code == 404

    from database import get_session
    app.dependency_overrides.pop(get_session, None)


def test_put_main_character_updates_script_json(monkeypatch):
    engine, app = _setup_app(monkeypatch)
    _seed_script(
        engine,
        "test-cfg-2",
        eli_enabled=False,
        main_character_dict={"name": "Old", "appearance": "x", "vibe": "y"},
    )

    from fastapi.testclient import TestClient
    client = TestClient(app)
    res = client.put(
        "/api/projects/test-cfg-2/config/character",
        json={"name": "New", "appearance": "z", "vibe": "w"},
    )
    assert res.status_code == 200

    follow = client.get("/api/projects/test-cfg-2/config")
    assert follow.json()["main_character"]["name"] == "New"

    from database import get_session
    app.dependency_overrides.pop(get_session, None)


def test_generate_and_select_main_character_reference_variants(monkeypatch, tmp_path):
    engine, app = _setup_app(monkeypatch)
    _seed_script(
        engine,
        "test-cfg-variants",
        eli_enabled=False,
        main_character_dict={"name": "N", "appearance": "A", "vibe": "V"},
    )

    import pipeline.main_character as mc

    monkeypatch.setattr(mc, "DATA_DIR", tmp_path)

    counter = {"value": 0}

    def fake_image(prompt, script_id):
        counter["value"] += 1
        path = tmp_path / f"generated-{counter['value']}.png"
        path.write_bytes(f"png-{counter['value']}".encode())
        return str(path)

    monkeypatch.setattr(mc, "_call_image_generator", fake_image)

    from fastapi.testclient import TestClient

    client = TestClient(app)
    first = client.post("/api/projects/test-cfg-variants/config/character/regenerate")
    second = client.post("/api/projects/test-cfg-variants/config/character/regenerate")

    assert first.status_code == 200
    assert second.status_code == 200
    body = second.json()
    assert body["main_character_reference_url"] == "/static/projects/test-cfg-variants/character/reference.png"
    assert [v["idx"] for v in body["main_character_reference_variants"]] == [2, 1]
    assert body["main_character_reference_variants"][0]["active"] is True

    selected = client.post("/api/projects/test-cfg-variants/config/character/select/1")
    assert selected.status_code == 200
    selected_body = selected.json()
    active = [v for v in selected_body["main_character_reference_variants"] if v["active"]]
    assert [v["idx"] for v in active] == [1]

    from database import get_session
    app.dependency_overrides.pop(get_session, None)


def test_legacy_global_main_character_endpoints_do_not_sync_to_project(monkeypatch, tmp_path):
    engine, app = _setup_app(monkeypatch)
    _seed_script(engine, "test-global-character-project", eli_enabled=False)

    import pipeline.main_character as mc

    monkeypatch.setattr(mc, "DATA_DIR", tmp_path)

    counter = {"value": 0}

    def fake_image(prompt, script_id):
        counter["value"] += 1
        path = tmp_path / f"global-character-{counter['value']}.png"
        path.write_bytes(f"global-png-{counter['value']}".encode())
        return str(path)

    monkeypatch.setattr(mc, "_call_image_generator", fake_image)

    from fastapi.testclient import TestClient

    client = TestClient(app)
    saved = client.put(
        "/api/style/main-character",
        json={
            "name": "Mara",
            "appearance": "A young cartographer with a green jacket.",
            "vibe": "Inventive and calm.",
        },
    )
    assert saved.status_code == 200
    assert saved.json()["main_character"]["name"] == "Mara"
    assert saved.json()["main_character_reference_url"] is None

    first = client.post("/api/style/main-character/regenerate")
    second = client.post("/api/style/main-character/regenerate")
    assert first.status_code == 200
    assert second.status_code == 200
    body = second.json()
    assert body["main_character_reference_url"] == "/static/character/main/reference.png"
    assert [v["idx"] for v in body["main_character_reference_variants"]] == [2, 1]
    assert body["main_character_reference_variants"][0]["active"] is True

    selected = client.post("/api/style/main-character/select/1")
    assert selected.status_code == 200
    assert [v["idx"] for v in selected.json()["main_character_reference_variants"] if v["active"]] == [1]

    project_ref = tmp_path / "projects" / "test-global-character-project" / "character" / "reference.png"
    assert not project_ref.exists()

    from database import get_session
    app.dependency_overrides.pop(get_session, None)


def test_put_main_character_rejected_when_eli_enabled(monkeypatch):
    engine, app = _setup_app(monkeypatch)
    _seed_script(engine, "test-cfg-3", eli_enabled=True)

    from fastapi.testclient import TestClient
    client = TestClient(app)
    res = client.put(
        "/api/projects/test-cfg-3/config/character",
        json={"name": "X", "appearance": "y", "vibe": "z"},
    )
    assert res.status_code == 400

    from database import get_session
    app.dependency_overrides.pop(get_session, None)


def test_get_project_config_includes_style_preset_enabled(monkeypatch):
    engine, app = _setup_app(monkeypatch)
    _seed_script(engine, "test-spe-1", eli_enabled=True)

    from fastapi.testclient import TestClient
    client = TestClient(app)
    res = client.get("/api/projects/test-spe-1/config")
    assert res.status_code == 200
    body = res.json()
    assert "style_preset_enabled" in body
    assert body["style_preset_enabled"] is True

    from database import get_session
    app.dependency_overrides.pop(get_session, None)


def test_put_project_config_updates_style_preset_enabled(monkeypatch):
    engine, app = _setup_app(monkeypatch)
    _seed_script(engine, "test-spe-2", eli_enabled=True)

    from fastapi.testclient import TestClient
    client = TestClient(app)

    res = client.put(
        "/api/projects/test-spe-2/config",
        json={"style_preset_enabled": False},
    )
    assert res.status_code == 200

    res = client.get("/api/projects/test-spe-2/config")
    assert res.json()["style_preset_enabled"] is False

    from database import get_session
    app.dependency_overrides.pop(get_session, None)


def test_put_project_config_style_preset_enabled_true(monkeypatch):
    """Verify style_preset_enabled=True can be explicitly set."""
    engine, app = _setup_app(monkeypatch)

    from models.project_config import ProjectConfig
    from models.script import Script, ScriptContent
    with Session(engine) as session:
        content = ScriptContent(title="t", segments=[])
        session.add(
            Script(
                id="test-spe-3",
                brand_id="default",
                format_id="youtube-listicle",
                topic_title="t",
                topic_description="",
                script_json=content.model_dump_json(),
            )
        )
        # Seed with style_preset_enabled=False
        session.add(ProjectConfig(script_id="test-spe-3", eli_enabled=True, style_preset_enabled=False))
        session.commit()

    from fastapi.testclient import TestClient
    client = TestClient(app)

    res = client.put(
        "/api/projects/test-spe-3/config",
        json={"style_preset_enabled": True},
    )
    assert res.status_code == 200

    res = client.get("/api/projects/test-spe-3/config")
    assert res.json()["style_preset_enabled"] is True

    from database import get_session
    app.dependency_overrides.pop(get_session, None)
