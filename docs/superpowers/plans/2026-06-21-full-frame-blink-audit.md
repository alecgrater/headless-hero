# Full-Frame Blink Audit Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a Test Lab `Blink Audit` tab that evaluates full-size Burger King scene images for in-place blink overlay eligibility, then renders reusable blink previews without using crop/re-composite.

**Architecture:** Add a backend audit service that loads the Burger King script, filters image-backed scenes, runs conservative full-image blink anchor detection, persists reports, and exposes API routes. Reuse the existing Remotion blink geometry by extracting a normal-image blink overlay component that can render inside `StaticImageScene`, so future production blink inherits Ken Burns/camera effects. Add a Test Lab frontend tab that displays still previews, blink previews, eligibility status, and rejection reasons.

**Tech Stack:** Python 3.12 with FastAPI, SQLModel, Pydantic, PIL/Pillow, `uv run --project backend pytest`; React 19, TypeScript, Vite/Vitest, lucide-react, Remotion 4.

---

## File Structure

- Create `backend/pipeline/full_frame_blink.py`: full-image candidate discovery, detection result models, deterministic 50% gate helper, report persistence, and report loading.
- Modify `backend/api/test_lab.py`: add `/api/test-lab/blink-audits` routes.
- Modify `backend/tests/test_full_frame_blink.py`: backend tests for discovery, eligibility, persistence, and deterministic gate.
- Modify `backend/tests/test_test_lab.py`: API route tests for Blink Audit.
- Create `remotion/src/scenes/BlinkOverlay.tsx`: reusable overlay functions/components moved from `TreatmentRenderer`.
- Modify `remotion/src/scenes/TreatmentRenderer.tsx`: import reusable blink geometry/component and keep legacy `visual_mode="blink"` behavior.
- Modify `remotion/src/scenes/StaticImageScene.tsx`: render full-image blink overlay when scene metadata includes a detected full-frame blink anchor.
- Modify `remotion/src/types.ts`: add optional full-frame blink metadata to `SceneInput`.
- Modify `frontend/src/remotion/TreatmentRenderer.test.ts`: update imports after extracting blink overlay.
- Modify `frontend/src/remotion/SceneRenderer.test.ts`: assert full-frame blink metadata does not block whole-scene camera effects.
- Modify `frontend/src/types/script.ts`: add full-frame blink metadata shape.
- Modify `frontend/src/types/testLab.ts`: add Blink Audit API types.
- Modify `frontend/src/api.ts`: add Blink Audit helpers.
- Create `frontend/src/components/test-lab/BlinkAuditLab.tsx`: Test Lab tab UI.
- Create `frontend/src/components/test-lab/BlinkAuditLab.test.tsx`: frontend tests for loading and rendering statuses.
- Modify `frontend/src/components/test-lab/TestLabPage.tsx`: add the `Blink Audit` tab.
- Modify `frontend/src/components/test-lab/TestLabPage.test.tsx`: assert the tab appears.
- Modify `frontend/src/components/docs/WorkflowDocSection.tsx`: mention Test Lab -> Blink Audit.
- Modify `frontend/src/components/docs/DocsPage.test.tsx`: assert the workflow docs mention Blink Audit.
- Modify `AGENTS.md`: update blink convention from Test Lab-only visual mode toward full-frame audit/enhancement.

## Task 1: Backend Detection And Report Models

**Files:**
- Create: `backend/pipeline/full_frame_blink.py`
- Test: `backend/tests/test_full_frame_blink.py`

- [ ] **Step 1: Write failing backend model and gate tests**

Add `backend/tests/test_full_frame_blink.py`:

```python
from pathlib import Path

from PIL import Image


def test_deterministic_blink_gate_is_stable_and_roughly_half():
    from pipeline.full_frame_blink import deterministic_blink_enabled

    first = deterministic_blink_enabled("script-1", "scene-1")
    assert deterministic_blink_enabled("script-1", "scene-1") is first

    enabled_count = sum(
        deterministic_blink_enabled("script-1", f"scene-{index}")
        for index in range(100)
    )
    assert 35 <= enabled_count <= 65


def test_detect_full_frame_blink_anchor_rejects_missing_file(tmp_path):
    from pipeline.full_frame_blink import detect_full_frame_blink_anchor

    result = detect_full_frame_blink_anchor(tmp_path / "missing.png")

    assert result.eligible is False
    assert result.status == "failed"
    assert result.reason == "image_missing"


def test_detect_full_frame_blink_anchor_accepts_existing_detector_anchor(monkeypatch, tmp_path):
    from pipeline import full_frame_blink
    from pipeline.full_frame_blink import detect_full_frame_blink_anchor

    image_path = tmp_path / "scene.png"
    Image.new("RGBA", (400, 300), (240, 210, 180, 255)).save(image_path)
    anchor = {
        "detected": True,
        "coordinate_space": "normalized_layer_frame",
        "skin_fill": "#F0D2B4",
        "eye_left": {"x": 0.45, "y": 0.4, "width": 0.03, "height": 0.02},
        "eye_right": {"x": 0.55, "y": 0.4, "width": 0.03, "height": 0.02},
        "mouth": {"x": 0.5, "y": 0.52},
        "brow_left": {"x": 0.45, "y": 0.35},
        "brow_right": {"x": 0.55, "y": 0.35},
    }
    monkeypatch.setattr(full_frame_blink, "_blink_overlay_anchor_metadata", lambda *_args, **_kwargs: anchor)

    result = detect_full_frame_blink_anchor(image_path)

    assert result.eligible is True
    assert result.status == "passed"
    assert result.anchor == anchor
    assert result.reason == ""
```

- [ ] **Step 2: Run tests to verify they fail**

Run:

```bash
uv run --project backend pytest backend/tests/test_full_frame_blink.py -q
```

Expected: FAIL because `pipeline.full_frame_blink` does not exist.

- [ ] **Step 3: Implement minimal detection models and gate helper**

Create `backend/pipeline/full_frame_blink.py`:

```python
"""Full-frame blink audit and eligibility helpers."""

from __future__ import annotations

import hashlib
from pathlib import Path
from typing import Literal

from PIL import Image
from pydantic import BaseModel, Field

from pipeline.image_gen import (
    BLINK_CUTOUT_REGISTRATION_VERSION,
    BlinkRegistrationError,
    _blink_overlay_anchor_metadata,
)


class FullFrameBlinkDetection(BaseModel):
    status: Literal["passed", "failed"]
    eligible: bool
    reason: str = ""
    anchor: dict[str, object] | None = None
    registration_algorithm_version: str = BLINK_CUTOUT_REGISTRATION_VERSION


class FullFrameBlinkCandidate(BaseModel):
    script_id: str
    scene_id: str
    segment_name: str
    scene_label: str
    visual_mode: str
    image_url: str
    image_path: str
    detection: FullFrameBlinkDetection
    blink_enabled: bool = False


class FullFrameBlinkAuditReport(BaseModel):
    id: str
    script_id: str
    title: str
    created_at: str
    candidates: list[FullFrameBlinkCandidate] = Field(default_factory=list)


def deterministic_blink_enabled(script_id: str, scene_id: str) -> bool:
    digest = hashlib.sha256(f"{script_id}:{scene_id}".encode("utf-8")).digest()
    return digest[0] < 128


def detect_full_frame_blink_anchor(image_path: Path) -> FullFrameBlinkDetection:
    if not image_path.exists() or not image_path.is_file():
        return FullFrameBlinkDetection(status="failed", eligible=False, reason="image_missing")
    try:
        with Image.open(image_path) as image:
            anchor = _blink_overlay_anchor_metadata(image.convert("RGBA"), require_detected=True)
    except OSError:
        return FullFrameBlinkDetection(status="failed", eligible=False, reason="image_unreadable")
    except BlinkRegistrationError as exc:
        return FullFrameBlinkDetection(status="failed", eligible=False, reason=_stable_detection_reason(str(exc)))
    if not _anchor_is_full_frame_eligible(anchor):
        return FullFrameBlinkDetection(status="failed", eligible=False, reason="anchor_not_full_frame_safe")
    return FullFrameBlinkDetection(status="passed", eligible=True, anchor=anchor)


def _anchor_is_full_frame_eligible(anchor: dict[str, object]) -> bool:
    required = ("eye_left", "eye_right", "mouth", "brow_left", "brow_right")
    if anchor.get("detected") is not True:
        return False
    for key in required:
        point = anchor.get(key)
        if not isinstance(point, dict):
            return False
        if not isinstance(point.get("x"), int | float) or not isinstance(point.get("y"), int | float):
            return False
    return isinstance(anchor.get("skin_fill"), str)


def _stable_detection_reason(message: str) -> str:
    text = message.casefold()
    if "facial landmarks" in text:
        return "face_landmarks_missing"
    if "no visible subject" in text:
        return "subject_missing"
    if "centered chest-up" in text:
        return "face_framing_unsafe"
    return "detector_rejected"
```

- [ ] **Step 4: Run tests to verify they pass**

Run:

```bash
uv run --project backend pytest backend/tests/test_full_frame_blink.py -q
```

Expected: PASS.

## Task 2: Backend Audit Discovery And Persistence

**Files:**
- Modify: `backend/pipeline/full_frame_blink.py`
- Modify: `backend/tests/test_full_frame_blink.py`

- [ ] **Step 1: Write failing audit discovery and persistence tests**

Append to `backend/tests/test_full_frame_blink.py`:

```python
from datetime import datetime, timezone

from sqlmodel import Session


def test_run_full_frame_blink_audit_discovers_media_backed_scene(monkeypatch, tmp_path):
    from models.script import Script, ScriptContent, Segment, Scene
    from pipeline import full_frame_blink
    from pipeline.full_frame_blink import run_full_frame_blink_audit

    image_dir = tmp_path / "projects" / "burger-script" / "images"
    image_dir.mkdir(parents=True)
    image_path = image_dir / "scene-1.png"
    Image.new("RGBA", (400, 300), (240, 210, 180, 255)).save(image_path)
    content = ScriptContent(
        title="Your Life At Every Level Of Working At Burger King",
        segments=[
            Segment(
                name="Level 1",
                scenes=[
                    Scene(id="title-1", narration="Title.", visual_prompt="", is_title_card=True),
                    Scene(id="scene-1", narration="He waits.", visual_prompt="A worker character.", visual_mode="full_frame", image_url="/static/projects/burger-script/images/scene-1.png"),
                    Scene(id="scene-2", narration="A stat.", visual_prompt="", visual_mode="stat_card"),
                ],
            )
        ],
    )
    script = Script(
        id="burger-script",
        brand_id="default",
        format_id="life-as-a",
        topic_title="Your Life At Every Level Of Working At Burger King",
        topic_description="",
        script_json=content.model_dump_json(),
        created_at=datetime.now(timezone.utc),
    )
    session.add(script)
    session.commit()
    monkeypatch.setattr(full_frame_blink, "DATA_DIR", tmp_path)
    monkeypatch.setattr(
        full_frame_blink,
        "detect_full_frame_blink_anchor",
        lambda _path: full_frame_blink.FullFrameBlinkDetection(status="passed", eligible=True, anchor={"detected": True, "skin_fill": "#F0D2B4"}),
    )

    report = run_full_frame_blink_audit(session=session, script_id="burger-script")

    assert report.script_id == "burger-script"
    assert [candidate.scene_id for candidate in report.candidates] == ["scene-1"]
    assert report.candidates[0].image_url == "/static/projects/burger-script/images/scene-1.png"
    assert report.candidates[0].blink_enabled in {True, False}


def test_full_frame_blink_audit_persists_report(monkeypatch, tmp_path):
    from pipeline import full_frame_blink
    from pipeline.full_frame_blink import FullFrameBlinkAuditReport, save_blink_audit_report, list_blink_audit_reports

    monkeypatch.setattr(full_frame_blink, "DATA_DIR", tmp_path)
    report = FullFrameBlinkAuditReport(
        id="audit-1",
        script_id="script-1",
        title="Title",
        created_at="2026-06-21T00:00:00+00:00",
        candidates=[],
    )

    save_blink_audit_report(report)

    reports = list_blink_audit_reports()
    assert [item.id for item in reports] == ["audit-1"]
```

