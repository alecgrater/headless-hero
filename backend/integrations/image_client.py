"""Image generation provider router.

Reads IMAGE_PROVIDER from environment and delegates to the appropriate backend.
"""

import os


def generate_image(prompt: str, width: int = 1344, height: int = 768, seed: int | None = None) -> str:
    """Generate an image using the configured provider."""
    provider = os.environ.get("IMAGE_PROVIDER", "google")

    if provider == "replicate":
        from integrations.replicate_client import generate_image as _gen
    else:
        from integrations.google_image_client import generate_image as _gen

    return _gen(prompt, width, height, seed=seed)
