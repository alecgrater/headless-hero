"""Endpoints for browsing exported videos and uploading to YouTube."""

import logging
from datetime import datetime, timezone
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlmodel import Session, select

from config import get_export_folder
from database import get_default_brand_id, get_session
from models.credential import PlatformCredential
from pipeline.publishing import publish_to_youtube
from pipeline.render_jobs import create_job, run_in_background, update_job

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
    youtube_url: str | None = None


class CatalogListResponse(BaseModel):
    entries: list[CatalogEntry]


class ToggleUploadedResponse(BaseModel):
    uploaded: bool


class CatalogUploadRequest(BaseModel):
    folder_name: str
    title: str | None = None
    description: str | None = None
    tags: list[str] | None = None
    privacy_status: str = "unlisted"


class CatalogUploadResponse(BaseModel):
    job_id: str


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
    """Scan the export directory and return all exported video entries."""
    export_dir = get_export_folder()
    if not export_dir.exists():
        return CatalogListResponse(entries=[])

    entries: list[CatalogEntry] = []
    for item in export_dir.iterdir():
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
        youtube_url_marker = item / ".youtube_url"
        youtube_url: str | None = None
        if youtube_url_marker.exists():
            youtube_url = youtube_url_marker.read_text(encoding="utf-8").strip() or None
            uploaded = True

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
            youtube_url=youtube_url,
        ))

    entries.sort(key=lambda e: e.exported_at, reverse=True)
    return CatalogListResponse(entries=entries)


@router.post("/{folder_name}/toggle-uploaded", response_model=ToggleUploadedResponse)
def toggle_uploaded(folder_name: str):
    """Toggle the .uploaded marker file in a catalog folder."""
    export_dir = get_export_folder()
    folder = (export_dir / folder_name).resolve()
    if not folder.is_relative_to(export_dir.resolve()):
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


@router.post("/upload", response_model=CatalogUploadResponse)
def catalog_upload(body: CatalogUploadRequest, session: Session = Depends(get_session)):
    """Upload a catalog video to YouTube in the background."""
    export_dir = get_export_folder()
    folder = (export_dir / body.folder_name).resolve()
    if not folder.is_relative_to(export_dir.resolve()):
        raise HTTPException(status_code=400, detail="Invalid folder name")
    if not folder.exists() or not folder.is_dir():
        raise HTTPException(status_code=404, detail="Folder not found")

    video_path: str | None = None
    thumbnail_path: str | None = None
    seo_path: Path | None = None
    for f in folder.iterdir():
        if f.name.startswith("."):
            continue
        lower = f.name.lower()
        if f.suffix.lower() == ".mp4" and video_path is None:
            video_path = str(f)
        elif lower == "thumbnail.png" or lower.endswith(" - thumbnail.png"):
            thumbnail_path = str(f)
        elif lower == "seo.txt" or lower.endswith(" - seo.txt"):
            seo_path = f

    if not video_path:
        raise HTTPException(status_code=400, detail="No .mp4 video file found in folder")

    title = body.title
    description = body.description
    tags = body.tags
    if not title or description is None or tags is None:
        seo_title, seo_desc, seo_tags = (None, None, [])
        if seo_path:
            seo_title, seo_desc, seo_tags = _parse_seo_txt(seo_path)
        if not title:
            title = seo_title or body.folder_name
        if description is None:
            description = seo_desc or ""
        if tags is None:
            tags = seo_tags

    brand_id = get_default_brand_id(session)
    stmt = select(PlatformCredential).where(
        PlatformCredential.brand_id == brand_id,
        PlatformCredential.platform == "youtube",
    )
    cred = session.exec(stmt).first()
    if not cred:
        raise HTTPException(status_code=400, detail="YouTube not connected")

    cred_brand = cred.brand_id
    cred_refresh = cred.refresh_token
    cred_access = cred.access_token
    cred_expiry = cred.token_expiry

    job = create_job()
    folder_path_str = str(folder)
    privacy = body.privacy_status

    logger.info("Starting catalog upload for folder %s", body.folder_name)

    def do_upload():
        temp_cred = PlatformCredential(
            brand_id=cred_brand,
            platform="youtube",
            access_token=cred_access,
            refresh_token=cred_refresh,
            token_expiry=cred_expiry,
        )

        def on_progress(p: float, msg: str):
            update_job(job.id, progress=p, current_step=msg)

        result = publish_to_youtube(
            credential=temp_cred,
            file_path=video_path,
            metadata={"title": title, "description": description, "tags": tags},
            on_progress=on_progress,
            thumbnail_path=thumbnail_path or "",
            privacy_status=privacy,
        )

        youtube_url_marker = Path(folder_path_str) / ".youtube_url"
        youtube_url_marker.write_text(result["url"], encoding="utf-8")

        # Persist refreshed token if it changed
        if temp_cred.access_token != cred_access:
            from database import engine as db_engine
            from sqlmodel import Session as SyncSession
            with SyncSession(db_engine) as s:
                stmt = select(PlatformCredential).where(
                    PlatformCredential.brand_id == cred_brand,
                    PlatformCredential.platform == "youtube",
                )
                db_cred = s.exec(stmt).first()
                if db_cred:
                    db_cred.access_token = temp_cred.access_token
                    db_cred.token_expiry = temp_cred.token_expiry
                    db_cred.updated_at = datetime.now(timezone.utc)
                    s.add(db_cred)
                    s.commit()

        return result["url"]

    run_in_background(job.id, do_upload)
    return CatalogUploadResponse(job_id=job.id)
