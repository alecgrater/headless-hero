"""News/RSS trending topics fetcher using NewsAPI + feedparser."""

import logging
import os
import time
from datetime import datetime, timedelta, timezone

import feedparser

logger = logging.getLogger(__name__)

# RSS feeds for science/education content
RSS_FEEDS = [
    "https://www.scientificamerican.com/feed/",
    "https://www.psychologytoday.com/us/blog/feed",
    "https://feeds.arstechnica.com/arstechnica/science",
    "https://api.quantamagazine.org/feed/",
    "https://www.smithsonianmag.com/rss/latest_articles/",
    "https://www.newscientist.com/section/news/feed/",
]


def _fetch_newsapi() -> list[dict]:
    """Fetch from NewsAPI. Requires NEWS_API_KEY."""
    api_key = os.environ.get("NEWS_API_KEY")
    if not api_key:
        logger.info("NEWS_API_KEY not set — skipping NewsAPI")
        return []

    topics = []
    try:
        from newsapi import NewsApiClient

        newsapi = NewsApiClient(api_key=api_key)
        from_date = (datetime.now(timezone.utc) - timedelta(days=3)).strftime("%Y-%m-%d")
        resp = newsapi.get_everything(
            q="science OR psychology OR health OR technology",
            sort_by="publishedAt",
            from_param=from_date,
            language="en",
            page_size=50,
        )
        for article in resp.get("articles", []):
            title = article.get("title", "")
            if not title or title == "[Removed]":
                continue
            topics.append({
                "title": title,
                "source": "news",
                "raw_data": {
                    "sub_source": "newsapi",
                    "source_name": article.get("source", {}).get("name", ""),
                    "description": article.get("description", ""),
                    "url": article.get("url", ""),
                    "published_at": article.get("publishedAt", ""),
                },
                "search_velocity": 0.0,
                "competitor_view_rate": 0.0,
                "reddit_engagement": 0.0,
                "is_breakout": False,
            })
    except Exception:
        logger.warning("NewsAPI fetch failed", exc_info=True)

    return topics


def _fetch_rss() -> list[dict]:
    """Fetch from hardcoded RSS feeds. No API key needed."""
    topics = []
    cutoff = datetime.now(timezone.utc) - timedelta(days=3)

    for feed_url in RSS_FEEDS:
        try:
            feed = feedparser.parse(feed_url)
            for entry in feed.entries:
                # Check publication date
                published = entry.get("published_parsed") or entry.get("updated_parsed")
                if published:
                    pub_dt = datetime(*published[:6], tzinfo=timezone.utc)
                    if pub_dt < cutoff:
                        continue

                title = entry.get("title", "").strip()
                if not title:
                    continue

                topics.append({
                    "title": title,
                    "source": "news",
                    "raw_data": {
                        "sub_source": "rss",
                        "feed": feed_url,
                        "summary": entry.get("summary", "")[:200],
                        "link": entry.get("link", ""),
                    },
                    "search_velocity": 0.0,
                    "competitor_view_rate": 0.0,
                    "reddit_engagement": 0.0,
                    "is_breakout": False,
                })
        except Exception:
            logger.warning("RSS fetch failed for %s", feed_url, exc_info=True)
        time.sleep(0.3)

    return topics


def fetch_news_topics() -> list[dict]:
    """Fetch trending topics from NewsAPI and RSS feeds."""
    logger.info("Fetching trending topics from News/RSS")
    topics: list[dict] = []
    topics.extend(_fetch_newsapi())
    topics.extend(_fetch_rss())
    logger.info("News fetcher returned %d topics", len(topics))
    return topics
