# Project Blink Review Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a project-level Blink Review tab that lets the user manually approve eligible full-frame blinks and blocks render/export until the review is complete.

**Architecture:** Keep blink detection in `pipeline.full_frame_blink`, and add a focused `pipeline.project_blink_review` module for candidate refresh, review decisions, fingerprints, and render/export validation. Backend APIs expose the review state and decision updates. The Timeline UI adds a `Blink Review` tab that mirrors Blink Audit previews, while render/export endpoints call the shared guard before starting jobs.

**Tech Stack:** Python 3.12/FastAPI/SQLModel backend, React 19/TypeScript/Tailwind 4 frontend, Remotion metadata rendering, Vitest and pytest.

---

## File Structure

- Create `backend/pipeline/project_blink_review.py`: project-scoped candidate refresh, metadata fingerprinting, decision persistence, review status summaries, and blocking validation.
- Modify `backend/pipeline/full_frame_blink.py`: remove production use of the deterministic 50% gate; keep detector helpers and lab-only gate compatibility for Blink Audit.
- Modify `backend/pipeline/remotion_render.py`: emit `full_frame_blink` props only when review status is `enabled`.
- Modify `backend/api/blink_review.py`: new project Blink Review API routes.
- Modify `backend/api/__init__.py`: register the new API router.
- Modify `backend/api/render.py`, `backend/api/short_form.py`, `backend/api/upload_suite.py`, and `backend/api/publish.py`: call the shared render/export guard before jobs or cached export reuse begins.
- Modify `backend/api/visuals.py` and `backend/pipeline/render_phases.py`: create unreviewed blink metadata with fingerprints after full-frame image generation.
- Modify `backend/tests/test_full_frame_blink.py`, `backend/tests/test_visual_treatments.py`, `backend/tests/pipeline/test_remotion_render.py`, and create `backend/tests/test_project_blink_review.py`: backend coverage.
- Modify `frontend/src/api.ts` and create/update `frontend/src/types/blinkReview.ts`: API client and types.
- Create `frontend/src/components/timeline/BlinkReviewTab.tsx`: project tab UI.
- Modify `frontend/src/components/timeline/TimelinePage.tsx`: add tab, load status, route blocked render/export errors to Blink Review.
- Create `frontend/src/components/timeline/BlinkReviewTab.test.tsx` and update existing Timeline tests: frontend coverage.
- Modify `frontend/src/components/docs/WorkflowDocSection.tsx`, `frontend/src/components/docs/DocsPage.test.tsx`, and `AGENTS.md`: final workflow docs and conventions.

## Task 1: Backend Review Model And Fingerprints

**Files:**
- Create: `backend/pipeline/project_blink_review.py`
- Modify: `backend/pipeline/full_frame_blink.py`
- Test: `backend/tests/test_project_blink_review.py`

- [ ] **Step 1: Write failing tests for candidate refresh and fingerprinting**

Create `backend/tests/test_project_blink_review.py` with these tests:

```python
from datetime import datetime, timezone

from models.script import Scene, Script, ScriptContent, Segment


def content_with_scene(scene: Scene) -> ScriptContent:
    return ScriptContent(title="Blink Review", segments=[Segment(name="Segment", scenes=[scene])])


def test_refresh_blink_review_creates_unreviewed_metadata(monkeypatch, tmp_path):
    from pipeline import project_blink_review

    image_path = tmp_path / "projects" / "script-1" / "images" / "scene_001.png"
    image_path.parent.mkdir(parents=True)
    image_path.write_bytes(b"fake")
    scene = Scene(
        id="scene_001",
        narration="A worker waits.",
        visual_prompt="A worker in a kitchen.",
        visual_mode="full_frame",
        image_url="/static/projects/script-1/images/scene_001.png",
    )
    content = content_with_scene(scene)
    monkeypatch.setattr(project_blink_review, "DATA_DIR", tmp_path)
    monkeypatch.setattr(
        project_blink_review.full_frame_blink,
        "detect_full_frame_blink_anchor",
        lambda _path: project_blink_review.full_frame_blink.FullFrameBlinkDetection(
            status="passed",
            eligible=True,
            anchor={
                "detected": True,
                "skin_fill": "#F0D2B4",
                "eye_left": {"x": 0.4, "y": 0.3, "width": 0.01, "height": 0.01},
                "eye_right": {"x": 0.46, "y": 0.3, "width": 0.01, "height": 0.01},
            },
        ),
    )

    summary = project_blink_review.refresh_project_blink_review(content, "script-1")

    metadata = content.segments[0].scenes[0].visual_source_metadata["full_frame_blink"]
    assert summary.eligible_count == 1
    assert summary.unreviewed_count == 1
    assert metadata["enabled"] is False
    assert metadata["action"] == "blink"
    assert metadata["review"]["status"] == "unreviewed"
    assert metadata["fingerprint"]


def test_refresh_blink_review_resets_stale_review_when_image_changes(monkeypatch, tmp_path):
    from pipeline import project_blink_review

    image_path = tmp_path / "projects" / "script-1" / "images" / "new.png"
    image_path.parent.mkdir(parents=True)
    image_path.write_bytes(b"fake")
    scene = Scene(
        id="scene_001",
        narration="A worker waits.",
        visual_prompt="A worker in a kitchen.",
        visual_mode="full_frame",
        image_url="/static/projects/script-1/images/new.png",
        visual_source_metadata={
            "full_frame_blink": {
                "enabled": True,
                "action": "blink",
                "fingerprint": "old-fingerprint",
                "anchor": {"detected": True},
                "review": {"status": "enabled", "reviewed_at": "2026-06-21T00:00:00+00:00"},
            }
        },
    )
    content = content_with_scene(scene)
    monkeypatch.setattr(project_blink_review, "DATA_DIR", tmp_path)
    monkeypatch.setattr(
        project_blink_review.full_frame_blink,
        "detect_full_frame_blink_anchor",
        lambda _path: project_blink_review.full_frame_blink.FullFrameBlinkDetection(
            status="passed",
            eligible=True,
            anchor={"detected": True, "skin_fill": "#F0D2B4", "eye_left": {"x": 0.4}, "eye_right": {"x": 0.5}},
        ),
    )

    project_blink_review.refresh_project_blink_review(content, "script-1")

    metadata = content.segments[0].scenes[0].visual_source_metadata["full_frame_blink"]
    assert metadata["fingerprint"] != "old-fingerprint"
    assert metadata["enabled"] is False
    assert metadata["review"]["status"] == "unreviewed"
```

