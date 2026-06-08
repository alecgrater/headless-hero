# GitHub Actions Whitespace Discovery Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a profile-seeded GitHub Actions whitespace discovery feed and surface it in a new Discover tab.

**Architecture:** The desktop app remains the source of truth for the local content profile, but uploads only a sanitized seed JSON to GitHub after profile refresh. GitHub Actions reads that seed, runs a YouTube Data API analyzer, commits a static feed JSON into `frontend/public/discovery`, and the frontend renders that cached feed in a new Whitespace tab.

**Tech Stack:** Python 3.12/FastAPI/SQLModel/uv backend, GitHub REST contents API via `httpx`, GitHub Actions, YouTube Data API v3 via `google-api-python-client`, React 19/Vite/TypeScript/Tailwind 4 frontend, Vitest and pytest.

---

## File Structure

- Create `backend/pipeline/discovery_seed.py`: deterministic sanitized seed builder from `ContentProfileRead`-shaped dictionaries.
- Create `backend/integrations/github_contents.py`: focused GitHub contents API client for one file update.
- Modify `backend/api/settings.py`: allow `GITHUB_CONTENTS_TOKEN` through existing API key UI/storage.
- Modify `backend/api/trending.py`: include upload status in content profile refresh response and invoke seed upload after successful local profile refresh.
- Create `backend/tests/test_discovery_seed.py`: unit tests for sanitized output and search query generation.
- Create `backend/tests/test_github_contents.py`: mocked HTTP tests for create, update, retry, and failure.
- Modify `backend/tests/test_content_profile.py` or add `backend/tests/test_content_profile_seed_upload.py`: API-level tests for missing token and upload warning behavior.
- Create `scripts/youtube_whitespace.py`: Actions-safe analyzer that reads the seed and writes the static feed.
- Create `tests/test_youtube_whitespace.py` only if the repo has top-level test wiring; otherwise create `backend/tests/test_youtube_whitespace.py` and import the script by path.
- Create `.github/workflows/youtube-whitespace.yml`: scheduled/path-triggered Action.
- Create `frontend/public/discovery/youtube-whitespace.json`: initial empty feed.
- Modify `frontend/src/types/trending.ts`: add whitespace feed/result types.
- Create `frontend/src/components/trending/WhitespaceTab.tsx`: read-only feed UI.
- Modify `frontend/src/components/trending/DiscoverPage.tsx`: add Whitespace tab.
- Modify `frontend/src/components/settings/ApiKeysSection.tsx`: add GitHub Contents Token under Discovery.
- Add/update frontend tests for API key visibility and Whitespace tab states.
- Update `AGENTS.md`: record the new convention that remote discovery uses sanitized seed JSON and must not commit SQLite/local data.

---

### Task 1: Add Sanitized Discovery Seed Builder

**Files:**
- Create: `backend/pipeline/discovery_seed.py`
- Test: `backend/tests/test_discovery_seed.py`

- [ ] **Step 1: Write failing seed builder tests**

Create `backend/tests/test_discovery_seed.py`:

```python
from datetime import datetime, timezone

from pipeline.discovery_seed import build_discovery_seed


def test_build_discovery_seed_sanitizes_profile_and_queries():
    profile = {
        "script_count": 4,
        "common_topics": ["Science Myths", "Ancient Engineering", ""],
        "typical_keywords": ["Psychology", "science", "AI", "the"],
        "audience_profile": "Curious adults who like vivid explainers.",
        "narration_style": "Fast, direct, second-person narration with punchy turns.",
        "visual_approach": "High-contrast metaphors and comparison boards.",
        "avg_segment_count": 7.5,
        "analyzed_at": "2026-05-29T10:00:00+00:00",
        "is_stale": False,
        "local_path": "~/secret",
        "script_bodies": ["do not leak"],
    }

    seed = build_discovery_seed(
        profile,
        now=datetime(2026, 5, 29, 17, 0, tzinfo=timezone.utc),
    )

    assert seed["version"] == 1
    assert seed["generated_at"] == "2026-05-29T17:00:00Z"
    assert seed["source"] == "headless-hero-content-profile"
    assert seed["profile"] == {
        "script_count": 4,
        "common_topics": ["Science Myths", "Ancient Engineering"],
        "typical_keywords": ["Psychology", "science", "AI"],
        "audience_profile": "Curious adults who like vivid explainers.",
        "narration_style": "Fast, direct, second-person narration with punchy turns.",
        "visual_approach": "High-contrast metaphors and comparison boards.",
        "avg_segment_count": 7.5,
    }
    assert "local_path" not in seed["profile"]
    assert "script_bodies" not in seed["profile"]
    assert len(seed["search_queries"]) >= 6
    assert len(seed["search_queries"]) <= 40
    assert "Science Myths explained" in seed["search_queries"]
    assert "Ancient Engineering documentary" in seed["search_queries"]
    assert len(seed["search_queries"]) == len(set(seed["search_queries"]))


def test_build_discovery_seed_limits_long_text_and_query_count():
    profile = {
        "script_count": 1,
        "common_topics": [f"Topic {i}" for i in range(80)],
        "typical_keywords": [f"keyword{i}" for i in range(80)],
        "audience_profile": "A" * 2000,
        "narration_style": "B" * 2000,
        "visual_approach": "C" * 2000,
        "avg_segment_count": 6,
    }

    seed = build_discovery_seed(
        profile,
        now=datetime(2026, 5, 29, 17, 0, tzinfo=timezone.utc),
    )

    assert len(seed["profile"]["audience_profile"]) == 500
    assert len(seed["profile"]["narration_style"]) == 500
    assert len(seed["profile"]["visual_approach"]) == 500
    assert len(seed["search_queries"]) == 40
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run --project backend pytest backend/tests/test_discovery_seed.py -v`

Expected: FAIL with `ModuleNotFoundError: No module named 'pipeline.discovery_seed'`.

- [ ] **Step 3: Implement seed builder**

Create `backend/pipeline/discovery_seed.py`:

