"""YouTube trending topics fetcher using YouTube Data API v3."""

import logging
import math
import os
from datetime import datetime, timedelta, timezone

logger = logging.getLogger(__name__)

# Educational/explainer channels to track for competitor velocity
COMPETITOR_CHANNELS = [
    "Everything Professor",
    "Vsauce",
    "Kurzgesagt",
    "Veritasium",
    "TED-Ed",
    "Wendover Productions",
    "CGP Grey",
]

# YouTube category IDs: 27=Education, 26=Howto & Style
EDUCATION_CATEGORY = "27"
HOWTO_CATEGORY = "26"


def _get_youtube_client():
    """Build a YouTube Data API v3 client."""
    api_key = os.environ.get("YOUTUBE_API_KEY")
    if not api_key:
        return None
    from googleapiclient.discovery import build
    return build("youtube", "v3", developerKey=api_key)


def _resolve_channel_ids(youtube, channel_names: list[str]) -> dict[str, str]:
    """Resolve channel names to IDs. Uses AppSetting cache."""
    from database import engine
    from models.settings import AppSetting
    from sqlmodel import Session

    resolved: dict[str, str] = {}
    to_lookup: list[str] = []

    with Session(engine) as session:
        for name in channel_names:
            cache_key = f"_yt_channel_id:{name}"
            setting = session.get(AppSetting, cache_key)
            if setting and setting.value:
                resolved[name] = setting.value
            else:
                to_lookup.append(name)

    for name in to_lookup:
        try:
            resp = youtube.search().list(q=name, type="channel", part="snippet", maxResults=1).execute()
            items = resp.get("items", [])
            if items:
                channel_id = items[0]["snippet"]["channelId"]
                resolved[name] = channel_id
                with Session(engine) as session:
                    cache_key = f"_yt_channel_id:{name}"
                    existing = session.get(AppSetting, cache_key)
                    if existing:
                        existing.value = channel_id
                    else:
                        session.add(AppSetting(key=cache_key, value=channel_id))
                    session.commit()
        except Exception:
            logger.warning("Failed to resolve channel ID for %s", name, exc_info=True)

    return resolved


def _fetch_most_popular(youtube) -> list[dict]:
    """Fetch trending education/how-to videos."""
    topics = []
    for cat_id in [EDUCATION_CATEGORY, HOWTO_CATEGORY]:
        try:
            resp = youtube.videos().list(
                chart="mostPopular",
                videoCategoryId=cat_id,
                part="snippet,statistics",
                regionCode="US",
                maxResults=25,
            ).execute()
            for item in resp.get("items", []):
                snippet = item["snippet"]
                stats = item.get("statistics", {})
                topics.append({
                    "title": snippet["title"],
                    "source": "youtube",
                    "raw_data": {
                        "sub_source": "most_popular",
                        "category": cat_id,
                        "channel": snippet.get("channelTitle", ""),
                        "view_count": int(stats.get("viewCount", 0)),
                        "published_at": snippet.get("publishedAt", ""),
                    },
                    "search_velocity": 0.0,
                    "competitor_view_rate": 0.0,
                    "reddit_engagement": 0.0,
                    "is_breakout": False,
                })
        except Exception:
            logger.warning("Failed to fetch mostPopular for category %s", cat_id, exc_info=True)
    return topics


def _fetch_exploding_recent(youtube) -> list[dict]:
    """Fetch recently exploding education videos."""
    topics = []
    after = (datetime.now(timezone.utc) - timedelta(days=14)).strftime("%Y-%m-%dT%H:%M:%SZ")
    try:
        resp = youtube.search().list(
            order="viewCount",
            publishedAfter=after,
            type="video",
            videoCategoryId=EDUCATION_CATEGORY,
            part="snippet",
            maxResults=25,
            regionCode="US",
        ).execute()
        video_ids = [item["id"]["videoId"] for item in resp.get("items", []) if item["id"].get("videoId")]
        if video_ids:
            stats_resp = youtube.videos().list(
                id=",".join(video_ids),
                part="snippet,statistics",
            ).execute()
            for item in stats_resp.get("items", []):
                snippet = item["snippet"]
                stats = item.get("statistics", {})
                views = int(stats.get("viewCount", 0))
                published = snippet.get("publishedAt", "")
                days_old = 1
                if published:
                    try:
                        pub_dt = datetime.fromisoformat(published.replace("Z", "+00:00"))
                        days_old = max(1, (datetime.now(timezone.utc) - pub_dt).days)
                    except ValueError:
                        pass
                velocity = views / days_old
                topics.append({
                    "title": snippet["title"],
                    "source": "youtube",
                    "raw_data": {
                        "sub_source": "exploding_recent",
                        "channel": snippet.get("channelTitle", ""),
                        "view_count": views,
                        "velocity": velocity,
                        "days_old": days_old,
                        "published_at": published,
                    },
                    "search_velocity": 0.0,
                    "competitor_view_rate": 0.0,
                    "reddit_engagement": 0.0,
                    "is_breakout": False,
                })
    except Exception:
        logger.warning("Failed to fetch exploding recent videos", exc_info=True)
    return topics


