"""Segmented script generation must survive one bad segment response.

A segmented listicle is nine sequential LLM calls. Against a cloud model each
takes seconds and a failure is cheap; against a local model each takes ~11
minutes, and one empty response used to discard the whole run. These pin the
two things that changed: a retried segment call, and a resume that does not
re-pay for segments already generated.
"""

import json

import pytest

from pipeline import scriptwriter


def _outline(segment_count: int = 2) -> dict:
    return {
        "title": "T",
        "segments": [
            {"name": f"Segment {i + 1}", "short_name": f"S{i + 1}", "topic_summary": "x"}
            for i in range(segment_count)
        ],
    }


def _scene_json(text: str) -> str:
    return json.dumps({
        "scenes": [
            {"id": "tmp", "narration": text, "visual_prompt": "a prompt", "visual_mode": "full_frame"}
        ]
    })


@pytest.fixture
def isolated_progress(tmp_path, monkeypatch):
    monkeypatch.setattr(scriptwriter, "_PROGRESS_DIR", tmp_path / "script-progress")
    return tmp_path


def _patch_outline(monkeypatch, outline: dict) -> None:
    monkeypatch.setattr(
        scriptwriter, "_generate_outline",
        lambda *args, **kwargs: outline,
    )


def test_an_empty_segment_response_is_retried_not_fatal(isolated_progress, monkeypatch):
    outline = _outline(1)
    _patch_outline(monkeypatch, outline)

    responses = ["", _scene_json("recovered")]
    calls: list[str] = []

    def fake_chat(system, user, **kwargs):
        calls.append(user)
        return responses[len(calls) - 1]

    monkeypatch.setattr(scriptwriter, "chat", fake_chat)

    content = scriptwriter._generate_segmented(
        "sys", "user", "topic", "", "", None,
    )

    assert len(calls) == 2, "the empty response should have been retried"
    assert content.segments[0].scenes[0].narration == "recovered"


def test_a_segment_that_fails_twice_still_raises(isolated_progress, monkeypatch):
    _patch_outline(monkeypatch, _outline(1))
    calls: list[str] = []

    def fake_chat(system, user, **kwargs):
        calls.append(user)
        return ""

    monkeypatch.setattr(scriptwriter, "chat", fake_chat)

    with pytest.raises(RuntimeError, match="Segment 1/1"):
        scriptwriter._generate_segmented("sys", "user", "topic", "", "", None)

    assert len(calls) == scriptwriter._SEGMENT_PARSE_ATTEMPTS, "retries must be bounded"


def test_a_failed_run_resumes_instead_of_regenerating_earlier_segments(
    isolated_progress, monkeypatch
):
    outline = _outline(2)
    outline_calls: list[int] = []

    def fake_outline(*args, **kwargs):
        outline_calls.append(1)
        return outline

    monkeypatch.setattr(scriptwriter, "_generate_outline", fake_outline)

    # First run: segment 1 succeeds, segment 2 is unrecoverable.
    first_run: list[str] = [_scene_json("segment one"), "", ""]
    calls: list[str] = []

    def failing_chat(system, user, **kwargs):
        calls.append(user)
        return first_run[len(calls) - 1]

    monkeypatch.setattr(scriptwriter, "chat", failing_chat)
    with pytest.raises(RuntimeError, match="Segment 2/2"):
        scriptwriter._generate_segmented("sys", "user", "topic", "", "", None)
    assert len(calls) == 3  # one for segment 1, two attempts for segment 2

    # Second run, same prompt: the outline and segment 1 come from the cache, so
    # only segment 2 is generated.
    second_calls: list[str] = []

    def recovering_chat(system, user, **kwargs):
        second_calls.append(user)
        return _scene_json("segment two")

    monkeypatch.setattr(scriptwriter, "chat", recovering_chat)
    content = scriptwriter._generate_segmented("sys", "user", "topic", "", "", None)

    assert len(second_calls) == 1, "segment 1 should have been reused, not regenerated"
    assert len(outline_calls) == 1, "the outline should have been reused, not regenerated"
    assert content.segments[0].scenes[0].narration == "segment one"
    assert content.segments[1].scenes[0].narration == "segment two"
    # Scene ids are assigned after the cache is written, so a resumed run must
    # still renumber across the whole script rather than repeating ids.
    assert [sc.id for sc in content.all_scenes()] == ["scene_001", "scene_002"]


