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


def _rating_payload(**overrides) -> dict:
    payload = {
        "continuity_errors": [],
        "unintroduced_references": [],
        "bumpy_transitions": [],
        "ai_tells": [{"scene": "scene-2", "quote": "why old games still teach modern designers",
                      "problem": "Tidy thesis line.", "severity": "minor"}],
        "read_aloud_problems": [],
        "standalone_violations": [{"scene": "scene-2", "quote": "next time we will cover arcades",
                                   "problem": "Invented line.", "severity": "major"}],
        "voice_violations": [],
        "scores": {"flow": 7, "clarity": 8, "human_sounding": 6, "continuity": 8, "format_fit": 7, "overall": 7},
        "worst_problem": "The closing line states the thesis outright.",
    }
    payload.update(overrides)
    return payload


def _narration() -> str:
    return " ".join(scene.narration for scene in _content().all_scenes())


def test_review_keeps_only_quotes_that_are_in_the_narration():
    from pipeline.script_rating import parse_script_rating_response

    rating = parse_script_rating_response(json.dumps(_rating_payload()), narration=_narration(), model="claude-sonnet-5-5")

    assert rating.overall == 7
    assert rating.scores.human_sounding == 6
    assert [p.category for p in rating.problems] == ["ai_tells"], "the invented quote must be dropped"
    assert rating.worst_problem.startswith("The closing line")


def test_major_problems_sort_first():
    from pipeline.script_rating import parse_script_rating_response

    payload = _rating_payload(standalone_violations=[{"scene": "scene-1", "quote": "a cartridge clicks into place",
                                                      "problem": "x", "severity": "major"}])
    rating = parse_script_rating_response(json.dumps(payload), narration=_narration(), model="m")
    assert [p.severity for p in rating.problems] == ["major", "minor"]


def test_review_round_trips_on_script_content():
    from pipeline.script_rating import parse_script_rating_response

    rating = parse_script_rating_response(json.dumps(_rating_payload()), narration=_narration(), model="m")
    content = _content().model_copy(update={"script_rating": rating})
    restored = ScriptContent.model_validate_json(content.model_dump_json())
    assert restored.script_rating == rating


def test_retired_scorecards_load_as_unrated():
    # Pre-2026-09-30 ratings had category keys and no `scores`; they must not break loading.
    data = _content().model_dump(mode="json")
    data["script_rating"] = {"viewer_retention": {"average": 7.3}, "overall": 7.4, "model": "gpt-5.6-terra"}
    assert ScriptContent.model_validate(data).script_rating is None


@pytest.mark.parametrize("scores", [{"flow": 7}, {"flow": 11, "clarity": 8, "human_sounding": 6, "continuity": 8,
                                                 "format_fit": 7, "overall": 7}])
def test_review_rejects_missing_or_out_of_range_scores(scores):
    from pipeline.script_rating import parse_script_rating_response

    with pytest.raises(ValueError):
        parse_script_rating_response(json.dumps(_rating_payload(scores=scores)), narration=_narration(), model="m")


def test_script_rating_task_defaults_to_the_calibrated_claude_model(monkeypatch):
    monkeypatch.delenv("SCRIPT_RATING_LLM_PROVIDER", raising=False)
    monkeypatch.delenv("SCRIPT_RATING_MODEL", raising=False)
    monkeypatch.setenv("LLM_PROVIDER", "ollama")

    assert _resolve_provider("script_rating") == "anthropic"
    assert _resolve_model("anthropic", "script_rating", None) == "claude-sonnet-5-5"


@pytest.mark.parametrize("format_id,expected,absent", [
    ("life-as-a", "Literary 'Your Life As A", "for this listicle"),
    ("youtube-listicle", "for this listicle: earlier in the SAME segment", "always an empty list"),
])
def test_review_prompt_uses_the_format_notes(monkeypatch, format_id, expected, absent):
    from pipeline import script_rating

    captured = {}

    def fake_chat(system: str, user: str, **kwargs):
        captured.update(system=system, user=user)
        return json.dumps(_rating_payload())

    monkeypatch.setattr(script_rating, "chat", fake_chat)
    script_rating.rate_script(_content().model_copy(update={"format_id": format_id}), script_id="script-123")

    assert captured["system"] == script_rating.JUDGE_SYSTEM
    assert expected in captured["user"]
    assert absent not in captured["user"]
    assert "scene-1: A cartridge clicks into place" in captured["user"]


def test_fractional_sub_scores_round_instead_of_discarding_the_review():
    from pipeline.script_rating import parse_script_rating_response

    scores = {"flow": 6.5, "clarity": 8, "human_sounding": 6, "continuity": 8, "format_fit": 7, "overall": 6.5}
    rating = parse_script_rating_response(json.dumps(_rating_payload(scores=scores)), narration=_narration(), model="m")
    assert rating.scores.flow in (6, 7)
    assert rating.overall == 6.5


def test_a_non_numeric_overall_is_a_parse_error():
    from pipeline.script_rating import parse_script_rating_response

    scores = {"flow": 7, "clarity": 8, "human_sounding": 6, "continuity": 8, "format_fit": 7, "overall": None}
    with pytest.raises(ValueError):
        parse_script_rating_response(json.dumps(_rating_payload(scores=scores)), narration=_narration(), model="m")


def test_an_unparseable_reply_is_resampled_once(monkeypatch):
    # A real run lost its rating to one unescaped quote inside a quoted problem.
    from pipeline import script_rating

    replies = iter(['{"scores": {"overall": 7 "flow": 7}}', json.dumps(_rating_payload())])
    calls = []

    def fake_chat(system: str, user: str, **kwargs):
        calls.append(user)
        return next(replies)

    monkeypatch.setattr(script_rating, "chat", fake_chat)
    rating = script_rating.rate_script(_content(), script_id="script-123")

    assert len(calls) == 2
    assert rating.overall == _rating_payload()["scores"]["overall"]


def test_two_unparseable_replies_still_fail(monkeypatch):
    from pipeline import script_rating

    calls = []

    def fake_chat(system: str, user: str, **kwargs):
        calls.append(user)
        return "not json"

    monkeypatch.setattr(script_rating, "chat", fake_chat)
    with pytest.raises(RuntimeError):
        script_rating.rate_script(_content(), script_id="script-123")
    assert len(calls) == 2
