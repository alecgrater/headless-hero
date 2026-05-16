# Short Form Export Simplification — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Strip the per-segment ElevenLabs intro generation from the short-form export pipeline. The short's title card scene now reuses the segment's existing first-scene audio (already a title card with narration that names the segment) and shows the stripped long-form title statically with a pop-in flourish on the segment name.

**Architecture:** This is a transformation of an existing partially-built feature, not a greenfield build. We delete the entire intro VO subsystem (`ShortIntro` model, `pipeline/short_form_intros.py`, intros REST endpoints, intros UI card and gating). We rewrite `ShortTitleCardScene.tsx` from a word-by-word timestamp-synced reveal to a static title + spring/glow pop-in for the segment name. We change the Remotion props shape so the title card scene is the segment's first scene (`is_title_card=True`), not a separate intro sequence.

**Tech Stack:** Python 3.12 (UV) / FastAPI / SQLModel (backend) · Remotion 4 / React (renderer) · React 19 / TypeScript / Tailwind 4 (frontend)

**Spec:** `docs/superpowers/specs/2026-05-15-short-form-export-design.md`

---

## File Map

**Backend (Python):**
- Modify: `backend/pipeline/short_form_render.py` — drop intro plumbing, use first-scene's audio
- Modify: `backend/api/short_form.py` — drop intros endpoints + validation
- Modify: `backend/models/script.py` — drop `ShortIntro` model + `short_intros` field
- Modify: `backend/tests/pipeline/test_short_form_render.py` — update for new prop shape, add `strip_leading_number` tests
- Delete: `backend/pipeline/short_form_intros.py`
- Delete: `backend/tests/pipeline/test_short_form_intros.py`

**Remotion (TypeScript):**
- Modify: `remotion/src/types.ts` — replace `ShortIntroProps`, update `ShortFormVideoProps`
- Rewrite: `remotion/src/scenes/ShortTitleCardScene.tsx` — static title + pop-in flourish
- Modify: `remotion/src/ShortFormVideo.tsx` — first-scene-is-title-card pattern (no separate intro sequence)

**Frontend (React):**
- Modify: `frontend/src/api.ts` — remove intro generation functions
- Modify: `frontend/src/types/render.ts` — remove `ShortIntro` type, simplify `ShortFormJobStatus` if needed
- Modify: `frontend/src/types/script.ts` — drop `short_intros` field reference
- Modify: `frontend/src/components/timeline/short-form/ShortFormTab.tsx` — drop intros card
- Modify: `frontend/src/components/timeline/short-form/RenderShortsCard.tsx` — drop gating, modal, "introsReady"
- Modify: `frontend/src/components/timeline/short-form/ShortFormStatusPill.tsx` — show only renders count
- Modify: `frontend/src/components/timeline/ExportPanel.tsx` — drop `shortIntros` / `onShortIntrosChanged` props
- Modify: `frontend/src/components/timeline/TimelinePage.tsx` — drop intro-related plumbing
- Delete: `frontend/src/components/timeline/short-form/ShortIntrosCard.tsx`

---

## Task 1: Refactor `short_form_render.py` to use first-scene's audio

The render pipeline currently relies on a separate `ShortIntro` (with its own audio file). After this task, it uses the segment's first scene (`is_title_card=True`) directly. The `strip_leading_number` helper is moved here so we can delete `short_form_intros.py` later.

**Files:**
- Modify: `backend/pipeline/short_form_render.py`

- [ ] **Step 1: Replace the file's contents**

