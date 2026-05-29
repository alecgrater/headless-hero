#!/usr/bin/env python3
"""Find YouTube whitespace channels from a Headless Hero discovery seed."""

from __future__ import annotations

import argparse
import json
import math
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

MAX_VIDEOS = 10
MIN_TOTAL_VIEWS = 200_000
MIN_VIEWS_PER_VIDEO = 100_000
TOP_RESULTS = 20


def utc_now() -> str:
    return (
        datetime.now(timezone.utc)
        .replace(microsecond=0)
        .isoformat()
        .replace("+00:00", "Z")
    )


def compute_whitespace_score(total_views: int, total_videos: int) -> float:
    return round(math.log10(max(0, total_views) + 1) * 100 / max(total_videos, 1), 1)


def qualify_channel(channel: dict[str, Any], query: str) -> dict[str, Any] | None:
    total_videos = int(channel.get("total_videos") or 0)
    if total_videos > MAX_VIDEOS or total_videos <= 0:
        return None

    videos = channel.get("videos") or []
    view_counts = [int(video.get("views") or 0) for video in videos]
    if not view_counts:
        return None

    video_views_total = sum(view_counts)
    total_views = max(int(channel.get("channel_total_views") or 0), video_views_total)
    max_views = max(view_counts)
    if total_views < MIN_TOTAL_VIEWS or max_views < MIN_VIEWS_PER_VIDEO:
        return None

    avg_views = round(video_views_total / len(view_counts))
    score = compute_whitespace_score(total_views=total_views, total_videos=total_videos)
    return {
        "rank": 0,
        "score": score,
        "query": query,
        "channel_id": channel["channel_id"],
        "channel_name": channel["channel_name"],
        "channel_url": channel["channel_url"],
        "subscriber_count": channel.get("subscriber_count"),
        "total_videos": total_videos,
        "channel_total_views": total_views,
        "video_views_total": video_views_total,
        "max_views": max_views,
        "avg_views": avg_views,
        "reason": (
            f"{total_videos} videos with {total_views:,} total views from a "
            "profile-matched query."
        ),
        "videos": sorted(
            videos,
            key=lambda item: int(item.get("views") or 0),
            reverse=True,
        )[:5],
    }


def build_feed(
    seed: dict[str, Any],
    records: list[dict[str, Any]],
    generated_at: str | None = None,
) -> dict[str, Any]:
    best_by_channel: dict[str, dict[str, Any]] = {}
    for record in records:
        channel_id = record["channel_id"]
        existing = best_by_channel.get(channel_id)
        if existing is None or float(record["score"]) > float(existing["score"]):
            best_by_channel[channel_id] = dict(record)

    ranked = sorted(
        best_by_channel.values(),
        key=lambda item: float(item["score"]),
        reverse=True,
    )[:TOP_RESULTS]
    for index, item in enumerate(ranked, 1):
        item["rank"] = index

    return {
        "version": 1,
        "generated_at": generated_at or utc_now(),
        "seed_generated_at": seed.get("generated_at"),
        "source_queries": seed.get("search_queries", []),
        "results": ranked,
    }


def build_youtube(api_key: str):
    from googleapiclient.discovery import build

    return build("youtube", "v3", developerKey=api_key)


def search_channels(youtube, query: str, max_results: int = 25) -> list[str]:
    channel_ids: list[str] = []
    page_token = None
    while len(channel_ids) < max_results:
        resp = (
            youtube.search()
            .list(
                part="snippet",
                q=query,
                type="channel",
                maxResults=min(50, max_results - len(channel_ids)),
                pageToken=page_token,
            )
            .execute()
        )
        for item in resp.get("items", []):
            channel_id = item.get("snippet", {}).get("channelId")
            if channel_id:
                channel_ids.append(channel_id)
        page_token = resp.get("nextPageToken")
        if not page_token:
            break
    return list(dict.fromkeys(channel_ids))


def get_channel_stats(youtube, channel_ids: list[str]) -> list[dict[str, Any]]:
    results: list[dict[str, Any]] = []
    for index in range(0, len(channel_ids), 50):
        resp = (
            youtube.channels()
            .list(
                part="snippet,statistics,contentDetails",
                id=",".join(channel_ids[index : index + 50]),
            )
            .execute()
        )
        results.extend(resp.get("items", []))
    return results


