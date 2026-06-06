# Flip-Flop Human Micro-Actions Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Require `flipflop` scenes to name one allowed human micro-action, then use that action to generate deterministic two-state cutout prompts.

**Architecture:** Add a small backend policy module for `flipflop_action` vocabulary, action definitions, validation, and prompt building. Thread the top-level field through `Scene`, script prompting, visual treatment analysis, image generation cache inputs, Test Lab settings, frontend types, and docs without adding a normal Timeline editor control.

**Tech Stack:** Python 3.12, Pydantic/SQLModel models, FastAPI pipeline code, React 19/TypeScript Test Lab UI, Vitest, pytest via `uv run --project backend pytest`.

---

## File Structure

- Create `backend/pipeline/flipflop_actions.py`: single source of truth for action enum values, reliability prompt text, human-subject heuristic, deterministic State A/B text, prompt builder, and downgrade helper.
- Modify `backend/models/script.py`: add `FlipflopAction` literal and `Scene.flipflop_action`; clear action when mode is not `flipflop`.
- Modify `backend/pipeline/visual_treatments.py`: validate explicit/inferred flip-flop scenes, assign actions for inferred scenes, and generate action-specific layer prompts.
- Modify `backend/prompts/script.py`: require `flipflop_action` in script JSON when `visual_mode="flipflop"` and include allowlist/reliability tiers.
- Modify `backend/pipeline/scriptwriter.py`: run a post-parse validator that downgrades invalid flip-flop scenes and records fallback events.
- Modify `backend/pipeline/image_gen.py`: include action-derived layer prompt text in the existing flip-flop cutout fingerprint path by relying on generated layer prompts.
- Modify `backend/pipeline/test_lab.py`: accept/pass `flipflop_action`, expose it in manifests, and build fallback layers from action definitions.
- Modify `frontend/src/types/script.ts` and `frontend/src/types/testLab.ts`: add `FlipflopAction` and optional `flipflop_action`.
- Modify `frontend/src/components/test-lab/TestLabControls.tsx`: add a compact action selector for flip-flop only; do not add Timeline controls.
- Modify docs: `AGENTS.md` and `frontend/src/components/settings/visual-modes/catalog.ts`.

## Task 1: Backend Action Policy

**Files:**
- Create: `backend/pipeline/flipflop_actions.py`
- Test: `backend/tests/pipeline/test_flipflop_actions.py`

- [ ] **Step 1: Write failing tests**

Create `backend/tests/pipeline/test_flipflop_actions.py`:

```python
from pipeline.flipflop_actions import (
    FLIPFLOP_ACTIONS,
    build_flipflop_state_prompt,
    flipflop_action_prompt_guidance,
    has_human_flipflop_subject,
    normalize_flipflop_action,
)


def test_normalize_flipflop_action_accepts_only_allowlist():
    assert normalize_flipflop_action("blink") == "blink"
    assert normalize_flipflop_action("Blink") == ""
    assert normalize_flipflop_action("walking") == ""
    assert normalize_flipflop_action(None) == ""


def test_flipflop_actions_are_stable_snake_case_values():
    assert FLIPFLOP_ACTIONS == (
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


def test_action_prompt_guidance_contains_reliability_tiers():
    guidance = flipflop_action_prompt_guidance()
    assert "Most reliable: blink, speaking_mouth, eye_glance, eyebrow_raise" in guidance
    assert "Reliable when supported: head_nod, explaining_hand_raise, thinking_pose" in guidance
    assert "Use only with clear prompt support: pointing_gesture, counting_fingers, small_shrug" in guidance


def test_build_flipflop_state_prompt_uses_action_specific_state_text():
    state_a = build_flipflop_state_prompt(
        visual_prompt="[REACTION] Cartoon teacher explaining at a podium.",
        narration="He calmly explains the rule.",
        action="speaking_mouth",
        state="a",
    )
    state_b = build_flipflop_state_prompt(
        visual_prompt="[REACTION] Cartoon teacher explaining at a podium.",
        narration="He calmly explains the rule.",
        action="speaking_mouth",
        state="b",
    )

    assert "mouth closed or lightly resting" in state_a
    assert "mouth slightly open as if speaking one syllable" in state_b
    assert "Only change the named micro-action" in state_b
    assert "same character, same outfit, same camera angle, same crop" in state_b


def test_has_human_flipflop_subject_checks_narration_and_prompt():
    assert has_human_flipflop_subject("He blinks once.", "[CLOSE-UP] Cartoon man at desk")
    assert has_human_flipflop_subject("The teacher points at the board.", "")
    assert not has_human_flipflop_subject("The clock ticks.", "[CLOSE-UP] Clock on wall")
    assert not has_human_flipflop_subject("The cracked wall shifts.", "[CLOSE-UP] Empty wall")
```

