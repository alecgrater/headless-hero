"""GitHub contents API helper for discovery seed uploads."""

from __future__ import annotations

import base64
import json
from typing import Any

import httpx

OWNER = "alecgrater"
REPO = "headless-hero"
BRANCH = "main"
API_BASE = "https://api.github.com"


class GitHubContentsError(RuntimeError):
    """Raised when GitHub rejects a contents API operation."""


def _headers(token: str) -> dict[str, str]:
    return {
        "Accept": "application/vnd.github+json",
        "Authorization": f"Bearer {token}",
        "X-GitHub-Api-Version": "2022-11-28",
    }


def _url(path: str) -> str:
    return f"{API_BASE}/repos/{OWNER}/{REPO}/contents/{path}"


def _get_sha(client: httpx.Client, token: str, path: str) -> str | None:
    response = client.get(_url(path), headers=_headers(token), params={"ref": BRANCH})
    if response.status_code == 404:
        return None
    if response.status_code >= 400:
        raise GitHubContentsError(
            f"GitHub contents API failed ({response.status_code}): {response.text}"
        )
    payload = response.json()
    sha = payload.get("sha")
    return sha if isinstance(sha, str) else None


def _put_file(
    client: httpx.Client,
    token: str,
    path: str,
    content: dict[str, Any],
    message: str,
    sha: str | None,
) -> httpx.Response:
    raw = json.dumps(content, indent=2, sort_keys=True) + "\n"
    body: dict[str, Any] = {
        "message": message,
        "content": base64.b64encode(raw.encode("utf-8")).decode("ascii"),
        "branch": BRANCH,
    }
    if sha:
        body["sha"] = sha
    return client.put(_url(path), headers=_headers(token), json=body)


def upload_json_file(
    *,
    token: str,
    path: str,
    content: dict[str, Any],
    message: str,
    client: httpx.Client | None = None,
) -> dict[str, Any]:
    """Create or update a JSON file in the hard-coded GitHub repository."""
    owns_client = client is None
    http_client = client or httpx.Client(timeout=30)
    try:
        sha = _get_sha(http_client, token, path)
        created = sha is None
        response = _put_file(http_client, token, path, content, message, sha)
        if response.status_code == 409:
            sha = _get_sha(http_client, token, path)
            response = _put_file(http_client, token, path, content, message, sha)
            created = False
        if response.status_code >= 400:
            raise GitHubContentsError(
                f"GitHub contents API failed ({response.status_code}): {response.text}"
            )
        payload = response.json()
        return {
            "content_sha": payload.get("content", {}).get("sha", ""),
            "commit_sha": payload.get("commit", {}).get("sha", ""),
            "created": created,
        }
    finally:
        if owns_client:
            http_client.close()
