"""Shared filesystem naming rules for user-facing exports."""

from __future__ import annotations

import os
import re
import shutil
from pathlib import Path
from typing import Literal

from config import sanitize_filename

ExportKind = Literal["Longform", "Shortform"]
ExportAsset = Literal["Thumbnail", "SEO", "Video", "Audio"]

# U+2215 division slash — visually like "/" but filesystem-safe (POSIX reserves U+002F).
SHORTFORM_SLASH = "∕"


def downloads_base() -> Path:
    """Return the configured Downloads directory for direct asset exports."""
    configured = os.environ.get("DOWNLOADS_DIR", "").strip()
    legacy_export_root = os.environ.get("EXPORT_FOLDER", "").strip()
    return Path(configured or legacy_export_root or str(Path.home() / "Downloads")).expanduser()


def project_folder_name(project_title: str) -> str:
    """Return the standard Downloads folder name for a project."""
    return sanitize_filename(project_title or "Untitled")


def project_downloads_folder(project_title: str, *, create: bool = True) -> Path:
    """Return the configured export project folder, creating it by default."""
    folder = downloads_base() / project_folder_name(project_title)
    if create:
        folder.mkdir(parents=True, exist_ok=True)
    return folder


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
    """Copy a file into the configured project export folder."""
    dest = project_downloads_folder(project_title) / filename
    shutil.copy2(str(src_path), str(dest))
    return str(dest)


def has_asset_label(filename: str, asset: ExportAsset) -> bool:
    """Return True for current bracketed export filenames."""
    return f"[{asset.lower()}]" in filename.lower()


def has_export_label(filename: str, kind: ExportKind, asset: ExportAsset) -> bool:
    """Match export labels including the new [Shortform N∕M] form."""
    lower = filename.lower()
    kind_lower = kind.lower()
    kind_pattern = rf"\[{re.escape(kind_lower)}(?:\s+\d+[/{SHORTFORM_SLASH}]\d+)?\]"
    return re.search(kind_pattern, lower) is not None and f"[{asset.lower()}]" in lower
