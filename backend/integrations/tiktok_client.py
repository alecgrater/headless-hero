"""Thin wrapper around TikTok Login Kit and Content Posting API."""

import logging
import math
import os
import time
from pathlib import Path
from typing import Callable
from urllib.parse import urlencode

import httpx

from config import BACKEND_PORT

logger = logging.getLogger(__name__)

_AUTH_URL = "https://www.tiktok.com/v2/auth/authorize/"
_TOKEN_URL = "https://open.tiktokapis.com/v2/oauth/token/"
_USER_INFO_URL = "https://open.tiktokapis.com/v2/user/info/"
_CREATOR_INFO_URL = "https://open.tiktokapis.com/v2/post/publish/creator_info/query/"
_INIT_UPLOAD_URL = "https://open.tiktokapis.com/v2/post/publish/video/init/"
_STATUS_URL = "https://open.tiktokapis.com/v2/post/publish/status/fetch/"
_REDIRECT_URI_DEFAULT = f"http://localhost:{BACKEND_PORT}/api/publish/oauth/callback/tiktok"
_CHUNK_SIZE = 10 * 1024 * 1024
_PUBLISH_POLL_INTERVAL_SECONDS = 5
_PUBLISH_POLL_TIMEOUT_SECONDS = 180
_SUCCESS_STATUS_PARTS = ("COMPLETE", "PUBLISHED", "SEND", "SENT")
_FAILURE_STATUS_PARTS = ("FAIL", "ERROR", "REJECT")


def _client_key() -> str:
    value = os.environ.get("TIKTOK_CLIENT_KEY", "")
    if not value:
        raise RuntimeError("TIKTOK_CLIENT_KEY must be set.")
    return value


def _client_secret() -> str:
    value = os.environ.get("TIKTOK_CLIENT_SECRET", "")
    if not value:
        raise RuntimeError("TIKTOK_CLIENT_SECRET must be set.")
    return value


def get_auth_url(redirect_uri: str = _REDIRECT_URI_DEFAULT, state: str = "") -> str:
    params = {
        "client_key": _client_key(),
        "scope": "user.info.basic,video.publish",
        "response_type": "code",
        "redirect_uri": redirect_uri,
        "state": state,
    }
    return f"{_AUTH_URL}?{urlencode(params)}"


def exchange_code(code: str, redirect_uri: str = _REDIRECT_URI_DEFAULT) -> dict:
    response = httpx.post(
        _TOKEN_URL,
        data={
            "client_key": _client_key(),
            "client_secret": _client_secret(),
            "code": code,
            "grant_type": "authorization_code",
            "redirect_uri": redirect_uri,
        },
        timeout=30,
    )
    response.raise_for_status()
    data = response.json()
    if data.get("error"):
        raise RuntimeError(data.get("error_description") or data["error"])
    return {
        "access_token": data.get("access_token", ""),
        "refresh_token": data.get("refresh_token", ""),
        "expires_in": data.get("expires_in"),
        "open_id": data.get("open_id", ""),
        "scope": data.get("scope", ""),
    }


def refresh_access_token(refresh_token: str) -> dict:
    response = httpx.post(
        _TOKEN_URL,
        data={
            "client_key": _client_key(),
            "client_secret": _client_secret(),
            "grant_type": "refresh_token",
            "refresh_token": refresh_token,
        },
        timeout=30,
    )
    response.raise_for_status()
    data = response.json()
    if data.get("error"):
        raise RuntimeError(data.get("error_description") or data["error"])
    return {
        "access_token": data.get("access_token", ""),
        "refresh_token": data.get("refresh_token", refresh_token),
        "expires_in": data.get("expires_in"),
    }


def get_user_info(access_token: str) -> dict[str, str]:
    response = httpx.get(
        _USER_INFO_URL,
        params={"fields": "open_id,display_name,avatar_url"},
        headers={"Authorization": f"Bearer {access_token}"},
        timeout=30,
    )
    response.raise_for_status()
    payload = response.json()
    if payload.get("error", {}).get("code") not in (None, "ok"):
        raise RuntimeError(payload["error"].get("message") or payload["error"].get("code"))
    user = payload.get("data", {}).get("user", {})
    return {
        "open_id": user.get("open_id", ""),
        "display_name": user.get("display_name", "") or "TikTok",
    }


def get_creator_info(access_token: str) -> dict:
    response = httpx.post(
        _CREATOR_INFO_URL,
        headers={"Authorization": f"Bearer {access_token}", "Content-Type": "application/json; charset=UTF-8"},
        json={},
        timeout=30,
    )
    response.raise_for_status()
    payload = response.json()
    if payload.get("error", {}).get("code") not in (None, "ok"):
        raise RuntimeError(payload["error"].get("message") or payload["error"].get("code"))
    return payload.get("data", {})


