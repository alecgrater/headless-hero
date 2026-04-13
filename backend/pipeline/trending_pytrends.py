"""Google Trends fetcher using pytrends."""

import logging

logger = logging.getLogger(__name__)


def fetch_google_trends_topics() -> list[dict]:
    """Fetch trending topics from Google Trends. Rate-limited; may return empty."""
    logger.info("Fetching trending topics from Google Trends")
    topics: list[dict] = []

    try:
        from pytrends.request import TrendReq

        pytrends = TrendReq(hl="en-US", tz=360)

        # Fetch trending searches (real-time trending)
        try:
            trending_df = pytrends.trending_searches(pn="united_states")
            for _, row in trending_df.iterrows():
                title = str(row.iloc[0]).strip()
                if title:
                    topics.append({
                        "title": title,
                        "source": "google_trends",
                        "raw_data": {"sub_source": "trending_searches"},
                        "search_velocity": 50.0,  # baseline for trending searches
                        "competitor_view_rate": 0.0,
                        "reddit_engagement": 0.0,
                        "is_breakout": False,
                    })
        except Exception:
            logger.warning("Failed to fetch trending searches", exc_info=True)

        # Fetch related queries for education-relevant seed keywords
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
                            # Normalize: cap at 100, breakout gets 100
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

    except Exception:
        logger.warning("Google Trends fetcher failed entirely", exc_info=True)
        return []

    logger.info("Google Trends fetcher returned %d topics", len(topics))
    return topics
