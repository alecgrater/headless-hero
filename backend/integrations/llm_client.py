"""Thin wrapper around routed LLM providers (Anthropic, OpenAI, or Ollama)."""

import json
import logging
import os
import re
import time

import anthropic

from config import BALANCED_CLAUDE_MODEL, DEFAULT_CLAUDE_MODEL, DEFAULT_OPENAI_MODEL, FAST_CLAUDE_MODEL
from integrations.usage_tracker import record_usage, get_model_pricing

logger = logging.getLogger(__name__)

_OLLAMA_BASE_URL = "http://localhost:11434/v1"
_DEFAULT_QWEN_MODEL = "qwen3:14b"
_DEFAULT_TASK = "script"

_THINK_BLOCK_RE = re.compile(r"<think>.*?</think>\s*", re.DOTALL)

ALLOWED_PROVIDERS = {"anthropic", "ollama", "openai"}

_ANTHROPIC_MODEL_ALIASES = {
    # Legacy Headless Hero defaults that used Bedrock-style or provisional ids.
    "anthropic.claude-opus-4-6-v1": DEFAULT_CLAUDE_MODEL,
    "anthropic.claude-sonnet-4-6": BALANCED_CLAUDE_MODEL,
    "anthropic.claude-sonnet-4-5-20250929-v1:0": BALANCED_CLAUDE_MODEL,
    "anthropic.claude-haiku-4-5-20251001-v1:0": FAST_CLAUDE_MODEL,
    "claude-opus-4-1-20250805": DEFAULT_CLAUDE_MODEL,
    "claude-opus-4-20250514": DEFAULT_CLAUDE_MODEL,
    "claude-sonnet-4-20250514": BALANCED_CLAUDE_MODEL,
    "claude-3-7-sonnet-20250219": BALANCED_CLAUDE_MODEL,
    "claude-3-5-haiku-20241022": FAST_CLAUDE_MODEL,
    "claude-haiku-4-5": FAST_CLAUDE_MODEL,
    # Common AWS Bedrock ids for currently supported Claude snapshots.
    "anthropic.claude-opus-4-1-20250805-v1:0": DEFAULT_CLAUDE_MODEL,
    "anthropic.claude-opus-4-20250514-v1:0": DEFAULT_CLAUDE_MODEL,
    "anthropic.claude-sonnet-4-20250514-v1:0": BALANCED_CLAUDE_MODEL,
    "anthropic.claude-3-7-sonnet-20250219-v1:0": BALANCED_CLAUDE_MODEL,
    "anthropic.claude-3-5-haiku-20241022-v1:0": FAST_CLAUDE_MODEL,
}

# Valid OpenAI reasoning_effort values for GPT-5 / o-series reasoning models.
# Used in LLM_TASKS["<task>"]["openai_reasoning_effort"] and the
# OPENAI_REASONING_EFFORT_<TASK> env-var override.
VALID_OPENAI_REASONING_EFFORTS = {"minimal", "low", "medium", "high"}

