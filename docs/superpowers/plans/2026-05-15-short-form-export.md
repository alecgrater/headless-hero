# Short Form Export Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a "Render - Short Form" tab that exports each of the project's 8 segments as a standalone 1080×1920 vertical short-form video (TikTok / Reels / Shorts), with each scene re-laid-out natively for 9:16 and a redesigned title card that uses a freshly generated ElevenLabs voiceover.

**Architecture:**

- **Backend.** A new `ShortIntro` model is added to `ScriptContent` (one per segment). A pipeline module `short_form_intros.py` generates per-segment intro VOs via ElevenLabs. A pipeline module `short_form_render.py` renders one or all shorts via Remotion (composition `ShortFormVideo`) using the existing render-job infrastructure. API routes mirror the existing `/api/voice/...` and `/api/render/...` patterns.
- **Remotion.** A new composition `ShortFormVideo` (1080×1920) sequences a `ShortTitleCardScene` then each segment scene wrapped in a new `VerticalSceneLayout`. The vertical layout renders blurred-dim copies of the focal image as top/bottom bands, a clean image in the middle, Eli top-center, and subtitles in the bottom band. `SubtitleScene` and `EliOverlay` accept an `orientation` prop.
- **Frontend.** A new tab `"Render - Short Form"` in `ExportPanel` mounts a `ShortFormTab` with two stacked cards: `ShortIntrosCard` (gate) and `RenderShortsCard` (renders). A `ShortFormStatusPill` is added to the Timeline page header.

**Tech Stack:** Python 3.12 + FastAPI + SQLModel (backend) · React 19 + TypeScript + Tailwind 4 (frontend) · Remotion 4 (renderer) · ElevenLabs TTS · pytest (backend tests)

**Spec:** `docs/superpowers/specs/2026-05-15-short-form-export-design.md`

---

## File Structure

### Created

**Backend**
- `backend/pipeline/short_form_intros.py` — Intro VO generation pipeline (ElevenLabs orchestration + display-text building).
- `backend/pipeline/short_form_render.py` — Remotion render orchestration for one/all shorts.
- `backend/api/short_form.py` — Router for intro + render endpoints (kept separate from `voiceover.py` / `render.py` for cohesion).
- `backend/tests/pipeline/test_short_form_intros.py` — Unit tests for display-string builder + title stripping.
- `backend/tests/pipeline/test_short_form_render.py` — Unit tests for path resolution + filename formatting.

**Remotion**
- `remotion/src/ShortFormVideo.tsx` — Composition body (intro + scene sequencing, no long-form overlays).
- `remotion/src/scenes/ShortTitleCardScene.tsx` — Full-frame square-image backdrop + two-zone word-by-word reveal.
- `remotion/src/scenes/VerticalSceneLayout.tsx` — Three-band vertical layout wrapper for narration scenes.

**Frontend**
- `frontend/src/components/timeline/short-form/ShortFormTab.tsx` — Tab body composing the two cards.
- `frontend/src/components/timeline/short-form/ShortIntrosCard.tsx` — Card 1: intros gate UI.
- `frontend/src/components/timeline/short-form/RenderShortsCard.tsx` — Card 2: render UI.
- `frontend/src/components/timeline/short-form/ShortFormStatusPill.tsx` — Timeline header status pill.

### Modified

**Backend**
- `backend/models/script.py` — Add `ShortIntro` Pydantic model; add `short_intros: list[ShortIntro] | None` to `ScriptContent`.
- `backend/api/__init__.py` — Register the new `short_form` router.

**Remotion**
- `remotion/src/types.ts` — Add `ShortIntro` type; add `orientation?: "horizontal" | "vertical"` to `SceneInput`; add `ShortFormVideoProps`.
- `remotion/src/Root.tsx` — Register the new `ShortFormVideo` composition (1080×1920).
- `remotion/src/scenes/SceneRenderer.tsx` — Accept `orientation` prop; wrap children in `VerticalSceneLayout` when vertical; skip aha-subtitle wrapping (full-frame).
- `remotion/src/scenes/SubtitleScene.tsx` — Accept `orientation` prop; switch font-size ramp + max-width when vertical.
- `remotion/src/effects/overlays/EliOverlay.tsx` — Add `orientation` prop; when vertical, position top-center at 380×380.

**Frontend**
- `frontend/src/types/render.ts` — Add `ShortIntro` and short-form render status types.
- `frontend/src/api.ts` — Add API client functions for the new endpoints.
- `frontend/src/components/timeline/ExportPanel.tsx` — Rename Render → Render - Long Form with description; add Render - Short Form tab with description; wire up the new tab body.
- `frontend/src/components/timeline/TimelinePage.tsx` — Mount `ShortFormStatusPill` in the header; wire click handler to open Export panel on the Short Form tab.

---

## Pre-Implementation Notes (read first)

- **Working directory:** `~/git/headless-hero`. All paths below are repo-relative.
- **Python tooling:** Always use `uv run`, `uv pip`, `uv add` — never bare `python`/`pip`.
- **Pytest:** The repo does not yet have a `backend/tests/` folder. Create it as part of Task 2; subsequent test tasks just add files.
- **Frontend tests:** The repo does not have a unit test setup for React components. Visual components are verified manually via the dev server (`npm run dev`) and a renders-on-mount check, not unit tests. The plan calls out manual verification steps explicitly where tests are not possible.
- **TDD scope:** Tests are written first for backend helpers and pipeline modules. Remotion compositions and React components are built and verified by running the renderer / dev server.
- **Commits:** Commit after each task. Use imperative-mood messages matching the repo convention (`Add X`, `Fix Y`, `Update Z`).

---

## Task 1: Add ShortIntro model + short_intros field

**Files:**
- Modify: `backend/models/script.py`

- [ ] **Step 1: Open `backend/models/script.py` and locate the `ScriptContent` class (around line 117).** Identify the existing fields so you can place the new one alongside `seo_metadata` and `hook_score`.

- [ ] **Step 2: Add the `ShortIntro` Pydantic model.** Insert this immediately after the `HookScore` class definition (around line 73, right before `class Scene`):

```python
class ShortIntro(BaseModel):
    """Per-segment short-form intro voiceover metadata."""

    segment_idx: int
    display_text: str                     # full string spoken (e.g. "Unsolved Crimes ... — The Isdal Woman")
    audio_url: str                        # web-relative path (/static/projects/{script_id}/audio/short_intro_{idx}.mp3)
    duration_seconds: float
    word_timestamps: list[dict] = []      # ElevenLabs word timestamps for synced text reveal
```

- [ ] **Step 3: Add the `short_intros` field to `ScriptContent`.** Insert it immediately after `hook_score` (around line 132):

```python
    short_intros: list[ShortIntro] | None = None  # Generated by short-form export flow; None until first generation
```

- [ ] **Step 4: Verify import.** Confirm `BaseModel` is already imported from `pydantic` at the top of the file (it is — line 7). No new imports needed.

- [ ] **Step 5: Run the backend in import-check mode to confirm no syntax errors.**

Run: `uv run python -c "from models.script import ScriptContent, ShortIntro; print(ShortIntro.model_fields.keys())"`
Expected output: `dict_keys(['segment_idx', 'display_text', 'audio_url', 'duration_seconds', 'word_timestamps'])`

Run from: `~/git/headless-hero/backend`

- [ ] **Step 6: Commit.**

```bash
git add backend/models/script.py
git commit -m "Add ShortIntro model and short_intros field to ScriptContent"
```

---

## Task 2: Add `strip_leading_number` helper with tests

**Files:**
- Create: `backend/pipeline/short_form_intros.py`
- Create: `backend/tests/__init__.py`
- Create: `backend/tests/pipeline/__init__.py`
- Create: `backend/tests/pipeline/test_short_form_intros.py`

- [ ] **Step 1: Create empty test package files.**

Create `backend/tests/__init__.py` with empty content.
Create `backend/tests/pipeline/__init__.py` with empty content.

- [ ] **Step 2: Write the failing test.** Create `backend/tests/pipeline/test_short_form_intros.py`:

```python
"""Tests for short_form_intros pipeline helpers."""

import pytest

from pipeline.short_form_intros import build_display_text, strip_leading_number


class TestStripLeadingNumber:
    def test_strips_single_digit_and_space(self):
        assert strip_leading_number("8 Unsolved Crimes") == "Unsolved Crimes"

    def test_strips_multi_digit_and_space(self):
        assert strip_leading_number("123 Things to Know") == "Things to Know"

    def test_no_leading_number_unchanged(self):
        assert strip_leading_number("How to Train Your Dragon") == "How to Train Your Dragon"

    def test_digit_without_space_unchanged(self):
        assert strip_leading_number("8Track Memories") == "8Track Memories"

    def test_empty_string(self):
        assert strip_leading_number("") == ""

    def test_only_a_number(self):
        # "8" with no following space is left alone (no whitespace match)
        assert strip_leading_number("8") == "8"

    def test_multiple_leading_whitespace(self):
        # Regex requires \s+ after digits, so multiple spaces also collapse
        assert strip_leading_number("8   Spaced Out") == "Spaced Out"


class TestBuildDisplayText:
    def test_combines_stripped_title_and_segment_with_em_dash(self):
        result = build_display_text(
            video_title="8 Unsolved Crimes That Still Baffle Detectives to This Day",
            segment_name="The Isdal Woman",
        )
        assert result == "Unsolved Crimes That Still Baffle Detectives to This Day — The Isdal Woman"

    def test_title_without_leading_number_passes_through(self):
        result = build_display_text(
            video_title="How to Train Your Dragon",
            segment_name="Toothless",
        )
        assert result == "How to Train Your Dragon — Toothless"

    def test_empty_segment_name_still_emits_em_dash(self):
        # Edge case: segment_name should never be empty in practice but be defensive
        result = build_display_text(video_title="8 Foo", segment_name="")
        assert result == "Foo — "
```

- [ ] **Step 3: Run the test to verify it fails.**

Run: `cd backend && uv run pytest tests/pipeline/test_short_form_intros.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'pipeline.short_form_intros'`

- [ ] **Step 4: Create the implementation file.** Create `backend/pipeline/short_form_intros.py` with the helpers:

```python
"""Short-form intro voiceover pipeline.

Generates per-segment intro voiceovers ("{stripped video title} — {segment name}")
via ElevenLabs and persists ShortIntro metadata into ScriptContent.short_intros.
"""

import logging
import re

logger = logging.getLogger(__name__)


def strip_leading_number(title: str) -> str:
    """Strip leading digit(s) followed by whitespace from a title.

    Examples:
        "8 Unsolved Crimes ..." -> "Unsolved Crimes ..."
        "How to Train Your Dragon" -> "How to Train Your Dragon"
        "8Track Memories" -> "8Track Memories"  (no following whitespace)
    """
    return re.sub(r"^\d+\s+", "", title)


def build_display_text(video_title: str, segment_name: str) -> str:
    """Build the display string spoken by Eli and rendered on the title card.

    Format: "{stripped video title} — {segment name}"
    The em-dash (U+2014) is the spoken/visual handoff between the two zones.
    """
    return f"{strip_leading_number(video_title)} — {segment_name}"
```

