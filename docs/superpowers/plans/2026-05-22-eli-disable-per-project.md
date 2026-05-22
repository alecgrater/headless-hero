# Eli Disable Per Project Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make Eli optionally disable-able per project. When disabled, the pipeline picks a topic-specific main character, generates a Gemini reference image, and chains it into scenes that include a person — replacing Eli's reference for that project.

**Architecture:** New `ProjectConfig` SQLModel (per-script row holding `eli_enabled` + `main_character_reference_url`). Structured `main_character` lives in `script_json` blob. Existing `Scene.contains_person` flag is reused — `image_gen.py` swaps the chained reference image based on `ProjectConfig.eli_enabled`. Toggle exposed at idea-pick time, locked at script generation. Header badge + disabled "Add Eli" affordances communicate state. Existing projects (no `ProjectConfig` row) default to `eli_enabled=True` — behavior preserved.

**Tech Stack:** Python 3.12 + FastAPI + SQLModel + SQLite (backend), React 19 + TypeScript + Tailwind 4 + Vite (frontend), Gemini 2.5 (image gen), pytest (backend tests).

**Spec deviation note:** Spec proposed a new `Scene.include_main_character` field. During implementation context exploration, we discovered `Scene.contains_person` already exists and `image_gen.py` already conditionally chains a character reference when it's true. Reusing `contains_person` (and updating its semantics from "scene contains Eli" to "scene contains the project's recurring character") keeps the data model thinner. The scriptwriter is taught to set `contains_person` for scenes that should feature the main character when `eli_enabled=False`.

---

## Phase 1 — Backend Foundation

### Task 1: ProjectConfig model + helpers

**Files:**
- Create: `backend/models/project_config.py`
- Modify: `backend/database.py` (import the new model so `init_db` registers the table)
- Test: `backend/tests/test_project_config.py`

- [ ] **Step 1: Write the failing test**

```python
# backend/tests/test_project_config.py
from sqlmodel import Session, SQLModel, create_engine
from models.project_config import ProjectConfig, get_or_create_project_config, get_project_config


def _make_engine():
    engine = create_engine("sqlite://")
    SQLModel.metadata.create_all(engine)
    return engine


def test_get_project_config_missing_returns_default():
    """Legacy projects with no row return a default with eli_enabled=True."""
    engine = _make_engine()
    with Session(engine) as session:
        cfg = get_project_config(session, "missing-script")
    assert cfg.eli_enabled is True
    assert cfg.script_id == "missing-script"
    assert cfg.main_character_reference_url is None


def test_get_or_create_project_config_persists_row():
    engine = _make_engine()
    with Session(engine) as session:
        cfg = get_or_create_project_config(session, "abc", eli_enabled=False)
        session.commit()
    with Session(engine) as session:
        loaded = get_project_config(session, "abc")
    assert loaded.eli_enabled is False
    assert loaded.script_id == "abc"


def test_get_or_create_idempotent():
    engine = _make_engine()
    with Session(engine) as session:
        get_or_create_project_config(session, "abc", eli_enabled=False)
        session.commit()
    with Session(engine) as session:
        # Calling again does not overwrite
        cfg = get_or_create_project_config(session, "abc", eli_enabled=True)
        session.commit()
    with Session(engine) as session:
        loaded = get_project_config(session, "abc")
    assert loaded.eli_enabled is False
```

- [ ] **Step 2: Run the test to confirm it fails**

Run: `cd backend && uv run pytest tests/test_project_config.py -v`
Expected: ImportError — `models.project_config` does not exist.

- [ ] **Step 3: Create the model**

```python
# backend/models/project_config.py
from datetime import datetime, timezone

from sqlmodel import Field, Session, SQLModel, select


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


class ProjectConfig(SQLModel, table=True):
    """Per-project configuration. One row per script.

    Missing rows are treated as the default (Eli enabled) so projects created
    before this feature shipped continue to behave identically.
    """

    __tablename__ = "project_config"

    script_id: str = Field(primary_key=True, foreign_key="script.id")
    eli_enabled: bool = Field(default=True)
    main_character_reference_url: str | None = Field(default=None)
    created_at: datetime = Field(default_factory=_utcnow)
    updated_at: datetime = Field(default_factory=_utcnow)


def get_project_config(session: Session, script_id: str) -> ProjectConfig:
    """Return the persisted ProjectConfig or a synthetic default for missing rows."""
    row = session.exec(
        select(ProjectConfig).where(ProjectConfig.script_id == script_id)
    ).first()
    if row is not None:
        return row
    return ProjectConfig(script_id=script_id, eli_enabled=True)


def get_or_create_project_config(
    session: Session, script_id: str, *, eli_enabled: bool
) -> ProjectConfig:
    """Insert a config row if missing, else return the existing row unchanged."""
    existing = session.exec(
        select(ProjectConfig).where(ProjectConfig.script_id == script_id)
    ).first()
    if existing is not None:
        return existing
    row = ProjectConfig(script_id=script_id, eli_enabled=eli_enabled)
    session.add(row)
    return row


def update_project_config(
    session: Session,
    script_id: str,
    *,
    main_character_reference_url: str | None = None,
) -> ProjectConfig:
    """Update mutable fields on an existing ProjectConfig. Raises if missing."""
    row = session.exec(
        select(ProjectConfig).where(ProjectConfig.script_id == script_id)
    ).first()
    if row is None:
        raise ValueError(f"ProjectConfig not found for script_id={script_id}")
    if main_character_reference_url is not None:
        row.main_character_reference_url = main_character_reference_url
    row.updated_at = _utcnow()
    session.add(row)
    return row
```

- [ ] **Step 4: Register the model with `init_db`**

Modify `backend/database.py`. At the top with the other model imports (search for an existing model import like `from models.script import Script`), add:

```python
from models.project_config import ProjectConfig  # noqa: F401  -- registers table
```

If there is no existing model import in `database.py`, place it directly above the `init_db` function definition.

- [ ] **Step 5: Run the test to confirm it passes**

Run: `cd backend && uv run pytest tests/test_project_config.py -v`
Expected: 3 passed.

- [ ] **Step 6: Commit**

```bash
git add backend/models/project_config.py backend/database.py backend/tests/test_project_config.py
git commit -m "Add ProjectConfig model with default-fallback helpers"
```

---

### Task 2: Add `eli_enabled_default` setting key

**Files:**
- Modify: `backend/api/settings.py`
- Test: `backend/tests/test_eli_enabled_default_setting.py`

- [ ] **Step 1: Write the failing test**

```python
# backend/tests/test_eli_enabled_default_setting.py
from api.settings import ALLOWED_KEYS, _DEFAULTS, _PLAINTEXT_KEYS


def test_eli_enabled_default_is_allowed():
    assert "ELI_ENABLED_DEFAULT" in ALLOWED_KEYS


def test_eli_enabled_default_has_default_true():
    assert _DEFAULTS.get("ELI_ENABLED_DEFAULT") == "true"


def test_eli_enabled_default_is_plaintext():
    assert "ELI_ENABLED_DEFAULT" in _PLAINTEXT_KEYS
```

- [ ] **Step 2: Run the test to confirm it fails**

Run: `cd backend && uv run pytest tests/test_eli_enabled_default_setting.py -v`
Expected: 3 failing assertions.

- [ ] **Step 3: Add the key**

In `backend/api/settings.py`:
- Add `"ELI_ENABLED_DEFAULT",` to `ALLOWED_KEYS` (alongside other plaintext bool flags such as `HOOK_REFINEMENT_ENABLED`).
- Add `"ELI_ENABLED_DEFAULT",` to `_PLAINTEXT_KEYS`.
- Add `"ELI_ENABLED_DEFAULT": "true",` to `_DEFAULTS`.

- [ ] **Step 4: Run the test to confirm it passes**

Run: `cd backend && uv run pytest tests/test_eli_enabled_default_setting.py -v`
Expected: 3 passed.

- [ ] **Step 5: Commit**

```bash
git add backend/api/settings.py backend/tests/test_eli_enabled_default_setting.py
git commit -m "Add ELI_ENABLED_DEFAULT app setting"
```

---

### Task 3: Wire `eli_enabled` through script-generation request

**Files:**
- Modify: `backend/models/script.py` (add field to `GenerateScriptRequest`)
- Modify: `backend/api/scripts.py` (read field, write `ProjectConfig`)
- Test: `backend/tests/test_script_generation_eli_flag.py`