- [ ] **Step 2: Run tests to verify they fail**

Run:

```bash
uv run --project backend pytest backend/tests/test_project_blink_review.py -q
```

Expected: FAIL because `pipeline.project_blink_review` does not exist.

- [ ] **Step 3: Implement the review service**

Create `backend/pipeline/project_blink_review.py`:

```python
from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, Field

from config import DATA_DIR
from models.script import Scene, ScriptContent
from pipeline import full_frame_blink

BlinkReviewStatus = Literal["unreviewed", "enabled", "disabled"]


class BlinkReviewCandidate(BaseModel):
    scene_id: str
    scene_label: str
    image_url: str
    eligible: bool
    reason: str = ""
    anchor: dict[str, object] | None = None
    fingerprint: str = ""
    review_status: BlinkReviewStatus | Literal["rejected"] = "rejected"
    enabled: bool = False


class BlinkReviewSummary(BaseModel):
    script_id: str
    candidates: list[BlinkReviewCandidate] = Field(default_factory=list)
    eligible_count: int = 0
    unreviewed_count: int = 0
    enabled_count: int = 0
    disabled_count: int = 0
    complete: bool = True


class BlinkReviewRequiredError(RuntimeError):
    def __init__(self, summary: BlinkReviewSummary):
        self.summary = summary
        super().__init__(
            f"Blink Review must be completed before rendering/exporting: "
            f"{summary.unreviewed_count} eligible scene(s) still need review."
        )


def blink_metadata_fingerprint(image_url: str, anchor: dict[str, object]) -> str:
    payload = json.dumps({"image_url": image_url, "anchor": anchor}, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def build_unreviewed_full_frame_blink_metadata(script_id: str, scene_id: str, image_url: str) -> dict[str, object] | None:
    image_path = full_frame_blink.image_path_from_static_url(image_url)
    if image_path is None:
        return None
    detection = full_frame_blink.detect_full_frame_blink_anchor(image_path)
    if not detection.eligible or detection.anchor is None:
        return None
    return {
        "enabled": False,
        "action": "blink",
        "fingerprint": blink_metadata_fingerprint(image_url, detection.anchor),
        "anchor": detection.anchor,
        "review": {"status": "unreviewed"},
    }


def refresh_project_blink_review(content: ScriptContent, script_id: str) -> BlinkReviewSummary:
    candidates: list[BlinkReviewCandidate] = []
    for scene in content.all_scenes():
        candidate = _refresh_scene(content, script_id, scene)
        if candidate is not None:
            candidates.append(candidate)
    return _summary(script_id, candidates)


def set_project_blink_review_decision(
    content: ScriptContent,
    script_id: str,
    scene_id: str,
    status: Literal["enabled", "disabled"],
) -> BlinkReviewSummary:
    refresh_project_blink_review(content, script_id)
    scene = next((item for item in content.all_scenes() if item.id == scene_id), None)
    if scene is None:
        raise ValueError(f"Scene not found: {scene_id}")
    blink = _blink_metadata(scene)
    if not blink or blink.get("review", {}).get("status") == "rejected":
        raise ValueError(f"Scene is not eligible for blink review: {scene_id}")
    blink["enabled"] = status == "enabled"
    blink["review"] = {"status": status, "reviewed_at": datetime.now(timezone.utc).isoformat()}
    scene.visual_source_metadata = {**(scene.visual_source_metadata or {}), "full_frame_blink": blink}
    return refresh_project_blink_review(content, script_id)


def validate_project_blink_review_complete(content: ScriptContent, script_id: str) -> BlinkReviewSummary:
    summary = refresh_project_blink_review(content, script_id)
    if not summary.complete:
        raise BlinkReviewRequiredError(summary)
    return summary


def _refresh_scene(content: ScriptContent, script_id: str, scene: Scene) -> BlinkReviewCandidate | None:
    if scene.is_title_card or scene.visual_mode not in full_frame_blink.MEDIA_BACKED_BLINK_MODES:
        return None
    image_url = scene.image_url or ""
    if not image_url:
        _clear_scene_blink(scene)
        return None
    image_path = full_frame_blink.image_path_from_static_url(image_url)
    if image_path is None:
        _clear_scene_blink(scene)
        return None
    detection = full_frame_blink.detect_full_frame_blink_anchor(image_path)
    if not detection.eligible or detection.anchor is None:
        _set_scene_blink(scene, {
            "enabled": False,
            "action": "blink",
            "anchor": None,
            "fingerprint": "",
            "review": {"status": "rejected"},
            "reason": detection.reason,
        })
        return BlinkReviewCandidate(
            scene_id=scene.id,
            scene_label=scene.narration[:120],
            image_url=image_url,
            eligible=False,
            reason=detection.reason,
            review_status="rejected",
        )
    fingerprint = blink_metadata_fingerprint(image_url, detection.anchor)
    existing = _blink_metadata(scene)
    existing_review = existing.get("review", {}) if existing and existing.get("fingerprint") == fingerprint else {}
    review_status = existing_review.get("status") if existing_review.get("status") in {"enabled", "disabled"} else "unreviewed"
    blink = {
        "enabled": review_status == "enabled",
        "action": "blink",
        "fingerprint": fingerprint,
        "anchor": detection.anchor,
        "review": {
            "status": review_status,
            **({"reviewed_at": existing_review.get("reviewed_at")} if existing_review.get("reviewed_at") else {}),
        },
    }
    _set_scene_blink(scene, blink)
    return BlinkReviewCandidate(
        scene_id=scene.id,
        scene_label=scene.narration[:120],
        image_url=image_url,
        eligible=True,
        anchor=detection.anchor,
        fingerprint=fingerprint,
        review_status=review_status,
        enabled=review_status == "enabled",
    )


def _summary(script_id: str, candidates: list[BlinkReviewCandidate]) -> BlinkReviewSummary:
    eligible = [item for item in candidates if item.eligible]
    unreviewed = [item for item in eligible if item.review_status == "unreviewed"]
    enabled = [item for item in eligible if item.review_status == "enabled"]
    disabled = [item for item in eligible if item.review_status == "disabled"]
    return BlinkReviewSummary(
        script_id=script_id,
        candidates=candidates,
        eligible_count=len(eligible),
        unreviewed_count=len(unreviewed),
        enabled_count=len(enabled),
        disabled_count=len(disabled),
        complete=len(unreviewed) == 0,
    )


def _blink_metadata(scene: Scene) -> dict[str, object] | None:
    metadata = scene.visual_source_metadata or {}
    blink = metadata.get("full_frame_blink")
    return blink if isinstance(blink, dict) else None


def _set_scene_blink(scene: Scene, blink: dict[str, object]) -> None:
    scene.visual_source_metadata = {**(scene.visual_source_metadata or {}), "full_frame_blink": blink}


def _clear_scene_blink(scene: Scene) -> None:
    metadata = dict(scene.visual_source_metadata or {})
    metadata.pop("full_frame_blink", None)
    scene.visual_source_metadata = metadata or None
```

