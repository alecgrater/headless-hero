"""Hacker News trending topics fetcher using Firebase API. No API key needed."""

import logging
import time
from concurrent.futures import ThreadPoolExecutor

import requests

logger = logging.getLogger(__name__)

HN_BASE = "https://hacker-news.firebaseio.com/v0"
TIMEOUT = 10.0
NO_PROXY = {"http": None, "https": None, "http://": None, "https://": None}

# Module-level cache (15-minute TTL)
_cache: list[dict] | None = None
_cache_ts: float = 0.0
_CACHE_TTL = 900.0


def _fetch_item(item_id: int) -> dict | None:
    """Fetch a single HN item by ID."""
    try:
        resp = requests.get(
            f"{HN_BASE}/item/{item_id}.json",
            timeout=TIMEOUT,
            proxies=NO_PROXY,
        )
        resp.raise_for_status()
        return resp.json()
    except Exception:
        return None


def fetch_hackernews_topics() -> list[dict]:
    """Fetch trending topics from Hacker News top + best stories."""
    global _cache, _cache_ts

    if _cache is not None and (time.time() - _cache_ts) < _CACHE_TTL:
        logger.info("HN fetcher returning cached %d topics", len(_cache))
        return list(_cache)

    logger.info("Fetching trending topics from Hacker News")

    # Fetch top and best story IDs
    all_ids: set[int] = set()
    for endpoint in ("topstories", "beststories"):
        try:
            resp = requests.get(
                f"{HN_BASE}/{endpoint}.json",
                timeout=TIMEOUT,
                proxies=NO_PROXY,
            )
            resp.raise_for_status()
            ids = resp.json()[:30]
            all_ids.update(ids)
        except Exception:
            logger.warning("Failed to fetch HN %s", endpoint, exc_info=True)

    if not all_ids:
        logger.info("HN fetcher returned 0 story IDs")
        return []

    # Fetch item details in parallel
    items: list[dict] = []
    with ThreadPoolExecutor(max_workers=10) as executor:
        results = executor.map(_fetch_item, all_ids)
        for item in results:
            if item and item.get("type") == "story" and item.get("title"):
                items.append(item)

    # Filter to last 48 hours
    cutoff = time.time() - 48 * 3600
    recent = [i for i in items if i.get("time", 0) >= cutoff]

    if not recent:
        logger.info("HN fetcher: no recent stories in last 48h")
        return []

    # Normalize score to 0-100
    max_score = max(i.get("score", 1) for i in recent)
    topics = []
    for item in recent:
        score = item.get("score", 0)
        normalized = (score / max_score * 100) if max_score > 0 else 0.0
        topics.append({
            "title": item["title"],
            "source": "hackernews",
            "raw_data": {
                "hn_id": item.get("id"),
                "score": score,
                "comments": item.get("descendants", 0),
                "url": item.get("url", f"https://news.ycombinator.com/item?id={item.get('id')}"),
            },
            "search_velocity": min(100.0, normalized),
            "competitor_view_rate": 0.0,
            "reddit_engagement": 0.0,
            "is_breakout": score > 500,
        })

    _cache = list(topics)
    _cache_ts = time.time()
    logger.info("HN fetcher returned %d topics", len(topics))
    return topics
