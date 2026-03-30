"""Thin wrapper around the Replicate API for image generation via Flux."""

import os
import tempfile
import threading
import time

import replicate

# Module-level rate limiter: tracks last API call time
_last_call_lock = threading.Lock()
_last_call_time: float = 0.0


def generate_image(prompt: str, width: int = 1344, height: int = 768, seed: int | None = None) -> str:
    """Generate an image via Replicate Flux and return the path to a temp file."""
    token = os.environ.get("REPLICATE_API_TOKEN")
    if not token:
        raise RuntimeError(
            "REPLICATE_API_TOKEN is not set. "
            "Export it in your shell or add it to the app settings."
        )

    # Enforce rate limit if enabled (IMAGE_RATE_LIMIT_MS > 0)
    rate_limit_ms = int(os.environ.get("IMAGE_RATE_LIMIT_MS", "10000"))
    if rate_limit_ms > 0:
        global _last_call_time
        with _last_call_lock:
            now = time.monotonic()
            elapsed_ms = (now - _last_call_time) * 1000
            if elapsed_ms < rate_limit_ms:
                time.sleep((rate_limit_ms - elapsed_ms) / 1000)
            _last_call_time = time.monotonic()

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