In `backend/pipeline/full_frame_blink.py`, promote `_image_path_from_url` to `image_path_from_static_url`, update existing internal callers, and use that public helper from `project_blink_review.py`.

- [ ] **Step 4: Run tests to verify they pass**

Run:

```bash
uv run --project backend pytest backend/tests/test_project_blink_review.py -q
```

Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add backend/pipeline/project_blink_review.py backend/tests/test_project_blink_review.py backend/pipeline/full_frame_blink.py
git commit -m "Add project blink review service"
```

## Task 2: Backend API And Persistence

**Files:**
- Create: `backend/api/blink_review.py`
- Modify: `backend/api/__init__.py`
- Modify: `backend/api/visuals.py`
- Modify: `backend/pipeline/render_phases.py`
- Test: `backend/tests/test_project_blink_review.py`

- [ ] **Step 1: Add failing API tests**

Append to `backend/tests/test_project_blink_review.py`:

```python
def test_blink_review_api_returns_project_candidates(monkeypatch, tmp_path):
    from api.blink_review import get_blink_review
    import pipeline.project_blink_review as review
    from sqlmodel import Session, SQLModel, create_engine
    from sqlmodel.pool import StaticPool

    import models.brand  # noqa: F401
    import models.script  # noqa: F401

    engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    SQLModel.metadata.create_all(engine)
    content = content_with_scene(
        Scene(
            id="scene_001",
            narration="A worker waits.",
            visual_prompt="Worker",
            visual_mode="full_frame",
            image_url="/static/projects/script-1/images/scene_001.png",
        )
    )
    monkeypatch.setattr(review, "refresh_project_blink_review", lambda content, script_id: review.BlinkReviewSummary(
        script_id=script_id,
        candidates=[
            review.BlinkReviewCandidate(
                scene_id="scene_001",
                scene_label="A worker waits.",
                image_url="/static/projects/script-1/images/scene_001.png",
                eligible=True,
                fingerprint="abc",
                review_status="unreviewed",
            )
        ],
        eligible_count=1,
        unreviewed_count=1,
        complete=False,
    ))
    with Session(engine) as session:
        session.add(Script(id="script-1", brand_id="brand", script_json=content.model_dump_json(), created_at=datetime.now(timezone.utc)))
        session.commit()
        response = get_blink_review("script-1", session)

    assert response["eligible_count"] == 1
    assert response["complete"] is False