```python
"""Sanitized discovery seed generation for remote whitespace analysis."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

MAX_LIST_ITEMS = 50
MAX_TEXT_CHARS = 500
MAX_SEARCH_QUERIES = 40

_QUERY_SUFFIXES = (
    "explained",
    "documentary",
    "facts explained",
    "story",
)

_WEAK_KEYWORDS = {
    "the",
    "and",
    "for",
    "with",
    "from",
    "that",
    "this",
    "you",
    "your",
}


def _utc_iso(dt: datetime) -> str:
    value = dt.astimezone(timezone.utc)
    return value.replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _clean_text(value: Any, limit: int = MAX_TEXT_CHARS) -> str:
    if not isinstance(value, str):
        return ""
    return " ".join(value.split())[:limit]


def _clean_list(value: Any) -> list[str]:
    if not isinstance(value, list):
        return []
    cleaned: list[str] = []
    seen: set[str] = set()
    for item in value:
        text = _clean_text(item, 120)
        if not text:
            continue
        key = text.casefold()
        if key in seen:
            continue
        seen.add(key)
        cleaned.append(text)
        if len(cleaned) >= MAX_LIST_ITEMS:
            break
    return cleaned


def build_search_queries(common_topics: list[str], typical_keywords: list[str]) -> list[str]:
    """Build deterministic YouTube search phrases from sanitized profile terms."""
    queries: list[str] = []
    seen: set[str] = set()

    def add(query: str) -> None:
        text = " ".join(query.split())
        if not text:
            return
        key = text.casefold()
        if key in seen:
            return
        seen.add(key)
        queries.append(text)

    for topic in common_topics:
        for suffix in _QUERY_SUFFIXES:
            add(f"{topic} {suffix}")

    strong_keywords = [
        keyword
        for keyword in typical_keywords
        if keyword.casefold() not in _WEAK_KEYWORDS and len(keyword) > 2
    ]
    for keyword in strong_keywords:
        add(f"{keyword} explained")
        add(f"{keyword} documentary")

    for topic in common_topics[:10]:
        for keyword in strong_keywords[:10]:
            if keyword.casefold() in topic.casefold():
                continue
            add(f"{topic} {keyword}")

    return queries[:MAX_SEARCH_QUERIES]


def build_discovery_seed(profile: dict[str, Any], now: datetime | None = None) -> dict[str, Any]:
    """Return the public, checked-in seed used by GitHub Actions discovery."""
    generated_at = now or datetime.now(timezone.utc)
    common_topics = _clean_list(profile.get("common_topics"))
    typical_keywords = _clean_list(profile.get("typical_keywords"))
    avg_segment_count = profile.get("avg_segment_count", 0)
    try:
        avg_segment_count = float(avg_segment_count)
    except (TypeError, ValueError):
        avg_segment_count = 0.0

    safe_profile = {
        "script_count": int(profile.get("script_count") or 0),
        "common_topics": common_topics,
        "typical_keywords": typical_keywords,
        "audience_profile": _clean_text(profile.get("audience_profile")),
        "narration_style": _clean_text(profile.get("narration_style")),
        "visual_approach": _clean_text(profile.get("visual_approach")),
        "avg_segment_count": avg_segment_count,
    }

    return {
        "version": 1,
        "generated_at": _utc_iso(generated_at),
        "source": "headless-hero-content-profile",
        "profile": safe_profile,
        "search_queries": build_search_queries(common_topics, typical_keywords),
    }
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run --project backend pytest backend/tests/test_discovery_seed.py -v`

Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add backend/pipeline/discovery_seed.py backend/tests/test_discovery_seed.py
git commit -m "Add sanitized discovery seed builder"
```

---

### Task 2: Add GitHub Contents Upload Integration

**Files:**
- Create: `backend/integrations/github_contents.py`
- Test: `backend/tests/test_github_contents.py`

- [ ] **Step 1: Write failing GitHub upload tests**

Create `backend/tests/test_github_contents.py`:

```python
import base64

import httpx
import pytest

from integrations.github_contents import GitHubContentsError, upload_json_file


class MockTransport:
    def __init__(self, responses):
        self.responses = list(responses)
        self.requests = []

    def __call__(self, request: httpx.Request) -> httpx.Response:
        self.requests.append(request)
        status, payload = self.responses.pop(0)
        return httpx.Response(status, json=payload, request=request)


def test_upload_json_file_updates_existing_file():
    transport = MockTransport([
        (200, {"sha": "old-sha"}),
        (200, {"content": {"sha": "new-sha"}, "commit": {"sha": "commit-sha"}}),
    ])

    result = upload_json_file(
        token="ghp_test",
        path="discovery/content-profile-seed.json",
        content={"version": 1},
        message="Update discovery content profile seed",
        client=httpx.Client(transport=httpx.MockTransport(transport)),
    )

    assert result == {"content_sha": "new-sha", "commit_sha": "commit-sha", "created": False}
    assert transport.requests[0].method == "GET"
    assert transport.requests[1].method == "PUT"
    body = transport.requests[1].read().decode()
    assert '"sha":"old-sha"' in body
    encoded = body.split('"content":"', 1)[1].split('"', 1)[0]
    assert base64.b64decode(encoded).decode().endswith("\n")


def test_upload_json_file_creates_missing_file():
    transport = MockTransport([
        (404, {"message": "Not Found"}),
        (201, {"content": {"sha": "created-sha"}, "commit": {"sha": "commit-sha"}}),
    ])

    result = upload_json_file(
        token="ghp_test",
        path="discovery/content-profile-seed.json",
        content={"version": 1},
        message="Update discovery content profile seed",
        client=httpx.Client(transport=httpx.MockTransport(transport)),
    )

    assert result["created"] is True
    assert '"sha"' not in transport.requests[1].read().decode()


def test_upload_json_file_retries_once_on_conflict():
    transport = MockTransport([
        (200, {"sha": "old-sha"}),
        (409, {"message": "conflict"}),
        (200, {"sha": "fresh-sha"}),
        (200, {"content": {"sha": "new-sha"}, "commit": {"sha": "commit-sha"}}),
    ])

    result = upload_json_file(
        token="ghp_test",
        path="discovery/content-profile-seed.json",
        content={"version": 1},
        message="Update discovery content profile seed",
        client=httpx.Client(transport=httpx.MockTransport(transport)),
    )

    assert result["content_sha"] == "new-sha"
    assert len(transport.requests) == 4


def test_upload_json_file_raises_clear_error_on_auth_failure():
    transport = MockTransport([(403, {"message": "Resource not accessible by personal access token"})])

    with pytest.raises(GitHubContentsError, match="GitHub contents API failed"):
        upload_json_file(
            token="bad",
            path="discovery/content-profile-seed.json",
            content={"version": 1},
            message="Update discovery content profile seed",
            client=httpx.Client(transport=httpx.MockTransport(transport)),
        )
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run --project backend pytest backend/tests/test_github_contents.py -v`

Expected: FAIL with `ModuleNotFoundError: No module named 'integrations.github_contents'`.

- [ ] **Step 3: Implement GitHub contents client**

Create `backend/integrations/github_contents.py`:

```python
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
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run --project backend pytest backend/tests/test_github_contents.py -v`

Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add backend/integrations/github_contents.py backend/tests/test_github_contents.py
git commit -m "Add GitHub contents upload helper"
```

---

### Task 3: Wire Profile Refresh To Seed Upload

**Files:**
- Modify: `backend/api/settings.py`
- Modify: `backend/api/trending.py`
- Test: `backend/tests/test_content_profile_seed_upload.py`

- [ ] **Step 1: Write failing API behavior tests**

Create `backend/tests/test_content_profile_seed_upload.py`:

```python
from fastapi.testclient import TestClient


def test_refresh_content_profile_skips_seed_upload_without_token(monkeypatch):
    from api.main import app
    import api.trending as trending_api

    monkeypatch.setattr(
        "pipeline.content_profile.analyze_content_profile",
        lambda: {
            "script_count": 3,
            "common_topics": ["Science Myths"],
            "typical_keywords": ["biology"],
            "audience_profile": "Curious adults.",
            "narration_style": "Direct.",
            "visual_approach": "Metaphors.",
            "avg_segment_count": 8,
            "analyzed_at": "2026-05-29T10:00:00+00:00",
            "is_stale": False,
        },
    )
    monkeypatch.setattr(trending_api, "_get_setting_or_env", lambda key: "")

    res = TestClient(app).post("/api/trending/content-profile/refresh")

    assert res.status_code == 200
    data = res.json()
    assert data["script_count"] == 3
    assert data["seed_upload"]["status"] == "skipped"
    assert "GitHub Contents Token" in data["seed_upload"]["message"]


def test_refresh_content_profile_returns_seed_upload_warning(monkeypatch):
    from api.main import app
    import api.trending as trending_api

    monkeypatch.setattr(
        "pipeline.content_profile.analyze_content_profile",
        lambda: {
            "script_count": 3,
            "common_topics": ["Science Myths"],
            "typical_keywords": ["biology"],
            "audience_profile": "Curious adults.",
            "narration_style": "Direct.",
            "visual_approach": "Metaphors.",
            "avg_segment_count": 8,
            "analyzed_at": "2026-05-29T10:00:00+00:00",
            "is_stale": False,
        },
    )
    monkeypatch.setattr(trending_api, "_get_setting_or_env", lambda key: "ghp_token")

    def fail_upload(*args, **kwargs):
        raise RuntimeError("GitHub rejected token")

    monkeypatch.setattr(trending_api, "upload_json_file", fail_upload)

    res = TestClient(app).post("/api/trending/content-profile/refresh")

    assert res.status_code == 200
    data = res.json()
    assert data["seed_upload"]["status"] == "warning"
    assert "GitHub rejected token" in data["seed_upload"]["message"]


def test_refresh_content_profile_uploads_seed_when_token_exists(monkeypatch):
    from api.main import app
    import api.trending as trending_api

    captured = {}
    monkeypatch.setattr(
        "pipeline.content_profile.analyze_content_profile",
        lambda: {
            "script_count": 3,
            "common_topics": ["Science Myths"],
            "typical_keywords": ["biology"],
            "audience_profile": "Curious adults.",
            "narration_style": "Direct.",
            "visual_approach": "Metaphors.",
            "avg_segment_count": 8,
            "analyzed_at": "2026-05-29T10:00:00+00:00",
            "is_stale": False,
        },
    )
    monkeypatch.setattr(trending_api, "_get_setting_or_env", lambda key: "ghp_token")

    def fake_upload(**kwargs):
        captured.update(kwargs)
        return {"content_sha": "seed-sha", "commit_sha": "commit-sha", "created": False}

    monkeypatch.setattr(trending_api, "upload_json_file", fake_upload)

    res = TestClient(app).post("/api/trending/content-profile/refresh")

    assert res.status_code == 200
    data = res.json()
    assert data["seed_upload"] == {
        "status": "uploaded",
        "message": "Discovery seed uploaded; GitHub Actions will refresh whitespace results.",
        "commit_sha": "commit-sha",
    }
    assert captured["token"] == "ghp_token"
    assert captured["path"] == "discovery/content-profile-seed.json"
    assert captured["message"] == "Update discovery content profile seed"
    assert captured["content"]["profile"]["common_topics"] == ["Science Myths"]
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run --project backend pytest backend/tests/test_content_profile_seed_upload.py -v`

Expected: FAIL because `seed_upload` is not in the response and imports are missing.

- [ ] **Step 3: Allow GitHub token in settings**

In `backend/api/settings.py`, add `"GITHUB_CONTENTS_TOKEN"` to `ALLOWED_KEYS` near the other Discovery keys. Do not add it to `_PLAINTEXT_KEYS`.

```python
    "YOUTUBE_API_KEY",
    "NEWS_API_KEY",
    "GITHUB_CONTENTS_TOKEN",
```

- [ ] **Step 4: Extend content profile response and upload helper**

In `backend/api/trending.py`, add imports:

```python
import os

from models.settings import AppSetting
from pipeline.discovery_seed import build_discovery_seed
from integrations.github_contents import upload_json_file
```

Add response models below `ContentProfileRead`:

```python
class SeedUploadStatus(BaseModel):
    status: str
    message: str
    commit_sha: str | None = None


class ContentProfileRefreshResponse(ContentProfileRead):
    seed_upload: SeedUploadStatus
```

Add helper functions:

```python
def _get_setting_or_env(key: str) -> str:
    with Session(engine) as session:
        setting = session.get(AppSetting, key)
        if setting and setting.value:
            return setting.value
    return os.environ.get(key, "")


def _upload_discovery_seed(profile: dict) -> SeedUploadStatus:
    token = _get_setting_or_env("GITHUB_CONTENTS_TOKEN").strip()
    if not token:
        return SeedUploadStatus(
            status="skipped",
            message="GitHub Contents Token is not configured, so remote whitespace refresh was not triggered.",
        )
    seed = build_discovery_seed(profile)
    try:
        result = upload_json_file(
            token=token,
            path="discovery/content-profile-seed.json",
            content=seed,
            message="Update discovery content profile seed",
        )
    except Exception as exc:
        logger.warning("Discovery seed upload failed", exc_info=True)
        return SeedUploadStatus(status="warning", message=str(exc))
    logger.info("Discovery seed uploaded to GitHub commit %s", result.get("commit_sha"))
    return SeedUploadStatus(
        status="uploaded",
        message="Discovery seed uploaded; GitHub Actions will refresh whitespace results.",
        commit_sha=result.get("commit_sha") or None,
    )
```

Change the endpoint decorator and body:

```python
@router.post("/content-profile/refresh", response_model=ContentProfileRefreshResponse)
async def refresh_content_profile():
    """Force-regenerate content profile and upload a sanitized discovery seed when configured."""
    from pipeline.content_profile import analyze_content_profile
    profile = analyze_content_profile()
    if not profile:
        raise HTTPException(status_code=422, detail="No scripts found to analyze")
    upload_status = _upload_discovery_seed(profile)
    return ContentProfileRefreshResponse(**profile, seed_upload=upload_status)
```

If `engine` is not already imported in this file, change `from database import get_session, get_default_brand_id` to:

```python
from database import engine, get_session, get_default_brand_id
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `uv run --project backend pytest backend/tests/test_content_profile_seed_upload.py backend/tests/test_content_profile.py -v`

Expected: PASS.

- [ ] **Step 6: Commit**

```bash
git add backend/api/settings.py backend/api/trending.py backend/tests/test_content_profile_seed_upload.py
git commit -m "Upload discovery seed after profile refresh"
```

---

### Task 4: Add GitHub Actions YouTube Whitespace Analyzer

**Files:**
- Create: `scripts/youtube_whitespace.py`
- Create: `backend/tests/test_youtube_whitespace.py`
- Create: `.github/workflows/youtube-whitespace.yml`
- Create: `discovery/content-profile-seed.json`
- Create: `frontend/public/discovery/youtube-whitespace.json`

- [ ] **Step 1: Write analyzer unit tests**

Create `backend/tests/test_youtube_whitespace.py`:

```python
import importlib.util
from pathlib import Path


