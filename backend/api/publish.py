"""Endpoints for OAuth connection and publishing to platforms."""

import json
import logging
import os
import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import HTMLResponse
from pydantic import BaseModel
from sqlmodel import Session, select

from database import get_default_brand_id, get_session
from config import DATA_DIR
from models.credential import PlatformCredential, PlatformCredentialRead
from models.publish import PublishRecord, PublishRecordRead
from models.script import Script, ScriptContent
from pipeline.publishing import publish_short_to_platform, publish_to_youtube
from pipeline.render_jobs import create_job, get_job, run_in_background, update_job

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/publish", tags=["publish"])

SUPPORTED_PLATFORMS = ("youtube", "tiktok", "instagram")

# --- Request / Response schemas ---

class ConnectRequest(BaseModel):
    platform: str

class ConnectResponse(BaseModel):
    auth_url: str

class DisconnectRequest(BaseModel):
    platform: str

class OAuthStatusResponse(BaseModel):
    youtube: PlatformCredentialRead
    tiktok: PlatformCredentialRead
    instagram: PlatformCredentialRead

class UploadRequest(BaseModel):
    script_id: str
    platform: str
    file_url: str
    metadata: dict
    schedule_at: str | None = None

class UploadResponse(BaseModel):
    job_id: str

class ShortFormUploadRequest(BaseModel):
    script_id: str
    segment_idx: int

class LongFormUploadRequest(BaseModel):
    script_id: str
    privacy_status: str = "unlisted"

class ShortUploadPlatformStatus(BaseModel):
    platform: str
    status: str
    platform_url: str = ""
    error: str = ""
    published_at: datetime | None = None

class ShortUploadStatus(BaseModel):
    short_index: int
    platforms: dict[str, ShortUploadPlatformStatus]

class PublishStatusResponse(BaseModel):
    job_id: str
    status: str
    progress: float
    current_step: str
    output_urls: list[str]
    error: str | None = None


# --- Helpers ---

def _get_credential(session: Session, brand_id: str, platform: str) -> PlatformCredential | None:
    stmt = select(PlatformCredential).where(
        PlatformCredential.brand_id == brand_id,
        PlatformCredential.platform == platform,
    )
    return session.exec(stmt).first()

def _make_credential_read(platform: str, cred: PlatformCredential | None) -> PlatformCredentialRead:
    if cred:
        return PlatformCredentialRead(
            platform=platform,
            platform_user_id=cred.platform_user_id,
            platform_user_name=cred.platform_user_name,
            connected=True,
        )
    return PlatformCredentialRead(
        platform=platform,
        platform_user_id="",
        platform_user_name="",
        connected=False,
    )

def _require_supported_platform(platform: str) -> None:
    if platform not in SUPPORTED_PLATFORMS:
        raise HTTPException(status_code=400, detail=f"Unsupported platform: {platform}")

def _credential_expiry_from_seconds(seconds: int | None) -> datetime | None:
    if not seconds:
        return None
    return datetime.now(timezone.utc) + timedelta(seconds=int(seconds))

def _upsert_credential(
    session: Session,
    brand_id: str,
    platform: str,
    access_token: str,
    refresh_token: str,
    platform_user_id: str,
    platform_user_name: str,
    scope: str,
    token_expiry: datetime | None = None,
) -> None:
    existing = _get_credential(session, brand_id, platform)
    if existing:
        existing.access_token = access_token
        existing.refresh_token = refresh_token or existing.refresh_token
        existing.token_expiry = token_expiry
        existing.platform_user_id = platform_user_id
        existing.platform_user_name = platform_user_name
        existing.scope = scope
        existing.updated_at = datetime.now(timezone.utc)
        session.add(existing)
        return

    session.add(
        PlatformCredential(
            brand_id=brand_id,
            platform=platform,
            access_token=access_token,
            refresh_token=refresh_token,
            token_expiry=token_expiry,
            platform_user_id=platform_user_id,
            platform_user_name=platform_user_name,
            scope=scope,
        )
    )

