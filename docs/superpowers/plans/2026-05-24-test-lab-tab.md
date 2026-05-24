# Test Lab Tab Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a hidden-production-pipeline Test tab for running one realistic dummy scene through real audio, visual, character, FX, and Remotion generation, with playable preview, assets, logs, cost, and last-20 run history.

**Architecture:** Add a Test Lab backend router backed by real hidden `Script` and `ProjectConfig` rows so behavior matches normal project generation. Keep run manifests under `data/test-lab/runs`, call production generation/render functions from a focused `pipeline.test_lab` service, and expose a React Test tab with comprehensive grouped controls and run inspection.

**Tech Stack:** FastAPI, SQLModel/SQLite, Pydantic, existing pipeline modules, React 19, TypeScript, Tailwind 4, Remotion render pipeline, pytest, Vite build.

---

## File Structure

- Modify `backend/models/script.py`: add `is_test_lab` to `Script`.
- Modify `backend/database.py`: migrate existing SQLite DBs with `scripts.is_test_lab`.
- Modify `backend/api/scripts.py`: exclude Test Lab scripts from normal project listing.
- Create `backend/pipeline/test_lab.py`: dummy presets, run manifest IO, hidden script creation, cost aggregation, stage orchestration, and history cleanup.
- Create `backend/api/test_lab.py`: API request/response models and endpoints.
- Modify `backend/api/__init__.py`: register the new router.
- Create `backend/tests/test_test_lab.py`: backend unit/API coverage.
- Modify `frontend/src/App.tsx`: add `test-lab` view and nav tab.
- Create `frontend/src/types/testLab.ts`: Test Lab API types.
- Modify `frontend/src/api.ts`: Test Lab API helpers.
- Create `frontend/src/components/test-lab/TestLabPage.tsx`: main page layout and orchestration.
- Create `frontend/src/components/test-lab/TestLabControls.tsx`: grouped settings controls.
- Create `frontend/src/components/test-lab/TestLabRunPanel.tsx`: status, assets, preview, cost, and history.
- Modify `AGENTS.md`: add Test Lab convention after implementation.

---

### Task 1: Hidden Test Lab Script Flag

**Files:**
- Modify: `backend/models/script.py`
- Modify: `backend/database.py`
- Modify: `backend/api/scripts.py`
- Test: `backend/tests/test_test_lab.py`

- [ ] **Step 1: Write failing tests for hidden scripts**

Create `backend/tests/test_test_lab.py` with the shared in-memory app setup and the first tests:

```python
"""Tests for the Test Lab hidden project and run APIs."""

import json
from datetime import datetime, timezone

from fastapi.testclient import TestClient
from sqlmodel import Session, SQLModel, create_engine, select
from sqlmodel.pool import StaticPool


def _build_inmemory_engine():
    import models.api_usage  # noqa: F401
    import models.brand  # noqa: F401
    import models.content_profile  # noqa: F401
    import models.credential  # noqa: F401
    import models.generation_duration  # noqa: F401
    import models.idea  # noqa: F401
    import models.project_config  # noqa: F401
    import models.publish  # noqa: F401
    import models.script  # noqa: F401
    import models.settings  # noqa: F401
    import models.style_preset  # noqa: F401
    import models.trending  # noqa: F401

    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    SQLModel.metadata.create_all(engine)
    return engine


def _setup_app(monkeypatch, tmp_path):
    engine = _build_inmemory_engine()

    from models.brand import BrandProfile

    with Session(engine) as session:
        session.add(BrandProfile(id="default", name="Headless Hero", description="", is_default=True))
        session.commit()

    import api.scripts as scripts_module
    import database
    try:
        import pipeline.test_lab as test_lab_module
    except ModuleNotFoundError:
        test_lab_module = None

    monkeypatch.setattr(database, "engine", engine)
    monkeypatch.setattr(scripts_module, "engine", engine)
    if test_lab_module is not None:
        monkeypatch.setattr(test_lab_module, "DATA_DIR", tmp_path)

    from api import app
    from database import get_session

    def _override_get_session():
        with Session(engine) as session:
            yield session

    app.dependency_overrides[get_session] = _override_get_session
    return engine, app


def _seed_script(engine, script_id: str, *, is_test_lab: bool):
    from models.script import Scene, Script, ScriptContent, Segment

    content = ScriptContent(
        title=f"Script {script_id}",
        segments=[
            Segment(
                name="Segment",
                scenes=[
                    Scene(
                        id=f"{script_id}-scene",
                        narration="A single line of narration.",
                        visual_prompt="A clean flat cartoon scene.",
                        duration_estimate_seconds=6,
                    )
                ],
            )
        ],
    )
    with Session(engine) as session:
        session.add(
            Script(
                id=script_id,
                brand_id="default",
                format_id="youtube-listicle",
                topic_title=f"Script {script_id}",
                topic_description="",
                script_json=content.model_dump_json(),
                is_test_lab=is_test_lab,
                created_at=datetime.now(timezone.utc),
            )
        )
        session.commit()


def test_list_scripts_excludes_test_lab_scripts(monkeypatch, tmp_path):
    engine, app = _setup_app(monkeypatch, tmp_path)
    _seed_script(engine, "normal-1", is_test_lab=False)
    _seed_script(engine, "test-lab-1", is_test_lab=True)

    client = TestClient(app)
    response = client.get("/api/scripts")

    assert response.status_code == 200
    ids = [item["id"] for item in response.json()]
    assert ids == ["normal-1"]

    from database import get_session
    app.dependency_overrides.pop(get_session, None)
```

- [ ] **Step 2: Run test to verify it fails**

Run:

```bash
uv run --project backend pytest backend/tests/test_test_lab.py::test_list_scripts_excludes_test_lab_scripts -q
```

Expected: FAIL because `Script` does not accept `is_test_lab` yet or `/api/scripts` still includes hidden records.

- [ ] **Step 3: Add `is_test_lab` to `Script`**

In `backend/models/script.py`, add the field to the `Script` table:

```python
    is_test_lab: bool = Field(default=False, index=True)
```

Place it near the other table fields, after `format_id` if present.

- [ ] **Step 4: Add SQLite migration**

In `backend/database.py`, call a new migration from `init_db()` after `_migrate_add_format_id_to_scripts()`:

```python
    _migrate_add_is_test_lab_to_scripts()
```

Add this function near the other script migrations:

```python
def _migrate_add_is_test_lab_to_scripts() -> None:
    """Add is_test_lab column to scripts if missing."""
    import sqlite3

    conn = sqlite3.connect(str(_db_path))
    try:
        cursor = conn.execute("PRAGMA table_info(scripts)")
        columns = {row[1] for row in cursor.fetchall()}
        if "is_test_lab" not in columns:
            conn.execute("ALTER TABLE scripts ADD COLUMN is_test_lab INTEGER DEFAULT 0 NOT NULL")
            conn.execute("CREATE INDEX IF NOT EXISTS ix_scripts_is_test_lab ON scripts(is_test_lab)")
            conn.commit()
            logger.info("Migrated: added is_test_lab to scripts")
    finally:
        conn.close()
```

- [ ] **Step 5: Filter normal script list**

In `backend/api/scripts.py`, update `list_scripts`:

```python
@router.get("", response_model=list[ScriptSummary])
def list_scripts(session: Session = Depends(get_session)):
    statement = (
        select(Script)
        .where(Script.is_test_lab == False)  # noqa: E712
        .order_by(Script.created_at.desc())  # type: ignore[arg-type]
    )
    records = session.exec(statement).all()
    return [_build_summary(r, session) for r in records]
```

- [ ] **Step 6: Run test to verify it passes**

Run:

```bash
uv run --project backend pytest backend/tests/test_test_lab.py::test_list_scripts_excludes_test_lab_scripts -q
```

Expected: PASS.

- [ ] **Step 7: Commit hidden script flag**

Run:

```bash
git add backend/models/script.py backend/database.py backend/api/scripts.py backend/tests/test_test_lab.py
git commit -m "Add hidden Test Lab script flag"
```

---

### Task 2: Dummy Presets And Run History Service

**Files:**
- Create: `backend/pipeline/test_lab.py`
- Test: `backend/tests/test_test_lab.py`

- [ ] **Step 1: Write failing tests for presets and history cap**

Append these tests to `backend/tests/test_test_lab.py`:

```python
def test_test_lab_presets_validate_as_script_content():
    from models.script import ScriptContent
    from pipeline.test_lab import TEST_LAB_PRESETS, build_content_from_preset

    assert len(TEST_LAB_PRESETS) == 10
    for preset in TEST_LAB_PRESETS:
        content = build_content_from_preset(preset.id, {})
        validated = ScriptContent.model_validate(content.model_dump())
        assert validated.segments
        assert validated.segments[0].scenes
        assert validated.segments[0].scenes[0].narration
        assert validated.segments[0].scenes[0].visual_prompt


def test_test_lab_history_is_capped_to_20(monkeypatch, tmp_path):
    import pipeline.test_lab as test_lab

    monkeypatch.setattr(test_lab, "DATA_DIR", tmp_path)

    for i in range(25):
        manifest = test_lab.TestLabRunManifest(
            run_id=f"run-{i:02d}",
            script_id=f"script-{i:02d}",
            preset_id="life-scribe",
            status="completed",
            settings={},
        )
        test_lab.save_run_manifest(manifest)

    history = test_lab.list_run_history()

    assert len(history) == 20
    assert history[0].run_id == "run-24"
    assert history[-1].run_id == "run-05"
    assert not (tmp_path / "test-lab" / "runs" / "run-00.json").exists()
```

