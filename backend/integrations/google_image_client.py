"""Thin wrapper around the Google GenAI SDK for image generation via Gemini."""

import logging
import os
import tempfile

from google import genai
from google.genai import types

from config import IMAGE_HEIGHT, IMAGE_WIDTH
from integrations.google_image_scraper import scrape_google_image_sync
from integrations.usage_tracker import record_usage, GOOGLE_IMAGE_PER_CALL

logger = logging.getLogger(__name__)


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


def _call_gemini(
    client: genai.Client,
    contents: list,
    aspect: str,
) -> str | None:
    """Single Gemini image generation call. Returns temp file path or None if blocked."""
    try:
        response = client.models.generate_content(
            model="gemini-2.5-flash-image",
            contents=contents,
            config=types.GenerateContentConfig(
                response_modalities=["IMAGE"],
                image_config=types.ImageConfig(
                    aspect_ratio=aspect,
                ),
            ),
        )
    except Exception:
        logger.error("Gemini image generation API call failed", exc_info=True)
        raise

    if not response.parts:
        return None

    for part in response.parts:
        if part.inline_data is not None:
            fd, tmp_path = tempfile.mkstemp(suffix=".png")
            with os.fdopen(fd, "wb") as f:
                f.write(part.inline_data.data)
            os.chmod(tmp_path, 0o644)
            record_usage(
                service="google_ai",
                operation="image_gen",
                model="gemini-2.5-flash-image",
                images=1,
                cost_estimate=GOOGLE_IMAGE_PER_CALL,
            )
            logger.info("Gemini image generated successfully")
            return tmp_path

    return None


def generate_image(
    prompt: str,
    width: int = IMAGE_WIDTH,
    height: int = IMAGE_HEIGHT,
    seed: int | None = None,
    reference_image_path: str | None = None,
    original_prompt: str | None = None,
) -> str:
    """Generate an image via Gemini and return the path to a temp file.

    If reference_image_path is provided, the image is loaded as a multi-modal
    Part so Gemini can use it as a visual reference for character/style consistency.

    original_prompt is the raw visual description before style guide was prepended.
    Used for retry when Gemini blocks the full prompt.

    Falls back to Google Image scraper if both Gemini attempts fail.
    """
    client = _get_client()
    aspect = _closest_aspect_ratio(width, height)
    logger.info("Generating image via Gemini")

    # Build reference image part (reusable across retries)
    ref_part = None
    if reference_image_path:
        ref_path = reference_image_path
        mime = "image/png" if ref_path.lower().endswith(".png") else "image/jpeg"
        with open(ref_path, "rb") as f:
            ref_part = types.Part.from_bytes(data=f.read(), mime_type=mime)
        logger.info("Including reference image: %s", ref_path)

    # First attempt with full prompt
    contents: list = []
    if ref_part:
        contents.append(ref_part)
    contents.append(prompt)

    result = _call_gemini(client, contents, aspect)
    if result:
        return result

    # Retry with original visual prompt (no style guide preamble)
    retry_prompt = (
        f"Educational illustration, flat 2D cartoon style, absolutely no text or letters in the image: {original_prompt}"
        if original_prompt
        else f"Educational illustration, flat 2D cartoon style, absolutely no text or letters in the image: {prompt[:500]}"
    )
    logger.warning(
        "Gemini returned empty response (content filter?), retrying with simplified prompt: %s",
        retry_prompt[:200],
    )

    contents = []
    if ref_part:
        contents.append(ref_part)
    contents.append(retry_prompt)

    result = _call_gemini(client, contents, aspect)
    if result:
        return result

    # Last resort: Google Image scraper
    search_query = (original_prompt or prompt)[:120]
    logger.warning(
        "Gemini failed on both attempts, falling back to Google Image scraper: %s",
        search_query,
    )
    fd, tmp_path = tempfile.mkstemp(suffix=".png")
    os.close(fd)
    scraped = scrape_google_image_sync(
        query=search_query,
        output_path=tmp_path,
        width=width,
        height=height,
    )
    if scraped:
        logger.warning("Using scraped web image as fallback for: %s", search_query)
        return scraped

    # Clean up temp file if scraper didn't use it
    if os.path.exists(tmp_path):
        os.unlink(tmp_path)

    raise RuntimeError(
        f"Gemini returned empty response on both attempts and Google Image scraper "
        f"also failed. Prompt: {prompt[:200]}"
    )
