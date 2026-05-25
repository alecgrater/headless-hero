# Captions Visual Mode Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a canonical `captions` visual mode for word-synced editorial text beats with red emphasis, optional side imagery, subtitle suppression, Timeline controls, Test Lab support, and scriptwriter prompt support without adding a required project-generation LLM call.

**Architecture:** Treat `captions` as a first-class `visual_mode` mirrored to `media_source="ai"` and `visual_treatment="full_frame"`. Add lightweight scene fields (`caption_text`, `caption_emphasis`) and a Remotion `CaptionScene` renderer that owns layout, typography, word reveal, fallback timing, and subtitle suppression. Keep image generation optional: generate one normal scene image when `visual_prompt` is present, and render text-centered over the canvas when it is empty.

**Tech Stack:** Python 3.12, Pydantic/SQLModel, FastAPI pipeline modules, pytest through `uv`, React 19, TypeScript, Tailwind 4, Vitest, Remotion 4.

---

## File Map

- Modify `backend/models/script.py`
  - Add `captions` to `VISUAL_MODES` and `VisualMode`.
  - Add `caption_text` and `caption_emphasis` to `Scene`.
  - Normalize `visual_beat="captions"` into `visual_mode="captions"`.
  - Preserve `image_url` and `frame_urls` for captions.
- Modify `backend/tests/test_visual_mode.py`
  - Cover explicit captions mode, legacy beat derivation, assignment sync, caption fields, and non-clearing behavior.
- Modify `frontend/src/types/script.ts`
  - Add `captions` to `VisualMode` and `Scene.visual_beat`.
  - Add `caption_text` and `caption_emphasis`.
- Modify `frontend/src/types/testLab.ts`
  - Add captions to Test Lab unions through the shared `VisualMode` type and add caption fields to settings/presets.
- Modify `remotion/src/types.ts`
  - Add captions to `VisualMode` and `SceneInput.visual_beat`.
  - Add `caption_text` and `caption_emphasis`.
- Create `remotion/src/utils/captionText.ts`
  - Normalize caption words, derive display text, derive emphasis fallback, and split words into emphasized ranges.
- Create `remotion/src/scenes/CaptionScene.tsx`
  - Render the static-canvas caption layout and word-synced animation.
- Modify `remotion/src/scenes/SceneRenderer.tsx`
  - Dispatch captions scenes to `CaptionScene`.
  - Suppress normal `SubtitleOverlay`, camera drift, zoom punch, vertical band layout, and Eli overlay for captions.
- Create `frontend/src/remotion/CaptionScene.test.ts`
  - Unit-test caption text utilities and renderer helper behavior.
- Modify `backend/pipeline/image_gen.py`
  - Skip image generation for text-only captions with empty `visual_prompt`.
  - Keep normal single-image generation for captions with a prompt.
  - Never route captions through popup/flip-flop visual layers.
- Modify `backend/tests/test_visual_treatments.py`
  - Cover captions preservation in visual treatment analysis and explicit captions assignments.
- Modify `backend/pipeline/visual_treatments.py`
  - Preserve explicit captions mode and do not overwrite caption fields.
- Modify `backend/pipeline/test_lab.py`
  - Add captions Test Lab defaults and preset/settings fields.
  - Keep treatment assets disabled for captions.
- Modify `backend/tests/test_test_lab.py`
  - Verify captions settings persist and do not enable treatment assets.
- Modify `frontend/src/components/timeline/PropertiesPanel.tsx`
  - Add Captions to visual mode picker.
  - Show Caption text and Red emphasis controls when selected.
- Modify `frontend/src/components/test-lab/TestLabControls.tsx`
  - Add Captions option, helper copy, defaults, and treatment asset disabled behavior.
- Modify `frontend/src/components/timeline/TimelineBlock.tsx`
- Modify `frontend/src/components/timeline/TimelinePage.tsx`
  - Add captions color/label to mode badges and visual mode mix.
- Modify `backend/prompts/script.py`
  - Add captions mode instructions and output schema fields.
  - Keep `life-as-a` captions disabled in the first pass.
- Modify `backend/tests/pipeline/test_scriptwriter_visual_beats.py`
- Modify `backend/tests/test_prompts.py`
  - Verify prompt vocabulary includes captions and does not ask for renderer-owned styling detail.
- Modify `AGENTS.md`
  - Add the project convention for captions visual mode.

## Task 1: Backend Scene Model

**Files:**
- Modify: `backend/models/script.py`
- Test: `backend/tests/test_visual_mode.py`

- [ ] **Step 1: Write failing model tests**

Append these tests to `backend/tests/test_visual_mode.py`:

```python
def test_scene_accepts_explicit_captions_visual_mode():
    scene = Scene(
        id="scene_001",
        narration="Spending big in one area while falling behind in another.",
        visual_prompt="[REACTION] A worried cartoon shopper holding a receipt.",
        visual_mode="captions",
        caption_text="Spending big while falling behind",
        caption_emphasis="falling behind",
        image_url="/static/projects/script/images/scene_001.png",
        frame_urls=["/static/projects/script/images/scene_001_0.png"],
    )

    assert scene.visual_mode == "captions"
    assert scene.visual_beat == "captions"
    assert scene.media_source == "ai"
    assert scene.visual_treatment == "full_frame"
    assert scene.caption_text == "Spending big while falling behind"
    assert scene.caption_emphasis == "falling behind"
    assert scene.image_url == "/static/projects/script/images/scene_001.png"
    assert scene.frame_urls == ["/static/projects/script/images/scene_001_0.png"]


def test_scene_derives_captions_from_legacy_visual_beat():
    scene = Scene(
        id="scene_001",
        narration="This was the real cost.",
        visual_prompt="",
        visual_beat="captions",
        caption_text="The real cost",
        caption_emphasis="real",
    )

    assert scene.visual_mode == "captions"
    assert scene.visual_beat == "captions"
    assert scene.media_source == "ai"
    assert scene.visual_treatment == "full_frame"


def test_scene_assignment_syncs_captions_visual_mode_without_clearing_media():
    scene = Scene(
        id="scene_001",
        narration="You were never behind.",
        visual_prompt="[CLOSE-UP] A character staring at a calendar.",
        image_url="/static/projects/script/images/scene_001.png",
        frame_urls=["/static/projects/script/images/scene_001_0.png"],
    )

    scene.visual_mode = "captions"

    assert scene.visual_mode == "captions"
    assert scene.visual_beat == "captions"
    assert scene.media_source == "ai"
    assert scene.visual_treatment == "full_frame"
    assert scene.image_url == "/static/projects/script/images/scene_001.png"
    assert scene.frame_urls == ["/static/projects/script/images/scene_001_0.png"]
```