- [ ] **Step 2: Run tests to verify they fail**

Run:

```bash
uv run --project backend pytest backend/tests/test_full_frame_blink.py -q
```

Expected: FAIL because audit functions do not exist.

- [ ] **Step 3: Implement audit discovery and persistence**

Update `backend/pipeline/full_frame_blink.py` with:

```python
import json
import uuid
from datetime import datetime, timezone

from config import DATA_DIR
from models.script import Script, ScriptContent
from sqlmodel import Session

BURGER_KING_BLINK_AUDIT_SCRIPT_ID = "9dacedc774514306ae1acb85215449e1"
MEDIA_BACKED_BLINK_MODES = {"full_frame", "multi_frame", "continuous", "captions"}


def run_full_frame_blink_audit(
    *,
    session: Session,
    script_id: str = BURGER_KING_BLINK_AUDIT_SCRIPT_ID,
) -> FullFrameBlinkAuditReport:
    script = session.get(Script, script_id)
    if script is None:
        raise FileNotFoundError(f"Script not found: {script_id}")
    content = ScriptContent.model_validate_json(script.script_json)
    report = FullFrameBlinkAuditReport(
        id=f"blink-audit-{uuid.uuid4().hex[:12]}",
        script_id=script.id,
        title=script.topic_title or content.title,
        created_at=datetime.now(timezone.utc).isoformat(),
        candidates=[],
    )
    for segment in content.segments:
        for scene in segment.scenes:
            if scene.is_title_card or scene.visual_mode not in MEDIA_BACKED_BLINK_MODES:
                continue
            image_url = _scene_image_url(script.id, scene.id, scene.image_url)
            image_path = _image_path_from_url(image_url)
            if image_path is None:
                detection = FullFrameBlinkDetection(status="failed", eligible=False, reason="image_missing")
                resolved_path = ""
            else:
                detection = detect_full_frame_blink_anchor(image_path)
                resolved_path = str(image_path)
            report.candidates.append(
                FullFrameBlinkCandidate(
                    script_id=script.id,
                    scene_id=scene.id,
                    segment_name=segment.name,
                    scene_label=scene.narration[:80],
                    visual_mode=scene.visual_mode,
                    image_url=image_url,
                    image_path=resolved_path,
                    detection=detection,
                    blink_enabled=detection.eligible and deterministic_blink_enabled(script.id, scene.id),
                )
            )
    save_blink_audit_report(report)
    return report


def list_blink_audit_reports() -> list[FullFrameBlinkAuditReport]:
    reports = []
    for path in sorted(_audit_dir().glob("*.json"), key=lambda item: item.stat().st_mtime, reverse=True):
        reports.append(FullFrameBlinkAuditReport.model_validate_json(path.read_text(encoding="utf-8")))
    return reports


def load_blink_audit_report(report_id: str) -> FullFrameBlinkAuditReport:
    path = _audit_report_path(report_id)
    if not path.exists():
        raise FileNotFoundError(report_id)
    return FullFrameBlinkAuditReport.model_validate_json(path.read_text(encoding="utf-8"))


def save_blink_audit_report(report: FullFrameBlinkAuditReport) -> None:
    path = _audit_report_path(report.id)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(report.model_dump_json(indent=2), encoding="utf-8")


def _audit_dir() -> Path:
    return DATA_DIR / "test-lab" / "full-frame-blink-audits"


def _audit_report_path(report_id: str) -> Path:
    if not report_id or "/" in report_id or "\\" in report_id:
        raise ValueError("Invalid blink audit report id.")
    return _audit_dir() / f"{report_id}.json"


def _scene_image_url(script_id: str, scene_id: str, image_url: str) -> str:
    return image_url or f"/static/projects/{script_id}/images/{scene_id}.png"


def _image_path_from_url(image_url: str) -> Path | None:
    prefix = "/static/projects/"
    if not image_url.startswith(prefix):
        return None
    relative = image_url.removeprefix(prefix)
    path = (DATA_DIR / "projects" / relative).resolve()
    projects_dir = (DATA_DIR / "projects").resolve()
    if not path.is_relative_to(projects_dir):
        return None
    return path
```

- [ ] **Step 4: Run tests to verify they pass**

Run:

```bash
uv run --project backend pytest backend/tests/test_full_frame_blink.py -q
```

Expected: PASS.

## Task 3: Test Lab API Routes

**Files:**
- Modify: `backend/api/test_lab.py`
- Modify: `backend/tests/test_test_lab.py`

- [ ] **Step 1: Write failing API tests**

Append to `backend/tests/test_test_lab.py`:

```python
def test_blink_audit_endpoint_runs_report(monkeypatch, tmp_path):
    engine, app = _setup_app(monkeypatch, tmp_path)
    _seed_script(engine, "burger-script", is_test_lab=False, title="Your Life At Every Level Of Working At Burger King")

    import api.test_lab as test_lab_api
    import pipeline.full_frame_blink as full_frame_blink

    monkeypatch.setattr(full_frame_blink, "DATA_DIR", tmp_path)
    monkeypatch.setattr(test_lab_api, "BURGER_KING_BLINK_AUDIT_SCRIPT_ID", "burger-script")

    client = TestClient(app)

    response = client.post("/api/test-lab/blink-audits", json={})

    assert response.status_code == 200
    assert response.json()["script_id"] == "burger-script"


def test_blink_audit_history_endpoint_lists_reports(monkeypatch, tmp_path):
    _engine, app = _setup_app(monkeypatch, tmp_path)

    import pipeline.full_frame_blink as full_frame_blink
    from pipeline.full_frame_blink import FullFrameBlinkAuditReport, save_blink_audit_report

    monkeypatch.setattr(full_frame_blink, "DATA_DIR", tmp_path)
    save_blink_audit_report(
        FullFrameBlinkAuditReport(
            id="audit-1",
            script_id="script-1",
            title="Title",
            created_at="2026-06-21T00:00:00+00:00",
            candidates=[],
        )
    )

    client = TestClient(app)
    response = client.get("/api/test-lab/blink-audits")

    assert response.status_code == 200
    assert response.json()["reports"][0]["id"] == "audit-1"
```

- [ ] **Step 2: Run tests to verify they fail**

Run:

```bash
uv run --project backend pytest backend/tests/test_test_lab.py::test_blink_audit_endpoint_runs_report backend/tests/test_test_lab.py::test_blink_audit_history_endpoint_lists_reports -q
```

Expected: FAIL because routes are missing.

- [ ] **Step 3: Add API request model and routes**

Modify `backend/api/test_lab.py` imports:

```python
from pipeline.full_frame_blink import (
    BURGER_KING_BLINK_AUDIT_SCRIPT_ID,
    list_blink_audit_reports,
    load_blink_audit_report,
    run_full_frame_blink_audit,
)
```

Add request model near other Test Lab models:

```python
class BlinkAuditRequest(BaseModel):
    script_id: str = BURGER_KING_BLINK_AUDIT_SCRIPT_ID
```

Add routes near existing blink routes:

```python
@router.post("/blink-audits")
def run_blink_audit(request: BlinkAuditRequest, session: Session = Depends(get_session)):
    try:
        return run_full_frame_blink_audit(session=session, script_id=request.script_id).model_dump(mode="json")
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail="Blink audit source script not found") from None


@router.get("/blink-audits")
def get_blink_audits():
    return {"reports": [report.model_dump(mode="json") for report in list_blink_audit_reports()]}


@router.get("/blink-audits/{report_id}")
def get_blink_audit(report_id: str):
    try:
        return load_blink_audit_report(report_id).model_dump(mode="json")
    except (FileNotFoundError, ValueError):
        raise HTTPException(status_code=404, detail="Blink Audit report not found") from None
```

- [ ] **Step 4: Run tests to verify they pass**

Run:

```bash
uv run --project backend pytest backend/tests/test_test_lab.py::test_blink_audit_endpoint_runs_report backend/tests/test_test_lab.py::test_blink_audit_history_endpoint_lists_reports -q
```

Expected: PASS.

## Task 4: Reusable Remotion Blink Overlay

**Files:**
- Create: `remotion/src/scenes/BlinkOverlay.tsx`
- Modify: `remotion/src/scenes/TreatmentRenderer.tsx`
- Modify: `frontend/src/remotion/TreatmentRenderer.test.ts`

- [ ] **Step 1: Move blink overlay exports without behavior changes**

Create `remotion/src/scenes/BlinkOverlay.tsx` by moving these exports and their helper dependencies from `TreatmentRenderer.tsx`:

```typescript
export const BLINK_OVERLAY_SVG_PROPS = {
  viewBox: "0 0 100 100",
  preserveAspectRatio: "none",
} as const;

export const blinkOverlayVisible = (frame: number, fps: number): boolean => {
  const intervalFrames = Math.max(1, Math.round(fps * 0.5));
  return Math.floor(Math.max(0, frame) / intervalFrames) % 2 === 1;
};

export const blinkMicroOverlay = (action?: string | null): BlinkOverlay | null => {
  switch (action) {
    case "blink":
      return { kind: "eyes", state: "closed" };
    default:
      return null;
  }
};

export const blinkOverlayAnchor = (layer: VisualLayer): BlinkResolvedOverlayAnchor | null => {
  const anchor = layer.visual_source_metadata?.blink_overlay_anchor;
  return resolveBlinkOverlayAnchor(anchor);
};

export const resolveBlinkOverlayAnchor = (anchor: unknown): BlinkResolvedOverlayAnchor | null => {
  if (!isBlinkOverlayAnchor(anchor) || anchor.detected !== true) {
    return null;
  }
  if (
    !validAnchorPoint(anchor.eye_left)
    || !validAnchorPoint(anchor.eye_right)
    || !validAnchorPoint(anchor.mouth)
    || !validAnchorPoint(anchor.brow_left)
    || !validAnchorPoint(anchor.brow_right)
  ) {
    return null;
  }
  return {
    eye_left: anchor.eye_left,
    eye_right: anchor.eye_right,
    mouth: anchor.mouth,
    brow_left: anchor.brow_left,
    brow_right: anchor.brow_right,
    skin_fill: typeof anchor.skin_fill === "string" ? anchor.skin_fill : undefined,
  };
};
```

Also move `blinkBlinkEyeOverlayGeometry` and `BlinkMicroExpressionOverlay`, exporting `BlinkMicroExpressionOverlay`.