- [ ] **Step 2: Run tests to verify they fail**

Run:

```bash
uv run --project backend pytest backend/tests/pipeline/test_flipflop_actions.py -q
```

Expected: fail with `ModuleNotFoundError: No module named 'pipeline.flipflop_actions'`.

- [ ] **Step 3: Implement action policy module**

Create `backend/pipeline/flipflop_actions.py`:

```python
"""Policy helpers for human-only flip-flop micro-actions."""

from __future__ import annotations

from dataclasses import dataclass
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
    "character",
    "teacher",
    "student",
    "worker",
    "doctor",
    "guard",
    "prisoner",
    "parent",
    "child",
    "teen",
    "elder",
    "employee",
    "manager",
    "scientist",
    "narrator",
    "protagonist",
    "he ",
    "she ",
    "they ",
    "his ",
    "her ",
    "their ",
}


def normalize_flipflop_action(value: object) -> FlipflopAction | str:
    return value if isinstance(value, str) and value in _ACTION_SET else ""


def has_human_flipflop_subject(narration: str, visual_prompt: str) -> bool:
    text = f" {narration} {visual_prompt} ".casefold()
    return any(marker in text for marker in _HUMAN_SUBJECT_MARKERS)


def flipflop_action_prompt_guidance() -> str:
    action_lines = [
        f"- `{action}`: {definition.use_when}"
        for action, definition in FLIPFLOP_ACTION_DEFINITIONS.items()
    ]
    return "\n".join(
        [
            "When `visual_mode` is `flipflop`, also emit `flipflop_action` using exactly one allowed value.",
            "Allowed flipflop_action values:",
            *action_lines,
            "Reliability tiers:",
            "- Most reliable: blink, speaking_mouth, eye_glance, eyebrow_raise",
            "- Reliable when supported: head_nod, explaining_hand_raise, thinking_pose",
            "- Use only with clear prompt support: pointing_gesture, counting_fingers, small_shrug",
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
        "Use one isolated human or character cutout. Keep the same character, same outfit, same camera angle, "
        "same crop, same scale, same style, and same clean silhouette across both states. "
        "Only change the named micro-action; do not change the setting, props, identity, lighting, or composition. "
        f"Base scene: {base_prompt}"
    )
```

- [ ] **Step 4: Run tests to verify they pass**

Run:

```bash
uv run --project backend pytest backend/tests/pipeline/test_flipflop_actions.py -q
```

Expected: all tests pass.

## Task 2: Scene Model Field

**Files:**
- Modify: `backend/models/script.py`
- Test: `backend/tests/test_visual_mode.py`

- [ ] **Step 1: Write failing model tests**

Append to `backend/tests/test_visual_mode.py`:

```python
def test_scene_accepts_valid_flipflop_action():
    scene = Scene(
        id="scene_001",
        narration="He blinks before answering.",
        visual_prompt="[CLOSE-UP] Cartoon teacher at a desk.",
        visual_mode="flipflop",
        flipflop_action="blink",
    )

    assert scene.visual_mode == "flipflop"
    assert scene.flipflop_action == "blink"
    assert scene.model_dump()["flipflop_action"] == "blink"


def test_scene_clears_flipflop_action_when_not_flipflop():
    scene = Scene(
        id="scene_001",
        narration="He blinks before answering.",
        visual_prompt="[CLOSE-UP] Cartoon teacher at a desk.",
        visual_mode="full_frame",
        flipflop_action="blink",
    )

    assert scene.visual_mode == "full_frame"
    assert scene.flipflop_action == ""


def test_scene_clears_invalid_flipflop_action():
    scene = Scene(
        id="scene_001",
        narration="He blinks before answering.",
        visual_prompt="[CLOSE-UP] Cartoon teacher at a desk.",
        visual_mode="flipflop",
        flipflop_action="walking",
    )

    assert scene.visual_mode == "flipflop"
    assert scene.flipflop_action == ""
```

