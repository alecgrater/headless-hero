"""Format registry — central entry point for format-aware orchestration."""

from __future__ import annotations

import logging

from .base import TitleCardStrategy, VideoFormat, VisualBeatRules

logger = logging.getLogger(__name__)

_REGISTRY: dict[str, VideoFormat] = {}

DEFAULT_FORMAT_ID = "youtube-listicle"


def _register(fmt: VideoFormat) -> VideoFormat:
    if fmt.id in _REGISTRY:
        raise RuntimeError(f"Format {fmt.id!r} already registered")
    _REGISTRY[fmt.id] = fmt
    return fmt


def get_format(format_id: str) -> VideoFormat:
    """Return the format. Raises KeyError if unknown — use resolve_format() for read paths."""
    if format_id not in _REGISTRY:
        raise KeyError(f"Unknown format_id: {format_id!r}. Known: {sorted(_REGISTRY)}")
    return _REGISTRY[format_id]


def list_formats() -> list[VideoFormat]:
    """Return all registered formats in registration order."""
    return list(_REGISTRY.values())


def resolve_format(format_id: str | None) -> VideoFormat:
    """Defensive read-side resolver. Falls back to youtube-listicle for missing/unknown.

    Logs a warning on fallback. Never raises.
    """
    if not format_id:
        return _REGISTRY[DEFAULT_FORMAT_ID]
    if format_id not in _REGISTRY:
        logger.warning(
            "resolve_format: unknown format_id %r — falling back to %s",
            format_id, DEFAULT_FORMAT_ID,
        )
        return _REGISTRY[DEFAULT_FORMAT_ID]
    return _REGISTRY[format_id]


# Register formats. Order matters — youtube-listicle must register first so it
# is the canonical default during list_formats() iteration.
def _bootstrap() -> None:
    from . import youtube_listicle  # noqa: F401 — side effect: registers
    # life-as-a registration lands in Task 5


_bootstrap()


__all__ = [
    "VideoFormat",
    "VisualBeatRules",
    "TitleCardStrategy",
    "get_format",
    "list_formats",
    "resolve_format",
    "DEFAULT_FORMAT_ID",
]