LLM_TASKS: dict[str, dict[str, str]] = {
    "script": {
        "label": "Script & cold opens",
        "provider_key": "SCRIPT_LLM_PROVIDER",
        "model_key": "SCRIPT_MODEL",
        "default_provider": "anthropic",
        "default_anthropic_model": DEFAULT_CLAUDE_MODEL,
        "default_openai_model": DEFAULT_OPENAI_MODEL,
        "openai_reasoning_effort": "low",
    },
    "idea": {
        "label": "Ideas & brainstorming",
        "provider_key": "IDEA_LLM_PROVIDER",
        "model_key": "IDEA_MODEL",
        "default_provider": "openai",
        "default_anthropic_model": BALANCED_CLAUDE_MODEL,
        "default_openai_model": "gpt-5-mini",
        "openai_reasoning_effort": "low",
    },
    "fx": {
        "label": "FX assignment",
        "provider_key": "FX_LLM_PROVIDER",
        "model_key": "FX_MODEL",
        "default_provider": "ollama",
        "default_anthropic_model": BALANCED_CLAUDE_MODEL,
        "default_openai_model": "gpt-5-mini",
        "openai_reasoning_effort": "minimal",
    },
    "seo": {
        "label": "SEO metadata",
        "provider_key": "SEO_LLM_PROVIDER",
        "model_key": "SEO_MODEL",
        "default_provider": "ollama",
        "default_anthropic_model": BALANCED_CLAUDE_MODEL,
        "default_openai_model": "gpt-5-mini",
        "openai_reasoning_effort": "minimal",
    },
    "short_form_seo": {
        "label": "Short-form SEO metadata",
        "provider_key": "SHORT_FORM_SEO_LLM_PROVIDER",
        "model_key": "SHORT_FORM_SEO_MODEL",
        "default_provider": "openai",
        "default_anthropic_model": BALANCED_CLAUDE_MODEL,
        "default_openai_model": "gpt-5-mini",
        "openai_reasoning_effort": "minimal",
    },
    "hook": {
        "label": "Hook scoring/refining",
        "provider_key": "HOOK_LLM_PROVIDER",
        "model_key": "HOOK_MODEL",
        "default_provider": "openai",
        "default_anthropic_model": FAST_CLAUDE_MODEL,
        "default_openai_model": "gpt-5.5",
        "openai_reasoning_effort": "low",
    },
    "media": {
        "label": "Media routing",
        "provider_key": "MEDIA_LLM_PROVIDER",
        "model_key": "MEDIA_MODEL",
        "default_provider": "ollama",
        "default_anthropic_model": BALANCED_CLAUDE_MODEL,
        "default_openai_model": "gpt-5-mini",
        "openai_reasoning_effort": "minimal",
    },
    "eli": {
        "label": "Eli animation",
        "provider_key": "ELI_LLM_PROVIDER",
        "model_key": "ELI_MODEL",
        "default_provider": "ollama",
        "default_anthropic_model": FAST_CLAUDE_MODEL,
        "default_openai_model": "gpt-5-nano",
        "openai_reasoning_effort": "minimal",
    },
    "analysis": {
        "label": "Analysis & scoring",
        "provider_key": "ANALYSIS_LLM_PROVIDER",
        "model_key": "ANALYSIS_MODEL",
        "default_provider": "ollama",
        "default_anthropic_model": FAST_CLAUDE_MODEL,
        "default_openai_model": "gpt-5-nano",
        "openai_reasoning_effort": "minimal",
    },
    "hook_detect": {
        "label": "Hook detection (short-form)",
        "provider_key": "HOOK_DETECT_LLM_PROVIDER",
        "model_key": "HOOK_DETECT_MODEL",
        "default_provider": "ollama",
        "default_anthropic_model": FAST_CLAUDE_MODEL,
        "default_openai_model": "gpt-5-nano",
        "openai_reasoning_effort": "minimal",
    },
}


def _get_provider() -> str:
    """Resolve the active LLM provider. Defaults to 'anthropic' if unset."""
    provider = (os.environ.get("LLM_PROVIDER", "anthropic") or "anthropic").strip().lower()
    if provider not in ALLOWED_PROVIDERS:
        logger.warning("Ignoring unsupported LLM_PROVIDER=%r; using anthropic", provider)
        return "anthropic"
    return provider


def _resolve_provider(task: str | None) -> str:
    task_config = LLM_TASKS.get(task or "")
    if task_config:
        task_provider = os.environ.get(task_config["provider_key"], "").strip().lower()
        if task_provider:
            if task_provider not in ALLOWED_PROVIDERS:
                logger.warning(
                    "Ignoring unsupported %s=%r; using %s",
                    task_config["provider_key"],
                    task_provider,
                    task_config["default_provider"],
                )
                return task_config["default_provider"]
            return task_provider
        return task_config["default_provider"]
    return _get_provider()


def _default_model_for_provider(provider: str, task: str | None) -> str:
    task_config = LLM_TASKS.get(task or "") or LLM_TASKS[_DEFAULT_TASK]
    if provider == "ollama":
        return os.environ.get("QWEN_MODEL", _DEFAULT_QWEN_MODEL).strip() or _DEFAULT_QWEN_MODEL
    if provider == "openai":
        return task_config["default_openai_model"]
    return task_config["default_anthropic_model"]


def _normalize_model_for_provider(provider: str, task: str | None, model: str) -> str:
    configured = _ANTHROPIC_MODEL_ALIASES.get(model, model) if provider == "anthropic" else model
    configured_lower = configured.lower()
    if provider == "ollama" and configured_lower.startswith(("anthropic.", "claude-", "gpt-", "o1", "o3", "o4")):
        return _default_model_for_provider(provider, task)
    if provider == "openai" and configured_lower.startswith(("anthropic.", "claude-")):
        task_config = LLM_TASKS.get(task or "") or LLM_TASKS[_DEFAULT_TASK]
        return task_config["default_openai_model"]
    if provider == "anthropic" and configured_lower.startswith(("gpt-", "o1", "o3", "o4")):
        task_config = LLM_TASKS.get(task or "") or LLM_TASKS[_DEFAULT_TASK]
        return task_config["default_anthropic_model"]
    return configured