def test_blink_review_api_persists_decision(monkeypatch):
    from api.blink_review import UpdateBlinkReviewDecisionRequest, update_blink_review_decision
    from sqlmodel import Session, SQLModel, create_engine
    from sqlmodel.pool import StaticPool

    import models.brand  # noqa: F401
    import models.script  # noqa: F401

    engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    SQLModel.metadata.create_all(engine)
    content = content_with_scene(
        Scene(
            id="scene_001",
            narration="A worker waits.",
            visual_prompt="Worker",
            visual_mode="full_frame",
            image_url="/static/projects/script-1/images/scene_001.png",
            visual_source_metadata={
                "full_frame_blink": {
                    "enabled": False,
                    "action": "blink",
                    "fingerprint": "abc",
                    "anchor": {"detected": True},
                    "review": {"status": "unreviewed"},
                }
            },
        )
    )
    monkeypatch.setattr(
        "pipeline.project_blink_review.refresh_project_blink_review",
        lambda content, script_id: __import__("pipeline.project_blink_review", fromlist=["BlinkReviewSummary"]).BlinkReviewSummary(
            script_id=script_id,
            candidates=[],
            complete=True,
        ),
    )
    with Session(engine) as session:
        session.add(Script(id="script-1", brand_id="brand", script_json=content.model_dump_json(), created_at=datetime.now(timezone.utc)))
        session.commit()
        update_blink_review_decision(
            "script-1",
            "scene_001",
            UpdateBlinkReviewDecisionRequest(status="enabled"),
            session,
        )
        stored = session.get(Script, "script-1")
        updated = ScriptContent.model_validate_json(stored.script_json)

    blink = updated.segments[0].scenes[0].visual_source_metadata["full_frame_blink"]
    assert blink["enabled"] is True
    assert blink["review"]["status"] == "enabled"
```

- [ ] **Step 2: Run tests to verify they fail**

Run:

```bash
uv run --project backend pytest backend/tests/test_project_blink_review.py::test_blink_review_api_returns_project_candidates backend/tests/test_project_blink_review.py::test_blink_review_api_persists_decision -q
```

Expected: FAIL because `api.blink_review` does not exist.

- [ ] **Step 3: Implement API routes**

Create `backend/api/blink_review.py`:

```python
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlmodel import Session

from database import get_session
from models.script import Script, ScriptContent
from pipeline.project_blink_review import refresh_project_blink_review, set_project_blink_review_decision

router = APIRouter(prefix="/api/blink-review", tags=["blink-review"])


class UpdateBlinkReviewDecisionRequest(BaseModel):
    status: Literal["enabled", "disabled"]


def _load_content(session: Session, script_id: str) -> tuple[Script, ScriptContent]:
    record = session.get(Script, script_id)
    if record is None:
        raise HTTPException(status_code=404, detail="Script not found")
    return record, ScriptContent.model_validate_json(record.script_json)


@router.get("/{script_id}")
def get_blink_review(script_id: str, session: Session = Depends(get_session)):
    record, content = _load_content(session, script_id)
    summary = refresh_project_blink_review(content, script_id)
    record.script_json = content.model_dump_json()
    session.add(record)
    session.commit()
    return summary.model_dump(mode="json")


@router.post("/{script_id}/scenes/{scene_id}")
def update_blink_review_decision(
    script_id: str,
    scene_id: str,
    request: UpdateBlinkReviewDecisionRequest,
    session: Session = Depends(get_session),
):
    record, content = _load_content(session, script_id)
    try:
        summary = set_project_blink_review_decision(content, script_id, scene_id, request.status)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    record.script_json = content.model_dump_json()
    session.add(record)
    session.commit()
    return summary.model_dump(mode="json")
```

Modify `backend/api/__init__.py`:

```python
from api.blink_review import router as blink_review_router

app.include_router(blink_review_router)
```

Place the import and `include_router` near the other feature routers.

- [ ] **Step 4: Update image-generation persistence to create unreviewed metadata**

In `backend/api/visuals.py`, replace direct calls to `full_frame_blink_mod.build_full_frame_blink_metadata` with `project_blink_review.build_unreviewed_full_frame_blink_metadata`. That helper creates `review.status = "unreviewed"` and `enabled = False`.

Preserve source metadata with this shape:

```python
source_metadata = _metadata_with_full_frame_blink(
    script_id=body.script_id,
    scene_id=body.scene_id,
    visual_mode=media_mode,
    image_url=image_url,
    source_metadata=source_metadata,
)
```

The returned metadata must include `full_frame_blink.enabled = False` until the user manually enables it.

In `backend/pipeline/render_phases.py`, mirror this behavior in `_phase_images`/`_phase_persist` so export-test image generation also creates unreviewed metadata instead of auto-enabled metadata.

- [ ] **Step 5: Run backend API and visual metadata tests**

Run:

```bash
uv run --project backend pytest backend/tests/test_project_blink_review.py backend/tests/test_visual_treatments.py -q
```

Expected: PASS.

- [ ] **Step 6: Commit**

```bash
git add backend/api/blink_review.py backend/api/__init__.py backend/api/visuals.py backend/pipeline/render_phases.py backend/tests/test_project_blink_review.py backend/tests/test_visual_treatments.py
git commit -m "Add project blink review API"
```

## Task 3: Render And Export Guards

**Files:**
- Modify: `backend/api/render.py`
- Modify: `backend/api/short_form.py`
- Modify: `backend/api/upload_suite.py`
- Modify: `backend/api/publish.py`
- Modify: `backend/pipeline/remotion_render.py`
- Test: `backend/tests/test_project_blink_review.py`
- Test: `backend/tests/pipeline/test_remotion_render.py`

- [ ] **Step 1: Write failing tests for guard and renderer props**

Append to `backend/tests/test_project_blink_review.py`:

```python
def test_validate_project_blink_review_blocks_unreviewed_scene():
    from pipeline.project_blink_review import BlinkReviewRequiredError, validate_project_blink_review_complete

    content = content_with_scene(
        Scene(
            id="scene_001",
            narration="A worker waits.",
            visual_prompt="Worker",
            visual_mode="full_frame",
            image_url="/static/projects/script-1/images/scene_001.png",
            visual_source_metadata={
                "full_frame_blink": {
                    "enabled": False,
                    "action": "blink",
                    "fingerprint": "abc",
                    "anchor": {"detected": True},
                    "review": {"status": "unreviewed"},
                }
            },
        )
    )

    try:
        validate_project_blink_review_complete(content, "script-1")
    except BlinkReviewRequiredError as exc:
        assert exc.summary.unreviewed_count == 1
    else:
        raise AssertionError("Expected BlinkReviewRequiredError")