- [ ] **Step 2: Run tests to verify they fail**

Run:

```bash
uv run --project backend pytest backend/tests/test_visual_mode.py -q
```

Expected: fail because `flipflop_action` is not modeled yet.

- [ ] **Step 3: Add model field and normalization**

Modify `backend/models/script.py`:

```python
from pipeline.flipflop_actions import FlipflopAction, normalize_flipflop_action
```

Add near `VisualTreatment`:

```python
FlipflopActionValue = FlipflopAction
```

Add to `Scene` fields after `visual_layers`:

```python
    flipflop_action: FlipflopActionValue | str = ""
```

In `normalize_visual_mode_fields`, after `normalized["visual_mode"] = mode`, add:

```python
        normalized["flipflop_action"] = (
            normalize_flipflop_action(normalized.get("flipflop_action"))
            if mode == "flipflop"
            else ""
        )
```

Add a field validator:

```python
    @field_validator("flipflop_action", mode="before")
    @classmethod
    def normalize_flipflop_action_value(_cls, value: object) -> str:
        return normalize_flipflop_action(value)
```

In `_sync_visual_mode_fields`, add:

```python
        if visual_mode != "flipflop":
            super().__setattr__("flipflop_action", "")
```

- [ ] **Step 4: Run model tests**

Run:

```bash
uv run --project backend pytest backend/tests/test_visual_mode.py -q
```

Expected: all tests pass.

## Task 3: Visual Treatment Validation And Action-Specific Layers

**Files:**
- Modify: `backend/pipeline/visual_treatments.py`
- Test: `backend/tests/test_visual_treatments.py`

- [ ] **Step 1: Write failing visual treatment tests**

Update `backend/tests/test_visual_treatments.py` around existing flip-flop tests:

```python
def test_explicit_flipflop_missing_action_downgrades_to_full_frame():
    scene = scene_with_words("s1", "He blinks before answering.")
    scene.set_visual_mode("flipflop")
    content = content_with_scenes(scene)

    assignments = analyze_visual_treatments(content, script_id="script-missing-action")

    assert assignments[0].visual_mode == "full_frame"
    assert assignments[0].visual_layers == []


def test_explicit_flipflop_non_human_downgrades_to_full_frame():
    scene = scene_with_words("s1", "The clock ticks once on the wall.")
    scene.set_visual_mode("flipflop")
    scene.flipflop_action = "blink"
    content = content_with_scenes(scene)

    assignments = analyze_visual_treatments(content, script_id="script-non-human")

    assert assignments[0].visual_mode == "full_frame"
    assert assignments[0].visual_layers == []


def test_explicit_flipflop_valid_action_uses_action_specific_prompts():
    scene = scene_with_words("s1", "He blinks before answering.")
    scene.set_visual_mode("flipflop")
    scene.flipflop_action = "blink"
    content = content_with_scenes(scene)

    assignments = analyze_visual_treatments(content, script_id="script-blink")

    assignment = assignments[0]
    assert assignment.visual_mode == "flipflop"
    assert [layer.id for layer in assignment.visual_layers] == ["s1_state_a", "s1_state_b"]
    assert "eyes open, neutral natural face" in assignment.visual_layers[0].prompt
    assert "eyes closed in a quick blink" in assignment.visual_layers[1].prompt
    assert all(layer.asset_kind == "cutout" for layer in assignment.visual_layers)


def test_inferred_flipflop_sets_action():
    scene = scene_with_words("s1", "He blinks once, then keeps explaining.")
    content = content_with_scenes(scene)

    assignments = analyze_visual_treatments(content, script_id="script-inferred-blink")

    assignment = assignments[0]
    assert assignment.visual_mode == "flipflop"
    assert assignment.visual_layers[0].prompt
    assert scene.flipflop_action == "blink"
```