- [ ] **Step 5: Run the test to verify it passes.**

Run: `cd backend && uv run pytest tests/pipeline/test_short_form_intros.py -v`
Expected: 9 passed.

- [ ] **Step 6: Commit.**

```bash
git add backend/pipeline/short_form_intros.py backend/tests/__init__.py backend/tests/pipeline/__init__.py backend/tests/pipeline/test_short_form_intros.py
git commit -m "Add short_form_intros helpers with tests for title stripping and display text"
```

---

## Task 3: Add intro generation function (single segment + batch)

**Files:**
- Modify: `backend/pipeline/short_form_intros.py`
- Modify: `backend/tests/pipeline/test_short_form_intros.py`

- [ ] **Step 1: Write the failing test for the staleness helper.** Append to `backend/tests/pipeline/test_short_form_intros.py`:

```python
from models.script import ShortIntro


class TestIsStale:
    def test_stale_when_display_text_differs(self):
        from pipeline.short_form_intros import is_stale

        existing = ShortIntro(
            segment_idx=0,
            display_text="Old text — Old segment",
            audio_url="/static/foo.mp3",
            duration_seconds=4.0,
        )
        assert is_stale(existing, expected_display_text="New text — New segment") is True

    def test_not_stale_when_display_text_matches(self):
        from pipeline.short_form_intros import is_stale

        existing = ShortIntro(
            segment_idx=0,
            display_text="Foo — Bar",
            audio_url="/static/foo.mp3",
            duration_seconds=4.0,
        )
        assert is_stale(existing, expected_display_text="Foo — Bar") is False
```

- [ ] **Step 2: Run the test to confirm failure.**

Run: `cd backend && uv run pytest tests/pipeline/test_short_form_intros.py::TestIsStale -v`
Expected: FAIL with `ImportError: cannot import name 'is_stale'`.

- [ ] **Step 3: Implement `is_stale`, `generate_short_intro`, and `generate_short_intros`.** Append to `backend/pipeline/short_form_intros.py`:

```python
from pathlib import Path

from config import DATA_DIR, DEFAULT_TTS_MODEL
from integrations.elevenlabs_client import generate_speech
from models.script import ScriptContent, ShortIntro
from pipeline.voiceover import _mp3_duration_seconds


def is_stale(existing: ShortIntro, expected_display_text: str) -> bool:
    """Return True if a stored intro's display text no longer matches what would be generated."""
    return existing.display_text != expected_display_text


def _intro_audio_path(script_id: str, segment_idx: int) -> Path:
    """Filesystem path for a short-form intro audio file."""
    audio_dir = DATA_DIR / "projects" / script_id / "audio"
    audio_dir.mkdir(parents=True, exist_ok=True)
    return audio_dir / f"short_intro_{segment_idx}.mp3"


def generate_short_intro(
    script_id: str,
    segment_idx: int,
    display_text: str,
    voice_id: str,
    model_id: str = DEFAULT_TTS_MODEL,
    voice_settings: dict | None = None,
) -> ShortIntro:
    """Generate a single intro voiceover via ElevenLabs and persist the MP3.

    Returns a fully populated ShortIntro (caller is responsible for writing it
    into ScriptContent.short_intros).
    """
    logger.info(
        "Generating short intro for script %s, segment %d (voice=%s, text=%r)",
        script_id, segment_idx, voice_id, display_text,
    )
    audio_bytes, word_timestamps = generate_speech(
        text=display_text,
        voice_id=voice_id,
        model_id=model_id,
        voice_settings=voice_settings,
        script_id=script_id,
    )

    audio_path = _intro_audio_path(script_id, segment_idx)
    audio_path.write_bytes(audio_bytes)

    if word_timestamps and word_timestamps[-1].get("end_ms", 0) > 0:
        duration = round(word_timestamps[-1]["end_ms"] / 1000, 3)
    else:
        duration = _mp3_duration_seconds(audio_bytes)

    web_url = f"/static/projects/{script_id}/audio/short_intro_{segment_idx}.mp3"
    return ShortIntro(
        segment_idx=segment_idx,
        display_text=display_text,
        audio_url=web_url,
        duration_seconds=duration,
        word_timestamps=word_timestamps or [],
    )


def generate_short_intros(
    script_id: str,
    content: ScriptContent,
    voice_id: str,
    force: bool = False,
    model_id: str = DEFAULT_TTS_MODEL,
    voice_settings: dict | None = None,
    on_progress=None,  # callable(idx, total, display_text) -> None
) -> list[ShortIntro]:
    """Generate intros for every segment in `content`.

    If `force` is False, skips segments whose existing ShortIntro is non-stale
    (display_text matches the current title/segment_name combination).
    Returns the full list of ShortIntros in segment order.
    """
    existing_map: dict[int, ShortIntro] = {}
    if content.short_intros:
        existing_map = {intro.segment_idx: intro for intro in content.short_intros}

    results: list[ShortIntro] = []
    total = len(content.segments)
    for idx, seg in enumerate(content.segments):
        display_text = build_display_text(content.title, seg.name)

        if on_progress:
            on_progress(idx, total, display_text)

        existing = existing_map.get(idx)
        if not force and existing and not is_stale(existing, display_text):
            logger.info("Short intro for segment %d is up-to-date — skipping", idx)
            results.append(existing)
            continue

        intro = generate_short_intro(
            script_id=script_id,
            segment_idx=idx,
            display_text=display_text,
            voice_id=voice_id,
            model_id=model_id,
            voice_settings=voice_settings,
        )
        results.append(intro)

    return results
```

- [ ] **Step 4: Run all short-form-intro tests to verify they pass.**

Run: `cd backend && uv run pytest tests/pipeline/test_short_form_intros.py -v`
Expected: 11 passed (9 from Task 2 + 2 new).

- [ ] **Step 5: Commit.**

```bash
git add backend/pipeline/short_form_intros.py backend/tests/pipeline/test_short_form_intros.py
git commit -m "Add short-form intro generation pipeline with single and batch helpers"
```

---

## Task 4: Add background-job orchestration for intro generation

**Files:**
- Create: `backend/api/short_form.py`
- Modify: `backend/api/__init__.py`

- [ ] **Step 1: Inspect existing router registration.** Open `backend/api/__init__.py` and identify how other routers are imported and included. (You will mirror that pattern.)

- [ ] **Step 2: Create `backend/api/short_form.py` with intro endpoints.** Write the file:

```python
"""Short-form export endpoints — intros + per-segment renders."""

import json
import logging

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlmodel import Session

from config import DEFAULT_TTS_MODEL
from database import get_session
from models.brand import BrandProfile
from models.script import Script, ScriptContent
from pipeline.render_jobs import (
    create_job,
    get_job,
    run_in_background,
    update_job,
)
from pipeline.short_form_intros import (
    build_display_text,
    generate_short_intro,
    generate_short_intros,
    is_stale,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/short-form", tags=["short-form"])

# --- Request / Response schemas ---


class GenerateShortIntrosRequest(BaseModel):
    script_id: str
    force: bool = False  # if true, regenerates even non-stale intros


class GenerateShortIntroRequest(BaseModel):
    script_id: str
    segment_idx: int


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


# --- Helpers ---


def _load_content(session: Session, script_id: str) -> ScriptContent:
    record = session.get(Script, script_id)
    if not record:
        raise HTTPException(status_code=404, detail="Script not found")
    return ScriptContent.model_validate(json.loads(record.script_json))


def _resolve_voice_id(session: Session, script_id: str) -> str:
    record = session.get(Script, script_id)
    if not record:
        raise HTTPException(status_code=404, detail="Script not found")
    brand = session.get(BrandProfile, record.brand_id)
    if not brand or not brand.voice_id:
        raise HTTPException(
            status_code=400,
            detail="No voice configured — set a voice in Settings first",
        )
    return brand.voice_id


def _persist_intros(script_id: str, intros: list) -> None:
    """Write a list of ShortIntros into the script's short_intros field."""
    from database import engine

    with Session(engine) as session:
        record = session.get(Script, script_id)
        if not record:
            return
        content = ScriptContent.model_validate(json.loads(record.script_json))

        existing_map = {intro.segment_idx: intro for intro in (content.short_intros or [])}
        for intro in intros:
            existing_map[intro.segment_idx] = intro
        content.short_intros = [existing_map[k] for k in sorted(existing_map.keys())]

        record.script_json = content.model_dump_json()
        session.add(record)
        session.commit()


# --- Endpoints: intros ---


@router.post("/intros/generate-all", response_model=JobResponse)
def start_generate_all_intros(
    body: GenerateShortIntrosRequest, session: Session = Depends(get_session)
):
    """Generate intros for every segment in the background."""
    content = _load_content(session, body.script_id)
    voice_id = _resolve_voice_id(session, body.script_id)
    total = len(content.segments)

    job = create_job(scene_count=total)
    logger.info(
        "Starting short-form intro generation for script %s (%d segments, force=%s)",
        body.script_id, total, body.force,
    )

    def do_generate():
        def on_progress(idx, n, display_text):
            update_job(
                job.id,
                progress=idx / max(1, n),
                current_step=f"Generating intro {idx + 1}/{n}...",
            )

        intros = generate_short_intros(
            script_id=body.script_id,
            content=content,
            voice_id=voice_id,
            force=body.force,
            on_progress=on_progress,
        )
        _persist_intros(body.script_id, intros)
        update_job(job.id, progress=1.0, current_step="Complete")
        return ""

    run_in_background(job.id, do_generate)
    return JobResponse(job_id=job.id)


@router.post("/intros/generate-one", response_model=JobResponse)
def start_generate_one_intro(
    body: GenerateShortIntroRequest, session: Session = Depends(get_session)
):
    """Regenerate a single segment's intro in the background."""
    content = _load_content(session, body.script_id)
    if body.segment_idx < 0 or body.segment_idx >= len(content.segments):
        raise HTTPException(status_code=400, detail="segment_idx out of range")
    voice_id = _resolve_voice_id(session, body.script_id)
    seg = content.segments[body.segment_idx]
    display_text = build_display_text(content.title, seg.name)

    job = create_job(scene_count=1)
    logger.info(
        "Starting short-form intro regen for script %s segment %d",
        body.script_id, body.segment_idx,
    )

    def do_generate():
        update_job(job.id, progress=0.1, current_step=f"Generating intro for {seg.name}...")
        intro = generate_short_intro(
            script_id=body.script_id,
            segment_idx=body.segment_idx,
            display_text=display_text,
            voice_id=voice_id,
        )
        _persist_intros(body.script_id, [intro])
        update_job(job.id, progress=1.0, current_step="Complete")
        return ""

    run_in_background(job.id, do_generate)
    return JobResponse(job_id=job.id)


@router.get("/jobs/{job_id}", response_model=JobStatusResponse)
def job_status(job_id: str):
    """Poll a short-form job (intro or render)."""
    job = get_job(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    return JobStatusResponse(**job.to_dict())
```