- [ ] **Step 1: Add the field to the request model**

In `backend/models/script.py`, in `GenerateScriptRequest` (around line 183–195):

```python
    eli_enabled: bool = PydanticField(
        default=True,
        description="Whether Eli is enabled for this project. False switches to per-project main character.",
    )
```

Place it after `stock_photo_enabled`.

- [ ] **Step 2: Write the failing integration test**

```python
# backend/tests/test_script_generation_eli_flag.py
from sqlmodel import Session, select

from database import engine
from models.project_config import ProjectConfig


def test_project_config_row_written_with_eli_enabled_false(monkeypatch):
    """When script gen completes with eli_enabled=False, a ProjectConfig row exists."""
    from api import scripts as scripts_module

    captured: dict = {}

    def fake_run(job_id, fn, *args, **kwargs):
        # Run synchronously so we can assert post-state.
        fn(*args, **kwargs)

    monkeypatch.setattr(scripts_module, "run_in_background", fake_run)

    # Stub generate_script to avoid hitting Claude.
    from pipeline import scriptwriter

    def fake_generate_script(**kwargs):
        from models.script import ScriptContent, Segment

        return ScriptContent(title="t", segments=[Segment(id="s1", title="x", scenes=[])])

    monkeypatch.setattr(scriptwriter, "generate_script", fake_generate_script)
    monkeypatch.setattr(scripts_module, "generate_script", fake_generate_script)

    from fastapi.testclient import TestClient
    from api import app

    client = TestClient(app)
    res = client.post(
        "/api/scripts/generate",
        json={
            "topic": "t",
            "format_id": "youtube-listicle",
            "eli_enabled": False,
        },
    )
    assert res.status_code == 200
    job_id = res.json()["job_id"]
    captured["job_id"] = job_id

    # Find the most recent ProjectConfig row — there should be exactly one with eli_enabled=False.
    with Session(engine) as session:
        rows = session.exec(
            select(ProjectConfig).where(ProjectConfig.eli_enabled == False)  # noqa: E712
        ).all()
    assert any(r for r in rows), "ProjectConfig row with eli_enabled=False not written"
```

- [ ] **Step 3: Run the test to confirm it fails**

Run: `cd backend && uv run pytest tests/test_script_generation_eli_flag.py -v`
Expected: FAIL — no ProjectConfig row written.

- [ ] **Step 4: Update `_run_generation` to persist `ProjectConfig`**

In `backend/api/scripts.py`, find the `_run_generation` function (line ~527). The function signature receives args from the endpoint — extend it to receive `eli_enabled`. The endpoint currently builds a closure or passes args; add `eli_enabled` to that path.

Concretely, in the `generate` endpoint (around line 468–500), where it currently passes generation args into `_run_generation`, also pass `body.eli_enabled`. Inside `_run_generation`, after the `bg_session.add(record); bg_session.commit()` block (around line 568), add:

```python
            from models.project_config import get_or_create_project_config

            get_or_create_project_config(
                bg_session, script_id, eli_enabled=eli_enabled
            )
            bg_session.commit()
```

If the endpoint uses `functools.partial` or kwargs to thread args into the background job, add `eli_enabled=body.eli_enabled` there.

- [ ] **Step 5: Run the test to confirm it passes**

Run: `cd backend && uv run pytest tests/test_script_generation_eli_flag.py -v`
Expected: PASS.

- [ ] **Step 6: Commit**

```bash
git add backend/models/script.py backend/api/scripts.py backend/tests/test_script_generation_eli_flag.py
git commit -m "Persist ProjectConfig row at script generation with eli_enabled flag"
```

---

## Phase 2 — Backend Main Character Generation

### Task 4: Add `main_character` to `ScriptContent`

**Files:**
- Modify: `backend/models/script.py`
- Test: `backend/tests/test_main_character_model.py`

- [ ] **Step 1: Write the failing test**

```python
# backend/tests/test_main_character_model.py
from models.script import MainCharacter, ScriptContent


def test_main_character_has_required_fields():
    char = MainCharacter(
        name="Maya",
        appearance="dark hair, leather jacket, late 30s, weathered face",
        vibe="grizzled detective with dry humor",
    )
    assert char.name == "Maya"


def test_script_content_main_character_optional():
    content = ScriptContent(title="t", segments=[])
    assert content.main_character is None


def test_script_content_main_character_serializes():
    char = MainCharacter(name="A", appearance="b", vibe="c")
    content = ScriptContent(title="t", segments=[], main_character=char)
    dumped = content.model_dump()
    assert dumped["main_character"]["name"] == "A"
```

- [ ] **Step 2: Run the test to confirm it fails**

Run: `cd backend && uv run pytest tests/test_main_character_model.py -v`
Expected: ImportError — `MainCharacter` not defined.

- [ ] **Step 3: Add the model**

In `backend/models/script.py`, near the other Pydantic blocks (above `ScriptContent`):

```python
class MainCharacter(BaseModel):
    name: str
    appearance: str
    vibe: str = ""
```

In `ScriptContent` (lines 134–161), add:

```python
    main_character: MainCharacter | None = None
```

Place it next to `eli_position` so character/host fields are co-located.

- [ ] **Step 4: Run the test to confirm it passes**

Run: `cd backend && uv run pytest tests/test_main_character_model.py -v`
Expected: 3 passed.

- [ ] **Step 5: Commit**

```bash
git add backend/models/script.py backend/tests/test_main_character_model.py
git commit -m "Add MainCharacter model and ScriptContent.main_character field"
```

---

### Task 5: Augment scriptwriter prompt when `eli_enabled=False`

**Files:**
- Modify: `backend/pipeline/scriptwriter.py`
- Test: `backend/tests/test_scriptwriter_eli_disabled.py`

- [ ] **Step 1: Write the failing test**

```python
# backend/tests/test_scriptwriter_eli_disabled.py
from pipeline.scriptwriter import build_main_character_instructions


def test_main_character_instructions_present():
    text = build_main_character_instructions()
    # Must instruct Claude to output a main_character block
    assert "main_character" in text
    # Must instruct Claude to set contains_person on relevant scenes
    assert "contains_person" in text
    # Must say Eli is disabled
    assert "Eli" in text


def test_main_character_instructions_short_enough_to_inject():
    text = build_main_character_instructions()
    # Sanity: not absurdly long (keeps prompt token budget reasonable)
    assert len(text) < 3000
```

- [ ] **Step 2: Run the test to confirm it fails**

Run: `cd backend && uv run pytest tests/test_scriptwriter_eli_disabled.py -v`
Expected: ImportError — `build_main_character_instructions` not defined.

- [ ] **Step 3: Add the prompt builder + plumb `eli_enabled` through `generate_script`**

In `backend/pipeline/scriptwriter.py`:

Add this function near the top (after `BASE_SYSTEM_PROMPT = SCRIPT_SYSTEM.template`):

```python
def build_main_character_instructions() -> str:
    """Instructions appended to the system prompt when Eli is disabled.

    Tells Claude to invent one project-wide main character and to set
    contains_person=true on scenes where that character would naturally appear.
    """
    return (
        "\n\n## Main Character (Eli is disabled for this project)\n"
        "Invent ONE recurring main character that fits this video's topic. "
        "Output a top-level `main_character` object with three fields:\n"
        "  - name: the character's name\n"
        "  - appearance: detailed visual description (face, hair, build, "
        "    clothing, distinguishing features) — written so an image "
        "    generator could draw them consistently\n"
        "  - vibe: 1-2 sentences on personality / energy\n\n"
        "For each scene, set `contains_person: true` ONLY when this main "
        "character should appear in that scene's visual. Set "
        "`contains_person: false` for landscapes, abstract concepts, "
        "object close-ups, or any shot where forcing a person in would "
        "feel awkward. Aim for a balance — not every scene needs a "
        "person.\n"
    )
```

Modify `generate_script` (around line 198) to accept `eli_enabled: bool = True`:

```python
def generate_script(
    topic: str,
    description: str = "",
    brand_context: str = "",
    animated_scene_count: int = 5,
    brand: dict | None = None,
    model: str | None = None,
    segmented: bool = False,
    cold_open_text: str | None = None,
    progress_callback: Callable[[int, int, str], None] | None = None,
    gameplay_enabled: bool = False,
    stock_photo_enabled: bool = False,
    script_id: str | None = None,
    format_id: str = "youtube-listicle",
    eli_enabled: bool = True,
) -> ScriptContent:
```

