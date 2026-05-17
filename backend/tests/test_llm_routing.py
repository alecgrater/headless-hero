"""Tests for routed LLM provider/model settings."""

from integrations.llm_client import (
    LLM_TASKS,
    _resolve_model,
    _resolve_openai_reasoning_effort,
    _resolve_provider,
)
from api.settings import ALLOWED_KEYS, _DEFAULTS, _PLAINTEXT_KEYS


def test_short_form_seo_has_dedicated_openai_default(monkeypatch):
    monkeypatch.delenv("SHORT_FORM_SEO_LLM_PROVIDER", raising=False)
    monkeypatch.delenv("SHORT_FORM_SEO_MODEL", raising=False)
    monkeypatch.setenv("LLM_PROVIDER", "ollama")

    assert LLM_TASKS["short_form_seo"]["provider_key"] == "SHORT_FORM_SEO_LLM_PROVIDER"
    assert _resolve_provider("short_form_seo") == "openai"
    assert _resolve_model("openai", "short_form_seo", None) == "gpt-5-mini"


def test_short_form_seo_settings_override_defaults(monkeypatch):
    monkeypatch.setenv("SHORT_FORM_SEO_LLM_PROVIDER", "anthropic")
    monkeypatch.setenv("SHORT_FORM_SEO_MODEL", "claude-sonnet-4-20250514")

    assert _resolve_provider("short_form_seo") == "anthropic"
    assert _resolve_model("anthropic", "short_form_seo", None) == "claude-sonnet-4-20250514"


def test_script_generation_defaults_to_anthropic_claude(monkeypatch):
    monkeypatch.delenv("SCRIPT_LLM_PROVIDER", raising=False)
    monkeypatch.delenv("SCRIPT_MODEL", raising=False)

    assert _resolve_provider("script") == "anthropic"
    assert _resolve_model("anthropic", "script", None) == "claude-opus-4-1-20250805"


def test_anthropic_bedrock_style_defaults_are_normalized(monkeypatch):
    monkeypatch.setenv("SCRIPT_LLM_PROVIDER", "anthropic")
    monkeypatch.setenv("SCRIPT_MODEL", "anthropic.claude-opus-4-6-v1")

    assert _resolve_model("anthropic", "script", None) == "claude-opus-4-1-20250805"


def test_structured_openai_tasks_use_minimal_reasoning_by_default(monkeypatch):
    monkeypatch.delenv("OPENAI_REASONING_EFFORT_ELI", raising=False)

    for task in ["fx", "seo", "short_form_seo", "media", "eli", "analysis", "hook_detect"]:
        monkeypatch.delenv(f"OPENAI_REASONING_EFFORT_{task.upper()}", raising=False)
        assert _resolve_openai_reasoning_effort(task) == "minimal"


def test_generation_openai_tasks_keep_low_reasoning_by_default(monkeypatch):
    for task in ["script", "idea", "hook"]:
        monkeypatch.delenv(f"OPENAI_REASONING_EFFORT_{task.upper()}", raising=False)
        assert _resolve_openai_reasoning_effort(task) == "low"


def test_openai_reasoning_efforts_are_exposed_as_settings():
    for task, config in LLM_TASKS.items():
        key = f"OPENAI_REASONING_EFFORT_{task.upper()}"

        assert key in ALLOWED_KEYS
        assert key in _PLAINTEXT_KEYS
        if config.get("openai_reasoning_effort"):
            assert _DEFAULTS[key] == config["openai_reasoning_effort"]
