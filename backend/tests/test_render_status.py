from api import render as render_api
from models.script import Scene, Script, ScriptContent, Segment
from pipeline.export_paths import longform_filename, project_downloads_folder
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
    markdown = render_api._format_shortform_seo_markdown(
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
    assert (folder / longform_filename("Video", project_title, ".mp4")).exists()
