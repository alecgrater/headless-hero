"""Thin wrapper around the Google GenAI SDK for image generation via Gemini."""

import logging
import os
import json
import tempfile
import time
from dataclasses import dataclass
from pathlib import Path

from google import genai
from google.genai import types

from config import DEFAULT_IMAGE_MODEL, IMAGE_HEIGHT, IMAGE_WIDTH
from integrations.google_client_base import get_google_client
from integrations.usage_tracker import record_usage, GOOGLE_IMAGE_PER_CALL

logger = logging.getLogger(__name__)

BATCH_IMAGE_PER_CALL = GOOGLE_IMAGE_PER_CALL / 2
BATCH_TERMINAL_STATES = {"JOB_STATE_SUCCEEDED", "JOB_STATE_FAILED", "JOB_STATE_CANCELLED", "JOB_STATE_EXPIRED"}


@dataclass(frozen=True)
class GoogleBatchImageRequest:
    key: str
    prompt: str
    aspect_ratio: str
    reference_image_path: str | None = None
    style_reference_path: str | None = None


@dataclass(frozen=True)
class GoogleBatchImageResult:
    key: str
    image_path: str | None = None
    error: str | None = None


def _part_from_path(path: str) -> types.Part:
    """Load an image file as a Gemini Part, inferring MIME type from extension."""
    ext = os.path.splitext(path.lower())[1]
    mime = {".png": "image/png", ".webp": "image/webp"}.get(ext, "image/jpeg")
    with open(path, "rb") as f:
        return types.Part.from_bytes(data=f.read(), mime_type=mime)


def _inline_part_from_path(path: str) -> dict:
    """Load an image file as a generateContent inline_data dict for Batch API."""
    ext = os.path.splitext(path.lower())[1]
    mime = {".png": "image/png", ".webp": "image/webp"}.get(ext, "image/jpeg")
    with open(path, "rb") as f:
        data = f.read()
    import base64

    return {
        "inline_data": {
            "mime_type": mime,
            "data": base64.b64encode(data).decode("ascii"),
        }
    }


def _get_attr_or_key(value: object, name: str):
    if isinstance(value, dict):
        return value.get(name)
    return getattr(value, name, None)


def _state_name(job: object) -> str:
    state = _get_attr_or_key(job, "state")
    if isinstance(state, str):
        return state
    return getattr(state, "name", str(state or ""))


def _extract_inline_responses(job: object) -> list:
    dest = _get_attr_or_key(job, "dest")
    responses = _get_attr_or_key(dest, "inlined_responses")
    if responses is None:
        responses = _get_attr_or_key(dest, "inlinedResponses")
    return list(responses or [])


def _extract_inline_image_data(response: object) -> bytes | None:
    parts = _get_attr_or_key(response, "parts") or []
    for part in parts:
        inline_data = _get_attr_or_key(part, "inline_data")
        if inline_data is None:
            inline_data = _get_attr_or_key(part, "inlineData")
        if inline_data is None:
            continue
        data = _get_attr_or_key(inline_data, "data")
        if isinstance(data, bytes):
            return data
        if isinstance(data, str):
            import base64

            return base64.b64decode(data)
    return None


def _batch_request_payload(request: GoogleBatchImageRequest) -> dict:
    parts: list[dict] = []
    if request.reference_image_path:
        parts.append(_inline_part_from_path(request.reference_image_path))
    if request.style_reference_path:
        parts.append(_inline_part_from_path(request.style_reference_path))
    parts.append({"text": request.prompt})
    return {
        "contents": [{"parts": parts, "role": "user"}],
        "config": {
            "response_modalities": ["IMAGE"],
            "image_config": {"aspect_ratio": request.aspect_ratio},
        },
    }