def _resolve_model(provider: str, task: str | None, model: str | None) -> str:
    if model:
        return _normalize_model_for_provider(provider, task, model)
    task_config = LLM_TASKS.get(task or "")
    if task_config:
        configured = os.environ.get(task_config["model_key"], "").strip()
        if configured:
            return _normalize_model_for_provider(provider, task, configured)
    return _default_model_for_provider(provider, task)


def _resolve_openai_reasoning_effort(task: str | None) -> str | None:
    """Per-task override via OPENAI_REASONING_EFFORT_<TASK>; otherwise the LLM_TASKS default.

    Returns None when no preference is set, leaving the OpenAI default ("medium" for GPT-5).
    Invalid env-var values are logged and ignored (falls back to the LLM_TASKS default).
    """
    task_config = LLM_TASKS.get(task or "")
    if task:
        env_key = f"OPENAI_REASONING_EFFORT_{task.upper()}"
        env_value = os.environ.get(env_key, "").strip().lower()
        if env_value:
            if env_value in VALID_OPENAI_REASONING_EFFORTS:
                return env_value
            logger.warning(
                "%s=%r is not a valid reasoning_effort — ignoring (valid: %s)",
                env_key, env_value, sorted(VALID_OPENAI_REASONING_EFFORTS),
            )
    if task_config:
        return task_config.get("openai_reasoning_effort")
    return None


def get_client(provider: str | None = None) -> anthropic.Anthropic:
    """Return an Anthropic client using ANTHROPIC_API_KEY."""
    provider = provider or _get_provider()
    if provider != "anthropic":
        raise ValueError(f"Anthropic client requested for unsupported provider: {provider}")
    if os.environ.get("ANTHROPIC_API_KEY"):
        return anthropic.Anthropic()
    raise RuntimeError("ANTHROPIC_API_KEY is required when using the Anthropic provider.")


def chat(
    system: str,
    user_message: str,
    *,
    model: str | None = None,
    max_tokens: int = 4096,
    timeout: float = 600.0,
    script_id: str | None = None,
    cache: bool = False,
    json_mode: bool = False,
    task: str | None = None,
) -> str:
    """Send a single-turn message to the active LLM provider and return the text response.

    Task-specific settings can override the global provider/model using the
    keys declared in LLM_TASKS. `model` remains an explicit request override.
    """
    provider = _resolve_provider(task)
    resolved_model = _resolve_model(provider, task, model)

    logger.info(
        "LLM routing: task=%s provider=%s model=%s json_mode=%s",
        task or "default", provider, resolved_model, json_mode,
    )

    if provider == "ollama":
        return _chat_ollama(
            system=system,
            user_message=user_message,
            model=resolved_model,
            max_tokens=max_tokens,
            timeout=timeout,
            script_id=script_id,
            cache=cache,
            json_mode=json_mode,
            task=task,
        )

    if provider == "openai":
        reasoning_effort = _resolve_openai_reasoning_effort(task)
        return _chat_openai(
            system=system,
            user_message=user_message,
            model=resolved_model,
            max_tokens=max_tokens,
            timeout=timeout,
            script_id=script_id,
            cache=cache,
            json_mode=json_mode,
            task=task,
            reasoning_effort=reasoning_effort,
        )

    client = get_client(provider)
    logger.info(
        "Calling Claude API provider=%s task=%s model=%s max_tokens=%d timeout=%.0fs cache=%s",
        provider, task or "default", resolved_model, max_tokens, timeout, cache,
    )
    t0 = time.monotonic()

    system_param: str | list[dict] | anthropic.NotGiven
    if not system:
        system_param = anthropic.NOT_GIVEN
    elif cache:
        system_param = [{"type": "text", "text": system, "cache_control": {"type": "ephemeral"}}]
    else:
        system_param = system

    try:
        response = client.messages.create(
            model=resolved_model,
            max_tokens=max_tokens,
            system=system_param,
            messages=[{"role": "user", "content": user_message}],
            timeout=timeout,
        )
    except anthropic.BadRequestError:
        if cache:
            logger.warning("Cache control rejected by API — retrying without cache (model=%s)", resolved_model)
            response = client.messages.create(
                model=resolved_model,
                max_tokens=max_tokens,
                system=system if system else anthropic.NOT_GIVEN,
                messages=[{"role": "user", "content": user_message}],
                timeout=timeout,
            )
        else:
            raise
    except Exception:
        elapsed = time.monotonic() - t0
        logger.error("Anthropic API call failed after %.1fs (model=%s)", elapsed, resolved_model, exc_info=True)
        raise

    elapsed = time.monotonic() - t0

    usage = response.usage
    input_tok = usage.input_tokens if usage else 0
    output_tok = usage.output_tokens if usage else 0
    cache_read_tok = getattr(usage, "cache_read_input_tokens", 0) or 0
    cache_create_tok = getattr(usage, "cache_creation_input_tokens", 0) or 0

    pricing = get_model_pricing(resolved_model)
    cost = (
        (input_tok - cache_read_tok - cache_create_tok) * pricing["input"]
        + cache_create_tok * pricing["input"] * 1.25
        + cache_read_tok * pricing["cache_read"]
        + output_tok * pricing["output"]
    )
    record_usage(
        service="anthropic",
        operation="chat",
        model=resolved_model,
        input_tokens=input_tok,
        output_tokens=output_tok,
        cost_estimate=cost,
        metadata_json=json.dumps({"task": task}) if task else "",
        script_id=script_id,
    )
    logger.info(
        "Claude API call complete in %.1fs — %s input (%s cached) / %s output tokens (model=%s)",
        elapsed, input_tok, cache_read_tok, output_tok, resolved_model,
    )

    return response.content[0].text