SCRIPT_PATH = Path(__file__).resolve().parents[2] / "scripts" / "youtube_whitespace.py"
spec = importlib.util.spec_from_file_location("youtube_whitespace", SCRIPT_PATH)
youtube_whitespace = importlib.util.module_from_spec(spec)
assert spec and spec.loader
spec.loader.exec_module(youtube_whitespace)


def test_score_rewards_high_views_and_low_video_count():
    low_supply = youtube_whitespace.compute_whitespace_score(total_views=500_000, total_videos=2)
    higher_supply = youtube_whitespace.compute_whitespace_score(total_views=500_000, total_videos=10)
    assert low_supply > higher_supply


def test_analyze_channel_filters_high_supply_and_low_demand():
    high_supply = {
        "channel_id": "UC1",
        "channel_name": "Many Videos",
        "channel_url": "https://www.youtube.com/channel/UC1",
        "subscriber_count": 100,
        "total_videos": 11,
        "channel_total_views": 1_000_000,
        "videos": [{"views": 1_000_000}],
    }
    low_demand = {
        "channel_id": "UC2",
        "channel_name": "Tiny",
        "channel_url": "https://www.youtube.com/channel/UC2",
        "subscriber_count": 100,
        "total_videos": 2,
        "channel_total_views": 10_000,
        "videos": [{"views": 8_000}],
    }

    assert youtube_whitespace.qualify_channel(high_supply, "science") is None
    assert youtube_whitespace.qualify_channel(low_demand, "science") is None


def test_qualify_channel_returns_feed_record():
    channel = {
        "channel_id": "UC3",
        "channel_name": "Breakout",
        "channel_url": "https://www.youtube.com/channel/UC3",
        "subscriber_count": None,
        "total_videos": 3,
        "channel_total_views": 450_000,
        "videos": [
            {
                "video_id": "v1",
                "title": "Big one",
                "url": "https://www.youtube.com/watch?v=v1",
                "views": 300_000,
                "likes": 10_000,
                "published_at": "2026-05-01",
            },
            {
                "video_id": "v2",
                "title": "Second",
                "url": "https://www.youtube.com/watch?v=v2",
                "views": 150_000,
                "likes": 4_000,
                "published_at": "2026-05-02",
            },
        ],
    }

    record = youtube_whitespace.qualify_channel(channel, "science myths")

    assert record is not None
    assert record["query"] == "science myths"
    assert record["channel_id"] == "UC3"
    assert record["total_videos"] == 3
    assert record["video_views_total"] == 450_000
    assert record["max_views"] == 300_000
    assert record["avg_views"] == 225_000
    assert "3 videos" in record["reason"]


def test_build_feed_dedupes_and_ranks_results():
    records = [
        {"channel_id": "UC1", "score": 10, "query": "a"},
        {"channel_id": "UC1", "score": 20, "query": "b"},
        {"channel_id": "UC2", "score": 15, "query": "c"},
    ]

    feed = youtube_whitespace.build_feed(
        seed={"generated_at": "2026-05-29T16:00:00Z", "search_queries": ["a", "b", "c"]},
        records=records,
        generated_at="2026-05-29T17:00:00Z",
    )

    assert [item["channel_id"] for item in feed["results"]] == ["UC1", "UC2"]
    assert [item["rank"] for item in feed["results"]] == [1, 2]
    assert feed["results"][0]["query"] == "b"
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run --project backend pytest backend/tests/test_youtube_whitespace.py -v`

Expected: FAIL because `scripts/youtube_whitespace.py` does not exist.

- [ ] **Step 3: Implement analyzer script**

Create `scripts/youtube_whitespace.py` with the provided analyzer adapted into pure helpers and a CLI. Use this structure:

```python
#!/usr/bin/env python3
"""Find YouTube whitespace channels from a Headless Hero discovery seed."""

from __future__ import annotations

import argparse
import json
import math
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from googleapiclient.discovery import build
from googleapiclient.errors import HttpError

MAX_VIDEOS = 10
MIN_TOTAL_VIEWS = 200_000
MIN_VIEWS_PER_VIDEO = 100_000
TOP_RESULTS = 20


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def compute_whitespace_score(total_views: int, total_videos: int) -> float:
    return round(math.log10(max(0, total_views) + 1) * 100 / max(total_videos, 1), 1)


def qualify_channel(channel: dict[str, Any], query: str) -> dict[str, Any] | None:
    total_videos = int(channel.get("total_videos") or 0)
    if total_videos > MAX_VIDEOS or total_videos <= 0:
        return None
    videos = channel.get("videos") or []
    view_counts = [int(video.get("views") or 0) for video in videos]
    if not view_counts:
        return None
    video_views_total = sum(view_counts)
    total_views = max(int(channel.get("channel_total_views") or 0), video_views_total)
    max_views = max(view_counts)
    if total_views < MIN_TOTAL_VIEWS or max_views < MIN_VIEWS_PER_VIDEO:
        return None
    avg_views = round(video_views_total / len(view_counts))
    score = compute_whitespace_score(total_views=total_views, total_videos=total_videos)
    return {
        "rank": 0,
        "score": score,
        "query": query,
        "channel_id": channel["channel_id"],
        "channel_name": channel["channel_name"],
        "channel_url": channel["channel_url"],
        "subscriber_count": channel.get("subscriber_count"),
        "total_videos": total_videos,
        "channel_total_views": total_views,
        "video_views_total": video_views_total,
        "max_views": max_views,
        "avg_views": avg_views,
        "reason": f"{total_videos} videos with {total_views:,} total views from a profile-matched query.",
        "videos": sorted(videos, key=lambda item: int(item.get("views") or 0), reverse=True)[:5],
    }


def build_feed(seed: dict[str, Any], records: list[dict[str, Any]], generated_at: str | None = None) -> dict[str, Any]:
    best_by_channel: dict[str, dict[str, Any]] = {}
    for record in records:
        channel_id = record["channel_id"]
        existing = best_by_channel.get(channel_id)
        if existing is None or float(record["score"]) > float(existing["score"]):
            best_by_channel[channel_id] = record
    ranked = sorted(best_by_channel.values(), key=lambda item: float(item["score"]), reverse=True)[:TOP_RESULTS]
    for index, item in enumerate(ranked, 1):
        item["rank"] = index
    return {
        "version": 1,
        "generated_at": generated_at or utc_now(),
        "seed_generated_at": seed.get("generated_at"),
        "source_queries": seed.get("search_queries", []),
        "results": ranked,
    }
```

Continue the same file by adapting the user's API functions:

```python
def build_youtube(api_key: str):
    return build("youtube", "v3", developerKey=api_key)


