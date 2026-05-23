# Static Canvas Visual Treatments Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add an always-on static canvas plus Phase 1 visual treatments: `full_frame`, `popup_sequence`, and `flipflop`.

**Architecture:** Store canvas and treatment data in `ScriptContent`/`Scene`, analyze treatments only after voiceover timing exists, generate panel assets as reusable visual layers, and render treatments through a Remotion treatment dispatcher layered over a global static canvas. Keep media source routing separate from visual treatment staging.

**Tech Stack:** Python 3.12/FastAPI/SQLModel/Pydantic, React 19/Vite/TypeScript/Tailwind 4, Remotion 4, SQLite app settings, existing dev-dashboard logging.

---

## File Map

- `backend/models/script.py`: Add `VisualCanvas`, `VisualLayer`, scene treatment fields, and validators.
- `backend/api/settings.py`: Allow the app-level visual canvas palette setting.
- `backend/api/visual_treatments.py`: New API for canvas updates, palette reads, treatment analysis jobs, treatment apply/manual updates.
- `backend/api/__init__.py`: Register the new router.
- `backend/pipeline/visual_treatments.py`: New analyzer, gate helpers, layer planner, palette utilities, and assignment application.
- `backend/pipeline/image_gen.py`: Add panel-generation helpers for visual layers.
- `backend/pipeline/render_phases.py`: Generate panel assets during the image phase.
- `backend/pipeline/remotion_render.py`: Pass canvas and treatment props to Remotion, including local panel asset paths.
- `backend/tests/test_visual_treatments.py`: Backend analyzer, gates, palette, and model tests.
- `backend/tests/pipeline/test_remotion_render.py`: Extend props conversion tests.
- `remotion/src/types.ts`: Add canvas/layer/treatment types.
- `remotion/src/FullVideo.tsx`: Pass canvas config into scenes.
- `remotion/src/scenes/SceneRenderer.tsx`: Render `StaticCanvas` under treatment renderer and dispatch treatments.
- `remotion/src/scenes/StaticCanvas.tsx`: New background canvas component.
- `remotion/src/scenes/TreatmentRenderer.tsx`: New treatment dispatcher and Phase 1 renderers.
- `frontend/src/types/script.ts`: Add canvas/layer/treatment types.
- `frontend/src/api.ts`: Add visual treatment API client types/functions.
- `frontend/src/components/timeline/VisualCanvasControls.tsx`: New hex input, swatch, and palette UI.
- `frontend/src/components/timeline/VisualTreatmentReviewPanel.tsx`: New scene treatment review UI.
- `frontend/src/components/timeline/MediaSourcesTab.tsx`: Add canvas controls and visual treatment section.
- `frontend/src/components/timeline/TimelinePage.tsx`: Add visual treatment state, handlers, polling, and content refresh.
- `docs/superpowers/specs/2026-05-23-static-canvas-visual-treatments-design.md`: Already written; use as source of truth.

## Task 1: Backend Models And Defaults

**Files:**
- Modify: `backend/models/script.py`
- Modify: `frontend/src/types/script.ts`
- Modify: `remotion/src/types.ts`
- Test: `backend/tests/test_visual_treatments.py`

- [ ] **Step 1: Write failing model tests**

Add `backend/tests/test_visual_treatments.py`:

```python
import json

from models.script import ScriptContent, Scene, VisualCanvas, VisualLayer


def test_visual_canvas_normalizes_hex_color():
    canvas = VisualCanvas(background_color="f6c54a")
    assert canvas.background_color == "#F6C54A"


def test_visual_canvas_invalid_color_falls_back_to_default():
    canvas = VisualCanvas(background_color="yellow")
    assert canvas.background_color == "#F6C54A"


def test_scene_defaults_to_full_frame_visual_treatment():
    scene = Scene(id="s1", narration="Hello.", visual_prompt="A simple scene")
    assert scene.visual_treatment == "full_frame"
    assert scene.visual_layers == []


def test_unknown_visual_treatment_normalizes_to_full_frame():
    scene = Scene(
        id="s1",
        narration="Hello.",
        visual_prompt="A simple scene",
        visual_treatment="unknown",
    )
    assert scene.visual_treatment == "full_frame"


def test_visual_layer_defaults_to_panel_image():
    layer = VisualLayer(id="panel_1", prompt="A small panel")
    assert layer.type == "image"
    assert layer.asset_kind == "panel"
    assert layer.placement == "center"
    assert layer.animation == "none"


def test_script_content_has_visual_canvas_default():
    content = ScriptContent(title="Test", segments=[])
    raw = json.loads(content.model_dump_json())
    assert raw["visual_canvas"]["background_color"] == "#F6C54A"
```

- [ ] **Step 2: Run model tests and verify failure**

Run:

```bash
uv run --project backend pytest backend/tests/test_visual_treatments.py -v
```

Expected: FAIL with import errors for `VisualCanvas` or missing `visual_treatment`.

- [ ] **Step 3: Add backend model types**

In `backend/models/script.py`, add after `FrameDirective`:

```python
VISUAL_TREATMENTS = {"full_frame", "popup_sequence", "flipflop"}
VISUAL_LAYER_TYPES = {"image"}
VISUAL_ASSET_KINDS = {"full_frame", "panel", "cutout"}
VISUAL_LAYER_ANIMATIONS = {"none", "pop_in"}


class VisualCanvas(BaseModel):
    """Video-level static canvas rendered beneath every scene."""

    background_color: str = "#F6C54A"

    @field_validator("background_color", mode="before")
    @classmethod
    def normalize_background_color(cls, value: object) -> str:
        if not isinstance(value, str):
            return "#F6C54A"
        text = value.strip().upper()
        if not text.startswith("#"):
            text = f"#{text}"
        if len(text) == 7 and all(ch in "0123456789ABCDEF" for ch in text[1:]):
            return text
        return "#F6C54A"


class VisualLayer(BaseModel):
    """A renderer-facing layer used by visual treatments."""

    id: str
    type: str = "image"
    asset_kind: str = "panel"
    image_url: str = ""
    prompt: str = ""
    placement: str = "center"
    enter_at_seconds: float = 0.0
    exit_at_seconds: float | None = None
    animation: str = "none"

    @field_validator("type", mode="before")
    @classmethod
    def normalize_type(cls, value: object) -> str:
        return value if isinstance(value, str) and value in VISUAL_LAYER_TYPES else "image"

    @field_validator("asset_kind", mode="before")
    @classmethod
    def normalize_asset_kind(cls, value: object) -> str:
        return value if isinstance(value, str) and value in VISUAL_ASSET_KINDS else "panel"

    @field_validator("animation", mode="before")
    @classmethod
    def normalize_animation(cls, value: object) -> str:
        return value if isinstance(value, str) and value in VISUAL_LAYER_ANIMATIONS else "none"
```

In `Scene`, add:

```python
    visual_treatment: str = "full_frame"  # "full_frame" | "popup_sequence" | "flipflop"
    visual_layers: list[VisualLayer] = []

    @field_validator("visual_treatment", mode="before")
    @classmethod
    def normalize_visual_treatment(cls, value: object) -> str:
        if isinstance(value, str) and value in VISUAL_TREATMENTS:
            return value
        return "full_frame"
```

In `ScriptContent`, add:

```python
    visual_canvas: VisualCanvas = VisualCanvas()
```

- [ ] **Step 4: Add frontend and Remotion types**

In `frontend/src/types/script.ts`, add:

```ts
export type VisualTreatment = "full_frame" | "popup_sequence" | "flipflop";

export interface VisualCanvas {
  background_color: string;
}

export interface VisualLayer {
  id: string;
  type: "image";
  asset_kind: "full_frame" | "panel" | "cutout";
  image_url?: string;
  prompt?: string;
  placement?: string;
  enter_at_seconds?: number;
  exit_at_seconds?: number | null;
  animation?: "none" | "pop_in";
}
```

Extend `Scene`:

```ts
  visual_treatment?: VisualTreatment;
  visual_layers?: VisualLayer[];
```

Extend `ScriptContent`:

```ts
  visual_canvas?: VisualCanvas;
```

In `remotion/src/types.ts`, add equivalent `VisualTreatment`, `VisualCanvas`, and `VisualLayer` interfaces. Extend `SceneInput` with:

```ts
  visual_treatment?: VisualTreatment;
  visual_layers?: VisualLayer[] | null;
```

Extend `FullVideoProps` and `ShortFormVideoProps` with:

```ts
  visual_canvas?: VisualCanvas | null;
```

- [ ] **Step 5: Run tests**

Run:

```bash
uv run --project backend pytest backend/tests/test_visual_treatments.py -v
```

Expected: PASS.

- [ ] **Step 6: Commit**

```bash
git add backend/models/script.py frontend/src/types/script.ts remotion/src/types.ts backend/tests/test_visual_treatments.py
git commit -m "Add visual treatment data models"
```

## Task 2: Canvas Palette And Canvas API

**Files:**
- Modify: `backend/api/settings.py`
- Create: `backend/api/visual_treatments.py`
- Modify: `backend/api/__init__.py`
- Test: `backend/tests/test_visual_treatments.py`

- [ ] **Step 1: Add failing palette and canvas API tests**

Append to `backend/tests/test_visual_treatments.py`:

```python
from sqlmodel import Session

from api.visual_treatments import (
    VISUAL_CANVAS_COLOR_PALETTE_KEY,
    add_palette_color,
    get_canvas_palette,
    update_visual_canvas,
    UpdateVisualCanvasRequest,
)
from models.settings import AppSetting
from models.script import Script


def test_palette_adds_recent_first_and_dedupes(tmp_path):
    from database import engine

    with Session(engine) as session:
        session.merge(AppSetting(key=VISUAL_CANVAS_COLOR_PALETTE_KEY, value='["#111111", "#222222"]'))
        session.commit()
        palette = add_palette_color(session, "#222222")
        assert palette[0] == "#222222"
        assert palette.count("#222222") == 1


def test_update_visual_canvas_persists_script_color_and_palette(tmp_path):
    from database import engine

    script = Script(
        id="canvas-script",
        brand_id="brand",
        topic_title="Canvas Test",
        script_json=ScriptContent(title="Canvas Test", segments=[]).model_dump_json(),
    )
    with Session(engine) as session:
        session.add(script)
        session.commit()
        response = update_visual_canvas(
            "canvas-script",
            UpdateVisualCanvasRequest(background_color="abcdef"),
            session,
        )
        assert response.script.visual_canvas.background_color == "#ABCDEF"
        assert "#ABCDEF" in get_canvas_palette(session).colors
```

- [ ] **Step 2: Run tests and verify failure**

Run:

```bash
uv run --project backend pytest backend/tests/test_visual_treatments.py -v
```

Expected: FAIL with missing `api.visual_treatments`.

- [ ] **Step 3: Allow the palette setting**

In `backend/api/settings.py`, add this constant near other setting keys:

```python
VISUAL_CANVAS_COLOR_PALETTE_KEY = "VISUAL_CANVAS_COLOR_PALETTE"
```

Add it to `ALLOWED_KEYS`, `_PLAINTEXT_KEYS`, and `_DEFAULTS`:

```python
VISUAL_CANVAS_COLOR_PALETTE_KEY,
```

```python
VISUAL_CANVAS_COLOR_PALETTE_KEY: '["#F6C54A"]',
```

- [ ] **Step 4: Create visual treatments API**

Create `backend/api/visual_treatments.py`:

```python
"""Visual canvas and visual treatment endpoints."""

import json
import logging

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlmodel import Session

from database import get_session
from models.script import Script, ScriptContent
from models.settings import AppSetting
from pipeline.render_cache import mark_render_inputs_changed

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/visual-treatments", tags=["visual-treatments"])

VISUAL_CANVAS_COLOR_PALETTE_KEY = "VISUAL_CANVAS_COLOR_PALETTE"
DEFAULT_CANVAS_COLOR = "#F6C54A"
MAX_PALETTE_COLORS = 24


class CanvasPaletteResponse(BaseModel):
    colors: list[str]


class UpdateVisualCanvasRequest(BaseModel):
    background_color: str


class UpdateVisualCanvasResponse(BaseModel):
    script: ScriptContent
    palette: list[str]


def normalize_hex_color(value: str) -> str:
    text = value.strip().upper()
    if not text.startswith("#"):
        text = f"#{text}"
    if len(text) == 7 and all(ch in "0123456789ABCDEF" for ch in text[1:]):
        return text
    raise HTTPException(status_code=400, detail="Enter a valid 6-digit hex color.")


def get_canvas_palette(session: Session) -> CanvasPaletteResponse:
    row = session.get(AppSetting, VISUAL_CANVAS_COLOR_PALETTE_KEY)
    if not row or not row.value:
        return CanvasPaletteResponse(colors=[DEFAULT_CANVAS_COLOR])
    try:
        raw = json.loads(row.value)
    except json.JSONDecodeError:
        logger.warning("[VISUAL_CANVAS] invalid palette JSON; resetting to default")
        return CanvasPaletteResponse(colors=[DEFAULT_CANVAS_COLOR])
    colors: list[str] = []
    for item in raw if isinstance(raw, list) else []:
        if not isinstance(item, str):
            continue
        try:
            color = normalize_hex_color(item)
        except HTTPException:
            continue
        if color not in colors:
            colors.append(color)
    return CanvasPaletteResponse(colors=colors or [DEFAULT_CANVAS_COLOR])


def add_palette_color(session: Session, color: str) -> list[str]:
    normalized = normalize_hex_color(color)
    current = get_canvas_palette(session).colors
    next_colors = [normalized] + [c for c in current if c != normalized]
    next_colors = next_colors[:MAX_PALETTE_COLORS]
    session.merge(AppSetting(
        key=VISUAL_CANVAS_COLOR_PALETTE_KEY,
        value=json.dumps(next_colors),
    ))
    session.commit()
    logger.info("[VISUAL_CANVAS] palette updated; added=%s size=%d", normalized, len(next_colors))
    return next_colors


@router.get("/palette", response_model=CanvasPaletteResponse)
def read_canvas_palette(session: Session = Depends(get_session)):
    return get_canvas_palette(session)


@router.put("/{script_id}/canvas", response_model=UpdateVisualCanvasResponse)
def update_visual_canvas(
    script_id: str,
    body: UpdateVisualCanvasRequest,
    session: Session = Depends(get_session),
):
    record = session.get(Script, script_id)
    if not record:
        raise HTTPException(status_code=404, detail="Script not found")
    color = normalize_hex_color(body.background_color)
    content = ScriptContent.model_validate(json.loads(record.script_json))
    old_color = content.visual_canvas.background_color
    content.visual_canvas.background_color = color
    record.script_json = content.model_dump_json()
    session.add(record)
    session.commit()
    palette = add_palette_color(session, color)
    mark_render_inputs_changed(script_id)
    logger.info("[VISUAL_CANVAS] script=%s old=%s new=%s", script_id, old_color, color)
    return UpdateVisualCanvasResponse(script=content, palette=palette)
```

- [ ] **Step 5: Register the router**

In `backend/api/__init__.py`, import and include:

```python
from api.visual_treatments import router as visual_treatments_router
```

```python
app.include_router(visual_treatments_router)
```

- [ ] **Step 6: Run tests**

Run:

```bash
uv run --project backend pytest backend/tests/test_visual_treatments.py backend/tests/test_eli_enabled_default_setting.py -v
```

Expected: PASS.

- [ ] **Step 7: Commit**

```bash
git add backend/api/settings.py backend/api/visual_treatments.py backend/api/__init__.py backend/tests/test_visual_treatments.py
git commit -m "Add visual canvas palette API"
```

## Task 3: Visual Treatment Analyzer And Apply Flow

**Files:**
- Create: `backend/pipeline/visual_treatments.py`
- Modify: `backend/api/visual_treatments.py`
- Test: `backend/tests/test_visual_treatments.py`

- [ ] **Step 1: Add failing analyzer tests**

