# Fallback Observability Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add structured fallback events and a Dev Dashboard Fallbacks tab so frequent silent degradation is visible and actionable.

**Architecture:** Use the existing SQLite-backed `DevLog` pipeline as storage and streaming infrastructure. A focused helper emits `[FALLBACK]` JSON log messages, `backend/dev/routes.py` parses and aggregates those rows for `/dev/api/fallbacks/stats`, and `backend/dev/dashboard.html` renders a dense operational analytics tab.

**Tech Stack:** Python 3.12, FastAPI, SQLModel/SQLite, pytest via `uv run --project backend pytest`, plain HTML/JavaScript/Tailwind in `backend/dev/dashboard.html`.

---

## File Structure

- Create `backend/pipeline/fallback_observability.py`
  - Owns event schema normalization, safe metadata filtering, log-level mapping, `[FALLBACK]` message formatting, parsing, aggregation, and hot-event heuristics.
- Create `backend/tests/test_fallback_observability.py`
  - Unit-tests helper emission/parsing/aggregation without requiring the full FastAPI app.
- Create `backend/tests/test_dev_fallback_routes.py`
  - Tests `/dev/api/fallbacks/stats` against an isolated SQLite engine and `DevLog` rows.
- Modify `backend/dev/routes.py`
  - Adds the stats endpoint and delegates parsing/aggregation to the helper.
- Modify `backend/dev/dashboard.html`
  - Adds the Fallbacks tab, filters, summary cards, aggregate lists, and recent examples table.
- Modify high-signal fallback modules:
  - `backend/pipeline/media_analyzer.py`
  - `backend/pipeline/image_gen.py`
  - `backend/pipeline/hook_detector.py`
  - `backend/pipeline/thumbnail.py`
  - `backend/pipeline/audio_alignment.py`
- Modify `AGENTS.md`
  - Documents the convention that meaningful fallbacks must call the structured helper.

## Task 1: Structured Fallback Helper

**Files:**
- Create: `backend/pipeline/fallback_observability.py`
- Test: `backend/tests/test_fallback_observability.py`

- [ ] **Step 1: Write failing helper tests**

Create `backend/tests/test_fallback_observability.py`:

```python
import json
import logging
from datetime import datetime, timezone

from pipeline import fallback_observability as fallback


def test_record_fallback_emits_parseable_json(caplog):
    caplog.set_level(logging.WARNING)

    fallback.record_fallback(
        category="image_generation",
        event="image_placeholder_created",
        reason="AI image generation failed",
        from_value="google",
        to_value="placeholder",
        script_id="script-1",
        scene_id="scene-2",
        severity="fail",
        metadata={
            "provider": "google",
            "asset_path": "~/git/headless-hero/data/projects/script-1/images/scene-2.png",
            "prompt": "do not leak prompt text",
            "duration_seconds": 4.2,
        },
    )

    assert len(caplog.records) == 1
    record = caplog.records[0]
    assert record.levelname == "ERROR"
    assert record.message.startswith("[FALLBACK] ")

    payload = json.loads(record.message.removeprefix("[FALLBACK] "))
    assert payload == {
        "category": "image_generation",
        "event": "image_placeholder_created",
        "reason": "AI image generation failed",
        "from": "google",
        "to": "placeholder",
        "script_id": "script-1",
        "scene_id": "scene-2",
        "severity": "fail",
        "metadata": {
            "asset_basename": "scene-2.png",
            "duration_seconds": 4.2,
            "provider": "google",
        },
    }


def test_parse_fallback_message_ignores_non_fallback_and_malformed_rows():
    assert fallback.parse_fallback_message("ordinary log") is None
    assert fallback.parse_fallback_message("[FALLBACK] not-json") is None


def test_summarize_fallback_events_counts_and_hot_events():
    events = [
        {
            "id": 1,
            "timestamp": datetime(2026, 6, 5, tzinfo=timezone.utc).isoformat(),
            "logger_name": "pipeline.image_gen",
            "category": "image_generation",
            "event": "image_placeholder_created",
            "reason": "AI failed",
            "severity": "fail",
        },
        {
            "id": 2,
            "timestamp": datetime(2026, 6, 5, tzinfo=timezone.utc).isoformat(),
            "logger_name": "pipeline.media_analyzer",
            "category": "visual_mode",
            "event": "ai_video_downgraded",
            "reason": "Adjacent video",
            "severity": "warn",
        },
        {
            "id": 3,
            "timestamp": datetime(2026, 6, 5, tzinfo=timezone.utc).isoformat(),
            "logger_name": "pipeline.media_analyzer",
            "category": "visual_mode",
            "event": "ai_video_downgraded",
            "reason": "Adjacent video",
            "severity": "warn",
        },
        {
            "id": 4,
            "timestamp": datetime(2026, 6, 5, tzinfo=timezone.utc).isoformat(),
            "logger_name": "pipeline.media_analyzer",
            "category": "visual_mode",
            "event": "ai_video_downgraded",
            "reason": "Adjacent video",
            "severity": "warn",
        },
    ]

    summary = fallback.summarize_fallback_events(events, window_hours=24, malformed_count=1)

    assert summary["total"] == 4
    assert summary["malformed_count"] == 1
    assert summary["by_severity"] == {"fail": 1, "warn": 3}
    assert summary["by_category"][0] == {"category": "visual_mode", "count": 3}
    assert summary["by_event"][0] == {
        "category": "visual_mode",
        "event": "ai_video_downgraded",
        "count": 3,
        "severity": "warn",
    }
    assert summary["by_reason"][0] == {"reason": "Adjacent video", "count": 3}
    assert {item["event"] for item in summary["hot_events"]} == {
        "image_placeholder_created",
        "ai_video_downgraded",
    }
```