def _rendered_short_path(script_id: str, segment_idx: int, content: ScriptContent, project_title: str) -> str:
    from pipeline.short_form_render import _short_filename
    from config import DATA_DIR
    from pipeline.export_paths import project_downloads_folder

    if segment_idx < 0 or segment_idx >= len(content.segments):
        raise HTTPException(status_code=400, detail="segment_idx out of range")

    project_path = DATA_DIR / "projects" / script_id / "renders" / "shorts" / f"{segment_idx}.mp4"
    if project_path.is_file():
        return str(project_path)

    segment = content.segments[segment_idx]
    downloads_path = project_downloads_folder(project_title, create=False) / _short_filename(
        segment.name or f"Segment {segment_idx + 1}"
    )
    if downloads_path.is_file():
        return str(downloads_path)

    raise HTTPException(status_code=400, detail=f"Short {segment_idx + 1} has not been rendered yet")

def _rendered_longform_path(script_id: str) -> Path:
    path = DATA_DIR / "projects" / script_id / "renders" / "full_youtube.mp4"
    if not path.is_file():
        raise HTTPException(status_code=400, detail="Render YouTube Video first before uploading to YouTube")
    return path

def _longform_thumbnail_path(script_id: str) -> Path:
    path = DATA_DIR / "projects" / script_id / "renders" / "thumbnails" / "0.png"
    if not path.is_file():
        raise HTTPException(status_code=400, detail="Generate the YouTube thumbnail first before uploading to YouTube")
    return path

def _longform_metadata(content: ScriptContent) -> dict:
    metadata = content.seo_metadata or {}
    youtube = metadata.get("youtube") or {}
    title = (youtube.get("title") or "").strip()
    description = youtube.get("description")
    tags = youtube.get("tags")
    if not title or description is None or not isinstance(tags, list):
        raise HTTPException(status_code=400, detail="Generate long-form YouTube SEO first before uploading to YouTube")
    return {
        "title": title,
        "description": description,
        "tags": tags,
    }

def _short_metadata(content: ScriptContent, segment_idx: int) -> dict:
    metadata = content.short_form_seo_metadata or {}
    shorts = metadata.get("shorts") or []
    uses_one_based_indices = any(int(s.get("index", -1)) == 1 for s in shorts)
    expected_index = segment_idx + 1 if uses_one_based_indices else segment_idx
    item = next((s for s in shorts if int(s.get("index", -1)) == expected_index), None)
    if not item:
        raise HTTPException(status_code=400, detail=f"Short-form SEO is missing for short {segment_idx + 1}")
    return {
        "title": item.get("title", content.title),
        "description": item.get("description", ""),
        "hashtags": item.get("hashtags", []),
        "tags": item.get("tags", []),
        "privacy_status": "public",
    }

def _already_published_record(
    session: Session,
    script_id: str,
    brand_id: str,
    platform: str,
    short_index: int,
) -> PublishRecord | None:
    stmt = select(PublishRecord).where(
        PublishRecord.script_id == script_id,
        PublishRecord.brand_id == brand_id,
        PublishRecord.platform == platform,
        PublishRecord.asset_kind == "short_form",
        PublishRecord.short_index == short_index,
        PublishRecord.status.in_(["pending", "uploading", "published", "scheduled"]),
    )
    return session.exec(stmt).first()

def _persist_refreshed_credential(session: Session, credential: PlatformCredential) -> None:
    stmt = select(PlatformCredential).where(
        PlatformCredential.brand_id == credential.brand_id,
        PlatformCredential.platform == credential.platform,
    )
    db_cred = session.exec(stmt).first()
    if not db_cred:
        return
    db_cred.access_token = credential.access_token
    db_cred.refresh_token = credential.refresh_token
    db_cred.token_expiry = credential.token_expiry
    db_cred.updated_at = datetime.now(timezone.utc)
    session.add(db_cred)
    session.commit()

