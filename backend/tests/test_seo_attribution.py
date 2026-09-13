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