- [ ] **Step 2: Run tests and verify they fail**

Run:

```bash
uv run --project backend pytest backend/tests/test_fallback_observability.py -q
```

Expected: FAIL with `ImportError` because `pipeline.fallback_observability` does not exist.

- [ ] **Step 3: Implement the helper**

Create `backend/pipeline/fallback_observability.py`:

```python
"""Structured fallback observability for the dev dashboard."""

from __future__ import annotations

import json
import logging
from collections import Counter
from pathlib import Path
from typing import Any

FALLBACK_PREFIX = "[FALLBACK] "

_LEVEL_BY_SEVERITY = {
    "info": logging.INFO,
    "warn": logging.WARNING,
    "fail": logging.ERROR,
}

_SAFE_METADATA_KEYS = {
    "provider",
    "model",
    "cap",
    "count",
    "duration_seconds",
    "max_duration_seconds",
    "segment_index",
    "attempt",
    "source_type",
    "fallback_count",
    "word_count",
}


def record_fallback(
    *,
    category: str,
    event: str,
    reason: str,
    from_value: str | None = None,
    to_value: str | None = None,
    script_id: str | None = None,
    scene_id: str | None = None,
    segment_index: int | None = None,
    severity: str = "warn",
    metadata: dict[str, Any] | None = None,
    logger: logging.Logger | None = None,
) -> None:
    """Emit a structured fallback event through normal logging."""

    normalized_severity = severity if severity in _LEVEL_BY_SEVERITY else "warn"
    payload: dict[str, Any] = {
        "category": _clean_string(category),
        "event": _clean_string(event),
        "reason": _clean_string(reason),
        "severity": normalized_severity,
    }
    if from_value:
        payload["from"] = _clean_string(from_value)
    if to_value:
        payload["to"] = _clean_string(to_value)
    if script_id:
        payload["script_id"] = _clean_string(script_id)
    if scene_id:
        payload["scene_id"] = _clean_string(scene_id)
    if segment_index is not None:
        payload["segment_index"] = segment_index
    safe_metadata = _safe_metadata(metadata or {})
    if safe_metadata:
        payload["metadata"] = safe_metadata

    target_logger = logger or logging.getLogger(__name__)
    target_logger.log(
        _LEVEL_BY_SEVERITY[normalized_severity],
        "%s%s",
        FALLBACK_PREFIX,
        json.dumps(payload, sort_keys=True, separators=(",", ":")),
    )


def parse_fallback_message(message: str) -> dict[str, Any] | None:
    """Parse a `[FALLBACK]` log message into a payload dict."""

    if not message.startswith(FALLBACK_PREFIX):
        return None
    try:
        payload = json.loads(message[len(FALLBACK_PREFIX):])
    except json.JSONDecodeError:
        return None
    if not isinstance(payload, dict):
        return None
    if not payload.get("category") or not payload.get("event"):
        return None
    payload["severity"] = payload.get("severity") if payload.get("severity") in _LEVEL_BY_SEVERITY else "warn"
    return payload


def summarize_fallback_events(
    events: list[dict[str, Any]],
    *,
    window_hours: int,
    malformed_count: int = 0,
    recent_limit: int = 50,
) -> dict[str, Any]:
    """Aggregate parsed fallback events for the dev dashboard."""

    by_category = Counter(str(event.get("category", "")) for event in events)
    by_reason = Counter(str(event.get("reason", "")) for event in events if event.get("reason"))
    by_severity = Counter(str(event.get("severity", "warn")) for event in events)

    event_counts: Counter[tuple[str, str]] = Counter()
    event_severities: dict[tuple[str, str], str] = {}
    for event in events:
        key = (str(event.get("category", "")), str(event.get("event", "")))
        event_counts[key] += 1
        event_severities[key] = _max_severity(event_severities.get(key), str(event.get("severity", "warn")))

    by_event = [
        {
            "category": category,
            "event": event,
            "count": count,
            "severity": event_severities[(category, event)],
        }
        for (category, event), count in event_counts.most_common()
    ]

    total = len(events)
    hot_events = [
        item
        for item in by_event
        if item["severity"] == "fail"
        or (item["severity"] == "warn" and item["count"] >= 3)
        or (total >= 4 and item["count"] / total >= 0.5)
    ]

    return {
        "window_hours": window_hours,
        "total": total,
        "malformed_count": malformed_count,
        "by_category": [
            {"category": category, "count": count}
            for category, count in by_category.most_common()
            if category
        ],
        "by_event": by_event,
        "by_reason": [
            {"reason": reason, "count": count}
            for reason, count in by_reason.most_common()
            if reason
        ],
        "by_severity": dict(by_severity),
        "hot_events": hot_events,
        "recent": events[:recent_limit],
    }


def _clean_string(value: object) -> str:
    return str(value).replace("\n", " ").strip()[:500]


def _safe_metadata(metadata: dict[str, Any]) -> dict[str, Any]:
    safe: dict[str, Any] = {}
    for key, value in metadata.items():
        if key in _SAFE_METADATA_KEYS:
            safe[key] = value
        elif key.endswith("_path") or key.endswith("_file"):
            safe[f"{key.rsplit('_', 1)[0]}_basename"] = Path(str(value)).name
    return dict(sorted(safe.items()))


def _max_severity(left: str | None, right: str) -> str:
    order = {"info": 0, "warn": 1, "fail": 2}
    if left is None:
        return right if right in order else "warn"
    return left if order.get(left, 1) >= order.get(right, 1) else right
```

