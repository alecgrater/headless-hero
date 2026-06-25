"""Lightweight helper to record API usage from any integration client."""

import atexit
import logging
import os
import queue
import threading
import time

from sqlmodel import Session

from database import engine
from models.api_usage import ApiUsage

logger = logging.getLogger(__name__)

_QUEUE_MAX = 10_000
_BATCH_SIZE = 50
_FLUSH_INTERVAL_S = 1.0
_SHUTDOWN_TIMEOUT_S = 5.0

_usage_queue: "queue.Queue[ApiUsage | None]" = queue.Queue(maxsize=_QUEUE_MAX)
_writer_thread: threading.Thread | None = None
_writer_lock = threading.Lock()
_disabled = False


def _flush_batch(batch: list[ApiUsage]) -> None:
    if not batch:
        return
    try:
        with Session(engine) as session:
            for row in batch:
                session.add(row)
            session.commit()
        return
    except Exception:
        logger.warning(
            "Batch commit failed for %d usage rows; retrying per-row",
            len(batch),
            exc_info=True,
        )
    # Fallback: insert each row independently so a single bad row doesn't
    # take down the rest of the batch.
    for row in batch:
        try:
            with Session(engine) as session:
                session.add(row)
                session.commit()
        except Exception:
            logger.warning("Dropping unwritable usage row service=%s operation=%s",
                           row.service, row.operation, exc_info=True)


def _writer_loop() -> None:
    """Drain the queue in batches until a None sentinel is received."""
    batch: list[ApiUsage] = []
    last_flush = time.monotonic()
    while True:
        # Block indefinitely when nothing is in flight; otherwise cap the
        # wait so we flush a partial batch within _FLUSH_INTERVAL_S.
        if batch:
            timeout: float | None = max(0.0, _FLUSH_INTERVAL_S - (time.monotonic() - last_flush))
        else:
            timeout = None
        try:
            item = _usage_queue.get(timeout=timeout)
        except queue.Empty:
            _flush_batch(batch)
            batch = []
            last_flush = time.monotonic()
            continue
        if item is None:
            # Shutdown sentinel: flush and exit.
            _flush_batch(batch)
            return
        batch.append(item)
        if len(batch) >= _BATCH_SIZE:
            _flush_batch(batch)
            batch = []
            last_flush = time.monotonic()


def _ensure_writer_started() -> None:
    """Lazy-start the singleton writer thread.

    HEADLESS_HERO_DISABLE_USAGE_THREAD is consulted on every call so tests
    that flip it via monkeypatch take effect without re-importing.
    """
    global _writer_thread, _disabled
    if os.environ.get("HEADLESS_HERO_DISABLE_USAGE_THREAD"):
        _disabled = True
        return
    _disabled = False
    if _writer_thread is not None and _writer_thread.is_alive():
        return
    with _writer_lock:
        if _writer_thread is not None and _writer_thread.is_alive():
            return
        _writer_thread = threading.Thread(
            target=_writer_loop,
            name="usage-writer",
            daemon=True,
        )
        _writer_thread.start()
        atexit.register(_shutdown_writer)


def _shutdown_writer() -> None:
    """Send sentinel and wait briefly so in-flight rows persist on exit."""
    if _writer_thread is None or not _writer_thread.is_alive():
        return
    # If the queue is full, drop a couple of pending records to make room
    # for the sentinel — losing a few records is preferable to silently
    # abandoning the entire backlog when the daemon is killed.
    for _ in range(3):
        try:
            _usage_queue.put_nowait(None)
            break
        except queue.Full:
            try:
                _usage_queue.get_nowait()
            except queue.Empty:
                # Writer drained between attempts — retry the put on the
                # next loop iteration so the sentinel still goes through.
                continue
    else:
        logger.warning("Could not enqueue usage-writer shutdown sentinel; rows may be lost")
        return
    _writer_thread.join(timeout=_SHUTDOWN_TIMEOUT_S)
    if _writer_thread.is_alive():
        logger.warning("usage-writer did not exit within %.1fs; pending rows may be lost",
                       _SHUTDOWN_TIMEOUT_S)


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
    """Enqueue an API usage event for batched background persistence."""
    _ensure_writer_started()
    if _disabled:
        return
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
    try:
        _usage_queue.put_nowait(row)
    except queue.Full:
        logger.warning(
            "Usage queue full (max=%d); dropping record service=%s operation=%s",
            _QUEUE_MAX, service, operation,
        )