def _refresh_pending_tiktok_record(session: Session, record: PublishRecord) -> None:
    if record.platform != "tiktok" or record.status not in ("pending", "uploading"):
        return
    metadata = json.loads(record.metadata_json or "{}")
    publish_id = metadata.get("publish_id") or record.platform_content_id
    credential = _get_credential(session, record.brand_id, "tiktok")
    if not credential or not publish_id:
        return

    from integrations.tiktok_client import (
        _first_public_post_id,
        _status_text,
        fetch_publish_status,
    )
    from pipeline.publishing import ensure_token_fresh

    if ensure_token_fresh(credential):
        session.add(credential)
        session.commit()

    status = fetch_publish_status(credential.access_token, publish_id)
    status_text = _status_text(status)
    now = datetime.now(timezone.utc)
    if status_text == "PUBLISH_COMPLETE":
        public_post_id = _first_public_post_id(status)
        if public_post_id:
            record.platform_content_id = public_post_id
        if status.get("share_url"):
            record.platform_url = status["share_url"]
        record.status = "published"
        record.published_at = now
        record.error = ""
    elif status_text == "SEND_TO_USER_INBOX":
        record.status = "failed"
        record.error = "TikTok sent the post to the creator inbox instead of publishing directly"
    elif any(part in status_text for part in ("FAIL", "ERROR", "REJECT")):
        record.status = "failed"
        record.error = str(status.get("fail_reason") or status.get("message") or status_text)[:1000]
    else:
        record.status = "pending"
    record.updated_at = now
    session.add(record)
    session.commit()

# --- Endpoints ---

@router.get("/oauth/status", response_model=OAuthStatusResponse)
def oauth_status(session: Session = Depends(get_session)):
    """Check OAuth connection status for all platforms."""
    brand_id = get_default_brand_id(session)
    return OAuthStatusResponse(
        youtube=_make_credential_read("youtube", _get_credential(session, brand_id, "youtube")),
        tiktok=_make_credential_read("tiktok", _get_credential(session, brand_id, "tiktok")),
        instagram=_make_credential_read("instagram", _get_credential(session, brand_id, "instagram")),
    )

@router.post("/oauth/connect", response_model=ConnectResponse)
def oauth_connect(body: ConnectRequest, session: Session = Depends(get_session)):
    """Start OAuth flow — returns the auth URL for the frontend to open."""
    _require_supported_platform(body.platform)
    brand_id = get_default_brand_id(session)
    logger.info("Starting OAuth connect for brand %s on %s", brand_id, body.platform)

    if body.platform == "youtube":
        if not os.environ.get("GOOGLE_CLIENT_ID") or not os.environ.get("GOOGLE_CLIENT_SECRET"):
            raise HTTPException(
                status_code=400,
                detail="YouTube OAuth requires GOOGLE_CLIENT_ID and GOOGLE_CLIENT_SECRET. Set them in Settings → API Keys.",
            )
        from integrations.youtube_client import get_auth_url
        auth_url = get_auth_url(state=brand_id)
    elif body.platform == "tiktok":
        if not os.environ.get("TIKTOK_CLIENT_KEY") or not os.environ.get("TIKTOK_CLIENT_SECRET"):
            raise HTTPException(
                status_code=400,
                detail="TikTok OAuth requires TIKTOK_CLIENT_KEY and TIKTOK_CLIENT_SECRET. Set them in Settings → API Keys.",
            )
        from integrations.tiktok_client import get_auth_url
        auth_url = get_auth_url(state=brand_id)
    else:
        if not os.environ.get("META_APP_ID") or not os.environ.get("META_APP_SECRET"):
            raise HTTPException(
                status_code=400,
                detail="Instagram OAuth requires META_APP_ID and META_APP_SECRET. Set them in Settings → API Keys.",
            )
        from integrations.instagram_client import get_auth_url
        auth_url = get_auth_url(state=brand_id)
    return ConnectResponse(auth_url=auth_url)

