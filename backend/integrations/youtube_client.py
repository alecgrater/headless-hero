"""Thin wrapper around Google OAuth2 and YouTube Data API v3 for video upload."""

import logging
import os
from typing import Callable

from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import Flow
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload

from config import BACKEND_PORT

logger = logging.getLogger(__name__)

_SCOPES = [
    "https://www.googleapis.com/auth/youtube.upload",
    "https://www.googleapis.com/auth/youtube.readonly",
]

_REDIRECT_URI_DEFAULT = f"http://localhost:{BACKEND_PORT}/api/publish/oauth/callback/youtube"
_TOKEN_URI = "https://oauth2.googleapis.com/token"
_UPLOAD_CHUNK_SIZE = 10 * 1024 * 1024  # 10 MB

def _get_client_config() -> dict[str, dict]:
    """Build client config dict from environment variables."""
    client_id = os.environ.get("GOOGLE_CLIENT_ID", "")
    client_secret = os.environ.get("GOOGLE_CLIENT_SECRET", "")
    if not client_id or not client_secret:
        raise RuntimeError(
            "GOOGLE_CLIENT_ID and GOOGLE_CLIENT_SECRET must be set."
        )
    return {
        "web": {
            "client_id": client_id,
            "client_secret": client_secret,
            "auth_uri": "https://accounts.google.com/o/oauth2/auth",
            "token_uri": _TOKEN_URI,
        }
    }

def get_auth_url(redirect_uri: str = _REDIRECT_URI_DEFAULT, state: str = "") -> str:
    """Generate the Google OAuth2 consent URL."""
    flow = Flow.from_client_config(_get_client_config(), scopes=_SCOPES)
    flow.redirect_uri = redirect_uri
    auth_url, _ = flow.authorization_url(
        access_type="offline",
        include_granted_scopes="true",
        prompt="consent",
        state=state,
    )
    return auth_url

def exchange_code(code: str, redirect_uri: str = _REDIRECT_URI_DEFAULT) -> dict:
    """Exchange authorization code for tokens.

    Returns dict with access_token, refresh_token, expiry.
    """
    flow = Flow.from_client_config(_get_client_config(), scopes=_SCOPES)
    flow.redirect_uri = redirect_uri
    flow.fetch_token(code=code)
    creds = flow.credentials
    return {
        "access_token": creds.token,
        "refresh_token": creds.refresh_token or "",
        "expiry": creds.expiry.isoformat() if creds.expiry else None,
    }

def refresh_access_token(refresh_token: str) -> dict:
    """Refresh an expired access token.

    Returns dict with access_token, expiry.
    """
    import google.auth.transport.requests

    config = _get_client_config()["web"]
    logger.info("Refreshing YouTube OAuth token")
    creds = Credentials(
        token=None,
        refresh_token=refresh_token,
        client_id=config["client_id"],
        client_secret=config["client_secret"],
        token_uri=_TOKEN_URI,
    )
    creds.refresh(google.auth.transport.requests.Request())
    return {
        "access_token": creds.token,
        "expiry": creds.expiry.isoformat() if creds.expiry else None,
    }

def get_channel_info(access_token: str) -> dict[str, str]:
    """Fetch the authenticated user's YouTube channel info.

    Returns dict with channel_id, channel_name.
    """
    creds = Credentials(token=access_token)
    logger.info("Fetching YouTube channel info")
    youtube = build("youtube", "v3", credentials=creds)
    response = youtube.channels().list(part="snippet", mine=True).execute()
    items = response.get("items", [])
    if not items:
        raise RuntimeError("No YouTube channel found for this account")
    channel = items[0]
    return {
        "channel_id": channel["id"],
        "channel_name": channel["snippet"]["title"],
    }

def upload_video(
    access_token: str,
    file_path: str,
    title: str,
    description: str = "",
    tags: list[str] | None = None,
    category_id: str = "27",  # Education
    privacy_status: str = "private",
    publish_at: str | None = None,
    on_progress: Callable[[float], None] | None = None,
) -> dict[str, str]:
    """Upload a video to YouTube.

    Args:
        publish_at: ISO 8601 datetime for scheduled publishing.
                    Requires privacy_status="private".

    Returns dict with id, url.
    """
    creds = Credentials(token=access_token)
    youtube = build("youtube", "v3", credentials=creds)

    body = {
        "snippet": {
            "title": title,
            "description": description,
            "tags": tags or [],
            "categoryId": category_id,
        },
        "status": {
            "privacyStatus": privacy_status,
            "selfDeclaredMadeForKids": False,
        },
    }

    if publish_at:
        body["status"]["privacyStatus"] = "private"
        body["status"]["publishAt"] = publish_at

    media = MediaFileUpload(file_path, chunksize=_UPLOAD_CHUNK_SIZE, resumable=True)
    request = youtube.videos().insert(part="snippet,status", body=body, media_body=media)

    response = None
    while response is None:
        status, response = request.next_chunk()
        if status and on_progress:
            on_progress(status.progress())

    video_id = response["id"]
    logger.info("Uploaded video: %s", video_id)
    return {
        "id": video_id,
        "url": f"https://www.youtube.com/watch?v={video_id}",
    }