- [ ] **Step 2: Run the focused failing tests**

Run:

```bash
uv run --project backend pytest backend/tests/test_visual_mode.py -v
```

Expected: the new tests fail because `captions`, `caption_text`, and `caption_emphasis` do not exist yet.

- [ ] **Step 3: Update `backend/models/script.py` constants and types**

Change the visual mode constants near the top to:

```python
VISUAL_MODES = {"video", "full_frame", "multi_frame", "continuous", "popup_sequence", "flipflop", "captions"}
VISUAL_TREATMENTS = {"full_frame", "popup_sequence", "flipflop"}
VISUAL_LAYER_TYPES = {"image"}
VISUAL_ASSET_KINDS = {"full_frame", "panel", "cutout"}
VISUAL_LAYER_ANIMATIONS = {"none", "pop_in"}
VisualMode = Literal["video", "full_frame", "multi_frame", "continuous", "popup_sequence", "flipflop", "captions"]
VisualTreatment = Literal["full_frame", "popup_sequence", "flipflop"]
```

- [ ] **Step 4: Add caption fields to `Scene`**

In `class Scene`, after `visual_layers`, add:

```python
    caption_text: str = ""
    caption_emphasis: str = ""
```

- [ ] **Step 5: Update normalization and sync logic**

In `normalize_visual_mode_fields`, keep the clear-frames guard as:

```python
        if mode in {"video", "popup_sequence", "flipflop"}:
            normalized["frame_urls"] = []
```

In `_sync_visual_mode_fields_from_assignment`, include captions wherever multi-frame/continuous modes are preserved:

```python
            elif self.visual_mode in {"multi_frame", "continuous", "popup_sequence", "flipflop", "captions"}:
                mode = self.visual_mode
```

and:

```python
            elif self.visual_mode in {"multi_frame", "continuous", "video", "captions"}:
                mode = self.visual_mode
```

For the `visual_beat` assignment branch, preserve captions as a canonical mode:

```python
            if self.visual_mode in {"video", "popup_sequence", "flipflop", "captions"}:
                mode = self.visual_mode
            else:
                mode = _resolve_visual_mode(None, None, None, self.visual_beat)
```

In `_sync_visual_mode_fields`, set the compatibility beat:

```python
        if visual_mode == "full_frame":
            super().__setattr__("visual_beat", "static")
        elif visual_mode in {"multi_frame", "continuous", "captions"}:
            super().__setattr__("visual_beat", visual_mode)
```

Keep frame clearing limited to:

```python
        if visual_mode in {"video", "popup_sequence", "flipflop"}:
            super().__setattr__("frame_urls", [])
```

In `_resolve_visual_mode`, add:

```python
    if visual_beat == "captions":
        return "captions"
```

In `_legacy_fields_for_visual_mode`, keep captions on the normal AI/full-frame mirror:

```python
    if visual_mode == "video":
        return "ai_video", "full_frame"
    if visual_mode in {"popup_sequence", "flipflop"}:
        return "ai", visual_mode
    return "ai", "full_frame"
```

- [ ] **Step 6: Run the model tests**

Run:

```bash
uv run --project backend pytest backend/tests/test_visual_mode.py -v
```

Expected: all tests in `backend/tests/test_visual_mode.py` pass.

- [ ] **Step 7: Commit**

```bash
git add backend/models/script.py backend/tests/test_visual_mode.py
git commit -m "Add captions scene model support"
```

## Task 2: Shared TypeScript Types

**Files:**
- Modify: `frontend/src/types/script.ts`
- Modify: `frontend/src/types/testLab.ts`
- Modify: `remotion/src/types.ts`

- [ ] **Step 1: Update frontend script types**

In `frontend/src/types/script.ts`, change `VisualMode` to:

```ts
export type VisualMode = "video" | "full_frame" | "multi_frame" | "continuous" | "popup_sequence" | "flipflop" | "captions";
```

Change `Scene.visual_beat` to:

```ts
  visual_beat?: "static" | "continuous" | "multi_frame" | "quick_cuts" | "aha_subtitle" | "montage" | "captions";
```

Add these fields near `visual_layers`:

```ts
  caption_text?: string;
  caption_emphasis?: string;
```

- [ ] **Step 2: Update Remotion input types**

In `remotion/src/types.ts`, change `VisualMode` to:

```ts
export type VisualMode = "video" | "full_frame" | "multi_frame" | "continuous" | "popup_sequence" | "flipflop" | "captions";
```

Change `SceneInput.visual_beat` to:

```ts
  visual_beat?: "static" | "continuous" | "multi_frame" | "quick_cuts" | "aha_subtitle" | "montage" | "captions";
```

Add these fields near `visual_layers`:

```ts
  caption_text?: string | null;
  caption_emphasis?: string | null;
```

- [ ] **Step 3: Update Test Lab types**

In `frontend/src/types/testLab.ts`, add optional caption fields to `TestLabPreset`:

```ts
  caption_text?: string;
  caption_emphasis?: string;
```

Add optional caption fields to `TestLabSettings`:

```ts
  caption_text?: string;
  caption_emphasis?: string;
```

- [ ] **Step 4: Run TypeScript checks through frontend tests**

Run:

```bash
npm run test:frontend -- --run
```

Expected: existing frontend tests still pass, or fail only because runtime behavior has not been implemented in later tasks. If this command is not supported by the repo, run:

```bash
cd frontend && npm run test -- --run
```

- [ ] **Step 5: Commit**

```bash
git add frontend/src/types/script.ts frontend/src/types/testLab.ts remotion/src/types.ts
git commit -m "Add captions TypeScript types"
```

## Task 3: Remotion Caption Utilities And Renderer

**Files:**
- Create: `remotion/src/utils/captionText.ts`
- Create: `remotion/src/scenes/CaptionScene.tsx`
- Modify: `remotion/src/scenes/SceneRenderer.tsx`
- Test: `frontend/src/remotion/CaptionScene.test.ts`

- [ ] **Step 1: Write failing utility tests**

Create `frontend/src/remotion/CaptionScene.test.ts` with:

```ts
import { describe, expect, it } from "vitest";

import {
  chooseCaptionEmphasis,
  splitCaptionWords,
  captionWordsForDisplay,
} from "@remotion-src/utils/captionText";

describe("captionText utilities", () => {
  it("uses caption text before narration and strips subtitle hyphens for display", () => {
    const words = captionWordsForDisplay({
      captionText: "You were never-behind",
      narration: "Fallback narration",
    });

    expect(words).toEqual(["You", "were", "neverbehind"]);
  });

  it("falls back to narration when caption text is empty", () => {
    const words = captionWordsForDisplay({
      captionText: "",
      narration: "The real cost",
    });

    expect(words).toEqual(["The", "real", "cost"]);
  });

  it("chooses explicit emphasis when it matches the caption", () => {
    expect(chooseCaptionEmphasis("Spending big while falling behind", "falling behind")).toBe("falling behind");
  });

  it("falls back to the final content phrase when emphasis is missing", () => {
    expect(chooseCaptionEmphasis("This is the real cost", "")).toBe("real cost");
  });

  it("marks multi-word emphasis ranges", () => {
    const result = splitCaptionWords("Spending big while falling behind", "falling behind");

    expect(result.map((word) => [word.text, word.emphasized])).toEqual([
      ["Spending", false],
      ["big", false],
      ["while", false],
      ["falling", true],
      ["behind", true],
    ]);
  });
});
```

- [ ] **Step 2: Run failing frontend test**

Run:

```bash
npm run test:frontend -- --run frontend/src/remotion/CaptionScene.test.ts
```

Expected: FAIL because `@remotion-src/utils/captionText` does not exist.

- [ ] **Step 3: Create `remotion/src/utils/captionText.ts`**

Add:

```ts
import { formatSubtitleText } from "./subtitleText";

const STOPWORDS = new Set(["a", "an", "and", "as", "at", "but", "for", "in", "is", "it", "of", "on", "or", "the", "to", "was", "were"]);

export interface CaptionWord {
  text: string;
  emphasized: boolean;
}

export function normalizeCaptionToken(value: string): string {
  return formatSubtitleText(value).toLowerCase().replace(/[^a-z0-9]/g, "");
}

export function captionWordsForDisplay({
  captionText,
  narration,
}: {
  captionText?: string | null;
  narration: string;
}): string[] {
  const text = (captionText?.trim() || narration.trim()).replace(/\s+/g, " ");
  if (!text) return [];
  return text.split(/\s+/).map(formatSubtitleText).filter(Boolean);
}

export function chooseCaptionEmphasis(captionText: string, captionEmphasis?: string | null): string {
  const explicit = captionEmphasis?.trim() ?? "";
  const normalizedCaption = captionText.toLowerCase();
  if (explicit && normalizedCaption.includes(explicit.toLowerCase())) {
    return explicit;
  }

  const words = captionText.split(/\s+/).map(formatSubtitleText).filter(Boolean);
  const contentWords = words.filter((word) => {
    const normalized = normalizeCaptionToken(word);
    return normalized.length >= 3 && !STOPWORDS.has(normalized);
  });
  if (contentWords.length >= 2) {
    return contentWords.slice(-2).join(" ");
  }
  return contentWords[0] ?? words[words.length - 1] ?? "";
}

export function splitCaptionWords(captionText: string, captionEmphasis?: string | null): CaptionWord[] {
  const displayWords = captionWordsForDisplay({ captionText, narration: "" });
  const emphasis = chooseCaptionEmphasis(displayWords.join(" "), captionEmphasis);
  const emphasisTokens = emphasis.split(/\s+/).map(normalizeCaptionToken).filter(Boolean);

  if (emphasisTokens.length === 0) {
    return displayWords.map((text) => ({ text, emphasized: false }));
  }

  const displayTokens = displayWords.map(normalizeCaptionToken);
  let startIndex = -1;
  for (let i = 0; i <= displayTokens.length - emphasisTokens.length; i += 1) {
    const matches = emphasisTokens.every((token, offset) => displayTokens[i + offset] === token);
    if (matches) {
      startIndex = i;
      break;
    }
  }

  return displayWords.map((text, index) => ({
    text,
    emphasized: startIndex >= 0 && index >= startIndex && index < startIndex + emphasisTokens.length,
  }));
}
```

- [ ] **Step 4: Create `remotion/src/scenes/CaptionScene.tsx`**

Add a first renderer with deterministic layout and helper exports:

```tsx
import React, { useMemo } from "react";
import { Img, interpolate, spring, useCurrentFrame, useVideoConfig } from "remotion";
import { loadFont } from "@remotion/google-fonts/Inter";
import type { Orientation, SceneInput, VisualCanvas } from "../types";
import { captionWordsForDisplay, splitCaptionWords } from "../utils/captionText";
import { findWordBoundary } from "../utils/wordMatch";
import { StaticCanvas } from "./StaticCanvas";

const { fontFamily } = loadFont("normal", {
  weights: ["800", "900"],
  subsets: ["latin"],
});

interface Props {
  scene: SceneInput;
  orientation?: Orientation;
  visualCanvas?: VisualCanvas | null;
}

const clamp = (value: number, min: number, max: number) => Math.min(max, Math.max(min, value));

const fontSizeFor = (wordCount: number, orientation: Orientation) => {
  if (orientation === "vertical") {
    if (wordCount <= 4) return 106;
    if (wordCount <= 8) return 88;
    return 72;
  }
  if (wordCount <= 4) return 112;
  if (wordCount <= 8) return 92;
  return 74;
};

export const CaptionScene: React.FC<Props> = ({ scene, orientation = "horizontal", visualCanvas }) => {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();
  const words = captionWordsForDisplay({
    captionText: scene.caption_text,
    narration: scene.narration,
  });
  const captionText = words.join(" ");
  const splitWords = splitCaptionWords(captionText, scene.caption_emphasis);
  const timestamps = scene.word_timestamps ?? [];
  const boundary = useMemo(
    () => findWordBoundary(timestamps, captionText),
    [timestamps, captionText],
  );
  const timedWords = boundary.subtitleWords.length === splitWords.length
    ? boundary.subtitleWords
    : timestamps.length >= splitWords.length
      ? timestamps.slice(-splitWords.length)
      : [];
  const hasImage = Boolean(scene.image_path);
  const isVertical = orientation === "vertical";
  const fontSize = fontSizeFor(splitWords.length, orientation);
  const visualEntrance = spring({
    frame,
    fps,
    config: { damping: 16, mass: 0.8 },
    from: 0,
    to: 1,
  });

  return (
    <div style={rootStyle}>
      <StaticCanvas canvas={visualCanvas} />
      {hasImage && (
        <div
          style={{
            ...imageFrameStyle(isVertical),
            opacity: visualEntrance,
            transform: `${imageFrameStyle(isVertical).transform ?? ""} scale(${0.94 + 0.06 * visualEntrance})`,
          }}
        >
          <Img src={scene.image_path ?? ""} style={imageStyle} />
        </div>
      )}
      <div style={textWrapStyle({ hasImage, isVertical, fontSize })}>
        {splitWords.map((word, index) => {
          const timing = timedWords[index];
          const startFrame = timing ? Math.round((timing.start_ms / 1000) * fps) : 10 + index * 5;
          const wordAge = frame - startFrame;
          const visible = wordAge >= 0;
          const progress = clamp(wordAge / 8, 0, 1);
          const pop = spring({
            frame: Math.max(0, wordAge),
            fps,
            config: { damping: word.emphasized ? 10 : 14, mass: 0.65 },
            from: word.emphasized ? 0.74 : 0.82,
            to: 1,
          });
          const pulse = word.emphasized && wordAge >= 0 && wordAge < 12
            ? 1 + Math.sin((wordAge / 12) * Math.PI) * 0.08
            : 1;

          return (
            <span
              key={`${word.text}-${index}`}
              style={{
                ...wordStyle(word.emphasized),
                opacity: visible ? progress : 0,
                transform: `translateY(${visible ? (1 - progress) * 22 : 22}px) scale(${visible ? pop * pulse : 0.82}) rotate(${index % 2 === 0 ? "-0.6deg" : "0.4deg"})`,
              }}
            >
              {word.text}
            </span>
          );
        })}
      </div>
    </div>
  );
};

const rootStyle: React.CSSProperties = {
  position: "absolute",
  inset: 0,
  overflow: "hidden",
};

const imageFrameStyle = (isVertical: boolean): React.CSSProperties => ({
  position: "absolute",
  left: isVertical ? 120 : 128,
  top: isVertical ? 180 : 120,
  width: isVertical ? 840 : 680,
  height: isVertical ? 620 : 760,
  border: "10px solid #111",
  borderRadius: 12,
  boxShadow: "18px 18px 0 rgba(0, 0, 0, 0.45)",
  overflow: "hidden",
  background: "#111",
});

const imageStyle: React.CSSProperties = {
  width: "100%",
  height: "100%",
  objectFit: "cover",
  display: "block",
};

const textWrapStyle = ({
  hasImage,
  isVertical,
  fontSize,
}: {
  hasImage: boolean;
  isVertical: boolean;
  fontSize: number;
}): React.CSSProperties => ({
  position: "absolute",
  left: hasImage && !isVertical ? 900 : isVertical ? 90 : 180,
  right: isVertical ? 90 : 120,
  top: hasImage && isVertical ? 880 : "50%",
  transform: hasImage && isVertical ? undefined : "translateY(-50%)",
  display: "flex",
  flexWrap: "wrap",
  justifyContent: hasImage && !isVertical ? "flex-start" : "center",
  alignItems: "center",
  gap: "0.18em",
  fontFamily,
  fontSize,
  fontWeight: 900,
  lineHeight: 1.06,
  textAlign: hasImage && !isVertical ? "left" : "center",
  textTransform: "uppercase",
  letterSpacing: 0,
});

const wordStyle = (emphasized: boolean): React.CSSProperties => ({
  display: "inline-block",
  color: emphasized ? "#FF1F1F" : "#F7F7F7",
  WebkitTextStroke: "4px #080808",
  textShadow: emphasized
    ? "7px 7px 0 #000, 0 0 22px rgba(255, 31, 31, 0.35)"
    : "7px 7px 0 #000",
  paintOrder: "stroke fill",
});
```

- [ ] **Step 5: Update `SceneRenderer` dispatch and suppression**

In `remotion/src/scenes/SceneRenderer.tsx`, import `CaptionScene`:

```ts
import { CaptionScene } from "./CaptionScene";
```

Add:

```ts
  const isCaptionScene = scene.visual_mode === "captions" || scene.visual_beat === "captions";
```

Dispatch before video/image branches:

```tsx
  } else if (isCaptionScene) {
    visualLayer = <CaptionScene scene={scene} orientation={orientation} visualCanvas={visualCanvas} />;
```

Update FX and layout suppression:

```ts
  if (fx?.drift && !isAhaSubtitle && !isCaptionScene && !isTitleCard) {
```

```ts
  if (fx?.zoom_punch && !isAhaSubtitle && !isCaptionScene) {
```

```ts
  if (isVertical && !isAhaSubtitle && !isCaptionScene && !isTitleCard) {
```

Suppress subtitles:

```tsx
          {!scene.is_title_card && !isAhaSubtitle && !isCaptionScene && (scene.word_timestamps?.length ?? 0) > 0 && (
```

Suppress Eli:

```tsx
      {!isAhaSubtitle && !isCaptionScene && scene.eli_overlay?.enabled && scene.eli_overlay.frame_id && scene.character_frames_base_url && (
```

- [ ] **Step 6: Run frontend caption tests**

Run:

```bash
npm run test:frontend -- --run frontend/src/remotion/CaptionScene.test.ts
```

Expected: PASS.

- [ ] **Step 7: Commit**

```bash
git add remotion/src/utils/captionText.ts remotion/src/scenes/CaptionScene.tsx remotion/src/scenes/SceneRenderer.tsx frontend/src/remotion/CaptionScene.test.ts
git commit -m "Add captions Remotion renderer"
```

## Task 4: Backend Generation And Analysis

**Files:**
- Modify: `backend/pipeline/image_gen.py`
- Modify: `backend/pipeline/visual_treatments.py`
- Test: `backend/tests/test_visual_treatments.py`

- [ ] **Step 1: Write failing visual treatment tests**

Append to `backend/tests/test_visual_treatments.py`:

```python
def test_analyze_visual_treatments_preserves_explicit_captions_scene():
    scene = Scene(
        id="scene_001",
        narration="This is the real cost.",
        visual_prompt="",
        visual_mode="captions",
        caption_text="The real cost",
        caption_emphasis="real",
        audio_duration_seconds=2.0,
        word_timestamps=[
            {"word": "This", "start_ms": 0, "end_ms": 100},
            {"word": "is", "start_ms": 120, "end_ms": 180},
            {"word": "the", "start_ms": 200, "end_ms": 260},
            {"word": "real", "start_ms": 300, "end_ms": 450},
            {"word": "cost", "start_ms": 470, "end_ms": 640},
        ],
    )
    content = ScriptContent(title="Test", segments=[Segment(name="Segment", scenes=[scene])])

    assignment = analyze_visual_treatments(content, script_id="script")[0]

    assert assignment.visual_mode == "captions"
    assert assignment.visual_treatment == "full_frame"
    assert assignment.visual_layers == []


def test_generate_batch_captions_without_prompt_skips_scene_image(monkeypatch):
    from pipeline import image_gen as image_gen_mod

    def fail_generate_scene_image(**_kwargs):
        raise AssertionError("text-only captions should not generate a scene image")

    monkeypatch.setattr(image_gen_mod, "generate_scene_image", fail_generate_scene_image)

    result = image_gen_mod.generate_scene_visual(
        {
            "scene_id": "scene_001",
            "visual_mode": "captions",
            "visual_prompt": "",
            "caption_text": "The real cost",
            "caption_emphasis": "real",
            "media_source": "ai",
            "visual_treatment": "full_frame",
            "frame_directives": [],
            "contains_person": False,
        },
        script_id="script",
    )

    assert result["scene_id"] == "scene_001"
    assert result["image_url"] is None
    assert result["frame_urls"] == []
    assert result["prompt_used"] is None
    assert result["error"] is None


def test_generate_batch_captions_with_prompt_uses_single_scene_image(monkeypatch):
    from pipeline import image_gen as image_gen_mod

    calls = []

    def fake_generate_scene_image(**kwargs):
        calls.append(kwargs)
        return "/static/projects/script/images/scene_001.png", kwargs["visual_prompt"], {"source_type": "ai_generated"}

    monkeypatch.setattr(image_gen_mod, "generate_scene_image", fake_generate_scene_image)

    result = image_gen_mod.generate_scene_visual(
        {
            "scene_id": "scene_001",
            "visual_mode": "captions",
            "visual_prompt": "[REACTION] A worried shopper holding a receipt.",
            "caption_text": "Falling behind",
            "caption_emphasis": "behind",
            "media_source": "ai",
            "visual_treatment": "full_frame",
            "frame_directives": [],
            "contains_person": True,
        },
        script_id="script",
    )

    assert len(calls) == 1
    assert result["image_url"] == "/static/projects/script/images/scene_001.png"
    assert result["video_url"] == ""
```

- [ ] **Step 2: Run failing tests**

Run:

```bash
uv run --project backend pytest backend/tests/test_visual_treatments.py -k "captions" -v
```

Expected: FAIL because captions analysis/generation behavior is not implemented yet.

- [ ] **Step 3: Preserve captions in `visual_treatments.py`**

In `_analyze_scene`, after the explicit flip-flop block, add:

```python
    if scene.visual_mode == "captions":
        return VisualTreatmentAssignment(
            scene_id=scene.id,
            visual_mode="captions",
            visual_treatment="full_frame",
            reasoning="Scene is explicitly marked for captions rendering.",
            visual_layers=[],
        )
```

In `apply_visual_treatment_assignments`, keep layers only for popup/flip-flop:

```python
        scene.visual_layers = (
            list(assignment.visual_layers)
            if mode in {"popup_sequence", "flipflop"}
            else []
        )
```

- [ ] **Step 4: Update `image_gen.py` captions dispatch**

Inside `generate_scene_visual`, after the video branch and before the default Gemini branch logging, add:

```python
        if visual_mode == "captions" and not str(scene.get("visual_prompt") or "").strip():
            logger.info("[CAPTIONS] scene %s — text-only caption, skipping image generation", scene["scene_id"])
            return {
                "scene_id": scene["scene_id"],
                "image_url": None,
                "frame_urls": [],
                "video_url": "",
                "prompt_used": None,
                "visual_source_metadata": None,
                "error": None,
            }
```

Ensure the layered treatment branch remains limited to:

```python
        if visual_mode in {"popup_sequence", "flipflop"}:
            treatment = visual_mode
```

and does not include captions.

- [ ] **Step 5: Run focused backend tests**

Run:

```bash
uv run --project backend pytest backend/tests/test_visual_treatments.py -k "captions" -v
```

Expected: PASS.

- [ ] **Step 6: Commit**

```bash
git add backend/pipeline/image_gen.py backend/pipeline/visual_treatments.py backend/tests/test_visual_treatments.py
git commit -m "Route captions visual generation"
```

## Task 5: Test Lab Support

**Files:**
- Modify: `backend/pipeline/test_lab.py`
- Modify: `backend/tests/test_test_lab.py`
- Modify: `frontend/src/components/test-lab/TestLabControls.tsx`

- [ ] **Step 1: Write failing backend Test Lab tests**

Append to `backend/tests/test_test_lab.py`:

```python
def test_test_lab_accepts_captions_visual_mode_without_treatment_assets():
    from pipeline.test_lab import TestLabPreset

    preset = TestLabPreset(
        id="caption-punch",
        title="Caption Punch",
        description="Caption test",
        segment_name="The point",
        narration="This was the real cost.",
        visual_prompt="",
        visual_mode="captions",
        caption_text="The real cost",
        caption_emphasis="real",
        duration_estimate_seconds=3.0,
    )

    assert preset.visual_mode == "captions"
    assert preset.media_source == "ai"
    assert preset.caption_text == "The real cost"
    assert preset.caption_emphasis == "real"
```

- [ ] **Step 2: Run failing Test Lab tests**

Run:

```bash
uv run --project backend pytest backend/tests/test_test_lab.py -k captions -v
```

Expected: FAIL because `TestLabPreset` does not accept `captions` or caption fields.

- [ ] **Step 3: Update `backend/pipeline/test_lab.py`**

Add defaults near the other text defaults:

```python
CAPTIONS_TEXT_DEFAULTS = {
    "narration": "Spending big in one area can hide how far behind you are in another.",
    "visual_prompt": (
        "[REACTION] Flat 2D cartoon person sitting beside a kitchen table with a receipt, "
        "a small luxury purchase on one side and overdue bills on the other, expressive worried face, "
        "bold clean composition, no readable words or letters."
    ),
    "caption_text": "Spending big while falling behind",
    "caption_emphasis": "falling behind",
}
```

Add it to `VISUAL_TREATMENT_TEXT_DEFAULTS` even though captions is not a `VisualTreatment`; this API field is already a mode-default convenience:

```python
VISUAL_TREATMENT_TEXT_DEFAULTS = {
    "multi_frame": MULTI_FRAME_TEXT_DEFAULTS,
    "continuous": CONTINUOUS_TEXT_DEFAULTS,
    "popup_sequence": POPUP_SEQUENCE_TEXT_DEFAULTS,
    "flipflop": FLIPFLOP_TEXT_DEFAULTS,
    "captions": CAPTIONS_TEXT_DEFAULTS,
}
```

Update `TestLabPreset.visual_mode` literal:

```python
    visual_mode: Literal["video", "full_frame", "multi_frame", "continuous", "popup_sequence", "flipflop", "captions"] = "full_frame"
```

Add preset fields:

```python
    caption_text: str = ""
    caption_emphasis: str = ""
```

Add a `TEST_LAB_PRESETS` entry:

```python
    TestLabPreset(
        id="caption-punch",
        title="Captions Punch Test",
        description="Editorial in-scene caption beat with red emphasis and optional side visual.",
        segment_name="The point",
        narration=CAPTIONS_TEXT_DEFAULTS["narration"],
        visual_prompt=CAPTIONS_TEXT_DEFAULTS["visual_prompt"],
        caption_text=CAPTIONS_TEXT_DEFAULTS["caption_text"],
        caption_emphasis=CAPTIONS_TEXT_DEFAULTS["caption_emphasis"],
        visual_mode="captions",
        background_color="#F6C54A",
    ),
```

Where Test Lab creates the hidden `Scene`, pass:

```python
        caption_text=settings.get("caption_text") or preset.caption_text,
        caption_emphasis=settings.get("caption_emphasis") or preset.caption_emphasis,
```

- [ ] **Step 4: Update Test Lab frontend option**

In `frontend/src/components/test-lab/TestLabControls.tsx`, import a text icon:

```ts
import { Captions, Film, HelpCircle, Image, Images, Palette, PanelsTopLeft, Repeat2, Route, UserRound } from "lucide-react";
```

Add an option to `VISUAL_MODE_OPTIONS`:

```tsx
  {
    value: "captions",
    label: "Captions",
    icon: <Captions className="h-4 w-4" />,
    summary: "Big editorial text lands on voiceover beats.",
    description: "Renders short in-scene caption text with red emphasis while suppressing normal bottom subtitles.",
    bestFor: "Use for reversals, emotional labels, shocking claims, and moments where the line itself is the visual punch.",
  },
```

Ensure layered treatment stays:

```ts
  const isLayeredTreatment = visualMode === "popup_sequence" || visualMode === "flipflop";
```

Update `settingsWithVisualTreatmentDefaults` to accept captions defaults by changing the `visualTreatment` parameter to `VisualMode | VisualTreatment` and reading from `visualTreatmentDefaults?.[visualTreatment]`.

Add controls under Scene text when `visualMode === "captions"`:

```tsx
        {visualMode === "captions" && (
          <div className="mt-3 grid grid-cols-2 gap-3">
            <label className="block">
              <span className="text-xs font-medium text-neutral-300">Caption text</span>
              <input
                value={settings.caption_text ?? ""}
                onChange={(event) => update({ caption_text: event.target.value })}
                className="mt-2 w-full rounded-md border border-neutral-800 bg-neutral-950/80 px-3 py-2 text-sm text-neutral-100 outline-none transition-colors placeholder:text-neutral-600 hover:border-neutral-700 focus:border-violet-500"
                placeholder="The real cost"
              />
            </label>
            <label className="block">
              <span className="text-xs font-medium text-neutral-300">Red emphasis</span>
              <input
                value={settings.caption_emphasis ?? ""}
                onChange={(event) => update({ caption_emphasis: event.target.value })}
                className="mt-2 w-full rounded-md border border-neutral-800 bg-neutral-950/80 px-3 py-2 text-sm text-neutral-100 outline-none transition-colors placeholder:text-neutral-600 hover:border-neutral-700 focus:border-violet-500"
                placeholder="real"
              />
            </label>
          </div>
        )}
```

- [ ] **Step 5: Run tests**

Run:

```bash
uv run --project backend pytest backend/tests/test_test_lab.py -k captions -v
npm run test:frontend -- --run
```

Expected: backend captions Test Lab test passes and frontend tests compile.

- [ ] **Step 6: Commit**

```bash
git add backend/pipeline/test_lab.py backend/tests/test_test_lab.py frontend/src/components/test-lab/TestLabControls.tsx
git commit -m "Add captions Test Lab support"
```

## Task 6: Timeline UI Support

**Files:**
- Modify: `frontend/src/components/timeline/PropertiesPanel.tsx`
- Modify: `frontend/src/components/timeline/TimelineBlock.tsx`
- Modify: `frontend/src/components/timeline/TimelinePage.tsx`

- [ ] **Step 1: Add Timeline visual mode option**

In `PropertiesPanel.tsx`, import `Captions`:

```ts
import { Captions, Film, Image, Images, PanelsTopLeft, Repeat2, Route } from "lucide-react";
```

Add to `VISUAL_MODE_OPTIONS`:

```tsx
    { value: "captions", label: "Captions", icon: <Captions className="h-3 w-3" /> },
```

Keep treatment mirroring unchanged:

```ts
  const visualTreatmentForMode = (mode: VisualMode): VisualTreatment =>
    mode === "popup_sequence" || mode === "flipflop" ? mode : "full_frame";
```

- [ ] **Step 2: Add caption fields to Timeline properties**

After the Visual Prompt textarea column, add a captions-only compact block:

```tsx
        {visualMode === "captions" && (
          <div className="flex-[1.4] flex flex-col gap-2 min-w-0 min-h-0">
            <label className="flex flex-col min-w-0">
              <span className="text-xs font-medium text-neutral-400 mb-0.5">Caption text</span>
              <input
                value={scene.caption_text ?? ""}
                onChange={(event) => onUpdate({ caption_text: event.target.value })}
                className="w-full text-sm text-neutral-200 bg-neutral-800/60 rounded-lg px-2 py-1.5 border border-neutral-700/50 focus:outline-none focus:border-violet-500/50 focus:ring-1 focus:ring-violet-500/30"
                placeholder="Short editorial phrase"
              />
            </label>
            <label className="flex flex-col min-w-0">
              <span className="text-xs font-medium text-neutral-400 mb-0.5">Red emphasis</span>
              <input
                value={scene.caption_emphasis ?? ""}
                onChange={(event) => onUpdate({ caption_emphasis: event.target.value })}
                className="w-full text-sm text-neutral-200 bg-neutral-800/60 rounded-lg px-2 py-1.5 border border-neutral-700/50 focus:outline-none focus:border-violet-500/50 focus:ring-1 focus:ring-violet-500/30"
                placeholder="Most intense word"
              />
            </label>
            <p className="text-[11px] leading-4 text-neutral-500">
              Rendered in-scene with word timing; normal subtitles are suppressed.
            </p>
          </div>
        )}
```

