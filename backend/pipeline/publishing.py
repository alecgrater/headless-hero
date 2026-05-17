"""Publishing pipeline — orchestrates uploads to YouTube and other platforms."""

import logging
import os
from datetime import datetime, timezone
from typing import Callable

from config import DATA_DIR
from integrations.youtube_client import refresh_access_token, set_thumbnail, upload_video
from models.credential import PlatformCredential

logger = logging.getLogger(__name__)

_TOKEN_REFRESH_BUFFER_SECONDS = 300  # Refresh if expiry within 5 minutes
_YOUTUBE_DESCRIPTION_LIMIT = 5000


def is_reauth_required_error(exc: Exception) -> bool:
    """Return True when an OAuth error requires the user to reconnect."""
    msg = str(exc)
    return (
        "invalid_grant" in msg
        or "Token has been expired or revoked" in msg
        or "connection has expired or been revoked" in msg
    )

def _resolve_local_path(file_url: str) -> str:
    """Convert a web-relative /static/projects/... URL to a local filesystem path."""
    if file_url.startswith("/static/projects/"):
        relative = file_url[len("/static/projects/"):]
        return str(DATA_DIR / "projects" / relative)
    raise FileNotFoundError(f"Cannot resolve file URL: {file_url}")

def ensure_token_fresh(credential: PlatformCredential) -> bool:
    """Refresh the access token if it's expired or about to expire.

    Returns True if the token was refreshed (caller should persist).
    Raises RuntimeError with a clear re-auth message on invalid_grant.
    """
    needs_refresh: bool
    if not credential.token_expiry:
        # No expiry stored — we can't know if the access token is still valid.
        # Attempt a proactive refresh so we don't hit a silent 401 mid-upload.
        needs_refresh = True
    else:
        now = datetime.now(timezone.utc)
        expiry = credential.token_expiry
        if expiry.tzinfo is None:
            expiry = expiry.replace(tzinfo=timezone.utc)
        remaining = (expiry - now).total_seconds()
        needs_refresh = remaining <= _TOKEN_REFRESH_BUFFER_SECONDS

    if not needs_refresh:
        return False

    logger.info("Refreshing expired %s token for brand %s", credential.platform, credential.brand_id)
    if credential.platform == "youtube":
        try:
            result = refresh_access_token(credential.refresh_token)
        except Exception as exc:
            _handle_refresh_error(exc, "youtube")
            raise  # _handle_refresh_error always raises; this line is unreachable but satisfies type checkers
        credential.access_token = result["access_token"]
        if result.get("expiry"):
            credential.token_expiry = datetime.fromisoformat(result["expiry"])
    elif credential.platform == "tiktok":
        from integrations.tiktok_client import refresh_access_token as refresh_tiktok_access_token

        try:
            result = refresh_tiktok_access_token(credential.refresh_token)
        except Exception as exc:
            _handle_refresh_error(exc, "tiktok")
            raise  # _handle_refresh_error always raises; this line is unreachable but satisfies type checkers
        credential.access_token = result["access_token"]
        credential.refresh_token = result.get("refresh_token", credential.refresh_token)
        if result.get("expires_in"):
            from datetime import timedelta

            credential.token_expiry = datetime.now(timezone.utc) + timedelta(seconds=int(result["expires_in"]))
    else:
        return False
    return True


def _handle_refresh_error(exc: Exception, platform: str) -> None:
    """Convert OAuth refresh errors into clear, actionable RuntimeErrors."""
    if is_reauth_required_error(exc):
        raise RuntimeError(
            f"Your {platform} connection has expired or been revoked. "
            "Please reconnect your account in Settings → Publishing."
        ) from exc
    # Re-raise anything else unchanged so it still surfaces with its original detail.
    raise exc

def _build_youtube_description(description: str, tags: list[str]) -> str:
    """Append tags to the description as 'Tags: tag1, tag2, ...' at the bottom."""
    base = description.strip()
    if tags:
        tags_line = "Tags: " + ", ".join(tags)
        if not base:
            return tags_line[:_YOUTUBE_DESCRIPTION_LIMIT]
        tagged = f"{base}\n\n{tags_line}"
        if len(tagged) <= _YOUTUBE_DESCRIPTION_LIMIT:
            return tagged
        return base[:_YOUTUBE_DESCRIPTION_LIMIT]
    return base[:_YOUTUBE_DESCRIPTION_LIMIT]


