"""Image generation provider router.

The only module allowed to name an image provider. Local Mode routes to
ComfyUI; otherwise calls go to Google Gemini. Every image entry point in the
pipeline goes through here so a mode switch can never leave one path on the
cloud.
"""

import logging
import os

from config import IMAGE_HEIGHT, IMAGE_WIDTH
# Re-exported so pipeline code never has to import google_image_client directly.
from integrations.google_image_client import GoogleBatchImageRequest, GoogleBatchImageResult
from integrations.local_models import active_model, modality_source

__all__ = [
    "CUTOUT_SHEET",
    "GoogleBatchImageRequest",
    "GoogleBatchImageResult",
    "SCENE",
    "generate_image",
    "generate_images_batch",
    "provider_fingerprint",
    "resolved_provider",
    "transform_with_references",
]

logger = logging.getLogger(__name__)

CLOUD_PROVIDER = "google"

# What the generated image is for. Most images are shown as generated; a few are
# raw material for a post-processing pass that can only succeed if the model
# actually obeyed the prompt's negative instructions.
SCENE = "scene"
CUTOUT_SHEET = "cutout_sheet"

# Purposes that need strict negative-instruction compliance. A contact sheet is
# cropped and chroma-keyed into transparent cutouts, so "flat chroma background,
# no frames, no text" are load-bearing, not stylistic. FLUX.2 klein-4B ignores
# all three: a measured export produced framed magenta panels with narration
# text baked in, on a green field, and the keyer could only remove the gutters —
# 38 of 40 cutouts came out as opaque rectangles. Scene images from the same
# model are fine, because nothing downstream has to cut them apart.
STRICT_INSTRUCTION_PURPOSES = frozenset({CUTOUT_SHEET})


def _cloud_provider() -> str:
    """The cloud image provider. Google is the only supported backend."""
    provider = os.environ.get("IMAGE_PROVIDER", CLOUD_PROVIDER)
    if provider != CLOUD_PROVIDER:
        logger.warning("Unsupported image provider %s; falling back to %s", provider, CLOUD_PROVIDER)
    return CLOUD_PROVIDER


def _cutout_provider_preference() -> str:
    """`auto`, `local`, or `cloud` for cutout sheets generated in Local Mode.

    Deliberately a separate key from LOCAL_IMAGE_MODE with a different suffix:
    `auto` here means "escalate to the cloud when a key exists", not "follow the
    master switch". Same word, different question.
    """
    value = (os.environ.get("LOCAL_IMAGE_CUTOUT_PROVIDER") or "auto").strip().lower()
    if value not in {"auto", "local", "cloud"}:
        logger.warning("Unknown LOCAL_IMAGE_CUTOUT_PROVIDER %r; using auto", value)
        return "auto"
    return value


def _cloud_image_key_available() -> bool:
    return bool((os.environ.get("GOOGLE_AI_KEY") or "").strip())


def _escalates_to_cloud(purpose: str) -> bool:
    """True when a Local Mode image should be generated on the cloud anyway.

    A handful of cutout sheets per video is ~$0.04 each — cheap next to the
    scene images that make Local Mode worth using — so `auto` buys back the one
    thing the local model cannot do. `local` keeps a fully offline install
    offline, and an install with no cloud key stays local regardless.
    """
    if purpose not in STRICT_INSTRUCTION_PURPOSES:
        return False
    preference = _cutout_provider_preference()
    if preference == "local":
        return False
    if preference == "cloud":
        return True
    return _cloud_image_key_available()


def resolved_provider(purpose: str = SCENE) -> str:
    """"local" or "google" for the current mode and image purpose.

    Local Mode wins over IMAGE_PROVIDER, which only selects among cloud
    backends — except for purposes the local model demonstrably cannot serve.
    """
    if modality_source("image") != "local":
        return _cloud_provider()
    if _escalates_to_cloud(purpose):
        return _cloud_provider()
    return "local"


def provider_fingerprint(purpose: str = SCENE) -> str:
    """Stable identity of the active image engine, for cache markers.

    Cloud-generated and locally generated images are not interchangeable, and
    neither are images from two different local models, so this value is part
    of every image cache marker. Purpose matters too: flipping cutout
    escalation has to invalidate cutout caches without touching scene images.
    """
    if resolved_provider(purpose) == "local":
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
    purpose: str = SCENE,
) -> str:
    """Generate an image using the configured provider.

    reference_image_path and style_reference_path are passed to the provider as
    visual references for character and global-style consistency.
    original_prompt is the raw visual description before the style guide was
    prepended; the Google provider uses it to retry content-filter blocks.
    purpose selects the provider for images that are post-processed rather than
    shown as generated — see STRICT_INSTRUCTION_PURPOSES.
    """
    provider = resolved_provider(purpose)
    logger.info(
        "Image generation via %s (purpose=%s, width=%d, height=%d, has_reference=%s, has_style_ref=%s)",
        provider, purpose, width, height, reference_image_path is not None, style_reference_path is not None,
    )
    if purpose in STRICT_INSTRUCTION_PURPOSES and modality_source("image") == "local" and provider != "local":
        logger.info("Escalating %s to %s: the local image model cannot hold a keyable cutout sheet", purpose, provider)

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


def _dimensions_for_aspect_ratio(aspect_ratio: str) -> tuple[int, int]:
    """Pixel size for one of the batch request's aspect ratios.

    The cloud batch API takes a ratio string; ComfyUI takes pixels. Without
    this the local branch silently rendered every batch request at the default
    landscape size, so cloud and local produced different geometry for the same
    request. Long edge is held at IMAGE_WIDTH so the sizes match the defaults.
    """
    long_edge = max(IMAGE_WIDTH, IMAGE_HEIGHT)
    sizes = {
        # 16:9 is the project's landscape default, so it maps to the configured
        # size exactly rather than to a recomputed one — a default-sized request
        # must render at the same pixels it always did.
        "16:9": (IMAGE_WIDTH, IMAGE_HEIGHT),
        "9:16": (IMAGE_HEIGHT, IMAGE_WIDTH),
        "1:1": (long_edge, long_edge),
        "4:3": (long_edge, int(long_edge * 3 / 4)),
        "3:4": (int(long_edge * 3 / 4), long_edge),
    }
    dimensions = sizes.get(aspect_ratio)
    if dimensions is None:
        logger.warning(
            "Unknown aspect ratio %r in a local batch request; using %dx%d",
            aspect_ratio, IMAGE_WIDTH, IMAGE_HEIGHT,
        )
        return IMAGE_WIDTH, IMAGE_HEIGHT
    # ComfyUI's latent nodes want multiples of 8.
    return (dimensions[0] // 8) * 8, (dimensions[1] // 8) * 8


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
            width, height = _dimensions_for_aspect_ratio(request.aspect_ratio)
            path = _gen(
                request.prompt,
                width=width,
                height=height,
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
