"""Read-only upload suite helpers for manual publishing workflows."""

import json
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import FileResponse
from pydantic import BaseModel
from sqlmodel import Session

from api.render import _format_longform_seo_markdown, _format_shortform_seo_markdown
from api.short_form_hooks import ensure_short_form_hook_scene_count
from config import DATA_DIR
from database import get_session
from models.script import Script, ScriptContent
from pipeline.export_paths import (
    longform_filename,
    project_downloads_folder,
    shortform_filename,
    shortform_video_filename,
)
from pipeline.short_form_thumbnails import short_thumbnail_filename

router = APIRouter(prefix="/api/upload-suite", tags=["upload-suite"])


class ShortUploadSuiteItem(BaseModel):
    index: int
    segment_name: str
    video_path: str | None = None
    seo_markdown: str
    thumbnail_url: str | None = None


class UploadSuiteStatusResponse(BaseModel):
    ready: bool
    project_title: str
    folder_path: str
    missing: list[str]
    longform_video_path: str | None = None
    longform_seo_markdown: str
    shorts: list[ShortUploadSuiteItem]


def _load_script(session: Session, script_id: str) -> tuple[Script, ScriptContent]:
    record = session.get(Script, script_id)
    if not record:
        raise HTTPException(status_code=404, detail="Script not found")
    content = ScriptContent.model_validate(json.loads(record.script_json))
    content = ensure_short_form_hook_scene_count(session, script_id, content, record)
    return record, content


def _read_text(path: Path) -> str:
    if not path.is_file():
        return ""
    return path.read_text(encoding="utf-8")


def _short_item_index(item: dict, fallback_index: int, uses_one_based_indices: bool) -> int:
    try:
        raw = int(item.get("index", -1))
    except (TypeError, ValueError):
        raw = -1
    if uses_one_based_indices and raw >= 1:
        return raw - 1
    if raw >= 0:
        return raw
    return fallback_index


def _short_seo_by_index(content: ScriptContent) -> dict[int, dict]:
    items = (content.short_form_seo_metadata or {}).get("shorts", [])
    parsed: list[int] = []
    for item in items:
        try:
            parsed.append(int(item.get("index", -1)))
        except (TypeError, ValueError):
            parsed.append(-1)
    uses_one_based_indices = 1 in parsed
    by_index: dict[int, dict] = {}
    for fallback_index, item in enumerate(items):
        by_index[_short_item_index(item, fallback_index, uses_one_based_indices)] = item
    return by_index


def _short_thumbnail_path(script_id: str, folder: Path, segment_name: str, index: int, total: int) -> Path | None:
    exported = folder / short_thumbnail_filename(segment_name, index + 1, total)
    if exported.is_file():
        return exported
    cached = DATA_DIR / "projects" / script_id / "renders" / "short_thumbnails" / f"{index}.png"
    if cached.is_file():
        return cached
    return None


@router.get("/status", response_model=UploadSuiteStatusResponse)
def upload_suite_status(script_id: str, session: Session = Depends(get_session)):
    """Return the manual upload suite if exported videos are ready."""
    record, content = _load_script(session, script_id)
    project_title = record.topic_title or content.title or "Untitled"
    folder = project_downloads_folder(project_title, create=False)
    total = len(content.segments)
    missing: list[str] = []

    if not folder.is_dir():
        missing.append(f"Project folder: {folder}")

    longform_video = folder / longform_filename("Video", project_title, ".mp4")
    longform_video_path = str(longform_video) if longform_video.is_file() else None
    if not longform_video_path:
        missing.append("Long-form video")

    longform_seo_path = folder / longform_filename("SEO", project_title, ".md")
    longform_seo_markdown = _read_text(longform_seo_path)
    if not longform_seo_markdown and content.seo_metadata:
        longform_seo_markdown = _format_longform_seo_markdown(content.seo_metadata)

    short_seo_by_index = _short_seo_by_index(content)
    shorts: list[ShortUploadSuiteItem] = []
    for idx, segment in enumerate(content.segments):
        n = idx + 1
        video = folder / shortform_video_filename(segment.name, n, total)
        video_path = str(video) if video.is_file() else None
        if not video_path:
            missing.append(f"Short-form video {n}")

        seo_path = folder / shortform_filename("SEO", segment.name, ".md", index=n, total=total)
        seo_markdown = _read_text(seo_path)
        if not seo_markdown:
            item = short_seo_by_index.get(idx)
            if item:
                seo_markdown = _format_shortform_seo_markdown(item)

        thumb = _short_thumbnail_path(script_id, folder, segment.name, idx, total)
        thumbnail_url = f"/api/upload-suite/thumbnail?script_id={script_id}&index={idx}" if thumb else None
        shorts.append(
            ShortUploadSuiteItem(
                index=idx,
                segment_name=segment.name,
                video_path=video_path,
                seo_markdown=seo_markdown,
                thumbnail_url=thumbnail_url,
            )
        )

    return UploadSuiteStatusResponse(
        ready=len(missing) == 0,
        project_title=project_title,
        folder_path=str(folder),
        missing=missing,
        longform_video_path=longform_video_path,
        longform_seo_markdown=longform_seo_markdown,
        shorts=shorts,
    )


@router.get("/thumbnail")
def upload_suite_thumbnail(script_id: str, index: int, session: Session = Depends(get_session)):
    """Serve the thumbnail used by the manual upload card carousel."""
    record, content = _load_script(session, script_id)
    if index < 0 or index >= len(content.segments):
        raise HTTPException(status_code=404, detail="Thumbnail not found")
    project_title = record.topic_title or content.title or "Untitled"
    folder = project_downloads_folder(project_title, create=False)
    thumb = _short_thumbnail_path(script_id, folder, content.segments[index].name, index, len(content.segments))
    if not thumb:
        raise HTTPException(status_code=404, detail="Thumbnail not found")
    return FileResponse(str(thumb))
