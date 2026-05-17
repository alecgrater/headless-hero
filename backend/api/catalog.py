"""Endpoints for browsing exported videos and uploading to YouTube."""

import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlmodel import Session, select

from config import get_export_folder
from database import get_default_brand_id, get_session
from models.credential import PlatformCredential
from models.publish import PublishRecord
from pipeline.catalog import (
    parse_seo_txt,
    read_script_id,
    read_youtube_url,
    toggle_uploaded_marker,
    write_youtube_url,
)
from pipeline.export_paths import downloads_base, has_asset_label, has_export_label
from pipeline.publishing import is_reauth_required_error, publish_to_youtube
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
    script_id: str | None = None


class CatalogListResponse(BaseModel):
    entries: list[CatalogEntry]


class ToggleUploadedResponse(BaseModel):
    uploaded: bool


class CatalogUploadRequest(BaseModel):
    folder_name: str
    title: str | None = None
    description: str | None = None
    tags: list[str] | None = None
    privacy_status: Literal["private", "unlisted", "public"] = "unlisted"


class CatalogUploadResponse(BaseModel):
    job_id: str


@router.get("", response_model=CatalogListResponse)
def list_catalog(session: Session = Depends(get_session)):
    """Scan the export directory and return all exported video entries."""
    export_dir = get_export_folder()
    if not export_dir.exists():
        return CatalogListResponse(entries=[])

    # First pass: scan folders and collect script_ids
    folder_data: list[tuple[Path, str | None]] = []
    script_ids: set[str] = set()
    for item in export_dir.iterdir():
        if not item.is_dir():
            continue
        sid = read_script_id(item)
        folder_data.append((item, sid))
        if sid:
            script_ids.add(sid)

    # Batch query DB for publish records matching these script_ids
    db_records: dict[str, PublishRecord] = {}
    if script_ids:
        stmt = select(PublishRecord).where(
            PublishRecord.script_id.in_(list(script_ids)),
            PublishRecord.platform == "youtube",
            PublishRecord.status.in_(["published", "scheduled", "unpublished"]),
        )
        for rec in session.exec(stmt).all():
            if rec.script_id not in db_records:
                db_records[rec.script_id] = rec

    entries: list[CatalogEntry] = []
    for item, script_id in folder_data:
        folder_name = item.name
        video_file = None
        thumbnail_file = None
        file_size_mb = 0.0

        seo_path = None
        for f in item.iterdir():
            if f.name.startswith("."):
                continue
            lower = f.name.lower()
            if f.suffix.lower() == ".mp4" and (
                video_file is None or has_export_label(f.name, "Longform", "Video")
            ):
                video_file = f.name
                file_size_mb = round(f.stat().st_size / (1024 * 1024), 1)
            elif (
                lower == "thumbnail.png"
                or lower.endswith(" - thumbnail.png")
                or (
                    has_asset_label(f.name, "Thumbnail")
                    and (thumbnail_file is None or has_export_label(f.name, "Longform", "Thumbnail"))
                )
            ):
                thumbnail_file = f.name
            elif (
                lower in ("seo.txt", "seo.md")
                or lower.endswith(" - seo.txt")
                or lower.endswith(" - seo.md")
                or (
                    has_asset_label(f.name, "SEO")
                    and (seo_path is None or has_export_label(f.name, "Longform", "SEO"))
                )
            ):
                seo_path = f

        seo_title, seo_description, seo_tags = None, None, []
        if seo_path:
            seo_title, seo_description, seo_tags = parse_seo_txt(seo_path)

        mtime = item.stat().st_mtime
        exported_at = datetime.fromtimestamp(mtime, tz=timezone.utc).isoformat()

        # Prefer DB record over file markers
        youtube_url: str | None = None
        uploaded = False
        db_rec = db_records.get(script_id) if script_id else None
        if db_rec and db_rec.platform_url:
            youtube_url = db_rec.platform_url
            uploaded = db_rec.status in ("published", "scheduled")
        else:
            youtube_url = read_youtube_url(item)
            uploaded = (item / ".uploaded").exists()
            if youtube_url:
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
            script_id=script_id,
        ))

    entries.sort(key=lambda e: e.exported_at, reverse=True)
    return CatalogListResponse(entries=entries)


class SyncYouTubeResponse(BaseModel):
    matched: int


