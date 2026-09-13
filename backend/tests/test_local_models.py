import pytest

from integrations import local_models


def test_registry_entries_are_internally_consistent():
    for model_id, model in local_models.REGISTRY.items():
        assert model.id == model_id
        assert model.modality in {"text", "image", "voice"}
        assert model.backend in {"ollama", "comfyui", "mlx-audio"}
        assert model.weights
        assert model.approx_resident_gb > 0
        assert model.license
        if model.requires_attribution:
            assert model.attribution_text


def test_modality_source_defaults_to_cloud(monkeypatch):
    monkeypatch.delenv("LOCAL_MODELS_ENABLED", raising=False)
    monkeypatch.delenv("LOCAL_TEXT_MODE", raising=False)
    assert local_models.modality_source("text") == "cloud"


def test_master_switch_turns_every_modality_local(monkeypatch):
    monkeypatch.setenv("LOCAL_MODELS_ENABLED", "true")
    for modality in ("text", "image", "voice"):
        monkeypatch.delenv(f"LOCAL_{modality.upper()}_MODE", raising=False)
        assert local_models.modality_source(modality) == "local"


def test_modality_override_beats_master_switch(monkeypatch):
    monkeypatch.setenv("LOCAL_MODELS_ENABLED", "true")
    monkeypatch.setenv("LOCAL_IMAGE_MODE", "cloud")
    monkeypatch.delenv("LOCAL_TEXT_MODE", raising=False)
    assert local_models.modality_source("image") == "cloud"
    assert local_models.modality_source("text") == "local"


def test_modality_override_works_with_master_switch_off(monkeypatch):
    monkeypatch.setenv("LOCAL_MODELS_ENABLED", "false")
    monkeypatch.setenv("LOCAL_VOICE_MODE", "local")
    assert local_models.modality_source("voice") == "local"


def test_unknown_mode_value_falls_back_to_auto(monkeypatch):
    monkeypatch.setenv("LOCAL_MODELS_ENABLED", "true")
    monkeypatch.setenv("LOCAL_TEXT_MODE", "banana")
    assert local_models.modality_source("text") == "local"


def test_active_model_reads_env_and_falls_back_to_default(monkeypatch):
    monkeypatch.delenv("LOCAL_VOICE_MODEL", raising=False)
    assert local_models.active_model("voice").id == local_models.DEFAULT_MODEL_IDS["voice"]
    monkeypatch.setenv("LOCAL_VOICE_MODEL", "kokoro-82m")
    assert local_models.active_model("voice").id == "kokoro-82m"


def test_active_model_ignores_wrong_modality_id(monkeypatch):
    monkeypatch.setenv("LOCAL_VOICE_MODEL", "flux2-klein-4b")
    assert local_models.active_model("voice").id == local_models.DEFAULT_MODEL_IDS["voice"]


def test_higgs_requires_attribution_and_others_do_not():
    assert local_models.attribution_for("higgs-tts-3-4b")
    assert local_models.attribution_for("kokoro-82m") == ""
    assert local_models.attribution_for("chatterbox") == ""


def test_get_model_rejects_unknown_id():
    with pytest.raises(KeyError):
        local_models.get_model("nope")


def test_models_for_returns_only_that_modality():
    for modality in local_models.MODALITIES:
        assert {m.modality for m in local_models.models_for(modality)} == {modality}


def test_modality_source_rejects_unknown_modality():
    with pytest.raises(ValueError):
        local_models.modality_source("smell")
