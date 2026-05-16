"""Thin wrapper around Meta OAuth and Instagram Reels publishing."""

import logging
import os
import time
from pathlib import Path
from typing import Callable
from urllib.parse import urlencode

import httpx

from config import BACKEND_PORT

logger = logging.getLogger(__name__)

_API_VERSION = "v25.0"
_GRAPH_BASE = f"https://graph.facebook.com/{_API_VERSION}"
_DIALOG_URL = f"https://www.facebook.com/{_API_VERSION}/dialog/oauth"
_REDIRECT_URI_DEFAULT = f"http://localhost:{BACKEND_PORT}/api/publish/oauth/callback/instagram"


def _app_id() -> str:
    value = os.environ.get("META_APP_ID", "")
    if not value:
        raise RuntimeError("META_APP_ID must be set.")
    return value


def _app_secret() -> str:
    value = os.environ.get("META_APP_SECRET", "")
    if not value:
        raise RuntimeError("META_APP_SECRET must be set.")
    return value


def get_auth_url(redirect_uri: str = _REDIRECT_URI_DEFAULT, state: str = "") -> str:
    params = {
        "client_id": _app_id(),
        "redirect_uri": redirect_uri,
        "scope": "instagram_basic,instagram_content_publish,pages_show_list,pages_read_engagement,business_management",
        "response_type": "code",
        "state": state,
    }
    return f"{_DIALOG_URL}?{urlencode(params)}"


def exchange_code(code: str, redirect_uri: str = _REDIRECT_URI_DEFAULT) -> dict:
    response = httpx.get(
        f"{_GRAPH_BASE}/oauth/access_token",
        params={
            "client_id": _app_id(),
            "client_secret": _app_secret(),
            "redirect_uri": redirect_uri,
            "code": code,
        },
        timeout=30,
    )
    response.raise_for_status()
    short_lived = response.json()
    if "access_token" not in short_lived:
        raise RuntimeError(short_lived.get("error", {}).get("message", "Instagram OAuth failed"))

    long_response = httpx.get(
        f"{_GRAPH_BASE}/oauth/access_token",
        params={
            "grant_type": "fb_exchange_token",
            "client_id": _app_id(),
            "client_secret": _app_secret(),
            "fb_exchange_token": short_lived["access_token"],
        },
        timeout=30,
    )
    long_response.raise_for_status()
    data = long_response.json()
    return {
        "access_token": data.get("access_token", short_lived["access_token"]),
        "expires_in": data.get("expires_in"),
    }


def get_instagram_account_info(access_token: str) -> dict[str, str]:
    response = httpx.get(
        f"{_GRAPH_BASE}/me/accounts",
        params={
            "access_token": access_token,
            "fields": "name,instagram_business_account{id,username}",
            "limit": 50,
        },
        timeout=30,
    )
    response.raise_for_status()
    payload = response.json()
    for page in payload.get("data", []):
        ig = page.get("instagram_business_account")
        if ig and ig.get("id"):
            return {
                "ig_user_id": ig["id"],
                "username": ig.get("username") or page.get("name") or "Instagram",
            }
    raise RuntimeError("No Instagram professional account found for this Meta login")


def _raise_graph_error(payload: dict) -> None:
    if payload.get("error"):
        err = payload["error"]
        raise RuntimeError(err.get("message") or err.get("code") or "Instagram API error")


def upload_reel(
    access_token: str,
    ig_user_id: str,
    file_path: str,
    caption: str,
    on_progress: Callable[[float], None] | None = None,
) -> dict[str, str]:
    """Publish a local MP4 file as an Instagram Reel via resumable upload."""
    path = Path(file_path)
    file_size = path.stat().st_size

    create_response = httpx.post(
        f"{_GRAPH_BASE}/{ig_user_id}/media",
        params={
            "access_token": access_token,
            "media_type": "REELS",
            "upload_type": "resumable",
            "caption": caption[:2200],
            "share_to_feed": "true",
        },
        timeout=30,
    )
    create_response.raise_for_status()
    container = create_response.json()
    _raise_graph_error(container)
    container_id = container.get("id")
    upload_uri = container.get("uri")
    if not container_id or not upload_uri:
        raise RuntimeError("Instagram did not return a media container upload URI")

    with path.open("rb") as f:
        upload_response = httpx.post(
            upload_uri,
            headers={
                "Authorization": f"OAuth {access_token}",
                "offset": "0",
                "file_size": str(file_size),
            },
            content=f.read(),
            timeout=300,
        )
    upload_response.raise_for_status()
    if on_progress:
        on_progress(0.6)

    for attempt in range(20):
        status_response = httpx.get(
            f"{_GRAPH_BASE}/{container_id}",
            params={"access_token": access_token, "fields": "status_code,status"},
            timeout=30,
        )
        status_response.raise_for_status()
        status_payload = status_response.json()
        _raise_graph_error(status_payload)
        status_code = status_payload.get("status_code")
        if status_code == "FINISHED":
            break
        if status_code == "ERROR":
            raise RuntimeError(status_payload.get("status") or "Instagram media processing failed")
        if on_progress:
            on_progress(0.6 + min(attempt + 1, 19) / 20 * 0.25)
        time.sleep(3)
    else:
        raise RuntimeError("Instagram media processing timed out")

    publish_response = httpx.post(
        f"{_GRAPH_BASE}/{ig_user_id}/media_publish",
        params={"access_token": access_token, "creation_id": container_id},
        timeout=30,
    )
    publish_response.raise_for_status()
    published = publish_response.json()
    _raise_graph_error(published)
    media_id = published.get("id")
    if not media_id:
        raise RuntimeError("Instagram did not return a published media id")
    permalink = ""
    try:
        permalink_response = httpx.get(
            f"{_GRAPH_BASE}/{media_id}",
            params={"access_token": access_token, "fields": "permalink"},
            timeout=30,
        )
        permalink_response.raise_for_status()
        permalink = permalink_response.json().get("permalink", "")
    except Exception:
        logger.warning("Failed to fetch Instagram permalink for media %s", media_id, exc_info=True)
    if on_progress:
        on_progress(1.0)
    return {
        "id": media_id,
        "url": permalink,
    }