@router.get("/oauth/callback/{platform}", response_class=HTMLResponse)
def oauth_callback(platform: str, code: str = "", state: str = "", error: str = "", session: Session = Depends(get_session)):
    """OAuth redirect handler — exchanges code for tokens and stores credential."""
    if error:
        return HTMLResponse(
            content=f"<html><body><h2>Authorization Failed</h2><p>{error}</p><p>You can close this tab.</p></body></html>",
            status_code=400,
        )

    if platform not in SUPPORTED_PLATFORMS:
        return HTMLResponse(
            content="<html><body><h2>Unsupported platform</h2></body></html>",
            status_code=400,
        )

    if not code:
        return HTMLResponse(
            content="<html><body><h2>No authorization code received</h2></body></html>",
            status_code=400,
        )

    brand_id = state

    try:
        if platform == "youtube":
            from integrations.youtube_client import exchange_code, get_channel_info
            tokens = exchange_code(code, state=brand_id)
            channel = get_channel_info(tokens["access_token"])
            _upsert_credential(
                session=session,
                brand_id=brand_id,
                platform="youtube",
                access_token=tokens["access_token"],
                refresh_token=tokens.get("refresh_token", ""),
                token_expiry=datetime.fromisoformat(tokens["expiry"]) if tokens.get("expiry") else None,
                platform_user_id=channel["channel_id"],
                platform_user_name=channel["channel_name"],
                scope="youtube.upload youtube.readonly",
            )
            display_name = channel["channel_name"]
        elif platform == "tiktok":
            from integrations.tiktok_client import exchange_code, get_user_info
            tokens = exchange_code(code)
            user = get_user_info(tokens["access_token"])
            _upsert_credential(
                session=session,
                brand_id=brand_id,
                platform="tiktok",
                access_token=tokens["access_token"],
                refresh_token=tokens.get("refresh_token", ""),
                token_expiry=_credential_expiry_from_seconds(tokens.get("expires_in")),
                platform_user_id=user["open_id"] or tokens.get("open_id", ""),
                platform_user_name=user["display_name"],
                scope=tokens.get("scope", "user.info.basic,video.publish"),
            )
            display_name = user["display_name"]
        else:
            from integrations.instagram_client import exchange_code, get_instagram_account_info
            tokens = exchange_code(code)
            account = get_instagram_account_info(tokens["access_token"])
            _upsert_credential(
                session=session,
                brand_id=brand_id,
                platform="instagram",
                access_token=tokens["access_token"],
                refresh_token="",
                token_expiry=_credential_expiry_from_seconds(tokens.get("expires_in")),
                platform_user_id=account["ig_user_id"],
                platform_user_name=account["username"],
                scope="instagram_basic instagram_content_publish pages_show_list pages_read_engagement business_management",
            )
            display_name = account["username"]
    except Exception as exc:
        logger.exception("OAuth exchange failed")
        return HTMLResponse(
            content=f"<html><body><h2>Authorization Failed</h2><p>{exc}</p></body></html>",
            status_code=500,
        )

    session.commit()
    logger.info("OAuth callback success: %s account %s linked for brand %s", platform, display_name, brand_id)

    return HTMLResponse(
        content=(
            "<html><body style='font-family:system-ui;text-align:center;padding:60px;background:#1a1a2e;color:#e0e0e0'>"
            "<h2 style='color:#4ade80'>Connected!</h2>"
            f"<p>{platform.title()} account <strong>{display_name}</strong> linked successfully.</p>"
            "<p style='color:#888'>You can close this tab and return to the app.</p>"
            "</body></html>"
        )
    )

@router.delete("/oauth/disconnect")
def oauth_disconnect(body: DisconnectRequest, session: Session = Depends(get_session)):
    """Remove OAuth credential for a platform."""
    _require_supported_platform(body.platform)
    brand_id = get_default_brand_id(session)
    cred = _get_credential(session, brand_id, body.platform)
    if cred:
        session.delete(cred)
        session.commit()
        logger.info("Disconnected %s for brand %s", body.platform, brand_id)
    return {"ok": True}

