# Renderer-Owned Canvas Context Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add reusable renderer-owned context stages for canvas-revealing visual modes, with flipflop as the first required consumer and no generated flipflop environment backgrounds.

**Architecture:** Add a shared `renderer_context` scene field and backend inference helper, then consume it from Remotion through a reusable `RendererContextStage` component. Flipflop generation should emit only two transparent State A/B cutouts; Remotion draws the context stage behind those cutouts and render fingerprints include a context-stage version.

**Tech Stack:** Python 3.12/FastAPI/Pydantic/SQLModel backend, React 19/TypeScript Remotion renderer, Vitest frontend tests, pytest backend tests.

---

### Task 1: Add Shared Renderer Context Model Contract

**Files:**
- Create: `backend/pipeline/renderer_context.py`
- Modify: `backend/models/script.py`
- Modify: `frontend/src/types/script.ts`
- Modify: `frontend/src/types/testLab.ts`
- Modify: `remotion/src/types.ts`
- Test: `backend/tests/pipeline/test_renderer_context.py`
- Test: `backend/tests/test_visual_mode.py`

- [ ] **Step 1: Write backend renderer context helper tests**

Add `backend/tests/pipeline/test_renderer_context.py`:

```python
from pipeline.renderer_context import (
    RENDERER_CONTEXTS,
    infer_renderer_context,
    normalize_renderer_context,
)


def test_renderer_context_values_are_stable():
    assert RENDERER_CONTEXTS == (
        "plain",
        "desk",
        "classroom",
        "office",
        "kitchen",
        "shop",
        "lab",
        "street",
    )


def test_normalize_renderer_context_accepts_only_allowlist():
    assert normalize_renderer_context("kitchen") == "kitchen"
    assert normalize_renderer_context("Kitchen") == "plain"
    assert normalize_renderer_context("") == "plain"
    assert normalize_renderer_context(None) == "plain"
    assert normalize_renderer_context("space_station") == "plain"


def test_infer_renderer_context_prefers_specific_setting():
    assert infer_renderer_context(
        narration="The fryer is screaming while a customer waits at the register.",
        visual_prompt="Fast food worker at a counter.",
    ) == "kitchen"
    assert infer_renderer_context(
        narration="The teacher points at the whiteboard.",
        visual_prompt="Student in a classroom.",
    ) == "classroom"
    assert infer_renderer_context(
        narration="The spreadsheet has seven fonts.",
        visual_prompt="Office worker with laptop and paperwork.",
    ) == "office"
    assert infer_renderer_context(
        narration="He blinks once.",
        visual_prompt="Human character portrait, no setting.",
    ) == "plain"
```

- [ ] **Step 2: Write Scene model tests**

Add to `backend/tests/test_visual_mode.py`:

```python
def test_scene_accepts_renderer_context():
    scene = Scene(
        id="s1",
        narration="He blinks in the classroom.",
        visual_prompt="Teacher character near a board.",
        visual_mode="flipflop",
        flipflop_action="blink",
        renderer_context="classroom",
    )

    assert scene.renderer_context == "classroom"


def test_scene_normalizes_invalid_renderer_context_to_plain():
    scene = Scene(
        id="s1",
        narration="He blinks.",
        visual_prompt="Teacher character.",
        visual_mode="flipflop",
        flipflop_action="blink",
        renderer_context="unknown",
    )

    assert scene.renderer_context == "plain"
```

- [ ] **Step 3: Run tests to verify failure**

Run:

```bash
npm run test:backend -- backend/tests/pipeline/test_renderer_context.py backend/tests/test_visual_mode.py::test_scene_accepts_renderer_context backend/tests/test_visual_mode.py::test_scene_normalizes_invalid_renderer_context_to_plain
```

Expected: FAIL because `pipeline.renderer_context` and `Scene.renderer_context` do not exist.

- [ ] **Step 4: Implement backend helper and model field**

Create `backend/pipeline/renderer_context.py`:

```python
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
    ("kitchen", ("kitchen", "restaurant", "cooking", "chef", "fryer", "counter", "food service", "burger")),
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
```

Modify `backend/models/script.py`:

```python
from pipeline.renderer_context import RendererContext, normalize_renderer_context

RendererContextValue = RendererContext

class Scene(BaseModel):
    ...
    renderer_context: RendererContextValue | str = "plain"

    @model_validator(mode="before")
    @classmethod
    def normalize_visual_mode_fields(_cls, data: object) -> object:
        ...
        normalized["renderer_context"] = normalize_renderer_context(normalized.get("renderer_context"))
        return normalized

    @field_validator("renderer_context", mode="before")
    @classmethod
    def normalize_renderer_context_value(_cls, value: object) -> str:
        return normalize_renderer_context(value)
```

