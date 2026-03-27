"""Thin wrapper around the fal-client SDK for image generation."""

from __future__ import annotations

import os

import fal_client


def _get_key() -> str:
    key = os.environ.get("FAL_KEY")
    if not key:
        raise RuntimeError(
            "FAL_KEY is not set. "
            "Export it in your shell or add it to the app settings."
        )
    return key


def generate_image(prompt: str, width: int = 1344, height: int = 768) -> str:
    """Generate an image via fal.ai Flux and return the CDN URL."""
    os.environ.setdefault("FAL_KEY", _get_key())
    result = fal_client.run(
        "fal-ai/flux/dev",
        arguments={
            "prompt": prompt,
            "image_size": {"width": width, "height": height},
        },
    )
    return result["images"][0]["url"]
