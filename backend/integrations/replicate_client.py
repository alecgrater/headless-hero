"""Thin wrapper around the Replicate API for image generation via Flux."""

import os
import tempfile

import replicate


def generate_image(prompt: str, width: int = 1344, height: int = 768) -> str:
    """Generate an image via Replicate Flux and return the path to a temp file."""
    token = os.environ.get("REPLICATE_API_TOKEN")
    if not token:
        raise RuntimeError(
            "REPLICATE_API_TOKEN is not set. "
            "Export it in your shell or add it to the app settings."
        )

    output = replicate.run(
        "black-forest-labs/flux-1.1-pro",
        input={
            "prompt": prompt,
            "width": width,
            "height": height,
        },
    )

    # output is a FileOutput — use .read() to get bytes per Replicate SDK docs
    fd, tmp_path = tempfile.mkstemp(suffix=".png")
    with os.fdopen(fd, "wb") as f:
        f.write(output.read())
    os.chmod(tmp_path, 0o644)
    return tmp_path