Update `TreatmentRenderer.tsx` to import:

```typescript
import {
  BlinkMicroExpressionOverlay,
  blinkBlinkEyeOverlayGeometry,
  blinkMicroOverlay,
  blinkOverlayAnchor,
  blinkOverlayVisible,
} from "./BlinkOverlay";
```

Update `frontend/src/remotion/TreatmentRenderer.test.ts` imports from `@remotion-src/scenes/BlinkOverlay` for `blinkBlinkEyeOverlayGeometry`.

- [ ] **Step 2: Run existing Remotion tests**

Run:

```bash
npm run test:frontend -- TreatmentRenderer.test.ts
```

Expected: PASS.

## Task 5: Full-Image Overlay Render Path

**Files:**
- Modify: `remotion/src/types.ts`
- Modify: `remotion/src/scenes/StaticImageScene.tsx`
- Modify: `frontend/src/remotion/SceneRenderer.test.ts`

- [ ] **Step 1: Write failing Remotion test for camera-compatible full-frame blink metadata**

Modify `frontend/src/remotion/SceneRenderer.test.ts`:

```typescript
it("keeps camera effects available for full-frame scenes with blink metadata", () => {
  expect(canApplyWholeSceneFx({ visual_mode: "full_frame" })).toBe(true);
});
```

This test should already pass for `canApplyWholeSceneFx`; the implementation step adds the rendering surface without changing the camera policy.

- [ ] **Step 2: Add full-frame blink metadata type**

Modify `remotion/src/types.ts`:

```typescript
export interface FullFrameBlinkOverlay {
  action: "blink";
  anchor: BlinkOverlayAnchor;
  enabled: boolean;
}
```

Add to `SceneInput`:

```typescript
full_frame_blink?: FullFrameBlinkOverlay | null;
```

- [ ] **Step 3: Render overlay inside `StaticImageScene`**

Modify `remotion/src/scenes/StaticImageScene.tsx`:

```typescript
import { useCurrentFrame, useVideoConfig, Img } from "remotion";
import {
  BlinkMicroExpressionOverlay,
  blinkMicroOverlay,
  blinkOverlayVisible,
  resolveBlinkOverlayAnchor,
} from "./BlinkOverlay";
```

Inside `StaticImageScene`:

```typescript
const frame = useCurrentFrame();
const { fps } = useVideoConfig();
const blink = scene.full_frame_blink?.enabled ? scene.full_frame_blink : null;
const blinkOverlay = blinkMicroOverlay(blink?.action);
const blinkAnchor = blink ? resolveBlinkOverlayAnchor(blink.anchor) : null;
const blinkVisible = blinkOverlay ? blinkOverlayVisible(frame, fps) : false;
```

Render image and overlay inside the same full-size relative container:

```tsx
<div style={{ width: "100%", height: "100%", backgroundColor: "#000", position: "relative", overflow: "hidden" }}>
  <Img src={scene.image_path} style={{ width: "100%", height: "100%", objectFit: "cover", display: "block" }} />
  {blinkOverlay && blinkAnchor ? (
    <BlinkMicroExpressionOverlay
      anchor={blinkAnchor}
      overlay={blinkOverlay}
      visible={blinkVisible}
    />
  ) : null}
</div>
```

- [ ] **Step 4: Run frontend tests**

Run:

```bash
npm run test:frontend -- SceneRenderer.test.ts TreatmentRenderer.test.ts
```

Expected: PASS.

## Task 6: Pass Audit Metadata To Remotion Previews

**Files:**
- Modify: `backend/pipeline/full_frame_blink.py`
- Modify: `backend/pipeline/remotion_render.py`
- Modify: `backend/tests/pipeline/test_remotion_render.py`

- [ ] **Step 1: Write failing Remotion prop test**

Append to `backend/tests/pipeline/test_remotion_render.py`:

```python
def test_scene_input_props_include_full_frame_blink_metadata():
    scene = Scene(
        id="s1",
        narration="He blinks.",
        visual_prompt="Worker.",
        visual_mode="full_frame",
        visual_source_metadata={
            "full_frame_blink": {
                "enabled": True,
                "action": "blink",
                "anchor": {"detected": True, "skin_fill": "#F0D2B4"},
            }
        },
    )

    props = remotion_render._scene_to_input_props(scene, "script-1")

    assert props["full_frame_blink"]["enabled"] is True
    assert props["full_frame_blink"]["action"] == "blink"
```

- [ ] **Step 2: Run test to verify it fails**

Run:

```bash
uv run --project backend pytest backend/tests/pipeline/test_remotion_render.py::test_scene_input_props_include_full_frame_blink_metadata -q
```

Expected: FAIL because `_scene_to_input_props` does not emit `full_frame_blink`.

- [ ] **Step 3: Emit sanitized metadata from Remotion props**

Modify `backend/pipeline/remotion_render.py` inside `_scene_to_input_props`:

```python
full_frame_blink = None
raw_blink = metadata.get("full_frame_blink")
if isinstance(raw_blink, dict) and raw_blink.get("enabled") is True:
    full_frame_blink = {
        "enabled": True,
        "action": "blink" if raw_blink.get("action") == "blink" else "",
        "anchor": raw_blink.get("anchor") if isinstance(raw_blink.get("anchor"), dict) else None,
    }
```

Add to returned props:

```python
"full_frame_blink": full_frame_blink,
```

- [ ] **Step 4: Run test to verify it passes**

Run:

```bash
uv run --project backend pytest backend/tests/pipeline/test_remotion_render.py::test_scene_input_props_include_full_frame_blink_metadata -q
```

Expected: PASS.

## Task 7: Frontend API Types And Blink Audit Tab

