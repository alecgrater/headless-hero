"""Thin wrapper around the Replicate API for image generation via Flux."""

import logging
import os
import tempfile
import threading
import time

import replicate
from replicate.exceptions import ReplicateError

from config import IMAGE_HEIGHT, IMAGE_WIDTH
from integrations.usage_tracker import record_usage, REPLICATE_FLUX_PER_IMAGE, REPLICATE_KONTEXT_PER_IMAGE

logger = logging.getLogger(__name__)

# Module-level rate limiter: tracks last API call time
_last_call_lock = threading.Lock()
_last_call_time: float = 0.0

_MAX_RETRIES = 3
_RETRY_BASE_SECONDS = 2.0


def _enforce_rate_limit() -> None:
    """Block until the per-call rate limit has elapsed."""
    rate_limit_ms = int(os.environ.get("IMAGE_RATE_LIMIT_MS", "10000"))
    if rate_limit_ms > 0:
        global _last_call_time
        with _last_call_lock:
            now = time.monotonic()
            elapsed_ms = (now - _last_call_time) * 1000
            if elapsed_ms < rate_limit_ms:
                time.sleep((rate_limit_ms - elapsed_ms) / 1000)
            _last_call_time = time.monotonic()


def _require_token() -> None:
    """Raise if REPLICATE_API_TOKEN is not set."""
    if not os.environ.get("REPLICATE_API_TOKEN"):
        raise RuntimeError(
            "REPLICATE_API_TOKEN is not set. "
            "Export it in your shell or add it to the app settings."
        )


def _run_with_retry(model: str, input_dict: dict) -> object:
    """Call replicate.run with automatic retry on 429 rate-limit errors."""
    for attempt in range(_MAX_RETRIES):
        try:
            return replicate.run(model, input=input_dict)
        except ReplicateError as exc:
            if exc.status == 429 and attempt < _MAX_RETRIES - 1:
                wait = _RETRY_BASE_SECONDS * (2 ** attempt)
                logger.warning(
                    "Replicate 429 rate limit hit, retrying in %.1fs (attempt %d/%d)",
                    wait, attempt + 1, _MAX_RETRIES,
                )
                time.sleep(wait)
                _enforce_rate_limit()
                continue
            raise


def generate_image(
    prompt: str,
    width: int = IMAGE_WIDTH,
    height: int = IMAGE_HEIGHT,
    seed: int | None = None,
    reference_image_path: str | None = None,
    script_id: str | None = None,
) -> str:
    """Generate an image via Replicate Flux and return the path to a temp file.

    If reference_image_path is provided, uses FLUX Kontext Pro for img2img
    frame chaining (previous frame as visual reference).
    """
    if reference_image_path:
        return generate_image_from_reference(
            prompt=prompt,
            reference_image_path=reference_image_path,
            seed=seed,
            script_id=script_id,
        )

    _require_token()
    _enforce_rate_limit()

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

    try:
        output = _run_with_retry(model, input_dict)
    except Exception:
        logger.error("Replicate image generation API call failed", exc_info=True)
        raise

    # output is a FileOutput — use .read() to get bytes per Replicate SDK docs
    fd, tmp_path = tempfile.mkstemp(suffix=".png")
    with os.fdopen(fd, "wb") as f:
        f.write(output.read())
    os.chmod(tmp_path, 0o644)
    record_usage(
        service="replicate",
        operation="image_gen",
        model=model,
        images=1,
        cost_estimate=REPLICATE_FLUX_PER_IMAGE,
        script_id=script_id,
    )
    return tmp_path


def generate_image_from_reference(
    prompt: str,
    reference_image_path: str,
    seed: int | None = None,
    script_id: str | None = None,
) -> str:
    """Generate an image using a reference via FLUX Kontext Pro.

    Uses the reference image as input_image so Kontext can maintain visual
    consistency while applying the edit described in the prompt.
    """
    _require_token()
    _enforce_rate_limit()

    model = "black-forest-labs/flux-kontext-pro"
    output_format = os.environ.get("REPLICATE_OUTPUT_FORMAT", "png")

    input_dict: dict = {
        "prompt": prompt,
        "input_image": open(reference_image_path, "rb"),
        "aspect_ratio": "match_input_image",
        "output_format": output_format,
        "safety_tolerance": 2,  # max allowed with input images
        "prompt_upsampling": False,
    }
    if seed is not None:
        input_dict["seed"] = seed

    try:
        output = _run_with_retry(model, input_dict)
    except Exception:
        logger.error("Replicate Kontext API call failed", exc_info=True)
        raise
    finally:
        # Close the file handle we opened for input_image
        if hasattr(input_dict.get("input_image"), "close"):
            input_dict["input_image"].close()

    fd, tmp_path = tempfile.mkstemp(suffix=".png")
    with os.fdopen(fd, "wb") as f:
        f.write(output.read())
    os.chmod(tmp_path, 0o644)
    record_usage(
        service="replicate",
        operation="image_gen_kontext",
        model=model,
        images=1,
        cost_estimate=REPLICATE_KONTEXT_PER_IMAGE,
        script_id=script_id,
    )
    return tmp_path
