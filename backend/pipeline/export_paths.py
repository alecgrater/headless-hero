"""Shared filesystem naming rules for user-facing exports."""

from __future__ import annotations

import logging
import os
import re
import shutil
from pathlib import Path
from typing import Literal

from config import DEFAULT_EXPORTS_DIR, sanitize_filename

logger = logging.getLogger(__name__)

ExportKind = Literal["Longform", "Shortform"]
ExportAsset = Literal["Thumbnail", "SEO", "Video", "Audio"]

# U+2215 division slash — visually like "/" but filesystem-safe (POSIX reserves U+002F).
SHORTFORM_SLASH = "∕"


def downloads_base() -> Path:
    """Return the configured base directory for final exported project assets."""
    configured = os.environ.get("DOWNLOADS_DIR", "").strip()
    return Path(configured).expanduser() if configured else DEFAULT_EXPORTS_DIR


def project_folder_name(project_title: str) -> str:
    """Return the standard Downloads folder name for a project."""
    safe_title = sanitize_filename(project_title or "Untitled")
    return f"[project] {safe_title}"


def project_downloads_folder(project_title: str, *, create: bool = True) -> Path:
    """Return the configured export project folder, creating it by default."""
    folder = downloads_base() / project_folder_name(project_title)
    if create:
        folder.mkdir(parents=True, exist_ok=True)
    return folder


def rename_project_exports(old_title: str, new_title: str, *, source_folder: Path | None = None) -> Path:
    """Move an existing project export folder and title-based filenames to a new title."""
    old_folder = source_folder or project_downloads_folder(old_title, create=False)
    new_folder = project_downloads_folder(new_title, create=False)
    if old_folder == new_folder:
        logger.info("Export project folder already matches title: %s", new_folder)
        return new_folder

    if old_folder.is_dir():
        new_folder.parent.mkdir(parents=True, exist_ok=True)
        if new_folder.exists():
            logger.info("Merging export project folder %s into existing folder %s", old_folder, new_folder)
            for child in old_folder.iterdir():
                target = new_folder / child.name
                if child.is_dir():
                    if target.exists():
                        _merge_directory_non_destructive(child, target)
                    else:
                        shutil.move(str(child), str(target))
                        logger.info("Moved export directory %s to %s", child, target)
                else:
                    if not target.exists():
                        target.parent.mkdir(parents=True, exist_ok=True)
                        os.replace(child, target)
                        logger.info("Moved export file %s to %s", child, target)
                    else:
                        logger.info("Skipped export file move because destination exists: %s", target)
            try:
                old_folder.rmdir()
                logger.info("Removed empty old export project folder: %s", old_folder)
            except OSError:
                logger.info("Kept old export project folder because it still has files: %s", old_folder)
                pass
        else:
            old_folder.rename(new_folder)
            logger.info("Renamed export project folder %s to %s", old_folder, new_folder)
    else:
        logger.info("No existing export project folder to rename: %s", old_folder)

    if not new_folder.is_dir():
        logger.info("New export project folder does not exist after title rename: %s", new_folder)
        return new_folder

    safe_old = sanitize_filename(old_title or "Untitled")
    safe_new = sanitize_filename(new_title or "Untitled")
    if safe_old == safe_new:
        logger.info("Sanitized export title did not change for %s", new_folder)
        return new_folder

    for child in sorted(new_folder.iterdir(), key=lambda path: path.name):
        if not child.is_file() or safe_old not in child.name:
            continue
        renamed = child.with_name(child.name.replace(safe_old, safe_new))
        if renamed == child:
            continue
        if not renamed.exists():
            os.replace(child, renamed)
            logger.info("Renamed export file %s to %s", child, renamed)
        else:
            logger.info("Skipped export file rename because destination exists: %s", renamed)
    return new_folder


