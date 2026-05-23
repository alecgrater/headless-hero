"""Verify script gen stores main character details without auto-generating
the reference image when eli_enabled=False.
"""

import sys

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


def test_main_character_reference_waits_for_ui_generation_when_eli_disabled(monkeypatch, tmp_path):
    """When Claude returns main_character, the reference URL stays empty for UI approval."""
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

    def fail_image_generation(prompt, script_id):
        raise AssertionError("script generation should not generate the reference image")

    monkeypatch.setattr(mc_mod, "_call_image_generator", fail_image_generation)
    if "pipeline.main_character" in sys.modules:
        sys.modules["pipeline.main_character"]._call_image_generator = fail_image_generation

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

        # The ProjectConfig row is ready for the UI step, but no reference has
        # been generated or approved yet.
        with Session(engine) as session:
            row = session.exec(
                select(ProjectConfig).where(ProjectConfig.eli_enabled == False)  # noqa: E712
            ).first()
        assert row is not None
        assert row.main_character_reference_url is None
    finally:
        app.dependency_overrides.pop(get_session, None)
