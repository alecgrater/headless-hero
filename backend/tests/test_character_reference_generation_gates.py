"""Tests for image-generation routes blocked by missing character references."""

from fastapi.testclient import TestClient
from sqlmodel import Session, SQLModel, create_engine
from sqlmodel.pool import StaticPool

from api import app
from database import get_session
from models.project_config import ProjectConfig
from models.script import MainCharacter, Scene, Script, ScriptContent, Segment


def _build_engine():
    import models.api_usage  # noqa: F401
    import models.brand  # noqa: F401
    import models.credential  # noqa: F401
    import models.generation_duration  # noqa: F401
    import models.project_config  # noqa: F401
    import models.publish  # noqa: F401
    import models.script  # noqa: F401
    import models.settings  # noqa: F401

    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    SQLModel.metadata.create_all(engine)
    return engine


def _client(engine):
    def _override_get_session():
        with Session(engine) as session:
            yield session

    app.dependency_overrides[get_session] = _override_get_session
    return TestClient(app)


def _seed_script(engine, script_id: str, *, format_id: str = "youtube-listicle") -> None:
    content = ScriptContent(
        title="Test Project",
        format_id=format_id,
        main_character=MainCharacter(
            name="Guide Max",
            appearance="green jacket and round glasses",
            vibe="curious and steady",
        ),
        cinematic_thumbnail_prompt="a dramatic transformation",
        segments=[
            Segment(
                name="Segment 1",
                scenes=[
                    Scene(
                        id="s1",
                        narration="x",
                        visual_prompt="x",
                        visual_beat="static",
                    ),
                ],
            )
        ],
    )
    with Session(engine) as session:
        session.add(
            Script(
                id=script_id,
                brand_id="default",
                format_id=format_id,
                topic_title="Test Project",
                topic_description="",
                script_json=content.model_dump_json(),
            )
        )
        session.add(ProjectConfig(script_id=script_id, eli_enabled=False))
        session.commit()


def test_recomposite_thumbnail_requires_character_reference():
    engine = _build_engine()
    _seed_script(engine, "recomposite-blocked")
    client = _client(engine)

    try:
        res = client.post(
            "/api/thumbnail/recomposite",
            json={"script_id": "recomposite-blocked"},
        )
    finally:
        app.dependency_overrides.pop(get_session, None)

    assert res.status_code == 400
    assert "Active style preset is missing" in res.json()["detail"]


def test_split_progression_thumbnail_requires_character_reference():
    engine = _build_engine()
    _seed_script(engine, "split-blocked", format_id="life-as-a")
    client = _client(engine)

    try:
        res = client.post(
            "/api/thumbnail/regenerate-split-progression",
            json={"script_id": "split-blocked"},
        )
    finally:
        app.dependency_overrides.pop(get_session, None)

    assert res.status_code == 400
    assert "Active style preset is missing" in res.json()["detail"]


def test_export_test_regen_images_requires_character_reference():
    engine = _build_engine()
    _seed_script(engine, "export-test-blocked")
    client = _client(engine)

    try:
        res = client.post(
            "/api/render/export-test",
            json={
                "script_id": "export-test-blocked",
                "regen_images": True,
                "regen_audio": False,
                "regen_fx": False,
                "regen_eli": False,
            },
        )
    finally:
        app.dependency_overrides.pop(get_session, None)

    assert res.status_code == 400
    assert "Active style preset is missing" in res.json()["detail"]