If this makes the fixed `h-36` header row too cramped, increase it to `h-44` only when captions is active:

```tsx
      <div className={`shrink-0 flex gap-4 px-4 py-2 ${visualMode === "captions" ? "h-44" : "h-36"}`}>
```

- [ ] **Step 3: Add captions timeline colors**

In `TimelineBlock.tsx`, add:

```ts
    captions: "bg-red-500/70",
```

In `ImageContent`, before the image branches, add a caption label:

```tsx
  if (scene.visual_mode === "captions") {
    return (
      <div className="flex gap-1.5 items-center">
        <span className="w-2 h-2 rounded-full shrink-0 bg-red-500" />
        <span className="text-[10px] font-medium text-red-200 uppercase">Captions</span>
      </div>
    );
  }
```

- [ ] **Step 4: Add captions to visual mix**

In `TimelinePage.tsx`, add the row:

```ts
    { key: "captions", label: "Captions", color: "text-red-300", count: modeCounts.captions ?? 0 },
```

- [ ] **Step 5: Run frontend tests**

Run:

```bash
npm run test:frontend -- --run
```

Expected: PASS.

- [ ] **Step 6: Commit**

```bash
git add frontend/src/components/timeline/PropertiesPanel.tsx frontend/src/components/timeline/TimelineBlock.tsx frontend/src/components/timeline/TimelinePage.tsx
git commit -m "Add captions timeline controls"
```

## Task 7: Script Prompt Support

**Files:**
- Modify: `backend/prompts/script.py`
- Modify: `backend/tests/pipeline/test_scriptwriter_visual_beats.py`
- Modify: `backend/tests/test_prompts.py`

- [ ] **Step 1: Write failing prompt tests**

Append to `backend/tests/pipeline/test_scriptwriter_visual_beats.py`:

```python
def test_script_prompt_includes_captions_mode_without_extra_renderer_detail():
    prompt_text = script_prompt.SCRIPT_SYSTEM.template

    assert '"captions"' in prompt_text
    assert "caption_text" in prompt_text
    assert "caption_emphasis" in prompt_text
    assert "renderer handles" in prompt_text
    assert "Do not put readable caption text into visual_prompt" in prompt_text
```

Append to `backend/tests/test_prompts.py`:

```python
    def test_script_prompt_keeps_life_as_a_captions_disabled(self):
        prompt_text = PROMPTS["SCRIPT_SYSTEM"].template

        assert 'captions' in prompt_text
        assert 'life-as-a' in prompt_text
        assert 'captions remain disabled' in prompt_text
```

- [ ] **Step 2: Run failing prompt tests**

Run:

```bash
uv run --project backend pytest backend/tests/pipeline/test_scriptwriter_visual_beats.py::test_script_prompt_includes_captions_mode_without_extra_renderer_detail backend/tests/test_prompts.py::TestPromptRegistry::test_script_prompt_keeps_life_as_a_captions_disabled -v
```

Expected: FAIL because prompt text does not mention captions.

- [ ] **Step 3: Update visual mode vocabulary in `backend/prompts/script.py`**

In the Visual Mode System section, add:

```text
- "captions" — When a sentence delivers a punchy editorial label, reversal, emotional realization, or key claim that should become large in-scene text. Use a static canvas with optional side visual plus renderer-owned caption typography. Emit "caption_text" (2-15 words ideally) and "caption_emphasis" (the one strongest word or phrase to render red). Do not describe typography, animation, color, or layout in detail; the renderer handles those. Do not put readable caption text into visual_prompt.
```

Update distribution rules to include captions:

```text
2. After every 2 consecutive full_frame scenes, the NEXT scene MUST use a different mode (multi_frame, continuous, captions, or aha_subtitle).
3. Variety modes (multi_frame, continuous, captions, aha_subtitle) must NEVER appear 2+ times consecutively — always separate them with at least one full_frame scene.
4. aha_subtitle and captions must be sandwiched between image-bearing modes when they are text-only.
```

Update frame directive guidance:

```text
Set "visual_beat" to the same value as "visual_mode" except use "static" when "visual_mode" is "full_frame".
For captions scenes, include "caption_text" and "caption_emphasis" on the scene object. Use a normal ai_generated frame directive only when visual_prompt is non-empty; use an empty frame_directives list for text-only captions.
```

In the output schema scene example, add:

```json
          "caption_text": "",
          "caption_emphasis": "",
```

In the life-as-a section that disables `aha_subtitle`, add:

```text
- **`captions`: DISABLED in life-as-a for the first pass.** Keep chapter-card and scene narration in the existing visual language; do not create editorial caption scenes for this format yet.
```

- [ ] **Step 4: Run prompt tests**

Run:

```bash
uv run --project backend pytest backend/tests/pipeline/test_scriptwriter_visual_beats.py::test_script_prompt_includes_captions_mode_without_extra_renderer_detail backend/tests/test_prompts.py::TestPromptRegistry::test_script_prompt_keeps_life_as_a_captions_disabled -v
```

Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add backend/prompts/script.py backend/tests/pipeline/test_scriptwriter_visual_beats.py backend/tests/test_prompts.py
git commit -m "Teach script prompt captions mode"
```

## Task 8: Remotion Render Props And Export Flow Verification

**Files:**
- Modify: `backend/pipeline/remotion_render.py`
- Modify: `backend/tests/pipeline/test_remotion_render.py`

- [ ] **Step 1: Write failing Remotion prop test**

Add to `backend/tests/pipeline/test_remotion_render.py`:

```python
def test_scene_to_input_props_include_caption_fields_for_captions_scene(tmp_path, monkeypatch):
    monkeypatch.setattr(remotion_render, "DATA_DIR", tmp_path)
    scene = Scene(
        id="scene_001",
        narration="This was the real cost.",
        visual_prompt="",
        visual_mode="captions",
        caption_text="The real cost",
        caption_emphasis="real",
        audio_duration_seconds=2.0,
        word_timestamps=[
            {"word": "This", "start_ms": 0, "end_ms": 120},
            {"word": "was", "start_ms": 140, "end_ms": 220},
            {"word": "the", "start_ms": 240, "end_ms": 310},
            {"word": "real", "start_ms": 330, "end_ms": 480},
            {"word": "cost", "start_ms": 500, "end_ms": 650},
        ],
    )
    props = remotion_render._scene_to_input_props(scene, "script")

    assert props["visual_mode"] == "captions"
    assert props["caption_text"] == "The real cost"
    assert props["caption_emphasis"] == "real"