**Files:**
- Modify: `frontend/src/types/testLab.ts`
- Modify: `frontend/src/api.ts`
- Create: `frontend/src/components/test-lab/BlinkAuditLab.tsx`
- Create: `frontend/src/components/test-lab/BlinkAuditLab.test.tsx`
- Modify: `frontend/src/components/test-lab/TestLabPage.tsx`
- Modify: `frontend/src/components/test-lab/TestLabPage.test.tsx`

- [ ] **Step 1: Write failing tab test**

Modify `frontend/src/components/test-lab/TestLabPage.test.tsx`:

```typescript
it("shows the Blink Audit tab", async () => {
  render(<TestLabPage />);
  expect(await screen.findByRole("button", { name: "Blink Audit" })).toBeInTheDocument();
});
```

- [ ] **Step 2: Write failing Blink Audit component test**

Create `frontend/src/components/test-lab/BlinkAuditLab.test.tsx`:

```typescript
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { vi } from "vitest";
import * as api from "../../api";
import BlinkAuditLab from "./BlinkAuditLab";

vi.mock("../../api", async () => {
  const actual = await vi.importActual<typeof import("../../api")>("../../api");
  return {
    ...actual,
    getBlinkAuditReports: vi.fn(),
    runBlinkAudit: vi.fn(),
    assetUrl: (url: string) => url,
  };
});

it("runs and displays a blink audit report", async () => {
  vi.mocked(api.getBlinkAuditReports).mockResolvedValue([]);
  vi.mocked(api.runBlinkAudit).mockResolvedValue({
    id: "audit-1",
    script_id: "burger-script",
    title: "Your Life At Every Level Of Working At Burger King",
    created_at: "2026-06-21T00:00:00+00:00",
    candidates: [
      {
        script_id: "burger-script",
        scene_id: "scene-1",
        segment_name: "Level 1",
        scene_label: "He waits.",
        visual_mode: "full_frame",
        image_url: "/static/projects/burger-script/images/scene-1.png",
        image_path: "/tmp/scene-1.png",
        blink_enabled: true,
        detection: { status: "passed", eligible: true, reason: "", anchor: { detected: true } },
      },
      {
        script_id: "burger-script",
        scene_id: "scene-2",
        segment_name: "Level 2",
        scene_label: "The room is empty.",
        visual_mode: "full_frame",
        image_url: "/static/projects/burger-script/images/scene-2.png",
        image_path: "/tmp/scene-2.png",
        blink_enabled: false,
        detection: { status: "failed", eligible: false, reason: "face_landmarks_missing", anchor: null },
      },
    ],
  });

  render(<BlinkAuditLab />);
  await userEvent.click(screen.getByRole("button", { name: /run blink audit/i }));

  expect(await screen.findByText("scene-1")).toBeInTheDocument();
  expect(screen.getByText("Eligible")).toBeInTheDocument();
  expect(screen.getByText("face_landmarks_missing")).toBeInTheDocument();
});
```

- [ ] **Step 3: Run tests to verify they fail**

Run:

```bash
npm run test:frontend -- TestLabPage.test.tsx BlinkAuditLab.test.tsx
```

Expected: FAIL because types/helpers/component/tab are missing.

- [ ] **Step 4: Add types and API helpers**

Modify `frontend/src/types/testLab.ts`:

```typescript
export interface FullFrameBlinkDetection {
  status: "passed" | "failed";
  eligible: boolean;
  reason: string;
  anchor?: Record<string, unknown> | null;
  registration_algorithm_version?: string;
}

export interface FullFrameBlinkCandidate {
  script_id: string;
  scene_id: string;
  segment_name: string;
  scene_label: string;
  visual_mode: VisualMode;
  image_url: string;
  image_path: string;
  detection: FullFrameBlinkDetection;
  blink_enabled: boolean;
}

export interface FullFrameBlinkAuditReport {
  id: string;
  script_id: string;
  title: string;
  created_at: string;
  candidates: FullFrameBlinkCandidate[];
}
```

Modify `frontend/src/api.ts`:

```typescript
export async function runBlinkAudit(scriptId?: string): Promise<FullFrameBlinkAuditReport | null> {
  const res = await api.post<FullFrameBlinkAuditReport>("/api/test-lab/blink-audits", scriptId ? { script_id: scriptId } : {});
  return res.ok ? res.data : null;
}

export async function getBlinkAuditReports(): Promise<FullFrameBlinkAuditReport[]> {
  const res = await api.get<{ reports: FullFrameBlinkAuditReport[] }>("/api/test-lab/blink-audits");
  return res.ok ? res.data.reports : [];
}
```

- [ ] **Step 5: Add `BlinkAuditLab` UI**

Create `frontend/src/components/test-lab/BlinkAuditLab.tsx`:

```tsx
import { AlertTriangle, CheckCircle2, Loader2, RefreshCw, ScanFace } from "lucide-react";
import { useEffect, useState } from "react";
import { assetUrl, getBlinkAuditReports, runBlinkAudit } from "../../api";
import type { FullFrameBlinkAuditReport } from "../../types/testLab";

export default function BlinkAuditLab() {
  const [reports, setReports] = useState<FullFrameBlinkAuditReport[]>([]);
  const [activeReport, setActiveReport] = useState<FullFrameBlinkAuditReport | null>(null);
  const [running, setRunning] = useState(false);

  async function refreshReports() {
    const next = await getBlinkAuditReports();
    setReports(next);
    setActiveReport((current) => current ?? next[0] ?? null);
  }

  useEffect(() => {
    refreshReports();
  }, []);

  async function handleRun() {
    setRunning(true);
    try {
      const report = await runBlinkAudit();
      if (report) {
        setActiveReport(report);
        setReports((current) => [report, ...current.filter((item) => item.id !== report.id)]);
      }
    } finally {
      setRunning(false);
    }
  }

  const eligibleCount = activeReport?.candidates.filter((candidate) => candidate.detection.eligible).length ?? 0;

  return (
    <div className="flex h-full min-h-0 flex-col gap-4">
      <div className="flex items-center justify-between gap-4 rounded-lg border border-neutral-800 bg-neutral-900/60 p-4">
        <div>
          <p className="text-xs font-semibold uppercase text-neutral-500">Blink Audit</p>
          <h2 className="mt-2 text-sm font-semibold text-neutral-100">Full-frame Burger King scenes</h2>
          <p className="mt-1 text-xs leading-5 text-neutral-500">
            Detects full-image eye anchors for in-place blink overlays without cropping the character out.
          </p>
        </div>
        <button
          onClick={handleRun}
          disabled={running}
          className="inline-flex items-center gap-2 rounded-md bg-violet-600 px-3 py-2 text-xs font-medium text-white transition-colors hover:bg-violet-500 disabled:cursor-not-allowed disabled:bg-neutral-800 disabled:text-neutral-500"
        >
          {running ? <Loader2 className="h-4 w-4 animate-spin" /> : <ScanFace className="h-4 w-4" />}
          Run Blink Audit
        </button>
      </div>
      <div className="grid min-h-0 flex-1 gap-4 lg:grid-cols-[260px_minmax(0,1fr)]">
        <aside className="min-h-0 overflow-y-auto rounded-lg border border-neutral-800 bg-neutral-900/60 p-3">
          <button
            onClick={refreshReports}
            className="mb-3 inline-flex w-full items-center justify-center gap-2 rounded-md border border-neutral-800 px-3 py-2 text-xs font-medium text-neutral-300 transition-colors hover:border-neutral-700 hover:text-neutral-100"
          >
            <RefreshCw className="h-4 w-4" />
            Refresh Reports
          </button>
          <div className="space-y-2">
            {reports.map((report) => (
              <button
                key={report.id}
                onClick={() => setActiveReport(report)}
                className={`w-full rounded-md border p-3 text-left transition-colors ${
                  activeReport?.id === report.id ? "border-violet-500 bg-violet-500/15" : "border-neutral-800 bg-neutral-950/50 hover:border-neutral-700"
                }`}
              >
                <p className="text-xs font-medium text-neutral-100">{report.title}</p>
                <p className="mt-1 text-xs text-neutral-500">{report.candidates.length} scenes</p>
              </button>
            ))}
          </div>
        </aside>
        <section className="min-h-0 overflow-y-auto rounded-lg border border-neutral-800 bg-neutral-900/60 p-4">
          {activeReport ? (
            <>
              <div className="mb-4 flex items-center justify-between gap-3">
                <div>
                  <h3 className="text-sm font-semibold text-neutral-100">{activeReport.title}</h3>
                  <p className="mt-1 text-xs text-neutral-500">{eligibleCount}/{activeReport.candidates.length} eligible</p>
                </div>
              </div>
              <div className="grid gap-3 xl:grid-cols-2">
                {activeReport.candidates.map((candidate) => (
                  <div key={candidate.scene_id} className="overflow-hidden rounded-lg border border-neutral-800 bg-neutral-950/50">
                    <img src={assetUrl(candidate.image_url)} alt="" className="aspect-video w-full object-cover" />
                    <div className="space-y-2 p-3">
                      <div className="flex items-center justify-between gap-3">
                        <p className="text-sm font-medium text-neutral-100">{candidate.scene_id}</p>
                        <span className={`inline-flex items-center gap-1 rounded-full px-2 py-1 text-xs font-medium ${
                          candidate.detection.eligible ? "bg-emerald-500/15 text-emerald-300" : "bg-amber-500/15 text-amber-300"
                        }`}>
                          {candidate.detection.eligible ? <CheckCircle2 className="h-3 w-3" /> : <AlertTriangle className="h-3 w-3" />}
                          {candidate.detection.eligible ? "Eligible" : "Rejected"}
                        </span>
                      </div>
                      <p className="line-clamp-2 text-xs leading-5 text-neutral-500">{candidate.scene_label}</p>
                      {!candidate.detection.eligible ? (
                        <p className="text-xs text-amber-300">{candidate.detection.reason}</p>
                      ) : (
                        <p className="text-xs text-emerald-300">{candidate.blink_enabled ? "50% gate: blink enabled" : "50% gate: blink skipped"}</p>
                      )}
                    </div>
                  </div>
                ))}
              </div>
            </>
          ) : (
            <div className="rounded-md border border-dashed border-neutral-800 bg-neutral-950/50 p-6 text-sm text-neutral-500">
              Run a Blink Audit to inspect full-frame scene eligibility.
            </div>
          )}
        </section>
      </div>
    </div>
  );
}
```

- [ ] **Step 6: Add tab to `TestLabPage`**

Modify `frontend/src/components/test-lab/TestLabPage.tsx`:

```typescript
import BlinkAuditLab from "./BlinkAuditLab";
type TestLabTab = "pipeline" | "popup-crop" | "blink-debug" | "blink-audit" | "smoke-test";
```

Add tab button:

```tsx
<TabButton active={activeTab === "blink-audit"} label="Blink Audit" onClick={() => setActiveTab("blink-audit")} />
```

Add render branch before smoke test:

```tsx
) : activeTab === "blink-audit" ? (
  <div className="min-h-0 flex-1 overflow-hidden p-4">
    <BlinkAuditLab />
  </div>
) : (
```

- [ ] **Step 7: Run frontend tests**

Run:

```bash
npm run test:frontend -- TestLabPage.test.tsx BlinkAuditLab.test.tsx
```