- [ ] **Step 3: Register the router.** Open `backend/api/__init__.py` and add the import + `include_router` call alongside the existing ones. The exact line numbers depend on the file; mirror the pattern used for `voiceover.router` or `render.router`:

```python
from api.short_form import router as short_form_router
# ...
app.include_router(short_form_router)
```

- [ ] **Step 4: Verify the route is registered.**

Run: `cd backend && uv run python -c "from api import app; print([r.path for r in app.routes if 'short-form' in r.path])"`
Expected output includes:
```
['/api/short-form/intros/generate-all', '/api/short-form/intros/generate-one', '/api/short-form/jobs/{job_id}']
```

- [ ] **Step 5: Commit.**

```bash
git add backend/api/short_form.py backend/api/__init__.py
git commit -m "Add short-form intro generation endpoints with background jobs"
```

---

## Task 5: Add Remotion types for short-form

**Files:**
- Modify: `remotion/src/types.ts`

- [ ] **Step 1: Open `remotion/src/types.ts` and add the orientation type + ShortIntro + ShortFormVideoProps.** Append to the end of the file (after `FullVideoProps`):

```typescript
// --- Short-form types ---

export type Orientation = "horizontal" | "vertical";

export interface ShortIntroProps {
  segment_idx: number;
  display_text: string;        // "stripped title — segment name"
  audio_path: string;           // absolute or http URL to short_intro_{idx}.mp3
  duration_seconds: number;
  word_timestamps: WordTimestamp[];
  backdrop_image_path: string;  // path to title_card_{idx}.png (square)
}

export interface ShortFormVideoProps {
  intro: ShortIntroProps;
  scenes: SceneInput[];         // segment scenes only (no title card scene from long-form)
  fps: number;
  width: number;                // 1080
  height: number;               // 1920
  subtitle_highlight?: SubtitleHighlightConfig | null;
}
```

- [ ] **Step 2: Add orientation to SceneInput.** Edit the `SceneInput` interface to add an `orientation` field. Place it near the top (after `narration`):

```typescript
  orientation?: Orientation;    // defaults to "horizontal" for backward compat with FullVideo
```

- [ ] **Step 3: Verify TypeScript compiles.**

Run: `cd remotion && npx tsc --noEmit`
Expected: no errors.

- [ ] **Step 4: Commit.**

```bash
git add remotion/src/types.ts
git commit -m "Add Remotion types for short-form composition and orientation"
```

---

## Task 6: Build VerticalSceneLayout component

**Files:**
- Create: `remotion/src/scenes/VerticalSceneLayout.tsx`

- [ ] **Step 1: Create the layout component.** Write `remotion/src/scenes/VerticalSceneLayout.tsx`:

```typescript
/**
 * VerticalSceneLayout — three-band layout for 9:16 narration scenes.
 *
 * - Top band (y=0..656): blurred-dim copy of the focal image (Eli sits inside).
 * - Middle band (y=656..1264): clean focal image, full-width.
 * - Bottom band (y=1264..1920): blurred-dim copy of the focal image (subtitles overlay).
 *
 * Eli is positioned top-center inside the top band by EliOverlay (handled separately).
 * Subtitles are positioned by SubtitleOverlay using its `orientation` prop.
 */
import React from "react";
import { Img } from "remotion";

interface Props {
  imagePath: string | null | undefined;
  children: React.ReactNode; // the focal-image element rendered by StaticImageScene/MultiFrameScene/etc.
}

// Layout constants — derived from spec (656 + 608 + 656 = 1920)
const TOP_BAND_HEIGHT = 656;
const MIDDLE_BAND_HEIGHT = 608;
const BOTTOM_BAND_HEIGHT = 656;

const BLUR_FILTER = "blur(40px) brightness(0.4) saturate(0.6)";

export const VerticalSceneLayout: React.FC<Props> = ({ imagePath, children }) => {
  return (
    <div style={{ width: "100%", height: "100%", position: "relative", backgroundColor: "#000" }}>
      {/* Top blurred-dim band */}
      <div
        style={{
          position: "absolute",
          top: 0,
          left: 0,
          width: "100%",
          height: TOP_BAND_HEIGHT,
          overflow: "hidden",
        }}
      >
        {imagePath && (
          <Img
            src={imagePath}
            style={{
              width: "100%",
              height: "100%",
              objectFit: "cover",
              filter: BLUR_FILTER,
              transform: "scale(1.1)", // prevents blur edge artifacts
            }}
          />
        )}
      </div>

      {/* Middle focal image band */}
      <div
        style={{
          position: "absolute",
          top: TOP_BAND_HEIGHT,
          left: 0,
          width: "100%",
          height: MIDDLE_BAND_HEIGHT,
          overflow: "hidden",
        }}
      >
        {children}
      </div>

      {/* Bottom blurred-dim band */}
      <div
        style={{
          position: "absolute",
          top: TOP_BAND_HEIGHT + MIDDLE_BAND_HEIGHT,
          left: 0,
          width: "100%",
          height: BOTTOM_BAND_HEIGHT,
          overflow: "hidden",
        }}
      >
        {imagePath && (
          <Img
            src={imagePath}
            style={{
              width: "100%",
              height: "100%",
              objectFit: "cover",
              filter: BLUR_FILTER,
              transform: "scale(1.1)",
            }}
          />
        )}
      </div>
    </div>
  );
};

// Exported for use by SubtitleOverlay positioning logic
export const VERTICAL_LAYOUT = {
  TOP_BAND_HEIGHT,
  MIDDLE_BAND_HEIGHT,
  BOTTOM_BAND_HEIGHT,
} as const;
```

- [ ] **Step 2: Verify TypeScript compiles.**

Run: `cd remotion && npx tsc --noEmit`
Expected: no errors.

- [ ] **Step 3: Commit.**

```bash
git add remotion/src/scenes/VerticalSceneLayout.tsx
git commit -m "Add VerticalSceneLayout component for 9:16 three-band layout"
```

---

## Task 7: Add orientation prop to EliOverlay (top-center, 380×380)

**Files:**
- Modify: `remotion/src/effects/overlays/EliOverlay.tsx`

- [ ] **Step 1: Open `remotion/src/effects/overlays/EliOverlay.tsx`.** Add `Orientation` to the imports from `../../types`:

```typescript
import type {
  EliOverlay as EliOverlayType,
  PhraseTimestamp,
  Orientation,
} from "../../types";
```

- [ ] **Step 2: Add two new constants near the existing `OVERLAY_SIZE` constant (around line 47):**

```typescript
const OVERLAY_SIZE_VERTICAL = 380;
const TOP_MARGIN_VERTICAL = 80;  // px inset from the top edge in vertical mode
```

- [ ] **Step 3: Replace the `cornerStyle` function with one that branches on orientation.** Locate the existing `cornerStyle` (around line 61) and replace it with:

```typescript
function cornerStyle(
  corner: string | null | undefined,
  orientation: Orientation | undefined,
): React.CSSProperties {
  // Vertical mode overrides corner: Eli is always top-center, larger
  if (orientation === "vertical") {
    return {
      position: "absolute",
      width: OVERLAY_SIZE_VERTICAL,
      height: OVERLAY_SIZE_VERTICAL,
      top: TOP_MARGIN_VERTICAL,
      left: "50%",
      transform: "translateX(-50%)",
    };
  }

  const c = corner ?? "BR";
  const base: React.CSSProperties = {
    position: "absolute",
    width: OVERLAY_SIZE,
    height: OVERLAY_SIZE,
  };
  switch (c) {
    case "TL":
      return { ...base, top: CORNER_MARGIN, left: CORNER_MARGIN };
    case "TR":
      return { ...base, top: CORNER_MARGIN, right: CORNER_MARGIN };
    case "BL":
      return { ...base, bottom: CORNER_MARGIN, left: CORNER_MARGIN };
    case "BR":
    default:
      return { ...base, bottom: CORNER_MARGIN, right: CORNER_MARGIN };
  }
}
```

- [ ] **Step 4: Update the Props interface and component signature.** Find the EliOverlay component definition (search for `export const EliOverlay`). Add `orientation` to its props interface. The change looks like:

```typescript
interface EliOverlayProps {
  overlay: EliOverlayType;
  phraseTimestamps?: PhraseTimestamp[] | null;
  characterFramesBaseUrl: string;
  sceneDurationInFrames: number;
  sceneId: string;
  orientation?: Orientation;
}

export const EliOverlay: React.FC<EliOverlayProps> = ({
  overlay,
  phraseTimestamps,
  characterFramesBaseUrl,
  sceneDurationInFrames,
  sceneId,
  orientation,
}) => {
  // ... existing body ...
```

(If the existing Props interface has a different name or inline form, adapt accordingly.)

- [ ] **Step 5: Pass `orientation` to `cornerStyle`.** Find every call to `cornerStyle(...)` inside the component body and pass `orientation` as the second argument: `cornerStyle(overlay.corner, orientation)`.

- [ ] **Step 6: Use the right size for sub-elements.** Search inside the component for any use of the `OVERLAY_SIZE` constant in inline styles (e.g., child element widths/heights). For any positioning/sizing that depends on the outer overlay size, gate it on orientation:

```typescript
const overlaySize = orientation === "vertical" ? OVERLAY_SIZE_VERTICAL : OVERLAY_SIZE;
```

Then replace `OVERLAY_SIZE` references inside style calculations with `overlaySize`. Leave the top-level constant alone.

- [ ] **Step 7: Verify TypeScript compiles.**

Run: `cd remotion && npx tsc --noEmit`
Expected: no errors.

- [ ] **Step 8: Commit.**

```bash
git add remotion/src/effects/overlays/EliOverlay.tsx
git commit -m "Add vertical orientation mode to EliOverlay (top-center, 380x380)"
```

---

## Task 8: Add orientation prop to SubtitleScene with retuned font ramp

**Files:**
- Modify: `remotion/src/scenes/SubtitleScene.tsx`

- [ ] **Step 1: Open `remotion/src/scenes/SubtitleScene.tsx`.** Import the Orientation type at the top:

```typescript
import type { SceneInput, Orientation } from "../types";
```

(If `SceneInput` is the only existing import from `../types`, just add `Orientation` to the same line.)

- [ ] **Step 2: Replace `getFontSize` with an orientation-aware variant.** Locate the existing `getFontSize` function (around line 26) and replace it with:

```typescript
/** Adaptive font size based on character count and orientation. */
function getFontSize(charCount: number, orientation: Orientation): number {
  if (orientation === "vertical") {
    // Vertical (1080w): bump everything up — less horizontal room to break into lines.
    if (charCount < 40) return 110;
    if (charCount < 80) return 92;
    return 76;
  }
  // Horizontal (1920w): original ramp.
  if (charCount < 40) return 96;
  if (charCount < 80) return 72;
  return 56;
}
```

