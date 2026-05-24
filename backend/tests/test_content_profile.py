"""Tests for creator content profile caching."""

from datetime import datetime, timezone

from sqlmodel import Session, SQLModel, create_engine
from sqlmodel.pool import StaticPool


def _build_inmemory_engine():
    import models.content_profile  # noqa: F401
    import models.script  # noqa: F401

    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    SQLModel.metadata.create_all(engine)
    return engine


def _seed_script(engine, script_id: str, *, is_test_lab: bool):
    from models.script import Scene, Script, ScriptContent, Segment

    content = ScriptContent(
        title=f"Script {script_id}",
        segments=[
            Segment(
                name="Segment",
                scenes=[
                    Scene(
                        id=f"{script_id}-scene",
                        narration="A single line of narration.",
                        visual_prompt="A clean flat cartoon scene.",
                        duration_estimate_seconds=6,
                    )
                ],
            )
        ],
    )
    with Session(engine) as session:
        session.add(
            Script(
                id=script_id,
                brand_id="default",
                topic_title=f"Script {script_id}",
                topic_description="",
                script_json=content.model_dump_json(),
                is_test_lab=is_test_lab,
                created_at=datetime.now(timezone.utc),
            )
        )
        session.commit()


def test_cached_profile_staleness_ignores_test_lab_scripts(monkeypatch):
    engine = _build_inmemory_engine()
    _seed_script(engine, "normal-1", is_test_lab=False)
    _seed_script(engine, "test-lab-1", is_test_lab=True)

    from models.content_profile import ContentProfile
    import pipeline.content_profile as content_profile

    monkeypatch.setattr(content_profile, "engine", engine)
    with Session(engine) as session:
        session.add(
            ContentProfile(
                script_count=1,
                common_topics='["topic"]',
                narration_style="Plainspoken",
                visual_approach="Simple",
                typical_keywords='["topic"]',
                audience_profile="Curious viewers.",
                avg_segment_count=1.0,
                analyzed_at=datetime.now(timezone.utc),
            )
        )
        session.commit()

    profile = content_profile.get_cached_profile()

    assert profile is not None
    assert profile["script_count"] == 1
    assert profile["is_stale"] is False


def test_load_scripts_excludes_test_lab_scripts(monkeypatch):
    engine = _build_inmemory_engine()
    _seed_script(engine, "normal-1", is_test_lab=False)
    _seed_script(engine, "test-lab-1", is_test_lab=True)

    import pipeline.content_profile as content_profile

    monkeypatch.setattr(content_profile, "engine", engine)

    scripts = content_profile._load_scripts()

    assert [script.title for script in scripts] == ["Script normal-1"]