def _merge_directory_non_destructive(src: Path, dest: Path) -> None:
    """Move files from src into dest without replacing existing destination paths."""
    dest.mkdir(parents=True, exist_ok=True)
    for child in src.iterdir():
        target = dest / child.name
        if child.is_dir():
            if target.exists():
                _merge_directory_non_destructive(child, target)
            else:
                shutil.move(str(child), str(target))
                logger.info("Moved export directory %s to %s", child, target)
        elif not target.exists():
            os.replace(child, target)
            logger.info("Moved export file %s to %s", child, target)
        else:
            logger.info("Skipped export file move because destination exists: %s", target)
    try:
        src.rmdir()
        logger.info("Removed empty merged export directory: %s", src)
    except OSError:
        logger.info("Kept merged export directory because it still has files: %s", src)
        pass


def export_filename(
    kind: ExportKind,
    asset: ExportAsset,
    name: str,
    extension: str,
) -> str:
    """Build a filename like '[Longform] [Video] - Project.mp4'."""
    clean_ext = extension if extension.startswith(".") else f".{extension}"
    safe_name = sanitize_filename(name or "Untitled")
    return f"[{kind}] [{asset}] - {safe_name}{clean_ext}"


def longform_filename(asset: ExportAsset, project_title: str, extension: str) -> str:
    return export_filename("Longform", asset, project_title, extension)


def shortform_filename(
    asset: ExportAsset,
    segment_name: str,
    extension: str,
    *,
    index: int,
    total: int,
) -> str:
    """Build a short-form thumbnail/SEO filename like '[Shortform 1∕8] [Thumbnail] - Segment.png'."""
    clean_ext = extension if extension.startswith(".") else f".{extension}"
    safe_name = sanitize_filename(segment_name or "Untitled")
    return f"[Shortform {index}{SHORTFORM_SLASH}{total}] [{asset}] - {safe_name}{clean_ext}"


def shortform_video_filename(segment_name: str, index: int, total: int) -> str:
    """Build the short-form video filename: '[Shortform N∕M] [Video] - {segment_name}.mp4'."""
    return shortform_filename("Video", segment_name, ".mp4", index=index, total=total)


def copy_to_project_downloads(
    project_title: str,
    src_path: str | Path,
    filename: str,
) -> str:
    """Copy a file into the configured project export folder.

    Large rendered videos are hard-linked when possible so the app can keep
    both the internal render path and the user-facing export path without
    storing duplicate MP4 bytes on the same drive. Cross-device exports fall
    back to a normal copy.
    """
    dest = project_downloads_folder(project_title) / filename
    src = Path(src_path)
    if _should_hardlink_export(src, dest):
        _hardlink_or_copy(src, dest)
    else:
        shutil.copy2(str(src), str(dest))
    return str(dest)


def _should_hardlink_export(src: Path, dest: Path) -> bool:
    """Return True for large rendered video exports that benefit from dedupe."""
    return src.suffix.lower() == ".mp4" and dest.suffix.lower() == ".mp4"


def _hardlink_or_copy(src: Path, dest: Path) -> None:
    """Hard-link src to dest when possible, falling back to shutil.copy2."""
    if dest.exists():
        try:
            if dest.samefile(src):
                return
        except OSError:
            pass
        dest.unlink()
    try:
        os.link(src, dest)
        shutil.copystat(src, dest, follow_symlinks=True)
        logger.info("Hard-linked export video %s to %s", src, dest)
    except OSError:
        shutil.copy2(str(src), str(dest))
        logger.info("Copied export video %s to %s", src, dest)


def has_asset_label(filename: str, asset: ExportAsset) -> bool:
    """Return True for current bracketed export filenames."""
    return f"[{asset.lower()}]" in filename.lower()


def has_export_label(filename: str, kind: ExportKind, asset: ExportAsset) -> bool:
    """Match export labels including the new [Shortform N∕M] form."""
    lower = filename.lower()
    kind_lower = kind.lower()
    kind_pattern = rf"\[{re.escape(kind_lower)}(?:\s+\d+[/{SHORTFORM_SLASH}]\d+)?\]"
    return re.search(kind_pattern, lower) is not None and f"[{asset.lower()}]" in lower
