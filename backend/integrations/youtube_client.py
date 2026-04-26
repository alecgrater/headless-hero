"""Thin wrapper around Google OAuth2 and YouTube Data API v3 for video upload."""

import logging
import os
from datetime import timezone
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

_pending_code_verifiers: dict[str, str] = {}

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
    if flow.code_verifier and state:
        _pending_code_verifiers[state] = flow.code_verifier
    return auth_url

def exchange_code(code: str, redirect_uri: str = _REDIRECT_URI_DEFAULT, state: str = "") -> dict:
    """Exchange authorization code for tokens.

    Returns dict with access_token, refresh_token, expiry.
    """
    flow = Flow.from_client_config(_get_client_config(), scopes=_SCOPES)
    flow.redirect_uri = redirect_uri
    code_verifier = _pending_code_verifiers.pop(state, None) if state else None
    flow.fetch_token(code=code, code_verifier=code_verifier)
    creds = flow.credentials
    expiry = creds.expiry
    if expiry and expiry.tzinfo is None:
        expiry = expiry.replace(tzinfo=timezone.utc)
    return {
        "access_token": creds.token,
        "refresh_token": creds.refresh_token or "",
        "expiry": expiry.isoformat() if expiry else None,
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
    expiry = creds.expiry
    if expiry and expiry.tzinfo is None:
        expiry = expiry.replace(tzinfo=timezone.utc)
    return {
        "access_token": creds.token,
        "expiry": expiry.isoformat() if expiry else None,
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


def list_channel_uploads(access_token: str, max_results: int = 50) -> list[dict[str, str]]:
    """Fetch recent uploads from the authenticated user's channel.

    Returns list of dicts with id, title, url.
    """
    creds = Credentials(token=access_token)
    youtube = build("youtube", "v3", credentials=creds)

    ch_resp = youtube.channels().list(part="contentDetails", mine=True).execute()
    ch_items = ch_resp.get("items", [])
    if not ch_items:
        return []
    uploads_playlist = ch_items[0]["contentDetails"]["relatedPlaylists"]["uploads"]

    videos: list[dict[str, str]] = []
    page_token: str | None = None
    while len(videos) < max_results:
        resp = youtube.playlistItems().list(
            part="snippet",
            playlistId=uploads_playlist,
            maxResults=min(50, max_results - len(videos)),
            pageToken=page_token,
        ).execute()
        for item in resp.get("items", []):
            vid_id = item["snippet"]["resourceId"]["videoId"]
            videos.append({
                "id": vid_id,
                "title": item["snippet"]["title"],
                "url": f"https://www.youtube.com/watch?v={vid_id}",
            })
        page_token = resp.get("nextPageToken")
        if not page_token:
            break

    return videos

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

    clean_tags: list[str] = []
    total_len = 0
    for t in (tags or []):
        t = t.replace("<", "").replace(">", "").lstrip("#").strip()[:100]
        if not t:
            continue
        sep = 2 if clean_tags else 0
        if total_len + sep + len(t) > 500:
            break
        clean_tags.append(t)
        total_len += sep + len(t)
    if tags and len(clean_tags) != len(tags):
        logger.info("Trimmed tags from %d to %d (%d chars) to fit YouTube limits", len(tags), len(clean_tags), total_len)

    body = {
        "snippet": {
            "title": title,
            "description": description,
            "tags": clean_tags,
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


def set_thumbnail(access_token: str, video_id: str, image_path: str) -> None:
    """Upload a custom thumbnail for a YouTube video.

    Requires the channel to be verified for custom thumbnails.
    Fails gracefully if not permitted.
    """
    creds = Credentials(token=access_token)
    youtube = build("youtube", "v3", credentials=creds)
    media = MediaFileUpload(image_path, mimetype="image/png", resumable=False)
    try:
        youtube.thumbnails().set(videoId=video_id, media_body=media).execute()
        logger.info("Set custom thumbnail for video %s", video_id)
    except Exception as exc:
        logger.warning("Failed to set thumbnail for video %s: %s", video_id, exc)
