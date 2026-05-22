"""Verify main character reference generation is triggered during script gen
when eli_enabled=False and the script content includes a main_character.
"""

import sys

import pytest
from sqlalchemy.pool import StaticPool
from sqlmodel import Session, SQLModel, create_engine, select


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


def test_main_character_reference_generated_when_eli_disabled(monkeypatch, tmp_path):
    """When eli_enabled=False and Claude returns main_character, reference URL is persisted."""
    monkeypatch.setenv("HH_DATA_DIR", str(tmp_path))

    # Reload config & main_character module so DATA_DIR points to tmp_path.
    import importlib

    import config

    importlib.reload(config)
    import pipeline.main_character as mc_mod

    importlib.reload(mc_mod)

    # In-memory DB engine
    engine = _build_inmemory_engine()

    from models.brand import BrandProfile
    from models.project_config import ProjectConfig
    from models.script import MainCharacter, ScriptContent, Segment

    with Session(engine) as session:
        session.add(BrandProfile(name="Default"))
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

    # Run script gen synchronously
    def fake_run(job_id, fn, *args, **kwargs):
        fn(*args, **kwargs)

    monkeypatch.setattr(scripts_module, "run_in_background", fake_run)

    # Stub generate_script to return a ScriptContent with a main_character.
    def fake_generate_script(**kwargs):
        return ScriptContent(
            title="t",
            segments=[Segment(name="s1", scenes=[])],
            main_character=MainCharacter(
                name="Maya",
                appearance="dark hair, leather jacket",
                vibe="brisk detective",
            ),
        )

    monkeypatch.setattr(scripts_module, "generate_script", fake_generate_script)

    # Stub the Gemini call to write a fake PNG and return its path.
    fake_png = tmp_path / "fake_gemini_output.png"
    fake_png.write_bytes(b"\x89PNG fake")

    monkeypatch.setattr(
        mc_mod, "_call_image_generator", lambda prompt, script_id: str(fake_png)
    )
    # Also patch the symbol referenced inside scripts.py via lazy import path.
    if "pipeline.main_character" in sys.modules:
        sys.modules["pipeline.main_character"]._call_image_generator = (
            lambda prompt, script_id: str(fake_png)
        )

    from fastapi.testclient import TestClient

    try:
        client = TestClient(app)
        res = client.post(
            "/api/scripts/generate",
            json={
                "topic": "t-trigger",
                "format_id": "youtube-listicle",
                "eli_enabled": False,
            },
        )
        assert res.status_code == 200, res.text

        # The ProjectConfig row should now have a main_character_reference_url.
        with Session(engine) as session:
            row = session.exec(
                select(ProjectConfig).where(ProjectConfig.eli_enabled == False)  # noqa: E712
            ).first()
        assert row is not None
        assert row.main_character_reference_url is not None, (
            "Expected main_character_reference_url to be persisted on ProjectConfig"
        )
        assert row.main_character_reference_url.startswith("/static/projects/")
        assert "/character/reference.png" in row.main_character_reference_url
    finally:
        app.dependency_overrides.pop(get_session, None)