```

- [ ] **Step 2: Run failing test**

Run:

```bash
uv run --project backend pytest backend/tests/pipeline/test_remotion_render.py -k caption -v
```

Expected: FAIL if caption fields are not passed to Remotion props.

- [ ] **Step 3: Update `backend/pipeline/remotion_render.py`**

Where scene props are built, include:

```python
            "caption_text": scene.caption_text,
            "caption_emphasis": scene.caption_emphasis,
```

Ensure `visual_mode` already flows through; if not, include:

```python
            "visual_mode": scene.visual_mode,
```

- [ ] **Step 4: Run focused Remotion prop test**

Run:

```bash
uv run --project backend pytest backend/tests/pipeline/test_remotion_render.py -k caption -v
```

Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add backend/pipeline/remotion_render.py backend/tests/pipeline/test_remotion_render.py
git commit -m "Pass captions fields to Remotion"
```

## Task 9: Project Convention Documentation

**Files:**
- Modify: `AGENTS.md`

- [ ] **Step 1: Add the captions convention**

In `AGENTS.md`, near the visual mode conventions, add:

```markdown
- **Captions visual mode is renderer-owned editorial text**: `visual_mode="captions"` is a static-canvas punch mode with optional side imagery plus large in-scene `caption_text` and red `caption_emphasis`. It is not standard subtitle rendering and must suppress normal bottom subtitles during the caption beat. Fresh script generation emits the fields in the existing script call; do not add a required extra LLM call or render readable caption text inside generated images.
```

- [ ] **Step 2: Commit**

```bash
git add AGENTS.md
git commit -m "Document captions visual mode convention"
```

## Task 10: Full Verification, Push, And Review Loop

**Files:**
- Verify all files changed in Tasks 1-9.

- [ ] **Step 1: Run targeted backend tests**

Run:

```bash
uv run --project backend pytest \
  backend/tests/test_visual_mode.py \
  backend/tests/test_visual_treatments.py -k "captions or analyze_visual_treatments_preserves_explicit_captions_scene or generate_batch_captions" \
  backend/tests/test_test_lab.py -k captions \
  backend/tests/pipeline/test_remotion_render.py -k caption \
  backend/tests/pipeline/test_scriptwriter_visual_beats.py::test_script_prompt_includes_captions_mode_without_extra_renderer_detail \
  backend/tests/test_prompts.py::TestPromptRegistry::test_script_prompt_keeps_life_as_a_captions_disabled \
  -v
```

Expected: PASS.

- [ ] **Step 2: Run frontend tests**

Run:

```bash
npm run test:frontend -- --run
```

Expected: PASS.

- [ ] **Step 3: Run production frontend build**

Run:

```bash
cd frontend && npm run build
```

Expected: PASS.

- [ ] **Step 4: Check git status**

Run:

```bash
git status --short
```

Expected: only intentional captions changes are staged or unstaged. Existing unrelated `data/` and `docs/superpowers/plans/2026-05-23-preset-scoped-characters.md` may still be untracked and must not be included unless they become related.

- [ ] **Step 5: Commit any remaining implementation changes**

If Tasks 1-9 were not committed individually, stage only captions-related files:

```bash
git add \
  AGENTS.md \
  backend/models/script.py \
  backend/pipeline/image_gen.py \
  backend/pipeline/remotion_render.py \
  backend/pipeline/test_lab.py \
  backend/pipeline/visual_treatments.py \
  backend/prompts/script.py \
  backend/tests/test_prompts.py \
  backend/tests/test_test_lab.py \
  backend/tests/test_visual_mode.py \
  backend/tests/test_visual_treatments.py \
  backend/tests/pipeline/test_remotion_render.py \
  backend/tests/pipeline/test_scriptwriter_visual_beats.py \
  frontend/src/components/test-lab/TestLabControls.tsx \
  frontend/src/components/timeline/PropertiesPanel.tsx \
  frontend/src/components/timeline/TimelineBlock.tsx \
  frontend/src/components/timeline/TimelinePage.tsx \
  frontend/src/remotion/CaptionScene.test.ts \
  frontend/src/types/script.ts \
  frontend/src/types/testLab.ts \
  remotion/src/scenes/CaptionScene.tsx \
  remotion/src/scenes/SceneRenderer.tsx \
  remotion/src/types.ts \
  remotion/src/utils/captionText.ts
git commit -m "Add captions visual mode"
```

- [ ] **Step 6: Push to main**

Run:

```bash
git push origin main
```

Expected: push succeeds.

- [ ] **Step 7: Dispatch delegated code review**

Use Codex agent delegation tooling with this exact prompt:

```text
Review the most recent commit on the main branch of this project.
Run `git diff HEAD~1..HEAD` to see the changes and `git show --stat HEAD` for context.
Read the full affected files (not just the diff) to understand surrounding code.
Check for: correctness bugs, error handling gaps, security issues, naive/aware datetime mismatches, unhandled promise rejections, race conditions, and style problems.
Return a structured verdict: either LGTM or NEEDS CHANGES.
If NEEDS CHANGES, provide a numbered list of findings with severity (FAIL/WARN), file:line, and a specific description of what's wrong and how to fix it.
```

- [ ] **Step 8: Apply review findings until LGTM**

If the review returns NEEDS CHANGES, implement every FAIL and WARN finding, commit as:

```bash
git add $(git diff --name-only -- AGENTS.md backend frontend remotion)
git commit -m "Fix captions review findings"
git push origin main
```

Then repeat Step 7. Continue until the delegated review returns LGTM.

## Self-Review Notes

- Spec coverage: model fields, visual mode semantics, Remotion renderer, prompt updates, no extra LLM call, Test Lab support, Timeline controls, image generation skip behavior, subtitle suppression, logging-oriented behavior, and AGENTS convention all have tasks.
- Scope control: automatic conversion of old projects is intentionally excluded; the plan only preserves explicit captions and supports fresh script generation/manual selection.
- Type consistency: all tasks use `visual_mode="captions"`, `caption_text`, and `caption_emphasis`; compatibility fields remain `media_source="ai"` and `visual_treatment="full_frame"`.