@router.post("/upload", response_model=UploadResponse)
def start_upload(body: UploadRequest, session: Session = Depends(get_session)):
    """Start a background upload to a platform."""
    if body.platform != "youtube":
        raise HTTPException(status_code=400, detail=f"Unsupported platform: {body.platform}")

    brand_id = get_default_brand_id(session)
    cred = _get_credential(session, brand_id, "youtube")
    if not cred:
        raise HTTPException(status_code=400, detail="YouTube not connected")

    # Create publish record
    record = PublishRecord(
        script_id=body.script_id,
        brand_id=brand_id,
        platform=body.platform,
        asset_kind="long_form",
        status="uploading",
        file_path=body.file_url,
        metadata_json=json.dumps(body.metadata),
        schedule_at=datetime.fromisoformat(body.schedule_at) if body.schedule_at else None,
    )
    session.add(record)
    session.commit()
    session.refresh(record)

    # Copy mutable state for background thread
    record_id = record.id
    cred_brand = cred.brand_id
    cred_refresh = cred.refresh_token
    cred_access = cred.access_token
    cred_expiry = cred.token_expiry

    job = create_job()

    logger.info("Starting upload for script %s to %s", body.script_id, body.platform)

    def do_upload():
        from database import engine as db_engine
        from sqlmodel import Session as SyncSession

        # Build a temporary credential object for the pipeline
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
                file_url=body.file_url,
                metadata=body.metadata,
                schedule_at=body.schedule_at,
                on_progress=on_progress,
            )

            # Update publish record in a new session
            with SyncSession(db_engine) as s:
                rec = s.get(PublishRecord, record_id)
                if rec:
                    rec.status = "scheduled" if body.schedule_at else "published"
                    rec.platform_content_id = result["id"]
                    rec.platform_url = result["url"]
                    rec.published_at = datetime.now(timezone.utc)
                    rec.updated_at = datetime.now(timezone.utc)

                    # Write file markers to export folder if it exists
                    from models.script import Script
                    from pipeline.catalog import find_export_folder, write_youtube_url
                    script = s.get(Script, body.script_id)
                    if script:
                        export_path = find_export_folder(script.topic_title, script.created_at)
                        if export_path:
                            write_youtube_url(export_path, result["url"])
                            rec.export_folder = export_path.name

                    s.add(rec)
                    s.commit()

                # Update credential if token was refreshed
                if temp_cred.access_token != cred_access:
                    stmt = select(PlatformCredential).where(
                        PlatformCredential.brand_id == cred_brand,
                        PlatformCredential.platform == "youtube",
                    )
                    db_cred = s.exec(stmt).first()
                    if db_cred:
                        db_cred.access_token = temp_cred.access_token
                        db_cred.refresh_token = temp_cred.refresh_token
                        db_cred.token_expiry = temp_cred.token_expiry
                        db_cred.updated_at = datetime.now(timezone.utc)
                        s.add(db_cred)
                        s.commit()

            return result["url"]

        except Exception as exc:
            # Update publish record with error
            with SyncSession(db_engine) as s:
                rec = s.get(PublishRecord, record_id)
                if rec:
                    rec.status = "failed"
                    rec.error = str(exc)[:1000]
                    rec.updated_at = datetime.now(timezone.utc)
                    s.add(rec)
                    s.commit()
            raise

    run_in_background(job.id, do_upload)
    return UploadResponse(job_id=job.id)

@router.post("/youtube-longform/upload", response_model=UploadResponse)
def start_longform_youtube_upload(body: LongFormUploadRequest, session: Session = Depends(get_session)):
    """Upload the rendered long-form YouTube video with generated SEO and thumbnail."""
    if body.privacy_status not in {"private", "unlisted", "public"}:
        raise HTTPException(status_code=400, detail="Invalid privacy status")

    brand_id = get_default_brand_id(session)
    script = session.get(Script, body.script_id)
    if not script:
        raise HTTPException(status_code=404, detail="Script not found")

    cred = _get_credential(session, brand_id, "youtube")
    if not cred:
        raise HTTPException(status_code=400, detail="YouTube not connected. Connect YouTube in Settings → Publishing first")

    content = ScriptContent.model_validate(json.loads(script.script_json))
    video_path = _rendered_longform_path(body.script_id)
    thumbnail_path = _longform_thumbnail_path(body.script_id)
    metadata = _longform_metadata(content)

    record = PublishRecord(
        script_id=body.script_id,
        brand_id=brand_id,
        platform="youtube",
        asset_kind="long_form",
        status="uploading",
        file_path=str(video_path),
        metadata_json=json.dumps(metadata),
    )
    session.add(record)
    session.commit()
    session.refresh(record)

    record_id = record.id
    cred_brand = cred.brand_id
    cred_refresh = cred.refresh_token
    cred_access = cred.access_token
    cred_expiry = cred.token_expiry
    script_title = script.topic_title
    script_created = script.created_at
    privacy = body.privacy_status

    job = create_job()
    logger.info("Starting long-form YouTube upload for script %s", body.script_id)

    def do_upload():
        from database import engine as db_engine
        from sqlmodel import Session as SyncSession

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
                file_path=str(video_path),
                metadata=metadata,
                on_progress=on_progress,
                thumbnail_path=str(thumbnail_path),
                privacy_status=privacy,
            )

            with SyncSession(db_engine) as s:
                rec = s.get(PublishRecord, record_id)
                if rec:
                    rec.status = "published"
                    rec.platform_content_id = result["id"]
                    rec.platform_url = result["url"]
                    rec.published_at = datetime.now(timezone.utc)
                    rec.updated_at = datetime.now(timezone.utc)

                    from pipeline.catalog import find_export_folder, write_youtube_url
                    export_path = find_export_folder(script_title, script_created)
                    if export_path:
                        write_youtube_url(export_path, result["url"])
                        rec.export_folder = export_path.name

                    s.add(rec)
                    s.commit()

                if temp_cred.access_token != cred_access:
                    stmt = select(PlatformCredential).where(
                        PlatformCredential.brand_id == cred_brand,
                        PlatformCredential.platform == "youtube",
                    )
                    db_cred = s.exec(stmt).first()
                    if db_cred:
                        db_cred.access_token = temp_cred.access_token
                        db_cred.refresh_token = temp_cred.refresh_token
                        db_cred.token_expiry = temp_cred.token_expiry
                        db_cred.updated_at = datetime.now(timezone.utc)
                        s.add(db_cred)
                        s.commit()

            return result["url"]
        except Exception as exc:
            with SyncSession(db_engine) as s:
                rec = s.get(PublishRecord, record_id)
                if rec:
                    rec.status = "failed"
                    rec.error = str(exc)[:1000]
                    rec.updated_at = datetime.now(timezone.utc)
                    s.add(rec)
                    s.commit()
            raise

    run_in_background(job.id, do_upload)
    return UploadResponse(job_id=job.id)