- [ ] **Step 2: Run tests to verify they fail**

Run:

```bash
uv run --project backend pytest backend/tests/test_test_lab.py::test_test_lab_presets_validate_as_script_content backend/tests/test_test_lab.py::test_test_lab_history_is_capped_to_20 -q
```

Expected: FAIL because `pipeline.test_lab` does not exist.

- [ ] **Step 3: Create `pipeline.test_lab` models and presets**

Create `backend/pipeline/test_lab.py` with:

```python
"""Test Lab support for hidden production-pipeline scene runs."""

from __future__ import annotations

import json
import shutil
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, Field
from sqlmodel import Session, select

from config import DATA_DIR
from models.project_config import ProjectConfig
from models.script import MainCharacter, Scene, Script, ScriptContent, Segment, VisualCanvas
from pipeline.script_helpers import _usage_task_label

MAX_HISTORY = 20
TEST_LAB_DIRNAME = "test-lab"


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


class TestLabPreset(BaseModel):
    id: str
    title: str
    format_id: str = "youtube-listicle"
    segment_name: str
    short_name: str = ""
    narration: str
    tts_narration: str = ""
    visual_prompt: str
    duration_estimate_seconds: float = 7.0
    contains_person: bool = False
    visual_beat: str = "static"
    frame_directives: list[dict] = Field(default_factory=list)
    main_character: MainCharacter | None = None
    tags: list[str] = Field(default_factory=list)


class TestLabAsset(BaseModel):
    kind: Literal["image", "video", "audio", "treatment_asset", "render"]
    label: str
    url: str


class TestLabLogEntry(BaseModel):
    at: str = Field(default_factory=utc_now_iso)
    stage: str
    status: Literal["pending", "running", "completed", "failed"]
    message: str


class TestLabRunManifest(BaseModel):
    run_id: str
    script_id: str
    preset_id: str
    status: Literal["pending", "running", "completed", "failed"] = "pending"
    settings: dict = Field(default_factory=dict)
    assets: list[TestLabAsset] = Field(default_factory=list)
    logs: list[TestLabLogEntry] = Field(default_factory=list)
    render_url: str = ""
    cost_total: float = 0.0
    cost_breakdown: list[dict] = Field(default_factory=list)
    error: str = ""
    started_at: str = Field(default_factory=utc_now_iso)
    completed_at: str | None = None


TEST_LAB_PRESETS: list[TestLabPreset] = [
    TestLabPreset(
        id="life-scribe",
        title="Your Life as a Medieval Scribe",
        format_id="life-as-a",
        segment_name="The First Morning",
        short_name="First Morning",
        narration="The bell rings before sunrise, and your first job is copying the same sentence until your hand stops shaking.",
        visual_prompt="Flat 2D cartoon, a tired medieval scribe at a wooden desk, candlelight, parchment, monastery room, expressive but clean educational style.",
        duration_estimate_seconds=7,
        contains_person=True,
        main_character=MainCharacter(name="Tomas", appearance="young medieval scribe with brown hair, simple robe, ink-stained fingers", vibe="nervous but determined"),
        tags=["life-as-a", "character"],
    ),
    TestLabPreset(
        id="coffee-brain",
        title="How Coffee Changes Your Brain",
        segment_name="The First Sip",
        narration="Within minutes, caffeine starts blocking the sleepy signals your brain has been quietly collecting all morning.",
        visual_prompt="Flat 2D educational cartoon, a giant coffee cup beside a simplified glowing brain diagram, warm kitchen morning light.",
        duration_estimate_seconds=6,
        tags=["science"],
    ),
    TestLabPreset(
        id="mars-minutes",
        title="The First 10 Minutes on Mars",
        segment_name="Dust and Silence",
        narration="The first thing you notice is not the red horizon. It is how quiet everything becomes once the airlock closes behind you.",
        visual_prompt="Flat 2D cartoon astronaut standing near a Mars habitat, red dust, huge empty landscape, cinematic educational composition.",
        duration_estimate_seconds=8,
        contains_person=True,
        tags=["space"],
    ),
    TestLabPreset(
        id="sleep-debt",
        title="Every Level of Sleep Debt",
        format_id="life-as-a",
        segment_name="Two Bad Nights",
        short_name="Two Nights",
        narration="After two bad nights, your brain starts treating simple choices like puzzles with missing pieces.",
        visual_prompt="Flat 2D cartoon, exhausted person staring at floating puzzle pieces over a messy bedroom desk, readable mobile composition.",
        duration_estimate_seconds=7,
        contains_person=True,
        tags=["life-as-a", "health"],
    ),
    TestLabPreset(
        id="airplane-boarding",
        title="Why Planes Board So Slowly",
        segment_name="The Aisle Problem",
        narration="One person reaches up for a bag, and suddenly the entire boarding process becomes a traffic jam with wings.",
        visual_prompt="Flat 2D cartoon airplane aisle, passengers waiting, one traveler lifting a suitcase overhead, clear comedic educational staging.",
        duration_estimate_seconds=7,
        contains_person=True,
        tags=["explainer"],
    ),
    TestLabPreset(
        id="ancient-library",
        title="How Ancient Libraries Worked",
        segment_name="Finding One Scroll",
        narration="Before search bars, finding one answer meant knowing which room, shelf, basket, and scroll keeper to ask.",
        visual_prompt="Flat 2D cartoon ancient library with scroll shelves, a scholar asking a librarian, warm sandstone interior.",
        duration_estimate_seconds=7,
        contains_person=True,
        tags=["history"],
    ),
    TestLabPreset(
        id="ocean-pressure",
        title="What Ocean Pressure Does to You",
        segment_name="The First Descent",
        narration="Every few meters down, the ocean adds another invisible weight, pressing evenly from every direction.",
        visual_prompt="Flat 2D educational cartoon diver descending into deep blue water, pressure rings around suit, simple scientific labels avoided.",
        duration_estimate_seconds=7,
        contains_person=True,
        tags=["science"],
    ),
    TestLabPreset(
        id="money-inflation",
        title="Why Money Loses Value",
        segment_name="The Shrinking Basket",
        narration="Inflation is easiest to see when the same basket of groceries quietly needs more bills every year.",
        visual_prompt="Flat 2D cartoon grocery basket on a counter with bills multiplying around it, clean economic explainer style.",
        duration_estimate_seconds=6,
        tags=["finance"],
    ),
    TestLabPreset(
        id="castle-siege",
        title="How Castle Sieges Really Worked",
        segment_name="Waiting Wins",
        narration="Most sieges were not constant battles. They were long, tense waiting games where food mattered more than swords.",
        visual_prompt="Flat 2D cartoon medieval castle from outside the walls, campfires, supply carts, waiting soldiers, no gore.",
        duration_estimate_seconds=8,
        contains_person=True,
        tags=["history"],
    ),
    TestLabPreset(
        id="phone-addiction",
        title="Every Level of Phone Addiction",
        format_id="life-as-a",
        segment_name="The Quick Check",
        short_name="Quick Check",
        narration="It starts as one quick check, but your thumb already knows the route before your attention catches up.",
        visual_prompt="Flat 2D cartoon person lit by a phone screen in a dark room, notification bubbles, cautionary but not horror.",
        duration_estimate_seconds=7,
        contains_person=True,
        main_character=MainCharacter(name="Maya", appearance="young adult with short black hair, hoodie, tired eyes", vibe="restless and distracted"),
        tags=["life-as-a", "cautionary"],
    ),
]
```

- [ ] **Step 4: Add content builder and manifest helpers**

Continue in `backend/pipeline/test_lab.py`:

