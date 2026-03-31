"""Publishing pipeline — orchestrates uploads to YouTube and other platforms."""

import logging
import os
from datetime import datetime, timezone
from typing import Callable

from config import DATA_DIR
from integrations.youtube_client import refresh_access_token, upload_video
from models.credential import PlatformCredential

logger = logging.getLogger(__name__)

_TOKEN_REFRESH_BUFFER_SECONDS = 300  # Refresh if expiry within 5 minutes

def _resolve_local_path(file_url: str) -> str:
    """Convert a web-relative /static/projects/... URL to a local filesystem path."""
    if file_url.startswith("/static/projects/"):
        relative = file_url[len("/static/projects/"):]
        return str(DATA_DIR / "projects" / relative)
    raise FileNotFoundError(f"Cannot resolve file URL: {file_url}")

def _ensure_token_fresh(credential: PlatformCredential) -> bool:
    """Refresh the access token if it's expired or about to expire.

    Returns True if the token was refreshed (caller should persist).
    """
    if not credential.token_expiry:
        return False

    now = datetime.now(timezone.utc)
    # Refresh if expiry is within the buffer window
    remaining = (credential.token_expiry - now).total_seconds()
    if remaining > _TOKEN_REFRESH_BUFFER_SECONDS:
        return False

    logger.info("Refreshing expired YouTube token for brand %s", credential.brand_id)
    result = refresh_access_token(credential.refresh_token)
    credential.access_token = result["access_token"]
    if result.get("expiry"):
        credential.token_expiry = datetime.fromisoformat(result["expiry"])
    return True

def publish_to_youtube(
    credential: PlatformCredential,
    file_url: str,
    metadata: dict,
    schedule_at: str | None = None,
    on_progress: Callable[[float, str], None] | None = None,
) -> dict[str, str]:
    """Upload a video to YouTube.

    Args:
        credential: PlatformCredential with valid tokens.
        file_url: Web-relative path like /static/projects/.../full_youtube.mp4
        metadata: dict with title, description, tags.
        schedule_at: Optional ISO 8601 datetime for scheduled publishing.
        on_progress: Callback(progress_0_to_1, message).

    Returns dict with id, url.
    """
    local_path = _resolve_local_path(file_url)
    if not os.path.exists(local_path):
        raise FileNotFoundError(f"Video file not found: {local_path}")

    logger.info("Starting YouTube upload: %s (scheduled=%s)", metadata.get("title", "Untitled"), schedule_at)

    # Refresh token if needed
    _ensure_token_fresh(credential)

    if on_progress:
        on_progress(0.05, "Starting YouTube upload...")

    def upload_progress(p: float) -> None:
        if on_progress:
            on_progress(0.05 + p * 0.9, f"Uploading... {int(p * 100)}%")

    result = upload_video(
        access_token=credential.access_token,
        file_path=local_path,
        title=metadata.get("title", "Untitled"),
        description=metadata.get("description", ""),
        tags=metadata.get("tags", []),
        privacy_status="private",
        publish_at=schedule_at,
        on_progress=upload_progress,
    )

    if on_progress:
        on_progress(1.0, "Published!")

    logger.info("YouTube upload complete: video_id=%s", result.get("id"))
    return result