@router.post("/sync-youtube", response_model=SyncYouTubeResponse)
def sync_youtube(session: Session = Depends(get_session)):
    """Cross-reference catalog entries with YouTube uploads by title."""
    brand_id = get_default_brand_id(session)
    stmt = select(PlatformCredential).where(
        PlatformCredential.brand_id == brand_id,
        PlatformCredential.platform == "youtube",
    )
    cred = session.exec(stmt).first()
    if not cred:
        return SyncYouTubeResponse(matched=0)

    from pipeline.publishing import ensure_token_fresh
    try:
        was_refreshed = ensure_token_fresh(cred)
    except RuntimeError as exc:
        raise HTTPException(status_code=401, detail=str(exc)) from exc

    from integrations.youtube_client import list_channel_uploads
    try:
        uploads = list_channel_uploads(cred.access_token)
    except Exception:
        logger.warning("Failed to fetch YouTube uploads for sync", exc_info=True)
        return SyncYouTubeResponse(matched=0)

    if was_refreshed:
        session.add(cred)
        session.commit()

    title_to_url: dict[str, str] = {}
    title_to_vid: dict[str, dict] = {}
    for vid in uploads:
        key = vid["title"].strip().lower()
        title_to_url[key] = vid["url"]
        title_to_vid[key] = vid

    export_dir = get_export_folder()
    if not export_dir.exists():
        return SyncYouTubeResponse(matched=0)

    matched = 0
    for item in export_dir.iterdir():
        if not item.is_dir():
            continue
        if read_youtube_url(item):
            continue

        seo_path = None
        for f in item.iterdir():
            lower = f.name.lower()
            if (
                lower in ("seo.txt", "seo.md")
                or lower.endswith(" - seo.txt")
                or lower.endswith(" - seo.md")
                or has_export_label(f.name, "Longform", "SEO")
            ):
                seo_path = f
                break

        seo_title = None
        if seo_path:
            seo_title, _, _ = parse_seo_txt(seo_path)

        candidates = []
        if seo_title:
            candidates.append(seo_title.strip().lower())
        candidates.append(item.name.strip().lower())

        for candidate in candidates:
            if candidate in title_to_url:
                url = title_to_url[candidate]
                write_youtube_url(item, url)

                script_id = read_script_id(item)
                if script_id:
                    existing = session.exec(
                        select(PublishRecord).where(
                            PublishRecord.script_id == script_id,
                            PublishRecord.platform == "youtube",
                            PublishRecord.status.in_(["published", "scheduled"]),
                        )
                    ).first()
                    if not existing:
                        vid = title_to_vid[candidate]
                        record = PublishRecord(
                            script_id=script_id,
                            brand_id=brand_id,
                            platform="youtube",
                            status="published",
                            platform_content_id=vid.get("id", ""),
                            platform_url=url,
                            export_folder=item.name,
                            published_at=datetime.now(timezone.utc),
                        )
                        session.add(record)

                matched += 1
                break

    session.commit()
    return SyncYouTubeResponse(matched=matched)


@router.post("/{folder_name}/toggle-uploaded", response_model=ToggleUploadedResponse)
def toggle_uploaded(folder_name: str, session: Session = Depends(get_session)):
    """Toggle the uploaded state — DB record if available, else file marker."""
    export_dir = get_export_folder()
    folder = (export_dir / folder_name).resolve()
    if not folder.is_relative_to(export_dir.resolve()):
        raise HTTPException(status_code=400, detail="Invalid folder name")
    if not folder.exists() or not folder.is_dir():
        raise HTTPException(status_code=404, detail="Folder not found")

    script_id = read_script_id(folder)
    if script_id:
        stmt = select(PublishRecord).where(
            PublishRecord.script_id == script_id,
            PublishRecord.platform == "youtube",
        )
        rec = session.exec(stmt).first()
        if rec:
            marker = folder / ".uploaded"
            if rec.status in ("published", "scheduled"):
                rec.status = "unpublished"
                rec.updated_at = datetime.now(timezone.utc)
                session.add(rec)
                session.commit()
                if marker.exists():
                    marker.unlink()
                return ToggleUploadedResponse(uploaded=False)
            else:
                rec.status = "published"
                rec.updated_at = datetime.now(timezone.utc)
                session.add(rec)
                session.commit()
                if not marker.exists():
                    marker.touch()
                return ToggleUploadedResponse(uploaded=True)

    new_state = toggle_uploaded_marker(folder)
    return ToggleUploadedResponse(uploaded=new_state)