def generate_images_batch(
    *,
    client: genai.Client | None = None,
    requests: list[GoogleBatchImageRequest],
    script_id: str | None = None,
    poll_interval_seconds: float = 10.0,
    timeout_seconds: float = 24 * 60 * 60,
) -> list[GoogleBatchImageResult]:
    """Generate independent images through Google Batch API.

    The Batch API is asynchronous and discounted, so this helper submits inline
    generateContent requests, polls to a terminal state, and writes each returned
    image to a temp PNG path.
    """
    if not requests:
        return []
    client = client or get_google_client()
    display_name = f"headless-hero-images-{script_id or 'no-script'}-{int(time.time())}"
    inline_requests = [_batch_request_payload(request) for request in requests]
    logger.info(
        "Creating Google image batch job for %d request(s) (script=%s)",
        len(requests), script_id or "none",
    )
    batch_job = client.batches.create(
        model=DEFAULT_IMAGE_MODEL,
        src=inline_requests,
        config={"display_name": display_name},
    )
    job_name = getattr(batch_job, "name", None) or batch_job["name"]
    deadline = time.monotonic() + timeout_seconds

    while True:
        batch_job = client.batches.get(name=job_name)
        state = _state_name(batch_job)
        if state in BATCH_TERMINAL_STATES:
            break
        if time.monotonic() >= deadline:
            raise RuntimeError(f"Google image batch timed out before completion: {job_name}")
        time.sleep(poll_interval_seconds)

    state = _state_name(batch_job)
    if state != "JOB_STATE_SUCCEEDED":
        error = _get_attr_or_key(batch_job, "error")
        raise RuntimeError(f"Google image batch failed ({state}): {error or job_name}")

    inline_responses = _extract_inline_responses(batch_job)
    results: list[GoogleBatchImageResult] = []
    for request, inline_response in zip(requests, inline_responses):
        error = _get_attr_or_key(inline_response, "error")
        if error:
            results.append(GoogleBatchImageResult(key=request.key, error=str(error)))
            continue
        response = _get_attr_or_key(inline_response, "response")
        data = _extract_inline_image_data(response)
        if not data:
            results.append(GoogleBatchImageResult(key=request.key, error="Google Batch returned no image data"))
            continue
        fd, tmp_path = tempfile.mkstemp(suffix=".png")
        with os.fdopen(fd, "wb") as f:
            f.write(data)
        os.chmod(tmp_path, 0o644)
        results.append(GoogleBatchImageResult(key=request.key, image_path=tmp_path))

    if len(inline_responses) < len(requests):
        for request in requests[len(inline_responses):]:
            results.append(GoogleBatchImageResult(key=request.key, error="Google Batch returned no response"))

    successful_images = sum(1 for result in results if result.image_path)
    if successful_images:
        record_usage(
            service="google_ai",
            operation="image_gen_batch",
            model=DEFAULT_IMAGE_MODEL,
            images=successful_images,
            cost_estimate=BATCH_IMAGE_PER_CALL * successful_images,
            script_id=script_id,
        )
    logger.info(
        "Google image batch job complete: %d/%d image(s) generated",
        successful_images, len(requests),
    )
    return results


def _setting_enabled(value: str | None) -> bool:
    return (value or "").strip().lower() in {"1", "true", "yes", "on"}


def _write_source_metadata(image_path: str, metadata: dict[str, str | bool]) -> None:
    Path(image_path).with_suffix(".source.json").write_text(
        json.dumps(metadata, indent=2),
        encoding="utf-8",
    )


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
    script_id: str | None = None,
    max_retries: int = 3,
) -> str | None:
    """Single Gemini image generation call. Returns temp file path or None if blocked.

    Retries on transient server errors (503, 500, 429) with exponential backoff.
    """
    t0 = time.monotonic()
    last_exc: Exception | None = None
    for attempt in range(max_retries):
        try:
            response = client.models.generate_content(
                model=DEFAULT_IMAGE_MODEL,
                contents=contents,
                config=types.GenerateContentConfig(
                    response_modalities=["IMAGE"],
                    image_config=types.ImageConfig(
                        aspect_ratio=aspect,
                    ),
                ),
            )
            last_exc = None
            break
        except Exception as exc:
            last_exc = exc
            # Retry on transient server errors
            status = getattr(exc, "status_code", None)
            if status in (500, 503, 429) and attempt < max_retries - 1:
                wait = 2 ** attempt * 5  # 5s, 10s, 20s
                logger.warning(
                    "Gemini returned %s, retrying in %ds (attempt %d/%d)",
                    status, wait, attempt + 1, max_retries,
                )
                time.sleep(wait)
                continue
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
                model=DEFAULT_IMAGE_MODEL,
                images=1,
                cost_estimate=GOOGLE_IMAGE_PER_CALL,
                script_id=script_id,
            )
            logger.info("Gemini image generated successfully (%.1fs)", time.monotonic() - t0)
            return tmp_path

    return None