```python
"""Short-form (9:16) render pipeline — renders one or all per-segment shorts via Remotion."""

import json
import logging
import os
import re
import shutil
from pathlib import Path
from typing import Callable

from config import BACKEND_PORT, DATA_DIR, FPS, sanitize_filename
from models.script import Scene, ScriptContent
from pipeline.remotion_render import (
    _reencode_h264,
    _run_remotion,
    _scene_to_input_props,
    _verify_video,
)

logger = logging.getLogger(__name__)

ProgressCallback = Callable[[float, str], None] | None

SHORT_WIDTH = 1080
SHORT_HEIGHT = 1920


def strip_leading_number(title: str) -> str:
    """Strip leading digit(s) followed by whitespace from a title.

    Examples:
        "8 Unsolved Crimes ..." -> "Unsolved Crimes ..."
        "How to Train Your Dragon" -> "How to Train Your Dragon"
        "8Track Memories" -> "8Track Memories"  (no following whitespace)
    """
    return re.sub(r"^\d+\s+", "", title)


def _shorts_dir(script_id: str) -> Path:
    d = DATA_DIR / "projects" / script_id / "renders" / "shorts"
    d.mkdir(parents=True, exist_ok=True)
    return d


def _title_card_backdrop_url(script_id: str, segment_idx: int) -> str:
    """Web-served URL for the per-segment square illustration used as title-card backdrop.

    Returns "" if the file does not exist on disk; the Remotion component falls back
    to a black background in that case.
    """
    base = DATA_DIR / "projects" / script_id / "images"
    p = base / f"title_card_{segment_idx}.png"
    if not p.exists():
        return ""
    return f"http://localhost:{BACKEND_PORT}/static/projects/{script_id}/images/title_card_{segment_idx}.png"


def _short_filename(project_title: str, n: int, total: int) -> str:
    """Build the destination filename per spec: '[short form N/M] {project name}.mp4'."""
    safe = sanitize_filename(project_title)
    # U+2215 division slash (∕) — visually like "/" but filesystem-safe (POSIX reserves U+002F).
    return f"[short form {n}∕{total}] {safe}.mp4"


def _copy_to_downloads(project_title: str, src_path: Path, dest_filename: str) -> str:
    """Copy a rendered short into ~/Downloads/{project name}/{dest_filename}.

    Always overwrites the destination.
    """
    base = os.environ.get("DOWNLOADS_DIR", "") or str(Path.home() / "Downloads")
    folder = Path(base) / sanitize_filename(project_title)
    folder.mkdir(parents=True, exist_ok=True)
    dest = folder / dest_filename
    shutil.copy2(str(src_path), str(dest))
    logger.info("Copied short to downloads: %s", dest)
    return str(dest)


def _build_segment_scene_props(
    segment_scenes: list[Scene],
    script_id: str,
    backdrop_url: str,
) -> list[dict]:
    """Convert a segment's scenes to Remotion input props.

    Overrides the title card scene's image_url to the per-segment square illustration
    (shorts use the square, not the long-form composite grid card).
    """
    props: list[dict] = []
    for scene in segment_scenes:
        scene_props = _scene_to_input_props(scene, script_id)
        if scene.is_title_card and backdrop_url:
            scene_props["image_path"] = backdrop_url
        props.append(scene_props)
    return props


def render_short_segment(
    script_id: str,
    segment_idx: int,
    content: ScriptContent,
    project_title: str,
    on_progress: ProgressCallback = None,
) -> tuple[str, str]:
    """Render a single short for one segment.

    Returns a tuple of (web_url, downloads_path):
    - web_url: web-relative path served via static mount (e.g. /static/projects/…)
    - downloads_path: absolute filesystem path in ~/Downloads/{project name}/
    """
    if segment_idx < 0 or segment_idx >= len(content.segments):
        raise RuntimeError(f"segment_idx {segment_idx} out of range (0..{len(content.segments) - 1})")

    segment = content.segments[segment_idx]
    if not segment.scenes:
        raise RuntimeError(f"Segment {segment_idx} has no scenes")
    if not segment.scenes[0].is_title_card:
        raise RuntimeError(
            f"Segment {segment_idx} first scene is not a title card — "
            "run the long-form pipeline first"
        )

    scenes_to_render = list(segment.scenes)

    # For short #1 (segment 0), skip the leading "hook" scenes that tease the whole video.
    # The first scene of segment 0 is still the title card, so skip starts at index 1.
    if segment_idx == 0 and content.hook_scene_count:
        # Preserve title card at index 0, drop the next `hook_scene_count` scenes.
        skip = min(content.hook_scene_count, max(0, len(scenes_to_render) - 2))
        if skip > 0:
            logger.info("[%s] short #1: skipping %d hook scene(s)", script_id, skip)
            scenes_to_render = [scenes_to_render[0]] + scenes_to_render[1 + skip:]

    backdrop_url = _title_card_backdrop_url(script_id, segment_idx)
    scene_props = _build_segment_scene_props(scenes_to_render, script_id, backdrop_url)

    props = {
        "scenes": scene_props,
        "stripped_title": strip_leading_number(content.title),
        "segment_name": segment.name,
        "fps": FPS,
        "width": SHORT_WIDTH,
        "height": SHORT_HEIGHT,
        "subtitle_highlight": (
            {"enabled": True} if content.subtitle_highlight_enabled else None
        ),
    }

    shorts_dir = _shorts_dir(script_id)
    n = segment_idx + 1
    total = len(content.segments)
    output_filename = f"{segment_idx}.mp4"
    output_path = shorts_dir / output_filename
    raw_output = shorts_dir / f"{segment_idx}_raw.mkv"

    props_path = shorts_dir / f"{segment_idx}_props.json"
    props_path.write_text(json.dumps(props, indent=2, default=str))

    if on_progress:
        on_progress(0.1, f"Rendering short {n}/{total} with Remotion...")

    try:
        _run_remotion(
            composition_id="ShortFormVideo",
            props_path=props_path,
            output_path=raw_output,
            width=SHORT_WIDTH,
            height=SHORT_HEIGHT,
            log_level="verbose",
        )
        if not _verify_video(raw_output):
            logger.warning("Raw short %d corrupt — retrying", segment_idx)
            _run_remotion(
                composition_id="ShortFormVideo",
                props_path=props_path,
                output_path=raw_output,
                width=SHORT_WIDTH,
                height=SHORT_HEIGHT,
                log_level="verbose",
            )
            if not _verify_video(raw_output):
                raise RuntimeError(f"Remotion produced corrupt short for segment {segment_idx}")

        if on_progress:
            on_progress(0.85, "Re-encoding to H.264...")
        if not _reencode_h264(raw_output, output_path):
            raise RuntimeError(f"H.264 re-encode failed for segment {segment_idx}")

        # Copy to downloads (always overwrites per spec)
        if on_progress:
            on_progress(0.95, "Copying to Downloads...")
        dest_name = _short_filename(project_title, n, total)
        downloads_path = _copy_to_downloads(project_title, output_path, dest_name)
    finally:
        try:
            props_path.unlink()
        except OSError:
            pass
        try:
            raw_output.unlink()
        except OSError:
            pass

    if on_progress:
        on_progress(1.0, f"Short {n}/{total} complete")

    web_url = f"/static/projects/{script_id}/renders/shorts/{output_filename}"
    return web_url, downloads_path


def render_all_shorts(
    script_id: str,
    content: ScriptContent,
    project_title: str,
    on_progress: ProgressCallback = None,
) -> list[tuple[str, str]]:
    """Render every segment as a short, sequentially.

    Returns list of (web_url, downloads_path) tuples, one per segment.
    """
    total = len(content.segments)
    results: list[tuple[str, str]] = []
    for i in range(total):
        n = i + 1

        def seg_progress(p: float, msg: str, _n: int = n) -> None:
            if on_progress:
                # Map per-segment 0..1 into the global range
                global_p = ((_n - 1) + p) / total
                on_progress(global_p, f"Short {_n}/{total}: {msg}")

        web_url, downloads_path = render_short_segment(
            script_id=script_id,
            segment_idx=i,
            content=content,
            project_title=project_title,
            on_progress=seg_progress,
        )
        results.append((web_url, downloads_path))

    return results
```

- [ ] **Step 2: Run pytest to confirm broken tests fail (intros tests still reference old code)**

