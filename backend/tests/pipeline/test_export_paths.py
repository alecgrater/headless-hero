"""Tests for shared export naming rules."""

from pathlib import Path

from pipeline.export_paths import (
    longform_filename,
    project_downloads_folder,
    project_folder_name,
    shortform_filename,
)


def test_project_folder_name_uses_project_prefix_and_sanitizes():
    assert project_folder_name('Bad/Project: "Test"') == "[project] BadProject Test"


def test_longform_filename_format():
    assert longform_filename("Video", "Mystery Project", ".mp4") == (
        "[Longform] [Video] - Mystery Project.mp4"
    )


def test_shortform_filename_format():
    assert shortform_filename("SEO", "Opening Hook", "txt") == (
        "[Shortform] [SEO] - Opening Hook.txt"
    )


def test_project_downloads_folder_uses_configured_base(tmp_path, monkeypatch):
    monkeypatch.setenv("DOWNLOADS_DIR", str(tmp_path))
    folder = project_downloads_folder("Project Name")

    assert folder == Path(tmp_path / "[project] Project Name")
    assert folder.is_dir()
