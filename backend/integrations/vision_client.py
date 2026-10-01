"""Claude vision checks: send labelled images, get a JSON verdict back.

Thin wrapper like the other integrations. The blink check is its only caller
today; it judges the exact closed-eye frame the renderer will draw.
"""

import base64
import io
import json
import logging
import os
import re
import time
from typing import Any

from PIL import Image

from config import BALANCED_CLAUDE_MODEL
from integrations.usage_tracker import get_model_pricing, record_usage

logger = logging.getLogger(__name__)

VISION_CHECK_MODEL = BALANCED_CLAUDE_MODEL


def vision_check_available() -> bool:
    return bool((os.environ.get("ANTHROPIC_API_KEY") or "").strip())


def _image_block(image: Image.Image, max_side: int = 768) -> dict[str, Any]:
    image = image.convert("RGB")
    image.thumbnail((max_side, max_side))
    buffer = io.BytesIO()
    image.save(buffer, format="PNG")
    return {
        "type": "image",
        "source": {"type": "base64", "media_type": "image/png", "data": base64.b64encode(buffer.getvalue()).decode()},
    }


def judge_images(
    question: str,
    images: list[tuple[str, Image.Image]],
    *,
    operation: str,
    script_id: str | None = None,
    timeout: float = 60.0,
) -> dict[str, Any]:
    """Ask Claude a yes/no-style question about labelled images; return the parsed JSON object.

    Raises RuntimeError when no key is configured or no JSON comes back.
    """
    if not vision_check_available():
        raise RuntimeError("ANTHROPIC_API_KEY is not set")
    from integrations.llm_client import get_anthropic_client

    content: list[dict[str, Any]] = []
    for label, image in images:
        content.append({"type": "text", "text": label})
        content.append(_image_block(image))
    content.append({"type": "text", "text": question})

    t0 = time.monotonic()
    response = get_anthropic_client().messages.create(
        model=VISION_CHECK_MODEL,
        max_tokens=2000,
        messages=[{"role": "user", "content": content}],
        # A visual yes/no check, not a reasoning task: low effort keeps it cheap.
        extra_body={"output_config": {"effort": "low"}},
        timeout=timeout,
    )
    usage = response.usage
    pricing = get_model_pricing(VISION_CHECK_MODEL)
    record_usage(
        service="anthropic",
        operation=operation,
        model=VISION_CHECK_MODEL,
        input_tokens=usage.input_tokens,
        output_tokens=usage.output_tokens,
        cost_estimate=usage.input_tokens * pricing["input"] + usage.output_tokens * pricing["output"],
        script_id=script_id,
    )
    text = "".join(block.text for block in response.content if getattr(block, "type", None) == "text")
    match = re.search(r"\{.*\}", text, re.S)
    if not match:
        raise RuntimeError(f"vision check returned no JSON (stop_reason={getattr(response, 'stop_reason', None)!r})")
    logger.info("Vision check %s answered in %.1fs", operation, time.monotonic() - t0)
    return json.loads(match.group(0))
