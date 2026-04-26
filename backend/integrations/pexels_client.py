"""Thin wrapper around the Pexels API for stock photo search and download."""

import logging
import os
import tempfile

import httpx

logger = logging.getLogger(__name__)

PEXELS_BASE = "https://api.pexels.com/v1"


def _get_api_key() -> str:
    key = os.environ.get("PEXELS_API_KEY", "")
    if not key:
        raise RuntimeError("PEXELS_API_KEY not configured")
    return key


def search_photos(query: str, per_page: int = 5, orientation: str = "landscape") -> list[dict]:
    """Search Pexels for photos matching *query*. Returns raw photo objects."""
    headers = {"Authorization": _get_api_key()}
    params = {"query": query, "per_page": per_page, "orientation": orientation}
    resp = httpx.get(f"{PEXELS_BASE}/search", headers=headers, params=params, timeout=15.0)
    resp.raise_for_status()
    return resp.json().get("photos", [])


def download_photo(photo: dict, width: int = 1920) -> str:
    """Download a Pexels photo at the given width. Returns path to temp file."""
    url = photo["src"].get("landscape") or photo["src"].get("large2x") or photo["src"]["original"]
    if "?w=" not in url and "pexels.com" in url:
        url = f"{url}?w={width}&fit=crop"

    resp = httpx.get(url, timeout=30.0, follow_redirects=True)
    resp.raise_for_status()

    suffix = ".jpg"
    if "png" in resp.headers.get("content-type", ""):
        suffix = ".png"

    tmp = tempfile.NamedTemporaryFile(suffix=suffix, delete=False)
    tmp.write(resp.content)
    tmp.close()
    logger.info("Downloaded Pexels photo %s → %s (%d bytes)", photo.get("id"), tmp.name, len(resp.content))
    return tmp.name


def search_and_download(query: str, width: int = 1920) -> str | None:
    """Search for a photo and download the best result. Returns temp path or None."""
    photos = search_photos(query)
    if not photos:
        logger.warning("No Pexels results for query: %r", query)
        return None
    return download_photo(photos[0], width=width)
