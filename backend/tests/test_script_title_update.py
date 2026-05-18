import json

import pytest
from fastapi import HTTPException
from sqlmodel import Session, SQLModel, create_engine

from api.scripts import update_script, update_script_title
from models.script import (
    Scene,
    Script,
    ScriptContent,
    Segment,
    UpdateScriptRequest,
    UpdateScriptTitleRequest,
)
from pipeline.export_paths import longform_filename, project_downloads_folder, shortform_filename, shortform_video_filename


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


def test_update_script_title_renames_existing_exports_and_short_seo(tmp_path, monkeypatch, caplog):
    monkeypatch.setenv("DOWNLOADS_DIR", str(tmp_path / "Exports"))
    caplog.set_level("INFO")
    engine = create_engine(f"sqlite:///{tmp_path / 'test.db'}")
    SQLModel.metadata.create_all(engine)
    content = ScriptContent(
        title="Old Title",
        seo_metadata={"youtube": {"title": "Old Title", "description": "Desc", "tags": ["tag"]}},
        short_form_seo_metadata={
            "shorts": [
                {"index": 1, "title": "Old Title - First", "description": "First desc", "hashtags": ["#One"], "tags": ["one"]},
                {"index": 2, "title": "Old Title - Second", "description": "Second desc", "hashtags": ["#Two"], "tags": ["two"]},
            ]
        },
        segments=[
            Segment(name="First", scenes=[Scene(id="scene-1", narration="One.", visual_prompt="Visual.")]),
            Segment(name="Second", scenes=[Scene(id="scene-2", narration="Two.", visual_prompt="Visual.")]),
        ],
    )
    old_folder = project_downloads_folder("Old Title")
    (old_folder / longform_filename("Video", "Old Title", ".mp4")).write_bytes(b"video")
    (old_folder / longform_filename("SEO", "Old Title", ".md")).write_text("old seo", encoding="utf-8")
    (old_folder / shortform_video_filename("First", 1, 2)).write_bytes(b"short")
    (old_folder / shortform_filename("SEO", "First", ".md", index=1, total=2)).write_text("old short", encoding="utf-8")

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

        update_script_title(
            "script-1",
            UpdateScriptTitleRequest(title="New Title"),
            session,
        )
        stored = session.get(Script, "script-1")

    new_folder = project_downloads_folder("New Title", create=False)
    stored_content = json.loads(stored.script_json)
    assert not old_folder.exists()
    assert (new_folder / longform_filename("Video", "New Title", ".mp4")).read_bytes() == b"video"
    assert (new_folder / shortform_video_filename("First", 1, 2)).read_bytes() == b"short"
    assert stored_content["seo_metadata"]["youtube"]["title"] == "New Title"
    assert [item["title"] for item in stored_content["short_form_seo_metadata"]["shorts"]] == [
        "New Title - First",
        "New Title - Second",
    ]
    assert "New Title" in (new_folder / longform_filename("SEO", "New Title", ".md")).read_text(encoding="utf-8")
    assert "New Title - First" in (
        new_folder / shortform_filename("SEO", "First", ".md", index=1, total=2)
    ).read_text(encoding="utf-8")
    messages = [record.getMessage() for record in caplog.records]
    assert any("Updating script title for script-1 from 'Old Title' to 'New Title'" in msg for msg in messages)
    assert any("Renamed export project folder" in msg for msg in messages)
    assert any("Renamed export file" in msg and "New Title.mp4" in msg for msg in messages)
    assert any("Retitled stored short-form SEO titles for 2 shorts" in msg for msg in messages)
    assert any("Refreshed exported short-form SEO markdown" in msg for msg in messages)


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


def test_update_script_preserves_record_title_when_body_has_stale_title(tmp_path):
    engine = create_engine(f"sqlite:///{tmp_path / 'test.db'}")
    SQLModel.metadata.create_all(engine)
    stale_content = ScriptContent(title="Old Title", segments=[])

    with Session(engine) as session:
        session.add(
            Script(
                id="script-1",
                brand_id="brand-1",
                topic_title="New Title",
                script_json=ScriptContent(title="New Title", segments=[]).model_dump_json(),
            )
        )
        session.commit()

        updated = update_script(
            "script-1",
            UpdateScriptRequest(script=stale_content),
            session,
        )
        stored = session.get(Script, "script-1")

    assert updated.topic_title == "New Title"
    assert updated.script.title == "New Title"
    assert stored is not None
    assert json.loads(stored.script_json)["title"] == "New Title"
