# Multi-Frame Visual Modes Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make `multi_frame` and `continuous` canonical visual modes, with old `quick_cuts` and `montage` data normalized into `multi_frame`.

**Architecture:** Keep `visual_mode` as the source of truth. Preserve `visual_treatment` as a compatibility mirror for static-canvas layer treatments only, so `multi_frame` and `continuous` mirror to `visual_treatment="full_frame"` while carrying their true behavior in `visual_mode`. Reuse existing multi-frame generation and Remotion rendering paths instead of adding a new renderer.

**Tech Stack:** Python 3.12, Pydantic/SQLModel, FastAPI pipeline modules, React 19/TypeScript, Remotion 4, Vitest, Pytest via `uv`.

---

## File Map

- Modify `backend/models/script.py`
  - Add `multi_frame` and `continuous` to `VISUAL_MODES` and `VisualMode`.
  - Add legacy `visual_beat` fallback inside model normalization.
  - Preserve `frame_urls` for `multi_frame` and `continuous`.
- Modify `backend/tests/test_visual_mode.py`
  - Cover explicit new modes and legacy beat-derived modes.
- Modify `remotion/src/types.ts`
  - Add new visual modes to Remotion input props.
- Modify `frontend/src/types/script.ts`
  - Add new visual modes to frontend script model.
- Modify `frontend/src/types/testLab.ts`
  - Add new visual modes to Test Lab settings and presets.
- Modify `frontend/src/components/test-lab/TestLabControls.tsx`
  - Add `Multi-frame` and `Continuous` options.
  - Keep treatment assets relevant only for `popup_sequence` and `flipflop`.
- Modify `backend/pipeline/test_lab.py`
  - Add new mode literals and text defaults.
  - Ensure only layered modes invoke treatment asset generation.
- Modify `backend/tests/test_test_lab.py`
  - Verify settings preserve `multi_frame` and `continuous`.
- Modify `backend/prompts/script.py`
  - Stop asking for `quick_cuts` and `montage`.
  - Describe `visual_mode` vocabulary including `multi_frame` and `continuous`.
- Modify `backend/pipeline/scriptwriter.py`
  - Synthesize frame directives by canonical mode first.
  - Keep old beat compatibility paths.
- Modify `backend/tests/pipeline/test_scriptwriter_visual_beats.py`
  - Verify `multi_frame` and `continuous` directive synthesis.
  - Verify prompt vocabulary does not instruct new `quick_cuts` or `montage` use.
- Modify `backend/pipeline/formats/youtube_listicle.py`
  - Replace old allowed beat vocabulary with the compatibility set used by the scriptwriter.
- Modify `backend/pipeline/formats/life_as_a.py`
  - Do not coerce `multi_frame` or `continuous` away.
  - Keep `aha_subtitle` disabled.
- Modify `backend/pipeline/visual_treatments.py`
- Modify `backend/pipeline/media_analyzer.py`
  - Emit canonical visual modes only.
  - Map list/example patterns to `multi_frame` and process/progression patterns to `continuous`.
- Modify `backend/tests/test_visual_treatments.py`
  - Verify analyzer/apply paths preserve new canonical modes.
- Modify `backend/tests/pipeline/test_remotion_render.py`
  - Verify Remotion props include new modes with frame paths.
- Modify `AGENTS.md`
  - Add the newly established convention that `multi_frame` and `continuous` are canonical visual modes and `quick_cuts`/`montage` are compatibility aliases only.

## Task 1: Backend Model Normalization

**Files:**
- Modify: `backend/models/script.py`
- Test: `backend/tests/test_visual_mode.py`

- [ ] **Step 1: Write failing model tests**

Append these tests to `backend/tests/test_visual_mode.py`:

```python
def test_scene_accepts_explicit_multi_frame_visual_mode():
    scene = Scene(
        id="scene_001",
        narration="Three images land fast.",
        visual_prompt="Several examples.",
        visual_mode="multi_frame",
        frame_urls=["/static/projects/script/images/scene_001_0.png"],
    )

    assert scene.visual_mode == "multi_frame"
    assert scene.media_source == "ai"
    assert scene.visual_treatment == "full_frame"
    assert scene.frame_urls == ["/static/projects/script/images/scene_001_0.png"]


def test_scene_accepts_explicit_continuous_visual_mode():
    scene = Scene(
        id="scene_001",
        narration="A plant grows across the scene.",
        visual_prompt="A sprout growing.",
        visual_mode="continuous",
        frame_urls=["/static/projects/script/images/scene_001_0.png"],
    )

    assert scene.visual_mode == "continuous"
    assert scene.media_source == "ai"
    assert scene.visual_treatment == "full_frame"
    assert scene.frame_urls == ["/static/projects/script/images/scene_001_0.png"]


def test_scene_derives_multi_frame_from_legacy_quick_cuts_beat():
    scene = Scene(
        id="scene_001",
        narration="First this, then that.",
        visual_prompt="Multiple examples.",
        visual_beat="quick_cuts",
        frame_urls=["/static/projects/script/images/scene_001_0.png"],
    )

    assert scene.visual_mode == "multi_frame"
    assert scene.media_source == "ai"
    assert scene.visual_treatment == "full_frame"
    assert scene.frame_urls == ["/static/projects/script/images/scene_001_0.png"]


def test_scene_derives_multi_frame_from_legacy_montage_beat():
    scene = Scene(
        id="scene_001",
        narration="Several places flash by.",
        visual_prompt="Several related places.",
        visual_beat="montage",
    )

    assert scene.visual_mode == "multi_frame"
    assert scene.media_source == "ai"
    assert scene.visual_treatment == "full_frame"


def test_scene_derives_continuous_from_legacy_continuous_beat():
    scene = Scene(
        id="scene_001",
        narration="The machine assembles itself.",
        visual_prompt="A machine being assembled.",
        visual_beat="continuous",
    )

    assert scene.visual_mode == "continuous"
    assert scene.media_source == "ai"
    assert scene.visual_treatment == "full_frame"
```

