import json
from datetime import datetime, timezone

from sqlmodel import Session, SQLModel, create_engine


def test_build_content_profile_input_snapshot_exports_real_scripts_only(monkeypatch):
    import pipeline.content_profile_snapshot as snapshot_module
    from models.script import Script

    engine = create_engine("sqlite:///:memory:")
    SQLModel.metadata.create_all(engine)
    monkeypatch.setattr(snapshot_module, "engine", engine)

    script_payload = {
        "title": "Why Rivers Bend",
        "format_id": "youtube-listicle",
        "segments": [
            {
                "name": "The curve",
                "scenes": [
                    {
                        "id": "scene-1",
                        "narration": "A river starts carving sideways when the outside edge speeds up.",
                        "visual_prompt": "Aerial river bend",
                        "visual_mode": "continuous",
                    }
                ],
            }
        ],
    }

    with Session(engine) as session:
        session.add(
            Script(
                id="real-script",
                brand_id="brand",
                format_id="youtube-listicle",
                topic_title="River Science",
                topic_description="How rivers meander",
                script_json=json.dumps(script_payload),
                created_at=datetime(2026, 6, 1, tzinfo=timezone.utc),
            )
        )
        session.add(
            Script(
                id="test-lab-script",
                brand_id="brand",
                is_test_lab=True,
                topic_title="Hidden test",
                script_json=json.dumps(script_payload),
            )
        )
        session.commit()

    snapshot = snapshot_module.build_content_profile_input_snapshot(
        now=datetime(2026, 6, 7, 12, 0, tzinfo=timezone.utc)
    )

    assert snapshot["version"] == 1
    assert snapshot["source"] == "headless-hero-content-profile-input"
    assert snapshot["generated_at"] == "2026-06-07T12:00:00+00:00"
    assert snapshot["script_count"] == 1
    assert snapshot["scripts"][0]["id"] == "real-script"
    assert snapshot["scripts"][0]["title"] == "River Science"
    assert snapshot["scripts"][0]["segments"][0]["scenes"][0]["visual_mode"] == "continuous"
    assert snapshot["scripts"][0]["segments"][0]["scenes"][0]["narration"].startswith("A river")