- [ ] **Step 2: Run tests to verify they fail**

Run:

```bash
uv run --project backend pytest backend/tests/test_visual_treatments.py -q
```

Expected: new tests fail because explicit flip-flop still preserves missing actions and prompts are generic.

- [ ] **Step 3: Implement validation and action inference**

In `backend/pipeline/visual_treatments.py`, import:

```python
from pipeline.flipflop_actions import (
    build_flipflop_state_prompt,
    has_human_flipflop_subject,
    normalize_flipflop_action,
)
```

Add helper:

```python
def _infer_flipflop_action(scene: Scene) -> str:
    text = f" {scene.narration} {scene.visual_prompt} ".casefold()
    if "blink" in text or "blinks" in text:
        return "blink"
    if any(word in text for word in ("talk", "talks", "speaking", "speaks", "explain", "explains")):
        return "speaking_mouth"
    if "glance" in text or "looks down" in text or "looks sideways" in text:
        return "eye_glance"
    if "eyebrow" in text or "skeptical" in text or "curious" in text:
        return "eyebrow_raise"
    if "nod" in text or "agrees" in text:
        return "head_nod"
    if "point" in text or "points" in text:
        return "pointing_gesture"
    if "count" in text or "counting" in text or "two fingers" in text:
        return "counting_fingers"
    if "think" in text or "thinking" in text or "considers" in text:
        return "thinking_pose"
    if "shrug" in text or "shrugs" in text:
        return "small_shrug"
    if any(word in text for word in ("gesture", "gestures", "present", "presents", "teach", "teaches")):
        return "explaining_hand_raise"
    return ""
```

Update the explicit flip-flop branch in `analyze_visual_treatments`:

```python
    if scene.visual_mode == "flipflop":
        action = normalize_flipflop_action(scene.flipflop_action)
        if not action or not has_human_flipflop_subject(scene.narration, scene.visual_prompt):
            scene.set_visual_mode("full_frame")
            scene.visual_layers = []
            return _full_frame_assignment(
                scene.id,
                "Invalid flipflop request; missing valid human micro-action.",
            )
        scene.flipflop_action = action
        existing_layers = [layer for layer in scene.visual_layers if layer.asset_kind == "cutout"]
        return VisualTreatmentAssignment(
            scene_id=scene.id,
            visual_mode="flipflop",
            reasoning=f"Explicit human micro-action flipflop: {action}.",
            visual_layers=existing_layers if len(existing_layers) >= 2 else _flipflop_layers(scene),
        )
```

Update inferred flip-flop branch:

```python
    if _looks_like_flipflop_micro_action(scene):
        action = _infer_flipflop_action(scene)
        if action and has_human_flipflop_subject(scene.narration, scene.visual_prompt):
            scene.flipflop_action = action
            return VisualTreatmentAssignment(
                scene_id=scene.id,
                visual_mode="flipflop",
                reasoning=f"Detected human micro-action suitable for flipflop: {action}.",
                visual_layers=_flipflop_layers(scene),
            )
```

Replace `_flipflop_layers` prompts:

```python
def _flipflop_layers(scene: Scene) -> list[VisualLayer]:
    action = normalize_flipflop_action(scene.flipflop_action)
    return [
        VisualLayer(
            id=f"{scene.id}_state_a",
            asset_kind="cutout",
            prompt=flipflop_cutout_prompt(scene.visual_prompt, scene.narration, "state A", action=action),
            placement="center",
            enter_at_seconds=0.0,
            animation="none",
        ),
        VisualLayer(
            id=f"{scene.id}_state_b",
            asset_kind="cutout",
            prompt=flipflop_cutout_prompt(scene.visual_prompt, scene.narration, "state B", action=action),
            placement="center",
            enter_at_seconds=0.0,
            animation="none",
        ),
    ]
```

Update `flipflop_cutout_prompt` signature:

```python
def flipflop_cutout_prompt(visual_prompt: str, narration: str, focus: str, *, action: str = "") -> str:
    base_prompt = (
        build_flipflop_state_prompt(
            visual_prompt=visual_prompt,
            narration=narration,
            action=action,
            state="a" if focus.strip().casefold().endswith("a") else "b",
        )
        if action
        else (visual_prompt.strip() or narration.strip())
    )
```

