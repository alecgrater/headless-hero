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
    assert data["profile_input_upload"]["status"] == "skipped"
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
    assert data["profile_input_upload"]["status"] == "warning"
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
    monkeypatch.setattr(
        trending_api,
        "build_content_profile_input_snapshot",
        lambda: {
            "version": 1,
            "source": "headless-hero-content-profile-input",
            "script_count": 3,
            "scripts": [{"id": "script-1", "title": "Science Myths"}],
        },
    )

    def fake_upload(**kwargs):
        captured["token"] = kwargs["token"]
        captured.setdefault("uploads", []).append(
            {
                "path": kwargs["path"],
                "message": kwargs["message"],
                "content": kwargs["content"],
            }
        )
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
    assert data["profile_input_upload"] == {
        "status": "uploaded",
        "message": "Content profile input uploaded; GitHub Actions can refresh the profile on schedule.",
        "commit_sha": "commit-sha",
    }
    assert captured["token"] == "ghp_token"
    uploads = captured["uploads"]
    assert [upload["path"] for upload in uploads] == [
        "discovery/content-profile-input.json",
        "discovery/content-profile-seed.json",
    ]
    assert uploads[0]["message"] == "Update remote content profile input"
    assert uploads[0]["content"]["scripts"][0]["title"] == "Science Myths"
    assert uploads[1]["message"] == "Update discovery content profile seed"
    assert uploads[1]["content"]["profile"]["common_topics"] == ["Science Myths"]
