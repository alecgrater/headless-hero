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
    "attempt",
    "cap",
    "count",
    "duration_seconds",
    "fallback_count",
    "max_duration_seconds",
    "model",
    "provider",
    "segment_index",
    "source_type",
    "word_count",
}

FALLBACK_OUTCOME_SPECS = {
    ("visual_mode", "flipflop_invalid_micro_action_downgraded"): {
        "success_event": "flipflop_assignment_succeeded",
        "success_logger": "pipeline.visual_treatments",
        "success_message_contains": ("[ANIMATION_TYPE]", "animation_type=flipflop"),
    },
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
    outcome_counts: dict[tuple[str, str], int] | None = None,
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

    outcome_counts = outcome_counts or {}
    by_event = []
    for (category, event), count in event_counts.most_common():
        item: dict[str, Any] = {
            "category": category,
            "event": event,
            "count": count,
            "severity": event_severities[(category, event)],
        }
        spec = FALLBACK_OUTCOME_SPECS.get((category, event))
        if spec is not None:
            success_count = max(0, int(outcome_counts.get((category, event), 0)))
            attempt_count = success_count + count
            item.update(
                {
                    "fallback_count": count,
                    "success_count": success_count,
                    "attempt_count": attempt_count,
                    "success_rate": round(success_count / attempt_count, 4) if attempt_count else 0,
                    "fallback_rate": round(count / attempt_count, 4) if attempt_count else 0,
                    "success_event": spec["success_event"],
                }
            )
        by_event.append(item)

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