@router.post("/short-form/upload", response_model=UploadResponse)
def start_short_form_upload(body: ShortFormUploadRequest, session: Session = Depends(get_session)):
    """Upload one rendered short to every connected short-form platform."""
    brand_id = get_default_brand_id(session)
    script = session.get(Script, body.script_id)
    if not script:
        raise HTTPException(status_code=404, detail="Script not found")

    content = ScriptContent.model_validate(json.loads(script.script_json))
    file_path = _rendered_short_path(
        script_id=body.script_id,
        segment_idx=body.segment_idx,
        content=content,
        project_title=script.topic_title or "Untitled",
    )
    metadata = _short_metadata(content, body.segment_idx)

    connected: list[PlatformCredential] = []
    skipped_urls: list[str] = []
    for platform in SUPPORTED_PLATFORMS:
        cred = _get_credential(session, brand_id, platform)
        if not cred:
            continue
        already = _already_published_record(session, body.script_id, brand_id, platform, body.segment_idx)
        if already:
            skipped_urls.append(already.platform_url)
            continue
        connected.append(cred)

    if not connected and skipped_urls:
        raise HTTPException(status_code=400, detail="This short is already uploaded or uploading to every connected platform")
    if not connected:
        raise HTTPException(status_code=400, detail="No connected short-form platforms. Connect accounts in Settings → Publishing.")

    batch_id = uuid.uuid4().hex
    record_ids: dict[str, str] = {}
    credential_snapshots: dict[str, dict] = {}
    for cred in connected:
        record = PublishRecord(
            script_id=body.script_id,
            brand_id=brand_id,
            platform=cred.platform,
            asset_kind="short_form",
            short_index=body.segment_idx,
            upload_batch_id=batch_id,
            status="uploading",
            file_path=file_path,
            metadata_json=json.dumps(metadata),
        )
        session.add(record)
        session.commit()
        session.refresh(record)
        record_ids[cred.platform] = record.id
        credential_snapshots[cred.platform] = {
            "brand_id": cred.brand_id,
            "platform": cred.platform,
            "access_token": cred.access_token,
            "refresh_token": cred.refresh_token,
            "token_expiry": cred.token_expiry,
            "platform_user_id": cred.platform_user_id,
        }

    job = create_job(scene_count=len(connected))
    logger.info(
        "Starting short-form upload for script %s short %d to %s",
        body.script_id,
        body.segment_idx,
        ", ".join(record_ids.keys()),
    )

    def do_upload():
        from database import engine as db_engine
        from sqlmodel import Session as SyncSession

        output_urls: list[str] = []
        failures: list[str] = []
        platform_count = len(credential_snapshots)

        for idx, (platform, snapshot) in enumerate(credential_snapshots.items()):
            record_id = record_ids[platform]
            temp_cred = PlatformCredential(
                brand_id=snapshot["brand_id"],
                platform=snapshot["platform"],
                access_token=snapshot["access_token"],
                refresh_token=snapshot["refresh_token"],
                token_expiry=snapshot["token_expiry"],
                platform_user_id=snapshot["platform_user_id"],
            )

            def on_progress(p: float, msg: str, _idx: int = idx, _platform: str = platform) -> None:
                global_p = (_idx + p) / platform_count
                update_job(
                    job.id,
                    progress=global_p,
                    current_step=f"{_platform.title()}: {msg}",
                )

            try:
                result = publish_short_to_platform(
                    platform=platform,
                    credential=temp_cred,
                    file_path=file_path,
                    metadata=metadata,
                    on_progress=on_progress,
                )
                output_urls.append(result.get("url", ""))
                with SyncSession(db_engine) as s:
                    rec = s.get(PublishRecord, record_id)
                    if rec:
                        result_status = result.get("status", "published")
                        rec.status = result_status
                        rec.platform_content_id = result.get("id", "")
                        rec.platform_url = result.get("url", "")
                        if result.get("publish_id"):
                            try:
                                record_metadata = json.loads(rec.metadata_json or "{}")
                            except json.JSONDecodeError:
                                record_metadata = {}
                            record_metadata["publish_id"] = result["publish_id"]
                            rec.metadata_json = json.dumps(record_metadata)
                        if result_status in ("published", "scheduled"):
                            rec.published_at = datetime.now(timezone.utc)
                        rec.updated_at = datetime.now(timezone.utc)
                        s.add(rec)
                        s.commit()
                    _persist_refreshed_credential(s, temp_cred)
            except Exception as exc:
                failures.append(f"{platform}: {exc}")
                logger.exception("Short-form upload failed for %s", platform)
                with SyncSession(db_engine) as s:
                    rec = s.get(PublishRecord, record_id)
                    if rec:
                        rec.status = "failed"
                        rec.error = str(exc)[:1000]
                        rec.updated_at = datetime.now(timezone.utc)
                        s.add(rec)
                        s.commit()

        if failures:
            raise RuntimeError("; ".join(failures))
        update_job(job.id, progress=1.0, current_step="Short uploaded")
        return output_urls

    run_in_background(job.id, do_upload)
    return UploadResponse(job_id=job.id)