- [ ] **Step 3: Add `orientation` to the Props interface.** Find the `interface Props` block (around line 21) and update it:

```typescript
interface Props {
  scene: SceneInput;
  orientation?: Orientation;
}
```

- [ ] **Step 4: Default and use orientation in the component.** Update the component signature:

```typescript
export const SubtitleScene: React.FC<Props> = ({ scene, orientation = "horizontal" }) => {
```

Then update the `getFontSize` call inside the body:

```typescript
const fontSize = getFontSize(text.length, orientation);
```

Update the `maxWidth` style on the word-reveal container from `"85%"` to:

```typescript
maxWidth: orientation === "vertical" ? "92%" : "85%",
```

- [ ] **Step 5: Verify TypeScript compiles.**

Run: `cd remotion && npx tsc --noEmit`
Expected: no errors.

- [ ] **Step 6: Commit.**

```bash
git add remotion/src/scenes/SubtitleScene.tsx
git commit -m "Add vertical orientation mode to SubtitleScene with retuned font ramp"
```

---

## Task 9: Update SceneRenderer to support vertical orientation

**Files:**
- Modify: `remotion/src/scenes/SceneRenderer.tsx`

- [ ] **Step 1: Open `remotion/src/scenes/SceneRenderer.tsx`.** Add imports at the top:

```typescript
import type { SceneInput, Orientation } from "../types";
import { VerticalSceneLayout } from "./VerticalSceneLayout";
```