```python
def test_lab_root() -> Path:
    root = DATA_DIR / TEST_LAB_DIRNAME
    root.mkdir(parents=True, exist_ok=True)
    return root


def runs_dir() -> Path:
    path = test_lab_root() / "runs"
    path.mkdir(parents=True, exist_ok=True)
    return path


def get_preset(preset_id: str) -> TestLabPreset:
    for preset in TEST_LAB_PRESETS:
        if preset.id == preset_id:
            return preset
    raise ValueError(f"Unknown Test Lab preset: {preset_id}")


def build_content_from_preset(preset_id: str, settings: dict) -> ScriptContent:
    preset = get_preset(preset_id)
    scene_id = settings.get("scene_id") or f"test-scene-{preset.id}"
    scene = Scene(
        id=scene_id,
        narration=settings.get("narration") or preset.narration,
        tts_narration=settings.get("tts_narration") or preset.tts_narration,
        visual_prompt=settings.get("visual_prompt") or preset.visual_prompt,
        duration_estimate_seconds=float(settings.get("duration_estimate_seconds") or preset.duration_estimate_seconds),
        contains_person=bool(settings.get("contains_person", preset.contains_person)),
        visual_beat=settings.get("visual_beat") or preset.visual_beat,
        frame_directives=settings.get("frame_directives") or preset.frame_directives,
        media_source=settings.get("media_source") or "ai",
        visual_treatment=settings.get("visual_treatment") or "full_frame",
        visual_layers=settings.get("visual_layers") or [],
        transition_in=settings.get("transition_in") or "cut",
        fx=settings.get("fx"),
        visual_in_seconds=float(settings.get("visual_in_seconds") or 0.0),
        visual_out_seconds=float(settings.get("visual_out_seconds") or 0.0),
        frame_timings=settings.get("frame_timings"),
    )
    content = ScriptContent(
        title=settings.get("title") or preset.title,
        segments=[
            Segment(
                name=settings.get("segment_name") or preset.segment_name,
                short_name=settings.get("short_name") or preset.short_name,
                scenes=[scene],
            )
        ],
        format_id=settings.get("format_id") or preset.format_id,
        visual_canvas=VisualCanvas(
            background_color=settings.get("visual_canvas", {}).get("background_color", "#F6C54A")
        ),
        segment_timer_enabled=bool(settings.get("segment_timer_enabled", True)),
        subtitle_highlight_enabled=bool(settings.get("subtitle_highlight_enabled", True)),
        ai_video_enabled=(settings.get("media_source") == "ai_video"),
        main_character=settings.get("main_character") or preset.main_character,
    )
    advanced = settings.get("advanced_script")
    if isinstance(advanced, dict):
        merged = content.model_dump()
        merged.update(advanced)
        content = ScriptContent.model_validate(merged)
    return content


def manifest_path(run_id: str) -> Path:
    return runs_dir() / f"{run_id}.json"


def save_run_manifest(manifest: TestLabRunManifest) -> None:
    path = manifest_path(manifest.run_id)
    path.write_text(manifest.model_dump_json(indent=2), encoding="utf-8")
    prune_run_history()


def load_run_manifest(run_id: str) -> TestLabRunManifest:
    path = manifest_path(run_id)
    if not path.is_file():
        raise FileNotFoundError(f"Test Lab run not found: {run_id}")
    return TestLabRunManifest.model_validate_json(path.read_text(encoding="utf-8"))


def list_run_history() -> list[TestLabRunManifest]:
    manifests = [
        TestLabRunManifest.model_validate_json(path.read_text(encoding="utf-8"))
        for path in runs_dir().glob("*.json")
    ]
    return sorted(manifests, key=lambda item: item.started_at, reverse=True)[:MAX_HISTORY]


def prune_run_history() -> None:
    paths = sorted(
        runs_dir().glob("*.json"),
        key=lambda path: path.stat().st_mtime,
        reverse=True,
    )
    for old_path in paths[MAX_HISTORY:]:
        try:
            old = TestLabRunManifest.model_validate_json(old_path.read_text(encoding="utf-8"))
            artifact_dir = runs_dir() / old.run_id
            if artifact_dir.is_dir():
                shutil.rmtree(artifact_dir)
        except Exception:
            pass
        old_path.unlink(missing_ok=True)
```

- [ ] **Step 5: Run tests to verify they pass**

Run:

```bash
uv run --project backend pytest backend/tests/test_test_lab.py::test_test_lab_presets_validate_as_script_content backend/tests/test_test_lab.py::test_test_lab_history_is_capped_to_20 -q
```

Expected: PASS.

- [ ] **Step 6: Commit presets and history service**

Run:

```bash
git add backend/pipeline/test_lab.py backend/tests/test_test_lab.py
git commit -m "Add Test Lab presets and run history"
```

---

### Task 3: Hidden Script Creation And Cost Aggregation

**Files:**
- Modify: `backend/pipeline/test_lab.py`
- Test: `backend/tests/test_test_lab.py`

- [ ] **Step 1: Write failing tests for hidden script creation and cost**

Append:

```python
def test_create_hidden_test_script_creates_script_and_project_config(monkeypatch, tmp_path):
    engine, _app = _setup_app(monkeypatch, tmp_path)

    from models.project_config import ProjectConfig
    from models.script import Script, ScriptContent
    from pipeline.test_lab import create_hidden_test_script

    with Session(engine) as session:
        script_id = create_hidden_test_script(
            session,
            run_id="run-create",
            preset_id="life-scribe",
            settings={
                "eli_enabled": False,
                "style_preset_enabled": True,
                "main_character": {
                    "name": "Test",
                    "appearance": "cartoon explorer",
                    "vibe": "curious",
                },
            },
        )
        session.commit()

        script = session.get(Script, script_id)
        cfg = session.get(ProjectConfig, script_id)

    assert script is not None
    assert script.is_test_lab is True
    assert script.topic_title == "Your Life as a Medieval Scribe"
    assert cfg is not None
    assert cfg.eli_enabled is False
    content = ScriptContent.model_validate_json(script.script_json)
    assert content.main_character is not None
    assert content.main_character.name == "Test"


def test_cost_breakdown_scopes_to_script_id(monkeypatch, tmp_path):
    engine, _app = _setup_app(monkeypatch, tmp_path)

    from models.api_usage import ApiUsage
    from pipeline.test_lab import build_cost_breakdown

    with Session(engine) as session:
        session.add(ApiUsage(script_id="test-script", service="elevenlabs", operation="tts", model="eleven_multilingual_v2", characters=100, cost_estimate=0.01))
        session.add(ApiUsage(script_id="other-script", service="google_ai", operation="image_gen", model="gemini", images=1, cost_estimate=0.03))
        session.add(ApiUsage(script_id="test-script", service="google_ai", operation="image_gen", model="gemini", images=1, cost_estimate=0.02))
        session.commit()

        cost = build_cost_breakdown(session, "test-script")

    assert cost["total_cost"] == 0.03
    assert {item["service"] for item in cost["breakdown"]} == {"elevenlabs", "google_ai"}
```

- [ ] **Step 2: Run tests to verify they fail**

Run:

```bash
uv run --project backend pytest backend/tests/test_test_lab.py::test_create_hidden_test_script_creates_script_and_project_config backend/tests/test_test_lab.py::test_cost_breakdown_scopes_to_script_id -q
```

Expected: FAIL because helpers are missing.

- [ ] **Step 3: Implement hidden script creation**

Add to `backend/pipeline/test_lab.py`:

```python
def create_hidden_test_script(
    session: Session,
    *,
    run_id: str,
    preset_id: str,
    settings: dict,
) -> str:
    from database import get_default_brand_id

    script_id = f"test-lab-{run_id}"
    content = build_content_from_preset(preset_id, settings)
    brand_id = settings.get("brand_id") or get_default_brand_id(session)
    existing = session.get(Script, script_id)
    if existing is None:
        existing = Script(
            id=script_id,
            brand_id=brand_id,
            format_id=content.format_id,
            topic_title=content.title,
            topic_description=f"Test Lab run {run_id}",
            script_json=content.model_dump_json(),
            is_test_lab=True,
        )
    else:
        existing.brand_id = brand_id
        existing.format_id = content.format_id
        existing.topic_title = content.title
        existing.topic_description = f"Test Lab run {run_id}"
        existing.script_json = content.model_dump_json()
        existing.is_test_lab = True
    session.add(existing)

    eli_enabled = bool(settings.get("eli_enabled", True))
    style_preset_enabled = bool(settings.get("style_preset_enabled", True))
    cfg = session.get(ProjectConfig, script_id)
    if cfg is None:
        cfg = ProjectConfig(
            script_id=script_id,
            eli_enabled=eli_enabled,
            style_preset_enabled=style_preset_enabled,
        )
    else:
        cfg.eli_enabled = eli_enabled
        cfg.style_preset_enabled = style_preset_enabled
        cfg.main_character_reference_url = None
    session.add(cfg)
    return script_id
```

- [ ] **Step 4: Implement cost aggregation**

Add to `backend/pipeline/test_lab.py`:

```python
def build_cost_breakdown(session: Session, script_id: str) -> dict:
    from collections import defaultdict
    from models.api_usage import ApiUsage

    rows = session.exec(select(ApiUsage).where(ApiUsage.script_id == script_id)).all()
    grouped = defaultdict(lambda: {
        "task": "",
        "service": "",
        "operation": "",
        "model": "",
        "call_count": 0,
        "input_tokens": 0,
        "output_tokens": 0,
        "characters": 0,
        "images": 0,
        "total_cost": 0.0,
    })

    for row in rows:
        task = _usage_task_label(row.service, row.operation, row.metadata_json)
        key = (task, row.service, row.operation, row.model)
        item = grouped[key]
        item["task"] = task
        item["service"] = row.service
        item["operation"] = row.operation
        item["model"] = row.model
        item["call_count"] += 1
        item["input_tokens"] += row.input_tokens
        item["output_tokens"] += row.output_tokens
        item["characters"] += row.characters
        item["images"] += row.images
        item["total_cost"] += row.cost_estimate

    breakdown = sorted(grouped.values(), key=lambda item: item["total_cost"], reverse=True)
    for item in breakdown:
        item["total_cost"] = round(float(item["total_cost"]), 4)
    return {
        "total_cost": round(sum(item["total_cost"] for item in breakdown), 4),
        "breakdown": breakdown,
    }
```

- [ ] **Step 5: Run tests to verify they pass**

Run:

```bash
uv run --project backend pytest backend/tests/test_test_lab.py::test_create_hidden_test_script_creates_script_and_project_config backend/tests/test_test_lab.py::test_cost_breakdown_scopes_to_script_id -q
```

Expected: PASS.

- [ ] **Step 6: Commit hidden script helpers**

Run:

```bash
git add backend/pipeline/test_lab.py backend/tests/test_test_lab.py
git commit -m "Add Test Lab hidden script helpers"
```

---

### Task 4: Test Lab Run Orchestrator

**Files:**
- Modify: `backend/pipeline/test_lab.py`
- Test: `backend/tests/test_test_lab.py`

- [ ] **Step 1: Write failing tests for phase order and asset classification**

Append:

```python
def test_run_test_lab_phases_uses_selected_order_and_classifies_assets(monkeypatch, tmp_path):
    engine, _app = _setup_app(monkeypatch, tmp_path)

    import pipeline.test_lab as test_lab

    calls = []

    def fake_audio(ctx):
        calls.append("audio")
        ctx.manifest.assets.append(test_lab.TestLabAsset(kind="audio", label="Voiceover", url="/static/projects/test/audio/scene.mp3"))

    def fake_visual(ctx):
        calls.append("visual")
        ctx.manifest.assets.append(test_lab.TestLabAsset(kind="video", label="AI video", url="/static/projects/test/videos/scene.mp4"))
        ctx.manifest.assets.append(test_lab.TestLabAsset(kind="image", label="Anchor image", url="/static/projects/test/images/scene.png"))

    def fake_render(ctx):
        calls.append("render")
        ctx.manifest.render_url = "/static/projects/test/renders/full_youtube.mp4"
        ctx.manifest.assets.append(test_lab.TestLabAsset(kind="render", label="Remotion render", url=ctx.manifest.render_url))

    monkeypatch.setattr(test_lab, "_stage_audio", fake_audio)
    monkeypatch.setattr(test_lab, "_stage_visual", fake_visual)
    monkeypatch.setattr(test_lab, "_stage_treatment_assets", lambda ctx: calls.append("treatment"))
    monkeypatch.setattr(test_lab, "_stage_fx", lambda ctx: calls.append("fx"))
    monkeypatch.setattr(test_lab, "_stage_eli", lambda ctx: calls.append("eli"))
    monkeypatch.setattr(test_lab, "_stage_render", fake_render)

    manifest = test_lab.run_test_lab(
        engine=engine,
        run_id="run-phases",
        preset_id="coffee-brain",
        settings={
            "media_source": "ai_video",
            "stages": {
                "audio": True,
                "visual": True,
                "treatment_assets": True,
                "fx": True,
                "eli": True,
                "render": True,
            },
        },
        job_id=None,
    )

    assert calls == ["audio", "visual", "treatment", "fx", "eli", "render"]
    assert manifest.status == "completed"
    assert [asset.kind for asset in manifest.assets] == ["audio", "video", "image", "render"]
```

- [ ] **Step 2: Run test to verify it fails**

Run:

```bash
uv run --project backend pytest backend/tests/test_test_lab.py::test_run_test_lab_phases_uses_selected_order_and_classifies_assets -q
```

Expected: FAIL because `run_test_lab` and stage functions are missing.

- [ ] **Step 3: Add orchestration context and stage runner**

Add to `backend/pipeline/test_lab.py`:

```python
class TestLabRunContext(BaseModel):
    run_id: str
    script_id: str
    preset_id: str
    settings: dict
    manifest: TestLabRunManifest

    class Config:
        arbitrary_types_allowed = True


def log_stage(manifest: TestLabRunManifest, stage: str, status: str, message: str) -> None:
    manifest.logs.append(TestLabLogEntry(stage=stage, status=status, message=message))
    save_run_manifest(manifest)


def _enabled(settings: dict, stage: str, default: bool = True) -> bool:
    stages = settings.get("stages") or {}
    if stage in stages:
        return bool(stages[stage])
    return default


def run_test_lab(
    *,
    engine,
    run_id: str,
    preset_id: str,
    settings: dict,
    job_id: str | None,
) -> TestLabRunManifest:
    from pipeline.render_jobs import update_job

    manifest = TestLabRunManifest(
        run_id=run_id,
        script_id=f"test-lab-{run_id}",
        preset_id=preset_id,
        status="running",
        settings=settings,
    )
    save_run_manifest(manifest)

    try:
        with Session(engine) as session:
            script_id = create_hidden_test_script(
                session,
                run_id=run_id,
                preset_id=preset_id,
                settings=settings,
            )
            session.commit()
        manifest.script_id = script_id
        ctx = TestLabRunContext(
            run_id=run_id,
            script_id=script_id,
            preset_id=preset_id,
            settings=settings,
            manifest=manifest,
        )
        phase_order = [
            ("character", _stage_character_reference, _enabled(settings, "character", False)),
            ("audio", _stage_audio, _enabled(settings, "audio", True)),
            ("visual", _stage_visual, _enabled(settings, "visual", True)),
            ("treatment_assets", _stage_treatment_assets, _enabled(settings, "treatment_assets", True)),
            ("fx", _stage_fx, _enabled(settings, "fx", False)),
            ("eli", _stage_eli, _enabled(settings, "eli", bool(settings.get("eli_enabled", True)))),
            ("render", _stage_render, _enabled(settings, "render", True)),
        ]
        active = [(name, fn) for name, fn, enabled in phase_order if enabled]
        for index, (name, fn) in enumerate(active):
            if job_id:
                update_job(job_id, progress=index / max(1, len(active)), current_step=f"Running {name}...")
            log_stage(manifest, name, "running", f"Running {name}")
            fn(ctx)
            log_stage(manifest, name, "completed", f"Completed {name}")

        with Session(engine) as session:
            cost = build_cost_breakdown(session, manifest.script_id)
        manifest.cost_total = cost["total_cost"]
        manifest.cost_breakdown = cost["breakdown"]
        manifest.status = "completed"
        manifest.completed_at = utc_now_iso()
        save_run_manifest(manifest)
        if job_id:
            update_job(job_id, progress=1.0, current_step="Complete")
        return manifest
    except Exception as exc:
        manifest.status = "failed"
        manifest.error = str(exc)
        manifest.completed_at = utc_now_iso()
        save_run_manifest(manifest)
        raise
```

- [ ] **Step 4: Implement production-backed stage functions**

Add to `backend/pipeline/test_lab.py`:

```python
def _load_content_for_script(script_id: str) -> ScriptContent:
    from database import engine as db_engine

    with Session(db_engine) as session:
        record = session.get(Script, script_id)
        if not record:
            raise RuntimeError(f"Script not found: {script_id}")
        return ScriptContent.model_validate_json(record.script_json)


def _first_scene(content: ScriptContent) -> Scene:
    return content.segments[0].scenes[0]


def _stage_character_reference(ctx: TestLabRunContext) -> None:
    if ctx.settings.get("eli_enabled", True):
        return
    from database import engine as db_engine
    from models.project_config import update_project_config
    from pipeline.main_character import generate_character_reference

    with Session(db_engine) as session:
        record = session.get(Script, ctx.script_id)
        if not record:
            raise RuntimeError("Test Lab script missing")
        content = ScriptContent.model_validate_json(record.script_json)
        if content.main_character is None:
            raise RuntimeError("Project character mode requires main character details")
        web_path = generate_character_reference(
            script_id=ctx.script_id,
            character=content.main_character,
            force=True,
        )
        update_project_config(session, ctx.script_id, main_character_reference_url=web_path)
        session.commit()
    ctx.manifest.assets.append(TestLabAsset(kind="image", label="Character reference", url=web_path))


def _stage_audio(ctx: TestLabRunContext) -> None:
    from database import engine as db_engine, get_default_brand_id
    from models.brand import BrandProfile
    from pipeline.voiceover import generate_scene_audio

    with Session(db_engine) as session:
        brand = session.get(BrandProfile, get_default_brand_id(session))
        if not brand or not brand.voice_id:
            raise RuntimeError("No voice configured in Settings")
        record = session.get(Script, ctx.script_id)
        if not record:
            raise RuntimeError("Test Lab script missing")
        content = ScriptContent.model_validate_json(record.script_json)
        scene = _first_scene(content)
        narration = scene.tts_narration or scene.narration
        audio_url, duration, word_timestamps, phrase_timestamps = generate_scene_audio(
            scene.id,
            narration,
            brand.voice_id,
            ctx.script_id,
            model_id=ctx.settings.get("voice_model_id", "eleven_multilingual_v2"),
            voice_settings=ctx.settings.get("voice_settings"),
        )
        scene.audio_url = audio_url
        scene.audio_duration_seconds = duration
        scene.word_timestamps = word_timestamps
        scene.phrase_timestamps = phrase_timestamps
        record.script_json = content.model_dump_json()
        session.add(record)
        session.commit()
    ctx.manifest.assets.append(TestLabAsset(kind="audio", label="Voiceover", url=audio_url))


def _stage_visual(ctx: TestLabRunContext) -> None:
    from database import engine as db_engine
    from pipeline.image_gen import generate_scene_image
    from pipeline.video_gen import generate_scene_video

    with Session(db_engine) as session:
        record = session.get(Script, ctx.script_id)
        if not record:
            raise RuntimeError("Test Lab script missing")
        content = ScriptContent.model_validate_json(record.script_json)
        scene = _first_scene(content)
        media_source = ctx.settings.get("media_source", scene.media_source or "ai")
        if media_source == "ai_video":
            video_url, _prompt_used, metadata = generate_scene_video(
                scene_id=scene.id,
                visual_prompt=scene.visual_prompt,
                script_id=ctx.script_id,
                scene_duration_seconds=scene.audio_duration_seconds or scene.duration_estimate_seconds,
                contains_person=scene.contains_person,
            )
            scene.video_url = video_url
            scene.image_url = ""
            scene.visual_source_metadata = metadata
            ctx.manifest.assets.append(TestLabAsset(kind="video", label="AI video", url=video_url))
        else:
            image_url, _prompt_used, metadata = generate_scene_image(
                scene_id=scene.id,
                visual_prompt=scene.visual_prompt,
                script_id=ctx.script_id,
                contains_person=scene.contains_person,
            )
            scene.image_url = image_url
            scene.video_url = ""
            scene.visual_source_metadata = metadata
            ctx.manifest.assets.append(TestLabAsset(kind="image", label="Image", url=image_url))
        record.script_json = content.model_dump_json()
        session.add(record)
        session.commit()


def _stage_treatment_assets(ctx: TestLabRunContext) -> None:
    from database import engine as db_engine
    from pipeline.image_gen import generate_visual_layer_panels

    with Session(db_engine) as session:
        record = session.get(Script, ctx.script_id)
        if not record:
            raise RuntimeError("Test Lab script missing")
        content = ScriptContent.model_validate_json(record.script_json)
        scene = _first_scene(content)
        if scene.visual_treatment not in {"popup_sequence", "flipflop"} or not scene.visual_layers:
            return
        layers = generate_visual_layer_panels(
            scene.id,
            [layer.model_dump() for layer in scene.visual_layers],
            ctx.script_id,
            force=True,
            contains_person=scene.contains_person,
        )
        scene.visual_layers = layers
        record.script_json = content.model_dump_json()
        session.add(record)
        session.commit()
    for layer in layers:
        url = layer.get("image_url") if isinstance(layer, dict) else getattr(layer, "image_url", "")
        if url:
            ctx.manifest.assets.append(TestLabAsset(kind="treatment_asset", label="Treatment asset", url=url))


def _stage_fx(ctx: TestLabRunContext) -> None:
    from database import engine as db_engine
    from pipeline.fx_generator import generate_scene_fx
    from config import FPS

    with Session(db_engine) as session:
        record = session.get(Script, ctx.script_id)
        if not record:
            raise RuntimeError("Test Lab script missing")
        content = ScriptContent.model_validate_json(record.script_json)
        scene = _first_scene(content)
        duration = scene.audio_duration_seconds or scene.duration_estimate_seconds
        payload = {
            "id": scene.id,
            "segment": content.segments[0].name,
            "segment_index": 0,
            "scene_index_in_segment": 0,
            "global_index": 0,
            "is_first_scene": True,
            "is_last_scene": True,
            "is_first_in_segment": True,
            "is_title_card": False,
            "narration": scene.narration,
            "duration_seconds": duration,
            "duration_frames": int(duration * FPS),
            "has_multiple_frames": bool(scene.frame_urls and len(scene.frame_urls) > 1),
        }
        if scene.word_timestamps:
            payload["word_timestamps"] = [w.model_dump() for w in scene.word_timestamps]
        scene.fx = generate_scene_fx(payload)["fx"]
        record.script_json = content.model_dump_json()
        session.add(record)
        session.commit()


def _stage_eli(ctx: TestLabRunContext) -> None:
    if not ctx.settings.get("eli_enabled", True):
        return
    from database import engine as db_engine
    from pipeline.eli_animator import generate_scene_eli

    with Session(db_engine) as session:
        record = session.get(Script, ctx.script_id)
        if not record:
            raise RuntimeError("Test Lab script missing")
        content = ScriptContent.model_validate_json(record.script_json)
        scene = _first_scene(content)
        if scene.contains_person:
            return
        scene.eli_overlay = generate_scene_eli(scene.narration, script_id=ctx.script_id)
        record.script_json = content.model_dump_json()
        session.add(record)
        session.commit()


def _stage_render(ctx: TestLabRunContext) -> None:
    from database import engine as db_engine
    from models.brand import BrandProfile
    from pipeline.remotion_render import render_full_video

    with Session(db_engine) as session:
        record = session.get(Script, ctx.script_id)
        if not record:
            raise RuntimeError("Test Lab script missing")
        content = ScriptContent.model_validate_json(record.script_json)
        brand = session.get(BrandProfile, record.brand_id)
        brand_dict = {"name": brand.name} if brand else {}
    render_url = render_full_video(
        script_id=ctx.script_id,
        content=content,
        title="",
        brand=brand_dict,
    )
    ctx.manifest.render_url = render_url
    ctx.manifest.assets.append(TestLabAsset(kind="render", label="Remotion render", url=render_url))
```

- [ ] **Step 5: Run orchestrator test**

Run:

```bash
uv run --project backend pytest backend/tests/test_test_lab.py::test_run_test_lab_phases_uses_selected_order_and_classifies_assets -q
```

Expected: PASS.

- [ ] **Step 6: Commit run orchestrator**

Run:

```bash
git add backend/pipeline/test_lab.py backend/tests/test_test_lab.py
git commit -m "Add Test Lab run orchestration"
```

---

### Task 5: Test Lab API Router

**Files:**
- Create: `backend/api/test_lab.py`
- Modify: `backend/api/__init__.py`
- Test: `backend/tests/test_test_lab.py`

- [ ] **Step 1: Write failing API tests**

Append:

```python
def test_test_lab_scenes_endpoint_returns_presets(monkeypatch, tmp_path):
    _engine, app = _setup_app(monkeypatch, tmp_path)
    client = TestClient(app)

    response = client.get("/api/test-lab/scenes")

    assert response.status_code == 200
    data = response.json()
    assert len(data["presets"]) == 10
    assert data["presets"][0]["id"]

    from database import get_session
    app.dependency_overrides.pop(get_session, None)


def test_start_test_lab_run_returns_run_and_job(monkeypatch, tmp_path):
    engine, app = _setup_app(monkeypatch, tmp_path)

    import api.test_lab as test_lab_api

    def fake_background(job_id, fn):
        fn()

    monkeypatch.setattr(test_lab_api, "run_in_background", fake_background)

    client = TestClient(app)
    response = client.post(
        "/api/test-lab/runs",
        json={
            "preset_id": "coffee-brain",
            "settings": {
                "stages": {"audio": False, "visual": False, "render": False, "eli": False, "fx": False, "treatment_assets": False},
            },
        },
    )

    assert response.status_code == 200
    body = response.json()
    assert body["run_id"]
    assert body["job_id"]

    history = client.get("/api/test-lab/runs")
    assert history.status_code == 200
    assert history.json()["runs"][0]["preset_id"] == "coffee-brain"

    from database import get_session
    app.dependency_overrides.pop(get_session, None)
```

- [ ] **Step 2: Run API tests to verify they fail**

Run:

```bash
uv run --project backend pytest backend/tests/test_test_lab.py::test_test_lab_scenes_endpoint_returns_presets backend/tests/test_test_lab.py::test_start_test_lab_run_returns_run_and_job -q
```

Expected: FAIL because router does not exist.

- [ ] **Step 3: Create API router**

Create `backend/api/test_lab.py`:

```python
"""Test Lab endpoints for disposable production-pipeline scene runs."""

from __future__ import annotations

import uuid

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from database import engine
from pipeline.render_jobs import create_job, get_job, run_in_background, update_job
from pipeline.test_lab import (
    TEST_LAB_PRESETS,
    TestLabRunManifest,
    clear_test_lab_history,
    list_run_history,
    load_run_manifest,
    run_test_lab,
)

router = APIRouter(prefix="/api/test-lab", tags=["test-lab"])


class TestLabScenesResponse(BaseModel):
    presets: list[dict]


class StartTestLabRunRequest(BaseModel):
    preset_id: str
    settings: dict = Field(default_factory=dict)


class StartTestLabRunResponse(BaseModel):
    run_id: str
    job_id: str


class TestLabHistoryResponse(BaseModel):
    runs: list[TestLabRunManifest]


@router.get("/scenes", response_model=TestLabScenesResponse)
def get_test_lab_scenes() -> TestLabScenesResponse:
    return TestLabScenesResponse(presets=[preset.model_dump() for preset in TEST_LAB_PRESETS])


@router.post("/runs", response_model=StartTestLabRunResponse)
def start_test_lab_run(body: StartTestLabRunRequest) -> StartTestLabRunResponse:
    run_id = uuid.uuid4().hex
    job = create_job(scene_count=1)

    def _run() -> list[str]:
        manifest = run_test_lab(
            engine=engine,
            run_id=run_id,
            preset_id=body.preset_id,
            settings=body.settings,
            job_id=job.id,
        )
        update_job(job.id, status="completed", progress=1.0, current_step="Complete", output_urls=[manifest.run_id])
        return [manifest.run_id]

    run_in_background(job.id, _run)
    return StartTestLabRunResponse(run_id=run_id, job_id=job.id)


@router.get("/runs", response_model=TestLabHistoryResponse)
def get_test_lab_runs() -> TestLabHistoryResponse:
    return TestLabHistoryResponse(runs=list_run_history())


@router.get("/runs/{run_id}", response_model=TestLabRunManifest)
def get_test_lab_run(run_id: str) -> TestLabRunManifest:
    try:
        return load_run_manifest(run_id)
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.get("/runs/status/{job_id}")
def get_test_lab_run_status(job_id: str):
    job = get_job(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    result = job.to_dict()
    if job.status == "completed" and job.output_urls:
        result["run_id"] = job.output_urls[0]
    return result


@router.delete("/runs")
def delete_test_lab_runs():
    clear_test_lab_history()
    return {"ok": True}
```

- [ ] **Step 4: Add clear helper**

Add to `backend/pipeline/test_lab.py`:

```python
def clear_test_lab_history() -> None:
    root = test_lab_root()
    if root.is_dir():
        shutil.rmtree(root)
    runs_dir()
```

- [ ] **Step 5: Register router**

In `backend/api/__init__.py`, import:

```python
from api.test_lab import router as test_lab_router
```

