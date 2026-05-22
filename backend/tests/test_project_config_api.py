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
