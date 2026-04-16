"""Wikipedia most-read articles fetcher using Wikimedia REST API. No API key needed."""

import logging
import time
from datetime import datetime, timedelta, timezone

import requests

logger = logging.getLogger(__name__)

WIKI_BASE = "https://wikimedia.org/api/rest_v1"
HEADERS = {"User-Agent": "HeadlessHero/1.0 (educational content tool)"}
TIMEOUT = 15.0
NO_PROXY = {"http": None, "https": None, "http://": None, "https://": None}

# Meta pages to exclude
_META_PAGES = {
    "Main_Page", "Special:Search", "Wikipedia:Featured_articles",
    "-", "Wikipedia", "Portal:Current_events",
}

# Module-level cache (15-minute TTL)
_cache: list[dict] | None = None
_cache_ts: float = 0.0
_CACHE_TTL = 900.0


def _fetch_daily_views(article: str, days: int = 7) -> list[int]:
    """Fetch daily pageviews for an article over the past N days."""
    end = datetime.now(timezone.utc) - timedelta(days=1)
    start = end - timedelta(days=days - 1)
    url = (
        f"{WIKI_BASE}/metrics/pageviews/per-article/en.wikipedia/all-access/all-agents/"
        f"{article}/daily/{start:%Y%m%d}/{end:%Y%m%d}"
    )
    try:
        resp = requests.get(url, headers=HEADERS, timeout=TIMEOUT, proxies=NO_PROXY)
        resp.raise_for_status()
        items = resp.json().get("items", [])
        return [item.get("views", 0) for item in items]
    except Exception:
        return []


def fetch_wikipedia_topics() -> list[dict]:
    """Fetch most-read Wikipedia articles from yesterday. Detect breakouts via 7-day spike."""
    global _cache, _cache_ts

    if _cache is not None and (time.time() - _cache_ts) < _CACHE_TTL:
        logger.info("Wikipedia fetcher returning cached %d topics", len(_cache))
        return list(_cache)

    logger.info("Fetching trending topics from Wikipedia most-read")

    yesterday = datetime.now(timezone.utc) - timedelta(days=1)
    url = (
        f"{WIKI_BASE}/metrics/pageviews/top/en.wikipedia/all-access/"
        f"{yesterday:%Y}/{yesterday:%m}/{yesterday:%d}"
    )

    try:
        resp = requests.get(url, headers=HEADERS, timeout=TIMEOUT, proxies=NO_PROXY)
        resp.raise_for_status()
        data = resp.json()
    except Exception:
        logger.warning("Wikipedia most-read fetch failed", exc_info=True)
        return []

    articles_raw = []
    for item in data.get("items", [{}]):
        for article in item.get("articles", []):
            title = article.get("article", "")
            if title in _META_PAGES or title.startswith(("Special:", "Wikipedia:", "File:", "Template:", "Help:", "Category:", "Portal:")):
                continue
            articles_raw.append({
                "title": title.replace("_", " "),
                "views": article.get("views", 0),
                "rank": article.get("rank", 999),
            })

    # Keep top 50
    candidates = articles_raw[:50]
    if not candidates:
        logger.info("Wikipedia fetcher: no articles found")
        return []

    # Normalize views to 0-100
    max_views = max(a["views"] for a in candidates)

    # Spike detection for top 30: fetch 7-day daily views
    breakout_titles: set[str] = set()
    for article in candidates[:30]:
        raw_title = article["title"].replace(" ", "_")
        daily = _fetch_daily_views(raw_title)
        if len(daily) >= 2:
            avg_prior = sum(daily[:-1]) / max(1, len(daily) - 1)
            yesterday_views = daily[-1]
            if avg_prior > 0 and yesterday_views > 3 * avg_prior:
                breakout_titles.add(article["title"])
        time.sleep(0.05)  # Be polite to Wikimedia

    topics = []
    for article in candidates:
        normalized = (article["views"] / max_views * 100) if max_views > 0 else 0.0
        topics.append({
            "title": article["title"],
            "source": "wikipedia",
            "raw_data": {
                "views": article["views"],
                "rank": article["rank"],
            },
            "search_velocity": min(100.0, normalized),
            "competitor_view_rate": 0.0,
            "reddit_engagement": 0.0,
            "is_breakout": article["title"] in breakout_titles,
        })

    _cache = list(topics)
    _cache_ts = time.time()
    logger.info("Wikipedia fetcher returned %d topics (%d breakouts)", len(topics), len(breakout_titles))
    return topics
