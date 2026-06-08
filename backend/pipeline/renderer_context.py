"""Renderer-owned context presets for canvas-revealing visual modes."""

from __future__ import annotations

import re
from typing import Literal

RendererContext = Literal[
    "plain",
    "desk",
    "classroom",
    "office",
    "kitchen",
    "shop",
    "lab",
    "street",
]

RENDERER_CONTEXTS: tuple[RendererContext, ...] = (
    "plain",
    "desk",
    "classroom",
    "office",
    "kitchen",
    "shop",
    "lab",
    "street",
)

_CONTEXT_SET = set(RENDERER_CONTEXTS)

_CONTEXT_KEYWORDS: tuple[tuple[RendererContext, tuple[str, ...]], ...] = (
    ("kitchen", ("kitchen", "restaurant", "cooking", "chef", "fryer", "food service", "burger")),
    ("shop", ("store", "cashier", "customer", "register", "retail", "bar", "cafe", "line three")),
    ("lab", ("lab", "scientist", "experiment", "microscope", "clinic", "medical", "doctor", "nurse")),
    ("classroom", ("classroom", "school", "teacher", "student", "whiteboard", "lecture", "homework")),
    ("office", ("office", "meeting", "spreadsheet", "document", "email", "desk job", "cubicle")),
    ("street", ("street", "sidewalk", "city", "car", "bus", "outside")),
    ("desk", ("laptop", "computer", "books", "paperwork", "study", "writing", "desk")),
)


def normalize_renderer_context(value: object) -> RendererContext:
    return value if isinstance(value, str) and value in _CONTEXT_SET else "plain"  # type: ignore[return-value]


def infer_renderer_context(*, narration: str, visual_prompt: str) -> RendererContext:
    text = f"{narration} {visual_prompt}".casefold()
    for context, keywords in _CONTEXT_KEYWORDS:
        if any(re.search(rf"\b{re.escape(keyword)}\b", text) for keyword in keywords):
            return context
    return "plain"
