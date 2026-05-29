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
    if dt.tzinfo is None or dt.tzinfo.utcoffset(dt) is None:
        dt = dt.replace(tzinfo=timezone.utc)
    value = dt.astimezone(timezone.utc)
    return value.replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _safe_int(value: Any) -> int:
    try:
        return int(value or 0)
    except (TypeError, ValueError):
        return 0


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
        "script_count": _safe_int(profile.get("script_count")),
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