Include it with core routers:

```python
app.include_router(test_lab_router)
```

- [ ] **Step 6: Run API tests**

Run:

```bash
uv run --project backend pytest backend/tests/test_test_lab.py::test_test_lab_scenes_endpoint_returns_presets backend/tests/test_test_lab.py::test_start_test_lab_run_returns_run_and_job -q
```

Expected: PASS.

- [ ] **Step 7: Commit API router**

Run:

```bash
git add backend/api/test_lab.py backend/api/__init__.py backend/pipeline/test_lab.py backend/tests/test_test_lab.py
git commit -m "Add Test Lab API endpoints"
```

---

### Task 6: Frontend API Types And Navigation

**Files:**
- Create: `frontend/src/types/testLab.ts`
- Modify: `frontend/src/api.ts`
- Modify: `frontend/src/App.tsx`
- Create: `frontend/src/components/test-lab/TestLabPage.tsx`

- [ ] **Step 1: Add Test Lab types**

Create `frontend/src/types/testLab.ts`:

```typescript
import type { MainCharacter, SceneFX, VisualLayer, VisualTreatment } from "./script";
import type { ScriptCostBreakdownItem } from "../api";

export interface TestLabPreset {
  id: string;
  title: string;
  format_id: string;
  segment_name: string;
  short_name: string;
  narration: string;
  tts_narration: string;
  visual_prompt: string;
  duration_estimate_seconds: number;
  contains_person: boolean;
  visual_beat: string;
  frame_directives: Array<Record<string, unknown>>;
  main_character: MainCharacter | null;
  tags: string[];
}

export interface TestLabStages {
  character: boolean;
  audio: boolean;
  visual: boolean;
  treatment_assets: boolean;
  fx: boolean;
  eli: boolean;
  render: boolean;
}

export interface TestLabSettings {
  stages: TestLabStages;
  eli_enabled: boolean;
  style_preset_enabled: boolean;
  media_source: "ai" | "ai_video";
  visual_treatment: VisualTreatment;
  visual_layers: VisualLayer[];
  fx?: SceneFX | null;
  title?: string;
  segment_name?: string;
  short_name?: string;
  narration?: string;
  tts_narration?: string;
  visual_prompt?: string;
  duration_estimate_seconds?: number;
  contains_person?: boolean;
  visual_beat?: string;
  transition_in?: "cut" | "fade_black" | "flash_white" | "wipe";
  visual_canvas?: { background_color: string };
  segment_timer_enabled: boolean;
  subtitle_highlight_enabled: boolean;
  main_character?: MainCharacter | null;
  voice_model_id?: string;
  voice_settings?: Record<string, unknown> | null;
  advanced_script?: Record<string, unknown> | null;
}

export interface TestLabAsset {
  kind: "image" | "video" | "audio" | "treatment_asset" | "render";
  label: string;
  url: string;
}

export interface TestLabLogEntry {
  at: string;
  stage: string;
  status: "pending" | "running" | "completed" | "failed";
  message: string;
}

export interface TestLabRun {
  run_id: string;
  script_id: string;
  preset_id: string;
  status: "pending" | "running" | "completed" | "failed";
  settings: Partial<TestLabSettings>;
  assets: TestLabAsset[];
  logs: TestLabLogEntry[];
  render_url: string;
  cost_total: number;
  cost_breakdown: ScriptCostBreakdownItem[];
  error: string;
  started_at: string;
  completed_at?: string | null;
}
```

- [ ] **Step 2: Add API helpers**

In `frontend/src/api.ts`, import types:

```typescript
import type { TestLabPreset, TestLabRun, TestLabSettings } from "./types/testLab";
```

Add helpers near other API helpers:

```typescript
export async function getTestLabPresets(): Promise<TestLabPreset[]> {
  const res = await api.get<{ presets: TestLabPreset[] }>("/api/test-lab/scenes");
  return res.ok ? res.data.presets : [];
}

export async function getTestLabRuns(): Promise<TestLabRun[]> {
  const res = await api.get<{ runs: TestLabRun[] }>("/api/test-lab/runs");
  return res.ok ? res.data.runs : [];
}

export async function getTestLabRun(runId: string): Promise<TestLabRun | null> {
  const res = await api.get<TestLabRun>(`/api/test-lab/runs/${runId}`);
  return res.ok ? res.data : null;
}

export async function startTestLabRun(presetId: string, settings: Partial<TestLabSettings>): Promise<{ run_id: string; job_id: string } | null> {
  const res = await api.post<{ run_id: string; job_id: string }>("/api/test-lab/runs", {
    preset_id: presetId,
    settings,
  });
  return res.ok ? res.data : null;
}

export async function clearTestLabRuns(): Promise<boolean> {
  const res = await api.delete("/api/test-lab/runs");
  return res.ok;
}
```

Add `"/api/test-lab/runs/status/"` to `SILENT_PATHS`.

- [ ] **Step 3: Create page skeleton**

Create `frontend/src/components/test-lab/TestLabPage.tsx`:

```tsx
import { Beaker, Play, RotateCcw } from "lucide-react";
import { useEffect, useMemo, useState } from "react";
import { getTestLabPresets, getTestLabRuns, startTestLabRun } from "../../api";
import type { TestLabPreset, TestLabRun, TestLabSettings } from "../../types/testLab";

const DEFAULT_SETTINGS: TestLabSettings = {
  stages: {
    character: false,
    audio: true,
    visual: true,
    treatment_assets: true,
    fx: false,
    eli: true,
    render: true,
  },
  eli_enabled: true,
  style_preset_enabled: true,
  media_source: "ai",
  visual_treatment: "full_frame",
  visual_layers: [],
  segment_timer_enabled: true,
  subtitle_highlight_enabled: true,
};

export default function TestLabPage() {
  const [presets, setPresets] = useState<TestLabPreset[]>([]);
  const [selectedPresetId, setSelectedPresetId] = useState<string>("");
  const [settings, setSettings] = useState<TestLabSettings>(DEFAULT_SETTINGS);
  const [runs, setRuns] = useState<TestLabRun[]>([]);
  const [activeRun, setActiveRun] = useState<TestLabRun | null>(null);
  const [running, setRunning] = useState(false);

  useEffect(() => {
    getTestLabPresets().then((items) => {
      setPresets(items);
      setSelectedPresetId((current) => current || items[0]?.id || "");
    });
    getTestLabRuns().then(setRuns);
  }, []);

  const selectedPreset = useMemo(
    () => presets.find((preset) => preset.id === selectedPresetId) ?? null,
    [presets, selectedPresetId],
  );

  async function handleRun() {
    if (!selectedPresetId || running) return;
    setRunning(true);
    try {
      const started = await startTestLabRun(selectedPresetId, settings);
      if (!started) return;
      await pollRun(started.job_id, started.run_id);
    } finally {
      setRunning(false);
    }
  }

  async function pollRun(jobId: string, runId: string) {
    for (;;) {
      await new Promise((resolve) => setTimeout(resolve, 1500));
      const status = await fetch(`/api/test-lab/runs/status/${jobId}`).then((res) => res.json());
      const detail = await fetch(`/api/test-lab/runs/${runId}`).then((res) => (res.ok ? res.json() : null));
      if (detail) setActiveRun(detail);
      if (status.status === "completed" || status.status === "failed" || status.status === "cancelled") {
        const nextRuns = await getTestLabRuns();
        setRuns(nextRuns);
        return;
      }
    }
  }

  return (
    <div className="h-full min-h-0 bg-neutral-950 text-neutral-100">
      <div className="flex h-full min-h-0 flex-col">
        <div className="border-b border-neutral-800 px-6 py-4">
          <div className="flex items-center justify-between gap-4">
            <div className="flex items-center gap-3">
              <Beaker className="h-5 w-5 text-violet-300" />
              <div>
                <h1 className="text-lg font-semibold">Test Lab</h1>
                <p className="text-xs text-neutral-500">Run one realistic scene through the real production pipeline.</p>
              </div>
            </div>
            <button
              onClick={handleRun}
              disabled={running || !selectedPreset}
              className="inline-flex items-center gap-2 rounded-md bg-violet-600 px-3 py-2 text-sm font-medium text-white transition-colors hover:bg-violet-500 disabled:cursor-not-allowed disabled:bg-neutral-800 disabled:text-neutral-500"
            >
              {running ? <RotateCcw className="h-4 w-4 animate-spin" /> : <Play className="h-4 w-4" />}
              Generate & Render
            </button>
          </div>
        </div>
        <div className="grid min-h-0 flex-1 grid-cols-[280px_minmax(420px,1fr)_400px] gap-4 overflow-hidden p-4">
          <aside className="min-h-0 overflow-y-auto rounded-lg border border-neutral-800 bg-neutral-900/60 p-3">
            <p className="mb-3 text-xs font-semibold uppercase text-neutral-500">Dummy Scenes</p>
            <div className="space-y-2">
              {presets.map((preset) => (
                <button
                  key={preset.id}
                  onClick={() => setSelectedPresetId(preset.id)}
                  className={`w-full rounded-md border p-3 text-left transition-colors ${
                    selectedPresetId === preset.id
                      ? "border-violet-500 bg-violet-500/15"
                      : "border-neutral-800 bg-neutral-950/50 hover:border-neutral-700"
                  }`}
                >
                  <p className="text-sm font-medium text-neutral-100">{preset.title}</p>
                  <p className="mt-1 line-clamp-2 text-xs text-neutral-500">{preset.narration}</p>
                </button>
              ))}
            </div>
          </aside>
          <section className="min-h-0 overflow-y-auto rounded-lg border border-neutral-800 bg-neutral-900/60 p-4">
            <p className="text-xs font-semibold uppercase text-neutral-500">Settings</p>
            <p className="mt-2 text-sm text-neutral-300">{selectedPreset?.title ?? "Select a scene"}</p>
          </section>
          <aside className="min-h-0 overflow-y-auto rounded-lg border border-neutral-800 bg-neutral-900/60 p-4">
            <p className="text-xs font-semibold uppercase text-neutral-500">Run</p>
            <p className="mt-2 text-sm text-neutral-300">{activeRun?.status ?? "No run selected"}</p>
            <p className="mt-4 text-xs font-semibold uppercase text-neutral-500">History</p>
            <div className="mt-2 space-y-2">
              {runs.map((run) => (
                <button
                  key={run.run_id}
                  onClick={() => setActiveRun(run)}
                  className="w-full rounded-md border border-neutral-800 bg-neutral-950/50 p-2 text-left text-xs text-neutral-300 transition-colors hover:border-neutral-700"
                >
                  {run.preset_id} · {run.status}
                </button>
              ))}
            </div>
          </aside>
        </div>
      </div>
    </div>
  );
}
```