def search_channels(youtube, query: str, max_results: int = 25) -> list[str]:
    channel_ids: list[str] = []
    page_token = None
    while len(channel_ids) < max_results:
        resp = youtube.search().list(
            part="snippet",
            q=query,
            type="channel",
            maxResults=min(50, max_results - len(channel_ids)),
            pageToken=page_token,
        ).execute()
        for item in resp.get("items", []):
            channel_id = item.get("snippet", {}).get("channelId")
            if channel_id:
                channel_ids.append(channel_id)
        page_token = resp.get("nextPageToken")
        if not page_token:
            break
    return list(dict.fromkeys(channel_ids))


def get_channel_stats(youtube, channel_ids: list[str]) -> list[dict[str, Any]]:
    results: list[dict[str, Any]] = []
    for i in range(0, len(channel_ids), 50):
        resp = youtube.channels().list(
            part="snippet,statistics,contentDetails",
            id=",".join(channel_ids[i:i + 50]),
        ).execute()
        results.extend(resp.get("items", []))
    return results


def get_videos_for_channel(youtube, uploads_playlist_id: str, max_videos: int = MAX_VIDEOS + 2) -> list[dict[str, str]]:
    videos: list[dict[str, str]] = []
    page_token = None
    while len(videos) < max_videos:
        resp = youtube.playlistItems().list(
            part="snippet,contentDetails",
            playlistId=uploads_playlist_id,
            maxResults=min(50, max_videos - len(videos)),
            pageToken=page_token,
        ).execute()
        for item in resp.get("items", []):
            videos.append({
                "video_id": item["contentDetails"]["videoId"],
                "title": item["snippet"]["title"],
                "published_at": item["snippet"]["publishedAt"],
            })
        page_token = resp.get("nextPageToken")
        if not page_token:
            break
    return videos


def get_video_stats(youtube, video_ids: list[str]) -> dict[str, dict[str, Any]]:
    stats: dict[str, dict[str, Any]] = {}
    for i in range(0, len(video_ids), 50):
        resp = youtube.videos().list(
            part="statistics,snippet",
            id=",".join(video_ids[i:i + 50]),
        ).execute()
        for item in resp.get("items", []):
            stats[item["id"]] = {
                "video_id": item["id"],
                "title": item["snippet"]["title"],
                "url": f"https://www.youtube.com/watch?v={item['id']}",
                "views": int(item["statistics"].get("viewCount", 0)),
                "likes": int(item["statistics"].get("likeCount", 0)),
                "published_at": item["snippet"]["publishedAt"][:10],
            }
    return stats


def collect_channel(youtube, item: dict[str, Any]) -> dict[str, Any] | None:
    channel_id = item["id"]
    snippet = item.get("snippet", {})
    statistics = item.get("statistics", {})
    total_videos = int(statistics.get("videoCount", 0))
    if total_videos > MAX_VIDEOS:
        return None
    uploads_playlist = item.get("contentDetails", {}).get("relatedPlaylists", {}).get("uploads")
    if not uploads_playlist:
        return None
    videos = get_videos_for_channel(youtube, uploads_playlist)
    if len(videos) > MAX_VIDEOS or not videos:
        return None
    video_stats = get_video_stats(youtube, [video["video_id"] for video in videos])
    enriched_videos = [video_stats[video["video_id"]] for video in videos if video["video_id"] in video_stats]
    hidden_subs = statistics.get("hiddenSubscriberCount")
    return {
        "channel_id": channel_id,
        "channel_name": snippet.get("title", "Unknown"),
        "channel_url": f"https://www.youtube.com/channel/{channel_id}",
        "subscriber_count": None if hidden_subs else int(statistics.get("subscriberCount", 0)),
        "total_videos": total_videos,
        "channel_total_views": int(statistics.get("viewCount", 0)),
        "videos": enriched_videos,
    }


def run(seed_path: Path, output_path: Path, api_key: str) -> dict[str, Any]:
    seed = json.loads(seed_path.read_text())
    youtube = build_youtube(api_key)
    records: list[dict[str, Any]] = []
    for query in seed.get("search_queries", []):
        try:
            channel_ids = search_channels(youtube, query, max_results=25)
            for channel_item in get_channel_stats(youtube, channel_ids):
                channel = collect_channel(youtube, channel_item)
                if not channel:
                    continue
                record = qualify_channel(channel, query)
                if record:
                    records.append(record)
        except HttpError as exc:
            print(f"[warn] YouTube API error for query {query!r}: {exc}")
    feed = build_feed(seed, records)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(feed, indent=2) + "\n")
    return feed


def main() -> int:
    parser = argparse.ArgumentParser(description="Generate YouTube whitespace feed from discovery seed.")
    parser.add_argument("--seed", default="discovery/content-profile-seed.json")
    parser.add_argument("--output", default="frontend/public/discovery/youtube-whitespace.json")
    parser.add_argument("--api-key", default=os.environ.get("YOUTUBE_API_KEY", ""))
    args = parser.parse_args()
    seed_path = Path(args.seed)
    if not args.api_key:
        print("YOUTUBE_API_KEY missing; keeping previous feed.")
        return 0
    if not seed_path.exists():
        print(f"Seed file missing: {seed_path}; keeping previous feed.")
        return 0
    run(seed_path, Path(args.output), args.api_key)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
```

- [ ] **Step 4: Add initial seed and empty feed files**

Create `discovery/content-profile-seed.json`:

```json
{
  "version": 1,
  "generated_at": "2026-05-29T00:00:00Z",
  "source": "headless-hero-content-profile",
  "profile": {
    "script_count": 0,
    "common_topics": [],
    "typical_keywords": [],
    "audience_profile": "",
    "narration_style": "",
    "visual_approach": "",
    "avg_segment_count": 0
  },
  "search_queries": []
}
```

Create `frontend/public/discovery/youtube-whitespace.json`:

```json
{
  "version": 1,
  "generated_at": null,
  "seed_generated_at": null,
  "source_queries": [],
  "results": []
}
```

- [ ] **Step 5: Add workflow**

Create `.github/workflows/youtube-whitespace.yml`:

```yaml
name: YouTube Whitespace Discovery

on:
  push:
    paths:
      - discovery/content-profile-seed.json
  workflow_dispatch:
  schedule:
    - cron: "17 12 * * *"

permissions:
  contents: write

jobs:
  refresh:
    runs-on: ubuntu-latest
    steps:
      - name: Check out repository
        uses: actions/checkout@v4
        with:
          fetch-depth: 0

      - name: Set up Python
        uses: actions/setup-python@v5
        with:
          python-version: "3.12"

      - name: Install uv
        uses: astral-sh/setup-uv@v5

      - name: Install analyzer dependencies
        run: uv pip install --system google-api-python-client

      - name: Generate whitespace feed
        env:
          YOUTUBE_API_KEY: ${{ secrets.YOUTUBE_API_KEY }}
        run: uv run python scripts/youtube_whitespace.py

      - name: Commit feed changes
        run: |
          if git diff --quiet -- frontend/public/discovery/youtube-whitespace.json; then
            echo "No whitespace feed changes."
            exit 0
          fi
          git config user.name "github-actions[bot]"
          git config user.email "41898282+github-actions[bot]@users.noreply.github.com"
          git add frontend/public/discovery/youtube-whitespace.json
          git commit -m "Update YouTube whitespace discovery feed"
          git push