Keep the existing chroma/no-background wording after `base_prompt`.

- [ ] **Step 4: Run visual treatment tests**

Run:

```bash
uv run --project backend pytest backend/tests/test_visual_treatments.py -q
```

Expected: all tests pass after updating old explicit flip-flop tests to set `scene.flipflop_action` where preservation is still expected.

## Task 4: Script Prompt And Scriptwriter Validation

**Files:**
- Modify: `backend/prompts/script.py`
- Modify: `backend/pipeline/scriptwriter.py`
- Test: `backend/tests/pipeline/test_scriptwriter_visual_beats.py`

- [ ] **Step 1: Write failing prompt/validation tests**

Append to `backend/tests/pipeline/test_scriptwriter_visual_beats.py`:

```python
from pipeline.scriptwriter import _validate_flipflop_actions


def test_script_prompt_requires_flipflop_action_allowlist():
    prompt_text = SCRIPT_SYSTEM_PROMPT.template

    assert "flipflop_action" in prompt_text
    assert "blink, speaking_mouth, eye_glance, eyebrow_raise" in prompt_text
    assert "Use only with clear prompt support: pointing_gesture, counting_fingers, small_shrug" in prompt_text
    assert "If no allowed human micro-action naturally fits, choose another visual_mode" in prompt_text


def test_validate_flipflop_actions_downgrades_missing_action():
    scene = Scene(
        id="s1",
        narration="He blinks once.",
        visual_prompt="[CLOSE-UP] Cartoon man at a desk.",
        visual_mode="flipflop",
    )
    content = ScriptContent(title="Test", segments=[Segment(name="One", scenes=[scene])])

    counts = _validate_flipflop_actions(content, script_id="script-1")

    assert counts["downgraded"] == 1
    assert scene.visual_mode == "full_frame"
    assert scene.flipflop_action == ""


def test_validate_flipflop_actions_preserves_valid_human_action():
    scene = Scene(
        id="s1",
        narration="He blinks once.",
        visual_prompt="[CLOSE-UP] Cartoon man at a desk.",
        visual_mode="flipflop",
        flipflop_action="blink",
    )
    content = ScriptContent(title="Test", segments=[Segment(name="One", scenes=[scene])])

    counts = _validate_flipflop_actions(content, script_id="script-1")

    assert counts["preserved"] == 1
    assert scene.visual_mode == "flipflop"
    assert scene.flipflop_action == "blink"
```

- [ ] **Step 2: Run tests to verify they fail**

Run:

```bash
uv run --project backend pytest backend/tests/pipeline/test_scriptwriter_visual_beats.py -q
```

Expected: fail because prompt and validation helper do not exist yet.

- [ ] **Step 3: Update prompt text**

In `backend/prompts/script.py`, replace the `flipflop` vocabulary bullet with:

```text
- "flipflop" — Human/character-only cropped-subject micro-animation. Use only when one visible human, human-like character, or clearly personified character can alternate between two compatible states over the canvas. When you choose this mode, also emit "flipflop_action" using exactly one allowed value. Allowed values: blink, speaking_mouth, eye_glance, eyebrow_raise, head_nod, explaining_hand_raise, thinking_pose, pointing_gesture, counting_fingers, small_shrug. Reliability tiers: Most reliable: blink, speaking_mouth, eye_glance, eyebrow_raise. Reliable when supported: head_nod, explaining_hand_raise, thinking_pose. Use only with clear prompt support: pointing_gesture, counting_fingers, small_shrug. Do not use flipflop for object-only scenes, generic contrast, time-period changes, emotional-state contrast, different locations, statistics, or large pose/environment changes. If no allowed human micro-action naturally fits, choose another visual_mode.
```

In the Frame Directives Format section, add:

```text
For flipflop scenes, include "flipflop_action" on the scene object. For every non-flipflop scene, omit it or set it to an empty string.
```

- [ ] **Step 4: Add scriptwriter validation helper**

In `backend/pipeline/scriptwriter.py`, import:

