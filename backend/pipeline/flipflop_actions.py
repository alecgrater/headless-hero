"""Policy helpers for human-only flip-flop micro-actions."""

from __future__ import annotations

from dataclasses import dataclass
import re
from typing import Literal

FlipflopAction = Literal[
    "blink",
    "speaking_mouth",
    "eye_glance",
    "eyebrow_raise",
    "head_nod",
    "explaining_hand_raise",
    "thinking_pose",
    "pointing_gesture",
    "counting_fingers",
    "small_shrug",
]

FLIPFLOP_ACTIONS: tuple[FlipflopAction, ...] = (
    "blink",
    "speaking_mouth",
    "eye_glance",
    "eyebrow_raise",
    "head_nod",
    "explaining_hand_raise",
    "thinking_pose",
    "pointing_gesture",
    "counting_fingers",
    "small_shrug",
)

_ACTION_SET = set(FLIPFLOP_ACTIONS)

PRODUCTION_FLIPFLOP_ACTIONS: tuple[FlipflopAction, ...] = (
    "blink",
    "speaking_mouth",
    "eye_glance",
    "eyebrow_raise",
)

_PRODUCTION_ACTION_SET = set(PRODUCTION_FLIPFLOP_ACTIONS)


@dataclass(frozen=True)
class FlipflopActionDefinition:
    label: str
    use_when: str
    state_a: str
    state_b: str


FLIPFLOP_ACTION_DEFINITIONS: dict[FlipflopAction, FlipflopActionDefinition] = {
    "blink": FlipflopActionDefinition(
        label="Blink",
        use_when="A close or medium human/character face can blink naturally.",
        state_a="eyes open, neutral natural face",
        state_b="eyes closed in a quick blink, same face and head position",
    ),
    "speaking_mouth": FlipflopActionDefinition(
        label="Speaking mouth",
        use_when="The character is talking, explaining, narrating, or responding.",
        state_a="mouth closed or lightly resting",
        state_b="mouth slightly open as if speaking one syllable",
    ),
    "eye_glance": FlipflopActionDefinition(
        label="Eye glance",
        use_when="The character notices, checks, or reacts to something nearby.",
        state_a="eyes looking forward",
        state_b="eyes glance slightly to the side or down, head unchanged",
    ),
    "eyebrow_raise": FlipflopActionDefinition(
        label="Eyebrow raise",
        use_when="The character is curious, skeptical, surprised, or emphasizing a point.",
        state_a="neutral eyebrows",
        state_b="one or both eyebrows slightly raised in curiosity or emphasis",
    ),
    "head_nod": FlipflopActionDefinition(
        label="Head nod",
        use_when="The character agrees, acknowledges, confirms, or lands a point.",
        state_a="head level and facing forward",
        state_b="chin slightly dipped in a small nod",
    ),
    "explaining_hand_raise": FlipflopActionDefinition(
        label="Explaining hand raise",
        use_when="The character teaches, explains, emphasizes, pleads, or presents.",
        state_a="hand relaxed near body",
        state_b="one hand raised near chest as if explaining",
    ),
    "thinking_pose": FlipflopActionDefinition(
        label="Thinking pose",
        use_when="The character pauses, considers, realizes, or analyzes.",
        state_a="hand away from chin",
        state_b="hand near chin in a thinking pose",
    ),
    "pointing_gesture": FlipflopActionDefinition(
        label="Pointing gesture",
        use_when="The prompt includes a board, screen, object, map, chart, or implied off-frame target.",
        state_a="hand relaxed or half-raised",
        state_b="one finger pointing toward an implied subject or screen area",
    ),
    "counting_fingers": FlipflopActionDefinition(
        label="Counting fingers",
        use_when="The narration counts, lists, or compares a small number of points.",
        state_a="one finger raised",
        state_b="two fingers raised on the same hand",
    ),
    "small_shrug": FlipflopActionDefinition(
        label="Small shrug",
        use_when="The character is uncertain, resigned, confused, or mildly helpless.",
        state_a="arms relaxed",
        state_b="shoulders and palms slightly raised in a small shrug",
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


def normalize_flipflop_action(value: object) -> FlipflopAction | Literal[""]:
    return value if isinstance(value, str) and value in _ACTION_SET else ""  # type: ignore[return-value]


def normalize_production_flipflop_action(value: object) -> FlipflopAction | Literal[""]:
    return value if isinstance(value, str) and value in _PRODUCTION_ACTION_SET else ""  # type: ignore[return-value]


def _contains_human_subject_marker(text: str) -> bool:
    return any(
        re.search(rf"\b{re.escape(marker)}\b", text.casefold())
        for marker in _HUMAN_SUBJECT_MARKERS
    )


def has_human_flipflop_subject(narration: str, visual_prompt: str) -> bool:
    prompt = visual_prompt.strip()
    if prompt:
        return _contains_human_subject_marker(prompt)
    return _contains_human_subject_marker(narration)


def flipflop_action_prompt_guidance() -> str:
    action_lines = [
        f"- `{action}`: {definition.use_when}"
        for action, definition in FLIPFLOP_ACTION_DEFINITIONS.items()
        if action in _PRODUCTION_ACTION_SET
    ]
    return "\n".join(
        [
            "When `visual_mode` is `flipflop`, also emit `flipflop_action` using exactly one allowed value.",
            "Production flipflop_action values: blink, speaking_mouth, eye_glance, eyebrow_raise.",
            "Allowed production flipflop_action definitions:",
            *action_lines,
            "Do not choose pose-changing or body-action values for production flipflop.",
            "Avoid head nods, hand raises, thinking poses, pointing, counting fingers, shrugs, walking, leaning, or body repositioning.",
            "Only choose flipflop for a human, human-like, or clearly personified character scene.",
            "If no allowed human micro-action naturally fits, choose another visual_mode.",
        ]
    )


def build_flipflop_state_prompt(
    *,
    visual_prompt: str,
    narration: str,
    action: str,
    state: Literal["a", "b"],
) -> str:
    if state not in {"a", "b"}:
        raise ValueError("flipflop state must be 'a' or 'b'")
    normalized = normalize_flipflop_action(action)
    if not normalized:
        normalized = "speaking_mouth"
    definition = FLIPFLOP_ACTION_DEFINITIONS[normalized]  # type: ignore[index]
    state_text = definition.state_a if state == "a" else definition.state_b
    base_prompt = visual_prompt.strip() or narration.strip()
    state_label = "State A" if state == "a" else "State B"
    return (
        f"{state_label} for flip-flop action `{normalized}` ({definition.label}). "
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
        "Do not introduce a new emotion, do not change the mouth shape unless the action is speaking_mouth, "
        "do not change the eyes unless the action is blink or eye_glance, do not change the eyebrows unless "
        "the action is eyebrow_raise, and do not change hands or arms unless the action requires it. "
        f"Character description: {base_prompt}"
    )