```

- [ ] **Step 6: Run analyzer tests**

Run: `uv run --project backend pytest backend/tests/test_youtube_whitespace.py -v`

Expected: PASS.

- [ ] **Step 7: Run analyzer locally without key**

Run: `uv run --project backend python scripts/youtube_whitespace.py --seed discovery/content-profile-seed.json --output frontend/public/discovery/youtube-whitespace.json`

Expected: prints `YOUTUBE_API_KEY missing; keeping previous feed.` and exits 0.

- [ ] **Step 8: Commit**

```bash
git add scripts/youtube_whitespace.py backend/tests/test_youtube_whitespace.py .github/workflows/youtube-whitespace.yml discovery/content-profile-seed.json frontend/public/discovery/youtube-whitespace.json
git commit -m "Add YouTube whitespace discovery workflow"
```

---

### Task 5: Add Whitespace Feed Frontend Tab

**Files:**
- Modify: `frontend/src/types/trending.ts`
- Create: `frontend/src/components/trending/WhitespaceTab.tsx`
- Modify: `frontend/src/components/trending/DiscoverPage.tsx`
- Test: `frontend/src/components/trending/WhitespaceTab.test.tsx`

- [ ] **Step 1: Add failing frontend tests**

Create `frontend/src/components/trending/WhitespaceTab.test.tsx`:

```tsx
import { render, screen, waitFor } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import WhitespaceTab from "./WhitespaceTab";

const originalFetch = global.fetch;

describe("WhitespaceTab", () => {
  beforeEach(() => {
    vi.useRealTimers();
  });

  afterEach(() => {
    global.fetch = originalFetch;
  });

  it("renders whitespace results from the static feed", async () => {
    global.fetch = vi.fn().mockResolvedValue({
      ok: true,
      json: async () => ({
        version: 1,
        generated_at: "2026-05-29T17:00:00Z",
        seed_generated_at: "2026-05-29T16:00:00Z",
        source_queries: ["science myths"],
        results: [
          {
            rank: 1,
            score: 582.1,
            query: "science myths",
            channel_id: "UC123",
            channel_name: "Breakout Science",
            channel_url: "https://www.youtube.com/channel/UC123",
            subscriber_count: 12000,
            total_videos: 4,
            channel_total_views: 850000,
            video_views_total: 830000,
            max_views: 600000,
            avg_views: 207500,
            reason: "4 videos with 850,000 total views from a profile-matched query.",
            videos: [
              {
                video_id: "v1",
                title: "The big one",
                url: "https://www.youtube.com/watch?v=v1",
                views: 600000,
                likes: 12000,
                published_at: "2026-05-01",
              },
            ],
          },
        ],
      }),
    }) as unknown as typeof fetch;

    render(<WhitespaceTab />);

    expect(await screen.findByText("Breakout Science")).toBeInTheDocument();
    expect(screen.getByText("science myths")).toBeInTheDocument();
    expect(screen.getByText("4 videos")).toBeInTheDocument();
    expect(screen.getByText("850.0K")).toBeInTheDocument();
    expect(screen.getByText("The big one")).toBeInTheDocument();
  });

  it("renders empty state when no feed exists", async () => {
    global.fetch = vi.fn().mockResolvedValue({ ok: false, status: 404 }) as unknown as typeof fetch;

    render(<WhitespaceTab />);

    await waitFor(() => {
      expect(screen.getByText("No whitespace feed has been generated yet.")).toBeInTheDocument();
    });
  });

  it("renders invalid feed state", async () => {
    global.fetch = vi.fn().mockResolvedValue({
      ok: true,
      json: async () => ({ version: 1, results: "bad" }),
    }) as unknown as typeof fetch;

    render(<WhitespaceTab />);

    await waitFor(() => {
      expect(screen.getByText("Whitespace feed is invalid.")).toBeInTheDocument();
    });
  });
});
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd frontend && npm run test -- src/components/trending/WhitespaceTab.test.tsx`

Expected: FAIL because `WhitespaceTab` does not exist.

- [ ] **Step 3: Add feed types**

Append to `frontend/src/types/trending.ts`:

```ts
export interface WhitespaceVideo {
  video_id: string;
  title: string;
  url: string;
  views: number;
  likes: number;
  published_at: string;
}

export interface WhitespaceResult {
  rank: number;
  score: number;
  query: string;
  channel_id: string;
  channel_name: string;
  channel_url: string;
  subscriber_count: number | null;
  total_videos: number;
  channel_total_views: number;
  video_views_total: number;
  max_views: number;
  avg_views: number;
  reason: string;
  videos: WhitespaceVideo[];
}

export interface WhitespaceFeed {
  version: number;
  generated_at: string | null;
  seed_generated_at: string | null;
  source_queries: string[];
  results: WhitespaceResult[];
}
```

- [ ] **Step 4: Implement Whitespace tab**

Create `frontend/src/components/trending/WhitespaceTab.tsx`:

```tsx
import { useEffect, useState } from "react";
import type { WhitespaceFeed, WhitespaceResult } from "../../types/trending";

function fmt(n: number | null | undefined): string {
  if (n === null || n === undefined) return "hidden";
  if (n >= 1_000_000) return `${(n / 1_000_000).toFixed(1)}M`;
  if (n >= 1_000) return `${(n / 1_000).toFixed(1)}K`;
  return String(n);
}

function formatDate(value: string | null): string {
  if (!value) return "Never generated";
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return value;
  return date.toLocaleString();
}

function isFeed(value: unknown): value is WhitespaceFeed {
  if (!value || typeof value !== "object") return false;
  const feed = value as { results?: unknown };
  return Array.isArray(feed.results);
}

