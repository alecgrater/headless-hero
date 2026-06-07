import json
from datetime import datetime, timezone

from sqlmodel import Session, SQLModel, create_engine


def test_update_script_queues_remote_profile_input_sync(monkeypatch):
    import api.scripts as scripts_api
    from models.script import Script, ScriptContent, UpdateScriptRequest

    engine = create_engine("sqlite:///:memory:")
    SQLModel.metadata.create_all(engine)
    calls = []
    monkeypatch.setattr(scripts_api, "_sync_remote_profile_input_async", lambda reason: calls.append(reason))

    content = ScriptContent.model_validate(
        {
            "title": "River Science",
            "segments": [
                {
                    "name": "The curve",
                    "scenes": [
                        {
                            "id": "scene-1",
                            "narration": "Rivers curve when the outer edge speeds up.",
                            "visual_prompt": "River curve",
                            "visual_mode": "full_frame",
                        }
                    ],
                }
            ],
        }
    )

    with Session(engine) as session:
        session.add(
            Script(
                id="script-1",
                brand_id="brand",
                topic_title="River Science",
                script_json=content.model_dump_json(),
                created_at=datetime(2026, 6, 1, tzinfo=timezone.utc),
            )
        )
        session.commit()

        edited = content.model_copy(deep=True)
        edited.segments[0].scenes[0].narration = "Rivers curve when fast water cuts the outer edge."
        scripts_api.update_script("script-1", UpdateScriptRequest(script=edited), session)

    assert calls == ["script_updated"]


def test_delete_script_queues_remote_profile_input_sync(monkeypatch):
    import api.scripts as scripts_api
    from models.script import Script, ScriptContent

    engine = create_engine("sqlite:///:memory:")
    SQLModel.metadata.create_all(engine)
    calls = []
    monkeypatch.setattr(scripts_api, "_sync_remote_profile_input_async", lambda reason: calls.append(reason))

    content = ScriptContent.model_validate(
        {
            "title": "River Science",
            "segments": [
                {
                    "name": "The curve",
                    "scenes": [
                        {
                            "id": "scene-1",
                            "narration": "Rivers curve when the outer edge speeds up.",
                            "visual_prompt": "River curve",
                            "visual_mode": "full_frame",
                        }
                    ],
                }
            ],
        }
    )

    with Session(engine) as session:
        session.add(
            Script(
                id="script-1",
                brand_id="brand",
                topic_title="River Science",
                script_json=content.model_dump_json(),
                created_at=datetime(2026, 6, 1, tzinfo=timezone.utc),
            )
        )
        session.commit()

        scripts_api.delete_script("script-1", session)

    assert calls == ["script_deleted"]
