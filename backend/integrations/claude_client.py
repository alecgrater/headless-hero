"""Thin wrapper around LLM providers (Anthropic, local proxy, or Ollama)."""

import logging
import os
import re
import time

import anthropic

from config import DEFAULT_CLAUDE_MODEL
from integrations.usage_tracker import record_usage, get_model_pricing

logger = logging.getLogger(__name__)

_CLAUDE_CODE_PROXY_URL = "http://localhost:11211/api/anthropic"
_OLLAMA_BASE_URL = "http://localhost:11434/v1"
_DEFAULT_QWEN_MODEL = "qwen3:14b"

_THINK_BLOCK_RE = re.compile(r"<think>.*?</think>\s*", re.DOTALL)

ALLOWED_PROVIDERS = {"anthropic", "claude-code-proxy", "ollama"}


def _get_provider() -> str:
    """Resolve the active LLM provider. Defaults to 'anthropic' if unset."""
    return (os.environ.get("LLM_PROVIDER", "anthropic") or "anthropic").strip().lower()


def get_client() -> anthropic.Anthropic:
    """Return an Anthropic client, routing per LLM_PROVIDER setting.

    - 'claude-code-proxy': always hit localhost:11211 proxy (ignore real key)
    - 'anthropic' (default): real API if key present, proxy otherwise
    """
    provider = _get_provider()
    if provider == "claude-code-proxy":
        return anthropic.Anthropic(base_url=_CLAUDE_CODE_PROXY_URL, api_key="sk-1234")
    if os.environ.get("ANTHROPIC_API_KEY"):
        return anthropic.Anthropic()
    return anthropic.Anthropic(base_url=_CLAUDE_CODE_PROXY_URL, api_key="sk-1234")


def chat(
    system: str,
    user_message: str,
    *,
    model: str = DEFAULT_CLAUDE_MODEL,
    max_tokens: int = 4096,
    timeout: float = 600.0,
    script_id: str | None = None,
    cache: bool = False,
    json_mode: bool = False,
) -> str:
    """Send a single-turn message to the active LLM provider and return the text response.

    When LLM_PROVIDER=ollama, the `model` argument is ignored and QWEN_MODEL
    (default qwen3:14b) is used instead. `json_mode=True` asks the provider
    to return JSON (honored by Ollama; Anthropic ignores it but still produces
    JSON when the prompt asks for it).
    """
    if _get_provider() == "ollama":
        return _chat_ollama(
            system=system,
            user_message=user_message,
            max_tokens=max_tokens,
            timeout=timeout,
            script_id=script_id,
            cache=cache,
            json_mode=json_mode,
        )

    client = get_client()
    logger.info("Calling Claude API model=%s max_tokens=%d timeout=%.0fs cache=%s", model, max_tokens, timeout, cache)
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
            model=model,
            max_tokens=max_tokens,
            system=system_param,
            messages=[{"role": "user", "content": user_message}],
            timeout=timeout,
        )
    except anthropic.BadRequestError:
        if cache:
            logger.warning("Cache control rejected by API — retrying without cache (model=%s)", model)
            response = client.messages.create(
                model=model,
                max_tokens=max_tokens,
                system=system if system else anthropic.NOT_GIVEN,
                messages=[{"role": "user", "content": user_message}],
                timeout=timeout,
            )
        else:
            raise
    except Exception:
        elapsed = time.monotonic() - t0
        logger.error("Anthropic API call failed after %.1fs (model=%s)", elapsed, model, exc_info=True)
        raise

    elapsed = time.monotonic() - t0

    usage = response.usage
    input_tok = usage.input_tokens if usage else 0
    output_tok = usage.output_tokens if usage else 0
    cache_read_tok = getattr(usage, "cache_read_input_tokens", 0) or 0
    cache_create_tok = getattr(usage, "cache_creation_input_tokens", 0) or 0

    pricing = get_model_pricing(model)
    cost = (
        (input_tok - cache_read_tok - cache_create_tok) * pricing["input"]
        + cache_create_tok * pricing["input"] * 1.25
        + cache_read_tok * pricing["cache_read"]
        + output_tok * pricing["output"]
    )
    record_usage(
        service="anthropic",
        operation="chat",
        model=model,
        input_tokens=input_tok,
        output_tokens=output_tok,
        cost_estimate=cost,
        script_id=script_id,
    )
    logger.info(
        "Claude API call complete in %.1fs — %s input (%s cached) / %s output tokens (model=%s)",
        elapsed, input_tok, cache_read_tok, output_tok, model,
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
    max_tokens: int,
    timeout: float,
    script_id: str | None,
    cache: bool,
    json_mode: bool,
) -> str:
    """Call a local Ollama model via its OpenAI-compatible /v1 endpoint."""
    # Lazy import so the backend still starts if openai isn't installed yet.
    from openai import BadRequestError, OpenAI

    qwen_model = os.environ.get("QWEN_MODEL", _DEFAULT_QWEN_MODEL).strip() or _DEFAULT_QWEN_MODEL

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
        "Calling Ollama model=%s max_tokens=%d num_ctx=%d timeout=%.0fs json_mode=%s keep_alive=30m",
        qwen_model, max_tokens, num_ctx, timeout, json_mode,
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
        cost_estimate=0.0,
        script_id=script_id,
    )
    logger.info(
        "Ollama call complete in %.1fs — %s input / %s output tokens (model=%s)",
        elapsed, input_tok, output_tok, qwen_model,
    )

    return text
