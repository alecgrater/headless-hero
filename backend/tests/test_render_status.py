import json
import os
from pathlib import Path

from api import render as render_api
from api import short_form as short_form_api
from api import upload_suite as upload_suite_api
from models.script import Scene, Script, ScriptContent, Segment
from pipeline import short_form_thumbnails as thumbs
from pipeline import remotion_render
from pipeline import short_form_render
from pipeline.export_paths import longform_filename, project_downloads_folder, shortform_filename, shortform_video_filename
from pipeline.script_helpers import _format_shortform_seo_markdown
from pipeline.short_form_thumbnails import short_thumbnail_filename
from sqlmodel import Session, SQLModel, create_engine


def test_find_rendered_longform_prefers_project_cache(tmp_path, monkeypatch):
    monkeypatch.setattr(render_api, "DATA_DIR", tmp_path)
    monkeypatch.setenv("DOWNLOADS_DIR", str(tmp_path / "Exports"))

    script_id = "script-123"
    cache = tmp_path / "projects" / script_id / "renders" / "full_youtube.mp4"
    cache.parent.mkdir(parents=True)
    cache.write_bytes(b"video")

    path, url = render_api._find_rendered_longform(script_id, "Project Name")

    assert path == str(cache)
    assert url == f"/static/projects/{script_id}/renders/full_youtube.mp4"


def test_find_rendered_longform_detects_export_folder_video(tmp_path, monkeypatch):
    monkeypatch.setattr(render_api, "DATA_DIR", tmp_path)
    monkeypatch.setenv("DOWNLOADS_DIR", str(tmp_path / "Exports"))

    folder = project_downloads_folder("Project Name")
    exported = folder / longform_filename("Video", "Project Name", ".mp4")
    exported.write_bytes(b"video")

    path, url = render_api._find_rendered_longform("script-123", "Project Name")

    assert path == str(exported)
    assert url is None


def test_find_rendered_longform_detects_labelled_export_after_title_edit(tmp_path, monkeypatch):
    monkeypatch.setattr(render_api, "DATA_DIR", tmp_path)
    monkeypatch.setenv("DOWNLOADS_DIR", str(tmp_path / "Exports"))

    folder = project_downloads_folder("Project Name")
    exported = folder / longform_filename("Video", "Old Project Name", ".mp4")
    exported.write_bytes(b"video")

    path, url = render_api._find_rendered_longform("script-123", "Project Name")

    assert path == str(exported)
    assert url is None


def test_find_rendered_longform_returns_missing(tmp_path, monkeypatch):
    monkeypatch.setattr(render_api, "DATA_DIR", tmp_path)
    monkeypatch.setenv("DOWNLOADS_DIR", str(tmp_path / "Exports"))

    path, url = render_api._find_rendered_longform("script-123", "Project Name")

    assert path is None
    assert url is None


def test_render_router_has_no_audio_only_export_endpoint():
    paths = {route.path for route in render_api.router.routes}

    assert "/export-audio" not in paths
    assert "/api/render/export-audio" not in paths


def test_format_shortform_seo_markdown_includes_platform_sections():
    markdown = _format_shortform_seo_markdown(
        {
            "index": 2,
            "title": "Project - Segment",
            "description": "Caption line one.\nCaption line two.",
            "hashtags": ["#TinyHabits", "#StartSmall"],
            "tags": ["tiny habits", "self improvement"],
        }
    )

    assert markdown == (
        "# Short 2\n\n"
        "# Youtube\n\n"
        "## Title\n\n"
        "Project - Segment\n\n"
        "## Description\n\n"
        "Caption line one.\nCaption line two.\n\n"
        "## Hashtags\n\n"
        "#TinyHabits #StartSmall\n\n"
        "## SEO Tags\n\n"
        "tiny habits, self improvement\n\n"
        "# Tiktok / Insta\n\n"
        "Project - Segment\n\n"
        "Caption line one.\nCaption line two.\n\n"
        "#TinyHabits #StartSmall\n\n"
        "tiny habits, self improvement\n"
    )


