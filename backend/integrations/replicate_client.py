"""Thin wrapper around the Replicate API for image generation via Flux."""

import os
import tempfile

import replicate


def generate_image(prompt: str, width: int = 1344, height: int = 768, seed: int | None = None) -> str:
    """Generate an image via Replicate Flux and return the path to a temp file."""
    token = os.environ.get("REPLICATE_API_TOKEN")
    if not token:
        raise RuntimeError(
            "REPLICATE_API_TOKEN is not set. "
            "Export it in your shell or add it to the app settings."
        )

    prompt_upsampling = os.environ.get(
        "REPLICATE_PROMPT_UPSAMPLING", "true"
    ).lower() in ("true", "1", "yes")

    safety_tolerance = int(os.environ.get("REPLICATE_SAFETY_TOLERANCE", "2"))

    output_format = os.environ.get("REPLICATE_OUTPUT_FORMAT", "png")

    model = os.environ.get("REPLICATE_MODEL", "black-forest-labs/flux-1.1-pro")

    input_dict = {
            "prompt": prompt,
            "width": width,
            "height": height,
            "prompt_upsampling": prompt_upsampling,
            "safety_tolerance": safety_tolerance,
            "output_format": output_format,
        }
    if seed is not None:
        input_dict["seed"] = seed

    output = replicate.run(
        model,
        input=input_dict,
    )

    # output is a FileOutput — use .read() to get bytes per Replicate SDK docs
    fd, tmp_path = tempfile.mkstemp(suffix=".png")
    with os.fdopen(fd, "wb") as f:
        f.write(output.read())
    os.chmod(tmp_path, 0o644)
    return tmp_path