- [ ] **Step 4: Run helper tests and verify they pass**

Run:

```bash
uv run --project backend pytest backend/tests/test_fallback_observability.py -q
```

Expected: PASS.

## Task 2: Fallback Stats Endpoint

**Files:**
- Modify: `backend/dev/routes.py`
- Test: `backend/tests/test_dev_fallback_routes.py`

- [ ] **Step 1: Write failing endpoint tests**

Create `backend/tests/test_dev_fallback_routes.py`:

```python
import json
from datetime import datetime, timedelta, timezone

from fastapi.testclient import TestClient
from sqlmodel import Session, SQLModel, create_engine

from dev.log_handler import DevLog
from pipeline.fallback_observability import FALLBACK_PREFIX


def test_fallback_stats_endpoint_aggregates_logs(monkeypatch, tmp_path):
    import database
    from api import app

    engine = create_engine(f"sqlite:///{tmp_path / 'fallbacks.db'}")
    SQLModel.metadata.create_all(engine)
    monkeypatch.setattr(database, "engine", engine)

    from dev import routes as dev_routes

    monkeypatch.setattr(dev_routes, "engine", engine)

    now = datetime.now(timezone.utc)
    payload = {
        "category": "visual_mode",
        "event": "ai_video_downgraded",
        "reason": "Adjacent AI-video scene",
        "severity": "warn",
        "script_id": "script-1",
        "scene_id": "scene-2",
    }
    old_payload = {
        "category": "thumbnail",
        "event": "thumbnail_enhancement_fallback",
        "reason": "Old event outside window",
        "severity": "warn",
    }

    with Session(engine) as session:
        session.add(
            DevLog(
                timestamp=now,
                level="WARNING",
                logger_name="pipeline.media_analyzer",
                message=FALLBACK_PREFIX + json.dumps(payload),
            )
        )
        session.add(
            DevLog(
                timestamp=now,
                level="WARNING",
                logger_name="pipeline.media_analyzer",
                message=FALLBACK_PREFIX + "not-json",
            )
        )
        session.add(
            DevLog(
                timestamp=now - timedelta(hours=30),
                level="WARNING",
                logger_name="pipeline.thumbnail",
                message=FALLBACK_PREFIX + json.dumps(old_payload),
            )
        )
        session.commit()

    response = TestClient(app).get("/dev/api/fallbacks/stats?hours=24")

    assert response.status_code == 200
    data = response.json()
    assert data["window_hours"] == 24
    assert data["total"] == 1
    assert data["malformed_count"] == 1
    assert data["by_category"] == [{"category": "visual_mode", "count": 1}]
    assert data["by_event"] == [
        {
            "category": "visual_mode",
            "event": "ai_video_downgraded",
            "count": 1,
            "severity": "warn",
        }
    ]
    assert data["recent"][0]["script_id"] == "script-1"
    assert data["recent"][0]["scene_id"] == "scene-2"
    assert data["recent"][0]["logger_name"] == "pipeline.media_analyzer"


def test_fallback_stats_endpoint_filters_by_category(monkeypatch, tmp_path):
    import database
    from api import app
    from dev import routes as dev_routes

    engine = create_engine(f"sqlite:///{tmp_path / 'fallbacks.db'}")
    SQLModel.metadata.create_all(engine)
    monkeypatch.setattr(database, "engine", engine)
    monkeypatch.setattr(dev_routes, "engine", engine)

    now = datetime.now(timezone.utc)
    with Session(engine) as session:
        for category in ["visual_mode", "thumbnail"]:
            session.add(
                DevLog(
                    timestamp=now,
                    level="WARNING",
                    logger_name=f"pipeline.{category}",
                    message=FALLBACK_PREFIX
                    + json.dumps(
                        {
                            "category": category,
                            "event": f"{category}_fallback",
                            "reason": "test",
                            "severity": "warn",
                        }
                    ),
                )
            )
        session.commit()

    response = TestClient(app).get("/dev/api/fallbacks/stats?hours=24&category=thumbnail")

    assert response.status_code == 200
    data = response.json()
    assert data["total"] == 1
    assert data["by_category"] == [{"category": "thumbnail", "count": 1}]
```