Do not clear `renderer_context` when switching visual modes; full-bleed renderers ignore it.

- [ ] **Step 5: Add TypeScript fields**

Modify `frontend/src/types/script.ts`:

```ts
export type RendererContext = "plain" | "desk" | "classroom" | "office" | "kitchen" | "shop" | "lab" | "street";

export interface Scene {
  ...
  renderer_context?: RendererContext;
}
```

Modify `frontend/src/types/testLab.ts`:

```ts
import type { FlipflopAction, RendererContext, SceneFX, SubtitleStyle, VisualLayer, VisualMode } from "./script";

export interface TestLabPreset {
  ...
  renderer_context?: RendererContext;
}

export interface TestLabSettings {
  ...
  renderer_context?: RendererContext;
}
```

Modify `remotion/src/types.ts`:

```ts
export type RendererContext = "plain" | "desk" | "classroom" | "office" | "kitchen" | "shop" | "lab" | "street";

export interface SceneInput {
  ...
  renderer_context?: RendererContext;
}
```

- [ ] **Step 6: Run model tests**

Run:

```bash
npm run test:backend -- backend/tests/pipeline/test_renderer_context.py backend/tests/test_visual_mode.py::test_scene_accepts_renderer_context backend/tests/test_visual_mode.py::test_scene_normalizes_invalid_renderer_context_to_plain
```

Expected: PASS.

### Task 2: Normalize Flipflop Context And Remove Generated Background Layers

**Files:**
- Modify: `backend/pipeline/visual_treatments.py`
- Modify: `backend/pipeline/image_gen.py`
- Modify: `backend/pipeline/test_lab.py`
- Test: `backend/tests/test_visual_treatments.py`
- Test: `backend/tests/test_test_lab.py`

- [ ] **Step 1: Update backend tests for two cutout layers**

Update `backend/tests/test_visual_treatments.py` assertions that currently expect flipflop background layers:

```python
def test_explicit_flipflop_layers_use_renderer_context_without_background():
    scene = scene_with_words("s1", "He blinks while the kitchen noise keeps going.")
    scene.visual_prompt = "Young fast-food employee in a red polo, fast-food kitchen context."
    scene.set_visual_mode("flipflop")
    scene.flipflop_action = "blink"
    content = content_with_scenes(scene)

    assignments = analyze_visual_treatments(content, script_id="script-flipflop-context")

    layers = assignments[0].visual_layers
    assert [layer.id for layer in layers] == ["s1_state_a", "s1_state_b"]
    assert [layer.asset_kind for layer in layers] == ["cutout", "cutout"]
    assert content.segments[0].scenes[0].renderer_context == "kitchen"
```

Add or update a generation test:

```python
def test_generate_flipflop_cutouts_generates_only_state_sheet_cutouts(tmp_path, monkeypatch):
    image_gen, _, _ = _stub_panel_image_context(monkeypatch, tmp_path)
    prompts: list[str] = []

    monkeypatch.setattr(image_gen, "save_vault_image", lambda **_kwargs: None)

    def fake_generate_image(prompt, *, width, height, **_kwargs):
        prompts.append(prompt)
        source = tmp_path / f"source-{len(prompts)}.png"
        image = Image.new("RGBA", (120, 100), (0, 255, 0, 255))
        draw = ImageDraw.Draw(image)
        draw.rectangle((20, 20, 50, 60), fill=(255, 0, 0, 255))
        draw.rectangle((80, 20, 110, 60), fill=(255, 0, 0, 255))
        image.save(source)
        return str(source)

    monkeypatch.setattr(image_gen, "generate_image", fake_generate_image)

    layers = image_gen.generate_flipflop_cutouts(
        scene_id="scene_001",
        layers=[
            {"id": "state_a", "type": "image", "asset_kind": "cutout", "prompt": "State A prompt"},
            {"id": "state_b", "type": "image", "asset_kind": "cutout", "prompt": "State B prompt"},
        ],
        script_id="script-1",
        scene_prompt="Person blinks.",
        scene_narration="Person blinks.",
        width=320,
        height=180,
        contains_person=True,
    )

    assert len(prompts) == 1
    assert "two-cell contact sheet" in prompts[0]
    assert [layer["asset_kind"] for layer in layers if layer.get("type") == "image"] == ["cutout", "cutout"]
```

