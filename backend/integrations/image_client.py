"""Image generation provider router.

Reads IMAGE_PROVIDER from environment and delegates to the appropriate backend.
"""

import os


def generate_image(
    prompt: str,
    width: int = 1344,
    height: int = 768,
    seed: int | None = None,
    reference_image_path: str | None = None,
) -> str:
    """Generate an image using the configured provider.

    If reference_image_path is provided, the provider may use it as a visual
    reference for img2img generation (e.g. FLUX Kontext on Replicate).
    """
    provider = os.environ.get("IMAGE_PROVIDER", "google")

    if provider == "replicate":
        from integrations.replicate_client import generate_image as _gen
    else:
        from integrations.google_image_client import generate_image as _gen

    return _gen(prompt, width, height, seed=seed, reference_image_path=reference_image_path)