Expected: PASS.

## Task 8: Docs And Project Conventions

**Files:**
- Modify: `AGENTS.md`
- Modify: `frontend/src/components/docs/WorkflowDocSection.tsx`
- Modify: `frontend/src/components/docs/DocsPage.test.tsx`

- [ ] **Step 1: Write failing docs test**

Modify `frontend/src/components/docs/DocsPage.test.tsx`:

```typescript
expect(screen.getByText(/Test Lab -> Blink Audit/i)).toBeInTheDocument();
```

- [ ] **Step 2: Run docs test to verify it fails**

Run:

```bash
npm run test:frontend -- DocsPage.test.tsx
```

Expected: FAIL because the docs do not mention Blink Audit.

- [ ] **Step 3: Update workflow docs**

Modify `frontend/src/components/docs/WorkflowDocSection.tsx` in the Test Lab guidance list:

```typescript
"Use Test Lab -> Blink Audit to validate full-frame character blink eligibility on real generated scenes before enabling automatic production blink.",
```

- [ ] **Step 4: Update `AGENTS.md` conventions**

Replace the old “Blink visual mode is Test Lab-only” convention with:

```markdown
- **Full-frame blink is an enhancement, not a production visual mode**: Production blink should not be selected through `visual_mode="blink"`. Keep `visual_mode` focused on composition. Full-frame blink uses detected eye/skin anchors on the normal generated image plus renderer-owned eyelid overlays inside the same image layer, so Ken Burns/camera drift moves image and blink together. Use Test Lab -> Blink Audit to validate real full-size scene images before enabling automatic production blink. The old cutout-based `visual_mode="blink"` path remains only for Test Lab/debug compatibility until removed.
```

Also update related `AGENTS.md` bullets that list `blink` as production-routable or layered mode so they describe it as debug compatibility only.

- [ ] **Step 5: Run docs test**

Run:

```bash
npm run test:frontend -- DocsPage.test.tsx
```

Expected: PASS.

## Task 9: Verification, Commit, Push, Review Loop

**Files:**
- All changed implementation, test, docs, and plan files.

- [ ] **Step 1: Run focused backend tests**

Run:

```bash
uv run --project backend pytest backend/tests/test_full_frame_blink.py backend/tests/test_test_lab.py::test_blink_audit_endpoint_runs_report backend/tests/test_test_lab.py::test_blink_audit_history_endpoint_lists_reports backend/tests/pipeline/test_remotion_render.py::test_scene_input_props_include_full_frame_blink_metadata -q
```

Expected: PASS.

- [ ] **Step 2: Run focused frontend tests**

Run:

```bash
npm run test:frontend -- TreatmentRenderer.test.ts SceneRenderer.test.ts TestLabPage.test.tsx BlinkAuditLab.test.tsx DocsPage.test.tsx
```

Expected: PASS.

- [ ] **Step 3: Run broad suites if focused tests pass**

Run:

```bash
npm run test:backend
npm run test:frontend
```

Expected: PASS.

- [ ] **Step 4: Inspect final diff**

Run:

```bash
git status --short
git diff --stat
```

Expected: only intended Blink Audit, overlay, docs, and test files are changed.

- [ ] **Step 5: Commit and push to main**

Run:

```bash
git add AGENTS.md backend/api/test_lab.py backend/pipeline/full_frame_blink.py backend/pipeline/remotion_render.py backend/tests/test_full_frame_blink.py backend/tests/test_test_lab.py backend/tests/pipeline/test_remotion_render.py frontend/src/api.ts frontend/src/components/docs/DocsPage.test.tsx frontend/src/components/docs/WorkflowDocSection.tsx frontend/src/components/test-lab/BlinkAuditLab.tsx frontend/src/components/test-lab/BlinkAuditLab.test.tsx frontend/src/components/test-lab/TestLabPage.tsx frontend/src/components/test-lab/TestLabPage.test.tsx frontend/src/remotion/SceneRenderer.test.ts frontend/src/remotion/TreatmentRenderer.test.ts frontend/src/types/script.ts frontend/src/types/testLab.ts remotion/src/scenes/BlinkOverlay.tsx remotion/src/scenes/StaticImageScene.tsx remotion/src/scenes/TreatmentRenderer.tsx remotion/src/types.ts docs/superpowers/plans/2026-06-21-full-frame-blink-audit.md
git commit -m "Add full-frame blink audit"
git push origin main
```

Expected: commit and push succeed.

- [ ] **Step 6: Dispatch delegated code review**

Use Codex agent delegation tooling with:

```text
Review the most recent commit on the main branch of this project.
Run `git diff HEAD~1..HEAD` to see the changes and `git show --stat HEAD` for context.
Read the full affected files (not just the diff) to understand surrounding code.
Check for: correctness bugs, error handling gaps, security issues, naive/aware datetime mismatches, unhandled promise rejections, race conditions, and style problems.
Return a structured verdict: either LGTM or NEEDS CHANGES.
If NEEDS CHANGES, provide a numbered list of findings with severity (FAIL/WARN), file:line, and a specific description of what's wrong and how to fix it.
```

Expected: if NEEDS CHANGES, immediately fix every FAIL then WARN finding, commit as `fix: address review findings`, push, and repeat review until LGTM.

## Self-Review

- Spec coverage: The plan covers the in-place full-image overlay decision, Burger King Blink Audit tab, conservative detection, persisted reports, Remotion camera-compatible overlay, docs updates, and future deterministic 50% production gate helper.
- Placeholder scan: No unfinished marker words or unfilled implementation steps remain.
- Type consistency: Backend uses `FullFrameBlink*`; frontend mirrors those names; Remotion uses `full_frame_blink` metadata.