function ResultCard({ result }: { result: WhitespaceResult }) {
  return (
    <article className="bg-neutral-900 border border-neutral-800 rounded-xl p-5 space-y-4">
      <div className="flex items-start justify-between gap-4">
        <div>
          <div className="flex items-center gap-2 text-xs text-neutral-500 mb-1">
            <span>#{result.rank}</span>
            <span>Score {result.score.toFixed(1)}</span>
            <span>{result.query}</span>
          </div>
          <a
            href={result.channel_url}
            target="_blank"
            rel="noreferrer"
            className="text-lg font-semibold text-neutral-100 hover:text-sky-300 transition-colors"
          >
            {result.channel_name}
          </a>
          <p className="text-sm text-neutral-400 mt-2">{result.reason}</p>
        </div>
        <div className="text-right text-xs text-neutral-500 shrink-0">
          <div>{result.total_videos} videos</div>
          <div>{fmt(result.channel_total_views)} views</div>
        </div>
      </div>

      <div className="grid grid-cols-2 sm:grid-cols-4 gap-3 text-sm">
        <div className="bg-neutral-950/70 border border-neutral-800 rounded-lg p-3">
          <div className="text-neutral-500 text-xs">Max views</div>
          <div className="text-neutral-100 font-medium">{fmt(result.max_views)}</div>
        </div>
        <div className="bg-neutral-950/70 border border-neutral-800 rounded-lg p-3">
          <div className="text-neutral-500 text-xs">Avg views</div>
          <div className="text-neutral-100 font-medium">{fmt(result.avg_views)}</div>
        </div>
        <div className="bg-neutral-950/70 border border-neutral-800 rounded-lg p-3">
          <div className="text-neutral-500 text-xs">Analyzed views</div>
          <div className="text-neutral-100 font-medium">{fmt(result.video_views_total)}</div>
        </div>
        <div className="bg-neutral-950/70 border border-neutral-800 rounded-lg p-3">
          <div className="text-neutral-500 text-xs">Subscribers</div>
          <div className="text-neutral-100 font-medium">{fmt(result.subscriber_count)}</div>
        </div>
      </div>

      {result.videos.length > 0 && (
        <div className="space-y-2">
          <div className="text-xs uppercase tracking-wide text-neutral-500">Top videos</div>
          {result.videos.map((video) => (
            <a
              key={video.video_id}
              href={video.url}
              target="_blank"
              rel="noreferrer"
              className="block text-sm text-neutral-300 hover:text-sky-300 transition-colors"
            >
              {video.title}
              <span className="text-neutral-500"> · {fmt(video.views)} views</span>
            </a>
          ))}
        </div>
      )}
    </article>
  );
}

export default function WhitespaceTab() {
  const [feed, setFeed] = useState<WhitespaceFeed | null>(null);
  const [state, setState] = useState<"loading" | "ready" | "empty" | "invalid">("loading");

  useEffect(() => {
    let cancelled = false;
    fetch("/discovery/youtube-whitespace.json", { cache: "no-store" })
      .then(async (res) => {
        if (!res.ok) {
          if (!cancelled) setState("empty");
          return;
        }
        const data = await res.json();
        if (!isFeed(data)) {
          if (!cancelled) setState("invalid");
          return;
        }
        if (!cancelled) {
          setFeed(data);
          setState(data.results.length > 0 ? "ready" : "empty");
        }
      })
      .catch(() => {
        if (!cancelled) setState("empty");
      });
    return () => {
      cancelled = true;
    };
  }, []);

  return (
    <div className="space-y-6">
      <div>
        <h2 className="text-2xl font-bold mb-1">Whitespace</h2>
        <p className="text-neutral-400 text-sm">
          Profile-matched YouTube channels with unusually high demand and low visible supply.
        </p>
        <p className="text-neutral-500 text-xs mt-2">
          Results update after Refresh profile uploads a sanitized seed and GitHub Actions completes.
        </p>
      </div>

      {state === "loading" && <div className="text-neutral-500 text-sm">Loading whitespace feed...</div>}

      {state === "invalid" && (
        <div className="bg-red-500/10 border border-red-500/20 rounded-xl p-5 text-sm text-red-300">
          Whitespace feed is invalid.
        </div>
      )}

      {state === "empty" && (
        <div className="bg-neutral-900 border border-neutral-800 rounded-xl p-6 text-sm text-neutral-400">
          No whitespace feed has been generated yet.
        </div>
      )}

      {state === "ready" && feed && (
        <>
          <div className="flex items-center justify-between text-xs text-neutral-500">
            <span>{feed.results.length} opportunities</span>
            <span>Generated {formatDate(feed.generated_at)}</span>
          </div>
          <div className="space-y-4">
            {feed.results.map((result) => (
              <ResultCard key={`${result.channel_id}-${result.rank}`} result={result} />
            ))}
          </div>
        </>
      )}
    </div>
  );
}
```

- [ ] **Step 5: Add tab to Discover page**

In `frontend/src/components/trending/DiscoverPage.tsx`, import the component:

```tsx
import WhitespaceTab from "./WhitespaceTab";
```

Change state:

```tsx
const [activeTab, setActiveTab] = useState<"trending" | "for-you" | "whitespace">("for-you");
```

Add a third button after Trending:

```tsx
<button
  onClick={() => setActiveTab("whitespace")}
  className={`flex items-center gap-2 px-5 py-2 text-sm font-medium rounded-lg transition-all duration-200 ${
    activeTab === "whitespace"
      ? "bg-neutral-700/80 text-white shadow-sm"
      : "text-neutral-400 hover:text-neutral-200"
  }`}
>
  <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" strokeWidth={1.8} stroke="currentColor">
    <path strokeLinecap="round" strokeLinejoin="round" d="M3 17.25V6.75A2.25 2.25 0 015.25 4.5h13.5A2.25 2.25 0 0121 6.75v10.5a2.25 2.25 0 01-2.25 2.25H5.25A2.25 2.25 0 013 17.25zM7.5 8.25h9M7.5 12h5.25M7.5 15.75h7.5" />
  </svg>
  Whitespace
</button>
```

Add panel:

```tsx
<div className={activeTab === "whitespace" ? "block" : "hidden"}>
  <WhitespaceTab />
</div>
```

- [ ] **Step 6: Run frontend test**

Run: `cd frontend && npm run test -- src/components/trending/WhitespaceTab.test.tsx`

Expected: PASS.

- [ ] **Step 7: Commit**

```bash
git add frontend/src/types/trending.ts frontend/src/components/trending/WhitespaceTab.tsx frontend/src/components/trending/DiscoverPage.tsx frontend/src/components/trending/WhitespaceTab.test.tsx
git commit -m "Add whitespace discovery tab"
```

---

### Task 6: Update API Keys UI For GitHub Token

**Files:**
- Modify: `frontend/src/components/settings/ApiKeysSection.tsx`
- Test: `frontend/src/components/settings/ApiKeysSection.test.tsx`

- [ ] **Step 1: Add failing settings UI test**

Open `frontend/src/components/settings/ApiKeysSection.test.tsx` and add:

```tsx
it("shows GitHub Contents Token under Discovery", async () => {
  vi.mocked(api.get).mockResolvedValue({
    ok: true,
    data: {
      GITHUB_CONTENTS_TOKEN: {
        configured: false,
        masked: "",
        source: "none",
      },
    },
  });

  render(<ApiKeysSection />);

  expect(await screen.findByText("GitHub Contents Token")).toBeInTheDocument();
  expect(screen.getByText("Fine-grained GitHub token with Contents write access for uploading the sanitized discovery seed.")).toBeInTheDocument();
});
```

If this file does not already mock `api`, follow its existing test setup rather than adding a second mock style.

- [ ] **Step 2: Run test to verify it fails**

Run: `cd frontend && npm run test -- src/components/settings/ApiKeysSection.test.tsx`

Expected: FAIL because the GitHub token label is missing.

- [ ] **Step 3: Add service config**

In `frontend/src/components/settings/ApiKeysSection.tsx`, add to the Discovery `services` array after `YOUTUBE_API_KEY`:

```tsx
{
  key: "GITHUB_CONTENTS_TOKEN",
  label: "GitHub Contents Token",
  description: "Fine-grained GitHub token with Contents write access for uploading the sanitized discovery seed.",
  placeholder: "github_pat_...",
},
```

- [ ] **Step 4: Run settings UI test**

Run: `cd frontend && npm run test -- src/components/settings/ApiKeysSection.test.tsx`

Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add frontend/src/components/settings/ApiKeysSection.tsx frontend/src/components/settings/ApiKeysSection.test.tsx
git commit -m "Add GitHub discovery token setting"
```