def test_a_completed_script_leaves_no_progress_cache(isolated_progress, monkeypatch):
    _patch_outline(monkeypatch, _outline(1))
    monkeypatch.setattr(scriptwriter, "chat", lambda system, user, **kwargs: _scene_json("done"))

    scriptwriter._generate_segmented("sys", "user", "topic", "", "", None)

    cache_dir = scriptwriter._PROGRESS_DIR
    assert not cache_dir.exists() or not list(cache_dir.glob("*.json"))


def test_an_unreadable_progress_cache_does_not_block_generation(isolated_progress, monkeypatch):
    _patch_outline(monkeypatch, _outline(1))
    key = scriptwriter._progress_key("sys", "user")
    scriptwriter._PROGRESS_DIR.mkdir(parents=True, exist_ok=True)
    (scriptwriter._PROGRESS_DIR / f"{key}.json").write_text("{not json", encoding="utf-8")

    monkeypatch.setattr(scriptwriter, "chat", lambda system, user, **kwargs: _scene_json("fresh"))
    content = scriptwriter._generate_segmented("sys", "user", "topic", "", "", None)

    assert content.segments[0].scenes[0].narration == "fresh"


def test_a_malformed_json_segment_is_retried(isolated_progress, monkeypatch):
    _patch_outline(monkeypatch, _outline(1))
    responses = ["{not json at all", _scene_json("recovered")]
    calls: list[str] = []

    def fake_chat(system, user, **kwargs):
        calls.append(user)
        return responses[len(calls) - 1]

    monkeypatch.setattr(scriptwriter, "chat", fake_chat)
    content = scriptwriter._generate_segmented("sys", "user", "topic", "", "", None)

    assert len(calls) == 2
    assert content.segments[0].scenes[0].narration == "recovered"


def test_a_segment_with_zero_scenes_is_retried(isolated_progress, monkeypatch):
    """`{"scenes": []}` parses, but it is the same non-answer as an empty body."""
    _patch_outline(monkeypatch, _outline(1))
    responses = [json.dumps({"scenes": []}), _scene_json("recovered")]
    calls: list[str] = []

    def fake_chat(system, user, **kwargs):
        calls.append(user)
        return responses[len(calls) - 1]

    monkeypatch.setattr(scriptwriter, "chat", fake_chat)
    content = scriptwriter._generate_segmented("sys", "user", "topic", "", "", None)

    assert len(calls) == 2
    assert [len(seg.scenes) for seg in content.segments] == [1]


def test_a_resumed_segment_still_gets_cross_segment_continuity(isolated_progress, monkeypatch):
    """The continuity context is derived from the previous segment's scenes,
    reused or freshly generated — a resume must not drop it."""
    _patch_outline(monkeypatch, _outline(2))

    first: list[str] = [_scene_json("segment one"), "", ""]
    calls: list[str] = []
    monkeypatch.setattr(
        scriptwriter, "chat",
        lambda system, user, **kw: (calls.append(user), first[len(calls) - 1])[1],
    )
    with pytest.raises(RuntimeError):
        scriptwriter._generate_segmented("sys", "user", "topic", "", "", None)

    prompts: list[str] = []
    monkeypatch.setattr(
        scriptwriter, "chat",
        lambda system, user, **kw: (prompts.append(user), _scene_json("segment two"))[1],
    )
    scriptwriter._generate_segmented("sys", "user", "topic", "", "", None)

    assert len(prompts) == 1
    assert "CROSS-SEGMENT CONTINUITY" in prompts[0]


