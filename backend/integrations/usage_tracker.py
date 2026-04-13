"""Lightweight helper to record API usage from any integration client."""

import logging
import threading

from sqlmodel import Session

from database import engine
from models.api_usage import ApiUsage

logger = logging.getLogger(__name__)


def record_usage(
    *,
    service: str,
    operation: str = "",
    model: str = "",
    input_tokens: int = 0,
    output_tokens: int = 0,
    characters: int = 0,
    images: int = 0,
    cost_estimate: float = 0.0,
    metadata_json: str = "",
    script_id: str | None = None,
) -> None:
    """Record an API usage event in a background thread (fire-and-forget)."""
    def _write():
        try:
            row = ApiUsage(
                service=service,
                operation=operation,
                model=model,
                input_tokens=input_tokens,
                output_tokens=output_tokens,
                characters=characters,
                images=images,
                cost_estimate=cost_estimate,
                metadata_json=metadata_json,
                script_id=script_id,
            )
            with Session(engine) as session:
                session.add(row)
                session.commit()
        except Exception:
            logger.debug("Failed to record API usage", exc_info=True)

    threading.Thread(target=_write, daemon=True).start()


# --- Pricing constants (USD) ---
# Anthropic Claude Sonnet 4
ANTHROPIC_INPUT_PER_TOKEN = 3.0 / 1_000_000   # $3/MTok
ANTHROPIC_OUTPUT_PER_TOKEN = 15.0 / 1_000_000  # $15/MTok

# Google Gemini 2.5 Flash image generation — per image
GOOGLE_IMAGE_PER_CALL = 0.039  # $0.0390/image (Gemini 2.5 Flash image gen)

# Replicate Flux 1.1 Pro — per image (approximate)
REPLICATE_FLUX_PER_IMAGE = 0.04

# Replicate FLUX Kontext Pro — per image (approximate)
REPLICATE_KONTEXT_PER_IMAGE = 0.04

# ElevenLabs — per character (Creator plan ~$22/mo for ~100k chars)
ELEVENLABS_PER_CHAR = 0.00022  # rough estimate