@router.get("/status/{job_id}", response_model=PublishStatusResponse)
def publish_status(job_id: str):
    """Poll the progress of a background publish job."""
    job = get_job(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    job_dict = job.to_dict()
    return PublishStatusResponse(**job_dict)

@router.get("/history/{script_id}", response_model=list[PublishRecordRead])
def publish_history(script_id: str, session: Session = Depends(get_session)):
    """Get publish history for a script."""
    stmt = select(PublishRecord).where(
        PublishRecord.script_id == script_id
    ).order_by(PublishRecord.created_at.desc())
    records = session.exec(stmt).all()
    return [
        PublishRecordRead(
            id=r.id,
            script_id=r.script_id,
            brand_id=r.brand_id,
            platform=r.platform,
            status=r.status,
            platform_content_id=r.platform_content_id,
            platform_url=r.platform_url,
            asset_kind=r.asset_kind,
            short_index=r.short_index,
            upload_batch_id=r.upload_batch_id,
            file_path=r.file_path,
            schedule_at=r.schedule_at,
            published_at=r.published_at,
            error=r.error,
            created_at=r.created_at,
        )
        for r in records
    ]

@router.get("/short-form/status/{script_id}", response_model=dict[int, ShortUploadStatus])
def short_form_upload_status(script_id: str, session: Session = Depends(get_session)):
    """Return latest per-platform publish state for each short in a project."""
    stmt = select(PublishRecord).where(
        PublishRecord.script_id == script_id,
        PublishRecord.asset_kind == "short_form",
    ).order_by(PublishRecord.created_at.desc())
    records = session.exec(stmt).all()
    grouped: dict[int, ShortUploadStatus] = {}
    for record in records:
        try:
            _refresh_pending_tiktok_record(session, record)
        except Exception:
            logger.exception("Failed to refresh pending TikTok publish status")
        if record.short_index is None:
            continue
        if record.short_index not in grouped:
            grouped[record.short_index] = ShortUploadStatus(short_index=record.short_index, platforms={})
        if record.platform in grouped[record.short_index].platforms:
            continue
        grouped[record.short_index].platforms[record.platform] = ShortUploadPlatformStatus(
            platform=record.platform,
            status=record.status,
            platform_url=record.platform_url,
            error=record.error,
            published_at=record.published_at,
        )
    return grouped