def _strip_think_blocks(text: str) -> str:
    """Remove <think>...</think> reasoning blocks Qwen3 emits by default."""
    cleaned = _THINK_BLOCK_RE.sub("", text)
    return cleaned.strip()


def _chat_ollama(
    *,
    system: str,
    user_message: str,
    model: str,
    max_tokens: int,
    timeout: float,
    script_id: str | None,
    cache: bool,
    json_mode: bool,
    task: str | None,
) -> str:
    """Call a local Ollama model via its OpenAI-compatible /v1 endpoint."""
    # Lazy import so the backend still starts if openai isn't installed yet.
    from openai import BadRequestError, OpenAI

    qwen_model = model.strip() or _DEFAULT_QWEN_MODEL

    try:
        num_ctx = int(os.environ.get("QWEN_NUM_CTX", "16384"))
    except ValueError:
        num_ctx = 16384

    if cache:
        logger.debug("Ollama path ignores cache=True (KV prefix caching is automatic)")

    # json_object mode requires the prompt to mention "json" or the server will
    # reject the request. Nudge the user message if neither side mentions it.
    effective_user_message = user_message
    if json_mode and "json" not in (system + user_message).lower():
        effective_user_message = user_message + "\n\nReturn ONLY valid JSON."

    messages: list[dict] = []
    if system:
        messages.append({"role": "system", "content": system})
    messages.append({"role": "user", "content": effective_user_message})

    client = OpenAI(api_key="ollama", base_url=_OLLAMA_BASE_URL, timeout=timeout)
    logger.info(
        "Calling Ollama task=%s model=%s max_tokens=%d num_ctx=%d timeout=%.0fs json_mode=%s keep_alive=30m",
        task or "default", qwen_model, max_tokens, num_ctx, timeout, json_mode,
    )
    t0 = time.monotonic()

    kwargs: dict = {
        "model": qwen_model,
        "max_completion_tokens": max_tokens,
        "messages": messages,
        "extra_body": {"keep_alive": "30m", "options": {"num_ctx": num_ctx}},
    }
    if json_mode:
        kwargs["response_format"] = {"type": "json_object"}

    try:
        response = client.chat.completions.create(**kwargs)
    except BadRequestError:
        if json_mode:
            logger.warning(
                "Ollama rejected response_format=json_object — retrying without it (model=%s)",
                qwen_model,
            )
            kwargs.pop("response_format", None)
            response = client.chat.completions.create(**kwargs)
        else:
            elapsed = time.monotonic() - t0
            logger.error("Ollama call failed after %.1fs (model=%s)", elapsed, qwen_model, exc_info=True)
            raise
    except Exception:
        elapsed = time.monotonic() - t0
        logger.error("Ollama call failed after %.1fs (model=%s)", elapsed, qwen_model, exc_info=True)
        raise

    elapsed = time.monotonic() - t0

    raw_text = (response.choices[0].message.content or "").strip()
    text = _strip_think_blocks(raw_text)

    usage = getattr(response, "usage", None)
    input_tok = getattr(usage, "prompt_tokens", 0) if usage else 0
    output_tok = getattr(usage, "completion_tokens", 0) if usage else 0

    record_usage(
        service="ollama",
        operation="chat",
        model=qwen_model,
        input_tokens=input_tok,
        output_tokens=output_tok,
        characters=len(system) + len(effective_user_message) + len(text),
        cost_estimate=0.0,
        metadata_json=json.dumps({"task": task}) if task else "",
        script_id=script_id,
    )
    logger.info(
        "Ollama call complete in %.1fs — %s input / %s output tokens (model=%s)",
        elapsed, input_tok, output_tok, qwen_model,
    )

    return text