- [ ] **Step 4: Add App nav**

In `frontend/src/App.tsx`:

1. Import `TestTube` and `TestLabPage`.
2. Add `"test-lab"` to `View`.
3. Include `"test-lab"` in `viewPanelClass` overflow-hidden branch.
4. Add a nav button between Developer and Settings:

```tsx
<button
  onClick={() => handleSetView("test-lab")}
  className={`flex items-center gap-1.5 rounded-lg px-3 py-1.5 text-sm transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-violet-500 focus-visible:ring-offset-2 focus-visible:ring-offset-neutral-950 ${
    view === "test-lab"
      ? "bg-violet-500/15 text-violet-300 font-semibold"
      : "text-neutral-500 hover:bg-neutral-800 hover:text-neutral-200"
  }`}
>
  <TestTube className="w-4 h-4" />
  Test
</button>
```

5. Add main panel:

```tsx
<div className={viewPanelClass("test-lab", view)}>
  {visitedViews.has("test-lab") && <TestLabPage />}
</div>
```

- [ ] **Step 5: Run frontend build**

Run:

```bash
npm run build:frontend
```

Expected: PASS.

- [ ] **Step 6: Commit frontend shell**

Run:

```bash
git add frontend/src/types/testLab.ts frontend/src/api.ts frontend/src/App.tsx frontend/src/components/test-lab/TestLabPage.tsx
git commit -m "Add Test Lab frontend shell"
```

---

### Task 7: Settings Controls, Run Panel, Assets, And Cost UI

**Files:**
- Create: `frontend/src/components/test-lab/TestLabControls.tsx`
- Create: `frontend/src/components/test-lab/TestLabRunPanel.tsx`
- Modify: `frontend/src/components/test-lab/TestLabPage.tsx`

- [ ] **Step 1: Create controls component**

Create `frontend/src/components/test-lab/TestLabControls.tsx`:

```tsx
import { HelpCircle } from "lucide-react";
import { Tooltip } from "../ui/Tooltip";
import type { TestLabPreset, TestLabSettings } from "../../types/testLab";

function Help({ text }: { text: string }) {
  return (
    <Tooltip content={text}>
      <HelpCircle className="h-3.5 w-3.5 text-neutral-500" />
    </Tooltip>
  );
}

function FieldLabel({ label, help }: { label: string; help: string }) {
  return (
    <div className="mb-1 flex items-center gap-1.5">
      <span className="text-xs font-medium text-neutral-300">{label}</span>
      <Help text={help} />
    </div>
  );
}

export default function TestLabControls({
  preset,
  settings,
  onChange,
}: {
  preset: TestLabPreset | null;
  settings: TestLabSettings;
  onChange: (settings: TestLabSettings) => void;
}) {
  const set = <K extends keyof TestLabSettings>(key: K, value: TestLabSettings[K]) => {
    onChange({ ...settings, [key]: value });
  };
  const setStage = (key: keyof TestLabSettings["stages"], value: boolean) => {
    onChange({ ...settings, stages: { ...settings.stages, [key]: value } });
  };

  return (
    <div className="space-y-5">
      <section>
        <h2 className="text-sm font-semibold text-neutral-100">Pipeline</h2>
        <div className="mt-3 grid grid-cols-2 gap-2">
          {Object.entries(settings.stages).map(([key, value]) => (
            <label key={key} className="flex items-center justify-between rounded-md border border-neutral-800 bg-neutral-950/50 px-3 py-2 text-xs text-neutral-300">
              <span className="capitalize">{key.replace("_", " ")}</span>
              <input
                type="checkbox"
                checked={value}
                onChange={(event) => setStage(key as keyof TestLabSettings["stages"], event.target.checked)}
                className="accent-violet-500"
              />
            </label>
          ))}
        </div>
      </section>

      <section>
        <h2 className="text-sm font-semibold text-neutral-100">Visual Source</h2>
        <div className="mt-3 grid grid-cols-2 gap-2">
          <button
            type="button"
            onClick={() => set("media_source", "ai")}
            className={`rounded-md border px-3 py-2 text-left text-xs transition-colors ${settings.media_source === "ai" ? "border-violet-500 bg-violet-500/15 text-violet-200" : "border-neutral-800 bg-neutral-950/50 text-neutral-300 hover:border-neutral-700"}`}
          >
            AI image
          </button>
          <button
            type="button"
            onClick={() => set("media_source", "ai_video")}
            className={`rounded-md border px-3 py-2 text-left text-xs transition-colors ${settings.media_source === "ai_video" ? "border-violet-500 bg-violet-500/15 text-violet-200" : "border-neutral-800 bg-neutral-950/50 text-neutral-300 hover:border-neutral-700"}`}
          >
            AI video
          </button>
        </div>
      </section>

      <section>
        <h2 className="text-sm font-semibold text-neutral-100">Character</h2>
        <div className="mt-3 grid grid-cols-2 gap-3">
          <label className="rounded-md border border-neutral-800 bg-neutral-950/50 p-3">
            <FieldLabel label="Eli enabled" help="When on, eligible scenes can generate Eli overlay animation. When off, scene images require a project-specific character reference." />
            <input
              type="checkbox"
              checked={settings.eli_enabled}
              onChange={(event) => set("eli_enabled", event.target.checked)}
              className="accent-violet-500"
            />
          </label>
          <label className="rounded-md border border-neutral-800 bg-neutral-950/50 p-3">
            <FieldLabel label="Style preset" help="When project character mode is active, this controls whether the active house style preset is applied to image prompts." />
            <input
              type="checkbox"
              checked={settings.style_preset_enabled}
              onChange={(event) => set("style_preset_enabled", event.target.checked)}
              className="accent-violet-500"
            />
          </label>
        </div>
      </section>

      <section>
        <h2 className="text-sm font-semibold text-neutral-100">Scene Text</h2>
        <div className="mt-3 space-y-3">
          <label className="block">
            <FieldLabel label="Narration" help="The text sent through the same TTS path used by project scenes, unless a TTS override is provided." />
            <textarea
              value={settings.narration ?? preset?.narration ?? ""}
              onChange={(event) => set("narration", event.target.value)}
              className="h-24 w-full rounded-md border border-neutral-800 bg-neutral-950 px-3 py-2 text-sm text-neutral-100 outline-none transition-colors focus:border-violet-500"
            />
          </label>
          <label className="block">
            <FieldLabel label="Visual prompt" help="The prompt sent to AI image generation or used as the anchor prompt for AI video." />
            <textarea
              value={settings.visual_prompt ?? preset?.visual_prompt ?? ""}
              onChange={(event) => set("visual_prompt", event.target.value)}
              className="h-24 w-full rounded-md border border-neutral-800 bg-neutral-950 px-3 py-2 text-sm text-neutral-100 outline-none transition-colors focus:border-violet-500"
            />
          </label>
        </div>
      </section>

      <section>
        <h2 className="text-sm font-semibold text-neutral-100">Treatment, FX, Canvas</h2>
        <div className="mt-3 grid grid-cols-2 gap-3">
          <label>
            <FieldLabel label="Visual treatment" help="Controls how the generated visual is staged over the global canvas during Remotion render." />
            <select
              value={settings.visual_treatment}
              onChange={(event) => set("visual_treatment", event.target.value as TestLabSettings["visual_treatment"])}
              className="w-full rounded-md border border-neutral-800 bg-neutral-950 px-3 py-2 text-sm text-neutral-100 outline-none transition-colors focus:border-violet-500"
            >
              <option value="full_frame">Full frame</option>
              <option value="popup_sequence">Popup sequence</option>
              <option value="flipflop">Flipflop</option>
            </select>
          </label>
          <label>
            <FieldLabel label="Canvas color" help="The video-level static background color beneath the scene visual." />
            <input
              value={settings.visual_canvas?.background_color ?? "#F6C54A"}
              onChange={(event) => set("visual_canvas", { background_color: event.target.value })}
              className="w-full rounded-md border border-neutral-800 bg-neutral-950 px-3 py-2 text-sm text-neutral-100 outline-none transition-colors focus:border-violet-500"
            />
          </label>
        </div>
      </section>
    </div>
  );
}
```

- [ ] **Step 2: Create run panel**

