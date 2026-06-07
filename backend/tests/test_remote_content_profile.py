from datetime import datetime, timezone


def test_analyze_content_profile_snapshot_builds_profile_from_uploaded_scripts(monkeypatch):
    import pipeline.remote_content_profile as remote_profile

    captured = {}

    def fake_chat(system, user_message, **kwargs):
        captured["user_message"] = user_message
        captured["kwargs"] = kwargs
        return """
        {
          "common_topics": ["river science", "hidden physics"],
          "narration_style": "Clear, vivid explanations with concrete cause and effect.",
          "visual_approach": "Aerial diagrams and close-up visual metaphors.",
          "typical_keywords": ["river", "erosion", "curve"],
          "audience_profile": "Curious adults who like visual science stories."
        }
        """

    monkeypatch.setattr(remote_profile, "chat", fake_chat)

    snapshot = {
        "version": 1,
        "generated_at": "2026-06-07T12:00:00+00:00",
        "source": "headless-hero-content-profile-input",
        "scripts": [
            {
                "id": "script-1",
                "title": "River Science",
                "format_id": "youtube-listicle",
                "segments": [
                    {
                        "name": "The curve",
                        "scenes": [
                            {
                                "id": "scene-1",
                                "narration": "A river starts carving sideways when the outside edge speeds up.",
                                "visual_mode": "continuous",
                            }
                        ],
                    }
                ],
            }
        ],
    }

    profile = remote_profile.analyze_content_profile_snapshot(
        snapshot,
        now=datetime(2026, 6, 7, 13, 0, tzinfo=timezone.utc),
    )

    assert profile == {
        "script_count": 1,
        "common_topics": ["river science", "hidden physics"],
        "narration_style": "Clear, vivid explanations with concrete cause and effect.",
        "visual_approach": "Aerial diagrams and close-up visual metaphors.",
        "typical_keywords": ["river", "erosion", "curve"],
        "audience_profile": "Curious adults who like visual science stories.",
        "avg_segment_count": 1.0,
        "analyzed_at": "2026-06-07T13:00:00+00:00",
        "is_stale": False,
    }
    assert captured["kwargs"]["task"] == "analysis"
    assert "River Science" in captured["user_message"]
    assert "A river starts carving sideways" in captured["user_message"]


def test_remote_profile_outputs_seed_from_generated_profile(monkeypatch):
    import pipeline.remote_content_profile as remote_profile

    monkeypatch.setattr(
        remote_profile,
        "analyze_content_profile_snapshot",
        lambda snapshot: {
            "script_count": 1,
            "common_topics": ["river science"],
            "narration_style": "Direct.",
            "visual_approach": "Aerial diagrams.",
            "typical_keywords": ["river"],
            "audience_profile": "Curious adults.",
            "avg_segment_count": 1.0,
            "analyzed_at": "2026-06-07T13:00:00+00:00",
            "is_stale": False,
        },
    )

    profile, seed = remote_profile.build_remote_profile_artifacts({"scripts": []})

    assert profile["common_topics"] == ["river science"]
    assert seed["source"] == "headless-hero-content-profile"
    assert seed["profile"]["common_topics"] == ["river science"]
    assert seed["search_queries"]


def test_choose_freshest_profile_prefers_newer_remote_artifact():
    import pipeline.remote_content_profile as remote_profile

    local = {
        "script_count": 3,
        "common_topics": ["old topic"],
        "analyzed_at": "2026-06-06T12:00:00+00:00",
        "is_stale": False,
    }
    remote = {
        "script_count": 4,
        "common_topics": ["new topic"],
        "analyzed_at": "2026-06-07T12:00:00+00:00",
        "is_stale": False,
    }

    assert remote_profile.choose_freshest_profile(local, remote) == remote


def test_load_remote_content_profile_reads_valid_artifact(tmp_path):
    import json
    import pipeline.remote_content_profile as remote_profile

    profile_path = tmp_path / "content-profile.json"
    profile_path.write_text(
        json.dumps(
            {
                "script_count": 4,
                "common_topics": ["new topic"],
                "narration_style": "Direct.",
                "visual_approach": "Diagrams.",
                "typical_keywords": ["topic"],
                "audience_profile": "Curious adults.",
                "avg_segment_count": 8,
                "analyzed_at": "2026-06-07T12:00:00+00:00",
                "is_stale": False,
            }
        )
    )

    assert remote_profile.load_remote_content_profile(profile_path)["common_topics"] == ["new topic"]


def test_load_remote_content_profile_ignores_invalid_numeric_fields(tmp_path):
    import json
    import pipeline.remote_content_profile as remote_profile

    profile_path = tmp_path / "content-profile.json"
    profile_path.write_text(
        json.dumps(
            {
                "script_count": "many",
                "common_topics": ["new topic"],
                "narration_style": "Direct.",
                "visual_approach": "Diagrams.",
                "typical_keywords": ["topic"],
                "audience_profile": "Curious adults.",
                "avg_segment_count": "often",
                "analyzed_at": "2026-06-07T12:00:00+00:00",
                "is_stale": False,
            }
        )
    )

    assert remote_profile.load_remote_content_profile(profile_path) is None


def test_load_remote_content_profile_ignores_non_finite_average(tmp_path):
    import pipeline.remote_content_profile as remote_profile

    profile_path = tmp_path / "content-profile.json"
    profile_path.write_text(
        """
        {
          "script_count": 4,
          "common_topics": ["new topic"],
          "narration_style": "Direct.",
          "visual_approach": "Diagrams.",
          "typical_keywords": ["topic"],
          "audience_profile": "Curious adults.",
          "avg_segment_count": NaN,
          "analyzed_at": "2026-06-07T12:00:00+00:00",
          "is_stale": false
        }
        """
    )

    assert remote_profile.load_remote_content_profile(profile_path) is None
