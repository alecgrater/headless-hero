from pipeline import seo


def _local_higgs(monkeypatch):
    monkeypatch.setenv("LOCAL_MODELS_ENABLED", "true")
    monkeypatch.delenv("LOCAL_VOICE_MODE", raising=False)
    monkeypatch.setenv("LOCAL_VOICE_MODEL", "higgs-tts-3-4b")


def test_no_attribution_in_cloud_mode(monkeypatch):
    monkeypatch.setenv("LOCAL_MODELS_ENABLED", "false")
    monkeypatch.delenv("LOCAL_VOICE_MODE", raising=False)
    assert seo.required_voice_attribution() == ""
    assert seo.apply_voice_attribution("body") == "body"


def test_no_attribution_when_voice_is_pinned_to_cloud(monkeypatch):
    _local_higgs(monkeypatch)
    monkeypatch.setenv("LOCAL_VOICE_MODE", "cloud")
    assert seo.required_voice_attribution() == ""


def test_higgs_attribution_is_appended(monkeypatch):
    _local_higgs(monkeypatch)
    credit = seo.required_voice_attribution()
    assert credit
    result = seo.apply_voice_attribution("body")
    assert result.startswith("body")
    assert result.endswith(credit)


def test_attribution_is_not_duplicated(monkeypatch):
    _local_higgs(monkeypatch)
    once = seo.apply_voice_attribution("body")
    assert seo.apply_voice_attribution(once) == once


def test_no_attribution_for_permissive_local_models(monkeypatch):
    monkeypatch.setenv("LOCAL_MODELS_ENABLED", "true")
    monkeypatch.delenv("LOCAL_VOICE_MODE", raising=False)
    monkeypatch.setenv("LOCAL_VOICE_MODEL", "kokoro-82m")
    assert seo.required_voice_attribution() == ""
    assert seo.apply_voice_attribution("body") == "body"


def test_generate_seo_applies_attribution(monkeypatch):
    _local_higgs(monkeypatch)
    payload = '{"youtube": {"title": "T", "description": "D", "tags": ["a"]}}'
    monkeypatch.setattr(seo, "chat", lambda *a, **k: payload)
    result = seo.generate_seo("T", [("Intro", "0:00")])
    assert seo.required_voice_attribution() in result.youtube.description


def test_generate_seo_leaves_description_alone_in_cloud_mode(monkeypatch):
    monkeypatch.setenv("LOCAL_MODELS_ENABLED", "false")
    monkeypatch.delenv("LOCAL_VOICE_MODE", raising=False)
    payload = '{"youtube": {"title": "T", "description": "D", "tags": ["a"]}}'
    monkeypatch.setattr(seo, "chat", lambda *a, **k: payload)
    result = seo.generate_seo("T", [("Intro", "0:00")])
    assert result.youtube.description == "D"


def test_empty_description_still_gets_the_credit(monkeypatch):
    _local_higgs(monkeypatch)
    assert seo.apply_voice_attribution("") == seo.required_voice_attribution()


def test_persisted_engine_beats_the_current_mode(monkeypatch):
    """The credit follows the engine that voiced the audio, not today's setting."""
    monkeypatch.setenv("LOCAL_MODELS_ENABLED", "false")
    monkeypatch.delenv("LOCAL_VOICE_MODE", raising=False)

    # Audio was produced by Higgs, even though voice is on cloud right now.
    credit = seo.required_voice_attribution("local:higgs-tts-3-4b")
    assert credit
    assert credit in seo.apply_voice_attribution("body", "local:higgs-tts-3-4b")


def test_cloud_recorded_audio_never_gets_a_credit(monkeypatch):
    """Switching to Local Mode must not credit Boson for ElevenLabs audio."""
    _local_higgs(monkeypatch)
    assert seo.required_voice_attribution("elevenlabs") == ""
    assert seo.apply_voice_attribution("body", "elevenlabs") == "body"


def test_permissive_local_engine_records_no_credit():
    assert seo.required_voice_attribution("local:kokoro-82m") == ""


def _content_with_engines(*engines: str):
    from models.script import Scene, ScriptContent, Segment

    scenes = [
        Scene(id=f"s{i}", narration="n", visual_prompt="p", voice_engine=engine)
        for i, engine in enumerate(engines)
    ]
    return ScriptContent(title="T", segments=[Segment(name="Intro", scenes=scenes)])


def test_voice_engine_for_content_prefers_an_attribution_requiring_engine():
    content = _content_with_engines("elevenlabs", "local:higgs-tts-3-4b")
    assert seo.voice_engine_for_content(content) == "local:higgs-tts-3-4b"


def test_voice_engine_for_content_returns_blank_when_unrecorded():
    assert seo.voice_engine_for_content(_content_with_engines("", "")) == ""
    assert seo.voice_engine_for_content(None) == ""


def test_short_form_seo_applies_attribution(monkeypatch):
    _local_higgs(monkeypatch)
    payload = (
        '{"shorts": [{"index": 1, "title": "A", "description": "D",'
        ' "hashtags": ["#a"], "tags": ["a"]}]}'
    )
    monkeypatch.setattr(seo, "chat", lambda *a, **k: payload)
    result = seo.generate_short_form_seo(
        "Project", [{"index": 1, "total": 1, "segment_name": "Intro", "duration_seconds": 10.0, "transcript": "t"}]
    )
    credit = seo.required_voice_attribution()
    assert credit
    assert all(credit in short.description for short in result.shorts)


def test_short_form_seo_skips_attribution_in_cloud_mode(monkeypatch):
    monkeypatch.setenv("LOCAL_MODELS_ENABLED", "false")
    monkeypatch.delenv("LOCAL_VOICE_MODE", raising=False)
    payload = (
        '{"shorts": [{"index": 1, "title": "A", "description": "D",'
        ' "hashtags": ["#a"], "tags": ["a"]}]}'
    )
    monkeypatch.setattr(seo, "chat", lambda *a, **k: payload)
    result = seo.generate_short_form_seo(
        "Project", [{"index": 1, "total": 1, "segment_name": "Intro", "duration_seconds": 10.0, "transcript": "t"}]
    )
    assert result.shorts[0].description == "D"