- [ ] **Step 2: Run the focused failing tests**

Run:

```bash
uv run --project backend pytest backend/tests/test_visual_mode.py -v
```

Expected: the new tests fail because `multi_frame` and `continuous` are not valid `visual_mode` values and beat fallback does not derive them.

- [ ] **Step 3: Update `backend/models/script.py`**

Change the visual mode constants near the top of the file to:

```python
VISUAL_MODES = {"video", "full_frame", "multi_frame", "continuous", "popup_sequence", "flipflop"}
VISUAL_TREATMENTS = {"full_frame", "popup_sequence", "flipflop"}
VISUAL_LAYER_TYPES = {"image"}
VISUAL_ASSET_KINDS = {"full_frame", "panel", "cutout"}
VISUAL_LAYER_ANIMATIONS = {"none", "pop_in"}
VisualMode = Literal["video", "full_frame", "multi_frame", "continuous", "popup_sequence", "flipflop"]
VisualTreatment = Literal["full_frame", "popup_sequence", "flipflop"]
```

Update `Scene.normalize_visual_mode_fields` so it passes `visual_beat` into `_resolve_visual_mode` and only clears frames for modes that own non-frame assets:

```python
        mode = _resolve_visual_mode(
            normalized.get("visual_mode"),
            normalized.get("media_source"),
            normalized.get("visual_treatment"),
            normalized.get("visual_beat"),
        )
        media_source, visual_treatment = _legacy_fields_for_visual_mode(mode)
        normalized["visual_mode"] = mode
        normalized["media_source"] = media_source
        normalized["visual_treatment"] = visual_treatment
        if mode in {"video", "popup_sequence", "flipflop"}:
            normalized["frame_urls"] = []
```

Update `_resolve_visual_mode` to accept `visual_beat`:

```python
def _resolve_visual_mode(
    visual_mode: object,
    media_source: object,
    visual_treatment: object,
    visual_beat: object = None,
) -> VisualMode:
    if isinstance(visual_mode, str) and visual_mode in VISUAL_MODES:
        return visual_mode  # type: ignore[return-value]
    if media_source == "ai_video":
        return "video"
    if isinstance(visual_treatment, str) and visual_treatment in {"popup_sequence", "flipflop"}:
        return visual_treatment  # type: ignore[return-value]
    if visual_beat in {"quick_cuts", "montage", "multi_frame"}:
        return "multi_frame"
    if visual_beat == "continuous":
        return "continuous"
    return "full_frame"
```

Update `_legacy_fields_for_visual_mode`:

```python
def _legacy_fields_for_visual_mode(visual_mode: VisualMode) -> tuple[str, VisualTreatment]:
    if visual_mode == "video":
        return "ai_video", "full_frame"
    if visual_mode in {"popup_sequence", "flipflop"}:
        return "ai", visual_mode
    return "ai", "full_frame"
```

- [ ] **Step 4: Run the model tests**

Run:

```bash
uv run --project backend pytest backend/tests/test_visual_mode.py -v
```

Expected: all tests in `test_visual_mode.py` pass.

- [ ] **Step 5: Commit Task 1**

Run:

```bash
git add backend/models/script.py backend/tests/test_visual_mode.py
git commit -m "Add multi-frame visual mode normalization"
```

## Task 2: TypeScript Types and Test Lab Controls

**Files:**
- Modify: `remotion/src/types.ts`
- Modify: `frontend/src/types/script.ts`
- Modify: `frontend/src/types/testLab.ts`
- Modify: `frontend/src/components/test-lab/TestLabControls.tsx`
- Test: `frontend/src/remotion/TreatmentRenderer.test.ts`

- [ ] **Step 1: Update TypeScript visual mode unions**

In `remotion/src/types.ts`, change:

```ts
export type VisualMode = "video" | "full_frame" | "popup_sequence" | "flipflop";
```

to:

```ts
export type VisualMode = "video" | "full_frame" | "multi_frame" | "continuous" | "popup_sequence" | "flipflop";
```

In `frontend/src/types/script.ts`, make the same `VisualMode` change and update `Scene.visual_beat` to accept compatibility mode labels:

```ts
export type VisualMode = "video" | "full_frame" | "multi_frame" | "continuous" | "popup_sequence" | "flipflop";
```

```ts
visual_beat?: "static" | "continuous" | "multi_frame" | "quick_cuts" | "aha_subtitle" | "montage";
```

In `frontend/src/types/testLab.ts`, update every `VisualMode` import/alias or literal union so `multi_frame` and `continuous` are valid settings.

- [ ] **Step 2: Update Test Lab option list**

In `frontend/src/components/test-lab/TestLabControls.tsx`, import suitable icons:

```ts
import { Film, HelpCircle, Images, Image, Palette, PanelsTopLeft, Repeat2, Route, UserRound } from "lucide-react";
```

Add these entries to `VISUAL_MODE_OPTIONS` between `full_frame` and `popup_sequence`:

```tsx
  {
    value: "multi_frame",
    label: "Multi-frame",
    icon: <Images className="h-4 w-4" />,
    summary: "Several independent images share one narration scene.",
    description: "Generates multiple separate frames and cuts through them for examples, comparisons, or rapid visual variety.",
    bestFor: "Use for lists, multiple examples, fast context shifts, or montage-like visual rhythm.",
  },
  {
    value: "continuous",
    label: "Continuous",
    icon: <Route className="h-4 w-4" />,
    summary: "One scene evolves across several frames.",
    description: "Generates related frames with reference continuity so a process or transformation unfolds over time.",
    bestFor: "Use for growth, construction, pouring, movement through a process, or a single action progressing.",
  },
```

- [ ] **Step 3: Keep treatment assets scoped to layered modes**

Replace the local `isVideo`-only stage logic with a layered-mode helper:

```ts
  const isVideo = visualMode === "video";
  const isLayeredTreatment = visualMode === "popup_sequence" || visualMode === "flipflop";
```

In `updateStage`, replace:

```ts
    if (isVideo && key === "treatment_assets") return;
```

with:

```ts
    if (!isLayeredTreatment && key === "treatment_assets") return;
```

In the stage option loop, replace:

```ts
            const disabled = (stage.key === "treatment_assets" && isVideo) || (stage.key === "eli" && !settings.eli_enabled);
```

with:

```ts
            const disabled = (stage.key === "treatment_assets" && !isLayeredTreatment) || (stage.key === "eli" && !settings.eli_enabled);
```

In `updateVisualMode`, replace the `visualTreatment` calculation and layer clearing:

```ts
    const visualTreatment = nextMode === "popup_sequence" || nextMode === "flipflop" ? nextMode : "full_frame";
```

```ts
        visual_layers: nextMode === "popup_sequence" || nextMode === "flipflop" ? settings.visual_layers : [],
```

and disable treatment assets for every non-layered mode:

```ts
          treatment_assets: nextMode === "popup_sequence" || nextMode === "flipflop"
            ? settings.stages.treatment_assets
            : false,
```

Update the helper paragraph under the mode list so it applies to all non-layered modes:

```tsx
            {!isLayeredTreatment && (
              <p className="mt-2 text-xs leading-5 text-neutral-500">
                This mode does not use layered animation assets; it renders through the main scene media pipeline.
              </p>
            )}
```

- [ ] **Step 4: Run frontend type/test checks**

Run:

```bash
npm run test:frontend -- --run
```

Expected: Vitest passes. If the command does not accept `-- --run` in this repo, run `npm run test:frontend` and verify it exits cleanly.

- [ ] **Step 5: Commit Task 2**

Run:

```bash
git add remotion/src/types.ts frontend/src/types/script.ts frontend/src/types/testLab.ts frontend/src/components/test-lab/TestLabControls.tsx
git commit -m "Add multi-frame visual modes to frontend types"
```

## Task 3: Test Lab Backend Mode Support

**Files:**
- Modify: `backend/pipeline/test_lab.py`
- Test: `backend/tests/test_test_lab.py`

- [ ] **Step 1: Write failing Test Lab tests**

Append tests to `backend/tests/test_test_lab.py` that verify mode preservation. Use existing test helpers in that file for manifests/settings. If there is no focused helper, add direct model tests:

```python
from pipeline.test_lab import TestLabPreset


def test_test_lab_preset_accepts_multi_frame_visual_mode():
    preset = TestLabPreset(
        id="multi",
        title="Multi",
        description="Multi frame",
        segment_name="Segment",
        narration="First this, then that.",
        visual_prompt="Several examples.",
        visual_mode="multi_frame",
    )

    assert preset.visual_mode == "multi_frame"


def test_test_lab_preset_accepts_continuous_visual_mode():
    preset = TestLabPreset(
        id="continuous",
        title="Continuous",
        description="Continuous",
        segment_name="Segment",
        narration="The object grows.",
        visual_prompt="A sprout growing.",
        visual_mode="continuous",
    )

    assert preset.visual_mode == "continuous"
```

- [ ] **Step 2: Run the focused failing tests**

Run:

```bash
uv run --project backend pytest backend/tests/test_test_lab.py -v
```

Expected: new tests fail because the `TestLabPreset.visual_mode` literal does not include the new modes.

- [ ] **Step 3: Update Test Lab backend literals and defaults**

In `backend/pipeline/test_lab.py`, change the `visual_mode` literal on `TestLabPreset`:

```python
    visual_mode: Literal["video", "full_frame", "multi_frame", "continuous", "popup_sequence", "flipflop"] = "full_frame"
```

Add text defaults near the existing `POPUP_SEQUENCE_TEXT_DEFAULTS` and `FLIPFLOP_TEXT_DEFAULTS`:

```python
MULTI_FRAME_TEXT_DEFAULTS = {
    "narration": (
        "First the warning signs were tiny, then they were everywhere, and by the end nobody could pretend "
        "they had not seen them."
    ),
    "visual_prompt": (
        "[CONTRAST] Flat 2D cartoon sequence of escalating warning signs in a city, starting with a small "
        "cracked sidewalk, then a crowded notice board, then a wide street scene where everyone is reacting, "
        "bold outlines, clean staged compositions, no readable words or letters."
    ),
}
CONTINUOUS_TEXT_DEFAULTS = {
    "narration": (
        "The tiny crack spreads across the wall until the whole room feels like it is holding its breath."
    ),
    "visual_prompt": (
        "[CLOSE-UP] Flat 2D cartoon wall with a tiny crack slowly spreading outward through the same room, "
        "consistent camera angle, bold outline, simple dramatic lighting, no readable words or letters."
    ),
}
```

