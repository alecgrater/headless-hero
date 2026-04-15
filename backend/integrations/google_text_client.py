"""Thin wrapper around the Google GenAI SDK for text generation via Gemini."""

import logging
import os
import time

from google import genai
from google.genai import types

logger = logging.getLogger(__name__)

DEFAULT_TEXT_MODEL = "gemini-3.1-pro-preview"


def _get_client() -> genai.Client:
    key = os.environ.get("GOOGLE_AI_KEY")
    if not key:
        raise RuntimeError(
            "GOOGLE_AI_KEY is not set. "
            "Export it in your shell or add it to the app settings."
        )
    return genai.Client(api_key=key)


def generate_text(
    system_prompt: str,
    user_message: str,
    model: str = DEFAULT_TEXT_MODEL,
    max_tokens: int = 4096,
) -> str:
    """Generate text via Gemini and return the response string.

    Args:
        system_prompt: System-level instructions for the model.
        user_message: The user message / prompt content.
        model: Gemini model identifier.
        max_tokens: Maximum output tokens.

    Returns:
        The generated text response.

    Raises:
        RuntimeError: If the API key is missing or the call returns no content.
    """
    client = _get_client()
    t0 = time.monotonic()
    logger.info("Generating text via Gemini (model=%s)", model)

    response = client.models.generate_content(
        model=model,
        contents=user_message,
        config=types.GenerateContentConfig(
            system_instruction=system_prompt,
            max_output_tokens=max_tokens,
        ),
    )

    if not response.text:
        raise RuntimeError(
            f"Gemini returned empty text response (model={model}). "
            f"Prompt may have been blocked by content filters."
        )

    elapsed = time.monotonic() - t0
    logger.info("Gemini text generated in %.1fs (%d chars)", elapsed, len(response.text))
    return response.text