def _chat_openai(
    *,
    system: str,
    user_message: str,
    model: str,
    max_tokens: int,
    timeout: float,
    script_id: str | None,
    cache: bool,
    json_mode: bool,
    task: str | None,
    reasoning_effort: str | None = None,
) -> str:
    """Call OpenAI via Chat Completions."""
    from openai import BadRequestError, OpenAI

    if not os.environ.get("OPENAI_API_KEY"):
        raise RuntimeError("OPENAI_API_KEY is not configured")
    if cache:
        logger.debug("OpenAI path ignores cache=True")

    effective_user_message = user_message
    if json_mode and "json" not in (system + user_message).lower():
        effective_user_message = user_message + "\n\nReturn ONLY valid JSON."

    messages: list[dict] = []
    if system:
        messages.append({"role": "system", "content": system})
    messages.append({"role": "user", "content": effective_user_message})

    client = OpenAI(timeout=timeout)
    logger.info(
        "Calling OpenAI task=%s model=%s max_tokens=%d timeout=%.0fs json_mode=%s reasoning_effort=%s",
        task or "default", model, max_tokens, timeout, json_mode, reasoning_effort or "default",
    )
    t0 = time.monotonic()

    kwargs: dict = {
        "model": model,
        "messages": messages,
        "max_completion_tokens": max_tokens,
    }
    if json_mode:
        kwargs["response_format"] = {"type": "json_object"}
    if reasoning_effort:
        kwargs["reasoning_effort"] = reasoning_effort

    try:
        response = client.chat.completions.create(**kwargs)
    except BadRequestError as e:
        err_text = str(e).lower()
        stripped: list[str] = []
        # Narrow match for reasoning_effort: only strip when the error explicitly references reasoning.
        if reasoning_effort and "reasoning" in err_text and "reasoning_effort" in kwargs:
            kwargs.pop("reasoning_effort", None)
            stripped.append("reasoning_effort")
        # Broad fallback for json_mode: any BadRequestError while json_mode is set strips response_format.
        # Some models / OpenAI-compatible providers don't put "response_format" in the error text verbatim.
        elif json_mode and "response_format" in kwargs:
            kwargs.pop("response_format", None)
            stripped.append("response_format")
        if not stripped:
            elapsed = time.monotonic() - t0
            logger.error("OpenAI call failed after %.1fs (model=%s)", elapsed, model, exc_info=True)
            raise
        logger.warning(
            "OpenAI rejected %s — retrying without it (model=%s, error=%s)",
            stripped, model, err_text[:200],
        )
        response = client.chat.completions.create(**kwargs)
    except Exception:
        elapsed = time.monotonic() - t0
        logger.error("OpenAI call failed after %.1fs (model=%s)", elapsed, model, exc_info=True)
        raise

    elapsed = time.monotonic() - t0
    text = (response.choices[0].message.content or "").strip()

    usage = getattr(response, "usage", None)
    input_tok = getattr(usage, "prompt_tokens", 0) if usage else 0
    output_tok = getattr(usage, "completion_tokens", 0) if usage else 0
    details = getattr(usage, "prompt_tokens_details", None) if usage else None
    cached_tok = getattr(details, "cached_tokens", 0) or 0
    pricing = get_model_pricing(model)
    cost = (
        max(input_tok - cached_tok, 0) * pricing["input"]
        + cached_tok * pricing["cache_read"]
        + output_tok * pricing["output"]
    )

    record_usage(
        service="openai",
        operation="chat",
        model=model,
        input_tokens=input_tok,
        output_tokens=output_tok,
        cost_estimate=cost,
        metadata_json=json.dumps({"task": task}) if task else "",
        script_id=script_id,
    )
    logger.info(
        "OpenAI call complete in %.1fs — %s input / %s output tokens (model=%s)",
        elapsed, input_tok, output_tok, model,
    )

    return text