---

### Task 7: Update For You Refresh Feedback

**Files:**
- Modify: `frontend/src/types/trending.ts`
- Modify: `frontend/src/api.ts`
- Modify: `frontend/src/components/trending/ForYouTab.tsx`
- Test: `frontend/src/components/trending/ForYouTab.test.tsx` if present, otherwise `frontend/src/components/trending/ForYouTabSeedUpload.test.tsx`

- [ ] **Step 1: Add response type fields**

In `frontend/src/types/trending.ts`, add:

```ts
export interface SeedUploadStatus {
  status: "uploaded" | "skipped" | "warning";
  message: string;
  commit_sha?: string | null;
}

export interface ContentProfileRefreshResponse extends ContentProfile {
  seed_upload: SeedUploadStatus;
}
```

- [ ] **Step 2: Update API return type**

In `frontend/src/api.ts`, change `refreshContentProfile`:

```ts
import type { TrendingTopic, TrendingRefreshStatus, ContentProfile, ContentProfileRefreshResponse } from "./types/trending";
```

```ts
export async function refreshContentProfile(): Promise<ContentProfileRefreshResponse> {
  const res = await api.post("/api/trending/content-profile/refresh");
  if (!res.ok) throw new Error((res.data as { detail?: string }).detail || "Failed to refresh profile");
  return res.data as ContentProfileRefreshResponse;
}
```

- [ ] **Step 3: Update For You toast behavior**

In `frontend/src/components/trending/ForYouTab.tsx`, update `handleRefreshProfile` after `const p = await refreshContentProfile();`:

```tsx
setProfile(p);
if (p.seed_upload.status === "uploaded") {
  showToast("Content profile refreshed and whitespace seed uploaded", "success");
} else if (p.seed_upload.status === "warning") {
  showToast(`Profile refreshed, but seed upload failed: ${p.seed_upload.message}`, "warning");
} else {
  showToast("Content profile refreshed. Add a GitHub Contents Token to refresh whitespace remotely.", "info");
}
```

Remove or replace any older unconditional success toast in the same handler.

- [ ] **Step 4: Run frontend typecheck/build**

Run: `cd frontend && npm run build`

Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add frontend/src/types/trending.ts frontend/src/api.ts frontend/src/components/trending/ForYouTab.tsx
git commit -m "Show discovery seed upload status"
```

---

### Task 8: Update Project Convention Docs

**Files:**
- Modify: `AGENTS.md`

- [ ] **Step 1: Add convention**

In `AGENTS.md`, under Key Patterns near the content profile/discovery/trending conventions, add:

```markdown
- **Remote whitespace discovery uses sanitized seeds only**: GitHub Actions discovery must read `discovery/content-profile-seed.json`, which is uploaded after content profile refresh and contains only sanitized profile summaries plus deterministic search queries. Never commit the local SQLite DB, script bodies, secrets, OAuth data, generated asset paths, or project records to power remote discovery. The GitHub repo/branch for seed upload is hard-coded to `alecgrater/headless-hero` on `main`; only `GITHUB_CONTENTS_TOKEN` is user-configurable in Settings -> API Keys.
```

- [ ] **Step 2: Commit**

```bash
git add AGENTS.md
git commit -m "Document remote whitespace discovery convention"
```

---

### Task 9: Final Verification And Auto-Commit Loop

**Files:**
- No new files unless review findings require fixes.

- [ ] **Step 1: Run backend tests for touched areas**

Run:

```bash
uv run --project backend pytest \
  backend/tests/test_discovery_seed.py \
  backend/tests/test_github_contents.py \
  backend/tests/test_content_profile_seed_upload.py \
  backend/tests/test_youtube_whitespace.py \
  backend/tests/test_content_profile.py \
  -v
```

Expected: PASS.

- [ ] **Step 2: Run frontend tests for touched areas**

Run:

```bash
cd frontend && npm run test -- \
  src/components/settings/ApiKeysSection.test.tsx \
  src/components/trending/WhitespaceTab.test.tsx
```

Expected: PASS.

- [ ] **Step 3: Run frontend build**

Run: `cd frontend && npm run build`

Expected: PASS.

- [ ] **Step 4: Run analyzer missing-key smoke test**

Run:

```bash
uv run --project backend python scripts/youtube_whitespace.py \
  --seed discovery/content-profile-seed.json \
  --output frontend/public/discovery/youtube-whitespace.json
```

Expected: exits 0 and prints `YOUTUBE_API_KEY missing; keeping previous feed.` when no key is present.

- [ ] **Step 5: Check worktree**

Run: `git status --short`

Expected: only intended files are modified, or clean after commits. Preserve any unrelated pre-existing changes such as `backend/models/script.py`, `data/`, and `docs/superpowers/plans/2026-05-23-preset-scoped-characters.md`.

- [ ] **Step 6: Push main**

Run: `git push origin main`

Expected: push succeeds.

- [ ] **Step 7: Dispatch delegated review**

Use Codex agent delegation tooling with this exact prompt:

```text
Review the most recent commit on the main branch of this project.
Run `git diff HEAD~1..HEAD` to see the changes and `git show --stat HEAD` for context.
Read the full affected files (not just the diff) to understand surrounding code.
Check for: correctness bugs, error handling gaps, security issues, naive/aware datetime mismatches, unhandled promise rejections, race conditions, and style problems.
Return a structured verdict: either LGTM or NEEDS CHANGES.
If NEEDS CHANGES, provide a numbered list of findings with severity (FAIL/WARN), file:line, and a specific description of what's wrong and how to fix it.
```

Expected: review returns LGTM or actionable findings.

- [ ] **Step 8: Apply review findings if needed**

If verdict is NEEDS CHANGES, implement every FAIL and WARN finding, then run targeted tests, commit with:

```bash
git add <fixed-files>
git commit -m "fix: address review findings"
git push origin main
```

Then repeat Step 7 until review returns LGTM.

- [ ] **Step 9: Final summary**

After LGTM only, summarize:

- seed upload behavior
- workflow/analyzer behavior
- Whitespace tab behavior
- review findings and fixes, if any
- tests run

---

## Self-Review

- Spec coverage: covered settings token placement, hard-coded repo/branch, sanitized seed, GitHub upload, Action trigger/schedule, YouTube analyzer, static feed, Whitespace tab, errors, security, tests, and AGENTS convention update.
- Placeholder scan: no `TBD`, `TODO`, or unspecified implementation steps remain.
- Type consistency: backend response uses `seed_upload`; frontend mirrors it with `ContentProfileRefreshResponse`; feed/result type names match the Whitespace tab usage.
