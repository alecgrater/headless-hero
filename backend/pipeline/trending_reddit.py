"""Reddit trending topics fetcher using public JSON API."""

import logging
import time

import requests

logger = logging.getLogger(__name__)

# Education-adjacent subreddits
SUBREDDITS = [
    "psychology",
    "productivity",
    "YouShouldKnow",
    "explainlikeimfive",
    "science",
    "selfimprovement",
]

HEADERS = {"User-Agent": "HeadlessHero/1.0"}
TIMEOUT = 15.0
# Bypass env-var proxy — these are public API calls that don't need proxying
NO_PROXY = {"http": None, "https": None, "http://": None, "https://": None}


def _fetch_subreddit(sub: str, sort: str, limit: int = 25) -> list[dict]:
    """Fetch posts from a subreddit's JSON endpoint."""
    url = f"https://www.reddit.com/r/{sub}/{sort}.json?limit={limit}"
    try:
        resp = requests.get(url, headers=HEADERS, timeout=TIMEOUT, proxies=NO_PROXY)
        resp.raise_for_status()
        data = resp.json()
        return data.get("data", {}).get("children", [])
    except Exception:
        logger.warning("Failed to fetch r/%s/%s", sub, sort, exc_info=True)
        return []


def fetch_reddit_topics() -> list[dict]:
    """Fetch trending topics from Reddit. No API key needed."""
    logger.info("Fetching trending topics from Reddit")
    cutoff = time.time() - 86400  # last 24 hours
    raw_posts: list[dict] = []

    for sub in SUBREDDITS:
        for sort in ["rising", "hot"]:
            children = _fetch_subreddit(sub, sort)
            for child in children:
                post = child.get("data", {})
                created = post.get("created_utc", 0)
                if created < cutoff:
                    continue
                upvotes = max(1, post.get("ups", 1))
                comments = post.get("num_comments", 0)
                # Score: upvotes weighted by comment engagement ratio
                engagement = upvotes * (1 + comments / upvotes)
                raw_posts.append({
                    "title": post.get("title", ""),
                    "subreddit": sub,
                    "upvotes": upvotes,
                    "comments": comments,
                    "engagement": engagement,
                    "url": f"https://reddit.com{post.get('permalink', '')}",
                    "created_utc": created,
                })
            # Be polite to Reddit's public API
            time.sleep(0.5)

    if not raw_posts:
        logger.info("Reddit fetcher returned 0 topics")
        return []

    # Normalize engagement scores to 0-100
    max_engagement = max(p["engagement"] for p in raw_posts)
    topics = []
    for post in raw_posts:
        normalized = (post["engagement"] / max_engagement * 100) if max_engagement > 0 else 0.0
        topics.append({
            "title": post["title"],
            "source": "reddit",
            "raw_data": {
                "subreddit": post["subreddit"],
                "upvotes": post["upvotes"],
                "comments": post["comments"],
                "url": post["url"],
            },
            "search_velocity": 0.0,
            "competitor_view_rate": 0.0,
            "reddit_engagement": min(100.0, normalized),
            "is_breakout": False,
        })

    logger.info("Reddit fetcher returned %d topics", len(topics))
    return topics