Update `VISUAL_TREATMENT_TEXT_DEFAULTS`:

```python
VISUAL_TREATMENT_TEXT_DEFAULTS = {
    "multi_frame": MULTI_FRAME_TEXT_DEFAULTS,
    "continuous": CONTINUOUS_TEXT_DEFAULTS,
    "popup_sequence": POPUP_SEQUENCE_TEXT_DEFAULTS,
    "flipflop": FLIPFLOP_TEXT_DEFAULTS,
}
```

Find checks like:

```python
scene.visual_mode in {"popup_sequence", "flipflop"}
```

Keep those unchanged for layered asset generation. `multi_frame` and `continuous` should not enter `generate_visual_layer_panels` or `generate_popup_sequence_cutouts`.

- [ ] **Step 4: Run Test Lab tests**

Run:

```bash
uv run --project backend pytest backend/tests/test_test_lab.py -v
```

Expected: all Test Lab tests pass.

- [ ] **Step 5: Commit Task 3**

Run:

```bash
git add backend/pipeline/test_lab.py backend/tests/test_test_lab.py
git commit -m "Support multi-frame modes in Test Lab"
```

## Task 4: Scriptwriter Prompt and Directive Synthesis

**Files:**
- Modify: `backend/prompts/script.py`
- Modify: `backend/pipeline/scriptwriter.py`
- Modify: `backend/tests/pipeline/test_scriptwriter_visual_beats.py`

- [ ] **Step 1: Write failing prompt and synthesis tests**

Add these tests to `backend/tests/pipeline/test_scriptwriter_visual_beats.py`:

```python
from prompts import script as script_prompt


def test_script_prompt_no_longer_requests_quick_cuts_or_montage():
    prompt_text = script_prompt.SCRIPT_SYSTEM

    assert '"quick_cuts"' not in prompt_text
    assert '"montage"' not in prompt_text
    assert '"multi_frame"' in prompt_text


def test_multi_frame_mode_without_directives_is_repaired():
    scene = _static_scene("scene_001")
    scene.visual_mode = "multi_frame"
    scene.visual_beat = "multi_frame"
    scene.frame_directives = []
    content = ScriptContent(
        title="Your Life As A Test",
        format_id="life-as-a",
        segments=[Segment(name="Level 1, the waiting", scenes=[scene])],
    )

    _ensure_visual_beat_directives(content)

    assert scene.visual_mode == "multi_frame"
    assert len(scene.frame_directives) == 4
    assert all(frame.reference_previous is False for frame in scene.frame_directives)
    assert all(frame.transition == "cut" for frame in scene.frame_directives)


def test_continuous_mode_without_directives_is_repaired():
    scene = _static_scene("scene_001")
    scene.visual_mode = "continuous"
    scene.visual_beat = "continuous"
    scene.frame_directives = []
    content = ScriptContent(
        title="Your Life As A Test",
        format_id="life-as-a",
        segments=[Segment(name="Level 1, the waiting", scenes=[scene])],
    )

    _ensure_visual_beat_directives(content)

    assert scene.visual_mode == "continuous"
    assert len(scene.frame_directives) == 3
    assert scene.frame_directives[0].reference_previous is False
    assert all(frame.reference_previous is True for frame in scene.frame_directives[1:])
    assert all(frame.transition == "crossfade" for frame in scene.frame_directives[1:])
```

- [ ] **Step 2: Run the focused failing tests**

Run:

```bash
uv run --project backend pytest backend/tests/pipeline/test_scriptwriter_visual_beats.py -v
```

Expected: prompt test fails while the old prompt contains `quick_cuts` and `montage`; synthesis tests fail if `multi_frame` is not handled.

- [ ] **Step 3: Update prompt vocabulary**

In `backend/prompts/script.py`, replace the visual beat vocabulary section with wording that asks for modes directly. The updated section should include this text:

```text
### Visual Mode System
Use "visual_mode" to control how each scene looks.

VISUAL MODE VOCABULARY:
- "full_frame" — The DEFAULT mode. A single strong image per scene. Since scenes are only 1-2 sentences, one well-composed image is usually sufficient. Most scenes should use this.
- "continuous" — When narration describes a physical process unfolding over time (pouring, growing, building). 2-4 frames with reference_previous: true and transition: "crossfade". Frames show subtle progression of the SAME scene. Use deliberately, not as default.
- "multi_frame" — When narration covers multiple examples, lists, comparisons, or rapid context switches. 3-8 frames with reference_previous: false and transition: "cut" primarily. Each frame is a different shot, subject, angle, composition, or example. Use deliberately for visual variety. Narration should be one short punchy sentence when possible.
- "aha_subtitle" — When a sentence delivers a shocking stat, counterintuitive fact, or "wait, really?" moment. Pure white text on black. 1 frame directive with source: "subtitle". Aim for 5-6 per video, no more than 7. Must be preceded and followed by image-bearing beats for contrast. visual_prompt should be empty. Narration should be 1 short sentence — a single stat or fact, under 8 seconds of speech.
```

Update distribution rules in that same section so they refer to `full_frame`, `multi_frame`, `continuous`, and `aha_subtitle`; do not mention `quick_cuts` or `montage`.

Where the prompt still requires `visual_beat`, keep compatibility wording:

```text
For backward compatibility, set visual_beat to the same value as visual_mode except use "static" when visual_mode is "full_frame".
```

- [ ] **Step 4: Update directive synthesis**