Append to `backend/tests/test_visual_treatments.py`:

```python
import pytest

from pipeline.render_jobs import UserFacingJobError
from pipeline.visual_treatments import (
    VisualTreatmentAssignment,
    apply_visual_treatment_assignments,
    analyze_visual_treatments,
    require_visual_treatment_voiceover,
)


def scene_with_words(scene_id: str, narration: str) -> Scene:
    words = []
    cursor = 0
    for idx, word in enumerate(narration.replace(",", "").replace(".", "").split()):
        words.append({"word": word, "start_ms": cursor, "end_ms": cursor + 300})
        cursor += 350
    return Scene(
        id=scene_id,
        narration=narration,
        visual_prompt=f"Panel for {scene_id}",
        audio_duration_seconds=max(cursor / 1000, 1.0),
        word_timestamps=words,
    )


def content_with_scenes(*scenes: Scene) -> ScriptContent:
    return ScriptContent(title="Treatment Test", segments=[{"name": "Segment", "scenes": list(scenes)}])


def test_visual_treatment_gate_requires_audio_duration():
    content = content_with_scenes(Scene(id="s1", narration="No audio.", visual_prompt="x"))
    with pytest.raises(UserFacingJobError) as exc:
        require_visual_treatment_voiceover(content)
    assert "Generate voiceover first" in str(exc.value)


def test_visual_treatment_gate_requires_word_timestamps():
    content = content_with_scenes(Scene(id="s1", narration="No words.", visual_prompt="x", audio_duration_seconds=2.0))
    with pytest.raises(UserFacingJobError) as exc:
        require_visual_treatment_voiceover(content)
    assert "word timing" in str(exc.value)


def test_analyze_visual_treatments_assigns_popup_sequence_for_list():
    scene = scene_with_words("s1", "They learned to keep your head down, hide feelings, and never be different.")
    assignments = analyze_visual_treatments(content_with_scenes(scene), script_id="script")
    assignment = assignments[0]
    assert assignment.visual_treatment == "popup_sequence"
    assert 2 <= len(assignment.visual_layers) <= 4
    assert assignment.visual_layers[0].enter_at_seconds <= assignment.visual_layers[-1].enter_at_seconds


def test_analyze_visual_treatments_assigns_flipflop_for_two_state_contrast():
    scene = scene_with_words("s1", "Part of him wanted freedom, but part of him feared rejection.")
    assignment = analyze_visual_treatments(content_with_scenes(scene), script_id="script")[0]
    assert assignment.visual_treatment == "flipflop"
    assert len(assignment.visual_layers) == 2


def test_apply_visual_treatment_assignments_updates_matching_scenes():
    scene = scene_with_words("s1", "Again and again, he tried and failed.")
    content = content_with_scenes(scene)
    assignment = VisualTreatmentAssignment(
        scene_id="s1",
        visual_treatment="flipflop",
        reasoning="Two-state loop.",
        visual_layers=[],
    )
    apply_visual_treatment_assignments(content, [assignment])
    assert content.segments[0].scenes[0].visual_treatment == "flipflop"
```

- [ ] **Step 2: Run tests and verify failure**

Run:

```bash
uv run --project backend pytest backend/tests/test_visual_treatments.py -v
```

Expected: FAIL with missing `pipeline.visual_treatments`.

- [ ] **Step 3: Implement analyzer module**

Create `backend/pipeline/visual_treatments.py`:

```python
"""Visual treatment analysis and layer planning."""

import logging
import re
from pydantic import BaseModel

from models.script import ScriptContent, Scene, VisualLayer
from pipeline.render_jobs import UserFacingJobError

logger = logging.getLogger(__name__)

ALLOWED_VISUAL_TREATMENTS = {"full_frame", "popup_sequence", "flipflop"}
VIDEO_MEDIA_SOURCES = {"ai_video", "gameplay_video", "user_upload", "stock_photo"}


class VisualTreatmentAssignment(BaseModel):
    scene_id: str
    visual_treatment: str
    reasoning: str = ""
    visual_layers: list[VisualLayer] = []


def missing_visual_treatment_voiceover_scene_ids(content: ScriptContent) -> tuple[list[str], list[str]]:
    missing_audio: list[str] = []
    missing_words: list[str] = []
    for scene in content.all_scenes():
        if scene.is_title_card:
            continue
        if scene.audio_duration_seconds <= 0:
            missing_audio.append(scene.id)
        elif not scene.word_timestamps:
            missing_words.append(scene.id)
    return missing_audio, missing_words


def visual_treatment_voiceover_required_message(audio_count: int, word_count: int) -> str:
    parts = ["Generate voiceover first so visual treatments can sync to words."]
    if audio_count:
        parts.append(f"{audio_count} scene(s) are missing audio duration timing.")
    if word_count:
        parts.append(f"{word_count} scene(s) are missing word timing.")
    return " ".join(parts)


def require_visual_treatment_voiceover(content: ScriptContent) -> None:
    missing_audio, missing_words = missing_visual_treatment_voiceover_scene_ids(content)
    if missing_audio or missing_words:
        logger.info(
            "[VISUAL_TREATMENT] blocked; missing_audio=%d missing_word_timing=%d scene_ids=%s",
            len(missing_audio),
            len(missing_words),
            ",".join(missing_audio + missing_words),
        )
        raise UserFacingJobError(
            visual_treatment_voiceover_required_message(len(missing_audio), len(missing_words))
        )


def _word_time(scene: Scene, target: str, fallback_seconds: float) -> float:
    target_words = re.findall(r"[a-z0-9']+", target.lower())
    if not target_words or not scene.word_timestamps:
        return fallback_seconds
    first = target_words[0]
    for word in scene.word_timestamps:
        if re.sub(r"[^a-z0-9']", "", word.word.lower()) == first:
            return round(word.start_ms / 1000, 2)
    return fallback_seconds


def _list_items(narration: str) -> list[str]:
    text = narration.strip()
    if "," not in text and " and " not in text.lower():
        return []
    rough = re.split(r",|;|\\band\\b|\\bor\\b", text, flags=re.IGNORECASE)
    items = [item.strip(" .") for item in rough if len(item.strip(" .")) >= 4]
    if len(items) < 2:
        return []
    return items[-4:]


def _has_two_state_contrast(narration: str) -> bool:
    text = narration.lower()
    markers = [
        " but ",
        " on one hand ",
        " on the other hand ",
        " again and again",
        " over and over",
        " before ",
        " after ",
        " wanted ",
        " feared ",
    ]
    return any(marker in text for marker in markers)


def _panel_prompt(scene: Scene, item: str) -> str:
    return (
        "Create a small framed Headless Hero cartoon illustration panel. "
        "This panel will sit on a flat static color background, so keep it simple, bold, and readable. "
        "Do not design a full video background. No text in the image. "
        f"Panel subject: {item}. Scene context: {scene.visual_prompt or scene.narration}"
    )


def _popup_layers(scene: Scene, items: list[str]) -> list[VisualLayer]:
    placements = {
        2: ["left", "right"],
        3: ["left", "center", "right"],
        4: ["top-left", "top-right", "bottom-left", "bottom-right"],
    }[len(items)]
    layers: list[VisualLayer] = []
    for idx, item in enumerate(items):
        fallback = min(scene.audio_duration_seconds - 0.4, 0.8 + idx * 1.0)
        layers.append(VisualLayer(
            id=f"{scene.id}_panel_{idx + 1}",
            type="image",
            asset_kind="panel",
            prompt=_panel_prompt(scene, item),
            placement=placements[idx],
            enter_at_seconds=max(0.0, _word_time(scene, item, fallback)),
            animation="pop_in",
        ))
    return layers


def _flipflop_layers(scene: Scene) -> list[VisualLayer]:
    return [
        VisualLayer(
            id=f"{scene.id}_state_a",
            type="image",
            asset_kind="panel",
            prompt=_panel_prompt(scene, f"First emotional or visual state from: {scene.narration}"),
            placement="center",
            enter_at_seconds=0.0,
        ),
        VisualLayer(
            id=f"{scene.id}_state_b",
            type="image",
            asset_kind="panel",
            prompt=_panel_prompt(scene, f"Contrasting emotional or visual state from: {scene.narration}"),
            placement="center",
            enter_at_seconds=0.5,
        ),
    ]


def analyze_visual_treatments(content: ScriptContent, *, script_id: str) -> list[VisualTreatmentAssignment]:
    require_visual_treatment_voiceover(content)
    logger.info(
        "[VISUAL_TREATMENT] analysis requested; script=%s scenes=%d format=%s",
        script_id,
        len(content.all_scenes()),
        content.format_id,
    )
    assignments: list[VisualTreatmentAssignment] = []
    for scene in content.all_scenes():
        if scene.is_title_card or scene.media_source in VIDEO_MEDIA_SOURCES:
            assignment = VisualTreatmentAssignment(
                scene_id=scene.id,
                visual_treatment="full_frame",
                reasoning="Title cards and video/photo-backed scenes use full-frame treatment in Phase 1.",
            )
        else:
            items = _list_items(scene.narration)
            if 2 <= len(items) <= 4:
                assignment = VisualTreatmentAssignment(
                    scene_id=scene.id,
                    visual_treatment="popup_sequence",
                    visual_layers=_popup_layers(scene, items),
                    reasoning="Narration contains a clear list or sequence.",
                )
            elif _has_two_state_contrast(scene.narration):
                assignment = VisualTreatmentAssignment(
                    scene_id=scene.id,
                    visual_treatment="flipflop",
                    visual_layers=_flipflop_layers(scene),
                    reasoning="Narration contains contrast or repeated two-state motion.",
                )
            else:
                assignment = VisualTreatmentAssignment(
                    scene_id=scene.id,
                    visual_treatment="full_frame",
                    reasoning="No clear layered treatment signal.",
                )
        logger.info(
            "[VISUAL_TREATMENT] scene=%s treatment=%s layers=%d reason=%s",
            assignment.scene_id,
            assignment.visual_treatment,
            len(assignment.visual_layers),
            assignment.reasoning,
        )
        assignments.append(assignment)
    return assignments


def apply_visual_treatment_assignments(
    content: ScriptContent,
    assignments: list[VisualTreatmentAssignment],
) -> None:
    by_id = {assignment.scene_id: assignment for assignment in assignments}
    for scene in content.all_scenes():
        assignment = by_id.get(scene.id)
        if not assignment:
            continue
        treatment = assignment.visual_treatment if assignment.visual_treatment in ALLOWED_VISUAL_TREATMENTS else "full_frame"
        if treatment != assignment.visual_treatment:
            logger.info(
                "[VISUAL_TREATMENT] normalized scene=%s unknown=%s fallback=full_frame",
                scene.id,
                assignment.visual_treatment,
            )
        scene.visual_treatment = treatment
        scene.visual_layers = assignment.visual_layers if treatment != "full_frame" else []
```

