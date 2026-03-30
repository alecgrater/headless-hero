"""Endpoints for OAuth connection and publishing to platforms."""

import json
import logging
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import HTMLResponse
from pydantic import BaseModel
from sqlmodel import Session, select

from api.database import get_session
from models.credential import PlatformCredential, PlatformCredentialRead
from models.publish import PublishRecord, PublishRecordRead
from pipeline.publishing import publish_to_youtube
from pipeline.render_jobs import create_job, get_job, run_in_background, update_job

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/publish", tags=["publish"])

# --- Request / Response schemas ---

class ConnectRequest(BaseModel):
    brand_id: str
    platform: str  # "youtube"

class ConnectResponse(BaseModel):
    auth_url: str

class DisconnectRequest(BaseModel):
    brand_id: str
    platform: str

class OAuthStatusResponse(BaseModel):
    youtube: PlatformCredentialRead

class UploadRequest(BaseModel):
    script_id: str
    brand_id: str
    platform: str
    file_url: str
    metadata: dict
    schedule_at: str | None = None

class UploadResponse(BaseModel):
    job_id: str

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

# --- Endpoints ---

@router.get("/oauth/status/{brand_id}", response_model=OAuthStatusResponse)
def oauth_status(brand_id: str, session: Session = Depends(get_session)):
    """Check OAuth connection status for all platforms."""
    yt_cred = _get_credential(session, brand_id, "youtube")
    return OAuthStatusResponse(youtube=_make_credential_read("youtube", yt_cred))

@router.post("/oauth/connect", response_model=ConnectResponse)
def oauth_connect(body: ConnectRequest, session: Session = Depends(get_session)):
    """Start OAuth flow — returns the auth URL for the frontend to open."""
    if body.platform != "youtube":
        raise HTTPException(status_code=400, detail=f"Unsupported platform: {body.platform}")

    from integrations.youtube_client import get_auth_url

    logger.info("Starting OAuth connect for brand %s on %s", body.brand_id, body.platform)

    # Encode brand_id in state so we can associate the credential on callback
    auth_url = get_auth_url(state=body.brand_id)
    return ConnectResponse(auth_url=auth_url)

@router.get("/oauth/callback/{platform}", response_class=HTMLResponse)
def oauth_callback(platform: str, code: str = "", state: str = "", error: str = "", session: Session = Depends(get_session)):
    """OAuth redirect handler — exchanges code for tokens and stores credential."""
    if error:
        return HTMLResponse(
            content=f"<html><body><h2>Authorization Failed</h2><p>{error}</p><p>You can close this tab.</p></body></html>",
            status_code=400,
        )

    if platform != "youtube":
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

    from integrations.youtube_client import exchange_code, get_channel_info

    try:
        tokens = exchange_code(code)
        channel = get_channel_info(tokens["access_token"])
    except Exception as exc:
        logger.exception("OAuth exchange failed")
        return HTMLResponse(
            content=f"<html><body><h2>Authorization Failed</h2><p>{exc}</p></body></html>",
            status_code=500,
        )

    # Upsert credential
    existing = _get_credential(session, brand_id, "youtube")
    if existing:
        existing.access_token = tokens["access_token"]
        existing.refresh_token = tokens.get("refresh_token", existing.refresh_token)
        if tokens.get("expiry"):
            existing.token_expiry = datetime.fromisoformat(tokens["expiry"])
        existing.platform_user_id = channel["channel_id"]
        existing.platform_user_name = channel["channel_name"]
        existing.updated_at = datetime.now(timezone.utc)
        session.add(existing)
    else:
        cred = PlatformCredential(
            brand_id=brand_id,
            platform="youtube",
            access_token=tokens["access_token"],
            refresh_token=tokens.get("refresh_token", ""),
            token_expiry=datetime.fromisoformat(tokens["expiry"]) if tokens.get("expiry") else None,
            platform_user_id=channel["channel_id"],
            platform_user_name=channel["channel_name"],
            scope="youtube.upload youtube.readonly",
        )
        session.add(cred)

    session.commit()
    logger.info("OAuth callback success: YouTube channel %s linked for brand %s", channel["channel_name"], brand_id)

    return HTMLResponse(
        content=(
            "<html><body style='font-family:system-ui;text-align:center;padding:60px;background:#1a1a2e;color:#e0e0e0'>"
            "<h2 style='color:#4ade80'>Connected!</h2>"
            f"<p>YouTube channel <strong>{channel['channel_name']}</strong> linked successfully.</p>"
            "<p style='color:#888'>You can close this tab and return to the app.</p>"
            "</body></html>"
        )
    )

@router.delete("/oauth/disconnect")
def oauth_disconnect(body: DisconnectRequest, session: Session = Depends(get_session)):
    """Remove OAuth credential for a platform."""
    cred = _get_credential(session, body.brand_id, body.platform)
    if cred:
        session.delete(cred)
        session.commit()
        logger.info("Disconnected %s for brand %s", body.platform, body.brand_id)
    return {"ok": True}

@router.post("/upload", response_model=UploadResponse)
def start_upload(body: UploadRequest, session: Session = Depends(get_session)):
    """Start a background upload to a platform."""
    if body.platform != "youtube":
        raise HTTPException(status_code=400, detail=f"Unsupported platform: {body.platform}")

    cred = _get_credential(session, body.brand_id, "youtube")
    if not cred:
        raise HTTPException(status_code=400, detail="YouTube not connected for this brand")

    # Create publish record
    record = PublishRecord(
        script_id=body.script_id,
        brand_id=body.brand_id,
        platform=body.platform,
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
        from api.database import engine as db_engine
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

@router.get("/status/{job_id}", response_model=PublishStatusResponse)
def publish_status(job_id: str):
    """Poll the progress of a background publish job."""
    job = get_job(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    d = job.to_dict()
    return PublishStatusResponse(**d)

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
            schedule_at=r.schedule_at,
            published_at=r.published_at,
            error=r.error,
            created_at=r.created_at,
        )
        for r in records
    ]