```python
from pipeline.fallback_observability import record_fallback
from pipeline.flipflop_actions import has_human_flipflop_subject, normalize_flipflop_action
```

Add helper near other post-processing helpers:

```python
def _validate_flipflop_actions(content: ScriptContent, *, script_id: str | None = None) -> dict[str, int]:
    counts = {"preserved": 0, "downgraded": 0, "cleared": 0}
    for scene in content.all_scenes():
        if scene.visual_mode != "flipflop":
            if scene.flipflop_action:
                scene.flipflop_action = ""
                counts["cleared"] += 1
            continue
        action = normalize_flipflop_action(scene.flipflop_action)
        if action and has_human_flipflop_subject(scene.narration, scene.visual_prompt):
            scene.flipflop_action = action
            counts["preserved"] += 1
            continue
        scene.set_visual_mode("full_frame")
        scene.visual_layers = []
        scene.flipflop_action = ""
        counts["downgraded"] += 1
        record_fallback(
            category="visual_mode",
            event="flipflop_invalid_micro_action_downgraded",
            reason="Flipflop scene missing valid human micro-action",
            severity="warn",
            script_id=script_id,
            scene_id=scene.id,
            from_value="flipflop",
            to_value="full_frame",
        )
    return counts
```

Call it after `fmt.enforce_post_processing` and before `_audit_visual_mode_metadata`:

```python
    flipflop_action_counts = _validate_flipflop_actions(content, script_id=script_id)
    if any(flipflop_action_counts.values()):
        logger.info("Script flipflop action validation: %s", flipflop_action_counts)
```

- [ ] **Step 5: Run scriptwriter tests**

Run:

```bash
uv run --project backend pytest backend/tests/pipeline/test_scriptwriter_visual_beats.py -q
```

Expected: all tests pass.

## Task 5: Test Lab And Frontend Pass-Through

**Files:**
- Modify: `backend/pipeline/test_lab.py`
- Modify: `frontend/src/types/script.ts`
- Modify: `frontend/src/types/testLab.ts`
- Modify: `frontend/src/components/test-lab/TestLabControls.tsx`
- Test: `backend/tests/test_test_lab.py`
- Test: `frontend/src/components/test-lab/TestLabControls.test.tsx`

- [ ] **Step 1: Write failing tests**

In `backend/tests/test_test_lab.py`, add:

```python
def test_test_lab_flipflop_settings_preserve_action():
    content = build_content_from_preset(
        "coffee-brain",
        {"visual_mode": "flipflop", "flipflop_action": "blink"},
    )

    scene = content.segments[0].scenes[0]
    assert scene.visual_mode == "flipflop"
    assert scene.flipflop_action == "blink"
```

In `frontend/src/components/test-lab/TestLabControls.test.tsx`, add:

```tsx
it("shows flipflop action selector only for flipflop", () => {
  renderControls({ ...baseSettings, visual_mode: "flipflop", flipflop_action: "blink" });
  expect(screen.getByLabelText("Flip-flop action")).toBeInTheDocument();

  renderControls({ ...baseSettings, visual_mode: "full_frame" });
  expect(screen.queryByLabelText("Flip-flop action")).not.toBeInTheDocument();
});

it("updates flipflop_action without rewriting scene text", async () => {
  const user = userEvent.setup();
  const onChange = vi.fn();
  render(
    <TestLabControls
      settings={{
        ...baseSettings,
        visual_mode: "flipflop",
        flipflop_action: "blink",
        narration: "He blinks once.",
        visual_prompt: "[CLOSE-UP] Cartoon person.",
      }}
      scenes={baseScenes}
      onChange={onChange}
    />,
  );

  await user.selectOptions(screen.getByLabelText("Flip-flop action"), "speaking_mouth");

  expect(onChange).toHaveBeenCalledWith(expect.objectContaining({
    flipflop_action: "speaking_mouth",
    narration: "He blinks once.",
    visual_prompt: "[CLOSE-UP] Cartoon person.",
  }));
});
```

- [ ] **Step 2: Run tests to verify they fail**

Run:

```bash
uv run --project backend pytest backend/tests/test_test_lab.py -q
cd frontend && npm run test -- TestLabControls.test.tsx
```