# --- Pricing constants (USD per token) ---
_MODEL_PRICING: dict[str, dict[str, float]] = {
    "claude-opus-4-7": {
        "input": 5.0 / 1_000_000,
        "output": 25.0 / 1_000_000,
        "cache_read": 0.5 / 1_000_000,
    },
    "claude-sonnet-4-6": {
        "input": 3.0 / 1_000_000,
        "output": 15.0 / 1_000_000,
        "cache_read": 0.3 / 1_000_000,
    },
    "claude-haiku-4-5-20251001": {
        "input": 1.0 / 1_000_000,
        "output": 5.0 / 1_000_000,
        "cache_read": 0.1 / 1_000_000,
    },
    "gpt-5.5": {
        # NOTE: Provisional pricing — mirrors gpt-5.2 until OpenAI's published
        # gpt-5.5 rate card is confirmed. Update with real per-token rates.
        "input": 1.75 / 1_000_000,
        "output": 14.0 / 1_000_000,
        "cache_read": 0.175 / 1_000_000,
    },
    "gpt-5.2": {
        "input": 1.75 / 1_000_000,
        "output": 14.0 / 1_000_000,
        "cache_read": 0.175 / 1_000_000,
    },
    "gpt-5-mini": {
        "input": 0.25 / 1_000_000,
        "output": 2.0 / 1_000_000,
        "cache_read": 0.025 / 1_000_000,
    },
    "gpt-5-nano": {
        "input": 0.05 / 1_000_000,
        "output": 0.4 / 1_000_000,
        "cache_read": 0.005 / 1_000_000,
    },
}

_DEFAULT_ANTHROPIC_PRICING = {
    "input": 3.0 / 1_000_000,
    "output": 15.0 / 1_000_000,
    "cache_read": 0.3 / 1_000_000,
}

_DEFAULT_OPENAI_PRICING = _MODEL_PRICING["gpt-5.2"]

_ZERO_PRICING = {
    "input": 0.0,
    "output": 0.0,
    "cache_read": 0.0,
}


def get_model_pricing(model: str) -> dict[str, float]:
    """Return per-token pricing dict for a model.

    Local models (Ollama/Qwen variants) are free — matched by prefix so any
    qwen/llama/etc. tag returns zero cost rather than phantom hosted pricing.
    """
    if model in _MODEL_PRICING:
        return _MODEL_PRICING[model]
    name = model.lower()
    if name.startswith(("qwen", "llama", "mistral", "gemma", "phi", "deepseek")):
        return _ZERO_PRICING
    if name.startswith(("gpt-", "o1", "o3", "o4")):
        return _DEFAULT_OPENAI_PRICING
    return _DEFAULT_ANTHROPIC_PRICING


ANTHROPIC_INPUT_PER_TOKEN = _DEFAULT_ANTHROPIC_PRICING["input"]
ANTHROPIC_OUTPUT_PER_TOKEN = _DEFAULT_ANTHROPIC_PRICING["output"]

LOCAL_LLM_SAVINGS_PRICING = _MODEL_PRICING["gpt-5-mini"]


def estimate_local_llm_savings(input_tokens: int, output_tokens: int) -> float:
    """Estimate avoided hosted LLM cost using GPT-5 mini as the comparison model."""
    return (
        max(input_tokens, 0) * LOCAL_LLM_SAVINGS_PRICING["input"]
        + max(output_tokens, 0) * LOCAL_LLM_SAVINGS_PRICING["output"]
    )

# Google Gemini 2.5 Flash image generation — per image
GOOGLE_IMAGE_PER_CALL = 0.039  # $0.0390/image (Gemini 2.5 Flash image gen)

# Runway Gen-4 Turbo video generation — 5 credits/sec, $0.01/credit.
RUNWAY_GEN4_TURBO_PER_SECOND = 0.05

# Fal Wan 2.2 A14B Turbo image-to-video — pricing is per generated video.
FAL_WAN_22_TURBO_PER_VIDEO_BY_RESOLUTION = {
    "480p": 0.05,
    "580p": 0.075,
    "720p": 0.10,
}

# Fal Wan 2.2 A14B (non-turbo) image-to-video — higher quality, supports
# variable clip length via num_frames. Rough per-video estimate (~2x turbo);
# verify against current fal pricing if exact accounting matters.
FAL_WAN_22_PER_VIDEO_BY_RESOLUTION = {
    "480p": 0.10,
    "580p": 0.15,
    "720p": 0.20,
}

# ElevenLabs — per character (Creator plan ~$22/mo for ~100k chars)
ELEVENLABS_PER_CHAR = 0.00022  # rough estimate
