"""Stack Exchange hot questions fetcher. No API key needed (300 req/day limit)."""

import logging
import time

import requests

logger = logging.getLogger(__name__)

# Education-relevant Stack Exchange sites
SITES = [
    "stackoverflow",
    "physics",
    "biology",
    "history",
    "psychology",
    "philosophy",
    "space",
]

TIMEOUT = 10.0
NO_PROXY = {"http": None, "https": None, "http://": None, "https://": None}

# Module-level cache (15-minute TTL)
_cache: list[dict] | None = None
_cache_ts: float = 0.0
_CACHE_TTL = 900.0


def fetch_stackexchange_topics() -> list[dict]:
    """Fetch hot questions from multiple Stack Exchange sites. No API key needed."""
    global _cache, _cache_ts

    if _cache is not None and (time.time() - _cache_ts) < _CACHE_TTL:
        logger.info("Stack Exchange fetcher returning cached %d topics", len(_cache))
        return list(_cache)

    logger.info("Fetching trending topics from Stack Exchange")

    raw_questions: list[dict] = []
    for site in SITES:
        try:
            resp = requests.get(
                "https://api.stackexchange.com/2.3/questions",
                params={
                    "order": "desc",
                    "sort": "hot",
                    "site": site,
                    "pagesize": 15,
                    "filter": "default",
                },
                timeout=TIMEOUT,
                proxies=NO_PROXY,
            )
            resp.raise_for_status()
            data = resp.json()
            for q in data.get("items", []):
                raw_questions.append({
                    "title": q.get("title", ""),
                    "site": site,
                    "view_count": q.get("view_count", 0),
                    "answer_count": q.get("answer_count", 0),
                    "score": q.get("score", 0),
                    "link": q.get("link", ""),
                    "tags": q.get("tags", []),
                })
        except Exception:
            logger.warning("Stack Exchange fetch failed for %s", site, exc_info=True)
        time.sleep(0.05)

    if not raw_questions:
        logger.info("Stack Exchange fetcher returned 0 questions")
        return []

    # Score: view_count * (answer_count + 1) — engagement signal
    for q in raw_questions:
        q["engagement"] = q["view_count"] * (q["answer_count"] + 1)

    max_engagement = max(q["engagement"] for q in raw_questions) or 1

    topics = []
    for q in raw_questions:
        normalized = (q["engagement"] / max_engagement * 100) if max_engagement > 0 else 0.0
        topics.append({
            "title": q["title"],
            "source": "stackexchange",
            "raw_data": {
                "site": q["site"],
                "view_count": q["view_count"],
                "answer_count": q["answer_count"],
                "score": q["score"],
                "link": q["link"],
                "tags": q["tags"][:5],
            },
            "search_velocity": 0.0,
            "competitor_view_rate": 0.0,
            "reddit_engagement": min(100.0, normalized),  # Community discussion signal
            "is_breakout": False,
        })

    _cache = list(topics)
    _cache_ts = time.time()
    logger.info("Stack Exchange fetcher returned %d topics", len(topics))
    return topics