def _pick_privacy_level(creator_info: dict) -> str:
    options = creator_info.get("privacy_level_options") or []
    for preferred in ("PUBLIC_TO_EVERYONE", "MUTUAL_FOLLOW_FRIENDS", "FOLLOWER_OF_CREATOR", "SELF_ONLY"):
        if preferred in options:
            return preferred
    return options[0] if options else "SELF_ONLY"


def upload_video(
    access_token: str,
    file_path: str,
    title: str,
    description: str = "",
    hashtags: list[str] | None = None,
    on_progress: Callable[[float], None] | None = None,
) -> dict[str, str]:
    """Direct-post a video to TikTok using FILE_UPLOAD."""
    path = Path(file_path)
    file_size = path.stat().st_size
    chunk_size = min(_CHUNK_SIZE, file_size)
    total_chunk_count = max(1, math.ceil(file_size / chunk_size))

    creator_info = get_creator_info(access_token)
    privacy_level = _pick_privacy_level(creator_info)
    caption = " ".join(
        part for part in [title.strip(), description.strip(), " ".join(hashtags or [])] if part
    )[:2200]

    response = httpx.post(
        _INIT_UPLOAD_URL,
        headers={"Authorization": f"Bearer {access_token}", "Content-Type": "application/json; charset=UTF-8"},
        json={
            "post_info": {
                "title": caption,
                "privacy_level": privacy_level,
                "disable_duet": False,
                "disable_comment": False,
                "disable_stitch": False,
            },
            "source_info": {
                "source": "FILE_UPLOAD",
                "video_size": file_size,
                "chunk_size": chunk_size,
                "total_chunk_count": total_chunk_count,
            },
        },
        timeout=30,
    )
    response.raise_for_status()
    payload = response.json()
    if payload.get("error", {}).get("code") not in (None, "ok"):
        raise RuntimeError(payload["error"].get("message") or payload["error"].get("code"))

    data = payload.get("data", {})
    upload_url = data.get("upload_url")
    publish_id = data.get("publish_id", "")
    if not upload_url:
        raise RuntimeError("TikTok did not return an upload URL")

    with path.open("rb") as f:
        for chunk_idx in range(total_chunk_count):
            first = chunk_idx * chunk_size
            f.seek(first)
            chunk = f.read(chunk_size)
            last = first + len(chunk) - 1
            upload_response = httpx.put(
                upload_url,
                headers={
                    "Content-Type": "video/mp4",
                    "Content-Length": str(len(chunk)),
                    "Content-Range": f"bytes {first}-{last}/{file_size}",
                },
                content=chunk,
                timeout=120,
            )
            upload_response.raise_for_status()
            if on_progress:
                on_progress(((chunk_idx + 1) / total_chunk_count) * 0.75)

    if on_progress:
        on_progress(0.8)

    status = wait_for_publish_complete(access_token, publish_id, on_progress=on_progress)

    return {
        "id": status.get("publicaly_available_post_id", "") or publish_id,
        "url": status.get("share_url", "") or "https://www.tiktok.com/",
    }


def fetch_publish_status(access_token: str, publish_id: str) -> dict:
    response = httpx.post(
        _STATUS_URL,
        headers={"Authorization": f"Bearer {access_token}", "Content-Type": "application/json; charset=UTF-8"},
        json={"publish_id": publish_id},
        timeout=30,
    )
    response.raise_for_status()
    payload = response.json()
    if payload.get("error", {}).get("code") not in (None, "ok"):
        raise RuntimeError(payload["error"].get("message") or payload["error"].get("code"))
    return payload.get("data", {})


def _status_text(status: dict) -> str:
    return str(status.get("status") or status.get("publish_status") or "").upper()


def wait_for_publish_complete(
    access_token: str,
    publish_id: str,
    on_progress: Callable[[float], None] | None = None,
) -> dict:
    """Poll TikTok until processing reaches a terminal success or failure."""
    deadline = time.monotonic() + _PUBLISH_POLL_TIMEOUT_SECONDS
    last_status: dict = {}
    while time.monotonic() < deadline:
        last_status = fetch_publish_status(access_token, publish_id)
        status_text = _status_text(last_status)
        if any(part in status_text for part in _SUCCESS_STATUS_PARTS):
            if on_progress:
                on_progress(1.0)
            return last_status
        if any(part in status_text for part in _FAILURE_STATUS_PARTS):
            error_message = last_status.get("fail_reason") or last_status.get("message") or status_text
            raise RuntimeError(f"TikTok publish failed: {error_message}")
        if on_progress:
            on_progress(0.85)
        time.sleep(_PUBLISH_POLL_INTERVAL_SECONDS)

    status_text = _status_text(last_status) or "unknown"
    raise RuntimeError(f"TikTok publish did not complete before timeout (last status: {status_text})")
