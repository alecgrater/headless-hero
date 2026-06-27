"""Read-only upload suite helpers for manual publishing workflows."""

import json
import logging
import shutil
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import FileResponse
from pydantic import BaseModel
from sqlmodel import Session

from api.render import _find_rendered_longform
from api.short_form_hooks import ensure_short_form_hook_scene_count
from config import DATA_DIR
from database import get_session
from models.script import Script, ScriptContent
from pipeline.script_helpers import _format_longform_seo_markdown, _format_shortform_seo_markdown
from pipeline.export_paths import (
    downloads_base,
    has_export_label,
    longform_filename,
    project_downloads_folder,
    shortform_filename,
    shortform_video_filename,
)
from pipeline.short_form_thumbnails import is_short_thumbnail_current, short_thumbnail_filename

logger = logging.getLogger(__name__)

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
    internal_folder_path: str
    missing: list[str]
    longform_video_path: str | None = None
    longform_thumbnail_url: str | None = None
    longform_seo_markdown: str
    shorts: list[ShortUploadSuiteItem]


class DeleteExportsFolderResponse(BaseModel):
    deleted: bool
    folder_path: str


class ExportFileCategoryStatus(BaseModel):
    label: str
    exported: int
    total: int


class ExportFileStatusResponse(BaseModel):
    project_title: str
    folder_path: str
    exported: int
    total: int
    categories: dict[str, ExportFileCategoryStatus]


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


def _short_thumbnail_path(
    script_id: str,
    folder: Path,
    segment_name: str,
    index: int,
    content: ScriptContent,
) -> Path | None:
    total = len(content.segments)
    exported = folder / short_thumbnail_filename(segment_name, index + 1, total)
    cached = DATA_DIR / "projects" / script_id / "renders" / "short_thumbnails" / f"{index}.png"
    cached_is_current = cached.is_file() and is_short_thumbnail_current(script_id, index, content)
    if cached_is_current:
        if exported.is_file():
            try:
                if exported.stat().st_mtime >= cached.stat().st_mtime:
                    return exported
            except OSError:
                pass
        return cached
    if exported.is_file() and is_short_thumbnail_current(script_id, index, content):
        return exported
    return None


def _exported_longform_path(
    script_id: str,
    project_title: str,
    folder: Path,
    content: ScriptContent,
) -> str | None:
    path, _url = _find_rendered_longform(script_id, project_title, content)
    if path:
        return path
    return None


def _longform_thumbnail_path(script_id: str) -> Path | None:
    rendered = DATA_DIR / "projects" / script_id / "renders" / "thumbnails" / "0.png"
    if rendered.is_file():
        return rendered
    composite = DATA_DIR / "projects" / script_id / "images" / "composite_title_card.png"
    if composite.is_file():
        return composite
    return None


def _count_labeled_files(folder: Path, kind: str, asset: str, extension: str, total: int) -> int:
    if total <= 0 or not folder.is_dir():
        return 0
    count = sum(
        1
        for file in folder.iterdir()
        if file.is_file()
        and file.suffix.lower() == extension
        and has_export_label(file.name, kind, asset)
    )
    return min(count, total)


def _count_expected_files(folder: Path, expected_files: list[str], kind: str, asset: str, extension: str) -> int:
    if not folder.is_dir():
        return 0
    exact_count = sum(1 for filename in expected_files if (folder / filename).is_file())
    labeled_count = _count_labeled_files(folder, kind, asset, extension, len(expected_files))
    return max(exact_count, labeled_count)


