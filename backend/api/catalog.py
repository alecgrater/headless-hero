"""Endpoints for browsing exported videos in the iCloud catalog."""

import logging
from datetime import datetime, timezone
from pathlib import Path

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from config import ICLOUD_VIDEOS_DIR

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/catalog", tags=["catalog"])


class CatalogEntry(BaseModel):
    folder_name: str
    folder_path: str = ""
    video_file: str | None = None
    thumbnail_file: str | None = None
    seo_title: str | None = None
    seo_description: str | None = None
    seo_tags: list[str] = []
    exported_at: str
    file_size_mb: float = 0.0
    uploaded: bool = False


class CatalogListResponse(BaseModel):
    entries: list[CatalogEntry]


class ToggleUploadedResponse(BaseModel):
    uploaded: bool


def _parse_seo_txt(path: Path) -> tuple[str | None, str | None, list[str]]:
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


@router.get("", response_model=CatalogListResponse)
def list_catalog():
    """Scan the iCloud videos directory and return all exported video entries."""
    if not ICLOUD_VIDEOS_DIR.exists():
        return CatalogListResponse(entries=[])

    entries: list[CatalogEntry] = []
    for item in ICLOUD_VIDEOS_DIR.iterdir():
        if not item.is_dir():
            continue

        folder_name = item.name
        video_file = None
        thumbnail_file = None
        file_size_mb = 0.0

        seo_path = None
        for f in item.iterdir():
            if f.name.startswith("."):
                continue
            lower = f.name.lower()
            if f.suffix.lower() == ".mp4":
                video_file = f.name
                file_size_mb = round(f.stat().st_size / (1024 * 1024), 1)
            elif lower == "thumbnail.png" or lower.endswith(" - thumbnail.png"):
                thumbnail_file = f.name
            elif lower == "seo.txt" or lower.endswith(" - seo.txt"):
                seo_path = f

        seo_title, seo_description, seo_tags = None, None, []
        if seo_path:
            seo_title, seo_description, seo_tags = _parse_seo_txt(seo_path)

        mtime = item.stat().st_mtime
        exported_at = datetime.fromtimestamp(mtime, tz=timezone.utc).isoformat()

        uploaded = (item / ".uploaded").exists()

        entries.append(CatalogEntry(
            folder_name=folder_name,
            folder_path=str(item),
            video_file=video_file,
            thumbnail_file=thumbnail_file,
            seo_title=seo_title,
            seo_description=seo_description,
            seo_tags=seo_tags,
            exported_at=exported_at,
            file_size_mb=file_size_mb,
            uploaded=uploaded,
        ))

    entries.sort(key=lambda e: e.exported_at, reverse=True)
    return CatalogListResponse(entries=entries)


@router.post("/{folder_name}/toggle-uploaded", response_model=ToggleUploadedResponse)
def toggle_uploaded(folder_name: str):
    """Toggle the .uploaded marker file in a catalog folder."""
    folder = (ICLOUD_VIDEOS_DIR / folder_name).resolve()
    if not folder.is_relative_to(ICLOUD_VIDEOS_DIR.resolve()):
        raise HTTPException(status_code=400, detail="Invalid folder name")
    if not folder.exists() or not folder.is_dir():
        raise HTTPException(status_code=404, detail="Folder not found")

    marker = folder / ".uploaded"
    if marker.exists():
        marker.unlink()
        return ToggleUploadedResponse(uploaded=False)
    else:
        marker.touch()
        return ToggleUploadedResponse(uploaded=True)