def _fetch_competitor_velocity(youtube) -> list[dict]:
    """Check competitor channels for recent uploads and their velocity."""
    topics = []
    channel_ids = _resolve_channel_ids(youtube, COMPETITOR_CHANNELS)
    after = (datetime.now(timezone.utc) - timedelta(days=14)).strftime("%Y-%m-%dT%H:%M:%SZ")

    velocities: list[float] = []
    raw_items: list[dict] = []

    for _name, channel_id in channel_ids.items():
        try:
            resp = youtube.search().list(
                channelId=channel_id,
                order="date",
                publishedAfter=after,
                type="video",
                part="snippet",
                maxResults=10,
            ).execute()
            video_ids = [item["id"]["videoId"] for item in resp.get("items", []) if item["id"].get("videoId")]
            if not video_ids:
                continue
            stats_resp = youtube.videos().list(
                id=",".join(video_ids),
                part="snippet,statistics",
            ).execute()
            for item in stats_resp.get("items", []):
                snippet = item["snippet"]
                stats = item.get("statistics", {})
                views = int(stats.get("viewCount", 0))
                published = snippet.get("publishedAt", "")
                days_old = 1
                if published:
                    try:
                        pub_dt = datetime.fromisoformat(published.replace("Z", "+00:00"))
                        days_old = max(1, (datetime.now(timezone.utc) - pub_dt).days)
                    except ValueError:
                        pass
                velocity = views / days_old
                velocities.append(velocity)
                raw_items.append({
                    "title": snippet["title"],
                    "channel": snippet.get("channelTitle", ""),
                    "views": views,
                    "velocity": velocity,
                    "days_old": days_old,
                    "published_at": published,
                })
        except Exception:
            logger.warning("Failed to fetch competitor channel %s", channel_id, exc_info=True)

    # Normalize velocities to 0-100 using log scale
    if velocities:
        log_vels = [math.log1p(v) for v in velocities]
        max_log = max(log_vels) if log_vels else 1.0
        for i, item in enumerate(raw_items):
            normalized = (math.log1p(item["velocity"]) / max_log * 100) if max_log > 0 else 0.0
            topics.append({
                "title": item["title"],
                "source": "youtube",
                "raw_data": {
                    "sub_source": "competitor_velocity",
                    "channel": item["channel"],
                    "view_count": item["views"],
                    "velocity": item["velocity"],
                    "days_old": item["days_old"],
                    "published_at": item["published_at"],
                },
                "search_velocity": 0.0,
                "competitor_view_rate": min(100.0, normalized),
                "reddit_engagement": 0.0,
                "is_breakout": False,
            })
    return topics


def check_saturation(youtube, title: str) -> bool:
    """Check if a topic is already saturated on YouTube (>20 recent videos)."""
    after = (datetime.now(timezone.utc) - timedelta(days=21)).strftime("%Y-%m-%dT%H:%M:%SZ")
    try:
        resp = youtube.search().list(
            q=title,
            publishedAfter=after,
            type="video",
            part="id",
            maxResults=25,
        ).execute()
        total = resp.get("pageInfo", {}).get("totalResults", 0)
        return total > 20
    except Exception:
        logger.warning("Saturation check failed for %r", title, exc_info=True)
        return False


def fetch_youtube_topics() -> list[dict]:
    """Fetch trending topics from YouTube. Returns empty list if no API key."""
    youtube = _get_youtube_client()
    if not youtube:
        logger.warning("YOUTUBE_API_KEY not set — skipping YouTube fetch")
        return []

    logger.info("Fetching trending topics from YouTube")
    topics: list[dict] = []
    topics.extend(_fetch_most_popular(youtube))
    topics.extend(_fetch_exploding_recent(youtube))
    topics.extend(_fetch_competitor_velocity(youtube))
    logger.info("YouTube fetcher returned %d raw topics", len(topics))
    return topics