In `backend/pipeline/scriptwriter.py`, update `_synthesize_frame_directives` so it resolves the canonical mode before branch selection:

```python
def _directive_mode(scene: Scene, beat: str) -> str:
    if scene.visual_mode in {"multi_frame", "continuous"}:
        return scene.visual_mode
    if beat in {"quick_cuts", "montage", "multi_frame"}:
        return "multi_frame"
    if beat == "continuous":
        return "continuous"
    if beat == "aha_subtitle":
        return "aha_subtitle"
    return "full_frame"
```

At the start of `_synthesize_frame_directives`, add:

```python
    mode = _directive_mode(scene, beat)
```

Replace the `beat == "static"` branch condition with:

```python
    if mode == "full_frame":
```

Replace the `beat == "continuous"` branch condition with:

```python
    elif mode == "continuous":
```

Replace the `beat == "quick_cuts"` branch condition with:

```python
    elif mode == "multi_frame":
```

Keep the current four independent directive prompts under the `multi_frame` branch. They are a good fallback for both old quick-cut and montage scenes.

Replace the `beat == "aha_subtitle"` branch condition with:

```python
    elif mode == "aha_subtitle":
```

In `_ensure_visual_beat_directives`, keep the call:

```python
        _synthesize_frame_directives(scene, scene.visual_beat or "static")
```

because `_synthesize_frame_directives` now prefers `scene.visual_mode`.

- [ ] **Step 5: Run scriptwriter tests**

Run:

```bash
uv run --project backend pytest backend/tests/pipeline/test_scriptwriter_visual_beats.py -v
```

Expected: all scriptwriter visual beat tests pass.

- [ ] **Step 6: Commit Task 4**

Run:

```bash
git add backend/prompts/script.py backend/pipeline/scriptwriter.py backend/tests/pipeline/test_scriptwriter_visual_beats.py
git commit -m "Unify multi-frame script visual modes"
```

## Task 5: Format Rules and Life-As-A Compatibility

**Files:**
- Modify: `backend/pipeline/formats/youtube_listicle.py`
- Modify: `backend/pipeline/formats/life_as_a.py`
- Test: `backend/tests/pipeline/test_life_as_a_post_processing.py`
- Test: `backend/tests/pipeline/test_formats_registry.py`

- [ ] **Step 1: Write failing format tests**

Add this test to `backend/tests/pipeline/test_life_as_a_post_processing.py`:

```python
def test_life_as_a_preserves_multi_frame_and_continuous_visual_modes():
    content = ScriptContent(
        title="Your Life As A Guard",
        format_id="life-as-a",
        segments=[
            Segment(
                name="Level 1, the rookie",
                scenes=[
                    Scene(
                        id="scene_001",
                        narration="First the gate rattles, then the lights fail.",
                        visual_prompt="[CONTRAST] A nervous guard at a gate.",
                        visual_mode="multi_frame",
                        visual_beat="multi_frame",
                    ),
                    Scene(
                        id="scene_002",
                        narration="The crack slowly crawls across the booth window.",
                        visual_prompt="[CLOSE-UP] A crack spreading across glass.",
                        visual_mode="continuous",
                        visual_beat="continuous",
                    ),
                ],
            )
        ],
    )

    enforce_life_as_a_constraints(content, eli_enabled=False)

    scenes = content.all_scenes()
    assert scenes[1].visual_mode == "multi_frame"
    assert scenes[1].visual_beat == "multi_frame"
    assert scenes[2].visual_mode == "continuous"
    assert scenes[2].visual_beat == "continuous"
```

If the test file uses different helper imports, add:

```python
from models.script import Scene, ScriptContent, Segment
from pipeline.formats.life_as_a import enforce_life_as_a_constraints
```

- [ ] **Step 2: Run focused format tests**

Run:

```bash
uv run --project backend pytest backend/tests/pipeline/test_life_as_a_post_processing.py backend/tests/pipeline/test_formats_registry.py -v
```

Expected: the new life-as-a test fails if the post-processor still treats `multi_frame` as disallowed.

- [ ] **Step 3: Update allowed beat compatibility**

In `backend/pipeline/formats/youtube_listicle.py`, update:

```python
allowed_beats=frozenset({"static", "continuous", "multi_frame", "aha_subtitle"}),
```

In `backend/pipeline/formats/life_as_a.py`, update `LIFE_AS_A_BEAT_RULES.allowed_beats` wherever it is defined so it includes:

```python
frozenset({"static", "continuous", "multi_frame"})
```

Keep `aha_subtitle` disabled for life-as-a.

Update the docstring in `enforce_life_as_a_constraints` from:

```python
    - Coerce disallowed visual_beat values ('aha_subtitle', 'montage') back to 'static'.
```

to:

```python
    - Coerce disallowed visual_beat values such as 'aha_subtitle' back to 'static'.
```

In the coercion loop, after a scene's `visual_beat` is coerced to `static`, call:

```python
            scene.set_visual_mode("full_frame")
```

so stale legacy values do not leave a disallowed canonical mode behind.

- [ ] **Step 4: Run format tests**

Run:

```bash
uv run --project backend pytest backend/tests/pipeline/test_life_as_a_post_processing.py backend/tests/pipeline/test_formats_registry.py -v
```

Expected: format tests pass.

- [ ] **Step 5: Commit Task 5**

Run:

```bash
git add backend/pipeline/formats/youtube_listicle.py backend/pipeline/formats/life_as_a.py backend/tests/pipeline/test_life_as_a_post_processing.py backend/tests/pipeline/test_formats_registry.py
git commit -m "Allow canonical multi-frame modes by format"
```