def test_a_cached_segment_that_no_longer_validates_is_regenerated(isolated_progress, monkeypatch):
    outline = _outline(2)
    _patch_outline(monkeypatch, outline)
    key = scriptwriter._progress_key("sys", "user", None)
    scriptwriter._PROGRESS_DIR.mkdir(parents=True, exist_ok=True)
    (scriptwriter._PROGRESS_DIR / f"{key}.json").write_text(json.dumps({
        "version": scriptwriter._PROGRESS_VERSION,
        "saved_at": __import__("time").time(),
        "outline": outline,
        # A scene shape Scene.model_validate will reject.
        "segments": [[{"narration": []}]],
    }), encoding="utf-8")

    calls: list[str] = []
    monkeypatch.setattr(
        scriptwriter, "chat",
        lambda system, user, **kw: (calls.append(user), _scene_json("fresh"))[1],
    )
    content = scriptwriter._generate_segmented("sys", "user", "topic", "", "", None)

    assert len(calls) == 2, "both segments should have been regenerated"
    assert all(seg.scenes[0].narration == "fresh" for seg in content.segments)


def test_an_unusable_outline_is_never_parked(isolated_progress, monkeypatch):
    """A structurally valid but segment-less outline must not become permanent."""
    outline_calls: list[int] = []

    def fake_outline(*args, **kwargs):
        outline_calls.append(1)
        return {"title": "T"}  # no segments

    monkeypatch.setattr(scriptwriter, "_generate_outline", fake_outline)
    monkeypatch.setattr(scriptwriter, "chat", lambda system, user, **kw: _scene_json("x"))

    for _ in range(2):
        with pytest.raises(KeyError):
            scriptwriter._generate_segmented("sys", "user", "topic", "", "", None)

    assert outline_calls == [1, 1], "the bad outline must not be replayed from cache"


def test_switching_text_engine_does_not_resume_the_other_engines_segments(
    isolated_progress, monkeypatch
):
    outline = _outline(2)
    _patch_outline(monkeypatch, outline)
    monkeypatch.setattr(scriptwriter, "text_fingerprint", lambda task, model: "ollama:local-27b")

    first: list[str] = [_scene_json("LOCAL"), "", ""]
    calls: list[str] = []
    monkeypatch.setattr(
        scriptwriter, "chat",
        lambda system, user, **kw: (calls.append(user), first[len(calls) - 1])[1],
    )
    with pytest.raises(RuntimeError):
        scriptwriter._generate_segmented("sys", "user", "topic", "", "", None)

    # Same prompt, different engine: nothing from the local attempt may be reused.
    monkeypatch.setattr(scriptwriter, "text_fingerprint", lambda task, model: "anthropic:claude")
    monkeypatch.setattr(scriptwriter, "chat", lambda system, user, **kw: _scene_json("CLOUD"))
    content = scriptwriter._generate_segmented("sys", "user", "topic", "", "", None)

    narrations = [sc.narration for sc in content.all_scenes()]
    assert narrations == ["CLOUD", "CLOUD"], f"spliced two engines: {narrations}"


def test_a_stale_cache_is_ignored(isolated_progress, monkeypatch):
    import time as _time

    outline = _outline(1)
    outline_calls: list[int] = []

    def fake_outline(*args, **kwargs):
        outline_calls.append(1)
        return outline

    monkeypatch.setattr(scriptwriter, "_generate_outline", fake_outline)
    key = scriptwriter._progress_key("sys", "user", None)
    scriptwriter._PROGRESS_DIR.mkdir(parents=True, exist_ok=True)
    (scriptwriter._PROGRESS_DIR / f"{key}.json").write_text(json.dumps({
        "version": scriptwriter._PROGRESS_VERSION,
        "saved_at": _time.time() - scriptwriter._PROGRESS_MAX_AGE_SECONDS - 60,
        "outline": outline,
        "segments": [[{"id": "x", "narration": "stale", "visual_prompt": "p"}]],
    }), encoding="utf-8")

    monkeypatch.setattr(scriptwriter, "chat", lambda system, user, **kw: _scene_json("fresh"))
    content = scriptwriter._generate_segmented("sys", "user", "topic", "", "", None)

    assert outline_calls == [1], "a stale cache must not short-circuit the outline"
    assert content.segments[0].scenes[0].narration == "fresh"