(Adjust the SceneInput import line to add `Orientation` if it's already importing from `../types`.)

- [ ] **Step 2: Update Props and component signature** to accept an `orientation` prop:

```typescript
interface Props {
  scene: SceneInput;
  highlightEnabled?: boolean;
  orientation?: Orientation;
}

export const SceneRenderer: React.FC<Props> = ({
  scene,
  highlightEnabled,
  orientation = "horizontal",
}) => {
```

- [ ] **Step 3: Wrap the focal-image layer in VerticalSceneLayout when vertical.** Find the block that builds `visualLayer` (around line 64) and after all the FX wrapping logic — before the return statement — add:

```typescript
const isVertical = orientation === "vertical";

// In vertical mode, narration scenes (non-title-card, non-aha-subtitle) get wrapped
// in the three-band layout. Aha-subtitle scenes occupy the full vertical frame
// natively. Title cards in shorts are handled by ShortTitleCardScene, not here.
if (isVertical && !isAhaSubtitle && !isTitleCard) {
  visualLayer = (
    <VerticalSceneLayout imagePath={scene.image_path}>
      {visualLayer}
    </VerticalSceneLayout>
  );
}
```

- [ ] **Step 4: Pass orientation to SubtitleScene and EliOverlay.** Find the `<SubtitleScene scene={scene} />` JSX (around line 68) and add the prop:

```typescript
visualLayer = <SubtitleScene scene={scene} orientation={orientation} />;
```

Find the `<EliOverlay ... />` JSX (around line 117) and add:

```typescript
orientation={orientation}
```

as a new prop.

- [ ] **Step 5: Update SubtitleOverlay positioning when vertical.** Open `remotion/src/effects/typography/Subtitles.tsx` (path inferred from the import), find the SubtitleOverlay component, and add an `orientation` prop. When vertical, anchor the subtitle container to the bottom band (top: ~1264, height: 656, centered).

If the existing SubtitleOverlay uses absolute positioning for the long-form layout, gate it on orientation. The exact change depends on the existing implementation — preserve horizontal behavior, only override for vertical. The new vertical style:

```typescript
const verticalStyle: React.CSSProperties = {
  position: "absolute",
  top: 1264,        // start of bottom band
  left: 0,
  width: "100%",
  height: 656,      // bottom band height
  display: "flex",
  alignItems: "center",
  justifyContent: "center",
  padding: "0 60px",
};
```

Wrap the existing subtitle content in this style when `orientation === "vertical"`.

If the SubtitleOverlay file doesn't accept props for orientation, add an `orientation?: Orientation` prop, default to `"horizontal"`, and branch on it.

- [ ] **Step 6: Pass orientation from SceneRenderer to SubtitleOverlay.** Find the `<SubtitleOverlay ... />` JSX (around line 110) and add:

```typescript
orientation={orientation}
```

- [ ] **Step 7: Verify TypeScript compiles.**

Run: `cd remotion && npx tsc --noEmit`
Expected: no errors.

- [ ] **Step 8: Commit.**

```bash
git add remotion/src/scenes/SceneRenderer.tsx remotion/src/effects/typography/Subtitles.tsx
git commit -m "Wire orientation prop through SceneRenderer for 9:16 layout"
```

---

## Task 10: Build ShortTitleCardScene component

**Files:**
- Create: `remotion/src/scenes/ShortTitleCardScene.tsx`

- [ ] **Step 1: Create the component.** Write `remotion/src/scenes/ShortTitleCardScene.tsx`:

```typescript
/**
 * ShortTitleCardScene — full-frame square image with darken/blur, plus
 * two-zone word-by-word text reveal synced to the intro VO.
 *
 * Zone 1 (upper half): video title (smaller, secondary weight).
 * Zone 2 (lower half): segment name (larger, primary weight, accent color).
 * The em-dash in display_text marks the boundary between the two zones.
 */
import React from "react";
import { Img, useCurrentFrame, useVideoConfig, spring, interpolate } from "remotion";
import { loadFont } from "@remotion/google-fonts/Inter";
import type { ShortIntroProps } from "../types";

const { fontFamily } = loadFont("normal", {
  weights: ["600", "800", "900"],
  subsets: ["latin"],
});

interface Props {
  intro: ShortIntroProps;
}

const ACCENT_COLOR = "#fbbf24"; // amber accent — matches existing aha-subtitle glow palette
const BACKDROP_FILTER = "blur(18px) brightness(0.45) saturate(0.7)";
const EM_DASH = "—";

function clamp(value: number, min: number, max: number): number {
  return Math.min(max, Math.max(min, value));
}

export const ShortTitleCardScene: React.FC<Props> = ({ intro }) => {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();

  // Split display_text on em-dash → title words (zone 1) + segment words (zone 2)
  const parts = intro.display_text.split(EM_DASH);
  const titleText = (parts[0] ?? "").trim();
  const segmentText = (parts[1] ?? "").trim();
  const titleWords = titleText.split(/\s+/).filter(Boolean);
  const segmentWords = segmentText.split(/\s+/).filter(Boolean);

  // Filter word_timestamps to non-em-dash entries (ElevenLabs may or may not emit the dash;
  // we strip any timestamp whose word matches the em-dash exactly).
  const wordTimestamps = (intro.word_timestamps ?? []).filter(
    (wt) => wt.word.trim() !== EM_DASH,
  );

  // Map timestamps to zones by index relative to titleWords.length
  function getWordStartFrame(zone: "title" | "segment", index: number): number {
    const globalIdx = zone === "title" ? index : titleWords.length + index;
    const ts = wordTimestamps[globalIdx];
    if (!ts) return 0;
    return Math.round((ts.start_ms / 1000) * fps);
  }

  function renderWord(
    word: string,
    zone: "title" | "segment",
    index: number,
  ): React.ReactNode {
    const wordStartFrame = getWordStartFrame(zone, index);
    const wordAge = frame - wordStartFrame;
    const entryProgress = clamp(wordAge / 8, 0, 1);
    const wordScale = spring({
      frame: Math.max(0, wordAge),
      fps,
      config: { damping: 14, mass: 0.6 },
      from: 0.7,
      to: 1,
    });
    const wordY = (1 - entryProgress) * 30;
    const wordOpacity = clamp(wordAge / 5, 0, 1);

    return (
      <span
        key={`${zone}-${index}`}
        style={{
          display: "inline-block",
          opacity: wordAge < 0 ? 0 : wordOpacity,
          transform: `translateY(${wordAge < 0 ? 30 : wordY}px) scale(${
            wordAge < 0 ? 0.7 : wordScale
          })`,
        }}
      >
        {word}
      </span>
    );
  }

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
      {intro.backdrop_image_path && (
        <Img
          src={intro.backdrop_image_path}
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

      {/* Zone 1: Title (upper half) */}
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
            display: "flex",
            flexWrap: "wrap",
            justifyContent: "center",
            gap: "0.25em",
          }}
        >
          {titleWords.map((w, i) => renderWord(w, "title", i))}
        </div>
      </div>

      {/* Zone 2: Segment name (lower half) */}
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
            display: "flex",
            flexWrap: "wrap",
            justifyContent: "center",
            gap: "0.2em",
          }}
        >
          {segmentWords.map((w, i) => renderWord(w, "segment", i))}
        </div>
      </div>
    </div>
  );
};
```

- [ ] **Step 2: Verify TypeScript compiles.**

Run: `cd remotion && npx tsc --noEmit`
Expected: no errors.

- [ ] **Step 3: Commit.**

```bash
git add remotion/src/scenes/ShortTitleCardScene.tsx
git commit -m "Add ShortTitleCardScene with two-zone word-by-word reveal"
```

---

## Task 11: Build ShortFormVideo composition and register it

**Files:**
- Create: `remotion/src/ShortFormVideo.tsx`
- Modify: `remotion/src/Root.tsx`

- [ ] **Step 1: Create the composition body.** Write `remotion/src/ShortFormVideo.tsx`:

```typescript
/**
 * ShortFormVideo composition — sequences a single segment's intro + scenes
 * for 9:16 short-form export. No chapter map, no global indicator bar, no
 * segment timer/counter (those are long-form-only).
 */
import React from "react";
import { Audio, Sequence } from "remotion";
import type { ShortFormVideoProps } from "./types";
import { SceneRenderer } from "./scenes/SceneRenderer";
import { ShortTitleCardScene } from "./scenes/ShortTitleCardScene";
import { secondsToFrames } from "./utils/timing";

export const ShortFormVideo: React.FC<ShortFormVideoProps> = ({
  intro,
  scenes,
  fps,
  subtitle_highlight,
}) => {
  const introDurationFrames = Math.max(fps, secondsToFrames(intro.duration_seconds, fps));

  const sequences: React.ReactNode[] = [];
  let currentFrame = 0;

  // Intro scene
  sequences.push(
    <Sequence
      key="intro"
      from={currentFrame}
      durationInFrames={introDurationFrames}
      name={`Intro: segment ${intro.segment_idx}`}
    >
      <ShortTitleCardScene intro={intro} />
      <Audio src={intro.audio_path} volume={1} />
    </Sequence>,
  );
  currentFrame += introDurationFrames;

  // Segment scenes
  for (let i = 0; i < scenes.length; i++) {
    const scene = scenes[i];
    const durationFrames = Math.max(fps, secondsToFrames(scene.duration_seconds, fps));

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

- [ ] **Step 2: Register the composition in Root.tsx.** Open `remotion/src/Root.tsx` and add the new composition next to `FullVideo`:

```typescript
import { ShortFormVideo } from "./ShortFormVideo";
// ...
// eslint-disable-next-line @typescript-eslint/no-explicit-any
const ShortFormVideoComp = ShortFormVideo as any;
```

Then inside the `<Root>` component's `<>...</>`, add:

```typescript
<Composition
  id="ShortFormVideo"
  component={ShortFormVideoComp}
  fps={30}
  width={1080}
  height={1920}
  durationInFrames={300}
  defaultProps={{
    intro: {
      segment_idx: 0,
      display_text: "",
      audio_path: "",
      duration_seconds: 3,
      word_timestamps: [],
      backdrop_image_path: "",
    },
    scenes: [],
    fps: 30,
    width: 1080,
    height: 1920,
  }}
  calculateMetadata={({ props }) => {
    const p = props as unknown as ShortFormVideoProps;
    const sceneSeconds = p.scenes.reduce((s, sc) => s + sc.duration_seconds, 0);
    const totalSeconds = p.intro.duration_seconds + sceneSeconds;
    return {
      durationInFrames: Math.max(1, Math.ceil(totalSeconds * p.fps)),
      fps: p.fps,
      width: p.width,
      height: p.height,
    };
  }}
/>
```

Add `ShortFormVideoProps` to the import from `./types` at the top:

```typescript
import type { FullVideoProps, ShortFormVideoProps } from "./types";
```

- [ ] **Step 3: Verify TypeScript compiles.**

Run: `cd remotion && npx tsc --noEmit`
Expected: no errors.

- [ ] **Step 4: Verify Remotion picks up the composition.**

Run: `cd remotion && npx remotion compositions`
Expected output includes a line for `ShortFormVideo` at 1080×1920.

- [ ] **Step 5: Commit.**

```bash
git add remotion/src/ShortFormVideo.tsx remotion/src/Root.tsx
git commit -m "Add ShortFormVideo composition for 1080x1920 vertical export"
```

---

## Task 12: Build short_form_render pipeline

**Files:**
- Create: `backend/pipeline/short_form_render.py`

- [ ] **Step 1: Create the file.** Write `backend/pipeline/short_form_render.py`:

```python
"""Short-form (9:16) render pipeline — renders one or all per-segment shorts via Remotion."""

import json
import logging
import os
import shutil
import subprocess
import time
from pathlib import Path
from typing import Callable

from config import BACKEND_PORT, DATA_DIR, FPS, sanitize_filename
from models.script import Scene, ScriptContent, ShortIntro
from pipeline.remotion_render import (
    REMOTION_DIR,
    REMOTION_ENTRY,
    _reencode_h264,
    _run_remotion,
    _scene_to_input_props,
    _verify_video,
)

logger = logging.getLogger(__name__)

ProgressCallback = Callable[[float, str], None] | None

SHORT_WIDTH = 1080
SHORT_HEIGHT = 1920


def _shorts_dir(script_id: str) -> Path:
    d = DATA_DIR / "projects" / script_id / "renders" / "shorts"
    d.mkdir(parents=True, exist_ok=True)
    return d


def _intro_backdrop_path(script_id: str, segment_idx: int) -> str | None:
    """Web-served path to the per-segment title card image (square)."""
    base = DATA_DIR / "projects" / script_id / "images"
    p = base / f"title_card_{segment_idx}.png"
    if not p.exists():
        return None
    return f"http://localhost:{BACKEND_PORT}/static/projects/{script_id}/images/title_card_{segment_idx}.png"


def _intro_audio_path(script_id: str, segment_idx: int) -> str | None:
    p = DATA_DIR / "projects" / script_id / "audio" / f"short_intro_{segment_idx}.mp3"
    if not p.exists():
        return None
    return f"http://localhost:{BACKEND_PORT}/static/projects/{script_id}/audio/short_intro_{segment_idx}.mp3"


def _build_intro_props(intro: ShortIntro, script_id: str) -> dict:
    backdrop_path = _intro_backdrop_path(script_id, intro.segment_idx)
    audio_path = _intro_audio_path(script_id, intro.segment_idx)
    if not audio_path:
        raise RuntimeError(
            f"Intro audio missing for segment {intro.segment_idx} — generate intros first"
        )
    return {
        "segment_idx": intro.segment_idx,
        "display_text": intro.display_text,
        "audio_path": audio_path,
        "duration_seconds": intro.duration_seconds,
        "word_timestamps": intro.word_timestamps or [],
        "backdrop_image_path": backdrop_path or "",
    }


def _short_filename(project_title: str, n: int, total: int) -> str:
    """Build the destination filename per spec: '[short form N/M] {project name}.mp4'."""
    safe = sanitize_filename(project_title)
    return f"[short form {n}/{total}] {safe}.mp4"


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


def _find_intro(content: ScriptContent, segment_idx: int) -> ShortIntro:
    if not content.short_intros:
        raise RuntimeError("No short_intros on content — generate intros first")
    for intro in content.short_intros:
        if intro.segment_idx == segment_idx:
            return intro
    raise RuntimeError(f"Short intro for segment {segment_idx} not generated yet")


def render_short_segment(
    script_id: str,
    segment_idx: int,
    content: ScriptContent,
    project_title: str,
    on_progress: ProgressCallback = None,
) -> str:
    """Render a single short for one segment. Returns the web-relative path to the MP4."""
    if segment_idx < 0 or segment_idx >= len(content.segments):
        raise RuntimeError(f"segment_idx {segment_idx} out of range (0..{len(content.segments) - 1})")

    intro = _find_intro(content, segment_idx)
    segment = content.segments[segment_idx]

    # Build scene props (skip the long-form title-card scene if present — shorts use intro instead)
    scene_props = []
    for sc in segment.scenes:
        if sc.is_title_card:
            continue
        scene_props.append(_scene_to_input_props(sc, script_id))

    props = {
        "intro": _build_intro_props(intro, script_id),
        "scenes": scene_props,
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
        _copy_to_downloads(project_title, output_path, dest_name)
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

    return f"/static/projects/{script_id}/renders/shorts/{output_filename}"


def render_all_shorts(
    script_id: str,
    content: ScriptContent,
    project_title: str,
    on_progress: ProgressCallback = None,
) -> list[str]:
    """Render every segment as a short, sequentially. Returns list of web-relative MP4 paths."""
    total = len(content.segments)
    results: list[str] = []
    for i in range(total):
        n = i + 1

        def seg_progress(p: float, msg: str, _n=n):
            if on_progress:
                # Map per-segment 0..1 into the global range
                global_p = ((_n - 1) + p) / total
                on_progress(global_p, f"Short {_n}/{total}: {msg}")

        url = render_short_segment(
            script_id=script_id,
            segment_idx=i,
            content=content,
            project_title=project_title,
            on_progress=seg_progress,
        )
        results.append(url)

    return results
```

- [ ] **Step 2: Check imports work.**

Run: `cd backend && uv run python -c "from pipeline.short_form_render import render_short_segment, render_all_shorts, _short_filename; print(_short_filename('My Project', 3, 8))"`
Expected output: `[short form 3/8] My Project.mp4`

- [ ] **Step 3: Commit.**

```bash
git add backend/pipeline/short_form_render.py
git commit -m "Add short_form_render pipeline for single and batch short renders"
```

---

## Task 13: Add render endpoints + status tests

**Files:**
- Modify: `backend/api/short_form.py`
- Create: `backend/tests/pipeline/test_short_form_render.py`

- [ ] **Step 1: Write failing test for filename helper.** Create `backend/tests/pipeline/test_short_form_render.py`:

```python
"""Tests for short_form_render helpers."""

from pipeline.short_form_render import _short_filename


class TestShortFilename:
    def test_basic_format(self):
        assert _short_filename("My Project", 1, 8) == "[short form 1/8] My Project.mp4"

    def test_handles_special_chars(self):
        # sanitize_filename strips < > : " / \ | ? *
        result = _short_filename("My/Project: Test", 5, 8)
        assert result == "[short form 5/8] MyProject Test.mp4"

    def test_last_of_8(self):
        assert _short_filename("Foo", 8, 8) == "[short form 8/8] Foo.mp4"

    def test_non_8_total(self):
        assert _short_filename("Bar", 2, 6) == "[short form 2/6] Bar.mp4"
```

- [ ] **Step 2: Run the tests to confirm they pass** (the implementation was added in Task 12).

Run: `cd backend && uv run pytest tests/pipeline/test_short_form_render.py -v`
Expected: 4 passed.

- [ ] **Step 3: Add render endpoints to `backend/api/short_form.py`.** Append after the existing intro endpoints:

```python
# --- Render endpoints ---


class RenderShortAllRequest(BaseModel):
    script_id: str


class RenderShortOneRequest(BaseModel):
    script_id: str
    segment_idx: int


def _validate_intros_present(content: ScriptContent) -> None:
    intros = content.short_intros or []
    intro_segments = {intro.segment_idx for intro in intros}
    missing = [i for i in range(len(content.segments)) if i not in intro_segments]
    if missing:
        raise HTTPException(
            status_code=400,
            detail=f"Missing intros for segments: {missing}. Generate intros first.",
        )


@router.post("/render/all", response_model=JobResponse)
def start_render_all_shorts(
    body: RenderShortAllRequest, session: Session = Depends(get_session)
):
    """Render all per-segment shorts in the background."""
    from pipeline.short_form_render import render_all_shorts

    content = _load_content(session, body.script_id)
    _validate_intros_present(content)

    record = session.get(Script, body.script_id)
    project_title = record.topic_title or "Untitled"
    total = len(content.segments)

    job = create_job(scene_count=total)
    logger.info("Starting render-all-shorts for script %s (%d segments)", body.script_id, total)

    def do_render():
        def on_progress(p: float, msg: str):
            update_job(job.id, progress=p, current_step=msg)

        urls = render_all_shorts(
            script_id=body.script_id,
            content=content,
            project_title=project_title,
            on_progress=on_progress,
        )
        for url in urls:
            job.output_urls.append(url)
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
    _validate_intros_present(content)

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

        url = render_short_segment(
            script_id=body.script_id,
            segment_idx=body.segment_idx,
            content=content,
            project_title=project_title,
            on_progress=on_progress,
        )
        job.output_urls.append(url)
        update_job(job.id, progress=1.0, current_step="Short rendered")
        return url

    run_in_background(job.id, do_render)
    return JobResponse(job_id=job.id)
```

- [ ] **Step 4: Verify routes are registered.**

Run: `cd backend && uv run python -c "from api import app; print([r.path for r in app.routes if 'short-form' in r.path])"`
Expected output now includes `/api/short-form/render/all` and `/api/short-form/render/one`.

- [ ] **Step 5: Commit.**

```bash
git add backend/api/short_form.py backend/tests/pipeline/test_short_form_render.py
git commit -m "Add short-form render endpoints with intro-gating validation"
```

---

## Task 14: Add frontend types + API client functions

**Files:**
- Modify: `frontend/src/types/render.ts`
- Modify: `frontend/src/api.ts`

- [ ] **Step 1: Add ShortIntro and short-form types.** Open `frontend/src/types/render.ts` and append:

```typescript
export interface ShortIntro {
  segment_idx: number;
  display_text: string;
  audio_url: string;
  duration_seconds: number;
  word_timestamps: { word: string; start_ms: number; end_ms: number }[];
}

export interface ShortFormJobStatus {
  job_id: string;
  status: "pending" | "running" | "completed" | "failed";
  progress: number;
  current_step: string;
  output_urls: string[];
  error: string | null;
  estimated_seconds: number | null;
  elapsed_seconds: number | null;
}
```

If `ScriptContent` is typed in this file or a sibling types file, add `short_intros?: ShortIntro[] | null` to it. If the frontend instead reads the script as `any` or `Record<string, unknown>`, skip this — the field will be accessed through the API response shape we already have.

- [ ] **Step 2: Open `frontend/src/api.ts` and add the short-form client functions.** Append near the other render functions:

```typescript
import type { ShortFormJobStatus } from "./types/render";

export async function generateShortIntrosAll(
  scriptId: string,
  force = false,
): Promise<{ job_id: string }> {
  const res = await fetch(`${API_BASE}/api/short-form/intros/generate-all`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ script_id: scriptId, force }),
  });
  if (!res.ok) throw new Error(`Failed to start intro generation: ${res.status}`);
  return res.json();
}