def test_validate_project_blink_review_allows_reviewed_scene():
    from pipeline.project_blink_review import validate_project_blink_review_complete

    content = content_with_scene(
        Scene(
            id="scene_001",
            narration="A worker waits.",
            visual_prompt="Worker",
            visual_mode="full_frame",
            image_url="/static/projects/script-1/images/scene_001.png",
            visual_source_metadata={
                "full_frame_blink": {
                    "enabled": True,
                    "action": "blink",
                    "fingerprint": "abc",
                    "anchor": {"detected": True},
                    "review": {"status": "enabled", "reviewed_at": "2026-06-21T00:00:00+00:00"},
                }
            },
        )
    )

    summary = validate_project_blink_review_complete(content, "script-1")

    assert summary.complete is True
```

Append to `backend/tests/pipeline/test_remotion_render.py`:

```python
def test_scene_input_props_suppresses_unreviewed_full_frame_blink():
    from models.script import Scene
    from pipeline.remotion_render import _scene_to_input_props

    scene = Scene(
        id="scene_001",
        narration="A worker waits.",
        visual_prompt="Worker",
        image_url="/static/projects/script-1/images/scene_001.png",
        visual_source_metadata={
            "full_frame_blink": {
                "enabled": False,
                "action": "blink",
                "fingerprint": "abc",
                "anchor": {"detected": True},
                "review": {"status": "unreviewed"},
            }
        },
    )

    props = _scene_to_input_props(scene, "script-1")

    assert props["full_frame_blink"] is None


def test_scene_input_props_includes_manually_enabled_full_frame_blink():
    from models.script import Scene
    from pipeline.remotion_render import _scene_to_input_props

    scene = Scene(
        id="scene_001",
        narration="A worker waits.",
        visual_prompt="Worker",
        image_url="/static/projects/script-1/images/scene_001.png",
        visual_source_metadata={
            "full_frame_blink": {
                "enabled": True,
                "action": "blink",
                "fingerprint": "abc",
                "anchor": {"detected": True, "eye_left": {"x": 0.4, "y": 0.3}},
                "review": {"status": "enabled", "reviewed_at": "2026-06-21T00:00:00+00:00"},
            }
        },
    )

    props = _scene_to_input_props(scene, "script-1")

    assert props["full_frame_blink"]["enabled"] is True
    assert props["full_frame_blink"]["anchor"]["eye_left"]["x"] == 0.4
```

- [ ] **Step 2: Run tests to verify failures**

Run:

```bash
uv run --project backend pytest backend/tests/test_project_blink_review.py::test_validate_project_blink_review_blocks_unreviewed_scene backend/tests/test_project_blink_review.py::test_validate_project_blink_review_allows_reviewed_scene backend/tests/pipeline/test_remotion_render.py::test_scene_input_props_suppresses_unreviewed_full_frame_blink backend/tests/pipeline/test_remotion_render.py::test_scene_input_props_includes_manually_enabled_full_frame_blink -q
```

Expected: FAIL for renderer prop behavior until `_scene_to_input_props` checks review status.

- [ ] **Step 3: Update Remotion props gating**

In `backend/pipeline/remotion_render.py`, change the `raw_blink` block:

```python
review = raw_blink.get("review") if isinstance(raw_blink.get("review"), dict) else {}
if isinstance(raw_blink, dict) and raw_blink.get("enabled") is True and review.get("status") == "enabled":
    raw_anchor = raw_blink.get("anchor")
    full_frame_blink = {
        "enabled": True,
        "action": "blink" if raw_blink.get("action") == "blink" else "",
        "anchor": raw_anchor if isinstance(raw_anchor, dict) else None,
    }
```

Update `_full_frame_blink_fingerprint` to include only manually enabled blink metadata, or include review status so cache invalidates when a review decision changes:

```python
return {
    "enabled": raw_blink.get("enabled") is True,
    "action": "blink" if raw_blink.get("action") == "blink" else "",
    "fingerprint": raw_blink.get("fingerprint"),
    "review_status": review.get("status"),
    "anchor": raw_anchor if isinstance(raw_anchor, dict) else None,
}
```

- [ ] **Step 4: Add render/export guard helper use**

Add a helper in `backend/pipeline/project_blink_review.py` if not already present:

```python
def ensure_project_blink_review_complete_for_script(record: Script) -> None:
    content = ScriptContent.model_validate_json(record.script_json)
    validate_project_blink_review_complete(content, record.id)
