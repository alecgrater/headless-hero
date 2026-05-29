# Script-Owned Layered Visual Modes Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Let script generation select `popup_sequence` and `flipflop`, while redefining flipflop as same-subject micro-animation instead of generic contrast.

**Architecture:** Update script prompts so the writer can emit layered modes directly. Keep the post-voiceover visual treatment analyzer as a timing/layer completion pass that preserves explicit modes, infers popup sequences from lists, and only infers flipflop from concrete physical micro-motion cues. Update tests and `AGENTS.md` to lock the convention.

**Tech Stack:** Python 3.12, Pydantic script models, pytest via `uv run --project backend pytest`, prompt constants in `backend/prompts`, analyzer helpers in `backend/pipeline/visual_treatments.py`.

---

## Files

- Modify: `backend/prompts/script.py`
- Modify: `backend/pipeline/visual_treatments.py`
- Modify: `backend/tests/pipeline/test_scriptwriter_visual_beats.py`
- Modify: `backend/tests/test_visual_treatments.py`
- Modify: `AGENTS.md`
- Create: `docs/superpowers/specs/2026-05-29-script-owned-layered-visual-modes-design.md`
- Create: `docs/superpowers/plans/2026-05-29-script-owned-layered-visual-modes.md`

## Task 1: Prompt Vocabulary

- [ ] **Step 1: Write failing prompt tests**

Add tests to `backend/tests/pipeline/test_scriptwriter_visual_beats.py`:

```python
def test_script_prompt_includes_popup_sequence_mode():
    assert '"popup_sequence"' in SCRIPT_SYSTEM.template
    assert "concrete items" in SCRIPT_SYSTEM.template
    assert "pop around" in SCRIPT_SYSTEM.template


def test_script_prompt_defines_flipflop_as_micro_animation_not_contrast():
    assert '"flipflop"' in SCRIPT_SYSTEM.template
    assert "micro-animation" in SCRIPT_SYSTEM.template
    assert "Do not use flipflop merely because a sentence contrasts" in SCRIPT_SYSTEM.template
```

- [ ] **Step 2: Run prompt tests to verify they fail**

Run:

```bash
uv run --project backend pytest backend/tests/pipeline/test_scriptwriter_visual_beats.py::test_script_prompt_includes_popup_sequence_mode backend/tests/pipeline/test_scriptwriter_visual_beats.py::test_script_prompt_defines_flipflop_as_micro_animation_not_contrast -q
```

Expected: FAIL because the prompt does not yet describe `popup_sequence` or the new `flipflop` semantics.

- [ ] **Step 3: Update prompt vocabulary**

In `backend/prompts/script.py`, extend the Visual Mode System:

- Add `popup_sequence` after `multi_frame`.
- Add `flipflop` after `popup_sequence`.
- Update distribution rules so variety modes include `popup_sequence` and `flipflop`.
- Keep `video` excluded from script generation.

Use this wording:

```text
- "popup_sequence" — When narration names a small set of concrete items, examples, ingredients, symptoms, tools, steps, or visible objects that should pop around the main subject. Use a single anchor visual plus popup item intent; the post-voiceover pass will create timed cutout layers. Do not use for abstract contrasts or long lists.
- "flipflop" — When one subject/action can read as simple micro-animation by alternating two compatible A/B states: hands moving while typing, stirring, sorting, opening, closing, pointing, counting, or handling an object; a character leaning in/out, looking up/down, pacing, nodding, or gesturing while talking. Do not use flipflop merely because a sentence contrasts two ideas, time periods, or emotional states.
```

- [ ] **Step 4: Run prompt tests to verify they pass**

Run the same focused pytest command. Expected: PASS.

## Task 2: Analyzer Semantics

- [ ] **Step 1: Write failing analyzer tests**

In `backend/tests/test_visual_treatments.py`, replace the contrast/repetition flipflop tests with:

```python
def test_analyze_visual_treatments_does_not_assign_flipflop_for_generic_contrast():
    scene = scene_with_words("s1", "At first the room is calm, but then everything becomes chaos.")
    content = content_with_scenes(scene)

    assignments = analyze_visual_treatments(content, script_id="script-contrast")

    assert assignments[0].visual_mode == "full_frame"
    assert assignments[0].visual_treatment == "full_frame"


def test_analyze_visual_treatments_assigns_flipflop_for_same_subject_micro_action():
    scene = scene_with_words("s1", "His hands open and close around the microphone while he talks.")
    content = content_with_scenes(scene)

    assignments = analyze_visual_treatments(content, script_id="script-micro-action")

    assignment = assignments[0]
    assert assignment.scene_id == "s1"
    assert assignment.visual_mode == "flipflop"
    assert assignment.visual_treatment == "flipflop"
    assert len(assignment.visual_layers) == 2
    assert [layer.id for layer in assignment.visual_layers] == ["s1_state_a", "s1_state_b"]
```

