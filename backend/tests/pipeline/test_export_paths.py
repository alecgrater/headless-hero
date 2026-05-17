"""Tests for shared export naming rules."""

from pathlib import Path

from pipeline.export_paths import (
    longform_filename,
    project_downloads_folder,
    project_folder_name,
    shortform_filename,
    shortform_video_filename,
)


def test_project_folder_name_prefixes_project_title_and_sanitizes():
    assert project_folder_name('Bad/Project: "Test"') == "[project] BadProject Test"


def test_longform_filename_format():
    assert longform_filename("Video", "Mystery Project", ".mp4") == (
        "[Longform] [Video] - Mystery Project.mp4"
    )


def test_shortform_filename_format():
    assert shortform_filename("SEO", "Opening Hook", "txt", index=1, total=8) == (
        "[Shortform 1∕8] [SEO] - Opening Hook.txt"
    )


def test_shortform_filename_thumbnail_with_index_total():
    assert shortform_filename("Thumbnail", "Design the Default", ".png", index=1, total=8) == (
        "[Shortform 1∕8] [Thumbnail] - Design the Default.png"
    )


def test_shortform_video_filename_uses_segment_name_with_index_total():
    assert shortform_video_filename("Design the Default", 1, 8) == (
        "[Shortform 1∕8] [Video] - Design the Default.mp4"
    )


def test_shortform_video_filename_uses_unicode_division_slash():
    result = shortform_video_filename("Foo", 3, 8)
    assert "/" not in result, f"Filename must not contain POSIX path separator: {result!r}"
    assert "∕" in result


def test_seo_markdown_filename_formats():
    assert longform_filename("SEO", "Mystery Project", ".md") == (
        "[Longform] [SEO] - Mystery Project.md"
    )
    assert shortform_filename("SEO", "Opening Hook", ".md", index=1, total=8) == (
        "[Shortform 1∕8] [SEO] - Opening Hook.md"
    )


def test_project_downloads_folder_uses_configured_base(tmp_path, monkeypatch):
    monkeypatch.setenv("EXPORT_FOLDER", str(tmp_path))
    monkeypatch.delenv("DOWNLOADS_DIR", raising=False)
    folder = project_downloads_folder("Project Name")

    assert folder == Path(tmp_path / "[project] Project Name")
    assert folder.is_dir()


def test_project_downloads_folder_prefers_downloads_dir(tmp_path, monkeypatch):
    downloads_dir = tmp_path / "Downloads"
    export_dir = tmp_path / "Exports"
    monkeypatch.setenv("DOWNLOADS_DIR", str(downloads_dir))
    monkeypatch.setenv("EXPORT_FOLDER", str(export_dir))

    folder = project_downloads_folder("Project Name")

    assert folder == Path(downloads_dir / "[project] Project Name")
    assert folder.is_dir()