def publish_to_youtube(
    credential: PlatformCredential,
    file_url: str = "",
    metadata: dict | None = None,
    schedule_at: str | None = None,
    on_progress: Callable[[float, str], None] | None = None,
    file_path: str = "",
    thumbnail_path: str = "",
    privacy_status: str = "private",
) -> dict[str, str]:
    """Upload a video to YouTube.

    Args:
        credential: PlatformCredential with valid tokens.
        file_url: Web-relative path like /static/projects/.../full_youtube.mp4
        metadata: dict with title, description, tags.
        schedule_at: Optional ISO 8601 datetime for scheduled publishing.
        on_progress: Callback(progress_0_to_1, message).
        file_path: Absolute path to video file (alternative to file_url).
        thumbnail_path: Absolute path to thumbnail image to set after upload.
        privacy_status: YouTube privacy status (private, unlisted, public).

    Returns dict with id, url.
    """
    if metadata is None:
        metadata = {}

    if file_path:
        local_path = file_path
    else:
        local_path = _resolve_local_path(file_url)
    if not os.path.exists(local_path):
        raise FileNotFoundError(f"Video file not found: {local_path}")

    logger.info("Starting YouTube upload: %s (scheduled=%s)", metadata.get("title", "Untitled"), schedule_at)

    # Refresh token if needed
    ensure_token_fresh(credential)

    if on_progress:
        on_progress(0.05, "Starting YouTube upload...")

    def upload_progress(p: float) -> None:
        if on_progress:
            on_progress(0.05 + p * 0.9, "Uploading...")

    tags = metadata.get("tags", [])
    description = _build_youtube_description(metadata.get("description", ""), tags)
    result = upload_video(
        access_token=credential.access_token,
        file_path=local_path,
        title=metadata.get("title", "Untitled"),
        description=description,
        tags=tags,
        privacy_status=privacy_status if not schedule_at else "private",
        publish_at=schedule_at,
        on_progress=upload_progress,
    )

    if thumbnail_path and os.path.exists(thumbnail_path):
        if on_progress:
            on_progress(0.96, "Setting thumbnail...")
        set_thumbnail(credential.access_token, result["id"], thumbnail_path)

    if on_progress:
        on_progress(1.0, "Published!")

    logger.info("YouTube upload complete: video_id=%s", result.get("id"))
    return result


def publish_short_to_platform(
    platform: str,
    credential: PlatformCredential,
    file_path: str,
    metadata: dict,
    on_progress: Callable[[float, str], None] | None = None,
) -> dict[str, str]:
    """Publish a short-form video to a connected platform."""
    if not os.path.exists(file_path):
        raise FileNotFoundError(f"Video file not found: {file_path}")

    ensure_token_fresh(credential)

    title = metadata.get("title", "Untitled")
    description = metadata.get("description", "")
    tags = metadata.get("tags", [])
    hashtags = metadata.get("hashtags", [])

    if platform == "youtube":
        yt_description = description
        if hashtags:
            yt_description = f"{yt_description}\n\n{' '.join(hashtags)}".strip()
        return publish_to_youtube(
            credential=credential,
            file_path=file_path,
            metadata={
                "title": title,
                "description": yt_description,
                "tags": tags,
            },
            on_progress=on_progress,
            privacy_status=metadata.get("privacy_status", "public"),
        )

    if platform == "tiktok":
        from integrations.tiktok_client import upload_video as upload_tiktok_video

        if on_progress:
            on_progress(0.05, "Starting TikTok upload...")

        def upload_progress(p: float) -> None:
            if on_progress:
                on_progress(0.05 + p * 0.9, "Uploading to TikTok...")

        result = upload_tiktok_video(
            access_token=credential.access_token,
            file_path=file_path,
            title=title,
            description=description,
            hashtags=hashtags,
            on_progress=upload_progress,
        )
        if on_progress:
            on_progress(1.0, "Published to TikTok")
        return result

    if platform == "instagram":
        from integrations.instagram_client import upload_reel

        if on_progress:
            on_progress(0.05, "Starting Instagram upload...")

        caption = " ".join(
            part for part in [title.strip(), description.strip(), " ".join(hashtags)] if part
        )

        def upload_progress(p: float) -> None:
            if on_progress:
                on_progress(0.05 + p * 0.9, "Publishing Instagram Reel...")

        result = upload_reel(
            access_token=credential.access_token,
            ig_user_id=credential.platform_user_id,
            file_path=file_path,
            caption=caption,
            on_progress=upload_progress,
        )
        if on_progress:
            on_progress(1.0, "Published to Instagram")
        return result

    raise RuntimeError(f"Unsupported platform: {platform}")