Inside the function, after the base system prompt is composed but before the Claude call, conditionally append:

```python
    if not eli_enabled:
        system_prompt = system_prompt + build_main_character_instructions()
```

(Identify the local variable holding the assembled system prompt — the existing code pieces it together from `BASE_SYSTEM_PROMPT` plus format-specific blocks. Append after all other blocks.)

- [ ] **Step 4: Plumb `eli_enabled` through `_run_generation`**

In `backend/api/scripts.py`, in `_run_generation`, pass `eli_enabled=eli_enabled` into the `generate_script(...)` call (lines 537–551).

- [ ] **Step 5: Run the test to confirm it passes**

Run: `cd backend && uv run pytest tests/test_scriptwriter_eli_disabled.py -v`
Expected: 2 passed.

- [ ] **Step 6: Commit**

```bash
git add backend/pipeline/scriptwriter.py backend/api/scripts.py backend/tests/test_scriptwriter_eli_disabled.py
git commit -m "Augment scriptwriter prompt with main character instructions when Eli is disabled"
```

---

### Task 6: Main character pipeline module

**Files:**
- Create: `backend/pipeline/main_character.py`
- Test: `backend/tests/test_main_character_pipeline.py`

- [ ] **Step 1: Write the failing test**

```python
# backend/tests/test_main_character_pipeline.py
from pathlib import Path
from unittest.mock import patch

from models.script import MainCharacter
from pipeline.main_character import (
    build_reference_prompt,
    character_reference_path,
    generate_character_reference,
)


def test_build_reference_prompt_uses_all_fields():
    char = MainCharacter(
        name="Sam",
        appearance="tall, red beard, flannel shirt",
        vibe="calm woodworker",
    )
    prompt = build_reference_prompt(char)
    assert "Sam" in prompt
    assert "red beard" in prompt
    assert "calm" in prompt
    # Must enforce neutral framing for a reference image
    assert "neutral" in prompt.lower() or "plain" in prompt.lower()


def test_character_reference_path_is_per_project():
    p = character_reference_path("script-abc")
    assert "script-abc" in str(p)
    assert p.name == "reference.png"


def test_generate_character_reference_writes_file_and_returns_web_path(tmp_path, monkeypatch):
    monkeypatch.setenv("HH_DATA_DIR", str(tmp_path))

    # Re-import so DATA_DIR picks up tmp path.
    import importlib

    import config

    importlib.reload(config)
    import pipeline.main_character as mc

    importlib.reload(mc)

    fake_temp = tmp_path / "fake_gemini_output.png"
    fake_temp.write_bytes(b"\x89PNG fake")

    with patch.object(mc, "_call_image_generator", return_value=str(fake_temp)):
        web_path = mc.generate_character_reference(
            script_id="script-xyz",
            character=MainCharacter(name="x", appearance="y", vibe="z"),
        )

    assert web_path.startswith("/static/projects/script-xyz/character/")
    target = tmp_path / "projects" / "script-xyz" / "character" / "reference.png"
    assert target.exists()
```

- [ ] **Step 2: Run the test to confirm it fails**

Run: `cd backend && uv run pytest tests/test_main_character_pipeline.py -v`
Expected: ImportError.

- [ ] **Step 3: Implement the module**

```python
# backend/pipeline/main_character.py
"""Main character reference image generation.

Used when ProjectConfig.eli_enabled is False. Produces a single canonical
reference image for the project's main character and persists it to
data/projects/{script_id}/character/reference.png.
"""

from __future__ import annotations

import logging
import shutil
from pathlib import Path

from config import DATA_DIR, IMAGE_HEIGHT, IMAGE_WIDTH
from integrations.google_image_client import generate_image
from models.script import MainCharacter

logger = logging.getLogger(__name__)


def character_reference_path(script_id: str) -> Path:
    """Absolute path to the persisted reference image for a script."""
    return DATA_DIR / "projects" / script_id / "character" / "reference.png"


def character_reference_web_path(script_id: str) -> str:
    """The /static path the frontend uses to load the reference."""
    return f"/static/projects/{script_id}/character/reference.png"


def build_reference_prompt(character: MainCharacter) -> str:
    """Compose the Gemini prompt for the canonical reference image."""
    return (
        f"Cinematic character reference portrait of {character.name}.\n"
        f"Appearance: {character.appearance}\n"
        f"Personality: {character.vibe}\n\n"
        "Chest-up framing. Centered. Direct lighting from front-left. "
        "Plain neutral light gray background. No props in hands. "
        "Mouth closed, neutral expression. "
        "Photorealistic, cinematic film still aesthetic, shallow depth of field. "
        "16:9 aspect ratio."
    )


def _call_image_generator(prompt: str, script_id: str) -> str:
    """Wrapper around generate_image() so tests can patch a single seam."""
    return generate_image(
        prompt=prompt,
        width=IMAGE_WIDTH,
        height=IMAGE_HEIGHT,
        script_id=script_id,
    )


def generate_character_reference(
    *, script_id: str, character: MainCharacter, force: bool = False
) -> str:
    """Generate the canonical reference image and persist it.

    Returns the web-relative path (suitable for ProjectConfig.main_character_reference_url).
    Skips regeneration if the file already exists and force is False.
    """
    target = character_reference_path(script_id)
    if target.exists() and not force:
        logger.info("Reusing existing main character reference at %s", target)
        return character_reference_web_path(script_id)

    target.parent.mkdir(parents=True, exist_ok=True)
    prompt = build_reference_prompt(character)
    logger.info("Generating main character reference for script_id=%s", script_id)
    temp_path = _call_image_generator(prompt, script_id)
    shutil.copyfile(temp_path, target)
    return character_reference_web_path(script_id)


def invalidate_dependent_scene_caches(script_id: str) -> int:
    """Delete .prompt marker files for scenes whose images depend on the character.

    Called when the user edits the character description or regenerates the
    reference image. Returns the number of markers deleted.
    """
    images_dir = DATA_DIR / "projects" / script_id / "images"
    if not images_dir.exists():
        return 0
    deleted = 0
    for marker in images_dir.glob("*.prompt"):
        marker.unlink()
        deleted += 1
    return deleted
```

- [ ] **Step 4: Run the test to confirm it passes**

Run: `cd backend && uv run pytest tests/test_main_character_pipeline.py -v`
Expected: 3 passed.

- [ ] **Step 5: Commit**

```bash
git add backend/pipeline/main_character.py backend/tests/test_main_character_pipeline.py
git commit -m "Add main_character pipeline module for character reference generation"
```

---

### Task 7: Trigger main character generation from `_run_generation`

**Files:**
- Modify: `backend/api/scripts.py`

- [ ] **Step 1: Add the post-script-gen trigger**

In `backend/api/scripts.py`, after the script row is committed AND `get_or_create_project_config` is called (the block added in Task 3), add:

```python
            if not eli_enabled and script_content.main_character is not None:
                from pipeline.main_character import generate_character_reference
                from models.project_config import update_project_config

                logger.info(
                    "Generating main character reference for script_id=%s", script_id
                )
                try:
                    web_path = generate_character_reference(
                        script_id=script_id,
                        character=script_content.main_character,
                    )
                    update_project_config(
                        bg_session,
                        script_id,
                        main_character_reference_url=web_path,
                    )
                    bg_session.commit()
                except Exception as exc:  # noqa: BLE001
                    logger.exception("Main character reference generation failed: %s", exc)
                    # Non-fatal: project still works, scenes will just lack the reference.
```

**Optional progress reporting:** If you want this step to surface in the user-facing progress UI, look at how `_progress(...)` is called elsewhere in `_run_generation` and add a matching call before the `try:` block (e.g., `_progress(label="Generating main character reference")` if the callback accepts that shape). If the existing callback signature is awkward to match, leaving this as logger-only is acceptable for v1 — the user-visible "Main character" pipeline step in Task 19 communicates state.

- [ ] **Step 2: Manual verification**

Manual check (no automated test — would require Gemini key):
1. Set `ELI_ENABLED_DEFAULT=false` (or pass `eli_enabled: false` from frontend).
2. Generate a script.
3. Confirm `data/projects/{script_id}/character/reference.png` exists after generation completes.
4. Confirm the corresponding `ProjectConfig` row has `main_character_reference_url` populated.