- [ ] **Step 2: Run endpoint tests and verify they fail**

Run:

```bash
uv run --project backend pytest backend/tests/test_dev_fallback_routes.py -q
```

Expected: FAIL with `404` because `/dev/api/fallbacks/stats` does not exist.

- [ ] **Step 3: Implement the route**

In `backend/dev/routes.py`, import the helper:

```python
from pipeline.fallback_observability import FALLBACK_PREFIX, parse_fallback_message, summarize_fallback_events
```

Add the endpoint after `log_stats()`:

```python
@router.get("/api/fallbacks/stats")
async def fallback_stats(
    hours: int = Query(default=24, ge=1, le=168),
    category: str | None = None,
    limit: int = Query(default=50, ge=1, le=200),
):
    since = datetime.now(timezone.utc) - timedelta(hours=hours)
    with Session(engine) as session:
        rows = session.exec(
            select(DevLog)
            .where(DevLog.timestamp >= since)
            .where(col(DevLog.message).startswith(FALLBACK_PREFIX))
            .order_by(col(DevLog.id).desc())
            .limit(1000)
        ).all()

    events = []
    malformed_count = 0
    for row in rows:
        payload = parse_fallback_message(row.message)
        if payload is None:
            malformed_count += 1
            continue
        if category and payload.get("category") != category:
            continue
        payload.update(
            {
                "id": row.id,
                "timestamp": (row.timestamp.isoformat() + "Z") if row.timestamp else None,
                "logger_name": row.logger_name,
                "level": row.level,
                "module": row.module,
                "func_name": row.func_name,
                "lineno": row.lineno,
            }
        )
        events.append(payload)

    return summarize_fallback_events(
        events,
        window_hours=hours,
        malformed_count=malformed_count,
        recent_limit=limit,
    )
```

- [ ] **Step 4: Run endpoint tests and verify they pass**

Run:

```bash
uv run --project backend pytest backend/tests/test_dev_fallback_routes.py -q
```

Expected: PASS.

## Task 3: Dev Dashboard Fallbacks Tab

**Files:**
- Modify: `backend/dev/dashboard.html`

- [ ] **Step 1: Add tab markup**

In the tab nav, add:

```html
<button onclick="switchTab('fallbacks')" id="tab-fallbacks" class="tab-btn px-4 py-2.5 text-sm font-medium border-b-2 border-transparent text-neutral-500 hover:text-neutral-300 transition-colors">Fallbacks</button>
```

After the Logs panel, add:

```html
<div id="panel-fallbacks" class="hidden h-[calc(100vh-97px)] overflow-y-auto scrollbar-thin p-6">
  <div class="max-w-7xl mx-auto space-y-4">
    <div class="flex items-center justify-between gap-3">
      <div>
        <h2 class="text-sm font-medium text-neutral-100">Fallback Visibility</h2>
        <p class="text-xs text-neutral-500 mt-1">Structured fallback events from generation, rendering, and pipeline recovery paths.</p>
      </div>
      <div class="flex items-center gap-2">
        <select id="fallbackHours" onchange="fetchFallbackStats()" class="bg-surface-800 border border-neutral-700 text-xs rounded px-2 py-1.5 text-neutral-300 focus:outline-none focus:border-violet-500">
          <option value="1">Last hour</option>
          <option value="24" selected>Last 24h</option>
          <option value="168">Last 7d</option>
        </select>
        <select id="fallbackCategory" onchange="fetchFallbackStats()" class="bg-surface-800 border border-neutral-700 text-xs rounded px-2 py-1.5 text-neutral-300 focus:outline-none focus:border-violet-500">
          <option value="">All categories</option>
        </select>
        <button onclick="fetchFallbackStats()" class="text-xs bg-neutral-700 hover:bg-neutral-600 text-neutral-300 px-3 py-1.5 rounded transition-colors">Refresh</button>
      </div>
    </div>

    <div id="fallbackSummaryCards" class="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-3"></div>

    <div class="grid grid-cols-1 lg:grid-cols-3 gap-4">
      <div class="bg-surface-800 border border-neutral-700 rounded-lg p-4">
        <h3 class="text-xs font-medium text-neutral-400 mb-3">By Category</h3>
        <div id="fallbackByCategory" class="space-y-2 text-xs"></div>
      </div>
      <div class="bg-surface-800 border border-neutral-700 rounded-lg p-4">
        <h3 class="text-xs font-medium text-neutral-400 mb-3">By Event</h3>
        <div id="fallbackByEvent" class="space-y-2 text-xs"></div>
      </div>
      <div class="bg-surface-800 border border-neutral-700 rounded-lg p-4">
        <h3 class="text-xs font-medium text-neutral-400 mb-3">Top Reasons</h3>
        <div id="fallbackByReason" class="space-y-2 text-xs"></div>
      </div>
    </div>

    <div class="bg-surface-800 border border-neutral-700 rounded-lg p-4">
      <h3 class="text-xs font-medium text-neutral-400 mb-3">Hot Events</h3>
      <div id="fallbackHotEvents" class="space-y-2 text-xs"></div>
    </div>

    <div class="bg-surface-800 border border-neutral-700 rounded-lg p-4">
      <h3 class="text-xs font-medium text-neutral-400 mb-3">Recent Examples</h3>
      <div id="fallbackRecentTable" class="overflow-x-auto"></div>
    </div>
  </div>
</div>
```