def test_export_bundle_does_not_include_standalone_audio_file(tmp_path, monkeypatch):
    monkeypatch.setattr(render_api, "DATA_DIR", tmp_path)
    monkeypatch.setenv("DOWNLOADS_DIR", str(tmp_path / "Exports"))

    engine = create_engine(f"sqlite:///{tmp_path / 'test.db'}")
    SQLModel.metadata.create_all(engine)

    script_id = "script-123"
    project_title = "Project Name"
    content = ScriptContent(
        title=project_title,
        seo_metadata={"youtube": {"title": "Title", "description": "Desc", "tags": ["tag"]}},
        short_form_seo_metadata={"shorts": []},
        segments=[
            Segment(
                name="Segment",
                scenes=[
                    Scene(
                        id="scene-1",
                        narration="Hello",
                        visual_prompt="A test image",
                        audio_url=f"/static/projects/{script_id}/audio/scene-1.mp3",
                        audio_duration_seconds=1.0,
                    )
                ],
            )
        ],
    )

    renders = tmp_path / "projects" / script_id / "renders"
    renders.mkdir(parents=True)
    (renders / "full_youtube.mp4").write_bytes(b"video")
    (renders / "full_youtube.mp4.json").write_text(
        json.dumps({"subtitle_render_fingerprint": remotion_render.subtitle_render_fingerprint(content)}),
        encoding="utf-8",
    )
    folder = project_downloads_folder(project_title)
    stale_audio = folder / longform_filename("Audio", project_title, ".mp3")
    stale_audio.write_bytes(b"stale audio from an older export")

    with Session(engine) as session:
        session.add(
            Script(
                id=script_id,
                brand_id="brand-1",
                topic_title=project_title,
                topic_description="",
                script_json=content.model_dump_json(),
            )
        )
        session.commit()

        result = render_api.export_bundle(render_api.ExportBundleRequest(script_id=script_id), session=session)

    assert longform_filename("Audio", project_title, ".mp3") not in result.files
    assert not stale_audio.exists()
    assert not (renders / "full_audio.mp3").exists()
    exported_video = folder / longform_filename("Video", project_title, ".mp4")
    assert exported_video.exists()
    assert exported_video.stat().st_ino == (renders / "full_youtube.mp4").stat().st_ino


def test_export_short_form_videos_hardlinks_project_cache(tmp_path, monkeypatch):
    monkeypatch.setattr(short_form_api, "DATA_DIR", tmp_path)
    monkeypatch.setattr(short_form_render, "DATA_DIR", tmp_path)
    monkeypatch.setenv("DOWNLOADS_DIR", str(tmp_path / "Exports"))

    engine = create_engine(f"sqlite:///{tmp_path / 'test.db'}")
    SQLModel.metadata.create_all(engine)

    script_id = "script-123"
    project_title = "Project Name"
    content = ScriptContent(
        title=project_title,
        segments=[
            Segment(
                name="First Segment",
                scenes=[
                    Scene(id="title-1", narration="", visual_prompt="", is_title_card=True),
                    Scene(id="scene-1", narration="Hello", visual_prompt="A test image"),
                ],
            )
        ],
    )
    cache = tmp_path / "projects" / script_id / "renders" / "shorts" / "0.mp4"
    cache.parent.mkdir(parents=True)
    cache.write_bytes(b"short video")
    (cache.parent / "0.json").write_text(
        json.dumps({
            "segment_idx": 0,
            "hook_scene_count": 0,
            "part_indicator": "",
            "subtitle_render_fingerprint": remotion_render.subtitle_render_fingerprint(content),
        }),
        encoding="utf-8",
    )

    with Session(engine) as session:
        session.add(
            Script(
                id=script_id,
                brand_id="brand-1",
                topic_title=project_title,
                topic_description="",
                script_json=content.model_dump_json(),
            )
        )
        session.commit()

        result = short_form_api.export_short_form_videos(
            short_form_api.ExportShortVideosRequest(script_id=script_id),
            session=session,
        )

    exported_video = Path(result.paths[0])
    assert exported_video.read_bytes() == b"short video"
    assert exported_video.stat().st_ino == cache.stat().st_ino