- [ ] **Step 3: Commit**

```bash
git add backend/api/scripts.py
git commit -m "Trigger main character reference generation when Eli is disabled"
```

---

## Phase 3 — Backend Image Gen + API

### Task 8: `image_gen.py` selects reference based on `ProjectConfig.eli_enabled`

**Files:**
- Modify: `backend/pipeline/image_gen.py`
- Test: `backend/tests/test_image_gen_main_character.py`

- [ ] **Step 1: Write the failing test**

```python
# backend/tests/test_image_gen_main_character.py
from pathlib import Path
from unittest.mock import patch

from models.script import MainCharacter, ScriptContent, Segment
from pipeline.image_gen import _resolve_character_reference


def test_resolve_eli_enabled_returns_eli_reference(tmp_path, monkeypatch):
    monkeypatch.setenv("HH_DATA_DIR", str(tmp_path))
    import importlib
    import config

    importlib.reload(config)

    eli_ref = tmp_path / "character" / "frames" / "selected_reference.png"
    eli_ref.parent.mkdir(parents=True, exist_ok=True)
    eli_ref.write_bytes(b"x")

    ref_path, char_text = _resolve_character_reference(
        script_id="s",
        contains_person=True,
        eli_enabled=True,
        main_character_reference_url=None,
        main_character=None,
    )
    assert ref_path == str(eli_ref)
    assert char_text  # Eli's text description present


def test_resolve_eli_disabled_uses_project_character(tmp_path, monkeypatch):
    monkeypatch.setenv("HH_DATA_DIR", str(tmp_path))
    import importlib
    import config

    importlib.reload(config)

    project_ref = tmp_path / "projects" / "abc" / "character" / "reference.png"
    project_ref.parent.mkdir(parents=True, exist_ok=True)
    project_ref.write_bytes(b"x")

    char = MainCharacter(name="Maya", appearance="red coat", vibe="brisk")
    ref_path, char_text = _resolve_character_reference(
        script_id="abc",
        contains_person=True,
        eli_enabled=False,
        main_character_reference_url="/static/projects/abc/character/reference.png",
        main_character=char,
    )
    assert ref_path == str(project_ref)
    assert "Maya" in char_text
    assert "red coat" in char_text


def test_resolve_no_person_returns_none(tmp_path, monkeypatch):
    ref_path, char_text = _resolve_character_reference(
        script_id="s",
        contains_person=False,
        eli_enabled=False,
        main_character_reference_url="/static/projects/s/character/reference.png",
        main_character=MainCharacter(name="x", appearance="y", vibe="z"),
    )
    assert ref_path is None
    assert char_text == ""
```

- [ ] **Step 2: Run the test to confirm it fails**

Run: `cd backend && uv run pytest tests/test_image_gen_main_character.py -v`
Expected: ImportError — `_resolve_character_reference` not defined.

- [ ] **Step 3: Refactor `image_gen.py` to extract the resolver**

In `backend/pipeline/image_gen.py`, find the existing `compose_prompt` block (lines 114–131 per exploration). It currently has:

```python
if contains_person and _CHARACTER_PROMPT:
    parts.append(_CHARACTER_PROMPT)
...
reference_image_path = _get_character_reference() if contains_person else None
```

Replace that with a call to a new helper, and add the helper to the module:

```python
from config import DATA_DIR
from models.script import MainCharacter


def _eli_reference_path() -> str | None:
    """Path to Eli's selected reference, or None if not present."""
    p = DATA_DIR / "character" / "frames" / "selected_reference.png"
    return str(p) if p.exists() else None


def _project_character_reference_path(script_id: str) -> str | None:
    p = DATA_DIR / "projects" / script_id / "character" / "reference.png"
    return str(p) if p.exists() else None


def _serialize_main_character(char: MainCharacter) -> str:
    return (
        f"Recurring main character: {char.name}. "
        f"Appearance: {char.appearance}. "
        f"Vibe: {char.vibe}."
    )


def _resolve_character_reference(
    *,
    script_id: str,
    contains_person: bool,
    eli_enabled: bool,
    main_character_reference_url: str | None,
    main_character: MainCharacter | None,
) -> tuple[str | None, str]:
    """Return (reference_image_path, character_prompt_text) for image gen.

    eli_enabled=True   → Eli's reference + _CHARACTER_PROMPT (existing behavior).
    eli_enabled=False  → project main character reference + serialized description.
    contains_person=False always returns (None, "").
    """
    if not contains_person:
        return None, ""

    if eli_enabled:
        return _eli_reference_path(), _CHARACTER_PROMPT or ""

    if main_character is None or not main_character_reference_url:
        # Eli disabled but project has not generated a character yet — fall back
        # to no reference. Scene will still render, just without character chaining.
        return None, ""

    ref = _project_character_reference_path(script_id)
    if ref is None:
        return None, ""
    return ref, _serialize_main_character(main_character)
```

- [ ] **Step 4: Update `generate_scene_image` to load `ProjectConfig` and call the resolver**

In `generate_scene_image`, replace the existing character-reference logic with:

```python
    from models.project_config import get_project_config
    from models.script import ScriptContent
    from sqlmodel import Session

    from database import engine

    # Load project config + main_character (if any) in a short-lived session.
    with Session(engine) as session:
        cfg = get_project_config(session, script_id)
        # main_character lives in the script_json blob — fetch the script row.
        from models.script import Script

        script_row = session.get(Script, script_id)

    main_character_obj = None
    if script_row is not None:
        try:
            content = ScriptContent.model_validate_json(script_row.script_json)
            main_character_obj = content.main_character
        except Exception:  # noqa: BLE001
            main_character_obj = None

    reference_image_path, character_text = _resolve_character_reference(
        script_id=script_id,
        contains_person=contains_person,
        eli_enabled=cfg.eli_enabled,
        main_character_reference_url=cfg.main_character_reference_url,
        main_character=main_character_obj,
    )
```

Replace the existing `parts.append(_CHARACTER_PROMPT)` and `reference_image_path = _get_character_reference() if contains_person else None` lines with the new resolver output. Use `character_text` instead of `_CHARACTER_PROMPT` when assembling the prompt:

```python
    if character_text:
        parts.append(character_text)
```

The `[char_ref:{hash}]` cache-key annotation already in the file should be updated to include the reference path's mtime so changing the reference invalidates the cache:

```python
    if reference_image_path:
        try:
            mtime = int(Path(reference_image_path).stat().st_mtime)
            prompt += f"\n[char_ref:{reference_image_path}:{mtime}]"
        except OSError:
            pass
```

(Replace any existing `[char_ref:...]` line that uses `_character_ref_hash()`.)

- [ ] **Step 5: Run the test to confirm it passes**

Run: `cd backend && uv run pytest tests/test_image_gen_main_character.py -v`
Expected: 3 passed.

- [ ] **Step 6: Run the full backend test suite to catch regressions**

Run: `cd backend && uv run pytest tests/ -v`
Expected: All passing (existing + new).

- [ ] **Step 7: Commit**

```bash
git add backend/pipeline/image_gen.py backend/tests/test_image_gen_main_character.py
git commit -m "Branch image_gen character reference on ProjectConfig.eli_enabled"
```

---

### Task 9: `project_config` API endpoints

**Files:**
- Create: `backend/api/project_config.py`
- Modify: `backend/api/__init__.py` (register the router)
- Test: `backend/tests/test_project_config_api.py`

- [ ] **Step 1: Write the failing test**