- [ ] **Step 2: Run tests to verify failure**

Run:

```bash
npm run test:backend -- backend/tests/test_visual_treatments.py::test_explicit_flipflop_layers_use_renderer_context_without_background backend/tests/test_visual_treatments.py::test_generate_flipflop_cutouts_generates_only_state_sheet_cutouts
```

Expected: FAIL because `_flipflop_layers` still creates a background and `generate_flipflop_cutouts` still generates it.

- [ ] **Step 3: Update visual treatment assignment**

Modify `backend/pipeline/visual_treatments.py`:

```python
from pipeline.renderer_context import infer_renderer_context, normalize_renderer_context


def _ensure_renderer_context(scene: Scene) -> None:
    context = normalize_renderer_context(scene.renderer_context)
    if context == "plain":
        context = infer_renderer_context(narration=scene.narration, visual_prompt=scene.visual_prompt)
    scene.renderer_context = context


def _flipflop_layers(scene: Scene) -> list[VisualLayer]:
    action = normalize_flipflop_action(scene.flipflop_action)
    _ensure_renderer_context(scene)
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

Call `_ensure_renderer_context(scene)` in explicit and inferred flipflop branches before returning assignments.

- [ ] **Step 4: Update flipflop cutout generation normalization**

Modify `_normalize_flipflop_generation_layers` in `backend/pipeline/image_gen.py` so it drops background/full-frame/panel layers and returns only two cutout layers:

```python
image_layers = [
    dict(layer)
    for layer in layers
    if isinstance(layer, dict) and layer.get("type", "image") == "image"
]
state_layers = [
    layer
    for layer in image_layers
    if layer.get("asset_kind") == "cutout" and not str(layer.get("id") or "").endswith("_background")
]
normalized: list[dict] = []
...
return normalized + other_layers
```

Remove the branch that creates a `{scene_id}_background` layer and remove background prompt/image generation from `generate_flipflop_cutouts`. Keep `_compose_flipflop_background_source_prompt` only until no tests/imports reference it; if unused after this task, delete it and its direct tests.

- [ ] **Step 5: Update Test Lab fallback layers**

Modify `_fallback_visual_layers_for_treatment` in `backend/pipeline/test_lab.py` so flipflop returns only State A/B cutouts and sets `scene.renderer_context` using the helper:

```python
from pipeline.renderer_context import infer_renderer_context, normalize_renderer_context

...
scene.renderer_context = normalize_renderer_context(scene.renderer_context)
if scene.visual_mode == "flipflop" and scene.renderer_context == "plain":
    scene.renderer_context = infer_renderer_context(
        narration=scene.narration,
        visual_prompt=scene.visual_prompt,
    )
return [
    VisualLayer(... state_a ...),
    VisualLayer(... state_b ...),
]
```

- [ ] **Step 6: Run backend visual treatment tests**

Run:

```bash
npm run test:backend -- backend/tests/test_visual_treatments.py backend/tests/test_test_lab.py
```

Expected: PASS.

### Task 3: Add Reusable Remotion RendererContextStage

**Files:**
- Create: `remotion/src/scenes/RendererContextStage.tsx`
- Modify: `remotion/src/scenes/TreatmentRenderer.tsx`
- Modify: `frontend/src/remotion/TreatmentRenderer.test.ts`

- [ ] **Step 1: Write Remotion tests**

Add to `frontend/src/remotion/TreatmentRenderer.test.ts` imports:

```ts
import {
  RENDERER_CONTEXT_STAGE_VERSION,
  rendererContextElements,
  normalizeRendererContext,
} from "@remotion-src/scenes/RendererContextStage";
```

Add tests:

```ts
describe("RendererContextStage", () => {
  it("normalizes unknown contexts to plain", () => {
    expect(normalizeRendererContext("classroom")).toBe("classroom");
    expect(normalizeRendererContext("unknown")).toBe("plain");
    expect(normalizeRendererContext(undefined)).toBe("plain");
  });

  it("defines a stable version for render fingerprints", () => {
    expect(RENDERER_CONTEXT_STAGE_VERSION).toBe("renderer-context-stage-v1");
  });

  it("renders deterministic classroom context shapes", () => {
    const elements = rendererContextElements("classroom");

    expect(elements.some((element) => element.id === "classroom-board")).toBe(true);
    expect(elements.some((element) => element.id === "floor-band")).toBe(true);
  });
});
```

- [ ] **Step 2: Run tests to verify failure**

Run:

```bash
npm run test:frontend -- TreatmentRenderer
```

Expected: FAIL because `RendererContextStage` does not exist.

- [ ] **Step 3: Implement reusable context stage**

Create `remotion/src/scenes/RendererContextStage.tsx`:

```tsx
import React from "react";
import type { RendererContext } from "../types";