Create `frontend/src/components/test-lab/TestLabRunPanel.tsx`:

```tsx
import { assetUrl } from "../../api";
import type { ScriptCostBreakdownItem } from "../../api";
import type { TestLabRun } from "../../types/testLab";

function formatCost(cost: number) {
  if (cost === 0) return "$0.00";
  if (cost < 0.01) return `$${cost.toFixed(4)}`;
  return `$${cost.toFixed(2)}`;
}

function formatCostMetrics(item: ScriptCostBreakdownItem) {
  const parts: string[] = [];
  if (item.call_count > 0) parts.push(`${item.call_count} call${item.call_count !== 1 ? "s" : ""}`);
  if (item.images > 0) parts.push(`${item.images} image${item.images !== 1 ? "s" : ""}`);
  if (item.characters > 0) parts.push(`${item.characters.toLocaleString()} chars`);
  if (item.input_tokens + item.output_tokens > 0) {
    parts.push(`${(item.input_tokens + item.output_tokens).toLocaleString()} tok`);
  }
  return parts.join(" · ");
}

export default function TestLabRunPanel({
  activeRun,
  runs,
  onSelectRun,
}: {
  activeRun: TestLabRun | null;
  runs: TestLabRun[];
  onSelectRun: (run: TestLabRun) => void;
}) {
  const renderUrl = activeRun?.render_url ? assetUrl(activeRun.render_url) : "";

  return (
    <div className="space-y-4">
      <section className="overflow-hidden rounded-lg border border-neutral-800 bg-neutral-950/60">
        <div className="border-b border-neutral-800 px-3 py-2 text-xs font-semibold text-neutral-200">Preview</div>
        {renderUrl ? (
          <video src={renderUrl} controls className="aspect-video w-full bg-black" />
        ) : (
          <div className="flex aspect-video items-center justify-center bg-black text-xs text-neutral-600">No render yet</div>
        )}
      </section>

      <section className="rounded-lg border border-neutral-800 bg-neutral-950/60 p-3">
        <div className="flex items-center justify-between">
          <span className="text-xs font-semibold text-neutral-200">Generated Assets</span>
          <span className="text-[11px] text-neutral-500">{activeRun?.assets.length ?? 0} assets</span>
        </div>
        <div className="mt-3 grid grid-cols-2 gap-2">
          {(activeRun?.assets ?? []).map((asset) => (
            <a
              key={`${asset.kind}-${asset.url}`}
              href={assetUrl(asset.url)}
              target="_blank"
              rel="noreferrer"
              className="rounded-md border border-neutral-800 bg-neutral-900 px-2 py-2 text-xs text-neutral-300 transition-colors hover:border-neutral-700"
            >
              <span className="block font-medium text-neutral-100">{asset.label}</span>
              <span className="mt-1 block text-neutral-500">{asset.kind.replace("_", " ")}</span>
            </a>
          ))}
        </div>
      </section>

      <section className="overflow-hidden rounded-lg border border-neutral-800 bg-neutral-950/60">
        <div className="flex items-center justify-between border-b border-neutral-800 px-3 py-2">
          <span className="text-xs font-semibold text-neutral-200">Cost breakdown</span>
          <span className="font-mono text-xs text-emerald-300">{formatCost(activeRun?.cost_total ?? 0)}</span>
        </div>
        <div className="max-h-56 overflow-y-auto py-1">
          {(activeRun?.cost_breakdown ?? []).length > 0 ? (
            activeRun!.cost_breakdown.map((item) => (
              <div key={`${item.task}-${item.service}-${item.operation}-${item.model}`} className="px-3 py-2 text-xs">
                <div className="flex items-start justify-between gap-3">
                  <div className="min-w-0">
                    <p className="truncate font-medium text-neutral-100">{item.task}</p>
                    <p className="mt-0.5 truncate text-[11px] text-neutral-500">{[item.service, item.model].filter(Boolean).join(" · ")}</p>
                    <p className="mt-1 text-[11px] text-neutral-500">{formatCostMetrics(item)}</p>
                  </div>
                  <span className="shrink-0 font-mono text-emerald-300">{formatCost(item.total_cost)}</span>
                </div>
              </div>
            ))
          ) : (
            <div className="px-3 py-5 text-center text-xs text-neutral-500">No tracked API usage yet.</div>
          )}
        </div>
      </section>

      <section className="rounded-lg border border-neutral-800 bg-neutral-950/60 p-3">
        <p className="text-xs font-semibold text-neutral-200">Stage log</p>
        <div className="mt-2 max-h-40 space-y-1 overflow-y-auto">
          {(activeRun?.logs ?? []).map((log, index) => (
            <div key={`${log.at}-${index}`} className="text-[11px] text-neutral-400">
              <span className="text-neutral-500">{log.stage}</span> · {log.message}
            </div>
          ))}
        </div>
      </section>

      <section className="rounded-lg border border-neutral-800 bg-neutral-950/60 p-3">
        <p className="text-xs font-semibold text-neutral-200">Last 20 runs</p>
        <div className="mt-2 space-y-2">
          {runs.map((run) => (
            <button
              key={run.run_id}
              onClick={() => onSelectRun(run)}
              className="w-full rounded-md border border-neutral-800 bg-neutral-900 px-2 py-2 text-left text-xs text-neutral-300 transition-colors hover:border-neutral-700"
            >
              <span className="block font-medium text-neutral-100">{run.preset_id}</span>
              <span className="mt-0.5 block text-neutral-500">{run.status} · {formatCost(run.cost_total)}</span>
            </button>
          ))}
        </div>
      </section>
    </div>
  );
}
```

- [ ] **Step 3: Wire components into page**

In `TestLabPage.tsx`, import:

```tsx
import TestLabControls from "./TestLabControls";
import TestLabRunPanel from "./TestLabRunPanel";
```

Replace the current middle section content with:

```tsx
<TestLabControls preset={selectedPreset} settings={settings} onChange={setSettings} />
```

Replace the current right aside content with:

```tsx
<TestLabRunPanel activeRun={activeRun} runs={runs} onSelectRun={setActiveRun} />
```

- [ ] **Step 4: Fix direct fetch URL in polling**

In `TestLabPage.tsx`, replace direct `fetch` calls in `pollRun` with `api.get` by importing default `api`:

```tsx
import api, { getTestLabPresets, getTestLabRun, getTestLabRuns, startTestLabRun } from "../../api";
```

Use:

```tsx
const status = await api.get<{ status: string }>(`/api/test-lab/runs/status/${jobId}`);
const detail = await getTestLabRun(runId);
if (detail) setActiveRun(detail);
if (!status.ok || ["completed", "failed", "cancelled"].includes(status.data.status)) {
  const nextRuns = await getTestLabRuns();
  setRuns(nextRuns);
  return;
}
```

- [ ] **Step 5: Run frontend build**

Run:

```bash
npm run build:frontend
```

Expected: PASS.

- [ ] **Step 6: Commit Test Lab UI**

Run:

```bash
git add frontend/src/components/test-lab/TestLabControls.tsx frontend/src/components/test-lab/TestLabRunPanel.tsx frontend/src/components/test-lab/TestLabPage.tsx
git commit -m "Build Test Lab controls and run panel"
```

---

### Task 8: Documentation And Full Verification

**Files:**
- Modify: `AGENTS.md`

- [ ] **Step 1: Update AGENTS.md convention**

Add under `Key Patterns`:

```markdown
- **Test Lab mirrors production behavior**: The Test tab uses hidden real `Script` and `ProjectConfig` records plus the same production pipeline functions as normal projects. Keep Test Lab records out of project lists/dashboards, persist only the last 20 run manifests under `data/test-lab/runs`, and do not reintroduce removed stock photo, gameplay video, or user-upload media paths into Test Lab settings.
```

- [ ] **Step 2: Run backend Test Lab tests**

Run:

```bash
uv run --project backend pytest backend/tests/test_test_lab.py -q
```

Expected: PASS.

- [ ] **Step 3: Run relevant existing backend tests**

Run:

```bash
uv run --project backend pytest backend/tests/test_project_config_api.py backend/tests/test_media_source_dispatch.py backend/tests/test_media_analysis_flags.py -q
```

Expected: PASS.

- [ ] **Step 4: Run frontend build**

Run:

```bash
npm run build:frontend
```

Expected: PASS.

- [ ] **Step 5: Run full backend test suite**

Run:

```bash
npm run test:backend -- -q
```

Expected: PASS.

- [ ] **Step 6: Start app for manual UI verification**

Run:

```bash
npm run dev
```

Open the app and verify:

- `Test` appears between `Developer` and `Settings`.
- Ten dummy scenes load.
- Render stage is on by default.
- Stock photo, gameplay video, and upload settings are absent.
- Tooltips appear on regular settings.
- Starting a low-stage run with all expensive stages off creates a history item.
- Selecting history reloads run detail.

- [ ] **Step 7: Commit docs and final fixes**

Run:

```bash
git add AGENTS.md
git commit -m "Document Test Lab production behavior"
```

If verification required code fixes, include those changed files in the same commit only if they directly fix the Test Lab implementation.

---

## Final Completion Loop

After implementation is complete:

- [ ] Run `git status --short` and confirm only intentional Test Lab changes remain.
- [ ] Run required verification commands from Task 8.
- [ ] Follow the repository auto-commit rule from `AGENTS.md`: stage relevant files, commit, push to `main`, dispatch delegated code review, fix every finding, and repeat until LGTM.
