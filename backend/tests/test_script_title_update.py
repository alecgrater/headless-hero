import json

import pytest
from fastapi import HTTPException
from sqlmodel import Session, SQLModel, create_engine

from api.scripts import ensure_script_exports_folder, update_script, update_script_title
from models.script import (
    Scene,
    Script,
    ScriptContent,
    ScriptRating,
    ScriptRatingCategory,
    ScriptRatingCriterion,
    Segment,
    UpdateScriptRequest,
    UpdateScriptTitleRequest,
)
from pipeline.export_paths import longform_filename, project_downloads_folder, shortform_filename, shortform_video_filename


def _script_rating(overall: float = 7.4) -> ScriptRating:
    def category(criteria: dict[str, int], average: float) -> ScriptRatingCategory:
        return ScriptRatingCategory(
            average=average,
            explanation="Useful but can be sharper.",
            criteria={key: ScriptRatingCriterion(score=value) for key, value in criteria.items()},
        )

    return ScriptRating(
        viewer_retention=category({"hook_strength": 8, "curiosity_gaps": 7, "pacing_variance": 7}, 7.3),
        narrative_quality=category({"coherence": 7, "throughline": 6}, 6.5),
        script_craft=category({"sentence_variety": 8, "specificity": 9, "redundancy": 7, "word_economy": 8}, 8.0),
        audience_fit=category(
            {
                "assumed_knowledge_level": 8,
                "relatability": 7,
                "tone_consistency": 8,
                "emotional_range": 7,
            },
            7.5,
        ),
        seo_alignment=category({"title_hook_match": 7, "search_intent_match": 6, "rewatch_value": 7}, 6.7),
        overall=overall,
        model="gpt-5-mini",
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


def test_update_script_clears_rating_when_script_text_changes(tmp_path):
    engine = create_engine(f"sqlite:///{tmp_path / 'test.db'}")
    SQLModel.metadata.create_all(engine)
    content = ScriptContent(
        title="Rated Script",
        intro_hook="Original hook.",
        script_rating=_script_rating(),
        segments=[
            Segment(
                name="Segment",
                scenes=[Scene(id="scene-1", narration="Original narration.", visual_prompt="Visual.")],
            ),
        ],
    )

    with Session(engine) as session:
        session.add(
            Script(
                id="script-1",
                brand_id="brand-1",
                topic_title="Rated Script",
                script_json=content.model_dump_json(),
            )
        )
        session.commit()

        edited = content.model_copy(deep=True)
        edited.segments[0].scenes[0].narration = "Updated narration."
        response = update_script("script-1", UpdateScriptRequest(script=edited), session)
        stored = session.get(Script, "script-1")

    assert response.script.script_rating is None
    assert stored is not None
    assert json.loads(stored.script_json)["script_rating"] is None


def test_update_script_preserves_rating_when_non_text_media_changes(tmp_path):
    engine = create_engine(f"sqlite:///{tmp_path / 'test.db'}")
    SQLModel.metadata.create_all(engine)
    content = ScriptContent(
        title="Rated Script",
        intro_hook="Original hook.",
        script_rating=_script_rating(),
        segments=[
            Segment(
                name="Segment",
                scenes=[Scene(id="scene-1", narration="Original narration.", visual_prompt="Visual.")],
            ),
        ],
    )

    with Session(engine) as session:
        session.add(
            Script(
                id="script-1",
                brand_id="brand-1",
                topic_title="Rated Script",
                script_json=content.model_dump_json(),
            )
        )
        session.commit()

        edited = content.model_copy(deep=True)
        edited.segments[0].scenes[0].image_url = "/static/projects/script-1/images/scene-1.png"
        response = update_script("script-1", UpdateScriptRequest(script=edited), session)
        stored = session.get(Script, "script-1")

    assert response.script.script_rating is not None
    assert response.script.script_rating.overall == 7.4
    assert stored is not None
    assert json.loads(stored.script_json)["script_rating"]["overall"] == 7.4


def test_ensure_script_exports_folder_uses_topic_title_and_creates_folder(tmp_path, monkeypatch):
    monkeypatch.setenv("DOWNLOADS_DIR", str(tmp_path / "Exports"))
    engine = create_engine(f"sqlite:///{tmp_path / 'test.db'}")
    SQLModel.metadata.create_all(engine)
    content = ScriptContent(
        title="Stale JSON Title",
        segments=[Segment(name="Segment", scenes=[Scene(id="scene-1", narration="One.", visual_prompt="Visual.")])],
    )

    with Session(engine) as session:
        session.add(
            Script(
                id="script-1",
                brand_id="brand-1",
                topic_title="Canonical Project",
                script_json=content.model_dump_json(),
            )
        )
        session.commit()

        response = ensure_script_exports_folder("script-1", session)

    folder = tmp_path / "Exports" / "[project] Canonical Project"
    assert response.folder_path == str(folder)
    assert folder.is_dir()


def test_ensure_script_exports_folder_repairs_discovered_export_folder(tmp_path, monkeypatch):
    monkeypatch.setenv("DOWNLOADS_DIR", str(tmp_path / "Exports"))
    engine = create_engine(f"sqlite:///{tmp_path / 'test.db'}")
    SQLModel.metadata.create_all(engine)
    content = ScriptContent(
        title="New Title",
        short_form_seo_metadata={
            "shorts": [
                {"index": 1, "title": "New Title - First", "description": "First desc", "hashtags": [], "tags": []},
            ]
        },
        segments=[
            Segment(name="First", scenes=[Scene(id="scene-1", narration="One.", visual_prompt="Visual.")]),
        ],
    )
    old_folder = project_downloads_folder("Much Older Title")
    (old_folder / shortform_video_filename("First", 1, 1)).write_bytes(b"short")
    (old_folder / longform_filename("Video", "Much Older Title", ".mp4")).write_bytes(b"video")

    with Session(engine) as session:
        session.add(
            Script(
                id="script-1",
                brand_id="brand-1",
                topic_title="New Title",
                script_json=content.model_dump_json(),
            )
        )
        session.commit()

        response = ensure_script_exports_folder("script-1", session)

    new_folder = tmp_path / "Exports" / "[project] New Title"
    assert response.folder_path == str(new_folder)
    assert not old_folder.exists()
    assert (new_folder / shortform_video_filename("First", 1, 1)).read_bytes() == b"short"
    assert (new_folder / longform_filename("Video", "New Title", ".mp4")).read_bytes() == b"video"
    assert (new_folder / shortform_filename("SEO", "First", ".md", index=1, total=1)).is_file()


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


def test_update_script_title_renames_discovered_exports_when_exact_old_folder_missing(tmp_path, monkeypatch, caplog):
    monkeypatch.setenv("DOWNLOADS_DIR", str(tmp_path / "Exports"))
    caplog.set_level("INFO")
    engine = create_engine(f"sqlite:///{tmp_path / 'test.db'}")
    SQLModel.metadata.create_all(engine)
    content = ScriptContent(
        title="Current Title BOOP",
        short_form_seo_metadata={
            "shorts": [
                {"index": 1, "title": "Current Title BOOP - First", "description": "First desc", "hashtags": [], "tags": []},
                {"index": 2, "title": "Current Title BOOP - Second", "description": "Second desc", "hashtags": [], "tags": []},
            ]
        },
        segments=[
            Segment(name="First", scenes=[Scene(id="scene-1", narration="One.", visual_prompt="Visual.")]),
            Segment(name="Second", scenes=[Scene(id="scene-2", narration="Two.", visual_prompt="Visual.")]),
        ],
    )
    discovered_folder = project_downloads_folder("Much Older Export Title")
    (discovered_folder / shortform_video_filename("First", 1, 2)).write_bytes(b"first")
    (discovered_folder / shortform_video_filename("Second", 2, 2)).write_bytes(b"second")
    (discovered_folder / longform_filename("Video", "Much Older Export Title", ".mp4")).write_bytes(b"video")

    with Session(engine) as session:
        session.add(
            Script(
                id="script-1",
                brand_id="brand-1",
                topic_title="Current Title BOOP",
                script_json=content.model_dump_json(),
            )
        )
        session.commit()

        update_script_title(
            "script-1",
            UpdateScriptTitleRequest(title="Current Title"),
            session,
        )

    new_folder = project_downloads_folder("Current Title", create=False)
    assert not discovered_folder.exists()
    assert (new_folder / shortform_video_filename("First", 1, 2)).read_bytes() == b"first"
    assert (new_folder / shortform_video_filename("Second", 2, 2)).read_bytes() == b"second"
    assert (new_folder / longform_filename("Video", "Current Title", ".mp4")).read_bytes() == b"video"
    messages = [record.getMessage() for record in caplog.records]
    assert any("Discovered export project folder for title rename" in msg for msg in messages)


def test_update_script_title_does_not_discover_unrelated_longform_only_folder(tmp_path, monkeypatch, caplog):
    monkeypatch.setenv("DOWNLOADS_DIR", str(tmp_path / "Exports"))
    caplog.set_level("INFO")
    engine = create_engine(f"sqlite:///{tmp_path / 'test.db'}")
    SQLModel.metadata.create_all(engine)
    content = ScriptContent(
        title="Current Title BOOP",
        segments=[
            Segment(name="First", scenes=[Scene(id="scene-1", narration="One.", visual_prompt="Visual.")]),
        ],
    )
    unrelated_folder = project_downloads_folder("Unrelated Project")
    (unrelated_folder / longform_filename("Video", "Unrelated Project", ".mp4")).write_bytes(b"video")
    (unrelated_folder / longform_filename("Thumbnail", "Unrelated Project", ".png")).write_bytes(b"thumb")

    with Session(engine) as session:
        session.add(
            Script(
                id="script-1",
                brand_id="brand-1",
                topic_title="Current Title BOOP",
                script_json=content.model_dump_json(),
            )
        )
        session.commit()

        update_script_title(
            "script-1",
            UpdateScriptTitleRequest(title="Current Title"),
            session,
        )

    new_folder = project_downloads_folder("Current Title", create=False)
    assert unrelated_folder.exists()
    assert not new_folder.exists()
    assert (unrelated_folder / longform_filename("Video", "Unrelated Project", ".mp4")).read_bytes() == b"video"
    messages = [record.getMessage() for record in caplog.records]
    assert any("No content-matching export folder found" in msg for msg in messages)


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
