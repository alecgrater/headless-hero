"""Thin wrapper around Twitch Helix API for game lookup and VOD discovery."""

import logging
import os
import time

import httpx

logger = logging.getLogger(__name__)

HELIX_BASE = "https://api.twitch.tv/helix"
TOKEN_URL = "https://id.twitch.tv/oauth2/token"

_app_token: str = ""
_token_expires: float = 0.0


def _get_credentials() -> tuple[str, str]:
    client_id = os.environ.get("TWITCH_CLIENT_ID", "")
    client_secret = os.environ.get("TWITCH_CLIENT_SECRET", "")
    if not client_id or not client_secret:
        raise RuntimeError("TWITCH_CLIENT_ID and TWITCH_CLIENT_SECRET not configured")
    return client_id, client_secret


def _ensure_token() -> tuple[str, str]:
    """Return (client_id, bearer_token), refreshing the app token if needed."""
    global _app_token, _token_expires

    client_id, client_secret = _get_credentials()

    if _app_token and time.monotonic() < _token_expires:
        return client_id, _app_token

    resp = httpx.post(TOKEN_URL, params={
        "client_id": client_id,
        "client_secret": client_secret,
        "grant_type": "client_credentials",
    }, timeout=10.0)
    resp.raise_for_status()
    data = resp.json()
    _app_token = data["access_token"]
    _token_expires = time.monotonic() + data.get("expires_in", 3600) - 60
    logger.info("Twitch app token refreshed, expires in %ds", data.get("expires_in", 0))
    return client_id, _app_token


def _helix_headers() -> dict[str, str]:
    client_id, token = _ensure_token()
    return {"Client-ID": client_id, "Authorization": f"Bearer {token}"}


def lookup_game(name: str) -> dict | None:
    """Look up a game by name. Returns the first matching game object or None."""
    resp = httpx.get(
        f"{HELIX_BASE}/games",
        headers=_helix_headers(),
        params={"name": name},
        timeout=10.0,
    )
    resp.raise_for_status()
    data = resp.json().get("data", [])
    if data:
        logger.info("Twitch game lookup: %r → id=%s", name, data[0]["id"])
        return data[0]
    logger.warning("Twitch game not found: %r", name)
    return None


def search_vods(game_id: str, max_results: int = 20, language: str = "en") -> list[dict]:
    """Search for VODs (past broadcasts) for a game. Returns video objects."""
    resp = httpx.get(
        f"{HELIX_BASE}/videos",
        headers=_helix_headers(),
        params={
            "game_id": game_id,
            "type": "archive",
            "first": max_results,
            "language": language,
            "sort": "views",
        },
        timeout=15.0,
    )
    resp.raise_for_status()
    vods = resp.json().get("data", [])
    logger.info("Found %d VODs for game_id=%s", len(vods), game_id)
    return vods


def search_clips(game_id: str, max_results: int = 20) -> list[dict]:
    """Search for popular clips of a game. Clips are short highlights guaranteed to be from the tagged game.

    Results are re-ranked to prefer clips whose title mentions the game,
    and to deprioritize test/automation accounts.
    """
    resp = httpx.get(
        f"{HELIX_BASE}/clips",
        headers=_helix_headers(),
        params={
            "game_id": game_id,
            "first": max_results,
        },
        timeout=15.0,
    )
    resp.raise_for_status()
    clips = resp.json().get("data", [])
    logger.info("Found %d clips for game_id=%s", len(clips), game_id)
    return clips


def filter_clips(clips: list[dict], game_name: str) -> list[dict]:
    """Re-rank clips to prefer ones that are clearly about the game.

    Filters out test/automation accounts and short meaningless titles,
    then sorts: title mentions game name first, then by view count.
    """
    skip_broadcasters = {"qa_vod_automation", "twitchdev", "test"}
    name_lower = game_name.lower()

    filtered = [
        c for c in clips
        if c.get("broadcaster_name", "").lower() not in skip_broadcasters
        and len(c.get("title", "")) > 3
    ]

    def _sort_key(c: dict) -> tuple[int, int]:
        title_has_game = 0 if name_lower in c.get("title", "").lower() else 1
        views = -(c.get("view_count", 0))
        return (title_has_game, views)

    filtered.sort(key=_sort_key)
    return filtered if filtered else clips