- [ ] **Step 2: Wire tab switching**

Change:

```javascript
const ALL_TABS = ['logs', 'jobs', 'api', 'database', 'usage', 'files'];
```

to:

```javascript
const ALL_TABS = ['logs', 'fallbacks', 'jobs', 'api', 'database', 'usage', 'files'];
```

In `switchTab(tab)`, add:

```javascript
if (tab === 'fallbacks') fetchFallbackStats();
```

- [ ] **Step 3: Add render helpers**

Add near the Stats JavaScript section:

```javascript
const FALLBACK_SEVERITY_COLORS = {
  info: 'bg-sky-600/30 text-sky-400',
  warn: 'bg-amber-600/30 text-amber-400',
  fail: 'bg-red-600/30 text-red-400',
};

async function fetchFallbackStats() {
  const hours = document.getElementById('fallbackHours').value;
  const category = document.getElementById('fallbackCategory').value;
  const params = new URLSearchParams({ hours, limit: '80' });
  if (category) params.set('category', category);

  const res = await fetch('/dev/api/fallbacks/stats?' + params);
  const stats = await res.json();
  renderFallbackStats(stats);
}

function renderFallbackStats(stats) {
  renderFallbackCategoryOptions(stats.by_category || []);
  renderFallbackSummaryCards(stats);
  renderFallbackList('fallbackByCategory', stats.by_category || [], 'category');
  renderFallbackEvents(stats.by_event || []);
  renderFallbackList('fallbackByReason', stats.by_reason || [], 'reason');
  renderFallbackHotEvents(stats.hot_events || []);
  renderFallbackRecent(stats.recent || []);
}

function renderFallbackCategoryOptions(categories) {
  const select = document.getElementById('fallbackCategory');
  const selected = select.value;
  const known = new Set(Array.from(select.options).map(opt => opt.value));
  for (const item of categories) {
    if (!known.has(item.category)) {
      const opt = document.createElement('option');
      opt.value = item.category;
      opt.textContent = item.category;
      select.appendChild(opt);
    }
  }
  select.value = selected;
}

function renderFallbackSummaryCards(stats) {
  const severity = stats.by_severity || {};
  const topCategory = (stats.by_category || [])[0];
  const hot = (stats.hot_events || [])[0];
  const cards = [
    ['Total', stats.total || 0, `${stats.window_hours || 24}h window`],
    ['Warn / Fail', `${severity.warn || 0} / ${severity.fail || 0}`, 'quality-risk events'],
    ['Top Category', topCategory ? topCategory.category : 'None', topCategory ? `${topCategory.count} events` : 'no data'],
    ['Hot Event', hot ? hot.event : 'None', hot ? `${hot.count}x ${hot.severity}` : 'no threshold hit'],
  ];
  document.getElementById('fallbackSummaryCards').innerHTML = cards.map(([label, value, helper]) => `
    <div class="bg-surface-800 border border-neutral-700 rounded-lg p-4">
      <div class="text-[10px] uppercase tracking-wide text-neutral-500">${escapeHtml(label)}</div>
      <div class="mt-1 text-lg font-semibold text-neutral-100 truncate" title="${escapeHtml(String(value))}">${escapeHtml(String(value))}</div>
      <div class="mt-1 text-xs text-neutral-500 truncate">${escapeHtml(helper)}</div>
    </div>
  `).join('');
}

function renderFallbackList(id, rows, labelKey) {
  const target = document.getElementById(id);
  if (!rows.length) {
    target.innerHTML = '<span class="text-neutral-600">No data</span>';
    return;
  }
  const max = Math.max(...rows.map(row => row.count || 0), 1);
  target.innerHTML = rows.slice(0, 10).map(row => {
    const label = row[labelKey] || 'unknown';
    const pct = Math.max(4, Math.round(((row.count || 0) / max) * 100));
    return `
      <div>
        <div class="flex items-center justify-between gap-2">
          <span class="text-neutral-300 truncate" title="${escapeHtml(label)}">${escapeHtml(label)}</span>
          <span class="text-neutral-500">${row.count || 0}</span>
        </div>
        <div class="mt-1 h-1.5 rounded-full bg-surface-900"><div class="h-1.5 rounded-full bg-violet-500" style="width:${pct}%"></div></div>
      </div>
    `;
  }).join('');
}

function renderFallbackEvents(events) {
  const target = document.getElementById('fallbackByEvent');
  if (!events.length) {
    target.innerHTML = '<span class="text-neutral-600">No data</span>';
    return;
  }
  target.innerHTML = events.slice(0, 10).map(item => {
    const cls = FALLBACK_SEVERITY_COLORS[item.severity] || FALLBACK_SEVERITY_COLORS.warn;
    return `
      <div class="flex items-start justify-between gap-3">
        <div class="min-w-0">
          <div class="text-neutral-300 truncate" title="${escapeHtml(item.event)}">${escapeHtml(item.event)}</div>
          <div class="text-[10px] text-neutral-500 truncate">${escapeHtml(item.category || '')}</div>
        </div>
        <div class="flex items-center gap-2 shrink-0">
          <span class="text-neutral-500">${item.count || 0}</span>
          <span class="text-[10px] px-1.5 py-0.5 rounded ${cls}">${escapeHtml(item.severity || 'warn')}</span>
        </div>
      </div>
    `;
  }).join('');
}

function renderFallbackHotEvents(events) {
  const target = document.getElementById('fallbackHotEvents');
  if (!events.length) {
    target.innerHTML = '<span class="text-neutral-600">No hot fallback events in this window</span>';
    return;
  }
  target.innerHTML = events.map(item => {
    const cls = FALLBACK_SEVERITY_COLORS[item.severity] || FALLBACK_SEVERITY_COLORS.warn;
    return `
      <div class="flex items-center justify-between gap-3 border border-neutral-700 rounded px-3 py-2">
        <div class="min-w-0">
          <div class="text-neutral-200 truncate" title="${escapeHtml(item.event)}">${escapeHtml(item.event)}</div>
          <div class="text-[10px] text-neutral-500 truncate">${escapeHtml(item.category || '')}</div>
        </div>
        <div class="flex items-center gap-2 shrink-0">
          <span class="text-neutral-400">${item.count || 0}x</span>
          <span class="text-[10px] px-1.5 py-0.5 rounded ${cls}">${escapeHtml(item.severity || 'warn')}</span>
        </div>
      </div>
    `;
  }).join('');
}

function renderFallbackRecent(rows) {
  const target = document.getElementById('fallbackRecentTable');
  if (!rows.length) {
    target.innerHTML = '<div class="text-neutral-600 text-xs">No fallback events in this window</div>';
    return;
  }
  target.innerHTML = `
    <table class="w-full text-xs">
      <thead class="text-neutral-500 text-left border-b border-neutral-700">
        <tr>
          <th class="py-2 pr-3">Time</th>
          <th class="py-2 pr-3">Severity</th>
          <th class="py-2 pr-3">Category</th>
          <th class="py-2 pr-3">Event</th>
          <th class="py-2 pr-3">Script</th>
          <th class="py-2 pr-3">Scene</th>
          <th class="py-2 pr-3">Reason</th>
          <th class="py-2 pr-3">Module</th>
        </tr>
      </thead>
      <tbody>
        ${rows.map(row => {
          const cls = FALLBACK_SEVERITY_COLORS[row.severity] || FALLBACK_SEVERITY_COLORS.warn;
          const time = row.timestamp ? new Date(row.timestamp).toLocaleTimeString('en-US', {timeZone:'America/Los_Angeles'}) : '';
          return `
            <tr class="border-b border-neutral-800/70 cursor-pointer hover:bg-white/5" onclick='showFallbackDetail(${JSON.stringify(row).replaceAll("'", "&apos;")})'>
              <td class="py-2 pr-3 text-neutral-500 whitespace-nowrap">${time}</td>
              <td class="py-2 pr-3"><span class="text-[10px] px-1.5 py-0.5 rounded ${cls}">${escapeHtml(row.severity || 'warn')}</span></td>
              <td class="py-2 pr-3 text-neutral-300">${escapeHtml(row.category || '')}</td>
              <td class="py-2 pr-3 text-neutral-300">${escapeHtml(row.event || '')}</td>
              <td class="py-2 pr-3 text-neutral-500">${escapeHtml(row.script_id || '')}</td>
              <td class="py-2 pr-3 text-neutral-500">${escapeHtml(row.scene_id || '')}</td>
              <td class="py-2 pr-3 text-neutral-400 max-w-md truncate" title="${escapeHtml(row.reason || '')}">${escapeHtml(row.reason || '')}</td>
              <td class="py-2 pr-3 text-neutral-500">${escapeHtml(row.logger_name || '')}</td>
            </tr>
          `;
        }).join('')}
      </tbody>
    </table>
  `;
}

function showFallbackDetail(row) {
  showDetail({
    level: (row.severity === 'fail' ? 'ERROR' : row.severity === 'info' ? 'INFO' : 'WARNING'),
    timestamp: row.timestamp,
    logger_name: row.logger_name,
    func_name: row.func_name,
    module: row.module,
    lineno: row.lineno,
    message: `[FALLBACK] ${JSON.stringify(row, null, 2)}`,
  });
}
```

