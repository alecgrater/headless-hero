import importlib.util
import json
from pathlib import Path

import pytest


SCRIPT_PATH = Path(__file__).resolve().parents[2] / "scripts" / "youtube_whitespace.py"
spec = importlib.util.spec_from_file_location("youtube_whitespace", SCRIPT_PATH)
youtube_whitespace = importlib.util.module_from_spec(spec)
assert spec and spec.loader
spec.loader.exec_module(youtube_whitespace)


def test_score_rewards_high_views_and_low_video_count():
    low_supply = youtube_whitespace.compute_whitespace_score(
        total_views=500_000,
        total_videos=2,
    )
    higher_supply = youtube_whitespace.compute_whitespace_score(
        total_views=500_000,
        total_videos=10,
    )
    assert low_supply > higher_supply


def test_analyze_channel_filters_high_supply_and_low_demand():
    high_supply = {
        "channel_id": "UC1",
        "channel_name": "Many Videos",
        "channel_url": "https://www.youtube.com/channel/UC1",
        "subscriber_count": 100,
        "total_videos": 11,
        "channel_total_views": 1_000_000,
        "videos": [{"views": 1_000_000}],
    }
    low_demand = {
        "channel_id": "UC2",
        "channel_name": "Tiny",
        "channel_url": "https://www.youtube.com/channel/UC2",
        "subscriber_count": 100,
        "total_videos": 2,
        "channel_total_views": 10_000,
        "videos": [{"views": 8_000}],
    }

    assert youtube_whitespace.qualify_channel(high_supply, "science") is None
    assert youtube_whitespace.qualify_channel(low_demand, "science") is None


def test_qualify_channel_returns_feed_record():
    channel = {
        "channel_id": "UC3",
        "channel_name": "Breakout",
        "channel_url": "https://www.youtube.com/channel/UC3",
        "subscriber_count": None,
        "total_videos": 3,
        "channel_total_views": 450_000,
        "videos": [
            {
                "video_id": "v1",
                "title": "Big one",
                "url": "https://www.youtube.com/watch?v=v1",
                "views": 300_000,
                "likes": 10_000,
                "published_at": "2026-05-01",
            },
            {
                "video_id": "v2",
                "title": "Second",
                "url": "https://www.youtube.com/watch?v=v2",
                "views": 150_000,
                "likes": 4_000,
                "published_at": "2026-05-02",
            },
        ],
    }

    record = youtube_whitespace.qualify_channel(channel, "science myths")

    assert record is not None
    assert record["query"] == "science myths"
    assert record["channel_id"] == "UC3"
    assert record["total_videos"] == 3
    assert record["video_views_total"] == 450_000
    assert record["max_views"] == 300_000
    assert record["avg_views"] == 225_000
    assert "3 videos" in record["reason"]


def test_build_feed_dedupes_and_ranks_results():
    records = [
        {"channel_id": "UC1", "score": 10, "query": "a"},
        {"channel_id": "UC1", "score": 20, "query": "b"},
        {"channel_id": "UC2", "score": 15, "query": "c"},
    ]

    feed = youtube_whitespace.build_feed(
        seed={"generated_at": "2026-05-29T16:00:00Z", "search_queries": ["a", "b", "c"]},
        records=records,
        generated_at="2026-05-29T17:00:00Z",
    )

    assert [item["channel_id"] for item in feed["results"]] == ["UC1", "UC2"]
    assert [item["rank"] for item in feed["results"]] == [1, 2]
    assert feed["results"][0]["query"] == "b"


def test_run_preserves_existing_feed_when_all_queries_fail(tmp_path, monkeypatch):
    seed_path = tmp_path / "seed.json"
    output_path = tmp_path / "youtube-whitespace.json"
    previous_feed = {
        "version": 1,
        "generated_at": "2026-05-29T00:00:00Z",
        "seed_generated_at": "2026-05-29T00:00:00Z",
        "source_queries": ["science"],
        "results": [{"channel_id": "previous"}],
    }
    seed_path.write_text(
        json.dumps(
            {
                "generated_at": "2026-05-29T16:00:00Z",
                "search_queries": ["science", "history"],
            }
        )
    )
    output_path.write_text(json.dumps(previous_feed, indent=2) + "\n")

    monkeypatch.setattr(youtube_whitespace, "build_youtube", lambda api_key: object())

    def fail_search(youtube, query, max_results=25):
        raise RuntimeError("quotaExceeded")

    monkeypatch.setattr(youtube_whitespace, "search_channels", fail_search)

    with pytest.raises(youtube_whitespace.YouTubeWhitespaceError):
        youtube_whitespace.run(seed_path, output_path, "fake-key")

    assert json.loads(output_path.read_text()) == previous_feed
