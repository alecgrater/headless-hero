# Standard Subtitle Routing Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add scene-level standard subtitle treatments (`auto`, `clean`, `kinetic`, `burst`, `none`) with deterministic auto-routing, Test Lab control, and caption-scene suppression preserved.

**Architecture:** Store an optional `subtitle_style` on backend/frontend/Remotion scene models, pass it through Test Lab and Remotion props, and move subtitle rendering behind a small Remotion router. The router receives full scene metadata, resolves `auto` locally, and delegates to focused treatment renderers that share phrase grouping and hyphen display formatting.

**Tech Stack:** Python 3.12/Pydantic/pytest backend, React 19/TypeScript/Vitest frontend, Remotion 4 renderer.

---

## File Structure

- Modify `backend/models/script.py`: add subtitle style constants, Literal, field, and validator.
- Modify `backend/pipeline/remotion_render.py`: pass `subtitle_style` into Remotion scene props.
- Modify `backend/pipeline/test_lab.py`: preserve subtitle style from Test Lab settings into hidden scene content.
- Modify `backend/tests/pipeline/test_remotion_render.py`: assert Remotion props include valid/default subtitle style.
- Modify `backend/tests/test_test_lab.py`: assert Test Lab settings can force subtitle style.
- Modify `remotion/src/types.ts`: add `SubtitleStyle` and `SceneInput.subtitle_style`.
- Create `remotion/src/effects/typography/subtitleRouting.ts`: pure routing, phrase grouping, and active word helpers.
- Modify `remotion/src/effects/typography/Subtitles.tsx`: accept `scene`, resolve treatment, render clean/kinetic/burst/none.
- Create `frontend/src/remotion/SubtitleRouting.test.ts`: router unit coverage.
- Modify `remotion/src/scenes/SceneRenderer.tsx`: pass the whole scene to `SubtitleOverlay`.
- Modify `frontend/src/types/script.ts` and `frontend/src/types/testLab.ts`: expose `SubtitleStyle`.
- Modify `frontend/src/components/test-lab/TestLabPage.tsx`: default `subtitle_style` to `auto`.
- Modify `frontend/src/components/test-lab/TestLabControls.tsx`: add compact subtitle style selector near subtitle highlight.
- Modify `frontend/src/components/test-lab/TestLabControls.test.ts`: assert Test Lab settings preserve subtitle style.

## Tasks

### Task 1: Backend Data Pass-Through

**Files:**
- Modify: `backend/models/script.py`
- Modify: `backend/pipeline/remotion_render.py`
- Modify: `backend/pipeline/test_lab.py`
- Test: `backend/tests/pipeline/test_remotion_render.py`
- Test: `backend/tests/test_test_lab.py`

- [ ] **Step 1: Write failing backend tests**

Add one test in `backend/tests/pipeline/test_remotion_render.py`:

```python
def test_scene_to_input_props_includes_subtitle_style(tmp_path, monkeypatch):
    monkeypatch.setattr(remotion_render, "DATA_DIR", tmp_path)
    scene = Scene(
        id="scene_subtitle_style",
        narration="Fast words hit hard.",
        visual_prompt="A stylized brain lighting up.",
        subtitle_style="kinetic",
        word_timestamps=[WordTimestamp(word="Fast", start_ms=0, end_ms=200)],
    )

    props = remotion_render._scene_to_input_props(scene, "script")

    assert props["subtitle_style"] == "kinetic"
```

Add one test in `backend/tests/test_test_lab.py` near other `build_content_from_preset` tests:

```python
def test_test_lab_settings_preserve_subtitle_style():
    content = build_content_from_preset("coffee-brain", {"subtitle_style": "burst"})

    scene = content.segments[0].scenes[0]

    assert scene.subtitle_style == "burst"
```

- [ ] **Step 2: Verify RED**

Run:

```bash
uv run --project backend pytest backend/tests/pipeline/test_remotion_render.py::test_scene_to_input_props_includes_subtitle_style backend/tests/test_test_lab.py::test_test_lab_settings_preserve_subtitle_style -q
```

Expected: fail because `Scene` does not accept/pass `subtitle_style`.

- [ ] **Step 3: Implement backend pass-through**

In `backend/models/script.py`, add:

```python
SUBTITLE_STYLES = {"auto", "clean", "kinetic", "burst", "none"}
SubtitleStyle = Literal["auto", "clean", "kinetic", "burst", "none"]
```

Add to `Scene`:

```python
subtitle_style: SubtitleStyle = "auto"
```

Add a validator:

```python
@field_validator("subtitle_style", mode="before")
@classmethod
def normalize_subtitle_style(_cls, value: object) -> str:
    return value if isinstance(value, str) and value in SUBTITLE_STYLES else "auto"
```

In `_scene_to_input_props`, include:

```python
"subtitle_style": scene.subtitle_style,
```

In `build_content_from_preset`, pass:

```python
subtitle_style=_subtitle_style_from_settings(settings),
```

with helper:

```python
def _subtitle_style_from_settings(settings: dict) -> str:
    value = settings.get("subtitle_style")
    return value if isinstance(value, str) and value in SUBTITLE_STYLES else "auto"
```

- [ ] **Step 4: Verify GREEN**

Run the same `uv run --project backend pytest ... -q` command. Expected: pass.

### Task 2: Remotion Subtitle Router And Treatments

**Files:**
- Modify: `remotion/src/types.ts`
- Create: `remotion/src/effects/typography/subtitleRouting.ts`
- Modify: `remotion/src/effects/typography/Subtitles.tsx`
- Modify: `remotion/src/scenes/SceneRenderer.tsx`
- Test: `frontend/src/remotion/SubtitleRouting.test.ts`

- [ ] **Step 1: Write failing router tests**

Create `frontend/src/remotion/SubtitleRouting.test.ts`:

```ts
import { describe, expect, it } from "vitest";

import { resolveSubtitleStyle } from "@remotion-src/effects/typography/subtitleRouting";
import type { SceneInput } from "@remotion-src/types";

const scene = (overrides: Partial<SceneInput>): SceneInput => ({
  id: "scene",
  narration: "This is a normal explanatory sentence.",
  duration_seconds: 6,
  is_title_card: false,
  visual_mode: "full_frame",
  word_timestamps: [
    { word: "This", start_ms: 0, end_ms: 500 },
    { word: "works", start_ms: 500, end_ms: 1000 },
  ],
  ...overrides,
});

describe("resolveSubtitleStyle", () => {
  it("honors explicit subtitle style overrides", () => {
    expect(resolveSubtitleStyle(scene({ subtitle_style: "kinetic" }), "horizontal")).toBe("kinetic");
  });

  it("suppresses captions visual mode and title cards", () => {
    expect(resolveSubtitleStyle(scene({ visual_mode: "captions" }), "horizontal")).toBe("none");
    expect(resolveSubtitleStyle(scene({ is_title_card: true }), "horizontal")).toBe("none");
  });

  it("routes fast dense word timing to kinetic", () => {
    expect(resolveSubtitleStyle(scene({
      narration: "One two three four five six seven eight.",
      word_timestamps: [
        { word: "One", start_ms: 0, end_ms: 120 },
        { word: "two", start_ms: 130, end_ms: 250 },
        { word: "three", start_ms: 260, end_ms: 380 },
        { word: "four", start_ms: 390, end_ms: 510 },
        { word: "five", start_ms: 520, end_ms: 640 },
        { word: "six", start_ms: 650, end_ms: 770 },
      ],
    }), "horizontal")).toBe("kinetic");
  });

  it("routes reveal language to burst", () => {
    expect(resolveSubtitleStyle(scene({ narration: "But then the real reason appears." }), "horizontal")).toBe("burst");
  });

  it("falls back to clean when uncertain", () => {
    expect(resolveSubtitleStyle(scene({}), "horizontal")).toBe("clean");
  });
});
```

- [ ] **Step 2: Verify RED**

Run:

```bash
npm run test:frontend -- frontend/src/remotion/SubtitleRouting.test.ts
```

Expected: fail because `subtitleRouting` and `subtitle_style` are missing.

- [ ] **Step 3: Implement router and treatments**

Add `SubtitleStyle` to `remotion/src/types.ts` and `subtitle_style?: SubtitleStyle`.

Create pure helpers in `subtitleRouting.ts`:

```ts
export const SUBTITLE_ROUTER_VERSION = "standard-subtitle-router-v1";
export type ResolvedSubtitleStyle = "clean" | "kinetic" | "burst" | "none";
export function resolveSubtitleStyle(scene: SceneInput, orientation: Orientation): ResolvedSubtitleStyle { ... }
export function groupIntoSubtitlePhrases(timestamps: WordTimestamp[], fps: number): SubtitlePhrase[] { ... }
```

Move phrase grouping from `Subtitles.tsx` into the helper file.

Update `SubtitleOverlay` props to:

```ts
interface Props {
  scene: SceneInput;
  highlightEnabled?: boolean;
  orientation?: Orientation;
}
```