- [ ] **Step 4: Manually verify dashboard syntax**

Run:

```bash
node -e "const fs=require('fs'); const html=fs.readFileSync('backend/dev/dashboard.html','utf8'); console.log(html.includes('panel-fallbacks') && html.includes('fetchFallbackStats') ? 'fallback dashboard hooks present' : 'missing hooks')"
```

Expected: `fallback dashboard hooks present`.

## Task 4: Instrument High-Signal Fallbacks

**Files:**
- Modify: `backend/pipeline/media_analyzer.py`
- Modify: `backend/pipeline/image_gen.py`
- Modify: `backend/pipeline/hook_detector.py`
- Modify: `backend/pipeline/thumbnail.py`
- Modify: `backend/pipeline/audio_alignment.py`
- Test: existing tests plus helper tests from Task 1

- [ ] **Step 1: Add imports**

Add to each modified pipeline module:

```python
from pipeline.fallback_observability import record_fallback
```

- [ ] **Step 2: Instrument `media_analyzer.py` downgrades and omissions**

At every branch that changes `mode` from `video` to another mode because `_ai_video_validation_failure(...)` returned a reason, call:

```python
record_fallback(
    category="visual_mode",
    event="ai_video_downgraded",
    reason=downgrade_reason,
    from_value="video",
    to_value=mode,
    script_id=script_id,
    scene_id=scene_id,
    segment_index=segment_index if segment_index >= 0 else None,
    severity="warn",
    metadata={"max_duration_seconds": ai_video_max_duration},
    logger=logger,
)
```