@router.post("/upload", response_model=CatalogUploadResponse)
def catalog_upload(body: CatalogUploadRequest, session: Session = Depends(get_session)):
    """Upload a catalog video to YouTube in the background."""
    export_dir = get_export_folder()
    folder = (export_dir / body.folder_name).resolve()
    export_root = export_dir.resolve()
    downloads_root = downloads_base().resolve()
    if not folder.is_relative_to(export_root):
        raise HTTPException(status_code=400, detail="Invalid folder name")
    if not folder.exists() or not folder.is_dir():
        downloads_folder = (downloads_root / body.folder_name).resolve()
        if downloads_folder.is_relative_to(downloads_root):
            folder = downloads_folder
    if not folder.exists() or not folder.is_dir():
        raise HTTPException(status_code=404, detail="Folder not found")

    video_path: str | None = None
    thumbnail_path: str | None = None
    seo_path: Path | None = None
    for f in folder.iterdir():
        if f.name.startswith("."):
            continue
        lower = f.name.lower()
        if f.suffix.lower() == ".mp4" and (
            video_path is None or has_export_label(f.name, "Longform", "Video")
        ):
            video_path = str(f)
        elif (
            lower == "thumbnail.png"
            or lower.endswith(" - thumbnail.png")
            or (
                has_asset_label(f.name, "Thumbnail")
                and (thumbnail_path is None or has_export_label(f.name, "Longform", "Thumbnail"))
            )
        ):
            thumbnail_path = str(f)
        elif (
            lower in ("seo.txt", "seo.md")
            or lower.endswith(" - seo.txt")
            or lower.endswith(" - seo.md")
            or (
                has_asset_label(f.name, "SEO")
                and (seo_path is None or has_export_label(f.name, "Longform", "SEO"))
            )
        ):
            seo_path = f

    if not video_path:
        raise HTTPException(status_code=400, detail="No .mp4 video file found in folder")

    title = body.title
    description = body.description
    tags = body.tags
    if not title or description is None or tags is None:
        seo_title, seo_desc, seo_tags = (None, None, [])
        if seo_path:
            seo_title, seo_desc, seo_tags = parse_seo_txt(seo_path)
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
    folder_script_id = read_script_id(folder)
    folder_name_str = body.folder_name
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

        try:
            result = publish_to_youtube(
                credential=temp_cred,
                file_path=video_path,
                metadata={"title": title, "description": description, "tags": tags},
                on_progress=on_progress,
                thumbnail_path=thumbnail_path or "",
                privacy_status=privacy,
            )
        except Exception as exc:
            if is_reauth_required_error(exc):
                from database import engine as db_engine
                from sqlmodel import Session as SyncSession

                with SyncSession(db_engine) as s:
                    stmt = select(PlatformCredential).where(
                        PlatformCredential.brand_id == cred_brand,
                        PlatformCredential.platform == "youtube",
                    )
                    stale_cred = s.exec(stmt).first()
                    if stale_cred:
                        s.delete(stale_cred)
                        s.commit()
                        logger.info("Disconnected stale youtube credential for brand %s after auth failure", cred_brand)
            raise

        write_youtube_url(Path(folder_path_str), result["url"])

        from database import engine as db_engine
        from sqlmodel import Session as SyncSession

        with SyncSession(db_engine) as s:
            # Persist refreshed token if it changed
            if temp_cred.access_token != cred_access:
                cred_stmt = select(PlatformCredential).where(
                    PlatformCredential.brand_id == cred_brand,
                    PlatformCredential.platform == "youtube",
                )
                db_cred = s.exec(cred_stmt).first()
                if db_cred:
                    db_cred.access_token = temp_cred.access_token
                    db_cred.token_expiry = temp_cred.token_expiry
                    db_cred.updated_at = datetime.now(timezone.utc)
                    s.add(db_cred)
                    s.commit()

            # Create PublishRecord if script_id is known
            if folder_script_id:
                record = PublishRecord(
                    script_id=folder_script_id,
                    brand_id=cred_brand,
                    platform="youtube",
                    status="published",
                    platform_content_id=result.get("id", ""),
                    platform_url=result["url"],
                    file_path=video_path or "",
                    export_folder=folder_name_str,
                    published_at=datetime.now(timezone.utc),
                )
                s.add(record)
                s.commit()

        return result["url"]

    run_in_background(job.id, do_upload)
    return CatalogUploadResponse(job_id=job.id)