export const RENDERER_CONTEXT_STAGE_VERSION = "renderer-context-stage-v1";

const CONTEXTS = new Set(["plain", "desk", "classroom", "office", "kitchen", "shop", "lab", "street"]);

export interface ContextElement {
  id: string;
  style: React.CSSProperties;
}

export const normalizeRendererContext = (value: unknown): RendererContext => (
  typeof value === "string" && CONTEXTS.has(value) ? value as RendererContext : "plain"
);

const baseElements = (): ContextElement[] => [
  { id: "wall-wash", style: { position: "absolute", inset: 0, background: "linear-gradient(180deg, rgba(255,255,255,0.18), rgba(0,0,0,0.08))" } },
  { id: "floor-band", style: { position: "absolute", left: 0, right: 0, bottom: 0, height: 260, background: "rgba(0,0,0,0.14)" } },
];

export const rendererContextElements = (context: unknown): ContextElement[] => {
  const normalized = normalizeRendererContext(context);
  const elements = baseElements();
  if (normalized === "desk" || normalized === "office" || normalized === "classroom") {
    elements.push({ id: "desk-band", style: { position: "absolute", left: 250, right: 250, bottom: 155, height: 88, borderRadius: 18, background: "rgba(88, 60, 36, 0.34)" } });
  }
  if (normalized === "classroom") {
    elements.push({ id: "classroom-board", style: { position: "absolute", left: 560, right: 560, top: 112, height: 235, borderRadius: 10, border: "10px solid rgba(80, 55, 36, 0.5)", background: "rgba(246, 241, 219, 0.62)" } });
  }
  if (normalized === "office") {
    elements.push({ id: "office-window", style: { position: "absolute", right: 360, top: 130, width: 250, height: 220, borderRadius: 8, background: "rgba(160, 200, 215, 0.26)" } });
  }
  if (normalized === "kitchen" || normalized === "shop") {
    elements.push({ id: `${normalized}-counter`, style: { position: "absolute", left: 180, right: 180, bottom: 190, height: 105, borderRadius: 16, background: "rgba(126, 91, 58, 0.38)" } });
  }
  if (normalized === "lab") {
    elements.push({ id: "lab-bench", style: { position: "absolute", left: 220, right: 220, bottom: 180, height: 95, borderRadius: 16, background: "rgba(210, 226, 230, 0.32)" } });
  }
  if (normalized === "street") {
    elements.push({ id: "street-horizon", style: { position: "absolute", left: 0, right: 0, bottom: 260, height: 80, background: "rgba(70, 80, 90, 0.18)" } });
  }
  return elements;
};

export const RendererContextStage: React.FC<{ context?: RendererContext }> = ({ context }) => (
  <div style={{ position: "absolute", inset: 0, overflow: "hidden", pointerEvents: "none" }}>
    {rendererContextElements(context).map((element) => (
      <div key={element.id} style={element.style} />
    ))}
  </div>
);
```

- [ ] **Step 4: Compose stage into flipflop renderer**

Modify `remotion/src/scenes/TreatmentRenderer.tsx`:

```tsx
import { RendererContextStage } from "./RendererContextStage";

...
return (
  <div style={{ position: "absolute", inset: 0 }}>
    <RendererContextStage context={scene.renderer_context} />
    <div style={flipflopLayerFrameStyle(activeLayer)}>
      ...
    </div>
  </div>
);
```

Remove `backgroundLayers` rendering from `Flipflop`; background image layers are no longer part of the forward contract.

- [ ] **Step 5: Run frontend tests**

Run:

```bash
npm run test:frontend -- TreatmentRenderer SceneRenderer
```

Expected: PASS.

### Task 4: Pass Renderer Context Through Remotion And Render Fingerprints

**Files:**
- Modify: `backend/pipeline/remotion_render.py`
- Test: `backend/tests/test_remotion_render.py` or nearest existing Remotion render test file

- [ ] **Step 1: Write render prop/fingerprint tests**

In the existing Remotion render test file, add:

```python
def test_scene_input_props_include_renderer_context():
    scene = Scene(
        id="s1",
        narration="He blinks at the whiteboard.",
        visual_prompt="Teacher character.",
        visual_mode="flipflop",
        flipflop_action="blink",
        renderer_context="classroom",
    )

    props = remotion_render._scene_to_input_props(scene, "script-1", subtitle_style="auto")

    assert props["renderer_context"] == "classroom"


