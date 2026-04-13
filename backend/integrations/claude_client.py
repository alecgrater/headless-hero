"""Thin wrapper around the Anthropic Python SDK."""

import logging
import os

import anthropic

from integrations.usage_tracker import (
    record_usage,
    ANTHROPIC_INPUT_PER_TOKEN,
    ANTHROPIC_OUTPUT_PER_TOKEN,
)

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
    model: str = "anthropic.claude-opus-4-6-v1",
    max_tokens: int = 4096,
    timeout: float = 600.0,
    script_id: str | None = None,
) -> str:
    """Send a single-turn message to Claude and return the text response."""
    client = get_client()
    logger.info("Calling Claude API model=%s max_tokens=%d timeout=%.0fs", model, max_tokens, timeout)
    try:
        response = client.messages.create(
            model=model,
            max_tokens=max_tokens,
            system=system,
            messages=[{"role": "user", "content": user_message}],
            timeout=timeout,
        )
    except Exception:
        logger.error("Anthropic API call failed (model=%s)", model, exc_info=True)
        raise

    # Record usage
    usage = response.usage
    input_tok = usage.input_tokens if usage else 0
    output_tok = usage.output_tokens if usage else 0
    cost = input_tok * ANTHROPIC_INPUT_PER_TOKEN + output_tok * ANTHROPIC_OUTPUT_PER_TOKEN
    record_usage(
        service="anthropic",
        operation="chat",
        model=model,
        input_tokens=input_tok,
        output_tokens=output_tok,
        cost_estimate=cost,
        script_id=script_id,
    )
    logger.info("Claude API call complete, usage: %s input / %s output tokens", input_tok, output_tok)

    return response.content[0].text
