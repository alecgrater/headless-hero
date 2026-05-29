"""Tests for format-aware cold-open generation."""

import json

from pipeline import cold_open


def test_life_as_a_cold_opens_use_format_specific_rubric(monkeypatch):
    captured = {}

    def fake_chat(system: str, user: str, **kwargs):
        captured["system"] = system
        captured["user"] = user
        return json.dumps({
            "variants": [
                {
                    "id": "immersive_entry",
                    "style": "Immersive Entry",
                    "intro_hook": "You wake before sunrise with the keys already cutting into your palm.",
                    "opening_narration": "The corridor is still dark. Someone is already waiting outside the gate.",
                    "scores": {
                        "tension": 75,
                        "specificity": 90,
                        "drop_rate_risk": 10,
                        "reasoning": "Immediate second-person role fantasy with concrete pressure.",
                    },
                }
            ],
        })

    monkeypatch.setattr(cold_open, "chat", fake_chat)

    result = cold_open.generate_cold_opens(
        topic="Your Life As A Castle Guard",
        description="Medieval job progression.",
        format_id="life-as-a",
    )

    assert "LIFE-AS-A OPENING VARIANTS" in captured["system"]
    assert "second-person immersion" in captured["system"]
    assert result.score_labels["tension"] == "Stakes"
    assert result.score_labels["specificity"] == "Immersion"
    assert result.score_labels["drop_rate_risk"] == "Drop Risk"
    assert result.variants[0].id == "immersive_entry"
    assert result.winner_id == "immersive_entry"