```

In every render/export entrypoint that starts or reuses media, load the script and call `validate_project_blink_review_complete(content, script_id)` before creating jobs or returning cached exported media. Convert `BlinkReviewRequiredError` to HTTP 409:

```python
except BlinkReviewRequiredError as exc:
    raise HTTPException(status_code=409, detail={
        "code": "blink_review_required",
        "message": str(exc),
        "summary": exc.summary.model_dump(mode="json"),
    }) from exc
```

Apply this to:

- long-form render start in `backend/api/render.py`
- rendered-longform status/export reuse paths in `backend/api/render.py`
- short-form render all/batch/one and export in `backend/api/short_form.py`
- upload suite rendered media status in `backend/api/upload_suite.py`
- publish upload endpoints in `backend/api/publish.py` when they resolve rendered video paths

Do not guard thumbnail or SEO-only exports.

- [ ] **Step 5: Run guard and render tests**

Run:

```bash
uv run --project backend pytest backend/tests/test_project_blink_review.py backend/tests/pipeline/test_remotion_render.py -q
```

Expected: PASS.

- [ ] **Step 6: Commit**

```bash
git add backend/pipeline/project_blink_review.py backend/pipeline/remotion_render.py backend/api/render.py backend/api/short_form.py backend/api/upload_suite.py backend/api/publish.py backend/tests/test_project_blink_review.py backend/tests/pipeline/test_remotion_render.py
git commit -m "Guard rendering on blink review"
```

## Task 4: Frontend API Types And Blink Review Tab

**Files:**
- Create: `frontend/src/types/blinkReview.ts`
- Modify: `frontend/src/api.ts`
- Create: `frontend/src/components/timeline/BlinkReviewTab.tsx`
- Create: `frontend/src/components/timeline/BlinkReviewTab.test.tsx`
- Modify: `frontend/src/components/timeline/TimelinePage.tsx`

- [ ] **Step 1: Write failing frontend tests for the tab**

Create `frontend/src/components/timeline/BlinkReviewTab.test.tsx`:

```tsx
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";

import BlinkReviewTab from "./BlinkReviewTab";

describe("BlinkReviewTab", () => {
  it("shows eligible scenes with manual enable and disable controls", async () => {
    const onDecision = vi.fn();
    render(
      <BlinkReviewTab
        summary={{
          script_id: "script-1",
          eligible_count: 1,
          unreviewed_count: 1,
          enabled_count: 0,
          disabled_count: 0,
          complete: false,
          candidates: [
            {
              scene_id: "scene_001",
              scene_label: "A worker waits.",
              image_url: "/static/projects/script-1/images/scene_001.png",
              eligible: true,
              reason: "",
              anchor: { detected: true, skin_fill: "#F0D2B4" },
              fingerprint: "abc",
              review_status: "unreviewed",
              enabled: false,
            },
          ],
        }}
        loading={false}
        updatingSceneId={null}
        onRefresh={vi.fn()}
        onDecision={onDecision}
      />,
    );

    expect(screen.getByText("scene_001")).toBeInTheDocument();
    expect(screen.getByText(/needs review/i)).toBeInTheDocument();
    await userEvent.click(screen.getByRole("button", { name: /enable blink/i }));
    expect(onDecision).toHaveBeenCalledWith("scene_001", "enabled");
  });

  it("shows a complete empty state when no candidates are eligible", () => {
    render(
      <BlinkReviewTab
        summary={{
          script_id: "script-1",
          eligible_count: 0,
          unreviewed_count: 0,
          enabled_count: 0,
          disabled_count: 0,
          complete: true,
          candidates: [],
        }}
        loading={false}
        updatingSceneId={null}
        onRefresh={vi.fn()}
        onDecision={vi.fn()}
      />,
    );

    expect(screen.getByText(/no safe blink candidates/i)).toBeInTheDocument();
  });
});
```

- [ ] **Step 2: Run test to verify it fails**

Run:

```bash
cd frontend && npm run test -- src/components/timeline/BlinkReviewTab.test.tsx
```

Expected: FAIL because `BlinkReviewTab` and blink review types do not exist.

- [ ] **Step 3: Add frontend types and API helpers**

Create `frontend/src/types/blinkReview.ts`:

```ts
export type BlinkReviewStatus = "unreviewed" | "enabled" | "disabled" | "rejected";

export interface BlinkReviewCandidate {
  scene_id: string;
  scene_label: string;
  image_url: string;
  eligible: boolean;
  reason: string;
  anchor?: Record<string, unknown> | null;
  fingerprint: string;
  review_status: BlinkReviewStatus;
  enabled: boolean;
}

export interface BlinkReviewSummary {
  script_id: string;
  candidates: BlinkReviewCandidate[];
  eligible_count: number;
  unreviewed_count: number;
  enabled_count: number;
  disabled_count: number;
  complete: boolean;
}
```

Add to `frontend/src/api.ts`:

```ts
import type { BlinkReviewSummary } from "./types/blinkReview";

export async function getBlinkReview(scriptId: string): Promise<BlinkReviewSummary> {
  const res = await api.get<BlinkReviewSummary>(`/api/blink-review/${encodeURIComponent(scriptId)}`);
  if (!res.ok) throw new Error((res.data as { detail?: string }).detail || "Failed to load Blink Review");
  return res.data;
}