Expected: fail because Test Lab does not carry `flipflop_action` yet.

- [ ] **Step 3: Update backend Test Lab**

In `backend/pipeline/test_lab.py`, import:

```python
from pipeline.flipflop_actions import FLIPFLOP_ACTIONS, build_flipflop_state_prompt, normalize_flipflop_action
```

Add to `TestLabPreset`:

```python
    flipflop_action: str = "blink"
```

When building a scene in `build_content_from_preset`, resolve:

```python
    flipflop_action = normalize_flipflop_action(settings.get("flipflop_action") or preset.flipflop_action)
```

Pass to `Scene(...)`:

```python
        flipflop_action=flipflop_action if visual_mode == "flipflop" else "",
```

In `_fallback_visual_layers_for_treatment`, replace generic flip-flop prompts with:

```python
            prompt=flipflop_cutout_prompt(scene.visual_prompt, scene.narration, "state A", action=scene.flipflop_action),
```

and:

```python
            prompt=flipflop_cutout_prompt(scene.visual_prompt, scene.narration, "state B", action=scene.flipflop_action),
```

Include `flipflop_action` in run scene manifests where `visual_mode` is currently dumped:

```python
                "flipflop_action": scene.flipflop_action,
```

- [ ] **Step 4: Update frontend types and controls**

In `frontend/src/types/script.ts`, add:

```ts
export type FlipflopAction =
  | "blink"
  | "speaking_mouth"
  | "eye_glance"
  | "eyebrow_raise"
  | "head_nod"
  | "explaining_hand_raise"
  | "thinking_pose"
  | "pointing_gesture"
  | "counting_fingers"
  | "small_shrug";
```

Add to `Scene`:

```ts
  flipflop_action?: FlipflopAction | "";
```

In `frontend/src/types/testLab.ts`, import `FlipflopAction` and add to `TestLabSettings` and `TestLabPreset`:

```ts
  flipflop_action?: FlipflopAction | "";
```

In `frontend/src/components/test-lab/TestLabControls.tsx`, define options near mode options:

```tsx
const FLIPFLOP_ACTION_OPTIONS: Array<{ value: FlipflopAction; label: string }> = [
  { value: "blink", label: "Blink" },
  { value: "speaking_mouth", label: "Speaking mouth" },
  { value: "eye_glance", label: "Eye glance" },
  { value: "eyebrow_raise", label: "Eyebrow raise" },
  { value: "head_nod", label: "Head nod" },
  { value: "explaining_hand_raise", label: "Explaining hand raise" },
  { value: "thinking_pose", label: "Thinking pose" },
  { value: "pointing_gesture", label: "Pointing gesture" },
  { value: "counting_fingers", label: "Counting fingers" },
  { value: "small_shrug", label: "Small shrug" },
];
```

Inside the flip-flop-only section before `LayerPromptFields`, render:

```tsx
<label className="block text-sm text-neutral-300">
  <span className="mb-1 block text-neutral-400">Flip-flop action</span>
  <select
    className="w-full rounded-lg border border-neutral-700 bg-neutral-900 px-3 py-2 text-sm text-neutral-100 transition-colors hover:border-violet-500/70"
    value={settings.flipflop_action || "blink"}
    onChange={(event) => update({ flipflop_action: event.target.value as FlipflopAction })}
  >
    {FLIPFLOP_ACTION_OPTIONS.map((option) => (
      <option key={option.value} value={option.value}>{option.label}</option>
    ))}
  </select>
</label>
```

When switching to `flipflop`, default:

```ts
flipflop_action: nextMode === "flipflop" ? (settings.flipflop_action || "blink") : "",
```

- [ ] **Step 5: Run Test Lab tests**

Run:

```bash
uv run --project backend pytest backend/tests/test_test_lab.py -q
cd frontend && npm run test -- TestLabControls.test.tsx
```

Expected: all tests pass.

## Task 6: Docs And Catalog

**Files:**
- Modify: `AGENTS.md`
- Modify: `frontend/src/components/settings/visual-modes/catalog.ts`
- Test: `frontend/src/components/settings/script-types/modes.test.ts` if catalog test coverage is affected

