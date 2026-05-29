"""Google Trends fetcher using official RSS feed + pytrends related queries."""

import logging
import signal
import time

import feedparser
import requests as req_lib

logger = logging.getLogger(__name__)

GOOGLE_TRENDS_RSS = "https://trends.google.com/trending/rss?geo=US"

# Module-level cache (30-minute TTL)
_cache: list[dict] | None = None
_cache_ts: float = 0.0
_CACHE_TTL = 1800.0


class _Timeout(Exception):
    pass


def _timeout_handler(_signum, frame):
    raise _Timeout("pytrends timed out")


def _fetch_trending_rss() -> list[dict]:
    """Fetch trending searches via Google Trends RSS (replaces broken pytrends.trending_searches)."""
    topics: list[dict] = []
    try:
        resp = req_lib.get(
            GOOGLE_TRENDS_RSS,
            timeout=15.0,
            proxies={"http": None, "https": None, "http://": None, "https://": None},
        )
        resp.raise_for_status()
        feed = feedparser.parse(resp.content)
        for entry in feed.entries:
            title = entry.get("title", "").strip()
            if title:
                topics.append({
                    "title": title,
                    "source": "google_trends",
                    "raw_data": {
                        "sub_source": "trending_rss",
                        "link": entry.get("link", ""),
                    },
                    "search_velocity": 50.0,
                    "competitor_view_rate": 0.0,
                    "reddit_engagement": 0.0,
                    "is_breakout": False,
                })
    except Exception:
        logger.warning("Failed to fetch Google Trends RSS", exc_info=True)
    return topics


def fetch_google_trends_topics() -> list[dict]:
    """Fetch trending topics from Google Trends. Rate-limited; may return empty."""
    global _cache, _cache_ts

    if _cache is not None and (time.time() - _cache_ts) < _CACHE_TTL:
        logger.info("Google Trends fetcher returning cached %d topics", len(_cache))
        return list(_cache)

    logger.info("Fetching trending topics from Google Trends")
    topics: list[dict] = []

    topics.extend(_fetch_trending_rss())

    # Set 30-second timeout — if pytrends hangs, bail immediately
    old_handler = None
    try:
        old_handler = signal.signal(signal.SIGALRM, _timeout_handler)
        signal.alarm(30)
    except (ValueError, OSError):
        pass  # Not on main thread or no SIGALRM support

    try:
        from pytrends.request import TrendReq

        pytrends = TrendReq(hl="en-US", tz=360, requests_args={
            "proxies": {"http": None, "https": None, "http://": None, "https://": None},
        })

        seed_keywords = [
            "science explained",
            "psychology facts",
            "history documentary",
            "how things work",
        ]
        for keyword in seed_keywords:
            try:
                pytrends.build_payload([keyword], timeframe="now 7-d")
                related = pytrends.related_queries()
                if keyword in related:
                    rising = related[keyword].get("rising")
                    if rising is not None and not rising.empty:
                        for _, row in rising.iterrows():
                            query = str(row.get("query", "")).strip()
                            value = float(row.get("value", 0))
                            if not query:
                                continue
                            is_breakout = value >= 5000
                            velocity = min(100.0, value / 50.0) if not is_breakout else 100.0
                            topics.append({
                                "title": query,
                                "source": "google_trends",
                                "raw_data": {
                                    "sub_source": "related_rising",
                                    "seed_keyword": keyword,
                                    "rise_percentage": value,
                                },
                                "search_velocity": velocity,
                                "competitor_view_rate": 0.0,
                                "reddit_engagement": 0.0,
                                "is_breakout": is_breakout,
                            })
            except Exception:
                logger.warning("Failed to get related queries for %r", keyword, exc_info=True)

    except _Timeout:
        logger.warning("Google Trends fetcher timed out after 30s — returning empty")
        if topics:
            _cache = list(topics)
            _cache_ts = time.time()
        return topics
    except Exception:
        logger.warning("Google Trends pytrends fetcher failed", exc_info=True)
    finally:
        try:
            signal.alarm(0)
            if old_handler is not None:
                signal.signal(signal.SIGALRM, old_handler)
        except (ValueError, OSError):
            pass

    if topics:
        _cache = list(topics)
        _cache_ts = time.time()
    logger.info("Google Trends fetcher returned %d topics", len(topics))
    return topics
