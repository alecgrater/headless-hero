"""Image generation provider router.

The only module allowed to name an image provider. Local Mode routes to
ComfyUI; otherwise calls go to Google Gemini. Every image entry point in the
pipeline goes through here so a mode switch can never leave one path on the
cloud.
"""

import logging
import os

from config import IMAGE_HEIGHT, IMAGE_WIDTH
from integrations.google_image_client import GoogleBatchImageRequest, GoogleBatchImageResult
from integrations.local_models import active_model, modality_source

logger = logging.getLogger(__name__)

CLOUD_PROVIDER = "google"


def _cloud_provider() -> str:
    """The cloud image provider. Google is the only supported backend."""
    provider = os.environ.get("IMAGE_PROVIDER", CLOUD_PROVIDER)
    if provider != CLOUD_PROVIDER:
        logger.warning("Unsupported image provider %s; falling back to %s", provider, CLOUD_PROVIDER)
    return CLOUD_PROVIDER


def resolved_provider() -> str:
    """"local" or "google" for the current mode.

    Local Mode wins over IMAGE_PROVIDER, which only selects among cloud
    backends.
    """
    return "local" if modality_source("image") == "local" else _cloud_provider()


def provider_fingerprint() -> str:
    """Stable identity of the active image engine, for cache markers.

    Cloud-generated and locally generated images are not interchangeable, and
    neither are images from two different local models, so this value is part
    of every image cache marker.
    """
    if resolved_provider() == "local":
        return f"local:{active_model('image').id}"
    return CLOUD_PROVIDER


def generate_image(
    prompt: str,
    width: int = IMAGE_WIDTH,
    height: int = IMAGE_HEIGHT,
    reference_image_path: str | None = None,
    style_reference_path: str | None = None,
    original_prompt: str | None = None,
    script_id: str | None = None,
) -> str:
    """Generate an image using the configured provider.

    reference_image_path and style_reference_path are passed to the provider as
    visual references for character and global-style consistency.
    original_prompt is the raw visual description before the style guide was
    prepended; the Google provider uses it to retry content-filter blocks.
    """
    provider = resolved_provider()
    logger.info(
        "Image generation via %s (width=%d, height=%d, has_reference=%s, has_style_ref=%s)",
        provider, width, height, reference_image_path is not None, style_reference_path is not None,
    )

    if provider == "local":
        from integrations.local_image_client import generate_image as _gen
    else:
        from integrations.google_image_client import generate_image as _gen

    return _gen(
        prompt,
        width=width,
        height=height,
        reference_image_path=reference_image_path,
        style_reference_path=style_reference_path,
        original_prompt=original_prompt,
        script_id=script_id,
    )


def transform_with_references(
    prompt: str,
    image_paths: list[str],
    width: int | None = None,
    height: int | None = None,
    script_id: str | None = None,
) -> str:
    """Transform an image using multiple reference images via the active provider.

    width and height are forwarded only when the caller supplies them, so the
    provider's own defaults still apply. Thumbnail callers deliberately omit
    them and let the provider derive the aspect ratio.
    """
    provider = resolved_provider()
    logger.info("Image transform via %s with %d reference images", provider, len(image_paths))

    if provider == "local":
        from integrations.local_image_client import transform_with_references as _transform
    else:
        from integrations.google_image_client import transform_with_references as _transform

    optional: dict[str, int] = {}
    if width is not None:
        optional["width"] = width
    if height is not None:
        optional["height"] = height

    return _transform(prompt, image_paths, script_id=script_id, **optional)


def generate_images_batch(
    *,
    requests: list[GoogleBatchImageRequest],
    script_id: str | None = None,
    poll_interval_seconds: float = 10.0,
    timeout_seconds: float = 24 * 60 * 60,
) -> list[GoogleBatchImageResult]:
    """Generate independent images through the active provider.

    Batching exists to amortise cloud round-trips and discounts, neither of
    which applies locally, so the local path runs the same requests
    sequentially and reports per-request errors rather than failing the batch.
    """
    if not requests:
        return []

    if resolved_provider() != "local":
        from integrations.google_image_client import generate_images_batch as _batch

        return _batch(
            requests=requests,
            script_id=script_id,
            poll_interval_seconds=poll_interval_seconds,
            timeout_seconds=timeout_seconds,
        )

    from integrations.local_image_client import generate_image as _gen

    logger.info("Running %d image requests sequentially on the local provider", len(requests))
    results: list[GoogleBatchImageResult] = []
    for request in requests:
        try:
            path = _gen(
                request.prompt,
                width=IMAGE_WIDTH,
                height=IMAGE_HEIGHT,
                reference_image_path=request.reference_image_path,
                style_reference_path=request.style_reference_path,
                original_prompt=None,
                script_id=script_id,
            )
            results.append(GoogleBatchImageResult(key=request.key, image_path=path))
        except Exception as exc:
            logger.error("Local image request %s failed: %s", request.key, exc, exc_info=True)
            results.append(GoogleBatchImageResult(key=request.key, error=str(exc)))
    return results
