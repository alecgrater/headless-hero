"""Thin wrapper around the Anthropic Python SDK."""

import logging
import os
import time

import anthropic

from config import DEFAULT_CLAUDE_MODEL
from integrations.usage_tracker import record_usage, get_model_pricing

logger = logging.getLogger(__name__)

def get_client() -> anthropic.Anthropic:
    """Return an Anthropic client, falling back to a local proxy if no API key is set."""
    if os.environ.get("ANTHROPIC_API_KEY"):
        return anthropic.Anthropic()
    return anthropic.Anthropic(
        base_url="http://localhost:11211/api/anthropic",
        api_key="sk-1234",
    )

def chat(
    system: str,
    user_message: str,
    *,
    model: str = DEFAULT_CLAUDE_MODEL,
    max_tokens: int = 4096,
    timeout: float = 600.0,
    script_id: str | None = None,
    cache: bool = False,
) -> str:
    """Send a single-turn message to Claude and return the text response."""
    client = get_client()
    logger.info("Calling Claude API model=%s max_tokens=%d timeout=%.0fs cache=%s", model, max_tokens, timeout, cache)
    t0 = time.monotonic()

    system_param: str | list[dict] = system
    if cache:
        system_param = [{"type": "text", "text": system, "cache_control": {"type": "ephemeral"}}]

    try:
        response = client.messages.create(
            model=model,
            max_tokens=max_tokens,
            system=system_param,
            messages=[{"role": "user", "content": user_message}],
            timeout=timeout,
        )
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
