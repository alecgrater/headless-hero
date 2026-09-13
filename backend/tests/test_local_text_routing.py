from integrations import llm_client


def _local(monkeypatch):
    monkeypatch.setenv("LOCAL_MODELS_ENABLED", "true")
    monkeypatch.delenv("LOCAL_TEXT_MODE", raising=False)
    monkeypatch.delenv("LOCAL_TEXT_MODEL", raising=False)
    monkeypatch.delenv("LOCAL_TEXT_FAST_MODEL", raising=False)


def test_local_mode_forces_ollama_even_when_task_prefers_anthropic(monkeypatch):
    _local(monkeypatch)
    monkeypatch.setenv("SCRIPT_LLM_PROVIDER", "anthropic")
    assert llm_client._resolve_provider("script") == "ollama"


def test_cloud_mode_leaves_task_provider_alone(monkeypatch):
    monkeypatch.setenv("LOCAL_MODELS_ENABLED", "false")
    monkeypatch.delenv("LOCAL_TEXT_MODE", raising=False)
    monkeypatch.setenv("SCRIPT_LLM_PROVIDER", "anthropic")
    assert llm_client._resolve_provider("script") == "anthropic"


def test_text_pinned_cloud_overrides_master_switch(monkeypatch):
    _local(monkeypatch)
    monkeypatch.setenv("LOCAL_TEXT_MODE", "cloud")
    monkeypatch.setenv("SCRIPT_LLM_PROVIDER", "anthropic")
    assert llm_client._resolve_provider("script") == "anthropic"


def test_narrative_task_uses_local_text_model(monkeypatch):
    _local(monkeypatch)
    monkeypatch.setenv("LOCAL_TEXT_MODEL", "qwen3.8-27b")
    assert llm_client._resolve_model("ollama", "script", None) == "hf.co/unsloth/Qwen3.8-27B-GGUF:Q4_K_M"


def test_minimal_effort_task_uses_fast_model_when_set(monkeypatch):
    _local(monkeypatch)
    monkeypatch.setenv("LOCAL_TEXT_FAST_MODEL", "qwen3.8-27b")
    # "fx" is declared with openai_reasoning_effort="minimal"
    assert llm_client._resolve_model("ollama", "fx", None) == "hf.co/unsloth/Qwen3.8-27B-GGUF:Q4_K_M"


def test_local_mode_ignores_stale_cloud_model_setting(monkeypatch):
    _local(monkeypatch)
    monkeypatch.setenv("SCRIPT_MODEL", "claude-opus-4-7")
    resolved = llm_client._resolve_model("ollama", "script", None)
    assert resolved.startswith("hf.co/")


def test_local_mode_ignores_explicit_cloud_model_argument(monkeypatch):
    _local(monkeypatch)
    resolved = llm_client._resolve_model("ollama", "script", "claude-opus-4-7")
    assert resolved.startswith("hf.co/")


def test_explicit_model_argument_still_wins_outside_local_mode(monkeypatch):
    monkeypatch.setenv("LOCAL_MODELS_ENABLED", "false")
    monkeypatch.delenv("LOCAL_TEXT_MODE", raising=False)
    assert llm_client._resolve_model("anthropic", "script", "claude-sonnet-4-6") == "claude-sonnet-4-6"


def test_fast_tier_ignores_a_wrong_modality_id(monkeypatch):
    _local(monkeypatch)
    monkeypatch.setenv("LOCAL_TEXT_FAST_MODEL", "kokoro-82m")
    assert llm_client._resolve_model("ollama", "fx", None) == "hf.co/unsloth/Qwen3.8-27B-GGUF:Q4_K_M"