Run: `cd backend && uv run pytest tests/pipeline/test_short_form_render.py -v`
Expected: PASS for `_short_filename` tests (the existing tests don't reference intros).
Run: `cd backend && uv run pytest tests/pipeline/test_short_form_intros.py -v`
Expected: PASS still (we haven't deleted that file yet).

- [ ] **Step 3: Commit**

```bash
git add backend/pipeline/short_form_render.py
git commit -m "Refactor short_form_render to use first-scene audio"
```

---

## Task 2: Update Remotion `types.ts`

Drop `ShortIntroProps`. Update `ShortFormVideoProps` to carry top-level `stripped_title` and `segment_name` strings; the title card scene is just the first item in `scenes` (with `is_title_card: true`).

**Files:**
- Modify: `remotion/src/types.ts:141-159`

- [ ] **Step 1: Replace the short-form types section**

Find the section starting `// --- Short-form types ---` and replace from that comment through the end of `ShortFormVideoProps` with:

```typescript
// --- Short-form types ---

export interface ShortFormVideoProps {
  scenes: SceneInput[];          // first scene has is_title_card=true; rest are narration
  stripped_title: string;         // long-form video title with leading digits stripped
  segment_name: string;           // this segment's name (rendered with pop-in flourish)
  fps: number;
  width: number;                  // 1080
  height: number;                 // 1920
  subtitle_highlight?: SubtitleHighlightConfig | null;
}
```

- [ ] **Step 2: Run TypeScript check**

Run: `cd remotion && npx tsc --noEmit`
Expected: TypeScript errors will surface in `ShortFormVideo.tsx` and `ShortTitleCardScene.tsx` (those still use `ShortIntroProps`). That's expected — the next two tasks fix them.

- [ ] **Step 3: Commit**

```bash
git add remotion/src/types.ts
git commit -m "Drop ShortIntroProps; pass title and segment name as top-level props"
```

---

## Task 3: Rewrite `ShortTitleCardScene.tsx` for static + pop-in flourish

The new scene displays the stripped title statically from t=0 in the upper zone, then pops the segment name into the lower zone at `TITLE_CARD_BEAT_FRAMES` with a spring scale + glow burst. No word-by-word reveal, no `word_timestamps`, no em-dash logic.

**Files:**
- Rewrite: `remotion/src/scenes/ShortTitleCardScene.tsx`

- [ ] **Step 1: Replace the entire file**

```typescript
/**
 * ShortTitleCardScene — full-frame square image with darken/blur, plus
 * static stripped long-form title (upper zone) and pop-in segment name (lower zone).
 *
 * Zone 1 (upper half): stripped video title (smaller, secondary weight, white).
 * Appears instantly at t=0 and holds.
 * Zone 2 (lower half): segment name (larger, primary weight, accent color).
 * Pops in at TITLE_CARD_BEAT_FRAMES with spring scale + radial glow burst.
 */
import React from "react";
import { Img, useCurrentFrame, useVideoConfig, spring } from "remotion";
import { loadFont } from "@remotion/google-fonts/Inter";

const { fontFamily } = loadFont("normal", {
  weights: ["600", "800", "900"],
  subsets: ["latin"],
});

interface Props {
  stripped_title: string;
  segment_name: string;
  backdrop_image_path: string;
}

const ACCENT_COLOR = "#fbbf24"; // amber accent — matches existing aha-subtitle glow palette
const BACKDROP_FILTER = "blur(18px) brightness(0.45) saturate(0.7)";

// Beat before the segment name pops in (in seconds). Tunable visually.
const TITLE_CARD_BEAT_SECONDS = 0.5;
// Glow burst total duration (in seconds), from start of pop-in.
const GLOW_BURST_SECONDS = 0.4;

function clamp(value: number, min: number, max: number): number {
  return Math.min(max, Math.max(min, value));
}

export const ShortTitleCardScene: React.FC<Props> = ({
  stripped_title,
  segment_name,
  backdrop_image_path,
}) => {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();

  const popInStartFrame = Math.round(TITLE_CARD_BEAT_SECONDS * fps);
  const popAge = frame - popInStartFrame;

  // Segment-name spring scale: 0.6 -> 1.05 -> 1.0 (natural settle via Remotion spring)
  const segmentScale = spring({
    frame: Math.max(0, popAge),
    fps,
    config: { damping: 12, mass: 0.7, stiffness: 180, overshootClamping: false },
    from: 0.6,
    to: 1,
  });

  // Opacity 0 -> 1 over ~120ms (~3-4 frames at 30fps).
  const opacityFrames = Math.max(1, Math.round(0.12 * fps));
  const segmentOpacity = popAge < 0 ? 0 : clamp(popAge / opacityFrames, 0, 1);

  // Glow burst: scale 0.7 -> 1.4 + opacity 0.85 -> 0 across GLOW_BURST_SECONDS
  const glowFrames = Math.max(1, Math.round(GLOW_BURST_SECONDS * fps));
  const glowProgress = popAge < 0 ? 0 : clamp(popAge / glowFrames, 0, 1);
  const glowScale = 0.7 + glowProgress * 0.7; // 0.7 -> 1.4
  const glowOpacity = popAge < 0 ? 0 : (1 - glowProgress) * 0.85;

  return (
    <div
      style={{
        width: "100%",
        height: "100%",
        position: "relative",
        backgroundColor: "#000",
        overflow: "hidden",
      }}
    >
      {/* Full-frame square image backdrop */}
      {backdrop_image_path && (
        <Img
          src={backdrop_image_path}
          style={{
            position: "absolute",
            inset: 0,
            width: "100%",
            height: "100%",
            objectFit: "cover",
            filter: BACKDROP_FILTER,
            transform: "scale(1.05)",
          }}
        />
      )}

      {/* Zone 1: Stripped title (upper half) — static, on at t=0 */}
      <div
        style={{
          position: "absolute",
          top: 0,
          left: 0,
          width: "100%",
          height: "50%",
          display: "flex",
          alignItems: "center",
          justifyContent: "center",
          padding: "0 60px",
          boxSizing: "border-box",
        }}
      >
        <div
          style={{
            fontFamily,
            fontWeight: 600,
            fontSize: 64,
            lineHeight: 1.2,
            color: "#FFFFFF",
            textAlign: "center",
            letterSpacing: "0.005em",
            textShadow: "0 4px 16px rgba(0,0,0,0.7)",
          }}
        >
          {stripped_title}
        </div>
      </div>

      {/* Zone 2: Segment name (lower half) — pops in at TITLE_CARD_BEAT_FRAMES */}
      <div
        style={{
          position: "absolute",
          top: "50%",
          left: 0,
          width: "100%",
          height: "50%",
          display: "flex",
          alignItems: "center",
          justifyContent: "center",
          padding: "0 60px",
          boxSizing: "border-box",
        }}
      >
        {/* Glow burst (behind the text, pointer-events: none) */}
        <div
          style={{
            position: "absolute",
            inset: 0,
            display: "flex",
            alignItems: "center",
            justifyContent: "center",
            pointerEvents: "none",
            opacity: glowOpacity,
          }}
        >
          <div
            style={{
              width: "70%",
              height: "60%",
              transform: `scale(${glowScale})`,
              background:
                "radial-gradient(ellipse at center, rgba(251,191,36,0.55) 0%, rgba(251,191,36,0.25) 40%, rgba(251,191,36,0) 70%)",
              filter: "blur(8px)",
            }}
          />
        </div>

        {/* Segment name text */}
        <div
          style={{
            fontFamily,
            fontWeight: 900,
            fontSize: 110,
            lineHeight: 1.1,
            color: ACCENT_COLOR,
            textAlign: "center",
            letterSpacing: "-0.005em",
            textShadow: "0 6px 24px rgba(0,0,0,0.8)",
            opacity: segmentOpacity,
            transform: `scale(${popAge < 0 ? 0.6 : segmentScale})`,
          }}
        >
          {segment_name}
        </div>
      </div>
    </div>
  );
};
```

- [ ] **Step 2: Verify TypeScript still complains only in ShortFormVideo.tsx**

Run: `cd remotion && npx tsc --noEmit`
Expected: errors in `ShortFormVideo.tsx` (uses old `intro` prop). Will fix in Task 4.

- [ ] **Step 3: Commit**

```bash
git add remotion/src/scenes/ShortTitleCardScene.tsx
git commit -m "Rewrite ShortTitleCardScene with static title + pop-in flourish"
```

---

## Task 4: Update `ShortFormVideo.tsx` to use first-scene-is-title-card pattern

Drop the separate intro `Sequence` and the `<Audio src={intro.audio_path}>` element. The first scene (`is_title_card: true`) is rendered via `ShortTitleCardScene` using the new prop shape; subsequent scenes use `SceneRenderer` with `orientation="vertical"`. Audio for the title card scene is provided by the scene's own `audio_path` (handled inside `SceneRenderer` like any other scene).

**Files:**
- Modify: `remotion/src/ShortFormVideo.tsx`

- [ ] **Step 1: Replace the file's contents**

```typescript
/**
 * ShortFormVideo composition — sequences a single segment's scenes for 9:16
 * short-form export. The first scene (is_title_card=true) renders via
 * ShortTitleCardScene with the new vertical title-card layout. Remaining
 * scenes render via SceneRenderer with orientation="vertical".
 *
 * No chapter map, no global indicator bar, no segment timer/counter
 * (those are long-form-only).
 */
import React from "react";
import { Audio, Sequence } from "remotion";
import type { ShortFormVideoProps } from "./types";
import { SceneRenderer } from "./scenes/SceneRenderer";
import { ShortTitleCardScene } from "./scenes/ShortTitleCardScene";
import { secondsToFrames } from "./utils/timing";

export const ShortFormVideo: React.FC<ShortFormVideoProps> = ({
  scenes,
  stripped_title,
  segment_name,
  fps,
  subtitle_highlight,
}) => {
  const sequences: React.ReactNode[] = [];
  let currentFrame = 0;

  for (let i = 0; i < scenes.length; i++) {
    const scene = scenes[i];
    const durationFrames = Math.max(fps, secondsToFrames(scene.duration_seconds, fps));

    if (i === 0 && scene.is_title_card) {
      sequences.push(
        <Sequence
          key={scene.id}
          from={currentFrame}
          durationInFrames={durationFrames}
          name={`Title card: ${scene.id}`}
        >
          <ShortTitleCardScene
            stripped_title={stripped_title}
            segment_name={segment_name}
            backdrop_image_path={scene.image_path ?? ""}
          />
          {scene.audio_path && <Audio src={scene.audio_path} volume={1} />}
        </Sequence>,
      );
      currentFrame += durationFrames;
      continue;
    }

    sequences.push(
      <Sequence
        key={scene.id}
        from={currentFrame}
        durationInFrames={durationFrames}
        name={`Scene ${i + 1}: ${scene.id}`}
      >
        <SceneRenderer
          scene={{
            ...scene,
            transition_out: scenes[i + 1]?.transition_in ?? "cut",
          }}
          highlightEnabled={subtitle_highlight?.enabled ?? false}
          orientation="vertical"
        />
      </Sequence>,
    );

    currentFrame += durationFrames;
  }

  return (
    <div style={{ width: "100%", height: "100%", backgroundColor: "#000" }}>
      {sequences}
    </div>
  );
};
```

- [ ] **Step 2: Verify TypeScript compiles cleanly**

Run: `cd remotion && npx tsc --noEmit`
Expected: PASS (no errors). If the `ShortFormVideo` composition's `calculateMetadata` in `Root.tsx` still references `intro.duration_seconds`, fix it in this same task.

- [ ] **Step 3: Check `Root.tsx` for stale `calculateMetadata` references to `intro`**

Run: `grep -n "intro" remotion/src/Root.tsx`
Expected: only references that are unrelated to short-form intros, OR references inside the `ShortFormVideo` composition's `calculateMetadata` that need updating.

If `Root.tsx`'s `ShortFormVideo` composition references `props.intro.duration_seconds`, replace that block. Find:

```typescript
calculateMetadata={({ props }) => {
  const p = props as unknown as ShortFormVideoProps;
  const sceneSeconds = p.scenes.reduce(...);
  const totalSeconds = p.intro.duration_seconds + sceneSeconds;
  return {
    durationInFrames: Math.max(1, Math.ceil(totalSeconds * p.fps)),
    fps: p.fps, width: p.width, height: p.height,
  };
}}
```

Replace with:

```typescript
calculateMetadata={({ props }) => {
  const p = props as unknown as ShortFormVideoProps;
  const totalSeconds = p.scenes.reduce(
    (acc, s) => acc + (s.duration_seconds ?? 0),
    0,
  );
  return {
    durationInFrames: Math.max(1, Math.ceil(totalSeconds * p.fps)),
    fps: p.fps,
    width: p.width,
    height: p.height,
  };
}}
```

Also update any `defaultProps={...}` for the `ShortFormVideo` composition: remove the `intro` field; add `stripped_title: ""` and `segment_name: ""`.

- [ ] **Step 4: Re-verify TypeScript**

Run: `cd remotion && npx tsc --noEmit`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add remotion/src/ShortFormVideo.tsx remotion/src/Root.tsx
git commit -m "ShortFormVideo: render first scene as title card, drop separate intro"
```

---

## Task 5: Refactor `api/short_form.py` to drop intros endpoints

Remove all intros generation endpoints, the `_persist_intros` helper, the `_validate_intros_present` helper, the imports from `short_form_intros`, and the `force` validation logic. Keep render endpoints (`/render/all`, `/render/one`) and the shared `/jobs/{job_id}` polling endpoint.

**Files:**
- Modify: `backend/api/short_form.py`

- [ ] **Step 1: Replace the file's contents**

```python
"""Short-form export endpoints — per-segment renders only.

Intros (per-segment voiceover generation) were removed in favor of reusing
each segment's existing first-scene narration audio (which already names the
segment). See docs/superpowers/specs/2026-05-15-short-form-export-design.md.
"""

import json
import logging

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlmodel import Session

from database import get_session
from models.script import Script, ScriptContent
from pipeline.render_jobs import (
    create_job,
    get_job,
    run_in_background,
    update_job,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/short-form", tags=["short-form"])


# --- Request / Response schemas ---


class JobResponse(BaseModel):
    job_id: str


class JobStatusResponse(BaseModel):
    job_id: str
    status: str
    progress: float
    current_step: str
    output_urls: list[str]
    error: str | None = None
    estimated_seconds: float | None = None
    elapsed_seconds: float | None = None


class RenderShortAllRequest(BaseModel):
    script_id: str


class RenderShortOneRequest(BaseModel):
    script_id: str
    segment_idx: int


# --- Helpers ---


def _load_content(session: Session, script_id: str) -> ScriptContent:
    record = session.get(Script, script_id)
    if not record:
        raise HTTPException(status_code=404, detail="Script not found")
    return ScriptContent.model_validate(json.loads(record.script_json))


# --- Endpoints ---


@router.get("/jobs/{job_id}", response_model=JobStatusResponse)
def job_status(job_id: str):
    """Poll a short-form render job."""
    job = get_job(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    return JobStatusResponse(**job.to_dict())


@router.post("/render/all", response_model=JobResponse)
def start_render_all_shorts(
    body: RenderShortAllRequest, session: Session = Depends(get_session)
):
    """Render all per-segment shorts in the background."""
    from pipeline.short_form_render import render_all_shorts

    content = _load_content(session, body.script_id)

    record = session.get(Script, body.script_id)
    project_title = record.topic_title or "Untitled"
    total = len(content.segments)

    job = create_job(scene_count=total)
    logger.info("Starting render-all-shorts for script %s (%d segments)", body.script_id, total)

    def do_render():
        def on_progress(p: float, msg: str):
            update_job(job.id, progress=p, current_step=msg)

        results = render_all_shorts(
            script_id=body.script_id,
            content=content,
            project_title=project_title,
            on_progress=on_progress,
        )
        for _web_url, downloads_path in results:
            job.output_urls.append(downloads_path)
        update_job(job.id, progress=1.0, current_step="All shorts rendered")
        return ""

    run_in_background(job.id, do_render)
    return JobResponse(job_id=job.id)


@router.post("/render/one", response_model=JobResponse)
def start_render_one_short(
    body: RenderShortOneRequest, session: Session = Depends(get_session)
):
    """Render a single segment's short in the background."""
    from pipeline.short_form_render import render_short_segment

    content = _load_content(session, body.script_id)
    if body.segment_idx < 0 or body.segment_idx >= len(content.segments):
        raise HTTPException(status_code=400, detail="segment_idx out of range")

    record = session.get(Script, body.script_id)
    project_title = record.topic_title or "Untitled"

    job = create_job(scene_count=1)
    logger.info(
        "Starting render-one-short for script %s segment %d",
        body.script_id, body.segment_idx,
    )

    def do_render():
        def on_progress(p: float, msg: str):
            update_job(job.id, progress=p, current_step=msg)

        _web_url, downloads_path = render_short_segment(
            script_id=body.script_id,
            segment_idx=body.segment_idx,
            content=content,
            project_title=project_title,
            on_progress=on_progress,
        )
        job.output_urls.append(downloads_path)
        update_job(job.id, progress=1.0, current_step="Short rendered")
        return downloads_path

    run_in_background(job.id, do_render)
    return JobResponse(job_id=job.id)
```

- [ ] **Step 2: Verify the import-free state by starting the backend**

Run: `cd backend && uv run python -c "from api.short_form import router; print('OK', router.prefix)"`
Expected: prints `OK /api/short-form`

- [ ] **Step 3: Commit**

```bash
git add backend/api/short_form.py
git commit -m "Drop short-form intros endpoints; keep render endpoints"
```

---

## Task 6: Delete `pipeline/short_form_intros.py` and its test

The module is no longer imported anywhere (Task 1 moved `strip_leading_number` into `short_form_render.py`; Task 5 removed the API import).

**Files:**
- Delete: `backend/pipeline/short_form_intros.py`
- Delete: `backend/tests/pipeline/test_short_form_intros.py`

- [ ] **Step 1: Verify no imports remain**

Run: `grep -rn "short_form_intros\|from pipeline.short_form_intros\|import short_form_intros" backend/ 2>/dev/null`
Expected: no results.

- [ ] **Step 2: Delete the files**

```bash
rm backend/pipeline/short_form_intros.py backend/tests/pipeline/test_short_form_intros.py
```

- [ ] **Step 3: Run the backend test suite to confirm nothing broke**

Run: `cd backend && uv run pytest tests/pipeline/ -v`
Expected: PASS (no import errors).

- [ ] **Step 4: Commit**

```bash
git add -A backend/pipeline/short_form_intros.py backend/tests/pipeline/test_short_form_intros.py
git commit -m "Delete unused short_form_intros pipeline and test"
```

---

## Task 7: Drop `ShortIntro` model and `short_intros` field from `models/script.py`

The model and field are no longer used by any code path. Removing them avoids carrying dead schema in `script_json` blobs.

**Files:**
- Modify: `backend/models/script.py:75-90` (the `ShortIntro` class)
- Modify: `backend/models/script.py:142` (the `short_intros` field on `ScriptContent`)

- [ ] **Step 1: Read the file and locate the exact lines**

Run: `grep -n "class ShortIntro\|short_intros" backend/models/script.py`
Expected: shows the class definition and the field on `ScriptContent`.

- [ ] **Step 2: Delete the `ShortIntro` class**

Edit `backend/models/script.py` and remove the entire `class ShortIntro(BaseModel):` block (the class plus its field annotations and any blank line separator that came with it).

- [ ] **Step 3: Delete the `short_intros` field from `ScriptContent`**

In `ScriptContent`, remove the line:

```python
    short_intros: list[ShortIntro] | None = None  # Generated by short-form export flow; None until first generation
```

- [ ] **Step 4: Verify no remaining `ShortIntro` references**

Run: `grep -rn "ShortIntro\|short_intros" backend/ 2>/dev/null | grep -v __pycache__ | grep -v ".pyc"`
Expected: no results.

- [ ] **Step 5: Run pytest to confirm nothing else breaks**

Run: `cd backend && uv run pytest tests/ -v`
Expected: PASS.

- [ ] **Step 6: Commit**

```bash
git add backend/models/script.py
git commit -m "Drop ShortIntro model and short_intros field"
```

---

## Task 8: Update `tests/pipeline/test_short_form_render.py` with `strip_leading_number` tests

Move the `strip_leading_number` test cases that lived in the deleted `test_short_form_intros.py` into the render module's test file (since the helper now lives there).

**Files:**
- Modify: `backend/tests/pipeline/test_short_form_render.py`

- [ ] **Step 1: Append `strip_leading_number` tests to the file**

Open `backend/tests/pipeline/test_short_form_render.py` and append:

```python
from pipeline.short_form_render import strip_leading_number


class TestStripLeadingNumber:
    def test_strips_single_digit_and_space(self):
        assert strip_leading_number("8 Unsolved Crimes") == "Unsolved Crimes"

    def test_strips_multi_digit_and_space(self):
        assert strip_leading_number("100 Things You Didn't Know") == "Things You Didn't Know"

    def test_no_change_when_no_leading_digits(self):
        assert strip_leading_number("How to Train Your Dragon") == "How to Train Your Dragon"

    def test_no_change_when_digits_not_followed_by_whitespace(self):
        assert strip_leading_number("8Track Memories") == "8Track Memories"

    def test_strips_with_multiple_whitespace(self):
        assert strip_leading_number("8  Two Spaces") == "Two Spaces"

    def test_empty_string(self):
        assert strip_leading_number("") == ""
```

- [ ] **Step 2: Run the tests**

Run: `cd backend && uv run pytest tests/pipeline/test_short_form_render.py -v`
Expected: all tests PASS, including the new `TestStripLeadingNumber` class.

- [ ] **Step 3: Commit**

```bash
git add backend/tests/pipeline/test_short_form_render.py
git commit -m "Test strip_leading_number in its new home"
```

---

## Task 9: Drop frontend `ShortIntro` type and `short_intros` field references

**Files:**
- Modify: `frontend/src/types/render.ts:69` (the `ShortIntro` interface)
- Modify: `frontend/src/types/script.ts:101` (the `short_intros` field reference)
- Possibly: `frontend/src/types/render.ts` `ShortFormJobStatus` if it references intro-only fields

- [ ] **Step 1: Locate the type definitions**

Run: `grep -n "ShortIntro\|short_intros" frontend/src/types/render.ts frontend/src/types/script.ts`

- [ ] **Step 2: Delete the `ShortIntro` interface from `render.ts`**

Open `frontend/src/types/render.ts`, remove the `export interface ShortIntro { ... }` block in its entirety (lines around :69 — read the file to get exact bounds).

- [ ] **Step 3: Inspect `ShortFormJobStatus` for any intro-only fields**

If `ShortFormJobStatus` only contains generic render-job fields (`job_id`, `status`, `progress`, `current_step`, `output_urls`, `error`, `estimated_seconds`, `elapsed_seconds`), leave it as-is (the `/api/short-form/jobs/{id}` endpoint still uses this shape for renders). If it has intro-specific fields (e.g., `display_text`, `intros: ShortIntro[]`), remove those.

- [ ] **Step 4: Delete the `short_intros` field reference from `script.ts`**

Open `frontend/src/types/script.ts` and remove the line:

```typescript
  short_intros?: import("./render").ShortIntro[] | null;
```

- [ ] **Step 5: Run TypeScript build to surface remaining usages**

Run: `cd frontend && npx tsc --noEmit`
Expected: errors point to consumers (`ShortFormTab.tsx`, `ShortFormStatusPill.tsx`, `ExportPanel.tsx`, `TimelinePage.tsx`, `ShortIntrosCard.tsx`, `RenderShortsCard.tsx`, `api.ts`). Tasks 10-15 fix these.

- [ ] **Step 6: Commit**

```bash
git add frontend/src/types/render.ts frontend/src/types/script.ts
git commit -m "Drop ShortIntro frontend type and short_intros field"
```

---

## Task 10: Drop intros functions from `frontend/src/api.ts`

**Files:**
- Modify: `frontend/src/api.ts:680-700` (approx — the intro generation functions)

- [ ] **Step 1: Locate the functions**

Run: `grep -n "generateShortIntros\|generateShortIntroOne\|generateShortIntrosAll" frontend/src/api.ts`

- [ ] **Step 2: Remove `generateShortIntrosAll` and `generateShortIntroOne`**

Open `frontend/src/api.ts`. Find and delete the two functions:

```typescript
export async function generateShortIntrosAll(
  scriptId: string,
  force = false,
): Promise<{ job_id: string }> {
  const res = await api.post("/api/short-form/intros/generate-all", { script_id: scriptId, force });
  if (!res.ok) throw new Error(res.error || "Failed to start intro generation");
  return res.data as { job_id: string };
}

export async function generateShortIntroOne(
  scriptId: string,
  segmentIdx: number,
): Promise<{ job_id: string }> {
  const res = await api.post("/api/short-form/intros/generate-one", { script_id: scriptId, segment_idx: segmentIdx });
  if (!res.ok) throw new Error(res.error || "Failed to start intro regen");
  return res.data as { job_id: string };
}
```

(The exact bodies may differ slightly — delete whatever the current implementations are, keeping only `renderShortAll`, `renderShortOne`, `getShortFormJobStatus`.)

- [ ] **Step 3: Verify TypeScript**

Run: `cd frontend && npx tsc --noEmit`
Expected: errors only in `ShortIntrosCard.tsx` (calls these now-deleted functions) and any other intros-related component. That's expected.

- [ ] **Step 4: Commit**

```bash
git add frontend/src/api.ts
git commit -m "Drop generateShortIntros API client functions"
```

---

## Task 11: Delete `ShortIntrosCard.tsx`

**Files:**
- Delete: `frontend/src/components/timeline/short-form/ShortIntrosCard.tsx`

- [ ] **Step 1: Verify no other consumer (besides `ShortFormTab.tsx`)**

Run: `grep -rn "ShortIntrosCard" frontend/src/ 2>/dev/null`
Expected: only `ShortFormTab.tsx` imports it. (Task 12 removes that import.)

- [ ] **Step 2: Delete the file**

```bash
rm frontend/src/components/timeline/short-form/ShortIntrosCard.tsx
```

- [ ] **Step 3: Commit**

```bash
git add -A frontend/src/components/timeline/short-form/ShortIntrosCard.tsx
git commit -m "Delete ShortIntrosCard"
```

---

## Task 12: Simplify `RenderShortsCard.tsx` — drop gating, modal, "introsReady"

The card always allows rendering. No "Generate intros first" warning, no confirmation modal, no `gate()` wrapper.

**Files:**
- Modify: `frontend/src/components/timeline/short-form/RenderShortsCard.tsx`

- [ ] **Step 1: Replace the file's contents**

```typescript
import { useState } from "react";
import {
  getShortFormJobStatus,
  renderShortAll,
  renderShortOne,
  showInFolder,
} from "../../../api";
import { usePollJob } from "../../../hooks/usePollJob";
import type { ShortFormJobStatus } from "../../../types/render";

interface Props {
  scriptId: string;
  segments: { name: string }[];
  /**
   * Map of segment_idx -> path string.
   * Values set by the disk probe are web-relative paths (/static/…).
   * Values set after a render are absolute filesystem paths to the Downloads copy.
   * Show in Finder is only shown for filesystem paths (not /static/… probe values).
   */
  renderedUrls: Record<number, string | undefined>;
  onRenderComplete: (segmentIdx: number, url: string) => void;
}

export default function RenderShortsCard({
  scriptId,
  segments,
  renderedUrls,
  onRenderComplete,
}: Props) {
  const [busy, setBusy] = useState(false);
  const [status, setStatus] = useState<ShortFormJobStatus | null>(null);
  const [busySegment, setBusySegment] = useState<number | null>(null);
  const [currentOp, setCurrentOp] = useState<"all" | number | null>(null);

  const total = segments.length;
  const renderedCount = Object.values(renderedUrls).filter(Boolean).length;
  const allDone = renderedCount === total && total > 0;

  const { startPolling } = usePollJob<ShortFormJobStatus>({
    pollFn: (id) => getShortFormJobStatus(id),
    isComplete: (s) => s.status === "completed",
    isFailed: (s) => s.status === "failed",
    onStatus: (s) => {
      setStatus(s);
      if (s.status === "completed" || s.status === "failed") {
        setBusy(false);
        setBusySegment(null);
        setCurrentOp((op) => {
          if (s.status === "completed") {
            if (op === "all") {
              (s.output_urls ?? []).forEach((url, i) => onRenderComplete(i, url));
            } else if (typeof op === "number") {
              const url = s.output_urls?.[0];
              if (url) onRenderComplete(op, url);
            }
          }
          return null;
        });
      }
    },
    onConnectionLost: () => {
      setBusy(false);
      setBusySegment(null);
      setCurrentOp(null);
    },
  });

  async function handleRenderAll() {
    setBusy(true);
    setCurrentOp("all");
    const { job_id } = await renderShortAll(scriptId);
    startPolling(job_id);
  }

  async function handleRenderOne(idx: number) {
    setBusySegment(idx);
    setCurrentOp(idx);
    const { job_id } = await renderShortOne(scriptId, idx);
    startPolling(job_id);
  }

  return (
    <section className="bg-neutral-900 border border-neutral-800 rounded-xl p-4 space-y-3">
      <header className="flex items-center justify-between">
        <div>
          <h3 className="text-sm font-semibold text-neutral-200">Render Shorts</h3>
          <p
            className={`text-xs ${
              allDone ? "text-emerald-400" : "text-neutral-500"
            }`}
          >
            {`${renderedCount}/${total} rendered`}
          </p>
        </div>
        <button
          onClick={handleRenderAll}
          disabled={busy || busySegment !== null}
          className="text-sm px-3 py-1.5 bg-violet-600 hover:bg-violet-500 disabled:opacity-40 rounded-lg font-medium transition-colors"
        >
          {busy ? "Rendering..." : `Render All ${total} Shorts`}
        </button>
      </header>

      {busy && status && (
        <div className="space-y-1">
          <div className="flex justify-between text-xs text-neutral-400">
            <span>{status.current_step || "Rendering..."}</span>
            <span>{Math.round((status.progress || 0) * 100)}%</span>
          </div>
          <div className="w-full h-1.5 bg-neutral-800 rounded-full overflow-hidden">
            <div
              className="h-full bg-violet-500 transition-all duration-300"
              style={{ width: `${Math.max((status.progress || 0) * 100, 1)}%` }}
            />
          </div>
        </div>
      )}

      <ul className="divide-y divide-neutral-800">
        {segments.map((seg, idx) => {
          const url = renderedUrls[idx];
          const segBusy = busySegment === idx;
          return (
            <li key={idx} className="py-2 flex items-center gap-3">
              <div className="w-6 text-xs text-neutral-500 text-center">{idx + 1}</div>
              <div className="flex-1 min-w-0">
                <p className="text-sm text-neutral-200 truncate">{seg.name}</p>
              </div>
              {url && !url.startsWith("/static/") && (
                <button
                  onClick={() => showInFolder(url)}
                  className="text-xs px-2.5 py-1 bg-neutral-800 hover:bg-neutral-700 rounded text-neutral-300 transition-colors"
                >
                  Show in Finder
                </button>
              )}
              <button
                onClick={() => handleRenderOne(idx)}
                disabled={busy || busySegment !== null}
                className="text-xs px-2.5 py-1 bg-violet-600 hover:bg-violet-500 disabled:opacity-40 rounded text-white transition-colors"
              >
                {segBusy ? "..." : url ? "Re-render" : "Render"}
              </button>
            </li>
          );
        })}
      </ul>
    </section>
  );
}
```

- [ ] **Step 2: Verify TypeScript**

Run: `cd frontend && npx tsc --noEmit`
Expected: errors only in `ShortFormTab.tsx` (still passes the now-removed props). Fixed in Task 13.

- [ ] **Step 3: Commit**

```bash
git add frontend/src/components/timeline/short-form/RenderShortsCard.tsx
git commit -m "Remove intros gating and confirmation modal from RenderShortsCard"
```

---

## Task 13: Simplify `ShortFormTab.tsx`

Drop `intros`, `onIntrosChanged`, the `ShortIntrosCard` mount, `introsRef`, and the `onRequestGenerateIntros` callback. Keep the rendered-URLs disk probe.

**Files:**
- Modify: `frontend/src/components/timeline/short-form/ShortFormTab.tsx`

- [ ] **Step 1: Replace the file's contents**

```typescript
import { useEffect, useState } from "react";
import { assetUrl } from "../../../api";
import RenderShortsCard from "./RenderShortsCard";

interface Props {
  scriptId: string;
  segments: { name: string }[];
  initialRenderedUrls?: Record<number, string | undefined>;
}

export default function ShortFormTab({
  scriptId,
  segments,
  initialRenderedUrls,
}: Props) {
  const [renderedUrls, setRenderedUrls] = useState<Record<number, string | undefined>>(
    initialRenderedUrls ?? {},
  );

  useEffect(() => {
    let cancelled = false;
    async function probe() {
      const found: Record<number, string | undefined> = {};
      for (let i = 0; i < segments.length; i++) {
        const path = `/static/projects/${scriptId}/renders/shorts/${i}.mp4`;
        try {
          const r = await fetch(assetUrl(path), { method: "HEAD" });
          if (r.ok) found[i] = path;
        } catch {
          /* ignore */
        }
      }
      if (!cancelled) setRenderedUrls((prev) => ({ ...prev, ...found }));
    }
    probe();
    return () => {
      cancelled = true;
    };
  }, [scriptId, segments.length]);

  return (
    <div className="space-y-4">
      <p className="text-xs text-neutral-500">
        Renders {segments.length} short form videos, one per segment. 1080×1920 9:16 30FPS.
      </p>

      <RenderShortsCard
        scriptId={scriptId}
        segments={segments}
        renderedUrls={renderedUrls}
        onRenderComplete={(idx, url) =>
          setRenderedUrls((prev) => ({ ...prev, [idx]: url }))
        }
      />
    </div>
  );
}
```

- [ ] **Step 2: Verify TypeScript**

Run: `cd frontend && npx tsc --noEmit`
Expected: errors point to `ExportPanel.tsx` (still passes intro props to `ShortFormTab`). Fixed in Task 16.

- [ ] **Step 3: Commit**

```bash
git add frontend/src/components/timeline/short-form/ShortFormTab.tsx
git commit -m "Simplify ShortFormTab to single render card"
```

---

## Task 14: Simplify `ShortFormStatusPill.tsx`

Drop `intros` prop. Show only `"Short Form: X/N rendered"`.

**Files:**
- Modify: `frontend/src/components/timeline/short-form/ShortFormStatusPill.tsx`

- [ ] **Step 1: Read the current file**

Run: `cat frontend/src/components/timeline/short-form/ShortFormStatusPill.tsx`

- [ ] **Step 2: Replace the contents**

```typescript
import { useEffect, useState } from "react";
import { assetUrl } from "../../../api";

interface Props {
  scriptId: string;
  segmentCount: number;
  onClick: () => void;
}

export default function ShortFormStatusPill({
  scriptId,
  segmentCount,
  onClick,
}: Props) {
  const [renderedCount, setRenderedCount] = useState(0);

  useEffect(() => {
    let cancelled = false;
    async function probe() {
      let count = 0;
      for (let i = 0; i < segmentCount; i++) {
        const path = `/static/projects/${scriptId}/renders/shorts/${i}.mp4`;
        try {
          const r = await fetch(assetUrl(path), { method: "HEAD" });
          if (r.ok) count++;
        } catch {
          /* ignore */
        }
      }
      if (!cancelled) setRenderedCount(count);
    }
    probe();
    return () => {
      cancelled = true;
    };
  }, [scriptId, segmentCount]);

  return (
    <button
      onClick={onClick}
      title="Open short-form export"
      className="text-xs px-2.5 py-1 bg-neutral-800 hover:bg-neutral-700 rounded text-neutral-300 transition-colors"
    >
      Short Form: {renderedCount}/{segmentCount} rendered
    </button>
  );
}
```

- [ ] **Step 3: Verify TypeScript**

Run: `cd frontend && npx tsc --noEmit`
Expected: errors point to `TimelinePage.tsx` (still passes `intros={...}` prop). Fixed in Task 16.

- [ ] **Step 4: Commit**

```bash
git add frontend/src/components/timeline/short-form/ShortFormStatusPill.tsx
git commit -m "Status pill shows only render count, drops intros tracking"
```

---

## Task 15: Update `ExportPanel.tsx` — drop `shortIntros` / `onShortIntrosChanged`

**Files:**
- Modify: `frontend/src/components/timeline/ExportPanel.tsx`

- [ ] **Step 1: Locate the prop in the type**

Run: `grep -n "shortIntros\|onShortIntrosChanged\|ShortIntro" frontend/src/components/timeline/ExportPanel.tsx`

- [ ] **Step 2: Remove the import of `ShortIntro`**

In the line:

```typescript
import type { ExportBundleResponse, RenderStatusResponse, SEOMetadata, ThumbnailConcept, ShortIntro } from "../../types/render";
```

Remove `, ShortIntro`:

```typescript
import type { ExportBundleResponse, RenderStatusResponse, SEOMetadata, ThumbnailConcept } from "../../types/render";
```

- [ ] **Step 3: Remove the props from the interface**

Find:

```typescript
  shortIntros: ShortIntro[] | null | undefined;
  onShortIntrosChanged: () => void;
```

Delete both lines.

- [ ] **Step 4: Remove from the destructure in the component**

Find the destructure block (around line 259) and remove `shortIntros,` and `onShortIntrosChanged,`.

- [ ] **Step 5: Update the `<ShortFormTab>` mount (around line 522)**

Find:

```tsx
<ShortFormTab
  scriptId={scriptId}
  videoTitle={videoTitle}
  segments={segments}
  intros={shortIntros}
  onIntrosChanged={onShortIntrosChanged}
  hookSceneCount={hookSceneCount}
/>
```

Replace with:

```tsx
<ShortFormTab
  scriptId={scriptId}
  segments={segments}
/>
```

(The `videoTitle` and `hookSceneCount` props are no longer used by `ShortFormTab`; if either is used elsewhere in `ExportPanel.tsx`, leave that elsewhere usage alone.)

- [ ] **Step 6: Verify TypeScript**

Run: `cd frontend && npx tsc --noEmit`
Expected: errors only in `TimelinePage.tsx` (still passes `shortIntros` to `<ExportPanel>`). Fixed in Task 16.

- [ ] **Step 7: Commit**

```bash
git add frontend/src/components/timeline/ExportPanel.tsx
git commit -m "Drop shortIntros props from ExportPanel"
```

---

## Task 16: Update `TimelinePage.tsx` — drop intros plumbing

**Files:**
- Modify: `frontend/src/components/timeline/TimelinePage.tsx`

- [ ] **Step 1: Locate the references**

Run: `grep -n "short_intros\|shortIntros\|onShortIntrosChanged\|ShortFormStatusPill" frontend/src/components/timeline/TimelinePage.tsx`

- [ ] **Step 2: Update the `<ShortFormStatusPill>` mount**

Find (around line 1084):

```tsx
<ShortFormStatusPill
  scriptId={scriptId}
  intros={state.content.short_intros}
  segmentCount={state.content.segments.length}
  onClick={openExportOnShortForm}
/>
```

Replace with:

```tsx
<ShortFormStatusPill
  scriptId={scriptId}
  segmentCount={state.content.segments.length}
  onClick={openExportOnShortForm}
/>
```

- [ ] **Step 3: Update the `<ExportPanel>` mount**

Find (around line 1463):

```tsx
shortIntros={state.content.short_intros}
onShortIntrosChanged={async () => {
  // ... existing reload-content logic
}}
```

Delete those two lines (and the surrounding multi-line callback body if present).

- [ ] **Step 4: Verify no remaining references**

Run: `grep -n "short_intros\|shortIntros\|onShortIntrosChanged" frontend/src/components/timeline/TimelinePage.tsx`
Expected: no results.

- [ ] **Step 5: Verify TypeScript across the whole frontend**

Run: `cd frontend && npx tsc --noEmit`
Expected: PASS (no errors).

- [ ] **Step 6: Run the frontend build**

Run: `cd frontend && npm run build`
Expected: build succeeds.

- [ ] **Step 7: Commit**

```bash
git add frontend/src/components/timeline/TimelinePage.tsx
git commit -m "Drop short_intros plumbing from TimelinePage"
```

---

## Task 17: End-to-end verification

The plan has touched backend, Remotion, and frontend code. Verify the full path manually before declaring done.

- [ ] **Step 1: Start the dev environment**

Run: `npm run dev`
Expected: backend on :8420, frontend on :5173, Electron window opens.

- [ ] **Step 2: Open an existing project with at least one segment that has a generated long-form audio**

In the Electron app, open a project from the dashboard that has been through the long-form generate-everything flow at least once (so each segment's first scene has audio + the per-segment `title_card_{idx}.png` exists).

- [ ] **Step 3: Open Export panel, navigate to "Render - Short Form" tab**

Verify:
- Tab is visible and labeled correctly.
- A single "Render Shorts" card shows (no "Short Form Intros" card above it).
- The card shows `"0/N rendered"` if no shorts have been rendered yet.
- No warning banner about generating intros.

- [ ] **Step 4: Click "Render All N Shorts"**

Verify:
- A progress bar appears.
- Backend logs (in terminal) show no errors about `short_form_intros`, no `_intro_audio_path`, no `_validate_intros_present`.
- Backend logs show "Starting render-all-shorts" followed by per-segment Remotion runs.

- [ ] **Step 5: When the render completes, verify the output files**

Run: `ls ~/Downloads/{project name}/`
Expected: N MP4 files matching `[short form 1∕N] {project name}.mp4` ... `[short form N∕N] {project name}.mp4`.

Run: `ffprobe -v error -select_streams v:0 -show_entries stream=width,height,r_frame_rate -of default=noprint_wrappers=1 ~/Downloads/{project\ name}/\[short\ form\ 1∕N\]\ {project\ name}.mp4`
Expected: `width=1080`, `height=1920`, `r_frame_rate=30/1`.

- [ ] **Step 6: Open one of the rendered shorts in a video player**

Verify visually:
- Title card opens with the stripped long-form title visible at top instantly.
- After ~0.5s, the segment name pops into the lower zone with the spring + glow animation.
- Audio is the segment's existing first-scene narration (typically `"Welcome to {segment name}."` or similar).
- After the title card scene ends, the short transitions into the segment's narration scenes with the vertical layout.
- No reference to a new "{stripped title} — {segment name}" voiceover exists (the audio is exclusively the existing scene narration).

- [ ] **Step 7: Verify no new audio files were generated**

Run: `ls data/projects/{script_id}/audio/short_intro_*.mp3 2>/dev/null`
Expected: no results (no `short_intro_N.mp3` files were created during render).

- [ ] **Step 8: Final commit (if any cleanup edits were made during verification)**

If steps 1-7 all pass without code changes, no commit needed. Otherwise:

```bash
git add -A
git commit -m "Fix issues found during short-form e2e verification"
```

- [ ] **Step 9: Report completion**

Verification complete. Short-form export now reuses existing scene audio with a static title + pop-in flourish. No new ElevenLabs calls.

---

## Notes for the implementer

- **Order matters.** Backend types are dropped only after Remotion + frontend stop referencing them. Tasks 7-9 happen after Tasks 1-6 land.
- **Each task is independently committable** — TypeScript / Python may surface errors in *consumer* files between tasks; that's expected and called out per task.
- **Tests are intentionally light.** Most of this work is deletion + rewrite of a partially-built feature. The new pop-in animation logic in `ShortTitleCardScene.tsx` is visual and inherently hard to unit test; it's verified manually in Task 17. The `strip_leading_number` helper has unit tests in Task 8.
- **Don't add backwards-compatibility shims.** When dropping `ShortIntro` from `ScriptContent`, existing `script_json` blobs that contain `short_intros: [...]` will simply have that field ignored on next load (Pydantic discards unknown fields by default if `model_config = ConfigDict(extra="ignore")` — verify this is the project's default; if it's `extra="forbid"`, the field needs explicit removal logic, but that's out of scope).
- **Hook detection becomes a graceful no-op.** Previously, `content.hook_scene_count` was computed and persisted as a side-effect of the intros-generation flow (in `api/short_form.py`'s `_persist_intros`). After this plan, nothing populates it during short-form rendering. Task 1 keeps the `if segment_idx == 0 and content.hook_scene_count` skip branch, so it still works for scripts where the field is already set, but newly created scripts won't auto-detect hooks. Restoring hook detection (e.g., as a dedicated endpoint or part of script generation) is out of scope here — flag it in the e2e verification report if short #1's intro feels too long.
