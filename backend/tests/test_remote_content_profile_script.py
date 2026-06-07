import importlib.util
import json
from pathlib import Path


SCRIPT_PATH = Path(__file__).resolve().parents[2] / "scripts" / "remote_content_profile.py"
spec = importlib.util.spec_from_file_location("remote_content_profile_script", SCRIPT_PATH)
remote_content_profile_script = importlib.util.module_from_spec(spec)
assert spec and spec.loader
spec.loader.exec_module(remote_content_profile_script)


def test_remote_content_profile_script_writes_profile_and_seed(tmp_path, monkeypatch):
    input_path = tmp_path / "content-profile-input.json"
    profile_path = tmp_path / "content-profile.json"
    seed_path = tmp_path / "content-profile-seed.json"
    input_path.write_text(json.dumps({"scripts": [{"title": "River Science"}]}))
    monkeypatch.setenv("OPENAI_API_KEY", "test-key")

    def fake_build(snapshot):
        assert snapshot["scripts"][0]["title"] == "River Science"
        return (
            {
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
            {
                "version": 1,
                "source": "headless-hero-content-profile",
                "profile": {"common_topics": ["river science"]},
                "search_queries": ["river science explained"],
            },
        )

    monkeypatch.setattr(remote_content_profile_script, "build_remote_profile_artifacts", fake_build)

    exit_code = remote_content_profile_script.main(
        [
            "--input",
            str(input_path),
            "--profile-output",
            str(profile_path),
            "--seed-output",
            str(seed_path),
        ]
    )

    assert exit_code == 0
    assert json.loads(profile_path.read_text())["common_topics"] == ["river science"]
    assert json.loads(seed_path.read_text())["search_queries"] == ["river science explained"]