def test_subtitle_render_fingerprint_includes_renderer_context_for_canvas_modes():
    scene = Scene(
        id="s1",
        narration="He blinks at the whiteboard.",
        visual_prompt="Teacher character.",
        visual_mode="flipflop",
        flipflop_action="blink",
        renderer_context="classroom",
    )
    content = ScriptContent(title="T", segments=[Segment(name="S", scenes=[scene])])

    fingerprint = remotion_render.subtitle_render_fingerprint(content)

    assert fingerprint["renderer_context_stage_version"] == "renderer-context-stage-v1"
    assert fingerprint["scenes"][0]["renderer_context"] == "classroom"
```

Use the actual helper name in the test file if `_scene_to_input_props` is named differently.

- [ ] **Step 2: Run tests to verify failure**

Run:

```bash
npm run test:backend -- backend/tests/test_remotion_render.py
```

Expected: FAIL because Remotion props/fingerprints do not include `renderer_context`.

- [ ] **Step 3: Implement prop and fingerprint fields**

Modify `backend/pipeline/remotion_render.py`:

```python
RENDERER_CONTEXT_STAGE_VERSION = "renderer-context-stage-v1"

...
"renderer_context": scene.renderer_context,
...

def subtitle_render_fingerprint(content: ScriptContent) -> dict[str, Any]:
    return {
        "subtitle_router_version": SUBTITLE_ROUTER_VERSION,
        "renderer_context_stage_version": RENDERER_CONTEXT_STAGE_VERSION,
        "settings": subtitle_settings_from_env(),
        "scenes": [
            {
                "id": scene.id,
                "subtitle_style": scene.subtitle_style,
                "visual_mode": scene.visual_mode,
                "renderer_context": scene.renderer_context if scene.visual_mode in {"flipflop", "popup_sequence", "comparison_board", "stat_card", "captions"} else "",
                ...
            }
            for scene in content.all_scenes()
        ],
    }
```

- [ ] **Step 4: Run render tests**

Run:

```bash
npm run test:backend -- backend/tests/test_remotion_render.py
```

Expected: PASS.

### Task 5: Add Test Lab Context Control And Manifest Support

**Files:**
- Modify: `backend/pipeline/test_lab.py`
- Modify: `frontend/src/components/test-lab/TestLabControls.tsx`
- Test: `backend/tests/test_test_lab.py`
- Test: `frontend/src/components/test-lab/TestLabControls.test.tsx`

- [ ] **Step 1: Write Test Lab tests**

Add frontend test:

```tsx
it("shows renderer context selector for flipflop", () => {
  renderControls({ ...baseSettings, visual_mode: "flipflop", renderer_context: "classroom" });

  expect(screen.getByLabelText("Scene context")).toHaveValue("classroom");
});

it("preserves scene text when changing renderer context", () => {
  const onChange = vi.fn();
  render(
    <TestLabControls
      settings={{ ...baseSettings, visual_mode: "flipflop", renderer_context: "desk" }}
      scenes={baseScenes}
      onChange={onChange}
    />,
  );

  fireEvent.change(screen.getByLabelText("Scene context"), { target: { value: "office" } });

  expect(onChange).toHaveBeenCalledWith(expect.objectContaining({
    renderer_context: "office",
    narration: baseSettings.narration,
    visual_prompt: baseSettings.visual_prompt,
  }));
});
```

Add backend Test Lab manifest assertion:

```python
def test_test_lab_manifest_includes_renderer_context(...):
    ...
    assert manifest["settings"]["renderer_context"] == "classroom"
    assert manifest["scene"]["renderer_context"] == "classroom"