def test_export_file_status_counts_only_project_export_files(tmp_path, monkeypatch):
    monkeypatch.setenv("DOWNLOADS_DIR", str(tmp_path / "Exports"))
    monkeypatch.setattr(upload_suite_api, "DATA_DIR", tmp_path)

    engine = create_engine(f"sqlite:///{tmp_path / 'test.db'}")
    SQLModel.metadata.create_all(engine)

    script_id = "script-123"
    project_title = "Project Name"
    content = ScriptContent(
        title=project_title,
        segments=[
            Segment(name="First Segment", scenes=[]),
            Segment(name="Second Segment", scenes=[]),
        ],
    )

    folder = project_downloads_folder(project_title)
    (folder / longform_filename("Video", project_title, ".mp4")).write_bytes(b"video")
    (folder / longform_filename("SEO", project_title, ".md")).write_text("seo", encoding="utf-8")
    (folder / shortform_video_filename("First Segment", 1, 2)).write_bytes(b"short")
    (folder / shortform_filename("Thumbnail", "First Segment", ".png", index=1, total=2)).write_bytes(b"thumb")
    (folder / shortform_filename("SEO", "Second Segment", ".md", index=2, total=2)).write_text("seo", encoding="utf-8")

    cache = tmp_path / "projects" / script_id / "renders" / "shorts"
    cache.mkdir(parents=True)
    (cache / "1.mp4").write_bytes(b"cached short should not count")

    with Session(engine) as session:
        session.add(
            Script(
                id=script_id,
                brand_id="brand-1",
                topic_title=project_title,
                topic_description="",
                script_json=content.model_dump_json(),
            )
        )
        session.commit()

        result = upload_suite_api.export_file_status(script_id, session=session)

    assert result.exported == 5
    assert result.total == 9
    assert result.categories["longform_video"].exported == 1
    assert result.categories["longform_thumbnail"].exported == 0
    assert result.categories["longform_seo"].exported == 1
    assert result.categories["shortform_videos"].exported == 1
    assert result.categories["shortform_thumbnails"].exported == 1
    assert result.categories["shortform_seo"].exported == 1


def test_upload_suite_thumbnail_prefers_newer_current_cache_over_stale_export(tmp_path, monkeypatch):
    monkeypatch.setenv("DOWNLOADS_DIR", str(tmp_path / "Exports"))
    monkeypatch.setattr(upload_suite_api, "DATA_DIR", tmp_path)
    monkeypatch.setattr(thumbs, "DATA_DIR", tmp_path)

    script_id = "script-123"
    project_title = "Project Name"
    content = ScriptContent(
        title=project_title,
        format_id="life-as-a",
        segments=[
            Segment(name="First Segment", scenes=[]),
            Segment(name="Second Segment", scenes=[]),
        ],
    )

    folder = project_downloads_folder(project_title)
    exported = folder / short_thumbnail_filename("Second Segment", 2, 2)
    exported.write_bytes(b"old exported thumbnail")

    cache = tmp_path / "projects" / script_id / "renders" / "short_thumbnails"
    cache.mkdir(parents=True)
    cached = cache / "1.png"
    cached.write_bytes(b"new cached thumbnail")
    (cache / "1.json").write_text(
        '{"segment_idx": 1, "part_indicator": "Part 2/2"}',
        encoding="utf-8",
    )

    stale_time = 1_700_000_000
    current_time = stale_time + 60
    exported.touch()
    cached.touch()
    os.utime(exported, (stale_time, stale_time))
    os.utime(cached, (current_time, current_time))

    assert upload_suite_api._short_thumbnail_path(
        script_id,
        folder,
        "Second Segment",
        1,
        content,
    ) == cached