- [ ] **Step 4: Add API models and endpoints**

Append to `backend/api/visual_treatments.py`:

```python
from pipeline.render_jobs import UserFacingJobError, create_job, get_job, run_in_background, update_job
from pipeline.visual_treatments import (
    VisualTreatmentAssignment,
    analyze_visual_treatments,
    apply_visual_treatment_assignments,
    require_visual_treatment_voiceover,
)
```

Add models:

```python
class AnalyzeVisualTreatmentsResponse(BaseModel):
    job_id: str


class ApplyVisualTreatmentsRequest(BaseModel):
    assignments: list[VisualTreatmentAssignment]


class ApplyVisualTreatmentsResponse(BaseModel):
    ok: bool
    script: ScriptContent


class UpdateVisualTreatmentRequest(BaseModel):
    scene_id: str
    visual_treatment: str
```

Add endpoints:

```python
@router.post("/{script_id}/analyze", response_model=AnalyzeVisualTreatmentsResponse)
def analyze_script_visual_treatments(script_id: str, session: Session = Depends(get_session)):
    record = session.get(Script, script_id)
    if not record:
        raise HTTPException(status_code=404, detail="Script not found")
    content = ScriptContent.model_validate(json.loads(record.script_json))
    try:
        require_visual_treatment_voiceover(content)
    except UserFacingJobError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc

    job = create_job()
    job_id = job.id

    def _run() -> list[str]:
        from database import engine
        from sqlmodel import Session as SqlSession

        update_job(job_id, current_step="Analyzing visual treatments...")
        with SqlSession(engine) as bg_session:
            rec = bg_session.get(Script, script_id)
            if not rec:
                raise RuntimeError(f"Script {script_id} not found")
            fresh_content = ScriptContent.model_validate(json.loads(rec.script_json))
            assignments = analyze_visual_treatments(fresh_content, script_id=script_id)
            update_job(job_id, output_data=json.dumps([a.model_dump() for a in assignments]))
        return [script_id]

    run_in_background(job_id, _run)
    return AnalyzeVisualTreatmentsResponse(job_id=job_id)


@router.get("/analyze/status/{job_id}")
def visual_treatment_status(job_id: str):
    job = get_job(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    result = job.to_dict()
    if job.status == "completed" and job.output_data:
        result["assignments"] = json.loads(job.output_data)
    return result


@router.post("/{script_id}/apply", response_model=ApplyVisualTreatmentsResponse)
def apply_script_visual_treatments(
    script_id: str,
    body: ApplyVisualTreatmentsRequest,
    session: Session = Depends(get_session),
):
    record = session.get(Script, script_id)
    if not record:
        raise HTTPException(status_code=404, detail="Script not found")
    content = ScriptContent.model_validate(json.loads(record.script_json))
    apply_visual_treatment_assignments(content, body.assignments)
    record.script_json = content.model_dump_json()
    session.add(record)
    session.commit()
    mark_render_inputs_changed(script_id)
    return ApplyVisualTreatmentsResponse(ok=True, script=content)


@router.put("/{script_id}/scene", response_model=ApplyVisualTreatmentsResponse)
def update_scene_visual_treatment(
    script_id: str,
    body: UpdateVisualTreatmentRequest,
    session: Session = Depends(get_session),
):
    record = session.get(Script, script_id)
    if not record:
        raise HTTPException(status_code=404, detail="Script not found")
    content = ScriptContent.model_validate(json.loads(record.script_json))
    assignment = VisualTreatmentAssignment(
        scene_id=body.scene_id,
        visual_treatment=body.visual_treatment,
        reasoning="Manual visual treatment override.",
        visual_layers=[],
    )
    apply_visual_treatment_assignments(content, [assignment])
    record.script_json = content.model_dump_json()
    session.add(record)
    session.commit()
    mark_render_inputs_changed(script_id)
    return ApplyVisualTreatmentsResponse(ok=True, script=content)
```

- [ ] **Step 5: Run tests**

Run:

```bash
uv run --project backend pytest backend/tests/test_visual_treatments.py -v
```

Expected: PASS.

- [ ] **Step 6: Commit**

```bash
git add backend/pipeline/visual_treatments.py backend/api/visual_treatments.py backend/tests/test_visual_treatments.py
git commit -m "Add visual treatment analyzer"
```

## Task 4: Panel Generation

**Files:**
- Modify: `backend/pipeline/image_gen.py`
- Modify: `backend/pipeline/render_phases.py`
- Test: `backend/tests/test_visual_treatments.py`

- [ ] **Step 1: Add failing panel generation unit test**

Append to `backend/tests/test_visual_treatments.py`:

```python
from pipeline.image_gen import visual_layer_image_filename


def test_visual_layer_image_filename_is_stable_and_png():
    assert visual_layer_image_filename("scene_001", "scene_001_panel_1") == "scene_001_layer_scene_001_panel_1.png"
```

- [ ] **Step 2: Run the test and verify failure**

Run:

```bash
uv run --project backend pytest backend/tests/test_visual_treatments.py::test_visual_layer_image_filename_is_stable_and_png -v
```

Expected: FAIL with missing function.

- [ ] **Step 3: Add visual layer panel generation helpers**

In `backend/pipeline/image_gen.py`, add near frame generation helpers:

```python
def visual_layer_image_filename(scene_id: str, layer_id: str) -> str:
    safe_layer = "".join(ch if ch.isalnum() or ch in {"_", "-"} else "_" for ch in layer_id)
    return f"{scene_id}_layer_{safe_layer}.png"


def generate_visual_layer_panels(
    scene_id: str,
    layers: list[dict],
    script_id: str,
    width: int = IMAGE_WIDTH,
    height: int = IMAGE_HEIGHT,
    force: bool = False,
) -> list[dict]:
    """Generate image assets for visual treatment panel layers."""
    images_dir = DATA_DIR / "projects" / script_id / "images"
    images_dir.mkdir(parents=True, exist_ok=True)
    updated: list[dict] = []
    for raw in layers:
        layer = dict(raw)
        if layer.get("type", "image") != "image" or layer.get("asset_kind", "panel") != "panel":
            updated.append(layer)
            continue
        layer_id = str(layer.get("id") or f"{scene_id}_layer_{len(updated) + 1}")
        filename = visual_layer_image_filename(scene_id, layer_id)
        local_path = images_dir / filename
        prompt_marker = images_dir / f"{filename}.prompt"
        web_path = f"/static/projects/{script_id}/images/{filename}"
        prompt = str(layer.get("prompt") or "").strip()
        if not prompt:
            logger.info("[PANEL_GEN] skipped empty prompt scene=%s layer=%s", scene_id, layer_id)
            updated.append(layer)
            continue
        if not force and local_path.exists() and prompt_marker.exists() and prompt_marker.read_text(encoding="utf-8").strip() == prompt:
            logger.info("[PANEL_GEN] cache hit scene=%s layer=%s", scene_id, layer_id)
            layer["image_url"] = web_path
            updated.append(layer)
            continue
        logger.info("[PANEL_GEN] start scene=%s layer=%s prompt=%s", scene_id, layer_id, prompt[:120])
        tmp_path = generate_image(
            prompt,
            width=width,
            height=height,
            reference_image_path=None,
            original_prompt=prompt,
            script_id=script_id,
        )
        metadata = _move_generated_image(tmp_path, local_path, {
            "source_type": "visual_layer_panel",
            "provider": os.environ.get("IMAGE_PROVIDER", "google"),
            "fallback": False,
        })
        prompt_marker.write_text(prompt, encoding="utf-8")
        layer["image_url"] = web_path
        layer["visual_source_metadata"] = metadata
        logger.info("[PANEL_GEN] complete scene=%s layer=%s output=%s", scene_id, layer_id, local_path)
        updated.append(layer)
    return updated
```

- [ ] **Step 4: Call panel generation from image phase**

In `backend/pipeline/render_phases.py`, update `_phase_images` to import the panel helper and persist generated visual layer URLs through `sc_info`.

Change the import inside `_phase_images` from:

```python
from pipeline.image_gen import generate_scene_image
```

to:

```python
from pipeline.image_gen import generate_scene_image, generate_visual_layer_panels
```

After:

```python
        sc_info["_image_url"] = image_url
        sc_info["_frame_urls"] = None
```

add:

```python
        visual_treatment = sc_info.get("visual_treatment", "full_frame")
        visual_layers = sc_info.get("visual_layers") or []
        if visual_treatment in {"popup_sequence", "flipflop"} and visual_layers:
            logger.info(
                "[VISUAL_TREATMENT] generating panels scene=%s treatment=%s layers=%d",
                sid,
                visual_treatment,
                len(visual_layers),
            )
            updated_layers = generate_visual_layer_panels(
                sid,
                visual_layers,
                ctx.script_id,
            )
            sc_info["_visual_layers"] = updated_layers
```

In `_phase_persist`, import `VisualLayer` inside the function:

```python
from models.script import VisualLayer
```

After phrase timestamp persistence:

```python
            sc.phrase_timestamps = sc_info.get("_phrase_timestamps", sc.phrase_timestamps)
```

add:

```python
            if "_visual_layers" in sc_info:
                sc.visual_layers = [
                    VisualLayer.model_validate(layer)
                    for layer in sc_info["_visual_layers"]
                ]
```

- [ ] **Step 5: Run tests**

Run:

```bash
uv run --project backend pytest backend/tests/test_visual_treatments.py backend/tests/test_media_source_dispatch.py -v
```

Expected: PASS.

- [ ] **Step 6: Commit**

```bash
git add backend/pipeline/image_gen.py backend/pipeline/render_phases.py backend/tests/test_visual_treatments.py
git commit -m "Generate panel assets for visual treatments"
```

## Task 5: Remotion Props And Treatment Rendering

**Files:**
- Modify: `backend/pipeline/remotion_render.py`
- Modify: `remotion/src/FullVideo.tsx`
- Modify: `remotion/src/scenes/SceneRenderer.tsx`
- Create: `remotion/src/scenes/StaticCanvas.tsx`
- Create: `remotion/src/scenes/TreatmentRenderer.tsx`
- Test: `backend/tests/pipeline/test_remotion_render.py`

- [ ] **Step 1: Add failing Remotion props test**

Append to `backend/tests/pipeline/test_remotion_render.py`:

```python
def test_scene_to_input_props_includes_visual_treatment_layers(tmp_path):
    scene = Scene(
        id="scene_layered",
        narration="A list appears.",
        visual_prompt="x",
        audio_duration_seconds=2.0,
        visual_treatment="popup_sequence",
        visual_layers=[
            {
                "id": "panel_1",
                "type": "image",
                "asset_kind": "panel",
                "image_url": "/static/projects/script/images/scene_layered_layer_panel_1.png",
                "placement": "left",
                "enter_at_seconds": 0.5,
                "animation": "pop_in",
            }
        ],
    )
    props = remotion_render._scene_to_input_props(scene, "script")
    assert props["visual_treatment"] == "popup_sequence"
    assert props["visual_layers"][0]["placement"] == "left"
    assert props["visual_layers"][0]["image_path"].endswith("scene_layered_layer_panel_1.png")
```

- [ ] **Step 2: Run props test and verify failure**

Run:

```bash
uv run --project backend pytest backend/tests/pipeline/test_remotion_render.py::test_scene_to_input_props_includes_visual_treatment_layers -v
```

Expected: FAIL because props do not include treatment fields.

- [ ] **Step 3: Pass treatment props**

In `backend/pipeline/remotion_render.py`, add:

```python
def _visual_layers_to_input_props(scene: Scene, script_id: str) -> list[dict[str, Any]]:
    layers: list[dict[str, Any]] = []
    for layer in scene.visual_layers:
        data = layer.model_dump()
        image_url = data.get("image_url") or ""
        data["image_path"] = _scene_image_path(script_id, scene.id, image_url) if image_url else None
        layers.append(data)
    return layers
```

In `_scene_to_input_props`, add:

```python
        "visual_treatment": scene.visual_treatment,
        "visual_layers": _visual_layers_to_input_props(scene, script_id) if scene.visual_layers else None,
```

In `render_full_video`, add to top-level props:

```python
        "visual_canvas": content.visual_canvas.model_dump(),
```

Add a log before writing props:

```python
    logger.info(
        "[VISUAL_CANVAS] render props script=%s color=%s",
        script_id,
        content.visual_canvas.background_color,
    )
```

- [ ] **Step 4: Add Remotion static canvas component**

Create `remotion/src/scenes/StaticCanvas.tsx`:

```tsx
import React from "react";
import type { VisualCanvas } from "../types";

interface Props {
  canvas?: VisualCanvas | null;
}

export const StaticCanvas: React.FC<Props> = ({ canvas }) => {
  const backgroundColor = canvas?.background_color ?? "#F6C54A";
  return (
    <div
      style={{
        position: "absolute",
        inset: 0,
        backgroundColor,
      }}
    />
  );
};
```

- [ ] **Step 5: Add treatment renderer**

Create `remotion/src/scenes/TreatmentRenderer.tsx`:

```tsx
import React from "react";
import { Img, interpolate, spring, useCurrentFrame, useVideoConfig } from "remotion";
import type { SceneInput, VisualLayer } from "../types";
import { StaticImageScene } from "./StaticImageScene";
import { MultiFrameScene } from "./MultiFrameScene";
import { VideoScene } from "./VideoScene";

interface Props {
  scene: SceneInput;
  fallbackVisualLayer: React.ReactNode;
}

const slotStyle = (placement?: string): React.CSSProperties => {
  const base: React.CSSProperties = {
    position: "absolute",
    width: "30%",
    aspectRatio: "4 / 3",
    border: "6px solid #171717",
    borderRadius: 8,
    overflow: "hidden",
    boxShadow: "0 16px 36px rgba(0,0,0,0.22)",
    backgroundColor: "#fff",
  };
  switch (placement) {
    case "left":
      return { ...base, left: "8%", top: "34%" };
    case "right":
      return { ...base, right: "8%", top: "34%" };
    case "top-left":
      return { ...base, left: "14%", top: "18%" };
    case "top-right":
      return { ...base, right: "14%", top: "18%" };
    case "bottom-left":
      return { ...base, left: "14%", bottom: "18%" };
    case "bottom-right":
      return { ...base, right: "14%", bottom: "18%" };
    case "center":
    default:
      return { ...base, left: "35%", top: "32%" };
  }
};

const PanelLayer: React.FC<{ layer: VisualLayer }> = ({ layer }) => {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();
  const enterFrame = Math.round((layer.enter_at_seconds ?? 0) * fps);
  const age = frame - enterFrame;
  if (age < 0 || !layer.image_path) return null;
  const opacity = interpolate(age, [0, 6], [0, 1], { extrapolateLeft: "clamp", extrapolateRight: "clamp" });
  const pop = layer.animation === "pop_in"
    ? spring({ frame: Math.max(0, age), fps, config: { damping: 12, mass: 0.6 }, from: 0.78, to: 1 })
    : 1;
  return (
    <div style={{ ...slotStyle(layer.placement), opacity, transform: `scale(${pop})` }}>
      <Img src={layer.image_path} style={{ width: "100%", height: "100%", objectFit: "cover" }} />
    </div>
  );
};

const PopupSequence: React.FC<{ layers: VisualLayer[] }> = ({ layers }) => (
  <div style={{ position: "absolute", inset: 0 }}>
    {layers.map((layer) => <PanelLayer key={layer.id} layer={layer} />)}
  </div>
);

const Flipflop: React.FC<{ layers: VisualLayer[] }> = ({ layers }) => {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();
  const valid = layers.filter((layer) => layer.image_path);
  if (valid.length === 0) return null;
  const index = valid.length === 1 ? 0 : Math.floor(frame / Math.max(1, Math.round(fps * 0.5))) % 2;
  return <PanelLayer layer={{ ...valid[index], placement: valid[index].placement ?? "center", enter_at_seconds: 0 }} />;
};

export const TreatmentRenderer: React.FC<Props> = ({ scene, fallbackVisualLayer }) => {
  const treatment = scene.visual_treatment ?? "full_frame";
  const layers = scene.visual_layers ?? [];
  if (treatment === "popup_sequence" && layers.length > 0) {
    return <PopupSequence layers={layers} />;
  }
  if (treatment === "flipflop" && layers.length > 0) {
    return <Flipflop layers={layers} />;
  }
  return <>{fallbackVisualLayer}</>;
};
```

- [ ] **Step 6: Wire Remotion scene rendering**

In `remotion/src/FullVideo.tsx`, pass `visual_canvas` to `SceneRenderer`.

In `remotion/src/scenes/SceneRenderer.tsx`:

- Import `StaticCanvas` and `TreatmentRenderer`.
- Add `visualCanvas?: VisualCanvas | null` to props.
- Build the existing visual dispatch as `fallbackVisualLayer`.
- Replace the non-title/non-aha visual layer with:

```tsx
visualLayer = (
  <>
    <StaticCanvas canvas={visualCanvas} />
    <TreatmentRenderer scene={scene} fallbackVisualLayer={fallbackVisualLayer} />
  </>
);
```

Keep title cards and `aha_subtitle` on their existing paths.

- [ ] **Step 7: Run backend props tests and frontend build**

Run:

```bash
uv run --project backend pytest backend/tests/pipeline/test_remotion_render.py -v
cd frontend && npm run build
```

Expected: pytest PASS and frontend build PASS.

- [ ] **Step 8: Commit**

```bash
git add backend/pipeline/remotion_render.py remotion/src frontend/src/types/script.ts backend/tests/pipeline/test_remotion_render.py
git commit -m "Render static canvas visual treatments"
```

## Task 6: Frontend API And UI Controls

**Files:**
- Modify: `frontend/src/api.ts`
- Create: `frontend/src/components/timeline/VisualCanvasControls.tsx`
- Create: `frontend/src/components/timeline/VisualTreatmentReviewPanel.tsx`
- Modify: `frontend/src/components/timeline/MediaSourcesTab.tsx`
- Modify: `frontend/src/components/timeline/TimelinePage.tsx`

- [ ] **Step 1: Add API client types**

In `frontend/src/api.ts`, add:

```ts
import type { ScriptContent, VisualLayer, VisualTreatment } from "./types/script";
```

Add:

```ts
export interface VisualTreatmentAssignment {
  scene_id: string;
  visual_treatment: VisualTreatment;
  reasoning: string;
  visual_layers: VisualLayer[];
}

export interface VisualTreatmentStatus {
  status: string;
  progress: number;
  error: string | null;
  assignments?: VisualTreatmentAssignment[];
}

export async function getVisualCanvasPalette() {
  return api.get<{ colors: string[] }>("/api/visual-treatments/palette");
}

export async function updateVisualCanvas(scriptId: string, backgroundColor: string) {
  return api.put<{ script: ScriptContent; palette: string[] }>(
    `/api/visual-treatments/${scriptId}/canvas`,
    { background_color: backgroundColor },
  );
}

export async function analyzeVisualTreatments(scriptId: string) {
  return api.post<{ job_id: string }>(`/api/visual-treatments/${scriptId}/analyze`);
}

export async function getVisualTreatmentStatus(jobId: string) {
  return api.get<VisualTreatmentStatus>(`/api/visual-treatments/analyze/status/${jobId}`);
}

export async function applyVisualTreatmentAssignments(scriptId: string, assignments: VisualTreatmentAssignment[]) {
  return api.post<{ ok: boolean; script: ScriptContent }>(
    `/api/visual-treatments/${scriptId}/apply`,
    { assignments },
  );
}

export async function updateSceneVisualTreatment(scriptId: string, sceneId: string, visualTreatment: VisualTreatment) {
  return api.put<{ ok: boolean; script: ScriptContent }>(
    `/api/visual-treatments/${scriptId}/scene`,
    { scene_id: sceneId, visual_treatment: visualTreatment },
  );
}
```

- [ ] **Step 2: Create canvas controls component**

Create `frontend/src/components/timeline/VisualCanvasControls.tsx`:

```tsx
import { useEffect, useState } from "react";

interface Props {
  color: string;
  palette: string[];
  saving?: boolean;
  onSelect: (color: string) => Promise<void> | void;
}

function normalizeHexInput(value: string): string {
  const text = value.trim().toUpperCase();
  return text.startsWith("#") ? text : `#${text}`;
}

function isValidHex(value: string): boolean {
  return /^#[0-9A-F]{6}$/.test(normalizeHexInput(value));
}