export async function updateBlinkReviewDecision(
  scriptId: string,
  sceneId: string,
  status: "enabled" | "disabled",
): Promise<BlinkReviewSummary> {
  const res = await api.post<BlinkReviewSummary>(
    `/api/blink-review/${encodeURIComponent(scriptId)}/scenes/${encodeURIComponent(sceneId)}`,
    { status },
  );
  if (!res.ok) throw new Error((res.data as { detail?: string }).detail || "Failed to update Blink Review");
  return res.data;
}
```

- [ ] **Step 4: Implement `BlinkReviewTab`**

Create `frontend/src/components/timeline/BlinkReviewTab.tsx`. Reuse `assetUrl` and copy the small overlay preview helper from `BlinkAuditLab.tsx`, or extract that helper into a shared `frontend/src/components/blink/BlinkPreviewOverlay.tsx` if duplication becomes awkward.

The component props:

```ts
interface Props {
  summary: BlinkReviewSummary | null;
  loading: boolean;
  updatingSceneId: string | null;
  onRefresh: () => void;
  onDecision: (sceneId: string, status: "enabled" | "disabled") => void;
}
```

UI requirements:

- Header text: `Review eligible full-frame blinks before rendering or exporting.`
- Summary chips for eligible, needs review, enabled, disabled.
- Eligible cards only in the main grid.
- Each card has `Enable blink` and `Disable blink` buttons.
- `unreviewed` status label text is `Needs review`.
- Empty complete state text is `No safe blink candidates were found. Blink Review is complete.`

- [ ] **Step 5: Run tab tests**

Run:

```bash
cd frontend && npm run test -- src/components/timeline/BlinkReviewTab.test.tsx
```

Expected: PASS.

- [ ] **Step 6: Add the tab to `TimelinePage`**

Modify the tab list in `frontend/src/components/timeline/TimelinePage.tsx`:

```ts
{ key: "blink-review", label: "Blink Review", Icon: Eye }
```

Add `blink-review` to the `ViewerTab` union. Load review state with `getBlinkReview(scriptId)` after images refresh and when the tab is opened. Implement:

```ts
const [blinkReview, setBlinkReview] = useState<BlinkReviewSummary | null>(null);
const [blinkReviewLoading, setBlinkReviewLoading] = useState(false);
const [blinkReviewUpdatingSceneId, setBlinkReviewUpdatingSceneId] = useState<string | null>(null);
```

Add callbacks:

```ts
const refreshBlinkReview = useCallback(async () => {
  setBlinkReviewLoading(true);
  try {
    setBlinkReview(await getBlinkReview(scriptId));
  } finally {
    setBlinkReviewLoading(false);
  }
}, [scriptId]);

const handleBlinkReviewDecision = useCallback(async (sceneId: string, status: "enabled" | "disabled") => {
  setBlinkReviewUpdatingSceneId(sceneId);
  try {
    const next = await updateBlinkReviewDecision(scriptId, sceneId, status);
    setBlinkReview(next);
    await refreshScriptContent();
  } finally {
    setBlinkReviewUpdatingSceneId(null);
  }
}, [refreshScriptContent, scriptId]);
```

Render `BlinkReviewTab` for the new tab.

- [ ] **Step 7: Commit**

```bash
git add frontend/src/types/blinkReview.ts frontend/src/api.ts frontend/src/components/timeline/BlinkReviewTab.tsx frontend/src/components/timeline/BlinkReviewTab.test.tsx frontend/src/components/timeline/TimelinePage.tsx
git commit -m "Add project blink review tab"
```

## Task 5: Frontend Render/Export Blocking UX

**Files:**
- Modify: `frontend/src/components/timeline/TimelinePage.tsx`
- Modify or create tests around Timeline export handling.

- [ ] **Step 1: Write failing test for blocked response handling**

Add a focused utility near `TimelinePage` or in a testable helper file:

```ts
export function isBlinkReviewRequiredError(error: unknown): boolean {
  return error instanceof Error && error.message.toLowerCase().includes("blink review");
}
```

Create or update a test file:

```tsx
import { describe, expect, it } from "vitest";
import { isBlinkReviewRequiredError } from "./TimelinePage";

describe("isBlinkReviewRequiredError", () => {
  it("detects backend blink review blocking errors", () => {
    expect(isBlinkReviewRequiredError(new Error("Blink Review must be completed before rendering/exporting"))).toBe(true);
    expect(isBlinkReviewRequiredError(new Error("Render failed"))).toBe(false);
  });
});
```

- [ ] **Step 2: Run test to verify it fails**

Run:

```bash
cd frontend && npm run test -- src/components/timeline/TimelinePage.test.tsx
```

Expected: FAIL until the helper exists/export is adjusted.

- [ ] **Step 3: Route blocked errors to the Blink Review tab**

In `TimelinePage.tsx`, inside render/export task catch blocks or `runProductionTask`, detect blink-review-required errors. On detection:

```ts
setActiveTab("blink-review");
void refreshBlinkReview();
showToast("Complete Blink Review before rendering or exporting.", "info");
```

If an existing modal/confirm component is already used for blocking task warnings, use that instead of `window.alert`. The message must mention `Blink Review` and must not start the render/export job.

- [ ] **Step 4: Run frontend tests**

Run:

```bash
cd frontend && npm run test -- src/components/timeline/BlinkReviewTab.test.tsx src/components/timeline/TimelinePage.test.tsx
```

Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add frontend/src/components/timeline/TimelinePage.tsx frontend/src/components/timeline/TimelinePage.test.tsx
git commit -m "Surface blink review render guard"
```

