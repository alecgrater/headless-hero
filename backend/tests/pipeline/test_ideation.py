import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from pipeline import ideation


def test_generate_ideas_includes_optional_guide(monkeypatch):
    captured: dict[str, str] = {}

    def fake_chat(system: str, user: str, **kwargs):
        captured["system"] = system
        captured["user"] = user
        return '{"ideas":[{"title":"Test","segments_est":8,"description":"Desc","keywords":["one"]}]}'

    monkeypatch.setattr(ideation, "chat", fake_chat)

    ideas = ideation.generate_ideas(
        niche="8 Things You Probably Thought Were True",
        guide="Focus on widespread misconceptions, not conspiracy theories.",
        count=1,
    )

    assert ideas[0].title == "Test"
    assert "Creator guidance" in captured["user"]
    assert "Focus on widespread misconceptions" in captured["user"]
    assert ideas[0].creator_guidance == "Focus on widespread misconceptions, not conspiracy theories."


def test_generate_ideas_omits_blank_guide(monkeypatch):
    captured: dict[str, str] = {}

    def fake_chat(system: str, user: str, **kwargs):
        captured["user"] = user
        return '{"ideas":[{"title":"Test","segments_est":8,"description":"Desc","keywords":["one"]}]}'

    monkeypatch.setattr(ideation, "chat", fake_chat)

    ideation.generate_ideas(niche="history myths", guide="   ", count=1)

    assert "Creator guidance" not in captured["user"]


def test_generate_ideas_omits_blank_creator_guidance_from_results(monkeypatch):
    def fake_chat(system: str, user: str, **kwargs):
        return '{"ideas":[{"title":"Test","segments_est":8,"description":"Desc","keywords":["one"]}]}'

    monkeypatch.setattr(ideation, "chat", fake_chat)

    ideas = ideation.generate_ideas(niche="history myths", guide="   ", count=1)

    assert ideas[0].creator_guidance is None


def test_generate_ideas_coerces_list_segments_est(monkeypatch):
    """A malformed list segments_est must not crash the batch (regression)."""

    def fake_chat(system: str, user: str, **kwargs):
        return (
            '{"ideas":[{"title":"Test","segments_est":'
            '["Hook — Picture this...","Part 2","Part 3"],'
            '"description":"Desc","keywords":["one"]}]}'
        )

    monkeypatch.setattr(ideation, "chat", fake_chat)

    ideas = ideation.generate_ideas(niche="conversation", count=1)

    assert len(ideas) == 1
    # Listicle format clamps to its fixed level_count of 8.
    assert ideas[0].segments_est == 8


def test_generate_ideas_skips_malformed_idea_keeps_valid(monkeypatch):
    """One unparseable idea is skipped; valid ideas still return."""

    def fake_chat(system: str, user: str, **kwargs):
        return (
            '{"ideas":['
            '{"segments_est":8,"description":"missing title"},'  # invalid: no title
            '{"title":"Good","segments_est":8,"description":"Desc","keywords":["one"]}'
            ']}'
        )

    monkeypatch.setattr(ideation, "chat", fake_chat)

    ideas = ideation.generate_ideas(niche="history myths", count=2)

    assert len(ideas) == 1
    assert ideas[0].title == "Good"


def test_generate_ideas_clamps_segments_to_format_range(monkeypatch):
    """segments_est is clamped to the format's allowed level range."""

    def fake_chat(system: str, user: str, **kwargs):
        return '{"ideas":[{"title":"Test","segments_est":99,"description":"Desc","keywords":["one"]}]}'

    monkeypatch.setattr(ideation, "chat", fake_chat)

    ideas = ideation.generate_ideas(
        niche="a nurse's life", count=1, format_id="life-as-a"
    )

    # life-as-a level_count is (4, 7) → clamped to 7.
    assert ideas[0].segments_est == 7