## Task 6: Analyzer and Assignment Routing

**Files:**
- Modify: `backend/pipeline/visual_treatments.py`
- Modify: `backend/pipeline/media_analyzer.py`
- Test: `backend/tests/test_visual_treatments.py`
- Test: `backend/tests/test_media_source_dispatch.py`

- [ ] **Step 1: Write failing analyzer tests**

Add these tests to `backend/tests/test_visual_treatments.py`:

```python
def test_analyze_visual_treatments_preserves_explicit_multi_frame_mode():
    content = content_with_scenes(
        scene_with_words("scene_001", "First the room gets colder, then the lights flicker, then the door opens.")
    )
    content.all_scenes()[0].set_visual_mode("multi_frame")

    assignments = analyze_visual_treatments(content, script_id="script-1")

    assert assignments[0].visual_mode == "multi_frame"
    assert assignments[0].visual_treatment == "full_frame"
    assert assignments[0].visual_layers == []


def test_analyze_visual_treatments_detects_continuous_progression():
    content = content_with_scenes(
        scene_with_words("scene_001", "The crack slowly spreads across the glass.")
    )

    assignments = analyze_visual_treatments(content, script_id="script-1")

    assert assignments[0].visual_mode == "continuous"
    assert assignments[0].visual_treatment == "full_frame"
    assert assignments[0].visual_layers == []


def test_apply_visual_treatment_assignment_accepts_multi_frame_mode():
    content = content_with_scenes(
        Scene(id="scene_001", narration="First this, then that.", visual_prompt="A list")
    )

    apply_visual_treatment_assignments(
        content,
        [
            VisualTreatmentAssignment(
                scene_id="scene_001",
                visual_mode="multi_frame",
                visual_treatment="full_frame",
                visual_layers=[VisualLayer(id="should_clear")],
            )
        ],
    )

    scene = content.all_scenes()[0]
    assert scene.visual_mode == "multi_frame"
    assert scene.media_source == "ai"
    assert scene.visual_treatment == "full_frame"
    assert scene.visual_layers == []


def test_apply_visual_treatment_assignment_accepts_continuous_mode():
    content = content_with_scenes(
        Scene(id="scene_001", narration="The wall slowly cracks.", visual_prompt="A cracking wall")
    )

    apply_visual_treatment_assignments(
        content,
        [
            VisualTreatmentAssignment(
                scene_id="scene_001",
                visual_mode="continuous",
                visual_treatment="full_frame",
                visual_layers=[VisualLayer(id="should_clear")],
            )
        ],
    )

    scene = content.all_scenes()[0]
    assert scene.visual_mode == "continuous"
    assert scene.media_source == "ai"
    assert scene.visual_treatment == "full_frame"
    assert scene.visual_layers == []
```

- [ ] **Step 2: Run focused analyzer tests**

Run:

```bash
uv run --project backend pytest backend/tests/test_visual_treatments.py backend/tests/test_media_source_dispatch.py -v
```

Expected: new tests fail if `_normalize_visual_mode` does not accept the new modes or assignment application leaves layers attached.

- [ ] **Step 3: Update `visual_treatments.py` normalization and routing**

In `apply_visual_treatment_assignments`, keep layers only for layered modes:

```python
        scene.visual_layers = list(assignment.visual_layers) if mode in {"popup_sequence", "flipflop"} else []
```

In `_normalize_visual_mode`, accepting `VISUAL_MODES` after Task 1 is enough:

```python
def _normalize_visual_mode(value: str) -> VisualMode:
    if value in VISUAL_MODES:
        return value  # type: ignore[return-value]
    if value in VISUAL_TREATMENTS:
        return value  # type: ignore[return-value]
    if value in {"quick_cuts", "montage"}:
        return "multi_frame"
    return "full_frame"
```

Add simple progression detection before list/repetition fallback in `_analyze_scene`:

```python
    if scene.visual_mode == "multi_frame" or scene.visual_beat in {"quick_cuts", "montage", "multi_frame"}:
        return VisualTreatmentAssignment(
            scene_id=scene.id,
            visual_mode="multi_frame",
            visual_treatment="full_frame",
            reasoning="Scene is explicitly marked for independent multi-frame rendering.",
            visual_layers=[],
        )

    if scene.visual_mode == "continuous" or scene.visual_beat == "continuous":
        return VisualTreatmentAssignment(
            scene_id=scene.id,
            visual_mode="continuous",
            visual_treatment="full_frame",
            reasoning="Scene is explicitly marked for same-scene progression.",
            visual_layers=[],
        )

    if _looks_like_continuous_progression(scene):
        return VisualTreatmentAssignment(
            scene_id=scene.id,
            visual_mode="continuous",
            visual_treatment="full_frame",
            reasoning="Detected physical process or transformation narration.",
            visual_layers=[],
        )
```

Add helper constants and function:

```python
PROGRESSION_MARKERS = {
    "build",
    "builds",
    "built",
    "crack",
    "cracks",
    "crawl",
    "crawls",
    "expand",
    "expands",
    "grow",
    "grows",
    "pour",
    "pours",
    "spread",
    "spreads",
    "transform",
    "transforms",
}


def _looks_like_continuous_progression(scene: Scene) -> bool:
    words = {_normalize_word(word.word) for word in scene.word_timestamps or []}
    if words & PROGRESSION_MARKERS:
        return True
    text = scene.narration.lower()
    return any(
        phrase in text
        for phrase in (
            "over time",
            "slowly turns",
            "slowly becomes",
            "step by step",
            "piece by piece",
        )
    )
```

