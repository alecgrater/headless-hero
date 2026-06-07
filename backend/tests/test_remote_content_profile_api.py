def test_get_available_content_profile_uses_newer_remote_artifact(monkeypatch):
    import api.trending as trending_api
    import pipeline.content_profile as content_profile

    monkeypatch.setattr(
        content_profile,
        "get_cached_profile",
        lambda: {
            "script_count": 3,
            "common_topics": ["old topic"],
            "narration_style": "Old.",
            "visual_approach": "Old visuals.",
            "typical_keywords": ["old"],
            "audience_profile": "Old audience.",
            "avg_segment_count": 8,
            "analyzed_at": "2026-06-06T12:00:00+00:00",
            "is_stale": False,
        },
    )
    monkeypatch.setattr(
        trending_api,
        "load_remote_content_profile",
        lambda: {
            "script_count": 4,
            "common_topics": ["new topic"],
            "narration_style": "New.",
            "visual_approach": "New visuals.",
            "typical_keywords": ["new"],
            "audience_profile": "New audience.",
            "avg_segment_count": 9,
            "analyzed_at": "2026-06-07T12:00:00+00:00",
            "is_stale": False,
        },
    )

    assert trending_api._get_available_content_profile()["common_topics"] == ["new topic"]
