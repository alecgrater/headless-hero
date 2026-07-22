from datetime import datetime, timezone

from pipeline.discovery_seed import build_discovery_seed


def test_build_discovery_seed_sanitizes_profile_and_queries():
    profile = {
        "script_count": 4,
        "common_topics": ["Science Myths", "Ancient Engineering", ""],
        "typical_keywords": ["Psychology", "science", "AI", "the"],
        "audience_profile": "Curious adults who like vivid explainers.",
        "narration_style": "Fast, direct, second-person narration with punchy turns.",
        "visual_approach": "High-contrast metaphors and comparison boards.",
        "avg_segment_count": 7.5,
        "analyzed_at": "2026-05-29T10:00:00+00:00",
        "is_stale": False,
        "local_path": "/tmp/secret",
        "script_bodies": ["do not leak"],
    }

    seed = build_discovery_seed(
        profile,
        now=datetime(2026, 5, 29, 17, 0, tzinfo=timezone.utc),
    )

    assert seed["version"] == 1
    assert seed["generated_at"] == "2026-05-29T17:00:00Z"
    assert seed["source"] == "headless-hero-content-profile"
    assert seed["profile"] == {
        "script_count": 4,
        "common_topics": ["Science Myths", "Ancient Engineering"],
        "typical_keywords": ["Psychology", "science", "AI", "the"],
        "audience_profile": "Curious adults who like vivid explainers.",
        "narration_style": "Fast, direct, second-person narration with punchy turns.",
        "visual_approach": "High-contrast metaphors and comparison boards.",
        "avg_segment_count": 7.5,
    }
    assert "local_path" not in seed["profile"]
    assert "script_bodies" not in seed["profile"]
    assert len(seed["search_queries"]) >= 6
    assert len(seed["search_queries"]) <= 40
    assert "Science Myths explained" in seed["search_queries"]
    assert "Ancient Engineering documentary" in seed["search_queries"]
    assert "the explained" not in seed["search_queries"]
    assert "the documentary" not in seed["search_queries"]
    assert len(seed["search_queries"]) == len(set(seed["search_queries"]))


def test_build_discovery_seed_limits_long_text_and_query_count():
    profile = {
        "script_count": 1,
        "common_topics": [f"Topic {i}" for i in range(80)],
        "typical_keywords": [f"keyword{i}" for i in range(80)],
        "audience_profile": "A" * 2000,
        "narration_style": "B" * 2000,
        "visual_approach": "C" * 2000,
        "avg_segment_count": 6,
    }

    seed = build_discovery_seed(
        profile,
        now=datetime(2026, 5, 29, 17, 0, tzinfo=timezone.utc),
    )

    assert len(seed["profile"]["audience_profile"]) == 500
    assert len(seed["profile"]["narration_style"]) == 500
    assert len(seed["profile"]["visual_approach"]) == 500
    assert len(seed["search_queries"]) == 40


def test_build_discovery_seed_treats_naive_datetime_as_utc():
    seed = build_discovery_seed(
        {},
        now=datetime(2026, 5, 29, 17, 0),
    )

    assert seed["generated_at"] == "2026-05-29T17:00:00Z"


def test_build_discovery_seed_defaults_malformed_script_count_to_zero():
    seed = build_discovery_seed(
        {"script_count": "many"},
        now=datetime(2026, 5, 29, 17, 0, tzinfo=timezone.utc),
    )

    assert seed["profile"]["script_count"] == 0