```python
# backend/tests/test_project_config_api.py
from fastapi.testclient import TestClient
from sqlmodel import Session

from api import app
from database import engine
from models.project_config import ProjectConfig
from models.script import (
    MainCharacter,
    Script,
    ScriptContent,
)


def _make_script(script_id: str, *, eli_enabled: bool, main_character: MainCharacter | None = None) -> None:
    with Session(engine) as session:
        content = ScriptContent(title="t", segments=[], main_character=main_character)
        session.add(
            Script(
                id=script_id,
                brand_id="default",
                format_id="youtube-listicle",
                topic_title="t",
                topic_description="",
                script_json=content.model_dump_json(),
            )
        )
        session.add(ProjectConfig(script_id=script_id, eli_enabled=eli_enabled))
        session.commit()


def test_get_project_config_returns_full_payload():
    _make_script(
        "test-cfg-1",
        eli_enabled=False,
        main_character=MainCharacter(name="N", appearance="A", vibe="V"),
    )
    client = TestClient(app)
    res = client.get("/api/projects/test-cfg-1/config")
    assert res.status_code == 200
    data = res.json()
    assert data["eli_enabled"] is False
    assert data["main_character"]["name"] == "N"


def test_get_project_config_legacy_script_returns_default():
    """Script with no ProjectConfig row gets eli_enabled=True default."""
    with Session(engine) as session:
        session.add(
            Script(
                id="legacy-1",
                brand_id="default",
                format_id="youtube-listicle",
                topic_title="t",
                topic_description="",
                script_json=ScriptContent(title="t", segments=[]).model_dump_json(),
            )
        )
        session.commit()
    client = TestClient(app)
    res = client.get("/api/projects/legacy-1/config")
    assert res.status_code == 200
    assert res.json()["eli_enabled"] is True


def test_put_main_character_updates_script_json():
    _make_script(
        "test-cfg-2",
        eli_enabled=False,
        main_character=MainCharacter(name="Old", appearance="x", vibe="y"),
    )
    client = TestClient(app)
    res = client.put(
        "/api/projects/test-cfg-2/config/character",
        json={"name": "New", "appearance": "z", "vibe": "w"},
    )
    assert res.status_code == 200

    follow = client.get("/api/projects/test-cfg-2/config")
    assert follow.json()["main_character"]["name"] == "New"
```

- [ ] **Step 2: Run the test to confirm it fails**

Run: `cd backend && uv run pytest tests/test_project_config_api.py -v`
Expected: 404 — endpoints don't exist.

- [ ] **Step 3: Implement the router**

```python
# backend/api/project_config.py
"""Per-project config endpoints (Eli on/off, main character)."""

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlmodel import Session

from database import get_session
from models.project_config import (
    ProjectConfig,
    get_project_config,
    update_project_config,
)
from models.script import MainCharacter, Script, ScriptContent

router = APIRouter(prefix="/api/projects", tags=["project_config"])


class ProjectConfigResponse(BaseModel):
    script_id: str
    eli_enabled: bool
    main_character_reference_url: str | None
    main_character: MainCharacter | None


@router.get("/{script_id}/config", response_model=ProjectConfigResponse)
def get_config(script_id: str, session: Session = Depends(get_session)) -> ProjectConfigResponse:
    script = session.get(Script, script_id)
    if script is None:
        raise HTTPException(status_code=404, detail="Script not found")

    cfg = get_project_config(session, script_id)
    main_character: MainCharacter | None = None
    try:
        content = ScriptContent.model_validate_json(script.script_json)
        main_character = content.main_character
    except Exception:  # noqa: BLE001
        main_character = None

    return ProjectConfigResponse(
        script_id=script_id,
        eli_enabled=cfg.eli_enabled,
        main_character_reference_url=cfg.main_character_reference_url,
        main_character=main_character,
    )


@router.put("/{script_id}/config/character", response_model=ProjectConfigResponse)
def update_character(
    script_id: str,
    body: MainCharacter,
    session: Session = Depends(get_session),
) -> ProjectConfigResponse:
    script = session.get(Script, script_id)
    if script is None:
        raise HTTPException(status_code=404, detail="Script not found")

    cfg = get_project_config(session, script_id)
    if cfg.eli_enabled:
        raise HTTPException(
            status_code=400, detail="Cannot edit main character when Eli is enabled"
        )

    content = ScriptContent.model_validate_json(script.script_json)
    content.main_character = body
    script.script_json = content.model_dump_json()
    session.add(script)

    # Invalidate cached scene images that depend on the character description.
    from pipeline.main_character import invalidate_dependent_scene_caches

    invalidate_dependent_scene_caches(script_id)

    session.commit()
    session.refresh(script)

    return ProjectConfigResponse(
        script_id=script_id,
        eli_enabled=cfg.eli_enabled,
        main_character_reference_url=cfg.main_character_reference_url,
        main_character=body,
    )


@router.post(
    "/{script_id}/config/character/regenerate", response_model=ProjectConfigResponse
)
def regenerate_character_reference(
    script_id: str, session: Session = Depends(get_session)
) -> ProjectConfigResponse:
    script = session.get(Script, script_id)
    if script is None:
        raise HTTPException(status_code=404, detail="Script not found")

    cfg = get_project_config(session, script_id)
    if cfg.eli_enabled:
        raise HTTPException(
            status_code=400, detail="Cannot regenerate main character when Eli is enabled"
        )

    content = ScriptContent.model_validate_json(script.script_json)
    if content.main_character is None:
        raise HTTPException(
            status_code=400, detail="Script has no main character to regenerate"
        )

    from pipeline.main_character import (
        generate_character_reference,
        invalidate_dependent_scene_caches,
    )

    web_path = generate_character_reference(
        script_id=script_id,
        character=content.main_character,
        force=True,
    )
    update_project_config(session, script_id, main_character_reference_url=web_path)
    invalidate_dependent_scene_caches(script_id)
    session.commit()

    return ProjectConfigResponse(
        script_id=script_id,
        eli_enabled=cfg.eli_enabled,
        main_character_reference_url=web_path,
        main_character=content.main_character,
    )
```

- [ ] **Step 4: Register the router**

In `backend/api/__init__.py`, find the block that does `app.include_router(...)` for routers like `eli`, `scripts`, etc. Add:

```python
from api import project_config as project_config_router

app.include_router(project_config_router.router)
```

- [ ] **Step 5: Run the test to confirm it passes**

Run: `cd backend && uv run pytest tests/test_project_config_api.py -v`
Expected: 3 passed.

- [ ] **Step 6: Commit**

```bash
git add backend/api/project_config.py backend/api/__init__.py backend/tests/test_project_config_api.py
git commit -m "Add /api/projects/{script_id}/config endpoints for Eli toggle + main character"
```

---

### Task 10: Eli endpoint guards

**Files:**
- Modify: `backend/api/eli.py`
- Test: `backend/tests/test_eli_endpoint_guards.py`

- [ ] **Step 1: Write the failing test**

```python
# backend/tests/test_eli_endpoint_guards.py
from fastapi.testclient import TestClient
from sqlmodel import Session

from api import app
from database import engine
from models.project_config import ProjectConfig
from models.script import Script, ScriptContent


def _seed(script_id: str, *, eli_enabled: bool) -> None:
    with Session(engine) as session:
        session.add(
            Script(
                id=script_id,
                brand_id="default",
                format_id="youtube-listicle",
                topic_title="t",
                topic_description="",
                script_json=ScriptContent(title="t", segments=[]).model_dump_json(),
            )
        )
        session.add(ProjectConfig(script_id=script_id, eli_enabled=eli_enabled))
        session.commit()


def test_eli_generate_rejected_when_disabled():
    _seed("guard-1", eli_enabled=False)
    client = TestClient(app)
    res = client.post("/api/eli/generate", json={"script_id": "guard-1"})
    assert res.status_code == 400
    assert "disabled" in res.json()["detail"].lower()


def test_eli_regenerate_rejected_when_disabled():
    _seed("guard-2", eli_enabled=False)
    client = TestClient(app)
    res = client.post(
        "/api/eli/regenerate", json={"script_id": "guard-2", "scene_id": "x"}
    )
    assert res.status_code == 400
```

- [ ] **Step 2: Run the test to confirm it fails**

Run: `cd backend && uv run pytest tests/test_eli_endpoint_guards.py -v`
Expected: FAIL — endpoints accept the requests.

- [ ] **Step 3: Add the guard helper**

In `backend/api/eli.py`, near the top:

```python
from fastapi import HTTPException

from models.project_config import get_project_config


def _ensure_eli_enabled(session: Session, script_id: str) -> None:
    cfg = get_project_config(session, script_id)
    if not cfg.eli_enabled:
        raise HTTPException(
            status_code=400, detail="Eli is disabled for this project"
        )
```

- [ ] **Step 4: Apply the guard**

At the top of every Eli endpoint handler that accepts a `script_id` (`generate_eli`, `regenerate_eli`, and any per-scene endpoints), add a call:

```python
@router.post("/generate")
async def generate_eli(req: GenerateEliRequest, session: Session = Depends(get_session)):
    _ensure_eli_enabled(session, req.script_id)
    # ... existing body unchanged
```

Apply identically to all Eli mutation endpoints in the file.

- [ ] **Step 5: Run the test to confirm it passes**

Run: `cd backend && uv run pytest tests/test_eli_endpoint_guards.py -v`
Expected: 2 passed.

- [ ] **Step 6: Commit**

```bash
git add backend/api/eli.py backend/tests/test_eli_endpoint_guards.py
git commit -m "Guard Eli endpoints against disabled projects"
```

---

## Phase 4 — Frontend Backbone

### Task 11: API client additions

**Files:**
- Modify: `frontend/src/api.ts`

- [ ] **Step 1: Add types and functions**

In `frontend/src/api.ts`, near the other type definitions, add:

```typescript
export type MainCharacter = {
  name: string;
  appearance: string;
  vibe: string;
};

export type ProjectConfig = {
  script_id: string;
  eli_enabled: boolean;
  main_character_reference_url: string | null;
  main_character: MainCharacter | null;
};
```

In the function exports section, add:

```typescript
export async function getProjectConfig(scriptId: string) {
  return api.get(`/api/projects/${scriptId}/config`);
}

export async function updateMainCharacter(scriptId: string, character: MainCharacter) {
  return api.put(`/api/projects/${scriptId}/config/character`, character);
}

export async function regenerateMainCharacterReference(scriptId: string) {
  return api.post(`/api/projects/${scriptId}/config/character/regenerate`, {});
}
```

If `api.put` does not exist on the existing API helper object, add it alongside `api.get` / `api.post` using the same fetch/IPC fallback pattern. Inspect the existing `api` definition in this file and copy the post/get pattern.

- [ ] **Step 2: Update `generateScript` to forward `eli_enabled`**