export async function generateShortIntroOne(
  scriptId: string,
  segmentIdx: number,
): Promise<{ job_id: string }> {
  const res = await fetch(`${API_BASE}/api/short-form/intros/generate-one`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ script_id: scriptId, segment_idx: segmentIdx }),
  });
  if (!res.ok) throw new Error(`Failed to start intro regen: ${res.status}`);
  return res.json();
}

export async function renderShortAll(scriptId: string): Promise<{ job_id: string }> {
  const res = await fetch(`${API_BASE}/api/short-form/render/all`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ script_id: scriptId }),
  });
  if (!res.ok) throw new Error(`Failed to start render-all: ${res.status}`);
  return res.json();
}

export async function renderShortOne(
  scriptId: string,
  segmentIdx: number,
): Promise<{ job_id: string }> {
  const res = await fetch(`${API_BASE}/api/short-form/render/one`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ script_id: scriptId, segment_idx: segmentIdx }),
  });
  if (!res.ok) throw new Error(`Failed to start render-one: ${res.status}`);
  return res.json();
}

export async function getShortFormJobStatus(jobId: string): Promise<ShortFormJobStatus> {
  const res = await fetch(`${API_BASE}/api/short-form/jobs/${jobId}`);
  if (!res.ok) throw new Error(`Failed to fetch job status: ${res.status}`);
  return res.json();
}
```

(Adjust `API_BASE` to match the existing convention — the file may use a different name like `BASE_URL` or `apiUrl`. Look at how existing functions like `getRenderStatus` build URLs and mirror that pattern.)

- [ ] **Step 3: Verify the frontend type-checks.**

Run: `cd frontend && npx tsc --noEmit`
Expected: no new errors. (Pre-existing errors unrelated to this change can be ignored.)

- [ ] **Step 4: Commit.**

```bash
git add frontend/src/types/render.ts frontend/src/api.ts
git commit -m "Add frontend types and API client functions for short-form export"
```

---

## Task 15: Build ShortIntrosCard component

**Files:**
- Create: `frontend/src/components/timeline/short-form/ShortIntrosCard.tsx`

- [ ] **Step 1: Create the component.** Write `frontend/src/components/timeline/short-form/ShortIntrosCard.tsx`:

```typescript
import { useState } from "react";
import {
  generateShortIntroOne,
  generateShortIntrosAll,
  getShortFormJobStatus,
  assetUrl,
} from "../../../api";
import { usePollJob } from "../../../hooks/usePollJob";
import type { ShortFormJobStatus, ShortIntro } from "../../../types/render";

interface Props {
  scriptId: string;
  videoTitle: string;
  segments: { name: string }[];
  intros: ShortIntro[] | null | undefined;
  onIntrosChanged: () => void;  // refetch script after generation completes
}

function buildDisplayPreview(videoTitle: string, segmentName: string): string {
  const stripped = videoTitle.replace(/^\d+\s+/, "");
  return `${stripped} — ${segmentName}`;
}

export default function ShortIntrosCard({
  scriptId,
  videoTitle,
  segments,
  intros,
  onIntrosChanged,
}: Props) {
  const [busy, setBusy] = useState(false);
  const [status, setStatus] = useState<ShortFormJobStatus | null>(null);

  const introMap = new Map<number, ShortIntro>();
  (intros ?? []).forEach((i) => introMap.set(i.segment_idx, i));
  const generatedCount = introMap.size;
  const total = segments.length;
  const allDone = generatedCount === total && total > 0;

  function isStale(idx: number): boolean {
    const existing = introMap.get(idx);
    if (!existing) return false;
    const expected = buildDisplayPreview(videoTitle, segments[idx].name);
    return existing.display_text !== expected;
  }

  const staleIndexes = segments
    .map((_, i) => i)
    .filter((i) => introMap.has(i) && isStale(i));

  const { startPolling } = usePollJob<ShortFormJobStatus>({
    pollFn: (id) => getShortFormJobStatus(id),
    isComplete: (s) => s.status === "completed",
    isFailed: (s) => s.status === "failed",
    onStatus: setStatus,
    onConnectionLost: () => setBusy(false),
  });

  async function handleGenerateAll() {
    setBusy(true);
    const { job_id } = await generateShortIntrosAll(scriptId, /* force */ false);
    startPolling(job_id, () => {
      setBusy(false);
      onIntrosChanged();
    });
  }

  async function handleRegenAll() {
    setBusy(true);
    const { job_id } = await generateShortIntrosAll(scriptId, /* force */ true);
    startPolling(job_id, () => {
      setBusy(false);
      onIntrosChanged();
    });
  }

  async function handleRegenOne(idx: number) {
    setBusy(true);
    const { job_id } = await generateShortIntroOne(scriptId, idx);
    startPolling(job_id, () => {
      setBusy(false);
      onIntrosChanged();
    });
  }

  const statusColor = allDone
    ? staleIndexes.length > 0
      ? "text-amber-400"
      : "text-emerald-400"
    : "text-amber-400";
  const statusLabel = allDone
    ? staleIndexes.length > 0
      ? `${generatedCount}/${total} generated · ${staleIndexes.length} stale`
      : `${total}/${total} generated`
    : `${generatedCount}/${total} generated — required before render`;

  return (
    <section className="bg-neutral-900 border border-neutral-800 rounded-xl p-4 space-y-3">
      <header className="flex items-center justify-between">
        <div>
          <h3 className="text-sm font-semibold text-neutral-200">Short Form Intros</h3>
          <p className={`text-xs ${statusColor}`}>{statusLabel}</p>
        </div>
        <div className="flex items-center gap-2">
          {!allDone && (
            <button
              onClick={handleGenerateAll}
              disabled={busy}
              className="text-sm px-3 py-1.5 bg-violet-600 hover:bg-violet-500 disabled:opacity-40 rounded-lg font-medium transition-colors"
            >
              Generate All Intros
            </button>
          )}
          {allDone && (
            <button
              onClick={handleRegenAll}
              disabled={busy}
              className="text-sm px-3 py-1.5 bg-neutral-800 hover:bg-neutral-700 disabled:opacity-40 rounded-lg font-medium transition-colors"
            >
              Regenerate All
            </button>
          )}
        </div>
      </header>

      {busy && status && (
        <div className="space-y-1">
          <div className="flex justify-between text-xs text-neutral-400">
            <span>{status.current_step || "Working..."}</span>
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
          const intro = introMap.get(idx);
          const stale = intro && isStale(idx);
          const preview = buildDisplayPreview(videoTitle, seg.name);
          return (
            <li key={idx} className="py-2 flex items-center gap-3">
              <div className="w-6 text-xs text-neutral-500 text-center">{idx + 1}</div>
              <div className="flex-1 min-w-0">
                <p className="text-sm text-neutral-200 truncate">{seg.name}</p>
                <p className="text-[11px] text-neutral-500 truncate">{preview}</p>
              </div>
              {intro && (
                <audio
                  src={assetUrl(intro.audio_url)}
                  controls
                  className="h-7"
                  style={{ maxWidth: 200 }}
                />
              )}
              <button
                onClick={() => handleRegenOne(idx)}
                disabled={busy}
                className={`text-xs px-2.5 py-1 rounded transition-colors ${
                  stale
                    ? "bg-amber-600 hover:bg-amber-500 text-white"
                    : intro
                      ? "bg-neutral-800 hover:bg-neutral-700 text-neutral-300"
                      : "bg-violet-600 hover:bg-violet-500 text-white"
                } disabled:opacity-40`}
              >
                {!intro ? "Generate" : stale ? "Regenerate (stale)" : "Regenerate"}
              </button>
            </li>
          );
        })}
      </ul>
    </section>
  );
}
```

- [ ] **Step 2: Verify the frontend type-checks.**

Run: `cd frontend && npx tsc --noEmit`
Expected: no errors related to this file. (If `usePollJob` has a different signature in the codebase, adjust the import/call accordingly.)

- [ ] **Step 3: Commit.**

```bash
git add frontend/src/components/timeline/short-form/ShortIntrosCard.tsx
git commit -m "Add ShortIntrosCard component for short-form intro generation gate"
```

---

## Task 16: Build RenderShortsCard component

**Files:**
- Create: `frontend/src/components/timeline/short-form/RenderShortsCard.tsx`

- [ ] **Step 1: Create the component.** Write `frontend/src/components/timeline/short-form/RenderShortsCard.tsx`:

```typescript
import { useState } from "react";
import {
  assetUrl,
  getShortFormJobStatus,
  renderShortAll,
  renderShortOne,
  showInFolder,
} from "../../../api";
import { usePollJob } from "../../../hooks/usePollJob";
import type { ShortFormJobStatus } from "../../../types/render";

interface Props {
  scriptId: string;
  introsReady: boolean;
  segments: { name: string }[];
  /** Map of segment_idx -> rendered short URL (web-relative path).
   * Caller can derive from script state by checking shorts files on disk via API,
   * or by storing render output URLs in component state across sessions. */
  renderedUrls: Record<number, string | undefined>;
  onRenderComplete: (segmentIdx: number, url: string) => void;
  onRequestGenerateIntros: () => void;
}

