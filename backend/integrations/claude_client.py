"""Thin wrapper around the Anthropic Python SDK."""

import os

import anthropic

def get_client() -> anthropic.Anthropic:
    """Return an Anthropic client using ANTHROPIC_API_KEY from the environment."""
    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        raise RuntimeError(
            "ANTHROPIC_API_KEY is not set. "
            "Export it in your shell or add it to the app settings."
        )
    return anthropic.Anthropic(api_key=api_key)

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