Also update `test_analyze_visual_treatments_keeps_contrast_mode_with_progression_words` so its scene explicitly calls `scene.set_visual_mode("flipflop")`; the preservation behavior remains valid, but contrast inference is removed.

- [ ] **Step 2: Run analyzer tests to verify they fail**

Run:

```bash
uv run --project backend pytest backend/tests/test_visual_treatments.py::test_analyze_visual_treatments_does_not_assign_flipflop_for_generic_contrast backend/tests/test_visual_treatments.py::test_analyze_visual_treatments_assigns_flipflop_for_same_subject_micro_action -q
```

Expected: FAIL because generic contrast still routes to `flipflop`.

- [ ] **Step 3: Update analyzer helpers**

In `backend/pipeline/visual_treatments.py`:

- Remove contrast-marker based `flipflop` routing from `_analyze_scene`.
- Add same-subject micro-action marker sets for body/action terms and motion terms.
- Add `_looks_like_flipflop_micro_action(scene: Scene) -> bool`.
- Route to `flipflop` only when that helper returns true.
- Change the default reasoning from `"No list or contrast pattern detected."` to `"No list or micro-action pattern detected."`.

The helper should require at least one subject/body cue and at least one physical motion cue, with phrases such as `open and close`, `back and forth`, or `while he talks` counting as strong cues.

- [ ] **Step 4: Run analyzer tests to verify they pass**

Run:

```bash
uv run --project backend pytest backend/tests/test_visual_treatments.py::test_analyze_visual_treatments_does_not_assign_flipflop_for_generic_contrast backend/tests/test_visual_treatments.py::test_analyze_visual_treatments_assigns_flipflop_for_same_subject_micro_action backend/tests/test_visual_treatments.py::test_analyze_visual_treatments_preserves_explicit_flipflop_with_progression_words -q
```

Expected: PASS.

## Task 3: Explicit Layer Completion

- [ ] **Step 1: Write or confirm tests for explicit preservation**

Confirm these existing tests still cover the desired behavior:

```bash
rg -n "preserves_explicit_popup_sequence|preserves_explicit_flipflop|accepts_multi_frame|accepts_continuous" backend/tests/test_visual_treatments.py
```

Expected: existing tests are present. If explicit layered modes without layers are not covered, add a test that sets `scene.set_visual_mode("flipflop")` with no layers and asserts two layers are returned.

- [ ] **Step 2: Run preservation tests**

Run:

```bash
uv run --project backend pytest backend/tests/test_visual_treatments.py::test_analyze_visual_treatments_preserves_explicit_popup_sequence_with_progression_words backend/tests/test_visual_treatments.py::test_analyze_visual_treatments_preserves_explicit_flipflop_with_progression_words -q
```

Expected: PASS.

## Task 4: Project Conventions

- [ ] **Step 1: Update `AGENTS.md`**

Edit the relevant bullets:

- In `Scene visual mode is canonical`, note that script generation may emit `popup_sequence` and `flipflop`.
- In `Layered visual modes render over a global static canvas`, note that the post-voiceover analyzer fills timing/layers for explicit layered modes.
- Replace the current flipflop convention with: `Flip-flop is same-subject micro-animation: Use visual_mode="flipflop" for one subject/action alternating between compatible A/B states to simulate simple animation without generating a video clip. Do not use it for generic contrast between different ideas, time periods, or emotional states.`

- [ ] **Step 2: Verify convention text**

Run:

```bash
rg -n "script generation may emit|same-subject micro-animation|generic contrast" AGENTS.md
```

Expected: all three phrases are present.

## Task 5: Verification

- [ ] **Step 1: Run focused backend tests**

Run:

```bash
uv run --project backend pytest backend/tests/pipeline/test_scriptwriter_visual_beats.py backend/tests/test_visual_treatments.py -q
```

Expected: PASS.

- [ ] **Step 2: Run broader backend tests if focused tests pass**

Run:

```bash
npm run test:backend
```

Expected: PASS.

- [ ] **Step 3: Review diff**

Run:

```bash
git diff -- backend/prompts/script.py backend/pipeline/visual_treatments.py backend/tests/pipeline/test_scriptwriter_visual_beats.py backend/tests/test_visual_treatments.py AGENTS.md docs/superpowers/specs/2026-05-29-script-owned-layered-visual-modes-design.md docs/superpowers/plans/2026-05-29-script-owned-layered-visual-modes.md
```

Expected: diff only contains scoped prompt, analyzer, test, docs, and convention changes.