Render `CleanSubtitleOverlay`, `KineticSubtitleOverlay`, or `BurstSubtitleOverlay` from the resolved style. Each renderer must call `formatSubtitleText` for every visible word.

Update `SceneRenderer`:

```tsx
<SubtitleOverlay scene={scene} highlightEnabled={highlightEnabled} orientation={orientation} />
```

- [ ] **Step 4: Verify GREEN**

Run:

```bash
npm run test:frontend -- frontend/src/remotion/SubtitleRouting.test.ts frontend/src/remotion/SceneRenderer.test.ts
```

Expected: pass.

### Task 3: Test Lab Subtitle Style Control

**Files:**
- Modify: `frontend/src/types/script.ts`
- Modify: `frontend/src/types/testLab.ts`
- Modify: `frontend/src/components/test-lab/TestLabPage.tsx`
- Modify: `frontend/src/components/test-lab/TestLabControls.tsx`
- Test: `frontend/src/components/test-lab/TestLabControls.test.ts`

- [ ] **Step 1: Write failing frontend Test Lab test**

Add to `TestLabControls.test.ts`:

```ts
it("preserves subtitle style when applying visual treatment defaults", () => {
  const settings: TestLabSettings = {
    stages: {
      character: false,
      audio: true,
      visual: true,
      treatment_assets: false,
      fx: true,
      eli: false,
      render: true,
    },
    eli_enabled: false,
    style_preset_enabled: true,
    visual_mode: "full_frame",
    visual_layers: [],
    subtitle_style: "burst",
    segment_timer_enabled: true,
    subtitle_highlight_enabled: true,
  };

  const next = settingsWithVisualTreatmentDefaults(settings, preset, "multi_frame", defaults);

  expect(next.subtitle_style).toBe("burst");
});
```

- [ ] **Step 2: Verify RED**

Run:

```bash
npm run test:frontend -- frontend/src/components/test-lab/TestLabControls.test.ts
```

Expected: fail because `subtitle_style` is not typed.

- [ ] **Step 3: Implement Test Lab control**

Add `SubtitleStyle` to `frontend/src/types/script.ts` and `subtitle_style?: SubtitleStyle` to `Scene`.

Add `subtitle_style: SubtitleStyle` to `TestLabSettings`, default it to `"auto"` in `TestLabPage.tsx`, and add a compact selector in `TestLabControls.tsx` near `Subtitle highlight` with options Auto/Clean/Kinetic/Burst/None.

- [ ] **Step 4: Verify GREEN**

Run:

```bash
npm run test:frontend -- frontend/src/components/test-lab/TestLabControls.test.ts
```

Expected: pass.

### Task 4: Verification, Commit, Push, Review Loop

**Files:**
- All modified files from Tasks 1-3.

- [ ] **Step 1: Run focused verification**

Run:

```bash
uv run --project backend pytest backend/tests/pipeline/test_remotion_render.py backend/tests/test_test_lab.py -q
npm run test:frontend -- frontend/src/remotion/SubtitleRouting.test.ts frontend/src/remotion/SceneRenderer.test.ts frontend/src/components/test-lab/TestLabControls.test.ts
```

Expected: pass.

- [ ] **Step 2: Run broader frontend build or tests if touched types affect app**

Run:

```bash
npm run test:frontend
```

Expected: pass.

- [ ] **Step 3: Commit and push**

Stage only implementation files and this plan:

```bash
git add backend/models/script.py backend/pipeline/remotion_render.py backend/pipeline/test_lab.py backend/tests/pipeline/test_remotion_render.py backend/tests/test_test_lab.py remotion/src/types.ts remotion/src/effects/typography/subtitleRouting.ts remotion/src/effects/typography/Subtitles.tsx remotion/src/scenes/SceneRenderer.tsx frontend/src/remotion/SubtitleRouting.test.ts frontend/src/types/script.ts frontend/src/types/testLab.ts frontend/src/components/test-lab/TestLabPage.tsx frontend/src/components/test-lab/TestLabControls.tsx frontend/src/components/test-lab/TestLabControls.test.ts docs/superpowers/plans/2026-05-29-standard-subtitle-routing.md
git commit -m "Add scene-level subtitle style routing"
git push origin main
```

- [ ] **Step 4: Delegated review loop**

Dispatch a review of the most recent commit. If review returns NEEDS CHANGES, fix all FAIL/WARN items, commit as `Fix subtitle routing review findings`, push, and repeat until LGTM.