```

- [ ] **Step 2: Run tests to verify failure**

Run:

```bash
npm run test:frontend -- TestLabControls
npm run test:backend -- backend/tests/test_test_lab.py
```

Expected: FAIL because the selector and manifest field do not exist.

- [ ] **Step 3: Add frontend selector**

Modify `frontend/src/components/test-lab/TestLabControls.tsx`:

```tsx
const RENDERER_CONTEXT_OPTIONS = [
  { value: "plain", label: "Plain" },
  { value: "desk", label: "Desk" },
  { value: "classroom", label: "Classroom" },
  { value: "office", label: "Office" },
  { value: "kitchen", label: "Kitchen" },
  { value: "shop", label: "Shop" },
  { value: "lab", label: "Lab" },
  { value: "street", label: "Street" },
] as const;
```

Inside the flipflop controls:

```tsx
<label className="block">
  <span className="text-xs font-medium text-neutral-300">Scene context</span>
  <select
    aria-label="Scene context"
    value={rendererContext || "plain"}
    onChange={(event) => onRendererContextChange(event.target.value as RendererContext)}
    className="mt-2 w-full rounded-md border border-neutral-800 bg-neutral-950/80 px-3 py-2 text-sm text-neutral-100 outline-none transition-colors hover:border-neutral-700 focus:border-violet-500"
  >
    {RENDERER_CONTEXT_OPTIONS.map((option) => (
      <option key={option.value} value={option.value}>{option.label}</option>
    ))}
  </select>
</label>
```

Wire `renderer_context` through settings updates without touching text fields.

- [ ] **Step 4: Add backend Test Lab persistence**

Modify `backend/pipeline/test_lab.py` so settings and scene data include `renderer_context`:

```python
scene.renderer_context = normalize_renderer_context(settings.get("renderer_context") or scene.renderer_context)
...
"renderer_context": scene.renderer_context,
```

Include `renderer_context` in run manifests and response settings.

- [ ] **Step 5: Run Test Lab tests**

Run:

```bash
npm run test:frontend -- TestLabControls
npm run test:backend -- backend/tests/test_test_lab.py
```

Expected: PASS.

### Task 6: Update In-App Docs And Catalog

**Files:**
- Modify: `frontend/src/components/docs/VisualAssetOwnershipDocSection.tsx`
- Modify: `frontend/src/components/docs/RenderCacheDocSection.tsx`
- Modify: `frontend/src/components/settings/visual-modes/catalog.ts`
- Test: `frontend/src/components/docs/DocsPage.test.tsx`

- [ ] **Step 1: Update docs text**

Update flipflop catalog text to say:

```ts
longDescription:
  "Two transparent human/character state cutouts cropped from a shared A/B sheet alternate over a renderer-owned context stage. Scenes must carry flipflop_action and a normalized renderer_context. Invalid, object-only, or non-human requests downgrade to full_frame.",
```

Update asset ownership docs so flipflop asset ownership says:

```ts
asset: "Two registered transparent state cutouts plus renderer_context metadata"
renderer: "Draws the shared context stage and alternates only the A/B cutouts from frame zero."
```

Update render cache docs so context-stage version and `renderer_context` are named as render-invalidating inputs for canvas-revealing modes.

- [ ] **Step 2: Run docs tests**

Run:

```bash
npm run test:frontend -- DocsPage
```

Expected: PASS.

### Task 7: Final Verification And Commit

**Files:**
- All files changed above.

- [ ] **Step 1: Run targeted backend tests**

Run:

```bash
npm run test:backend -- backend/tests/pipeline/test_renderer_context.py backend/tests/test_visual_mode.py backend/tests/test_visual_treatments.py backend/tests/test_test_lab.py backend/tests/test_remotion_render.py
```

Expected: PASS.

- [ ] **Step 2: Run targeted frontend tests**

Run:

```bash
npm run test:frontend -- TreatmentRenderer SceneRenderer TestLabControls DocsPage
```

Expected: PASS.

- [ ] **Step 3: Run broader checks**

Run:

```bash
npm run test:frontend
npm run test:backend
```

Expected: PASS.

- [ ] **Step 4: Inspect working tree**

Run:

```bash
git status --short
git diff --stat
```

Expected: only renderer-context implementation files are changed.

- [ ] **Step 5: Commit implementation**

Run:

```bash
git add backend frontend remotion docs AGENTS.md
git commit -m "Add renderer-owned context stages"
```

Expected: commit succeeds.

## Self-Review Notes

- Spec coverage: the plan covers the shared `renderer_context` field, flipflop as first consumer, no generated flipflop backgrounds, reusable Remotion stage, Test Lab support, cache fingerprinting, docs, and tests.
- Intentional gap: blink/state jump remains follow-up work. This plan keeps the existing bbox registration but does not add landmark or alpha-anchor alignment.
- Type consistency: all new cross-layer names use `renderer_context`, `RendererContext`, `RendererContextStage`, and `RENDERER_CONTEXT_STAGE_VERSION`.
