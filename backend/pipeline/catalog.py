"""Catalog business logic — file markers, DB bridging, backfill."""

import logging
from datetime import datetime
from pathlib import Path

from config import get_export_folder, sanitize_filename

logger = logging.getLogger(__name__)


def parse_seo_txt(path: Path) -> tuple[str | None, str | None, list[str]]:
    """Parse a seo.txt file into (title, description, tags)."""
    try:
        text = path.read_text(encoding="utf-8")
    except Exception:
        return None, None, []

    title = None
    description = None
    tags: list[str] = []
    current_section = None

    for line in text.split("\n"):
        stripped = line.strip()
        if stripped == "Title:":
            current_section = "title"
            continue
        elif stripped == "Description:":
            current_section = "description"
            continue
        elif stripped == "Tags:":
            current_section = "tags"
            continue

        if current_section == "title" and stripped:
            title = stripped
        elif current_section == "description" and stripped:
            if description is None:
                description = stripped
            else:
                description += "\n" + stripped
        elif current_section == "tags" and stripped:
            tags = [t.strip() for t in stripped.split(",") if t.strip()]

    return title, description, tags


def read_script_id(folder: Path) -> str | None:
    marker = folder / ".script_id"
    if marker.exists():
        val = marker.read_text(encoding="utf-8").strip()
        return val or None
    return None


def write_script_id(folder: Path, script_id: str) -> None:
    (folder / ".script_id").write_text(script_id, encoding="utf-8")


def read_youtube_url(folder: Path) -> str | None:
    marker = folder / ".youtube_url"
    if marker.exists():
        val = marker.read_text(encoding="utf-8").strip()
        return val or None
    return None


def write_youtube_url(folder: Path, url: str) -> None:
    (folder / ".youtube_url").write_text(url, encoding="utf-8")


def toggle_uploaded_marker(folder: Path) -> bool:
    """Toggle .uploaded marker file, return new state."""
    marker = folder / ".uploaded"
    if marker.exists():
        marker.unlink()
        return False
    else:
        marker.touch()
        return True


def resolve_export_folder(topic_title: str, created_at: datetime) -> str:
    """Compute the export folder name for a script."""
    safe_title = sanitize_filename(topic_title or "Untitled")
    date_str = created_at.strftime("%Y-%m-%d")
    return f"{safe_title} ({date_str})"


def find_export_folder(topic_title: str, created_at: datetime) -> Path | None:
    """Check if the export folder exists on disk, trying current and legacy patterns."""
    export_dir = get_export_folder()
    if not export_dir.exists():
        return None

    safe_title = sanitize_filename(topic_title or "Untitled")
    date_str = created_at.strftime("%Y-%m-%d")

    candidates = [
        f"{safe_title} ({date_str})",
        f"{safe_title} - {date_str}",
    ]
    for name in candidates:
        path = export_dir / name
        if path.is_dir():
            return path
    return None


def backfill_script_id_markers(session) -> int:
    """Write .script_id markers for existing export folders that match known scripts."""
    from models.script import Script

    export_dir = get_export_folder()
    if not export_dir.exists():
        return 0

    existing_folders = {item.name: item for item in export_dir.iterdir() if item.is_dir()}
    if not existing_folders:
        return 0

    from sqlmodel import select
    scripts = session.exec(select(Script)).all()

    count = 0
    for script in scripts:
        folder = find_export_folder(script.topic_title, script.created_at)
        if not folder:
            continue
        if read_script_id(folder) is not None:
            continue
        write_script_id(folder, script.id)
        logger.info("Backfilled .script_id for %s → %s", folder.name, script.id)
        count += 1

    return count
