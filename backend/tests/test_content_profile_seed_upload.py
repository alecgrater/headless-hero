from fastapi.testclient import TestClient


def test_refresh_content_profile_skips_seed_upload_without_token(monkeypatch):
    from api.main import app
    import api.trending as trending_api

    monkeypatch.setattr(
        "pipeline.content_profile.analyze_content_profile",
        lambda: {
            "script_count": 3,
            "common_topics": ["Science Myths"],
            "typical_keywords": ["biology"],
            "audience_profile": "Curious adults.",
            "narration_style": "Direct.",
            "visual_approach": "Metaphors.",
            "avg_segment_count": 8,
            "analyzed_at": "2026-05-29T10:00:00+00:00",
            "is_stale": False,
        },
    )
    monkeypatch.setattr(trending_api, "_get_setting_or_env", lambda key: "")

    res = TestClient(app).post("/api/trending/content-profile/refresh")

    assert res.status_code == 200
    data = res.json()
    assert data["script_count"] == 3
    assert data["seed_upload"]["status"] == "skipped"
    assert "GitHub Contents Token" in data["seed_upload"]["message"]


def test_refresh_content_profile_returns_seed_upload_warning(monkeypatch):
    from api.main import app
    import api.trending as trending_api

    monkeypatch.setattr(
        "pipeline.content_profile.analyze_content_profile",
        lambda: {
            "script_count": 3,
            "common_topics": ["Science Myths"],
            "typical_keywords": ["biology"],
            "audience_profile": "Curious adults.",
            "narration_style": "Direct.",
            "visual_approach": "Metaphors.",
            "avg_segment_count": 8,
            "analyzed_at": "2026-05-29T10:00:00+00:00",
            "is_stale": False,
        },
    )
    monkeypatch.setattr(trending_api, "_get_setting_or_env", lambda key: "ghp_token")

    def fail_upload(*args, **kwargs):
        raise RuntimeError("GitHub rejected token")

    monkeypatch.setattr(trending_api, "upload_json_file", fail_upload)

    res = TestClient(app).post("/api/trending/content-profile/refresh")

    assert res.status_code == 200
    data = res.json()
    assert data["seed_upload"]["status"] == "warning"
    assert "GitHub rejected token" in data["seed_upload"]["message"]


def test_refresh_content_profile_uploads_seed_when_token_exists(monkeypatch):
    from api.main import app
    import api.trending as trending_api

    captured = {}
    monkeypatch.setattr(
        "pipeline.content_profile.analyze_content_profile",
        lambda: {
            "script_count": 3,
            "common_topics": ["Science Myths"],
            "typical_keywords": ["biology"],
            "audience_profile": "Curious adults.",
            "narration_style": "Direct.",
            "visual_approach": "Metaphors.",
            "avg_segment_count": 8,
            "analyzed_at": "2026-05-29T10:00:00+00:00",
            "is_stale": False,
        },
    )
    monkeypatch.setattr(trending_api, "_get_setting_or_env", lambda key: "ghp_token")

    def fake_upload(**kwargs):
        captured.update(kwargs)
        return {"content_sha": "seed-sha", "commit_sha": "commit-sha", "created": False}

    monkeypatch.setattr(trending_api, "upload_json_file", fake_upload)

    res = TestClient(app).post("/api/trending/content-profile/refresh")

    assert res.status_code == 200
    data = res.json()
    assert data["seed_upload"] == {
        "status": "uploaded",
        "message": "Discovery seed uploaded; GitHub Actions will refresh whitespace results.",
        "commit_sha": "commit-sha",
    }
    assert captured["token"] == "ghp_token"
    assert captured["path"] == "discovery/content-profile-seed.json"
    assert captured["message"] == "Update discovery content profile seed"
    assert captured["content"]["profile"]["common_topics"] == ["Science Myths"]