Find the `generateScript` function (or its call site if it's a thin wrapper). It is likely defined alongside other functions, taking a payload object. Add `eli_enabled?: boolean` to its accepted type and pass it through. If the function passes `body` opaquely to `api.post`, the caller (Task 14) will include the field directly without changes here.

- [ ] **Step 3: Manual smoke check**

`cd frontend && npm run build` — ensure TypeScript compiles cleanly.

- [ ] **Step 4: Commit**

```bash
git add frontend/src/api.ts
git commit -m "Add ProjectConfig + main character API client functions"
```

---

### Task 12: Settings toggle for `ELI_ENABLED_DEFAULT`

**Files:**
- Modify: `frontend/src/components/settings/MiscSection.tsx`

- [ ] **Step 1: Add the toggle**

Read the existing `MiscSection.tsx` and find the pattern used for other boolean settings (likely `HOOK_REFINEMENT_ENABLED` or similar). Add a new toggle that follows the same pattern, with:

- Setting key: `ELI_ENABLED_DEFAULT`
- Label: **"Enable Eli host overlay by default for new projects"**
- Description: **"When off, new projects start with Eli disabled and use a project-specific main character integrated into scene images instead. Existing projects are unaffected."**

If `MiscSection.tsx` uses a generic `BooleanSetting` or similar reusable component, reuse it. If each toggle is hand-rolled, copy an existing toggle's structure verbatim and swap the key/label/description.

- [ ] **Step 2: Manual UI test**

```bash
npm run dev
```

Open Settings → Misc. Toggle the new switch. Refresh the page — confirm the value persists.

- [ ] **Step 3: Commit**

```bash
git add frontend/src/components/settings/MiscSection.tsx
git commit -m "Add Settings toggle for ELI_ENABLED_DEFAULT"
```

---

## Phase 5 — Frontend Ideation Toggle

### Task 13: Eli toggle on `IdeationPage`

**Files:**
- Modify: `frontend/src/components/ideation/IdeationPage.tsx`

- [ ] **Step 1: Add toggle state seeded from settings**

At the top of `IdeationPage`, after the existing `useState` declarations:

```typescript
const [eliEnabled, setEliEnabled] = useState<boolean>(true);

useEffect(() => {
  (async () => {
    const res = await api.get("/api/settings/keys");
    if (res.ok) {
      const data = res.data as Record<string, string>;
      const raw = data["ELI_ENABLED_DEFAULT"];
      // Stored as string "true"/"false"
      setEliEnabled(raw !== "false");
    }
  })();
}, []);
```

- [ ] **Step 2: Render the toggle UI above the idea grid**

Locate the JSX where the idea cards are rendered. Above the grid (and below any niche/format input row), add:

```tsx
<div className="flex items-center gap-3 px-4 py-3 bg-neutral-900 rounded-lg border border-neutral-800 mb-4">
  <span className="text-sm font-medium text-neutral-100">Eli host overlay</span>
  <button
    type="button"
    onClick={() => setEliEnabled(true)}
    className={`px-3 py-1.5 text-xs rounded-md transition-colors ${
      eliEnabled ? "bg-violet-600 text-white" : "bg-neutral-800 text-neutral-400 hover:bg-neutral-700"
    }`}
  >
    Enabled
  </button>
  <button
    type="button"
    onClick={() => setEliEnabled(false)}
    className={`px-3 py-1.5 text-xs rounded-md transition-colors ${
      !eliEnabled ? "bg-violet-600 text-white" : "bg-neutral-800 text-neutral-400 hover:bg-neutral-700"
    }`}
  >
    Disabled
  </button>
  <span className="text-xs text-neutral-500 ml-2">
    {eliEnabled
      ? "Eli will be the recurring on-screen host."
      : "A topic-specific main character will appear in scene images instead."}
  </span>
</div>
```

- [ ] **Step 3: Pass `eliEnabled` to script generation**

Find the `onUseIdea` callback (or wherever an idea is forwarded to script generation). Update its signature to include the toggle state. The simplest pattern: pass it via the existing `onUseIdea` prop signature. If the parent expects a function that takes `(idea: VideoIdea)`, extend it to `(idea: VideoIdea, opts: { eliEnabled: boolean })`.

Find the `IdeaCard` `onClick` / `onUse` handler invocation and forward `{ eliEnabled }`.

- [ ] **Step 4: Manual UI test**

```bash
npm run dev
```

Visit `/`, generate ideas, toggle Eli, pick an idea — confirm the chosen state flows to the next page (you'll wire the actual script-gen call in Task 14).

- [ ] **Step 5: Commit**

```bash
git add frontend/src/components/ideation/IdeationPage.tsx
git commit -m "Add Eli enabled/disabled toggle to ideation page"
```

---

### Task 14: Forward `eli_enabled` through script generation

**Files:**
- Modify: `frontend/src/components/script/useScriptGeneration.ts` (or wherever `POST /api/scripts/generate` is called from)
- Modify: parent component(s) that own `IdeationPage`'s `onUseIdea` handler (likely `App.tsx` or a top-level routing component)

- [ ] **Step 1: Locate the script-gen call site**

Run: `grep -rn "/api/scripts/generate" frontend/src/`

The known location from exploration is `frontend/src/components/script/useScriptGeneration.ts` (lines 303–316 and 434–447).

- [ ] **Step 2: Plumb `eli_enabled` through the hook**

In `useScriptGeneration.ts`, the script-gen call posts a body object. Extend the body:

```typescript
const res = await api.post("/api/scripts/generate", {
  topic: idea.title,
  description: idea.description,
  brand_id: brandId,
  format_id: idea.format_id ?? "youtube-listicle",
  // ... existing fields ...
  gameplay_enabled: gameplayEnabled,
  stock_photo_enabled: stockPhotoEnabled,
  eli_enabled: eliEnabled,  // NEW
});
```

Add `eliEnabled: boolean` to the hook's input args / options object, defaulting to `true`.

Update both call sites in `useScriptGeneration.ts` (303–316 and 434–447) consistently.

- [ ] **Step 3: Wire `IdeationPage`'s toggle into the parent's call**

In the parent component that owns `IdeationPage`'s `onUseIdea` and triggers script generation (locate via `grep -rn "onUseIdea" frontend/src/`), update the handler to accept the new options arg and pass `eliEnabled` into `useScriptGeneration`'s API.

- [ ] **Step 4: Manual end-to-end test**

```bash
npm run dev
```

1. Toggle Eli OFF on ideation page.
2. Pick an idea, generate script.
3. Hit `GET /api/projects/{script_id}/config` (curl or browser) — confirm `eli_enabled: false`.
4. Confirm the `data/projects/{script_id}/character/reference.png` file is created.

- [ ] **Step 5: Commit**

```bash
git add frontend/src/components/script/useScriptGeneration.ts <parent-files>
git commit -m "Forward eli_enabled from ideation toggle through script generation"
```

---

## Phase 6 — Frontend Project Header + Main Character Drawer

### Task 15: Fetch ProjectConfig in `TimelinePage` + render header badge

**Files:**
- Modify: `frontend/src/components/timeline/TimelinePage.tsx`

- [ ] **Step 1: Fetch ProjectConfig alongside the script**

In `TimelinePage`, near the existing `useEffect` that fetches the script, add a parallel fetch for project config:

```typescript
const [projectConfig, setProjectConfig] = useState<ProjectConfig | null>(null);

useEffect(() => {
  if (!scriptId) return;
  (async () => {
    const res = await getProjectConfig(scriptId);
    if (res.ok) setProjectConfig(res.data as ProjectConfig);
  })();
}, [scriptId]);
```

- [ ] **Step 2: Render the badge in the header**

Find the header JSX where `script.topic_title` (or equivalent) is rendered. Adjacent to the title, add:

```tsx
{projectConfig && !projectConfig.eli_enabled && (
  <button
    type="button"
    onClick={() => setShowMainCharacterDrawer(true)}
    className="ml-3 px-2.5 py-1 text-xs rounded-full bg-neutral-800 text-neutral-300 hover:bg-neutral-700 transition-colors border border-neutral-700"
    title="Open main character drawer"
  >
    {projectConfig.main_character
      ? `Main character: ${projectConfig.main_character.name}`
      : "Eli: off"}
  </button>
)}
```

Add `const [showMainCharacterDrawer, setShowMainCharacterDrawer] = useState(false);` near the other UI state.

- [ ] **Step 3: Pass `projectConfig` down to children that need it**

The following children need `projectConfig`:
- `PipelineSteps` (for the "Add Eli" button — Task 17)
- `TimelineLanes` (for hiding `EliLane` — Task 18)

Add it to their props. If the prop drilling is awkward, define it once on `TimelinePage` and pass.

- [ ] **Step 4: Commit**

```bash
git add frontend/src/components/timeline/TimelinePage.tsx
git commit -m "Fetch ProjectConfig in TimelinePage and show main character badge"
```

---

### Task 16: Main Character drawer

**Files:**
- Create: `frontend/src/components/timeline/MainCharacterDrawer.tsx`
- Modify: `frontend/src/components/timeline/TimelinePage.tsx` (mount the drawer)

- [ ] **Step 1: Create the drawer component**

```tsx
// frontend/src/components/timeline/MainCharacterDrawer.tsx
import { useEffect, useState } from "react";

import {
  MainCharacter,
  ProjectConfig,
  assetUrl,
  regenerateMainCharacterReference,
  updateMainCharacter,
} from "../../api";

type Props = {
  scriptId: string;
  config: ProjectConfig;
  onClose: () => void;
  onUpdated: (next: ProjectConfig) => void;
};

export default function MainCharacterDrawer({
  scriptId,
  config,
  onClose,
  onUpdated,
}: Props) {
  const initial = config.main_character;
  const [name, setName] = useState(initial?.name ?? "");
  const [appearance, setAppearance] = useState(initial?.appearance ?? "");
  const [vibe, setVibe] = useState(initial?.vibe ?? "");
  const [saving, setSaving] = useState(false);
  const [regenerating, setRegenerating] = useState(false);

  useEffect(() => {
    setName(config.main_character?.name ?? "");
    setAppearance(config.main_character?.appearance ?? "");
    setVibe(config.main_character?.vibe ?? "");
  }, [config.main_character]);

  const dirty =
    name !== (initial?.name ?? "") ||
    appearance !== (initial?.appearance ?? "") ||
    vibe !== (initial?.vibe ?? "");

  const save = async () => {
    setSaving(true);
    const character: MainCharacter = { name, appearance, vibe };
    const res = await updateMainCharacter(scriptId, character);
    setSaving(false);
    if (res.ok) {
      onUpdated(res.data as ProjectConfig);
    }
  };

  const regenerate = async () => {
    setRegenerating(true);
    const res = await regenerateMainCharacterReference(scriptId);
    setRegenerating(false);
    if (res.ok) {
      onUpdated(res.data as ProjectConfig);
    }
  };

  return (
    <div className="fixed inset-0 z-50 bg-black/50 flex justify-end" onClick={onClose}>
      <div
        className="w-[480px] h-full bg-neutral-950 border-l border-neutral-800 p-6 overflow-y-auto"
        onClick={(e) => e.stopPropagation()}
      >
        <div className="flex items-center justify-between mb-6">
          <h2 className="text-xl font-semibold text-neutral-100">Main Character</h2>
          <button
            type="button"
            onClick={onClose}
            className="text-neutral-500 hover:text-neutral-200 transition-colors"
          >
            ✕
          </button>
        </div>

        {config.main_character_reference_url ? (
          <img
            src={assetUrl(config.main_character_reference_url)}
            alt="Main character reference"
            className="w-full aspect-video rounded-lg border border-neutral-800 mb-4 object-cover"
          />
        ) : (
          <div className="w-full aspect-video rounded-lg border border-dashed border-neutral-700 flex items-center justify-center text-neutral-500 text-sm mb-4">
            Reference image not generated yet
          </div>
        )}

        <button
          type="button"
          onClick={regenerate}
          disabled={regenerating || !name}
          className="w-full mb-6 px-3 py-2 text-sm rounded-md bg-neutral-800 text-neutral-200 hover:bg-neutral-700 disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
        >
          {regenerating ? "Regenerating..." : "Regenerate reference image"}
        </button>

        <div className="space-y-4">
          <label className="block">
            <span className="text-xs text-neutral-400 uppercase tracking-wide">Name</span>
            <input
              type="text"
              value={name}
              onChange={(e) => setName(e.target.value)}
              className="mt-1 w-full bg-neutral-900 border border-neutral-800 rounded-md px-3 py-2 text-sm text-neutral-100 focus:border-violet-500 focus:outline-none"
            />
          </label>
          <label className="block">
            <span className="text-xs text-neutral-400 uppercase tracking-wide">Appearance</span>
            <textarea
              rows={5}
              value={appearance}
              onChange={(e) => setAppearance(e.target.value)}
              className="mt-1 w-full bg-neutral-900 border border-neutral-800 rounded-md px-3 py-2 text-sm text-neutral-100 focus:border-violet-500 focus:outline-none resize-y"
            />
          </label>
          <label className="block">
            <span className="text-xs text-neutral-400 uppercase tracking-wide">Vibe</span>
            <textarea
              rows={3}
              value={vibe}
              onChange={(e) => setVibe(e.target.value)}
              className="mt-1 w-full bg-neutral-900 border border-neutral-800 rounded-md px-3 py-2 text-sm text-neutral-100 focus:border-violet-500 focus:outline-none resize-y"
            />
          </label>
        </div>

        <button
          type="button"
          onClick={save}
          disabled={!dirty || saving}
          className="mt-6 w-full px-3 py-2 text-sm rounded-md bg-violet-600 text-white hover:bg-violet-500 disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
        >
          {saving ? "Saving..." : "Save"}
        </button>

        <p className="mt-4 text-xs text-neutral-500">
          Editing the description or regenerating the reference will invalidate
          cached scene images that include the character. They will re-render on
          next batch.
        </p>
      </div>
    </div>
  );
}
```

- [ ] **Step 2: Mount the drawer in `TimelinePage`**

In `TimelinePage`, render the drawer at the bottom of the JSX tree:

```tsx
{showMainCharacterDrawer && projectConfig && (
  <MainCharacterDrawer
    scriptId={scriptId}
    config={projectConfig}
    onClose={() => setShowMainCharacterDrawer(false)}
    onUpdated={(next) => setProjectConfig(next)}
  />
)}
```

Import the component at the top.

- [ ] **Step 3: Manual UI test**

```bash
npm run dev
```

1. Open a project that was generated with Eli disabled.
2. Click the "Main character: ..." badge in the header.
3. Drawer opens. Edit appearance, save — confirm the change persists (refresh page).
4. Click "Regenerate reference" — confirm the image updates.

- [ ] **Step 4: Commit**

```bash
git add frontend/src/components/timeline/MainCharacterDrawer.tsx frontend/src/components/timeline/TimelinePage.tsx
git commit -m "Add MainCharacterDrawer for editing project main character"
```

---

## Phase 7 — Frontend Disabled UI States

### Task 17: Disable "Add Eli" button when Eli is disabled

**Files:**
- Modify: `frontend/src/components/timeline/TimelinePage.tsx` (or `PipelineSteps.tsx` — wherever the Add Eli button lives)

- [ ] **Step 1: Locate the button**

Run: `grep -rn "Add Eli" frontend/src/`

Per exploration, it's in `TimelinePage.tsx` around line 350 (in title text passed to `PipelineSteps`). The actual button render likely lives in `PipelineSteps.tsx`.

- [ ] **Step 2: Pass `eliDisabled` prop to `PipelineSteps`**

In `TimelinePage.tsx`, where `<PipelineSteps ... />` is rendered, add:

```tsx
eliDisabled={projectConfig != null && !projectConfig.eli_enabled}
```

- [ ] **Step 3: Render the button as disabled**

In `PipelineSteps.tsx`, accept the new prop and gate the Eli button:

```tsx
<button
  type="button"
  onClick={onAddEli}
  disabled={eliDisabled || existingDisabledConditions}
  title={
    eliDisabled
      ? "Eli is disabled for this project. The main character is integrated into scene images instead."
      : existingTitleLogic
  }
  className={`... ${
    eliDisabled
      ? "opacity-40 cursor-not-allowed"
      : ""
  } ...`}
>
  Add Eli
</button>
```

Preserve all existing disabled conditions — just OR `eliDisabled` into them.

- [ ] **Step 4: Manual UI test**

```bash
npm run dev
```

1. Open a project with Eli disabled.
2. Hover the "Add Eli" button — tooltip shows the disabled message.
3. Confirm clicking it does nothing.
4. Open a project with Eli enabled — confirm the button still works as before.

- [ ] **Step 5: Commit**

```bash
git add frontend/src/components/timeline/PipelineSteps.tsx frontend/src/components/timeline/TimelinePage.tsx
git commit -m "Disable Add Eli button when project has Eli disabled"
```

---

### Task 18: Hide `EliLane` in `TimelineLanes` when Eli is disabled

**Files:**
- Modify: `frontend/src/components/timeline/TimelineLanes.tsx`

- [ ] **Step 1: Pass `eliEnabled` prop**

From `TimelinePage`, pass `eliEnabled={projectConfig?.eli_enabled ?? true}` into `<TimelineLanes ... />`.

- [ ] **Step 2: Skip the eli lane row when disabled**

In `TimelineLanes.tsx`, find the loop that iterates `LANE_TYPES` and renders a row per type. Wrap or filter:

```tsx
const visibleLanes = LANE_TYPES.filter(
  (type) => !(type === "eli" && !eliEnabled)
);

{visibleLanes.map((type) => (
  // existing render
))}
```

Apply the same filter to per-scene `SceneMicroTimeline` if it also iterates lanes.

- [ ] **Step 3: Manual UI test**

```bash
npm run dev
```

1. Open a project with Eli disabled — confirm the Eli lane row is gone, layout looks clean.
2. Open a project with Eli enabled — confirm Eli lane is visible (current behavior).

- [ ] **Step 4: Commit**

```bash
git add frontend/src/components/timeline/TimelineLanes.tsx frontend/src/components/timeline/TimelinePage.tsx
git commit -m "Hide Eli lane in timeline when Eli is disabled for project"
```

---

### Task 19: Pipeline progress step swap (Eli ↔ main character)

**Files:**
- Modify: `frontend/src/components/timeline/PipelineSteps.tsx` (or wherever pipeline step labels are defined)

- [ ] **Step 1: Locate the Eli pipeline step**

Run: `grep -rn "Eli" frontend/src/components/timeline/`

Identify the step entry that says something like "Generate Eli animations" in the pipeline progress / steps panel.

- [ ] **Step 2: Conditionally render**

When `eliDisabled` is true, replace the Eli step with a "Main character" step:

```tsx
{eliDisabled ? (
  <PipelineStep
    label="Main character"
    status={mainCharacterStatus}
    detail={
      projectConfig?.main_character_reference_url
        ? "Reference generated"
        : "Not yet generated"
    }
    onClick={() => setShowMainCharacterDrawer(true)}
  />
) : (
  <PipelineStep
    label="Generate Eli animations"
    status={eliStatus}
    onClick={onAddEli}
    // ... existing props
  />
)}
```

`mainCharacterStatus` is `"complete"` if `projectConfig.main_character_reference_url` is set, else `"pending"`. Reuse the existing `PipelineStep` component (whatever shape it has — read the existing Eli step usage and mirror it).

If no abstraction exists and the step is a hand-rolled `<div>...</div>`, copy the Eli step's structure verbatim and swap the label/status/onClick.

- [ ] **Step 3: Manual UI test**

```bash
npm run dev
```

1. Open project with Eli disabled — pipeline shows "Main character" step in place of Eli.
2. Click it — opens the Main Character drawer.

- [ ] **Step 4: Commit**

```bash
git add frontend/src/components/timeline/PipelineSteps.tsx
git commit -m "Swap Eli pipeline step for Main Character step when Eli disabled"
```

---

## Phase 8 — End-to-End Verification

### Task 20: End-to-end manual verification

- [ ] **Step 1: Verify Eli-disabled flow end to end**

Run: `npm run dev`

1. Settings → Misc → toggle "Enable Eli host overlay by default" OFF. Save.
2. Navigate to ideation page. Confirm the Eli toggle on the page shows "Disabled" by default.
3. Generate ideas. Pick one. Generate the script.
4. While script generation runs, watch progress — should include main character generation.
5. After generation: open the project. Confirm:
   - Header shows "Main character: {name}" badge.
   - Clicking the badge opens the drawer with the generated reference image.
   - "Add Eli" button is grayed/disabled with tooltip.
   - Eli lane row in timeline is hidden.
   - Pipeline steps panel shows "Main character" step instead of "Generate Eli animations".
6. Generate scene images for a few scenes. Confirm those with `contains_person=true` reflect the main character; those with `contains_person=false` don't.
7. Open the Main Character drawer. Edit the description. Save. Re-generate one scene image — confirm it picks up the new description (cached `.prompt` markers were invalidated).

- [ ] **Step 2: Verify Eli-enabled regression**

1. Settings → toggle Eli ON. Generate a new script with Eli enabled.
2. Confirm the project header shows no badge.
3. Confirm "Add Eli" button is fully functional, Eli lane is visible, original Eli pipeline step shows.
4. Confirm scene image generation still chains Eli's reference for `contains_person=true` scenes (existing behavior preserved).

- [ ] **Step 3: Verify legacy projects unaffected**

1. Open a project that was created before this feature shipped (no `ProjectConfig` row).
2. Confirm everything looks identical to today: no badge, Eli lane visible, "Add Eli" works, Eli step in pipeline.

- [ ] **Step 4: Final test sweep**

Run: `cd backend && uv run pytest tests/ -v`
Expected: all green.

Run: `cd frontend && npm run build`
Expected: clean compile, no TypeScript errors.

- [ ] **Step 5: Final commit + push**

If any small fixes were needed during e2e:

```bash
git add -A
git commit -m "Address e2e verification fixes"
git push origin main
```

---

## Self-Review Notes

- **Spec coverage:** All sections of the spec are addressed. Data model: Tasks 1, 4. Settings: Task 2, 12. Ideation flow: Tasks 13, 14. Main character pipeline: Tasks 5, 6, 7. Image gen chaining: Task 8. API endpoints: Task 9. Eli endpoint guards: Task 10. Project header + drawer: Tasks 15, 16. UI indicators: Tasks 17, 18, 19.
- **Spec deviation documented:** Reuse of `Scene.contains_person` instead of new `Scene.include_main_character` is called out in the plan header.
- **Settings location updated:** Spec said `CharacterSection.tsx`, but it doesn't exist in the frontend; toggle goes in `MiscSection.tsx`.
- **Auto-commit + review loop:** Per `CLAUDE.md`, after this plan is fully executed, the auto-commit subagent review loop runs against the merged work on `main`.