When the validator omits a scene and the code creates a default `MediaAssignment`, call:

```python
record_fallback(
    category="visual_mode",
    event="media_validator_omitted_scene",
    reason=reasoning,
    to_value=mode,
    script_id=script_id,
    scene_id=scene.id,
    segment_index=scene_segment_indexes.get(scene.id),
    severity="info",
    logger=logger,
)
```

In `_remove_adjacent_ai_video_assignments`, after an adjacent scene is changed away from `video`, call:

```python
record_fallback(
    category="visual_mode",
    event="adjacent_ai_video_removed",
    reason=downgrade_reason,
    from_value="video",
    to_value=existing_script_mode or "full_frame",
    script_id=script_content.id if hasattr(script_content, "id") else None,
    scene_id=downgrade_id,
    segment_index=segment_index,
    severity="warn",
    logger=logger,
)
```

If `script_content` has no script id available in this function, omit `script_id`; do not invent one.

- [ ] **Step 3: Instrument `image_gen.py` fallbacks**

When scraper fallback is used:

```python
record_fallback(
    category="image_generation",
    event="scraped_image_fallback_used",
    reason="AI image generation failed after retries",
    from_value=os.environ.get("IMAGE_PROVIDER", "google"),
    to_value="scraped_web_image",
    script_id=script_id,
    scene_id=scene_id,
    severity="fail",
    metadata={"provider": "google_images_scraper", "source_type": "scraped_web_image"},
    logger=logger,
)
```

When placeholder image is created:

```python
record_fallback(
    category="image_generation",
    event="image_placeholder_created",
    reason="AI image generation failed and scraped web-image fallback is disabled or unavailable",
    from_value=os.environ.get("IMAGE_PROVIDER", "google"),
    to_value="local_placeholder",
    script_id=script_id,
    scene_id=scene_id,
    severity="fail",
    metadata={"source_type": "placeholder"},
    logger=logger,
)
```

When popup protagonist anchor fallback is used:

```python
record_fallback(
    category="image_generation",
    event="popup_anchor_transparent_fallback",
    reason=anchor_fallback_reason,
    to_value="transparent_anchor",
    script_id=script_id,
    scene_id=scene_id,
    severity="warn",
    logger=logger,
)
```

- [ ] **Step 4: Instrument `hook_detector.py` fallbacks**

When the LLM call raises:

```python
record_fallback(
    category="hook_detection",
    event="hook_detection_llm_fallback",
    reason="Hook detection LLM call failed",
    to_value="deterministic_count",
    script_id=script_id,
    severity="warn",
    metadata={"fallback_count": fallback_count},
    logger=logger,
)
```

When parsing fails:

```python
record_fallback(
    category="hook_detection",
    event="hook_detection_parse_fallback",
    reason="Hook detector returned non-JSON or non-int",
    to_value="deterministic_count",
    script_id=script_id,
    severity="warn",
    metadata={"fallback_count": fallback_count},
    logger=logger,
)
```

- [ ] **Step 5: Instrument `thumbnail.py` enhancement fallback**

When Gemini enhancement returns `None` because transform failed:

```python
record_fallback(
    category="thumbnail",
    event="thumbnail_enhancement_fallback",
    reason="Gemini thumbnail enhancement failed, using base image",
    from_value="gemini_enhanced",
    to_value="base_image",
    script_id=script_id,
    severity="warn",
    logger=logger,
)
```

If there is an existing branch for split progression with too few levels, instrument it similarly with event `split_thumbnail_clean_image_fallback` and severity `warn`.

- [ ] **Step 6: Instrument `audio_alignment.py` estimated timings**

Before returning `_even_distribution(...)` from `align_audio`, call:

```python
record_fallback(
    category="subtitle_timing",
    event="word_timing_even_distribution",
    reason="Whisper alignment failed or returned no word timestamps",
    to_value="even_distribution",
    severity="warn",
    metadata={"word_count": len(words), "asset_path": audio_path},
    logger=logger,
)
```

If `ffprobe` also fails inside `_even_distribution`, call:

```python
record_fallback(
    category="subtitle_timing",
    event="audio_duration_estimated_from_word_count",
    reason="ffprobe duration lookup failed",
    to_value="word_count_duration_estimate",
    severity="warn",
    metadata={"word_count": len(words), "asset_path": audio_path},
    logger=logger,
)
```

- [ ] **Step 7: Run focused backend tests**

Run:

```bash
uv run --project backend pytest backend/tests/test_fallback_observability.py backend/tests/test_dev_fallback_routes.py backend/tests/test_media_analysis_flags.py backend/tests/test_thumbnail_regenerate.py -q
```

Expected: PASS.

## Task 5: Document The Convention

**Files:**
- Modify: `AGENTS.md`

- [ ] **Step 1: Add convention text**

In `AGENTS.md`, under **Feature UX & Dev Observability**, add:

```markdown
- Meaningful fallback behavior must emit a structured fallback event with `pipeline.fallback_observability.record_fallback` in addition to any local free-text log. This applies to fallbacks that affect generation, rendering, export, integrations, caching, background jobs, visual output, timing, or project quality. Include category, stable event name, reason, severity, and script/scene identifiers when available; never include secrets, full prompts, full script text, OAuth data, or absolute generated asset paths.
```

- [ ] **Step 2: Check docs diff**

Run:

```bash
git diff -- AGENTS.md docs/superpowers/specs/2026-06-05-fallback-observability-design.md
```

Expected: `AGENTS.md` contains the new convention; the already committed spec should be unchanged unless intentional.

## Task 6: Full Verification, Commit, Push, Review Loop

**Files:**
- All files changed by Tasks 1-5.

- [ ] **Step 1: Run backend focused verification**

Run:

```bash
uv run --project backend pytest backend/tests/test_fallback_observability.py backend/tests/test_dev_fallback_routes.py backend/tests/test_media_analysis_flags.py backend/tests/test_thumbnail_regenerate.py -q
```

Expected: PASS.

- [ ] **Step 2: Run frontend/dashboard syntax check**

Run:

```bash
node -e "const fs=require('fs'); const html=fs.readFileSync('backend/dev/dashboard.html','utf8'); console.log(html.includes('panel-fallbacks') && html.includes('fetchFallbackStats') ? 'fallback dashboard hooks present' : 'missing hooks')"
```

Expected: `fallback dashboard hooks present`.

- [ ] **Step 3: Run broader backend tests if focused tests pass**

Run:

```bash
npm run test:backend
```

Expected: PASS.

- [ ] **Step 4: Stage, commit, and push**

Run:

```bash
git status --short
git add AGENTS.md backend/dev/routes.py backend/dev/dashboard.html backend/pipeline/fallback_observability.py backend/pipeline/media_analyzer.py backend/pipeline/image_gen.py backend/pipeline/hook_detector.py backend/pipeline/thumbnail.py backend/pipeline/audio_alignment.py backend/tests/test_fallback_observability.py backend/tests/test_dev_fallback_routes.py docs/superpowers/plans/2026-06-05-fallback-observability.md
git commit -m "Add fallback observability dashboard"
git push origin main
```

Expected: commit succeeds and push updates `main`.

- [ ] **Step 5: Dispatch delegated code review**

Use Codex agent delegation tooling with this prompt:

```text
Review the most recent commit on the main branch of this project.
Run `git diff HEAD~1..HEAD` to see the changes and `git show --stat HEAD` for context.
Read the full affected files (not just the diff) to understand surrounding code.
Check for: correctness bugs, error handling gaps, security issues, naive/aware datetime mismatches, unhandled promise rejections, race conditions, and style problems.
Return a structured verdict: either LGTM or NEEDS CHANGES.
If NEEDS CHANGES, provide a numbered list of findings with severity (FAIL/WARN), file:line, and a specific description of what's wrong and how to fix it.
```

- [ ] **Step 6: Apply review findings internally**

If review verdict is `NEEDS CHANGES`, implement every FAIL then WARN finding, commit as:

```bash
git commit -m "fix: address review findings"
git push origin main
```

Then dispatch the same review prompt again. Repeat until the delegated review returns `LGTM`.

Only after `LGTM`, summarize what changed and what the review caught.

## Self-Review Checklist

- Spec coverage: helper, endpoint, dashboard, initial instrumentation, tests, and `AGENTS.md` convention are all represented.
- Scope: full analytics dashboard follow-ups are intentionally excluded from this implementation plan.
- TDD: helper and endpoint tasks start with failing tests before implementation.
- Commands: all Python commands use `uv` or `npm run test:backend`; no direct `python`, `python3`, `pip`, or `pip3`.
- Sensitive data: helper filters metadata and the convention forbids secrets, full prompts, full script text, OAuth data, and absolute generated asset paths.
