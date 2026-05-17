"""Tests for shared export naming rules."""

from pathlib import Path

from pipeline.export_paths import (
    longform_filename,
    project_downloads_folder,
    project_folder_name,
    shortform_filename,
)


def test_project_folder_name_uses_plain_project_title_and_sanitizes():
    assert project_folder_name('Bad/Project: "Test"') == "BadProject Test"


def test_longform_filename_format():
    assert longform_filename("Video", "Mystery Project", ".mp4") == (
        "[Longform] [Video] - Mystery Project.mp4"
    )


def test_shortform_filename_format():
    assert shortform_filename("SEO", "Opening Hook", "txt") == (
        "[Shortform] [SEO] - Opening Hook.txt"
    )


def test_seo_markdown_filename_formats():
    assert longform_filename("SEO", "Mystery Project", ".md") == (
        "[Longform] [SEO] - Mystery Project.md"
    )
    assert shortform_filename("SEO", "Opening Hook", ".md") == (
        "[Shortform] [SEO] - Opening Hook.md"
    )


def test_project_downloads_folder_uses_configured_base(tmp_path, monkeypatch):
    monkeypatch.setenv("EXPORT_FOLDER", str(tmp_path))
    monkeypatch.delenv("DOWNLOADS_DIR", raising=False)
    folder = project_downloads_folder("Project Name")

    assert folder == Path(tmp_path / "Project Name")
    assert folder.is_dir()


def test_project_downloads_folder_prefers_downloads_dir(tmp_path, monkeypatch):
    downloads_dir = tmp_path / "Downloads"
    export_dir = tmp_path / "Exports"
    monkeypatch.setenv("DOWNLOADS_DIR", str(downloads_dir))
    monkeypatch.setenv("EXPORT_FOLDER", str(export_dir))

    folder = project_downloads_folder("Project Name")

    assert folder == Path(downloads_dir / "Project Name")
    assert folder.is_dir()
