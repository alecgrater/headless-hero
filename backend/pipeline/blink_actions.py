"""Policy helpers for human-only blink subjects.

Blink is no longer a selectable visual mode or a generated-cutout treatment. It
is applied as a renderer-owned full-frame overlay (see pipeline.full_frame_blink)
when a safe face anchor is detected. These helpers remain for legacy field
normalization, human-subject detection, and prompt/guidance copy.
"""

from __future__ import annotations

import re
from typing import Literal

BlinkAction = Literal["blink"]

BLINK_ACTIONS: tuple[BlinkAction, ...] = (
    "blink",
)

_ACTION_SET = set(BLINK_ACTIONS)

_HUMAN_SUBJECT_MARKERS = {
    "person",
    "people",
    "man",
    "woman",
    "human",
    "human-like",
    "humanoid",
    "character",
    "personified",
    "eli",
    "teacher",
    "student",
    "worker",
    "doctor",
    "cashier",
    "bartender",
    "waiter",
    "waitress",
    "clerk",
    "chef",
    "farmer",
    "soldier",
    "officer",
    "athlete",
    "coach",
    "driver",
    "pilot",
    "nurse",
    "judge",
    "lawyer",
    "customer",
    "guest",
    "host",
    "performer",
    "artist",
    "musician",
    "guard",
    "prisoner",
    "parent",
    "child",
    "boy",
    "girl",
    "teen",
    "elder",
    "employee",
    "manager",
    "scientist",
    "narrator",
    "protagonist",
    "portrait",
}


def normalize_blink_action(value: object) -> BlinkAction | Literal[""]:
    return value if isinstance(value, str) and value in _ACTION_SET else ""  # type: ignore[return-value]


def _contains_human_subject_marker(text: str) -> bool:
    return any(
        re.search(rf"\b{re.escape(marker)}\b", text.casefold())
        for marker in _HUMAN_SUBJECT_MARKERS
    )


def has_human_blink_subject(narration: str, visual_prompt: str) -> bool:
    prompt = visual_prompt.strip()
    if prompt:
        return _contains_human_subject_marker(prompt)
    return _contains_human_subject_marker(narration)


def blink_action_prompt_guidance() -> str:
    return "\n".join(
        [
            "Do not choose `visual_mode=\"blink\"`; blink is not a selectable visual mode.",
            "Blinking is applied automatically as a renderer-owned full-frame overlay when a "
            "safe face anchor is detected on a normal full-frame image. No blink_action is required.",
            "Always choose another visual_mode in script generation and visual analysis.",
        ]
    )

