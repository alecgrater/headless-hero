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


def test_generate_ideas_omits_blank_guide(monkeypatch):
    captured: dict[str, str] = {}

    def fake_chat(system: str, user: str, **kwargs):
        captured["user"] = user
        return '{"ideas":[{"title":"Test","segments_est":8,"description":"Desc","keywords":["one"]}]}'

    monkeypatch.setattr(ideation, "chat", fake_chat)

    ideation.generate_ideas(niche="history myths", guide="   ", count=1)

    assert "Creator guidance" not in captured["user"]
