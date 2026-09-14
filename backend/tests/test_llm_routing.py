"""Tests for routed LLM provider/model settings."""

from integrations.llm_client import (
    ANTHROPIC_MODEL_ALIASES,
    LLM_TASKS,
    OPENAI_MODEL_ALIASES,
    STALE_MODEL_UPGRADES,
    VALID_OPENAI_REASONING_EFFORTS,
    _resolve_model,
    _resolve_openai_reasoning_effort,
    _resolve_provider,
)
from integrations.usage_tracker import get_model_pricing
from api.settings import ALLOWED_KEYS, _DEFAULTS, _PLAINTEXT_KEYS


def test_retired_openai_models_upgrade_within_the_same_provider():
    """A user who chose OpenAI for scripts must not be moved to Claude."""
    assert _resolve_model("openai", "script", "gpt-5.5") == "gpt-5.6"
    assert _resolve_model("openai", "script", "gpt-5-mini") == "gpt-5.6-terra"
    assert _resolve_model("openai", "script", "gpt-5-nano") == "gpt-5.6-luna"


def test_retired_claude_models_upgrade_to_current_tier():
    assert _resolve_model("anthropic", "script", "claude-opus-4-7") == "claude-opus-5"
    assert _resolve_model("anthropic", "script", "claude-sonnet-4-6") == "claude-sonnet-5"
    assert _resolve_model("anthropic", "script", "claude-haiku-4-5-20251001") == "claude-haiku-4-5"


def test_no_alias_maps_a_model_onto_itself():
    """A self-mapping entry is a no-op that hides a stale id from review."""
    for stale, current in STALE_MODEL_UPGRADES.items():
        assert stale != current, f"{stale} maps to itself"


def test_stale_map_covers_both_providers_without_collisions():
    overlap = ANTHROPIC_MODEL_ALIASES.keys() & OPENAI_MODEL_ALIASES.keys()
    assert not overlap, f"ids claimed by both providers: {sorted(overlap)}"
    assert len(STALE_MODEL_UPGRADES) == len(ANTHROPIC_MODEL_ALIASES) + len(OPENAI_MODEL_ALIASES)


def test_every_task_declares_a_tier_and_a_valid_reasoning_effort():
    """tier drives Local Mode's fast-model routing; it must not be inferred."""
    for name, task in LLM_TASKS.items():
        assert task["tier"] in {"fast", "standard"}, name
        assert task["openai_reasoning_effort"] in VALID_OPENAI_REASONING_EFFORTS, name


def test_retired_reasoning_effort_value_is_rewritten(monkeypatch):
    monkeypatch.setenv("OPENAI_REASONING_EFFORT_FX", "minimal")
    assert _resolve_openai_reasoning_effort("fx") == "none"


def test_short_form_seo_has_dedicated_openai_default(monkeypatch):
    monkeypatch.delenv("SHORT_FORM_SEO_LLM_PROVIDER", raising=False)
    monkeypatch.delenv("SHORT_FORM_SEO_MODEL", raising=False)
    monkeypatch.setenv("LLM_PROVIDER", "ollama")

    assert LLM_TASKS["short_form_seo"]["provider_key"] == "SHORT_FORM_SEO_LLM_PROVIDER"
    assert _resolve_provider("short_form_seo") == "openai"
    assert _resolve_model("openai", "short_form_seo", None) == "gpt-5.6-terra"


def test_short_form_seo_settings_override_defaults(monkeypatch):
    monkeypatch.setenv("SHORT_FORM_SEO_LLM_PROVIDER", "anthropic")
    monkeypatch.setenv("SHORT_FORM_SEO_MODEL", "claude-sonnet-5")

    assert _resolve_provider("short_form_seo") == "anthropic"
    assert _resolve_model("anthropic", "short_form_seo", None) == "claude-sonnet-5"


def test_script_generation_defaults_to_anthropic_claude(monkeypatch):
    monkeypatch.delenv("SCRIPT_LLM_PROVIDER", raising=False)
    monkeypatch.delenv("SCRIPT_MODEL", raising=False)

    assert _resolve_provider("script") == "anthropic"
    assert _resolve_model("anthropic", "script", None) == "claude-opus-5"


