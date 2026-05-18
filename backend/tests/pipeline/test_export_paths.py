"""Tests for shared export naming rules."""

from pathlib import Path

from pipeline.export_paths import (
    longform_filename,
    project_downloads_folder,
    project_folder_name,
    rename_project_exports,
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


def test_project_downloads_folder_uses_configured_exports_base(tmp_path, monkeypatch):
    monkeypatch.setenv("DOWNLOADS_DIR", str(tmp_path))
    folder = project_downloads_folder("Project Name")

    assert folder == Path(tmp_path / "[project] Project Name")
    assert folder.is_dir()


def test_project_downloads_folder_uses_exports_setting(tmp_path, monkeypatch):
    exports_dir = tmp_path / "Exports"
    monkeypatch.setenv("DOWNLOADS_DIR", str(exports_dir))

    folder = project_downloads_folder("Project Name")

    assert folder == Path(exports_dir / "[project] Project Name")
    assert folder.is_dir()


def test_rename_project_exports_moves_folder_and_title_based_files(tmp_path, monkeypatch):
    monkeypatch.setenv("DOWNLOADS_DIR", str(tmp_path / "Exports"))
    old_folder = project_downloads_folder("Old Project")
    old_video = old_folder / longform_filename("Video", "Old Project", ".mp4")
    old_video.write_bytes(b"video")
    short_video = old_folder / shortform_video_filename("Segment", 1, 2)
    short_video.write_bytes(b"short")

    new_folder = rename_project_exports("Old Project", "New Project")

    assert new_folder == Path(tmp_path / "Exports" / "[project] New Project")
    assert not old_folder.exists()
    assert (new_folder / longform_filename("Video", "New Project", ".mp4")).read_bytes() == b"video"
    assert (new_folder / shortform_video_filename("Segment", 1, 2)).read_bytes() == b"short"