export default function RenderShortsCard({
  scriptId,
  introsReady,
  segments,
  renderedUrls,
  onRenderComplete,
  onRequestGenerateIntros,
}: Props) {
  const [busy, setBusy] = useState(false);
  const [status, setStatus] = useState<ShortFormJobStatus | null>(null);
  const [busySegment, setBusySegment] = useState<number | null>(null);
  const [confirmOpen, setConfirmOpen] = useState<null | { action: () => void }>(null);

  const total = segments.length;
  const renderedCount = Object.values(renderedUrls).filter(Boolean).length;
  const allDone = renderedCount === total;

  const { startPolling } = usePollJob<ShortFormJobStatus>({
    pollFn: (id) => getShortFormJobStatus(id),
    isComplete: (s) => s.status === "completed",
    isFailed: (s) => s.status === "failed",
    onStatus: setStatus,
    onConnectionLost: () => {
      setBusy(false);
      setBusySegment(null);
    },
  });

  function gate(action: () => void) {
    if (!introsReady) {
      setConfirmOpen({ action });
      return;
    }
    action();
  }

  async function handleRenderAll() {
    setBusy(true);
    const { job_id } = await renderShortAll(scriptId);
    startPolling(job_id, (finalStatus) => {
      setBusy(false);
      if (finalStatus && finalStatus.output_urls) {
        finalStatus.output_urls.forEach((url, i) => onRenderComplete(i, url));
      }
    });
  }

  async function handleRenderOne(idx: number) {
    setBusySegment(idx);
    const { job_id } = await renderShortOne(scriptId, idx);
    startPolling(job_id, (finalStatus) => {
      setBusySegment(null);
      if (finalStatus && finalStatus.output_urls?.[0]) {
        onRenderComplete(idx, finalStatus.output_urls[0]);
      }
    });
  }

  const disabled = !introsReady;

  return (
    <section
      className={`bg-neutral-900 border rounded-xl p-4 space-y-3 ${
        disabled ? "border-amber-900/50 opacity-70" : "border-neutral-800"
      }`}
    >
      <header className="flex items-center justify-between">
        <div>
          <h3 className="text-sm font-semibold text-neutral-200">Render Shorts</h3>
          <p
            className={`text-xs ${
              disabled ? "text-amber-400" : allDone ? "text-emerald-400" : "text-neutral-500"
            }`}
          >
            {disabled
              ? "Generate short-form intro voiceovers first."
              : `${renderedCount}/${total} rendered`}
          </p>
        </div>
        <button
          onClick={() => gate(handleRenderAll)}
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
              {url && (
                <button
                  onClick={() => {
                    const path = assetUrl(url);
                    // Locate the file in Finder via the downloads folder convention
                    if (window.api?.showItemInFolder) {
                      window.api.showItemInFolder(path);
                    }
                  }}
                  className="text-xs px-2.5 py-1 bg-neutral-800 hover:bg-neutral-700 rounded text-neutral-300"
                >
                  Show in Finder
                </button>
              )}
              <button
                onClick={() => gate(() => handleRenderOne(idx))}
                disabled={busy || busySegment !== null}
                className="text-xs px-2.5 py-1 bg-violet-600 hover:bg-violet-500 disabled:opacity-40 rounded text-white"
              >
                {segBusy ? "..." : url ? "Re-render" : "Render"}
              </button>
            </li>
          );
        })}
      </ul>

      {confirmOpen && (
        <div className="fixed inset-0 bg-black/60 z-[60] flex items-center justify-center p-8">
          <div className="bg-neutral-900 border border-neutral-800 rounded-xl max-w-md w-full p-5 space-y-4">
            <h4 className="text-sm font-semibold text-neutral-100">Generate intros first?</h4>
            <p className="text-sm text-neutral-400">
              You haven't generated short-form intro voiceovers yet. They're required for the title
              cards. Generate now and then render?
            </p>
            <div className="flex justify-end gap-2">
              <button
                onClick={() => setConfirmOpen(null)}
                className="text-sm px-3 py-1.5 bg-neutral-800 hover:bg-neutral-700 rounded text-neutral-300"
              >
                Cancel
              </button>
              <button
                onClick={() => {
                  setConfirmOpen(null);
                  onRequestGenerateIntros();
                }}
                className="text-sm px-3 py-1.5 bg-violet-600 hover:bg-violet-500 rounded text-white"
              >
                Generate Intros
              </button>
            </div>
          </div>
        </div>
      )}
    </section>
  );
}
```

- [ ] **Step 2: Verify the frontend type-checks.**

Run: `cd frontend && npx tsc --noEmit`
Expected: no new errors.

- [ ] **Step 3: Commit.**

```bash
git add frontend/src/components/timeline/short-form/RenderShortsCard.tsx
git commit -m "Add RenderShortsCard component with intro-gating confirm modal"
```

---

## Task 17: Build ShortFormTab and ShortFormStatusPill

**Files:**
- Create: `frontend/src/components/timeline/short-form/ShortFormTab.tsx`
- Create: `frontend/src/components/timeline/short-form/ShortFormStatusPill.tsx`

- [ ] **Step 1: Create ShortFormTab.** Write `frontend/src/components/timeline/short-form/ShortFormTab.tsx`:

```typescript
import { useEffect, useRef, useState } from "react";
import type { ShortIntro } from "../../../types/render";
import ShortIntrosCard from "./ShortIntrosCard";
import RenderShortsCard from "./RenderShortsCard";

interface Props {
  scriptId: string;
  videoTitle: string;
  segments: { name: string }[];
  intros: ShortIntro[] | null | undefined;
  onIntrosChanged: () => void;
  initialRenderedUrls?: Record<number, string | undefined>;
}