def test_anthropic_bedrock_style_defaults_are_normalized(monkeypatch):
    monkeypatch.setenv("SCRIPT_LLM_PROVIDER", "anthropic")
    monkeypatch.setenv("SCRIPT_MODEL", "anthropic.claude-opus-4-6-v1")

    assert _resolve_model("anthropic", "script", None) == "claude-opus-5"


def test_explicit_incompatible_model_override_falls_back_to_provider_default():
    assert _resolve_model("anthropic", "script", "gpt-5.6") == "claude-opus-5"
    assert _resolve_model("openai", "script", "claude-opus-5") == "gpt-5.6"
    assert _resolve_model("ollama", "script", "claude-opus-5") == "qwen3:14b"


def test_claude_pricing_uses_direct_anthropic_api_model_ids():
    assert get_model_pricing("claude-opus-5")["input"] == 5.0 / 1_000_000
    assert get_model_pricing("claude-sonnet-5")["output"] == 10.0 / 1_000_000


def test_structured_openai_tasks_use_no_reasoning_by_default(monkeypatch):
    monkeypatch.delenv("OPENAI_REASONING_EFFORT_ELI", raising=False)

    for task in ["fx", "seo", "short_form_seo", "media", "eli", "analysis", "hook_detect", "script_rating"]:
        monkeypatch.delenv(f"OPENAI_REASONING_EFFORT_{task.upper()}", raising=False)
        assert _resolve_openai_reasoning_effort(task) == "none"


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


def test_ai_video_scenes_per_segment_is_exposed_as_plaintext_setting():
    assert "AI_VIDEO_SCENES_PER_SEGMENT" in ALLOWED_KEYS
    assert "AI_VIDEO_SCENES_PER_SEGMENT" in _PLAINTEXT_KEYS
    assert _DEFAULTS["AI_VIDEO_SCENES_PER_SEGMENT"] == "2"


def test_subtitle_settings_are_exposed_as_plaintext_defaults():
    expected = {
        "SUBTITLE_COVERAGE_MODE": "all",
        "SUBTITLE_STYLE_KINETIC_ENABLED": "true",
    }

    for key, default in expected.items():
        assert key in ALLOWED_KEYS
        assert key in _PLAINTEXT_KEYS
        assert _DEFAULTS[key] == default

    # Clean is the floor of the two-style catalogue and burst is deleted; neither
    # carries a setting any more.
    for retired in ("SUBTITLE_STYLE_CLEAN_ENABLED", "SUBTITLE_STYLE_BURST_ENABLED"):
        assert retired not in ALLOWED_KEYS
        assert retired not in _DEFAULTS


def test_text_fingerprint_matches_the_routing_chat_would_use(monkeypatch):
    """The resume cache keys on this, so it must not drift from chat()'s routing.

    If it did, a half-finished run on one engine would resume on another and
    splice two models into one script — the bug the key exists to prevent.
    """
    from integrations import llm_client

    monkeypatch.setenv("LOCAL_MODELS_ENABLED", "false")
    monkeypatch.setenv("SCRIPT_LLM_PROVIDER", "anthropic")
    monkeypatch.setenv("SCRIPT_MODEL", "claude-opus-5")
    assert llm_client.text_fingerprint("script") == "anthropic:claude-opus-5"

    # Local Mode overrides both halves, exactly as _resolve_provider/_resolve_model do.
    monkeypatch.setenv("LOCAL_MODELS_ENABLED", "true")
    monkeypatch.delenv("LOCAL_TEXT_MODE", raising=False)
    monkeypatch.setenv("LOCAL_TEXT_MODEL", "qwen3.8-27b")
    local = llm_client.text_fingerprint("script")
    assert local.startswith("ollama:")
    assert local != "anthropic:claude-opus-5"

    # It is derived, not guessed: it equals the two resolvers chat() calls.
    provider = llm_client._resolve_provider("script")
    assert local == f"{provider}:{llm_client._resolve_model(provider, 'script', None)}"