## Task 6: Docs And Final Workflow Conventions

**Files:**
- Modify: `AGENTS.md`
- Modify: `frontend/src/components/docs/WorkflowDocSection.tsx`
- Modify: `frontend/src/components/docs/DocsPage.test.tsx`
- Modify: `docs/superpowers/specs/2026-06-21-project-blink-review-design.md`

- [ ] **Step 1: Update docs tests**

Modify `frontend/src/components/docs/DocsPage.test.tsx` to assert:

```ts
expect(screen.getByText(/Blink Review before rendering or exporting/i)).toBeInTheDocument();
expect(screen.getByText(/render\/export uses only manually enabled blink candidates/i)).toBeInTheDocument();
```

- [ ] **Step 2: Run docs test to verify it fails**

Run:

```bash
cd frontend && npm run test -- src/components/docs/DocsPage.test.tsx
```

Expected: FAIL until workflow docs are updated.

- [ ] **Step 3: Update workflow docs and AGENTS**

In `frontend/src/components/docs/WorkflowDocSection.tsx`, replace the current Blink Audit production wording with:

```ts
"Use Test Lab -> Blink -> Blink Audit for detector tuning. For real projects, complete the Timeline -> Blink Review tab after images are generated; rendering and exporting are blocked until eligible blink candidates are reviewed.",
"Render/export uses only manually enabled Blink Review candidates. Disabled candidates stay static, and unreviewed candidates block the job instead of silently blinking or skipping.",
```

In `AGENTS.md`, update the full-frame blink convention to say:

```markdown
- **Full-frame blink requires manual project review**: Production blink must not be selected through `visual_mode="blink"` and must not be decided by an automatic 50% gate. Normal `full_frame` scenes may receive `visual_source_metadata.full_frame_blink` after image generation when the shared detector passes strict eye symmetry/alignment/anchor-safety checks. Those candidates start as `review.status="unreviewed"` and render/export is blocked until Timeline -> Blink Review marks every eligible candidate `enabled` or `disabled`. Render/export uses only manually `enabled` candidates. Blink Audit remains a detector lab, not the production approval surface.
```

In `docs/superpowers/specs/2026-06-21-project-blink-review-design.md`, remove the future-proposal disclaimer or replace it with an implementation note:

```markdown
This design is implemented by the project Blink Review feature.
```

- [ ] **Step 4: Run docs tests**

Run:

```bash
cd frontend && npm run test -- src/components/docs/DocsPage.test.tsx
```

Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add AGENTS.md frontend/src/components/docs/WorkflowDocSection.tsx frontend/src/components/docs/DocsPage.test.tsx docs/superpowers/specs/2026-06-21-project-blink-review-design.md
git commit -m "Document project blink review workflow"
```

## Task 7: Full Verification And Review

**Files:**
- No new files.

- [ ] **Step 1: Run backend tests**

Run:

```bash
npm run test:backend
```

Expected: `passed`.

- [ ] **Step 2: Run frontend tests**

Run:

```bash
npm run test:frontend
```

Expected: all Vitest files pass.

- [ ] **Step 3: Build frontend**

Run:

```bash
cd frontend && npm run build
```

Expected: TypeScript and Vite build succeed.

- [ ] **Step 4: Browser QA**

Start or reuse the dev server. Navigate to a project with full-frame images and verify:

- `Blink Review` tab is visible.
- Eligible candidates show still/blink previews.
- `Enable blink` and `Disable blink` update card status.
- Render/export attempts with unreviewed candidates show a warning and switch to `Blink Review`.
- Render/export attempts after all candidates are reviewed start normally.

- [ ] **Step 5: Confirm the working tree contains only intended implementation files**

Run:

```bash
git status --short
git diff --check
```

Expected: only intended Blink Review implementation files are listed, and `git diff --check` prints no whitespace errors.

- [ ] **Step 6: Push and review**

Run:

```bash
git push origin main
```

Then dispatch the required delegated review:

```text
Review the most recent commit on the main branch of this project.
Run `git diff HEAD~1..HEAD` to see the changes and `git show --stat HEAD` for context.
Read the full affected files (not just the diff) to understand surrounding code.
Check for: correctness bugs, error handling gaps, security issues, naive/aware datetime mismatches, unhandled promise rejections, race conditions, and style problems.
Return a structured verdict: either LGTM or NEEDS CHANGES.
If NEEDS CHANGES, provide a numbered list of findings with severity (FAIL/WARN), file:line, and a specific description of what's wrong and how to fix it.
```

Fix all FAIL/WARN findings, commit as `fix: address review findings`, push, and repeat review until LGTM.

## Self-Review

- Spec coverage: The plan covers project tab, shared detector use, manual enable/disable decisions, stale fingerprinting, render/export blocking, renderer gating, docs/conventions, and tests.
- Placeholder scan: No placeholder markers or unspecified implementation sections remain.
- Type consistency: Backend uses `BlinkReviewSummary`, `BlinkReviewCandidate`, and `review.status`; frontend mirrors those names in `BlinkReviewSummary` and `BlinkReviewCandidate`.
