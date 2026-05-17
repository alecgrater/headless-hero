from api import render as render_api
from pipeline.export_paths import longform_filename, project_downloads_folder


def test_find_rendered_longform_prefers_project_cache(tmp_path, monkeypatch):
    monkeypatch.setattr(render_api, "DATA_DIR", tmp_path)
    monkeypatch.setenv("EXPORT_FOLDER", str(tmp_path / "Exports"))

    script_id = "script-123"
    cache = tmp_path / "projects" / script_id / "renders" / "full_youtube.mp4"
    cache.parent.mkdir(parents=True)
    cache.write_bytes(b"video")

    path, url = render_api._find_rendered_longform(script_id, "Project Name")

    assert path == str(cache)
    assert url == f"/static/projects/{script_id}/renders/full_youtube.mp4"


def test_find_rendered_longform_detects_export_folder_video(tmp_path, monkeypatch):
    monkeypatch.setattr(render_api, "DATA_DIR", tmp_path)
    monkeypatch.setenv("EXPORT_FOLDER", str(tmp_path / "Exports"))

    folder = project_downloads_folder("Project Name")
    exported = folder / longform_filename("Video", "Project Name", ".mp4")
    exported.write_bytes(b"video")

    path, url = render_api._find_rendered_longform("script-123", "Project Name")

    assert path == str(exported)
    assert url is None


def test_find_rendered_longform_returns_missing(tmp_path, monkeypatch):
    monkeypatch.setattr(render_api, "DATA_DIR", tmp_path)
    monkeypatch.setenv("EXPORT_FOLDER", str(tmp_path / "Exports"))

    path, url = render_api._find_rendered_longform("script-123", "Project Name")

    assert path is None
    assert url is None
