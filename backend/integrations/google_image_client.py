"""Thin wrapper around the Google GenAI SDK for image generation via Gemini."""

import os
import tempfile

from google import genai
from google.genai import types


def _get_client() -> genai.Client:
    key = os.environ.get("GOOGLE_AI_KEY")
    if not key:
        raise RuntimeError(
            "GOOGLE_AI_KEY is not set. "
            "Export it in your shell or add it to the app settings."
        )
    return genai.Client(api_key=key)


def _closest_aspect_ratio(width: int, height: int) -> str:
    """Map width/height to the closest supported aspect ratio string."""
    ratio = width / height
    options = [
        (1 / 1, "1:1"),
        (3 / 4, "3:4"),
        (4 / 3, "4:3"),
        (9 / 16, "9:16"),
        (16 / 9, "16:9"),
    ]
    best = min(options, key=lambda x: abs(x[0] - ratio))
    return best[1]


def generate_image(prompt: str, width: int = 1344, height: int = 768) -> str:
    """Generate an image via Gemini and return the path to a temp file."""
    client = _get_client()
    aspect = _closest_aspect_ratio(width, height)

    response = client.models.generate_content(
        model="gemini-2.5-flash-image",
        contents=[prompt],
        config=types.GenerateContentConfig(
            response_modalities=["IMAGE"],
            image_config=types.ImageConfig(
                aspect_ratio=aspect,
            ),
        ),
    )

    # Extract image bytes from response (matching official SDK pattern)
    for part in response.parts:
        if part.inline_data is not None:
            # Write to a temp file and return its path
            fd, tmp_path = tempfile.mkstemp(suffix=".png")
            with os.fdopen(fd, "wb") as f:
                f.write(part.inline_data.data)
            return tmp_path

    raise RuntimeError("Gemini response did not contain an image")