Keep the current popup-sequence heuristics for explicit list markers and natural list items in this task. The new `multi_frame` analyzer path is for explicit canonical mode requests and legacy `quick_cuts`/`montage` compatibility; a later tuning pass can decide whether broad list narration should prefer `multi_frame` over `popup_sequence`.

- [ ] **Step 4: Update `media_analyzer.py` canonical mode handling**

Find places that construct `visual_mode` from `media_source`. Ensure any old beat/mode string from LLM or compatibility data is normalized:

```python
def _canonical_visual_mode(value: str, media_source: str = "ai") -> str:
    if media_source == "ai_video":
        return "video"
    if value in {"quick_cuts", "montage", "multi_frame"}:
        return "multi_frame"
    if value == "continuous":
        return "continuous"
    if value in {"video", "full_frame", "popup_sequence", "flipflop"}:
        return value
    return "full_frame"
```

Use `_canonical_visual_mode(...)` in assignment construction and when applying assignments to scenes:

```python
scene.set_visual_mode(_canonical_visual_mode(assignment.visual_mode, assignment.media_source))
```

- [ ] **Step 5: Run analyzer tests**

Run:

```bash
uv run --project backend pytest backend/tests/test_visual_treatments.py backend/tests/test_media_source_dispatch.py -v
```

Expected: analyzer tests pass.

- [ ] **Step 6: Commit Task 6**

Run:

```bash
git add backend/pipeline/visual_treatments.py backend/pipeline/media_analyzer.py backend/tests/test_visual_treatments.py backend/tests/test_media_source_dispatch.py
git commit -m "Route analyzer output to canonical visual modes"
```

## Task 7: Remotion Serialization

**Files:**
- Modify: `backend/tests/pipeline/test_remotion_render.py`
- Modify: `backend/pipeline/remotion_render.py` only if tests reveal missing frame path behavior.

- [ ] **Step 1: Write failing serialization tests**

Append tests to `backend/tests/pipeline/test_remotion_render.py`:

```python
def test_multi_frame_scene_props_include_mode_and_frame_paths(tmp_path, monkeypatch):
    monkeypatch.setattr(remotion_render, "DATA_DIR", tmp_path)
    image_dir = tmp_path / "projects" / "script-1" / "images"
    image_dir.mkdir(parents=True)
    (image_dir / "scene-1_0.png").write_bytes(b"fake image 1")
    (image_dir / "scene-1_1.png").write_bytes(b"fake image 2")
    scene = Scene(
        id="scene-1",
        narration="First this, then that.",
        visual_prompt="Several examples.",
        visual_mode="multi_frame",
        frame_urls=[
            "/static/projects/script-1/images/scene-1_0.png",
            "/static/projects/script-1/images/scene-1_1.png",
        ],
        audio_duration_seconds=4.0,
    )

    props = remotion_render._scene_to_input_props(scene, "script-1")

    assert props["visual_mode"] == "multi_frame"
    assert props["frame_paths"]
    assert len(props["frame_paths"]) == 2


def test_continuous_scene_props_include_mode_and_frame_paths(tmp_path, monkeypatch):
    monkeypatch.setattr(remotion_render, "DATA_DIR", tmp_path)
    image_dir = tmp_path / "projects" / "script-1" / "images"
    image_dir.mkdir(parents=True)
    (image_dir / "scene-1_0.png").write_bytes(b"fake image 1")
    (image_dir / "scene-1_1.png").write_bytes(b"fake image 2")
    scene = Scene(
        id="scene-1",
        narration="The crack spreads.",
        visual_prompt="A spreading crack.",
        visual_mode="continuous",
        frame_urls=[
            "/static/projects/script-1/images/scene-1_0.png",
            "/static/projects/script-1/images/scene-1_1.png",
        ],
        audio_duration_seconds=4.0,
    )

    props = remotion_render._scene_to_input_props(scene, "script-1")

    assert props["visual_mode"] == "continuous"
    assert props["frame_paths"]
    assert len(props["frame_paths"]) == 2
```

- [ ] **Step 2: Run focused serialization tests**

Run:

```bash
uv run --project backend pytest backend/tests/pipeline/test_remotion_render.py -v
```

Expected: tests should pass after Task 1. If they fail, inspect `_scene_frame_paths` and `_scene_to_input_props` and make the smallest compatibility fix.

- [ ] **Step 3: Implement only if needed**

If frame paths are missing because mode normalization cleared frames, fix `backend/models/script.py` as described in Task 1 and rerun Task 1 tests. If `_scene_frame_paths` filters by old beat names, update it to treat `multi_frame` and `continuous` like any other multi-frame scene:

```python
if scene.frame_urls:
    return [_to_remotion_path(path) for path in scene.frame_urls]
```

- [ ] **Step 4: Commit Task 7**

Run:

```bash
git add backend/pipeline/remotion_render.py backend/tests/pipeline/test_remotion_render.py backend/models/script.py
git commit -m "Preserve frame props for multi-frame visual modes"
```

If `backend/pipeline/remotion_render.py` and `backend/models/script.py` did not change in this task, omit them from `git add`.

## Task 8: Project Convention Documentation

**Files:**
- Modify: `AGENTS.md`

- [ ] **Step 1: Update visual mode convention**

In `AGENTS.md`, replace the current visual mode convention bullet:

```text
- **Scene visual mode is canonical**: Scene routing uses one canonical `visual_mode` field with values `video`, `full_frame`, `popup_sequence`, and `flipflop`. Legacy `media_source` and `visual_treatment` fields remain only as compatibility mirrors: `video` maps to `media_source="ai_video"` and `visual_treatment="full_frame"`; all other modes map to `media_source="ai"` and their matching treatment. New backend routing, asset generation, UI controls, tests, and docs should read/write `visual_mode` first.
```

with:

```text
- **Scene visual mode is canonical**: Scene routing uses one canonical `visual_mode` field with values `video`, `full_frame`, `multi_frame`, `continuous`, `popup_sequence`, and `flipflop`. Legacy `media_source` and `visual_treatment` fields remain only as compatibility mirrors: `video` maps to `media_source="ai_video"` and `visual_treatment="full_frame"`; `popup_sequence` and `flipflop` map to matching `visual_treatment` values; `full_frame`, `multi_frame`, and `continuous` map to `media_source="ai"` and `visual_treatment="full_frame"`. New backend routing, asset generation, UI controls, tests, and docs should read/write `visual_mode` first. Legacy `quick_cuts` and `montage` visual beats are compatibility aliases for `multi_frame`; `continuous` is a canonical mode for same-scene progression.
```

Update the layered canvas bullet from:

```text
- **Layered visual modes render over a global static canvas**: Every scene has a video-level `visual_canvas.background_color` beneath it. `full_frame` covers the canvas, while `popup_sequence` and `flipflop` stage their own assets over the canvas. The persisted `visual_treatment` field remains a backward-compatible Remotion mirror, but product logic should treat `visual_mode` as the source of truth. Layered mode analysis requires generated voiceover word timing before assignment (`audio_duration_seconds > 0` and non-empty `word_timestamps` for non-title scenes).
```

with:

```text
- **Layered visual modes render over a global static canvas**: Every scene has a video-level `visual_canvas.background_color` beneath it. `full_frame`, `multi_frame`, `continuous`, and `video` cover the canvas through their normal media paths, while `popup_sequence` and `flipflop` stage their own assets over the canvas. The persisted `visual_treatment` field remains a backward-compatible Remotion mirror for layer treatments, but product logic should treat `visual_mode` as the source of truth. Layered mode analysis requires generated voiceover word timing before assignment (`audio_duration_seconds > 0` and non-empty `word_timestamps` for non-title scenes).
```

Update the "Only `full_frame` generates a normal scene image" bullet so it excludes `multi_frame` and `continuous` from layered asset generation but preserves their frame generation:

```text
- **Only media-backed modes generate normal scene images/frames**: `full_frame` generates a normal scene image, while `multi_frame` and `continuous` generate normal scene frame sequences. Layered modes have their own asset generation and render pipeline. Test Lab, batch image generation, manual visual regeneration, and export image phases must skip/clear `Scene.image_url` and `frame_urls` for `video`, `popup_sequence`, and `flipflop`, then generate only the mode-specific assets (`video_url`, `visual_layers`, popup cutouts, flip-flop panels, etc.).
```

- [ ] **Step 2: Commit Task 8**

Run:

```bash
git add AGENTS.md
git commit -m "Document canonical multi-frame visual modes"
```

## Task 9: Full Verification and Auto-Commit Review Loop

**Files:**
- Verify all modified files.
- No planned source edits unless tests or review findings require them.

- [ ] **Step 1: Run backend tests**

Run:

```bash
uv run --project backend pytest
```

Expected: backend pytest suite passes.

- [ ] **Step 2: Run frontend tests**

Run:

```bash
npm run test:frontend -- --run
```

Expected: frontend Vitest suite passes. If the package script does not accept `-- --run`, run `npm run test:frontend` and confirm it exits successfully.

- [ ] **Step 3: Run frontend production build**

Run:

```bash
cd frontend && npm run build
```

Expected: TypeScript and Vite build succeeds.

- [ ] **Step 4: Inspect git status**

Run:

```bash
git status --short
```

Expected: only intended files are modified or committed. Ignore pre-existing untracked `data/` and any unrelated untracked plan files unless they are part of this implementation.

- [ ] **Step 5: Push main**

Run:

```bash
git push origin main
```

Expected: push succeeds.

- [ ] **Step 6: Dispatch delegated review**

Use Codex's agent delegation tooling with this prompt:

```text
Review the most recent commit on the main branch of this project.
Run `git diff HEAD~1..HEAD` to see the changes and `git show --stat HEAD` for context.
Read the full affected files (not just the diff) to understand surrounding code.
Check for: correctness bugs, error handling gaps, security issues, naive/aware datetime mismatches, unhandled promise rejections, race conditions, and style problems.
Return a structured verdict: either LGTM or NEEDS CHANGES.
If NEEDS CHANGES, provide a numbered list of findings with severity (FAIL/WARN), file:line, and a specific description of what's wrong and how to fix it.
```

Expected: review returns `LGTM` or actionable findings.

- [ ] **Step 7: Apply review findings if needed**

If review returns `NEEDS CHANGES`, implement every FAIL and WARN item, run the relevant focused tests, then commit:

```bash
git add <changed files>
git commit -m "fix: address review findings"
git push origin main
```

Dispatch another delegated review using the same prompt. Repeat until the review verdict is `LGTM`.

- [ ] **Step 8: Final summary**

After review returns `LGTM`, summarize:

- `multi_frame` and `continuous` are canonical visual modes.
- `quick_cuts` and `montage` are compatibility aliases for `multi_frame`.
- Test Lab, prompts, routing, types, docs, and render serialization were updated.
- Note any review findings that were fixed.
