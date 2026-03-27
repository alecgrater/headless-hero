"""Thin wrapper around the Anthropic Python SDK."""

import os

import anthropic

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
    model: str = "claude-sonnet-4-20250514",
    max_tokens: int = 4096,
) -> str:
    """Send a single-turn message to Claude and return the text response."""
    client = get_client()
    response = client.messages.create(
        model=model,
        max_tokens=max_tokens,
        system=system,
        messages=[{"role": "user", "content": user_message}],
    )
    return response.content[0].text