def generate_image(
    prompt: str,
    width: int = IMAGE_WIDTH,
    height: int = IMAGE_HEIGHT,
    _seed: int | None = None,
    reference_image_path: str | None = None,
    style_reference_path: str | None = None,
    original_prompt: str | None = None,
    script_id: str | None = None,
) -> str:
    """Generate an image via Gemini and return the path to a temp file.

    If reference_image_path is provided, the image is loaded as a multi-modal
    Part so Gemini can use it as a visual reference for character/style consistency.

    If style_reference_path is provided, it is attached as an additional Part
    after the character reference. Used to enforce a global art style across
    videos when the project has Eli disabled and style preset enabled.

    original_prompt is the raw visual description before style guide was prepended.
    Used for retry when Gemini blocks the full prompt.

    Falls back to Google Image scraper only when IMAGE_SCRAPER_FALLBACK_ENABLED
    is explicitly enabled.
    """
    client = get_google_client()
    aspect = _closest_aspect_ratio(width, height)
    logger.info(
        "Generating image via Gemini (aspect=%s, has_char_ref=%s, has_style_ref=%s)",
        aspect, reference_image_path is not None, style_reference_path is not None,
    )

    # Build reference image parts (reusable across retries)
    ref_parts: list = []
    if reference_image_path:
        ref_parts.append(_part_from_path(reference_image_path))
        logger.info("Including character reference image: %s", reference_image_path)
    if style_reference_path:
        ref_parts.append(_part_from_path(style_reference_path))
        logger.info("Including style reference image: %s", style_reference_path)

    # First attempt with full prompt
    contents: list = list(ref_parts)
    contents.append(prompt)

    try:
        result = _call_gemini(client, contents, aspect, script_id=script_id)
        if result:
            return result
    except Exception:
        logger.warning("First Gemini attempt raised, will retry with simplified prompt")

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

    contents = list(ref_parts)
    contents.append(retry_prompt)

    try:
        result = _call_gemini(client, contents, aspect, script_id=script_id)
        if result:
            return result
    except Exception:
        logger.warning("Second Gemini attempt also raised")

    scraper_fallback_enabled = _setting_enabled(os.environ.get("IMAGE_SCRAPER_FALLBACK_ENABLED"))
    if not scraper_fallback_enabled:
        raise RuntimeError(
            f"Gemini returned empty response on both attempts. Scraped web-image fallback "
            f"is disabled; enable IMAGE_SCRAPER_FALLBACK_ENABLED "
            f"if web scraping is acceptable for this project. Prompt: {prompt[:200]}"
        )

    # Last resort: Google Image scraper
    from integrations.google_image_scraper import scrape_google_image_sync

    search_query = (original_prompt or prompt)[:120]
    logger.warning(
        "Gemini failed on both attempts, using opt-in Google Image scraper fallback: %s",
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
        _write_source_metadata(scraped, {
            "source_type": "scraped_web_image",
            "provider": "google_images_scraper",
            "query": search_query,
            "reason": "Gemini image generation failed after retries",
            "license_note": "Scraped web image; verify usage rights before publishing.",
            "opt_in_setting": "IMAGE_SCRAPER_FALLBACK_ENABLED",
            "fallback": True,
        })
        return scraped

    # Clean up temp file if scraper didn't use it
    if os.path.exists(tmp_path):
        os.unlink(tmp_path)

    raise RuntimeError(
        f"Gemini returned empty response on both attempts and Google Image scraper "
        f"also failed. Prompt: {prompt[:200]}"
    )


def transform_with_references(
    prompt: str,
    image_paths: list[str],
    width: int = IMAGE_WIDTH,
    height: int = IMAGE_HEIGHT,
    script_id: str | None = None,
) -> str:
    """Transform an image using Gemini with multiple reference images.

    Sends all provided images as multi-modal Parts alongside the text prompt.
    Gemini returns a single transformed image.

    Args:
        prompt: Text instructions for how to transform the image.
        image_paths: List of image file paths to include (base image, references, etc.).
        width: Output width for aspect ratio calculation.
        height: Output height for aspect ratio calculation.
        script_id: Optional script ID for usage tracking.

    Returns:
        Path to the generated image temp file.

    Raises:
        RuntimeError: If Gemini fails to produce an image.
    """
    client = get_google_client()
    aspect = _closest_aspect_ratio(width, height)
    logger.info("Transforming image via Gemini with %d reference images", len(image_paths))

    # Build contents: all images first, then prompt text
    contents: list = []
    for img_path in image_paths:
        contents.append(_part_from_path(img_path))
    contents.append(prompt)

    result = _call_gemini(client, contents, aspect, script_id=script_id)
    if result:
        return result

    raise RuntimeError(
        f"Gemini returned empty response for image transformation. "
        f"Prompt: {prompt[:200]}"
    )
