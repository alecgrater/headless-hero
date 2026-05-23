"""Image generation provider router.

Reads IMAGE_PROVIDER from environment and delegates to the appropriate backend.
"""

import logging
import os

from config import IMAGE_HEIGHT, IMAGE_WIDTH

logger = logging.getLogger(__name__)


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

    If reference_image_path is provided, the provider may use it as a visual
    reference for img2img generation (e.g. FLUX Kontext on Replicate).

    If style_reference_path is provided, it is passed to the provider as an
    additional visual reference to enforce a global art style across generations.
    Only the Google provider currently supports this; other providers ignore it.

    original_prompt is the raw visual description before style guide was prepended,
    used by Google provider for retry on content filter blocks.
    """
    provider = os.environ.get("IMAGE_PROVIDER", "google")
    logger.info("Image generation via %s (width=%d, height=%d, has_reference=%s, has_style_ref=%s)",
                provider, width, height, reference_image_path is not None, style_reference_path is not None)

    if provider == "replicate":
        if style_reference_path is not None:
            logger.warning("Replicate provider does not support style_reference_path; ignoring")
        # style_reference_path intentionally not forwarded — Replicate has no img-style support
        from integrations.replicate_client import generate_image as _gen
        return _gen(prompt, width, height, reference_image_path=reference_image_path, script_id=script_id)
    else:
        from integrations.google_image_client import generate_image as _gen
        return _gen(prompt, width, height, reference_image_path=reference_image_path, style_reference_path=style_reference_path, original_prompt=original_prompt, script_id=script_id)