def get_videos_for_channel(
    youtube,
    uploads_playlist_id: str,
    max_videos: int = MAX_VIDEOS + 2,
) -> list[dict[str, str]]:
    videos: list[dict[str, str]] = []
    page_token = None
    while len(videos) < max_videos:
        resp = (
            youtube.playlistItems()
            .list(
                part="snippet,contentDetails",
                playlistId=uploads_playlist_id,
                maxResults=min(50, max_videos - len(videos)),
                pageToken=page_token,
            )
            .execute()
        )
        for item in resp.get("items", []):
            videos.append(
                {
                    "video_id": item["contentDetails"]["videoId"],
                    "title": item["snippet"]["title"],
                    "published_at": item["snippet"]["publishedAt"],
                }
            )
        page_token = resp.get("nextPageToken")
        if not page_token:
            break
    return videos


def get_video_stats(youtube, video_ids: list[str]) -> dict[str, dict[str, Any]]:
    stats: dict[str, dict[str, Any]] = {}
    for index in range(0, len(video_ids), 50):
        resp = (
            youtube.videos()
            .list(
                part="statistics,snippet",
                id=",".join(video_ids[index : index + 50]),
            )
            .execute()
        )
        for item in resp.get("items", []):
            stats[item["id"]] = {
                "video_id": item["id"],
                "title": item["snippet"]["title"],
                "url": f"https://www.youtube.com/watch?v={item['id']}",
                "views": int(item["statistics"].get("viewCount", 0)),
                "likes": int(item["statistics"].get("likeCount", 0)),
                "published_at": item["snippet"]["publishedAt"][:10],
            }
    return stats


def collect_channel(youtube, item: dict[str, Any]) -> dict[str, Any] | None:
    channel_id = item["id"]
    snippet = item.get("snippet", {})
    statistics = item.get("statistics", {})
    total_videos = int(statistics.get("videoCount", 0))
    if total_videos > MAX_VIDEOS:
        return None

    uploads_playlist = (
        item.get("contentDetails", {}).get("relatedPlaylists", {}).get("uploads")
    )
    if not uploads_playlist:
        return None

    videos = get_videos_for_channel(youtube, uploads_playlist)
    if len(videos) > MAX_VIDEOS or not videos:
        return None

    video_stats = get_video_stats(youtube, [video["video_id"] for video in videos])
    enriched_videos = [
        video_stats[video["video_id"]]
        for video in videos
        if video["video_id"] in video_stats
    ]
    hidden_subs = statistics.get("hiddenSubscriberCount")
    return {
        "channel_id": channel_id,
        "channel_name": snippet.get("title", "Unknown"),
        "channel_url": f"https://www.youtube.com/channel/{channel_id}",
        "subscriber_count": None if hidden_subs else int(statistics.get("subscriberCount", 0)),
        "total_videos": total_videos,
        "channel_total_views": int(statistics.get("viewCount", 0)),
        "videos": enriched_videos,
    }


def run(seed_path: Path, output_path: Path, api_key: str) -> dict[str, Any]:
    try:
        from googleapiclient.errors import HttpError
    except ModuleNotFoundError as exc:
        raise RuntimeError(
            "google-api-python-client is required for live YouTube analysis."
        ) from exc

    seed = json.loads(seed_path.read_text())
    youtube = build_youtube(api_key)
    records: list[dict[str, Any]] = []
    for query in seed.get("search_queries", []):
        try:
            channel_ids = search_channels(youtube, query, max_results=25)
            for channel_item in get_channel_stats(youtube, channel_ids):
                channel = collect_channel(youtube, channel_item)
                if not channel:
                    continue
                record = qualify_channel(channel, query)
                if record:
                    records.append(record)
        except HttpError as exc:
            print(f"[warn] YouTube API error for query {query!r}: {exc}")

    feed = build_feed(seed, records)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(feed, indent=2) + "\n")
    return feed


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Generate YouTube whitespace feed from discovery seed."
    )
    parser.add_argument("--seed", default="discovery/content-profile-seed.json")
    parser.add_argument(
        "--output",
        default="frontend/public/discovery/youtube-whitespace.json",
    )
    parser.add_argument("--api-key", default=os.environ.get("YOUTUBE_API_KEY", ""))
    args = parser.parse_args()

    seed_path = Path(args.seed)
    if not args.api_key:
        print("YOUTUBE_API_KEY missing; keeping previous feed.")
        return 0
    if not seed_path.exists():
        print(f"Seed file missing: {seed_path}; keeping previous feed.")
        return 0

    run(seed_path, Path(args.output), args.api_key)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