export default function VisualCanvasControls({ color, palette, saving, onSelect }: Props) {
  const [draft, setDraft] = useState(color);
  const normalized = normalizeHexInput(draft);
  const valid = isValidHex(draft);

  useEffect(() => {
    setDraft(color);
  }, [color]);

  return (
    <section className="border border-neutral-800 bg-neutral-900 rounded-lg p-4 space-y-3">
      <div className="flex items-start justify-between gap-4">
        <div>
          <h3 className="text-sm font-semibold text-neutral-200">Static Canvas</h3>
          <p className="text-xs text-neutral-500 mt-1 max-w-xl">
            The canvas color sits behind every scene. Full-frame visuals cover it completely; popup and flipflop treatments let it show through.
          </p>
        </div>
        <div className="w-10 h-10 rounded-md border border-neutral-700 shrink-0" style={{ backgroundColor: valid ? normalized : color }} />
      </div>
      <div className="flex items-center gap-2">
        <input
          value={draft}
          onChange={(event) => setDraft(event.target.value)}
          className="w-32 bg-neutral-950 border border-neutral-700 rounded px-2 py-1.5 text-sm text-neutral-100"
          placeholder="#F6C54A"
        />
        <button
          onClick={() => onSelect(normalized)}
          disabled={!valid || saving}
          className="px-3 py-1.5 text-sm bg-violet-600 hover:bg-violet-500 disabled:hover:bg-violet-600 disabled:opacity-50 rounded-md transition-colors text-white"
        >
          {saving ? "Saving..." : "Select"}
        </button>
        {!valid && <span className="text-xs text-amber-300">Enter a valid 6-digit hex color.</span>}
      </div>
      <div className="flex flex-wrap gap-2">
        {palette.map((swatch) => (
          <button
            key={swatch}
            onClick={() => onSelect(swatch)}
            className="w-7 h-7 rounded-md border border-neutral-700 hover:border-neutral-300 transition-colors"
            style={{ backgroundColor: swatch }}
            title={`Select ${swatch}`}
            aria-label={`Select canvas color ${swatch}`}
          />
        ))}
      </div>
    </section>
  );
}
```

- [ ] **Step 3: Create visual treatment review panel**

Create `frontend/src/components/timeline/VisualTreatmentReviewPanel.tsx`:

```tsx
import { useState } from "react";
import type { VisualTreatmentAssignment } from "../../api";
import type { Scene, VisualTreatment } from "../../types/script";

const TREATMENT_LABELS: Record<VisualTreatment, { label: string; blurb: string }> = {
  full_frame: {
    label: "Full frame",
    blurb: "A normal scene image or video fills the whole frame and covers the canvas.",
  },
  popup_sequence: {
    label: "Popup sequence",
    blurb: "Two to four small illustrated panels appear on narration beats, usually left to right.",
  },
  flipflop: {
    label: "Flipflop",
    blurb: "Two complementary visuals alternate every half second for a simple animated feel.",
  },
};

interface Props {
  assignments: VisualTreatmentAssignment[];
  scenes: Record<string, Scene>;
  onApply: (assignments: VisualTreatmentAssignment[]) => Promise<void>;
  onReanalyze: () => void;
  canAnalyze: boolean;
  analyzeBlockedReason: string;
}

export default function VisualTreatmentReviewPanel({
  assignments,
  scenes,
  onApply,
  onReanalyze,
  canAnalyze,
  analyzeBlockedReason,
}: Props) {
  const [draft, setDraft] = useState(assignments);
  const [saving, setSaving] = useState(false);

  const updateTreatment = (sceneId: string, visualTreatment: VisualTreatment) => {
    setDraft((prev) =>
      prev.map((assignment) =>
        assignment.scene_id === sceneId
          ? { ...assignment, visual_treatment: visualTreatment, visual_layers: visualTreatment === "full_frame" ? [] : assignment.visual_layers }
          : assignment,
      ),
    );
  };

  const save = async () => {
    setSaving(true);
    await onApply(draft);
    setSaving(false);
  };

  return (
    <section className="border border-neutral-800 bg-neutral-900 rounded-lg overflow-hidden">
      <div className="px-4 py-3 border-b border-neutral-800 flex items-center justify-between gap-3">
        <div>
          <h3 className="text-sm font-semibold text-neutral-200">Visual Treatment</h3>
          <p className="text-xs text-neutral-500 mt-1">
            Visual treatment controls how a scene is staged. Media source chooses where assets come from; treatment chooses how they appear on the canvas.
          </p>
        </div>
        <div className="flex items-center gap-2">
          <button
            onClick={onReanalyze}
            disabled={!canAnalyze}
            title={!canAnalyze ? analyzeBlockedReason : undefined}
            className="px-3 py-1.5 text-xs bg-neutral-800 hover:bg-neutral-700 disabled:hover:bg-neutral-800 disabled:opacity-50 rounded-md transition-colors text-neutral-300"
          >
            Re-analyze
          </button>
          <button
            onClick={save}
            disabled={saving}
            className="px-3 py-1.5 text-xs bg-violet-600 hover:bg-violet-500 disabled:opacity-50 rounded-md transition-colors text-white"
          >
            {saving ? "Saving..." : "Apply Treatments"}
          </button>
        </div>
      </div>
      {!canAnalyze && (
        <div className="px-4 py-2 text-xs text-amber-300 bg-amber-500/10 border-b border-amber-500/20">
          {analyzeBlockedReason}
        </div>
      )}
      <div className="divide-y divide-neutral-800 max-h-[34rem] overflow-y-auto">
        {draft.map((assignment, index) => {
          const scene = scenes[assignment.scene_id];
          return (
            <div key={assignment.scene_id} className="px-4 py-3 grid grid-cols-[2rem_13rem_1fr] gap-3">
              <span className="text-sm text-neutral-500 text-right pt-1">{index + 1}</span>
              <select
                value={assignment.visual_treatment}
                onChange={(event) => updateTreatment(assignment.scene_id, event.target.value as VisualTreatment)}
                className="h-8 bg-neutral-800 border border-neutral-700 rounded px-2 text-xs text-neutral-200"
              >
                <option value="full_frame">Full frame</option>
                <option value="popup_sequence">Popup sequence</option>
                <option value="flipflop">Flipflop</option>
              </select>
              <div className="min-w-0">
                <p className="text-sm text-neutral-200 truncate">{scene?.narration || "No narration."}</p>
                <p className="text-xs text-neutral-500 mt-1">
                  {TREATMENT_LABELS[assignment.visual_treatment].blurb}
                </p>
                {assignment.reasoning && (
                  <p className="text-xs text-neutral-400 mt-1">Reason: {assignment.reasoning}</p>
                )}
              </div>
            </div>
          );
        })}
      </div>
    </section>
  );
}
```

- [ ] **Step 4: Wire MediaSourcesTab**

Modify `frontend/src/components/timeline/MediaSourcesTab.tsx` props to include:

```ts
canvasPalette: string[];
visualTreatmentAssignments: VisualTreatmentAssignment[] | null;
visualTreatmentAnalyzing: boolean;
onSelectCanvasColor: (color: string) => Promise<void> | void;
onAnalyzeVisualTreatments: () => void;
onApplyVisualTreatments: (assignments: VisualTreatmentAssignment[]) => Promise<void>;
```

Render `VisualCanvasControls` at the top of the main tab, before media review content:

```tsx
<VisualCanvasControls
  color={content.visual_canvas?.background_color ?? "#F6C54A"}
  palette={canvasPalette}
  onSelect={onSelectCanvasColor}
/>
```

Render `VisualTreatmentReviewPanel` when assignments exist:

```tsx
{visualTreatmentAssignments && (
  <VisualTreatmentReviewPanel
    assignments={visualTreatmentAssignments}
    scenes={buildScenesMap(content)}
    canAnalyze={canAnalyzeMedia}
    analyzeBlockedReason={analyzeBlockedReason || "Generate voiceover first so treatments can sync to words."}
    onReanalyze={onAnalyzeVisualTreatments}
    onApply={onApplyVisualTreatments}
  />
)}
```

In the empty state, add a second button:

```tsx
<button
  onClick={onAnalyzeVisualTreatments}
  disabled={!canAnalyzeMedia}
  title={!canAnalyzeMedia ? analyzeBlockedReason : undefined}
  className="px-5 py-2 text-sm bg-sky-600 hover:bg-sky-500 disabled:hover:bg-sky-600 disabled:opacity-50 rounded-lg transition-colors text-white font-medium"
>
  Analyze Visual Treatments