export default function ShortFormTab({
  scriptId,
  videoTitle,
  segments,
  intros,
  onIntrosChanged,
  initialRenderedUrls,
}: Props) {
  const introsRef = useRef<HTMLDivElement>(null);
  const [renderedUrls, setRenderedUrls] = useState<Record<number, string | undefined>>(
    initialRenderedUrls ?? {},
  );

  const introsReady =
    !!intros && intros.length === segments.length && segments.length > 0;

  // Hydrate rendered URLs from disk on mount by checking the expected static paths
  useEffect(() => {
    let cancelled = false;
    async function probe() {
      const found: Record<number, string | undefined> = {};
      for (let i = 0; i < segments.length; i++) {
        const path = `/static/projects/${scriptId}/renders/shorts/${i}.mp4`;
        try {
          const r = await fetch(path, { method: "HEAD" });
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
        Renders 8 short form videos, corresponding to the 8 segments. 1080x1920 9:16 30FPS
      </p>

      <div ref={introsRef}>
        <ShortIntrosCard
          scriptId={scriptId}
          videoTitle={videoTitle}
          segments={segments}
          intros={intros}
          onIntrosChanged={onIntrosChanged}
        />
      </div>

      <RenderShortsCard
        scriptId={scriptId}
        introsReady={introsReady}
        segments={segments}
        renderedUrls={renderedUrls}
        onRenderComplete={(idx, url) =>
          setRenderedUrls((prev) => ({ ...prev, [idx]: url }))
        }
        onRequestGenerateIntros={() => {
          introsRef.current?.scrollIntoView({ behavior: "smooth", block: "start" });
        }}
      />
    </div>
  );
}
```

- [ ] **Step 2: Create ShortFormStatusPill.** Write `frontend/src/components/timeline/short-form/ShortFormStatusPill.tsx`:

```typescript
import type { ShortIntro } from "../../../types/render";

interface Props {
  segments: { name: string }[];
  intros: ShortIntro[] | null | undefined;
  renderedCount: number;
  onClick: () => void;
}

export default function ShortFormStatusPill({
  segments,
  intros,
  renderedCount,
  onClick,
}: Props) {
  const total = segments.length;
  const introsCount = intros?.length ?? 0;
  const introsDone = introsCount === total;
  const rendersDone = renderedCount === total;
  const allDone = introsDone && rendersDone;
  const color = allDone
    ? "text-emerald-400 border-emerald-700/50 bg-emerald-900/20"
    : introsDone
      ? "text-violet-400 border-violet-700/50 bg-violet-900/20"
      : "text-neutral-400 border-neutral-700 bg-neutral-800/40";

  return (
    <button
      onClick={onClick}
      className={`text-[11px] px-2.5 py-1 rounded-full border transition-colors hover:opacity-90 ${color}`}
      title="Open short-form export"
    >
      Short Form: intros {introsCount}/{total} · renders {renderedCount}/{total}
    </button>
  );
}
```

- [ ] **Step 3: Verify the frontend type-checks.**

Run: `cd frontend && npx tsc --noEmit`
Expected: no new errors.

- [ ] **Step 4: Commit.**

```bash
git add frontend/src/components/timeline/short-form/ShortFormTab.tsx frontend/src/components/timeline/short-form/ShortFormStatusPill.tsx
git commit -m "Add ShortFormTab and ShortFormStatusPill components"
```

---

## Task 18: Wire ExportPanel tabs (rename + add short-form tab)

**Files:**
- Modify: `frontend/src/components/timeline/ExportPanel.tsx`

- [ ] **Step 1: Open `frontend/src/components/timeline/ExportPanel.tsx` and update the `Tab` type and `TABS` array.** Replace these lines (around line 49–55):

```typescript
type Tab = "render" | "thumbnails" | "seo";

const TABS: { key: Tab; label: string }[] = [
  { key: "render", label: "Render" },
  { key: "thumbnails", label: "Thumbnails" },
  { key: "seo", label: "SEO" },
];
```

with:

```typescript
type Tab = "render-long" | "render-short" | "thumbnails" | "seo";

const TABS: { key: Tab; label: string; description?: string }[] = [
  {
    key: "render-long",
    label: "Render - Long Form",
    description: "Renders the full long form video at 1920×1080 16:9 30FPS",
  },
  {
    key: "render-short",
    label: "Render - Short Form",
    description: "Renders 8 short form videos, corresponding to the 8 segments. 1080x1920 9:16 30FPS",
  },
  { key: "thumbnails", label: "Thumbnails" },
  { key: "seo", label: "SEO" },
];
```

- [ ] **Step 2: Update `activeTab` initial value.** Find:

```typescript
const [activeTab, setActiveTab] = useState<Tab>("render");
```

Replace with:

```typescript
const [activeTab, setActiveTab] = useState<Tab>("render-long");
```

- [ ] **Step 3: Update `tabBadges`.** Find:

```typescript
const tabBadges: Record<Tab, boolean> = {
  render: !!youtubeUrl,
  thumbnails: thumbnails.length > 0,
  seo: !!seoMetadata,
};
```

Replace with:

```typescript
const tabBadges: Record<Tab, boolean> = {
  "render-long": !!youtubeUrl,
  "render-short": false, // updated dynamically by ShortFormTab via prop drilling — see below
  thumbnails: thumbnails.length > 0,
  seo: !!seoMetadata,
};
```

- [ ] **Step 4: Update the render-tab body and add short-form tab body.** Find the existing render tab section (`{activeTab === "render" && (...)`, around line 439) and change `"render"` to `"render-long"`. Then find the closing `)}` of that block and immediately after it, add the new short-form tab body.

You'll need a few new props on `Props` for the short-form data — add them to the `interface Props { ... }` (around line 9):

```typescript
  // Short-form
  scriptId: string;
  videoTitle: string;
  segments: { name: string }[];
  shortIntros: ShortIntro[] | null | undefined;
  onShortIntrosChanged: () => void;
```

Import `ShortIntro` at the top:

```typescript
import type { ShortIntro } from "../../types/render";
import ShortFormTab from "./short-form/ShortFormTab";
```

Destructure the new props in the component signature. Then in the body, after the long-form render block:

```tsx
{activeTab === "render-short" && (
  <ShortFormTab
    scriptId={scriptId}
    videoTitle={videoTitle}
    segments={segments}
    intros={shortIntros}
    onIntrosChanged={onShortIntrosChanged}
  />
)}
```

- [ ] **Step 5: Render the active tab's description under the tab bar.** Find the `Tab Bar` div (around line 416) and immediately after the closing `</div>` of the tab bar, add:

```tsx
{TABS.find((t) => t.key === activeTab)?.description && (
  <div className="px-6 py-2 text-xs text-neutral-500 border-b border-neutral-800/50 shrink-0">
    {TABS.find((t) => t.key === activeTab)!.description}
  </div>
)}
```

- [ ] **Step 6: Update the parent that passes props to ExportPanel.** The parent is `TimelinePage.tsx` (or wherever `<ExportPanel ...>` is rendered). Find that JSX site and add the new props:

```tsx
<ExportPanel
  /* ...existing props... */
  scriptId={scriptId}
  videoTitle={script.title}
  segments={script.segments.map((s) => ({ name: s.name }))}
  shortIntros={script.short_intros}
  onShortIntrosChanged={refetchScript}
/>
```

(`refetchScript` is the existing function used to reload the script after other generation operations — find it in TimelinePage by searching for how the script is reloaded after, e.g., audio generation completes. Reuse that same function.)

- [ ] **Step 7: Verify the frontend type-checks and builds.**

Run: `cd frontend && npx tsc --noEmit`
Expected: no new errors.

Run: `cd frontend && npm run build`
Expected: build succeeds.

- [ ] **Step 8: Commit.**

```bash
git add frontend/src/components/timeline/ExportPanel.tsx frontend/src/components/timeline/TimelinePage.tsx
git commit -m "Rename Render tab to Render - Long Form and add Render - Short Form tab"
```

---

## Task 19: Mount ShortFormStatusPill in Timeline header

**Files:**
- Modify: `frontend/src/components/timeline/TimelinePage.tsx`

- [ ] **Step 1: Open `frontend/src/components/timeline/TimelinePage.tsx`.** Locate the header section (where existing indicators / buttons render — search for the export button or settings nav).

- [ ] **Step 2: Add state to track rendered short count and Export panel open + tab.** Near the existing `useState` calls, add:

```typescript
const [shortRenderCount, setShortRenderCount] = useState(0);
const [exportOpenTab, setExportOpenTab] = useState<"render-long" | "render-short">("render-long");
```

If the panel already uses an `isOpen` state, reuse it and add a function that opens it on a specific tab:

```typescript
function openExportOnShortForm() {
  setExportOpenTab("render-short");
  setExportPanelOpen(true);  // reuse existing state name
}
```

- [ ] **Step 3: Probe rendered shorts on mount** to populate `shortRenderCount` so the pill is accurate without opening the panel:

```typescript
useEffect(() => {
  let cancelled = false;
  async function probe() {
    if (!script) return;
    let found = 0;
    for (let i = 0; i < script.segments.length; i++) {
      try {
        const r = await fetch(`/static/projects/${scriptId}/renders/shorts/${i}.mp4`, {
          method: "HEAD",
        });
        if (r.ok) found++;
      } catch {
        /* ignore */
      }
    }
    if (!cancelled) setShortRenderCount(found);
  }
  probe();
  return () => {
    cancelled = true;
  };
}, [scriptId, script?.segments.length]);
```

- [ ] **Step 4: Render the pill in the header.** Import the component at the top:

```typescript
import ShortFormStatusPill from "./short-form/ShortFormStatusPill";
```

In the header JSX (next to existing render/export status indicators), add:

```tsx
{script && (
  <ShortFormStatusPill
    segments={script.segments.map((s) => ({ name: s.name }))}
    intros={script.short_intros}
    renderedCount={shortRenderCount}
    onClick={openExportOnShortForm}
  />
)}
```

- [ ] **Step 5: Make ExportPanel honor `exportOpenTab`.** This means passing an `initialTab` prop down to `ExportPanel`. Add a prop in `ExportPanel.tsx`:

```typescript
interface Props {
  /* ...existing... */
  initialTab?: Tab;
}
```

And in the body:

```typescript
const [activeTab, setActiveTab] = useState<Tab>(initialTab ?? "render-long");
```

Then in `TimelinePage.tsx`, when rendering `<ExportPanel ... />`, pass:

```tsx
initialTab={exportOpenTab}
```

- [ ] **Step 6: Verify the frontend type-checks and builds.**

Run: `cd frontend && npx tsc --noEmit && npm run build`
Expected: success.

- [ ] **Step 7: Commit.**

```bash
git add frontend/src/components/timeline/TimelinePage.tsx frontend/src/components/timeline/ExportPanel.tsx
git commit -m "Mount ShortFormStatusPill in Timeline header and open Export on short-form tab"
```

---

## Task 20: Manual end-to-end verification

**Goal:** Run the full system and exercise the short-form pipeline against a real project. Captures visual issues that no automated test catches.

- [ ] **Step 1: Start dev environment.**

Run: `npm run dev`
Wait for: backend on :8420, Vite on :5173, Electron window open.

- [ ] **Step 2: Open an existing project with all assets generated** (a project where all 8 scenes have images, audio, and a long-form render works). If none exists, create one through the normal flow first.

- [ ] **Step 3: Verify the Export panel changes.**
  - Click "Export" to open the panel.
  - Confirm the first tab is "Render - Long Form" and shows the description text under it.
  - Confirm there is a second tab "Render - Short Form" with the matching description.
  - Confirm "Thumbnails" and "SEO" tabs still exist and work.

- [ ] **Step 4: Verify the status pill.**
  - In the Timeline header, confirm the pill reads "Short Form: intros 0/8 · renders 0/8".
  - Click the pill — Export panel opens on the Render - Short Form tab.

- [ ] **Step 5: Generate intros.**
  - Click "Generate All Intros". Watch the progress bar advance per segment.
  - When complete, each row shows an audio scrubber. Click play on a few — confirm each says "{stripped title} — {segment name}".
  - Confirm the status pill updates to "intros 8/8".

- [ ] **Step 6: Try clicking "Render" before everything is ready.** (Skip if step 5 already completed all intros.)
  - Delete one intro audio file from disk to simulate a missing intro: `rm data/projects/<script_id>/audio/short_intro_3.mp3` and remove the corresponding entry from `script_json` via the DB (or temporarily reload). Click "Render All" — confirm the confirm modal appears with the message "Generate intros first?".

- [ ] **Step 7: Render a single short and inspect it.**
  - Click "Render" on segment 1.
  - When complete, open `~/Downloads/{project name}/[short form 1/8] {project name}.mp4` in QuickTime.
  - Verify visually:
    - 1080×1920 vertical frame.
    - Opens with a darkened/blurred backdrop image, title appearing word-by-word in the upper half (smaller, white), segment name appearing word-by-word in the lower half (larger, accent color).
    - Title VO reads "{stripped title} — {segment name}".
    - After the intro, narration scenes show focal image in the middle band, blurred-dim bands above and below, Eli top-center (not corner), subtitles centered in the bottom band.
    - Per-scene transitions still apply.
    - No chapter map zoom, no global progress bar, no segment timer/counter.

- [ ] **Step 8: Render all 8 and verify.**
  - Click "Render All 8 Shorts".
  - On completion, `~/Downloads/{project name}/` contains exactly the 8 expected files named `[short form N/8] {project name}.mp4`.
  - Status pill reads "renders 8/8".

- [ ] **Step 9: Test re-render overwrites.** Click "Re-render" on segment 4. Confirm the file mtime updates in `~/Downloads/{project name}/`.

- [ ] **Step 10: If any visual issue stands out** (blur too strong/weak, Eli too big/small, fonts too cramped, subtitles too low), open a follow-up task. Do NOT tune values inline as part of this task — the spec calls them out as visual-tuning items, and a fresh tuning pass with the design doc in hand is the right approach.

- [ ] **Step 11: Commit any tuning** (if you did adjust constants):

```bash
git add -p
git commit -m "Tune short-form visual constants after end-to-end verification"
```

---

## Self-Review Summary

**Spec coverage check:** Every section of the spec maps to at least one task above:
- Output format/filenames → Task 12, Task 13
- Composition per short (intro + scenes; stripped overlays) → Task 11
- Vertical scene layout (three-band) → Task 6, Task 9
- Eli adjustments (top-center, 380×380) → Task 7
- Multi-frame and subtitle-frame scenes → preserved by SceneRenderer (no special task needed beyond Task 9)
- Title card scene (backdrop, text content, two-zone layout, VO) → Task 1, Task 2, Task 10
- Subtitle re-tuning → Task 8
- Voiceover generation flow (backend) → Task 3, Task 4
- Voiceover generation flow (frontend) → Task 15
- Export panel UI changes → Task 18
- Status pill outside the tab → Task 17, Task 19
- Architecture (Python, Remotion, React) → Tasks 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13, 14, 15, 16, 17, 18, 19
- Edge cases (≠8 segments, missing audio, stale intros, render fail, contains_person) → Handled by existing fallback paths in the long-form render; staleness handled in Task 3 + Task 15
- Acceptance criteria → Verified in Task 20

**Placeholder scan:** No "TBD" / "implement later" placeholders. Two items intentionally defer to manual tuning (blur values, font ramps) per the spec's explicit visual-tuning callout — these are flagged in Task 20 as a tuning pass rather than guessed-at constants in the code.

**Type consistency check:**
- `ShortIntro` (Python and TypeScript) — same shape across Tasks 1, 5, 14.
- `Orientation` type — single source in `types.ts` (Task 5), consumed in Tasks 7, 8, 9, 11.
- Endpoint paths — `/api/short-form/intros/generate-all`, `/api/short-form/intros/generate-one`, `/api/short-form/render/all`, `/api/short-form/render/one`, `/api/short-form/jobs/{job_id}` — consistent across backend (Task 4, Task 13) and frontend (Task 14).
- Filename pattern — `[short form N/M] {project name}.mp4` — same in spec, render pipeline (Task 12), and tests (Task 13).
- File names — `short_intro_{idx}.mp3` (audio), `{idx}.mp4` (intermediate render) — consistent across Task 3, Task 12.
