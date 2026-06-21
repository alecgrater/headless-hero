"""Renderer-owned context presets for canvas-revealing visual modes."""

from __future__ import annotations

import re
from typing import Literal

RendererContext = Literal[
    "outdoor",
    "indoor",
]

RENDERER_CONTEXTS: tuple[RendererContext, ...] = (
    "outdoor",
    "indoor",
)

_CONTEXT_SET = set(RENDERER_CONTEXTS)
_LEGACY_INDOOR_CONTEXTS = {"desk", "classroom", "office", "kitchen", "lab"}

_CONTEXT_KEYWORDS: tuple[tuple[RendererContext, tuple[str, ...]], ...] = (
    (
        "outdoor",
        (
            "outdoor", "outside", "grass", "sky", "park", "field", "street",
            "sidewalk", "city", "car", "bus",
        ),
    ),
    (
        "indoor",
        (
            "kitchen", "restaurant", "cooking", "chef", "fryer", "food service",
            "burger", "counter", "store", "cashier", "customer", "register",
            "retail", "bar", "cafe", "lab", "scientist", "experiment",
            "microscope", "clinic", "medical", "doctor", "nurse", "classroom",
            "school", "teacher", "student", "whiteboard", "lecture", "homework",
            "office", "meeting", "spreadsheet", "document", "email", "desk job",
            "cubicle", "laptop", "computer", "books", "paperwork", "study",
            "writing", "desk",
        ),
    ),
)


def normalize_renderer_context(value: object) -> RendererContext:
    if isinstance(value, str):
        if value in _CONTEXT_SET:
            return value  # type: ignore[return-value]
        if value in _LEGACY_INDOOR_CONTEXTS:
            return "indoor"
    return "outdoor"


def infer_renderer_context(*, narration: str, visual_prompt: str) -> RendererContext:
    text = f"{narration} {visual_prompt}".casefold()
    for context, keywords in _CONTEXT_KEYWORDS:
        if any(re.search(rf"\b{re.escape(keyword)}\b", text) for keyword in keywords):
            return context
    return "outdoor"