</button>
```

- [ ] **Step 5: Wire TimelinePage state and polling**

In `frontend/src/components/timeline/TimelinePage.tsx`, import the API helpers from `frontend/src/api.ts`. Add state near media analysis state:

```ts
const [canvasPalette, setCanvasPalette] = useState<string[]>(["#F6C54A"]);
const [visualTreatmentAssignments, setVisualTreatmentAssignments] = useState<VisualTreatmentAssignment[] | null>(null);
const [visualTreatmentAnalyzing, setVisualTreatmentAnalyzing] = useState(false);
```

Load palette when the page has a script:

```ts
useEffect(() => {
  if (!scriptId) return;
  getVisualCanvasPalette().then((res) => {
    if (res.ok) setCanvasPalette(res.data.colors);
  });
}, [scriptId]);
```

Add handlers:

```ts
const handleSelectCanvasColor = async (color: string) => {
  if (!scriptId) return;
  const res = await updateVisualCanvas(scriptId, color);
  if (res.ok) {
    state.setContent(res.data.script);
    setCanvasPalette(res.data.palette);
    showToast("Canvas color updated");
  } else {
    showToast("Could not update canvas color");
  }
};

const handleAnalyzeVisualTreatments = async () => {
  if (!scriptId) return;
  setVisualTreatmentAnalyzing(true);
  const start = await analyzeVisualTreatments(scriptId);
  if (!start.ok) {
    setVisualTreatmentAnalyzing(false);
    showToast((start.data as { detail?: string }).detail || "Could not analyze visual treatments");
    return;
  }
  const jobId = start.data.job_id;
  const interval = window.setInterval(async () => {
    const status = await getVisualTreatmentStatus(jobId);
    if (!status.ok) return;
    if (status.data.status === "completed") {
      window.clearInterval(interval);
      setVisualTreatmentAnalyzing(false);
      setVisualTreatmentAssignments(status.data.assignments ?? []);
    } else if (status.data.status === "failed") {
      window.clearInterval(interval);
      setVisualTreatmentAnalyzing(false);
      showToast(status.data.error || "Visual treatment analysis failed");
    }
  }, 1200);
};

const handleApplyVisualTreatments = async (assignments: VisualTreatmentAssignment[]) => {
  if (!scriptId) return;
  const res = await applyVisualTreatmentAssignments(scriptId, assignments);
  if (res.ok) {
    state.setContent(res.data.script);
    setVisualTreatmentAssignments(assignments);
    showToast("Visual treatments applied");
  } else {
    showToast("Could not apply visual treatments");
  }
};
```

Pass these props to `MediaSourcesTab`.

- [ ] **Step 6: Run frontend build**

Run:

```bash
cd frontend && npm run build
```

Expected: PASS.

- [ ] **Step 7: Commit**

```bash
git add frontend/src/api.ts frontend/src/components/timeline/VisualCanvasControls.tsx frontend/src/components/timeline/VisualTreatmentReviewPanel.tsx frontend/src/components/timeline/MediaSourcesTab.tsx frontend/src/components/timeline/TimelinePage.tsx frontend/src/types/script.ts
git commit -m "Add visual treatment controls"
```

## Task 7: End-To-End Verification And Logging Checks

**Files:**
- Verify: `backend/pipeline/visual_treatments.py`
- Verify: `backend/pipeline/image_gen.py`
- Verify: `backend/pipeline/render_phases.py`
- Verify: `backend/pipeline/remotion_render.py`
- Verify: `remotion/src/scenes/TreatmentRenderer.tsx`
- Verify: `frontend/src/components/timeline/VisualCanvasControls.tsx`
- Verify: `frontend/src/components/timeline/VisualTreatmentReviewPanel.tsx`

- [ ] **Step 1: Run backend test suite**

Run:

```bash
uv run --project backend pytest
```

Expected: PASS.

- [ ] **Step 2: Run frontend build**

Run:

```bash
cd frontend && npm run build
```

Expected: PASS.

- [ ] **Step 3: Start dev app**

Run:

```bash
npm run dev
```

Expected: backend on `:8420`, Vite on `:5173`, Electron starts.

- [ ] **Step 4: Manual QA in the app**

Use an existing project with generated voiceover or create a short test project.

Verify:

- Static Canvas section appears in the Media Sources tab.
- Hex input previews valid colors.
- Invalid hex shows "Enter a valid 6-digit hex color."
- Select saves the project canvas color.
- Previously selected colors appear as swatches after refresh.
- Analyze Visual Treatments is disabled before voiceover.
- Analyze Visual Treatments is enabled after voiceover.
- `popup_sequence` appears for list-like narration.
- `flipflop` appears for contrast/repetition narration.
- Scene treatment can be manually changed.
- Applying treatments persists after refresh.

- [ ] **Step 5: Dev dashboard log QA**

Open the dev dashboard and filter logs for:

```text
VISUAL_CANVAS
VISUAL_TREATMENT
PANEL_GEN
REMOTION_TREATMENT
```

Expected logs:

- Canvas color update with script id, old color, new color.
- Palette update with added color and size.
- Treatment analysis request with script id, scene count, and format id.
- Blocked analysis when missing timing.
- Per-scene treatment decisions.
- Panel generation start/cache/complete messages.
- Render prop canvas color.

- [ ] **Step 6: Render QA**

Render a short preview or first-segment video containing all three treatments.

Expected:

- `full_frame` scenes match current behavior.
- `popup_sequence` scenes show the static canvas behind panels.
- Panels pop in at word-aligned beats.
- `flipflop` alternates every 0.5 seconds.
- Missing panel assets fall back without crashing.
- The render is nonblank.

- [ ] **Step 7: Commit any fixes from QA**

If verification required fixes, stage the concrete files changed by the fix. For example, if the Remotion fallback guard needed adjustment:

```bash
git add remotion/src/scenes/TreatmentRenderer.tsx
git commit -m "Fix visual treatment verification issues"
```

If no fixes were required, do not create an empty commit.

## Task 8: Project Documentation And AGENTS Update Check

**Files:**
- Modify: `AGENTS.md` only if this implementation establishes a new durable project convention not already captured there.
- Modify: `docs/superpowers/specs/2026-05-23-static-canvas-visual-treatments-design.md` only if implementation intentionally differs from the approved spec.

- [ ] **Step 1: Check for new conventions**

Read the implemented behavior and decide whether a new durable convention was established. Add this to `AGENTS.md` only if true:

```markdown
- **Visual treatments render over a global static canvas**: Every scene has a video-level `visual_canvas.background_color` beneath it. `visual_treatment` controls staging (`full_frame`, `popup_sequence`, `flipflop`, etc.) and remains separate from `media_source`, which controls asset origin. Visual treatment analysis requires generated voiceover word timing before assignment.
```

- [ ] **Step 2: Run final verification**

Run:

```bash
uv run --project backend pytest
cd frontend && npm run build
```

Expected: both PASS.

- [ ] **Step 3: Commit documentation if changed**

If `AGENTS.md` or the spec changed:

```bash
git add AGENTS.md docs/superpowers/specs/2026-05-23-static-canvas-visual-treatments-design.md
git commit -m "Document visual treatment conventions"
```

If neither file changed, do not create an empty commit.

## Final Completion Loop

After implementation is complete:

- [ ] Run `git status --short` and confirm only intentional files changed.
- [ ] Run `uv run --project backend pytest`.
- [ ] Run `cd frontend && npm run build`.
- [ ] Stage relevant files.
- [ ] Commit with an imperative message.
- [ ] Push to `main`.
- [ ] Dispatch delegated review per `AGENTS.md`.
- [ ] Apply all FAIL/WARN review findings.
- [ ] Repeat review until LGTM.
- [ ] Summarize only after LGTM.

## Self-Review Notes

- Spec coverage: data model, canvas palette, UI blurbs, voiceover gate, analyzer, panel generation, Remotion rendering, dev-dashboard logging, testing, and future extensibility are covered.
- Scope control: Phase 1 implements only `full_frame`, `popup_sequence`, and `flipflop`.
- Type consistency: the plan uses `visual_canvas`, `visual_treatment`, `visual_layers`, `VisualLayer`, and `VisualTreatmentAssignment` consistently across backend, frontend, and Remotion.