@router.get("/export-status", response_model=ExportFileStatusResponse)
def export_file_status(script_id: str, session: Session = Depends(get_session)):
    """Count exported project files by category in the configured export folder."""
    record, content = _load_script(session, script_id)
    project_title = record.topic_title or content.title or "Untitled"
    folder = project_downloads_folder(project_title, create=False)
    total_segments = len(content.segments)

    expected_short_videos = [
        shortform_video_filename(segment.name, idx + 1, total_segments)
        for idx, segment in enumerate(content.segments)
    ]
    expected_short_thumbnails = [
        shortform_filename("Thumbnail", segment.name, ".png", index=idx + 1, total=total_segments)
        for idx, segment in enumerate(content.segments)
    ]
    expected_short_seo = [
        shortform_filename("SEO", segment.name, ".md", index=idx + 1, total=total_segments)
        for idx, segment in enumerate(content.segments)
    ]

    categories = {
        "longform_video": ExportFileCategoryStatus(
            label="Long form video",
            exported=_count_expected_files(
                folder,
                [longform_filename("Video", project_title, ".mp4")],
                "Longform",
                "Video",
                ".mp4",
            ),
            total=1,
        ),
        "longform_thumbnail": ExportFileCategoryStatus(
            label="Long form thumbnail",
            exported=_count_expected_files(
                folder,
                [longform_filename("Thumbnail", project_title, ".png")],
                "Longform",
                "Thumbnail",
                ".png",
            ),
            total=1,
        ),
        "longform_seo": ExportFileCategoryStatus(
            label="Long form SEO",
            exported=_count_expected_files(
                folder,
                [longform_filename("SEO", project_title, ".md")],
                "Longform",
                "SEO",
                ".md",
            ),
            total=1,
        ),
        "shortform_videos": ExportFileCategoryStatus(
            label="Short form videos",
            exported=_count_expected_files(folder, expected_short_videos, "Shortform", "Video", ".mp4"),
            total=total_segments,
        ),
        "shortform_thumbnails": ExportFileCategoryStatus(
            label="Short form thumbnails",
            exported=_count_expected_files(folder, expected_short_thumbnails, "Shortform", "Thumbnail", ".png"),
            total=total_segments,
        ),
        "shortform_seo": ExportFileCategoryStatus(
            label="Short form SEO",
            exported=_count_expected_files(folder, expected_short_seo, "Shortform", "SEO", ".md"),
            total=total_segments,
        ),
    }
    exported = sum(category.exported for category in categories.values())
    total = sum(category.total for category in categories.values())
    return ExportFileStatusResponse(
        project_title=project_title,
        folder_path=str(folder),
        exported=exported,
        total=total,
        categories=categories,
    )


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

    longform_video_path = _exported_longform_path(script_id, project_title, folder, content)
    if not longform_video_path:
        missing.append("Long-form video")
    longform_thumbnail_url = (
        f"/api/upload-suite/longform-thumbnail?script_id={script_id}"
        if _longform_thumbnail_path(script_id)
        else None
    )

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

        thumb = _short_thumbnail_path(script_id, folder, segment.name, idx, content)
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
        internal_folder_path=str(DATA_DIR / "projects" / script_id),
        missing=missing,
        longform_video_path=longform_video_path,
        longform_thumbnail_url=longform_thumbnail_url,
        longform_seo_markdown=longform_seo_markdown,
        shorts=shorts,
    )


@router.delete("/exports-folder", response_model=DeleteExportsFolderResponse)
def delete_exports_folder(script_id: str, session: Session = Depends(get_session)):
    """Delete the project's exported folder once uploads are complete.

    The internal ``data/projects/{script_id}`` copy is never touched — this only
    removes the user-facing export folder under the configured Exports root.
    """
    record, content = _load_script(session, script_id)
    project_title = record.topic_title or content.title or "Untitled"
    folder = project_downloads_folder(project_title, create=False)

    # Safety: only ever delete a folder that lives directly under the Exports root.
    base = downloads_base().resolve()
    try:
        resolved = folder.resolve()
    except OSError:
        resolved = folder
    if resolved.parent != base:
        logger.error("Refusing to delete exports folder outside Exports root: %s", resolved)
        raise HTTPException(status_code=400, detail="Export folder is outside the configured Exports root")

    if not folder.is_dir():
        logger.info("Exports folder already absent for '%s': %s", project_title, folder)
        return DeleteExportsFolderResponse(deleted=False, folder_path=str(folder))

    try:
        shutil.rmtree(folder)
    except OSError as exc:
        logger.error("Failed to delete exports folder %s: %s", folder, exc)
        raise HTTPException(status_code=500, detail=f"Could not delete export folder: {exc}") from exc

    logger.info("Deleted exports folder for '%s' (internal copy retained): %s", project_title, folder)
    return DeleteExportsFolderResponse(deleted=True, folder_path=str(folder))


@router.get("/longform-thumbnail")
def upload_suite_longform_thumbnail(script_id: str, session: Session = Depends(get_session)):
    """Serve the long-form thumbnail used by the manual upload panel."""
    _record, _content = _load_script(session, script_id)
    thumb = _longform_thumbnail_path(script_id)
    if not thumb:
        raise HTTPException(status_code=404, detail="Thumbnail not found")
    return FileResponse(str(thumb))


@router.get("/thumbnail")
def upload_suite_thumbnail(script_id: str, index: int, session: Session = Depends(get_session)):
    """Serve the thumbnail used by the manual upload card carousel."""
    record, content = _load_script(session, script_id)
    if index < 0 or index >= len(content.segments):
        raise HTTPException(status_code=404, detail="Thumbnail not found")
    project_title = record.topic_title or content.title or "Untitled"
    folder = project_downloads_folder(project_title, create=False)
    thumb = _short_thumbnail_path(script_id, folder, content.segments[index].name, index, content)
    if not thumb:
        raise HTTPException(status_code=404, detail="Thumbnail not found")
    return FileResponse(str(thumb))
