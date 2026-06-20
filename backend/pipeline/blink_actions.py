"""Policy helpers for human-only blink micro-actions."""

from __future__ import annotations

from dataclasses import dataclass
import re
from typing import Literal

BlinkAction = Literal["blink"]

BLINK_ACTIONS: tuple[BlinkAction, ...] = (
    "blink",
)

_ACTION_SET = set(BLINK_ACTIONS)

PRODUCTION_BLINK_ACTIONS: tuple[BlinkAction, ...] = ()

_PRODUCTION_ACTION_SET = set(PRODUCTION_BLINK_ACTIONS)


@dataclass(frozen=True)
class BlinkActionDefinition:
    label: str
    use_when: str
    state_a: str
    state_b: str


BLINK_ACTION_DEFINITIONS: dict[BlinkAction, BlinkActionDefinition] = {
    "blink": BlinkActionDefinition(
        label="Blink",
        use_when="A close or medium human/character face can blink naturally.",
        state_a="eyes open, neutral natural face",
        state_b="eyes closed in a quick blink, same face and head position",
    ),
}

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


def normalize_production_blink_action(value: object) -> BlinkAction | Literal[""]:
    return value if isinstance(value, str) and value in _PRODUCTION_ACTION_SET else ""  # type: ignore[return-value]


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
    action_lines = [
        f"- `{action}`: {definition.use_when}"
        for action, definition in BLINK_ACTION_DEFINITIONS.items()
    ]
    return "\n".join(
        [
            "Do not choose `visual_mode=\"blink\"` for production scripts yet.",
            "Production blink_action values: none. The current shared-sheet image path is not reliable enough for automatic production routing.",
            "Experimental Test Lab value: `blink`.",
            *action_lines,
            "Always choose another visual_mode in script generation and visual analysis.",
        ]
    )


def build_blink_state_prompt(
    *,
    visual_prompt: str,
    narration: str,
    action: str,
    state: Literal["a", "b"],
) -> str:
    if state not in {"a", "b"}:
        raise ValueError("blink state must be 'a' or 'b'")
    normalized = normalize_blink_action(action)
    if not normalized:
        normalized = "blink"
    definition = BLINK_ACTION_DEFINITIONS[normalized]  # type: ignore[index]
    state_text = definition.state_a if state == "a" else definition.state_b
    base_prompt = visual_prompt.strip() or narration.strip()
    state_label = "State A" if state == "a" else "State B"
    return (
        f"{state_label} for blink action `{normalized}` ({definition.label}). "
        f"Show {state_text}. "
        "Render ONE isolated human or character cutout only. Treat the description below as character-only "
        "information: ignore and do NOT render any setting, room, counter, register, table, desk, wall, "
        "background, equipment, vehicle, props, scenery, or other people. The character must stand alone. "
        "Lock identity across both states: same face, same skin tone, same hair, same eye shape, same outfit, "
        "same accessories, same body proportions, same camera angle, same crop, same scale, same art style, "
        "same lighting, same line work, and the same overall facial expression and mood. "
        "Keep the same pixel footprint and bounding box across both states. Do not zoom, crop tighter, crop wider, "
        "resize, rotate, translate, or shift the character on the canvas. Do not move the character higher, lower, "
        "left, or right; the silhouette must register over State A like a traced animation cel. "
        "The ONLY allowed change between State A and State B is the named micro-action. "
        "Copy State A exactly before making the micro-action change: hat, hair, ears, neck, collar, torso, "
        "shoulders, and arm edges must remain identical. For face-only actions, keep the head outline, jaw, "
        "chin, cheeks, nose, ears, neck, clothing, and body silhouette unchanged; only redraw the small "
        "internal facial mark required by the action. "
        "Do not introduce a new emotion, do not change the mouth shape, do not change the eyebrows, "
        "and do not change hands or arms. Only the eyelids may change for the blink. "
        f"Character description: {base_prompt}"
    )
