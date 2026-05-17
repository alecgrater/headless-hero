import json

import pytest
from fastapi import HTTPException
from sqlmodel import Session, SQLModel, create_engine

from api.scripts import update_script_title
from models.script import (
    Scene,
    Script,
    ScriptContent,
    Segment,
    UpdateScriptTitleRequest,
)


def test_update_script_title_updates_record_and_script_json(tmp_path):
    engine = create_engine(f"sqlite:///{tmp_path / 'test.db'}")
    SQLModel.metadata.create_all(engine)
    content = ScriptContent(
        title="Old Title",
        segments=[
            Segment(
                name="Segment",
                scenes=[
                    Scene(
                        id="scene-1",
                        narration="Narration.",
                        visual_prompt="Visual.",
                    ),
                ],
            ),
        ],
    )

    with Session(engine) as session:
        record = Script(
            id="script-1",
            brand_id="brand-1",
            topic_title="Old Title",
            script_json=content.model_dump_json(),
        )
        session.add(record)
        session.commit()

        updated = update_script_title(
            "script-1",
            UpdateScriptTitleRequest(title="  New Title  "),
            session,
        )
        stored = session.get(Script, "script-1")

    assert updated.topic_title == "New Title"
    assert updated.script.title == "New Title"
    assert stored is not None
    assert stored.topic_title == "New Title"
    assert json.loads(stored.script_json)["title"] == "New Title"


def test_update_script_title_rejects_blank_after_trim(tmp_path):
    engine = create_engine(f"sqlite:///{tmp_path / 'test.db'}")
    SQLModel.metadata.create_all(engine)
    content = ScriptContent(title="Old Title", segments=[])

    with Session(engine) as session:
        session.add(
            Script(
                id="script-1",
                brand_id="brand-1",
                topic_title="Old Title",
                script_json=content.model_dump_json(),
            )
        )
        session.commit()

        with pytest.raises(HTTPException) as exc:
            update_script_title(
                "script-1",
                UpdateScriptTitleRequest(title=" "),
                session,
            )

    assert exc.value.status_code == 422