- [ ] **Step 1: Update AGENTS.md**

Replace the current flip-flop convention sentence with:

```markdown
- **Flipflop visual mode is human micro-action only**: `visual_mode="flipflop"` requires a top-level `flipflop_action` selected from `blink`, `speaking_mouth`, `eye_glance`, `eyebrow_raise`, `head_nod`, `explaining_hand_raise`, `thinking_pose`, `pointing_gesture`, `counting_fingers`, or `small_shrug`. The scriptwriter chooses the action from narration and visual prompt context; backend validation downgrades missing, invalid, object-only, or non-human flip-flops to `full_frame`. Backend action definitions own deterministic State A/B prompts. Flipflop remains two transparent human/character cutouts over the canvas background, with State B generated from State A as reference. Do not add a normal Timeline action dropdown; Test Lab may expose action selection for deliberate testing.
```

- [ ] **Step 2: Update visual-mode catalog text**

In `frontend/src/components/settings/visual-modes/catalog.ts`, update the `flipflop` entry to mention:

```ts
"Human/character-only two-state micro-action cutouts over the canvas. Scenes must carry a flipflop_action such as blink, speaking_mouth, eye_glance, or explaining_hand_raise; invalid requests downgrade to full_frame."
```

- [ ] **Step 3: Run relevant frontend tests**

Run:

```bash
cd frontend && npm run test -- ScriptTypesSection.test.tsx modes.test.ts
```

Expected: all selected tests pass.

## Task 7: Full Verification And Commit

**Files:**
- All modified files above

- [ ] **Step 1: Run focused backend tests**

Run:

```bash
uv run --project backend pytest \
  backend/tests/pipeline/test_flipflop_actions.py \
  backend/tests/test_visual_mode.py \
  backend/tests/test_visual_treatments.py \
  backend/tests/pipeline/test_scriptwriter_visual_beats.py \
  backend/tests/test_test_lab.py \
  -q
```

Expected: all selected backend tests pass.

- [ ] **Step 2: Run focused frontend tests**

Run:

```bash
cd frontend && npm run test -- TestLabControls.test.tsx ScriptTypesSection.test.tsx modes.test.ts
```

Expected: all selected frontend tests pass.

- [ ] **Step 3: Run broader suites if focused tests pass**

Run:

```bash
npm run test:backend
npm run test:frontend
```

Expected: both suites pass.

- [ ] **Step 4: Stage and commit**

Run:

```bash
git add \
  AGENTS.md \
  backend/models/script.py \
  backend/pipeline/flipflop_actions.py \
  backend/pipeline/scriptwriter.py \
  backend/pipeline/test_lab.py \
  backend/pipeline/visual_treatments.py \
  backend/prompts/script.py \
  backend/tests/pipeline/test_flipflop_actions.py \
  backend/tests/pipeline/test_scriptwriter_visual_beats.py \
  backend/tests/test_test_lab.py \
  backend/tests/test_visual_mode.py \
  backend/tests/test_visual_treatments.py \
  frontend/src/components/settings/visual-modes/catalog.ts \
  frontend/src/components/test-lab/TestLabControls.tsx \
  frontend/src/components/test-lab/TestLabControls.test.tsx \
  frontend/src/types/script.ts \
  frontend/src/types/testLab.ts
git commit -m "Add flip-flop human micro-actions"
```

Expected: commit succeeds with only planned implementation files staged.

- [ ] **Step 5: Follow project auto-commit loop**

After the implementation commit, follow `AGENTS.md`: push to `main`, dispatch delegated code review, fix all FAIL/WARN findings, commit fixes as `fix: address review findings`, push, and repeat until LGTM.

## Self-Review

- Spec coverage: The plan covers action enum, validation, deterministic state prompts, script prompting, Test Lab-only selector, cache fingerprint via prompt changes, docs, and no Timeline dropdown.
- Placeholder scan: The plan contains no open-ended implementation markers or unspecified tests.
- Type consistency: The plan uses `flipflop_action` consistently as a top-level scene/Test Lab field and `FlipflopAction` for the TypeScript/Python action vocabulary.
