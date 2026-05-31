import json

import pytest

from integrations.llm_client import _resolve_model, _resolve_openai_reasoning_effort, _resolve_provider
from models.script import Scene, ScriptContent, Segment


def _content() -> ScriptContent:
    return ScriptContent(
        title="Why Old Games Still Matter",
        intro_hook="The best game design trick is older than you think.",
        segments=[
            Segment(
                name="Opening",
                scenes=[
                    Scene(
                        id="scene-1",
                        narration="A cartridge clicks into place, and suddenly the room feels faster.",
                        visual_prompt="[CLOSE] A retro console powering on",
                    ),
                    Scene(
                        id="scene-2",
                        narration="That instant feedback loop is why old games still teach modern designers.",
                        visual_prompt="[WIDE] A designer studying old level maps",
                    ),
                ],
            ),
        ],
    )


def _rating_payload() -> dict:
    return {
        "viewer_retention": {
            "criteria": {
                "hook_strength": {"score": 8, "note": "Clear promise."},
                "curiosity_gaps": {"score": 7, "note": "Some open loops."},
                "pacing_variance": {"score": 7, "note": "Could vary rhythm."},
            },
            "explanation": "The opening has a concrete promise, but the middle can add sharper turns.",
        },
        "narrative_quality": {
            "criteria": {
                "coherence": {"score": 7, "note": "Easy to follow."},
                "throughline": {"score": 6, "note": "Theme is present but light."},
            },
            "explanation": "The argument is coherent, but callbacks should carry the thesis harder.",
        },
        "script_craft": {
            "criteria": {
                "sentence_variety": {"score": 8, "note": "Good mix."},
                "specificity": {"score": 9, "note": "Strong images."},
                "redundancy": {"score": 7, "note": "Minor repeats."},
                "word_economy": {"score": 8, "note": "Mostly lean."},
            },
            "explanation": "The writing is specific and efficient with only a few repeated moves.",
        },
        "audience_fit": {
            "criteria": {
                "assumed_knowledge_level": {"score": 8, "note": "Accessible."},
                "relatability": {"score": 7, "note": "Familiar examples."},
                "tone_consistency": {"score": 8, "note": "Stable tone."},
                "emotional_range": {"score": 7, "note": "Could broaden stakes."},
            },
            "explanation": "The script fits a broad audience while leaving room for more emotional contrast.",
        },
        "seo_alignment": {
            "criteria": {
                "title_hook_match": {"score": 7, "note": "Mostly aligned."},
                "search_intent_match": {"score": 6, "note": "Needs clearer query fit."},
                "rewatch_value": {"score": 7, "note": "Useful takeaways."},
            },
            "explanation": "The title and hook match, but search intent could be more explicit.",
        },
    }


def test_script_rating_round_trips_on_script_content():
    from pipeline.script_rating import parse_script_rating_response

    rating = parse_script_rating_response(json.dumps(_rating_payload()), model="gpt-5-mini")
    content = _content().model_copy(update={"script_rating": rating})

    restored = ScriptContent.model_validate_json(content.model_dump_json())

    assert restored.script_rating is not None
    assert restored.script_rating.overall == 7.3
    assert restored.script_rating.viewer_retention.average == 7.3
    assert restored.script_rating.script_craft.average == 8.0


def test_script_rating_recomputes_model_math():
    from pipeline.script_rating import parse_script_rating_response

    payload = _rating_payload()
    payload["overall"] = 10
    payload["viewer_retention"]["average"] = 1

    rating = parse_script_rating_response(json.dumps(payload), model="gpt-5-mini")

    assert rating.viewer_retention.average == 7.3
    assert rating.narrative_quality.average == 6.5
    assert rating.seo_alignment.average == pytest.approx(6.7)
    assert rating.overall == 7.3


def test_script_rating_rejects_missing_criteria():
    from pipeline.script_rating import parse_script_rating_response

    payload = _rating_payload()
    del payload["viewer_retention"]["criteria"]["hook_strength"]

    with pytest.raises(ValueError, match="hook_strength"):
        parse_script_rating_response(json.dumps(payload), model="gpt-5-mini")


def test_script_rating_rejects_out_of_range_scores():
    from pipeline.script_rating import parse_script_rating_response

    payload = _rating_payload()
    payload["seo_alignment"]["criteria"]["search_intent_match"]["score"] = 11

    with pytest.raises(ValueError, match="less than or equal to 10"):
        parse_script_rating_response(json.dumps(payload), model="gpt-5-mini")


def test_script_rating_task_defaults_to_gpt_5_mini(monkeypatch):
    monkeypatch.delenv("SCRIPT_RATING_LLM_PROVIDER", raising=False)
    monkeypatch.delenv("SCRIPT_RATING_MODEL", raising=False)
    monkeypatch.delenv("OPENAI_REASONING_EFFORT_SCRIPT_RATING", raising=False)
    monkeypatch.setenv("LLM_PROVIDER", "ollama")

    assert _resolve_provider("script_rating") == "openai"
    assert _resolve_model("openai", "script_rating", None) == "gpt-5-mini"
    assert _resolve_openai_reasoning_effort("script_rating") == "minimal"


def test_life_as_a_rating_prompt_uses_format_specific_rubric(monkeypatch):
    from pipeline import script_rating

    captured = {}

    def fake_chat(system: str, user: str, **kwargs):
        captured["system"] = system
        captured["user"] = user
        return json.dumps(_rating_payload())

    content = _content().model_copy(update={"format_id": "life-as-a"})
    monkeypatch.setattr(script_rating, "chat", fake_chat)

    rating = script_rating.rate_script(content, script_id="script-123")

    assert rating.overall == 7.3
    assert "Format context: `life-as-a`" in captured["system"]
    assert "This is not a listicle" in captured["system"]
    assert "second-person present-tense immersion" in captured["system"]
