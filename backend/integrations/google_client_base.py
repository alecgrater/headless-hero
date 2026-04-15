"""Shared Google GenAI client factory."""

import os

from google import genai


def get_google_client() -> genai.Client:
    """Return a configured Google GenAI client.

    Raises RuntimeError if GOOGLE_AI_KEY is not set.
    """
    key = os.environ.get("GOOGLE_AI_KEY")
    if not key:
        raise RuntimeError(
            "GOOGLE_AI_KEY is not set. "
            "Export it in your shell or add it to the app settings."
        )
    return genai.Client(api_key=key)
