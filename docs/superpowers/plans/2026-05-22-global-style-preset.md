# Global Style Preset Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Enforce consistent visual style across all videos by attaching a single user-curated reference image to every Gemini image-generation call, gated by a per-project toggle that is mutually exclusive with the existing Eli toggle.

**Architecture:** New `style_presets` SQLModel table backed by image files on disk. Active preset id stored in existing `AppSettings` key/value table. `ProjectConfig` gains a `style_preset_enabled` bool. The image-gen pipeline passes the active preset image as an additional multi-modal `Part` to Gemini whenever a project has Eli disabled, the per-project toggle on, and an active preset exists. Cache invalidation reuses the existing `[char_ref:...]` marker pattern.

**Tech Stack:** Python 3.12 + FastAPI + SQLModel + SQLite (backend), React 19 + TypeScript + Tailwind 4 (frontend), Google Gemini via `google-genai` SDK. Spec: `docs/superpowers/specs/2026-05-22-global-style-preset-design.md`.

---

## File Structure

**New backend files:**
- `backend/models/style_preset.py` — SQLModel + Pydantic schemas
- `backend/api/style.py` — FastAPI router for preset library + active selection
- `backend/pipeline/style_presets.py` — Gemini generation + background job orchestration
- `backend/tests/test_style_preset_resolve.py`
- `backend/tests/test_image_gen_with_style_preset.py`
- `backend/tests/test_style_preset_api.py`
- `backend/tests/test_thumbnail_with_style_preset.py`

**Modified backend files:**
- `backend/models/project_config.py` — add `style_preset_enabled` field
- `backend/database.py` — register new model + add migration for `style_preset_enabled` column
- `backend/api/settings.py` — register `STYLE_PRESET_ENABLED_DEFAULT` and `ACTIVE_STYLE_PRESET_ID` in ALLOWED_KEYS / _PLAINTEXT_KEYS / _DEFAULTS
- `backend/api/__init__.py` — register style router + `/static/style` mount + register StylePreset table import
- `backend/api/project_config.py` — accept/return `style_preset_enabled`
- `backend/api/scripts.py` — accept `style_preset_enabled` in script generation request
- `backend/integrations/google_image_client.py` — add `style_reference_path` parameter
- `backend/pipeline/image_gen.py` — add resolver helpers, thread style ref through
- `backend/pipeline/thumbnail.py` — resolve and forward style ref
- `backend/pipeline/formats/title_cards/cinematic_chapters.py` — include style ref in split-progression enhancement

**New frontend files:**
- `frontend/src/contexts/StylePresetContext.tsx`
- `frontend/src/components/shared/StylePresetToggle.tsx`
- `frontend/src/components/settings/StylePresetsSection.tsx`
- `frontend/src/components/settings/StylePresetCreateModal.tsx`

**Modified frontend files:**
- `frontend/src/api.ts` — new functions and types
- `frontend/src/App.tsx` — wrap with StylePresetProvider
- `frontend/src/components/settings/SettingsPage.tsx` — add new section
- `frontend/src/components/settings/MiscSection.tsx` — add toggle pair
- `frontend/src/components/script/useScriptGeneration.ts` — add `stylePresetEnabled` state + payload
- `frontend/src/components/script/ScriptGenerationPage.tsx` — render new toggle
- `frontend/src/components/ideation/IdeationPage.tsx` — render new toggle
- `frontend/src/components/timeline/TimelinePage.tsx` — render read-only badge

---

## Task 1: Backend data model and migration

**Files:**
- Create: `backend/models/style_preset.py`
- Modify: `backend/models/project_config.py`
- Modify: `backend/database.py`
- Modify: `backend/api/settings.py`
- Modify: `backend/api/__init__.py:40-49`
- Test: `backend/tests/test_style_preset_model.py` (new)
- Test: `backend/tests/test_project_config.py` (modify)

- [ ] **Step 1: Write failing test for ProjectConfig.style_preset_enabled default**

Add to the existing `backend/tests/test_project_config.py`:

```python
def test_project_config_style_preset_enabled_defaults_true():
    from models.project_config import ProjectConfig

    cfg = ProjectConfig(script_id="s1")
    assert cfg.style_preset_enabled is True
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd backend && uv run pytest tests/test_project_config.py::test_project_config_style_preset_enabled_defaults_true -v`
Expected: FAIL with `AttributeError: 'ProjectConfig' object has no attribute 'style_preset_enabled'`.

- [ ] **Step 3: Add field to ProjectConfig**

Modify `backend/models/project_config.py`:

```python
class ProjectConfig(SQLModel, table=True):
    """Per-project configuration. One row per script.

    Missing rows are treated as the default (Eli enabled) so projects created
    before this feature shipped continue to behave identically.
    """

    __tablename__ = "project_config"

    script_id: str = Field(primary_key=True, foreign_key="scripts.id")
    eli_enabled: bool = Field(default=True)
    style_preset_enabled: bool = Field(default=True)
    main_character_reference_url: str | None = Field(default=None)
    created_at: datetime = Field(default_factory=_utcnow)
    updated_at: datetime = Field(default_factory=_utcnow)
```

Update `get_project_config` to keep the synthetic default consistent:

```python
def get_project_config(session: Session, script_id: str) -> ProjectConfig:
    """Return the persisted ProjectConfig or a synthetic default for missing rows."""
    row = session.exec(
        select(ProjectConfig).where(ProjectConfig.script_id == script_id)
    ).first()
    if row is not None:
        return row
    return ProjectConfig(script_id=script_id, eli_enabled=True, style_preset_enabled=True)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd backend && uv run pytest tests/test_project_config.py::test_project_config_style_preset_enabled_defaults_true -v`
Expected: PASS.

- [ ] **Step 5: Add SQLite migration for the new column**

Add to `backend/database.py`. Insert the new function in alphabetical/order grouping with the other project_config-related migrations and call it from `init_db()`:

In the `init_db()` body, add the call right after `_migrate_add_eli_position()`:

```python
def init_db() -> None:
    """Create all tables. Safe to call repeatedly."""
    logger.info("Initializing database")
    SQLModel.metadata.create_all(engine)
    _migrate_add_eli_position()
    _migrate_add_style_preset_enabled_to_project_config()
    _migrate_add_format_id_to_scripts()
    # ... rest unchanged
```

Add the migration function (place it next to other project_config migrations, e.g. directly below `_migrate_add_eli_position`):

```python
def _migrate_add_style_preset_enabled_to_project_config() -> None:
    """Add style_preset_enabled column to project_config if missing."""
    import sqlite3

    conn = sqlite3.connect(str(_db_path))
    try:
        cursor = conn.execute("PRAGMA table_info(project_config)")
        columns = {row[1] for row in cursor.fetchall()}
        if "style_preset_enabled" not in columns:
            conn.execute(
                "ALTER TABLE project_config ADD COLUMN style_preset_enabled INTEGER DEFAULT 1 NOT NULL"
            )
            conn.commit()
            logger.info("Migrated: added style_preset_enabled to project_config")
    finally:
        conn.close()
```

- [ ] **Step 6: Create StylePreset model file**

Create `backend/models/style_preset.py`:

```python
"""StylePreset SQLModel + Pydantic schemas.

A style preset is a single 16:9 reference image generated from a free-form
user prompt. The image lives on disk at data/style/presets/<id>.png and is
attached as a multi-modal Part to Gemini image-generation calls when the
active project has Eli disabled and style_preset_enabled set to True.
"""

from datetime import datetime, timezone

from pydantic import BaseModel
from sqlmodel import Field, SQLModel


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


class StylePreset(SQLModel, table=True):
    __tablename__ = "style_presets"

    id: str = Field(primary_key=True)
    name: str = Field(default="")
    prompt: str = Field(default="")
    created_at: datetime = Field(default_factory=_utcnow)


class StylePresetResponse(BaseModel):
    id: str
    name: str
    prompt: str
    image_url: str
    created_at: datetime


class CreateStylePresetRequest(BaseModel):
    prompt: str
    name: str = ""


class GeneratePresetJobResponse(BaseModel):
    job_id: str


class SetActivePresetRequest(BaseModel):
    preset_id: str | None
```

- [ ] **Step 7: Register model so SQLModel.metadata.create_all picks it up**

Modify `backend/api/__init__.py` to import the new model alongside the others. Add this line in the cluster around lines 40-49:

```python
from models.style_preset import StylePreset as _StylePreset  # noqa: F401 — register table
```

- [ ] **Step 8: Register AppSettings keys**

Modify `backend/api/settings.py` to add the two new keys:

In `ALLOWED_KEYS` (around line 60, near `"ELI_ENABLED_DEFAULT"`):

```python
    "ELI_ENABLED_DEFAULT",
    "STYLE_PRESET_ENABLED_DEFAULT",
    "ACTIVE_STYLE_PRESET_ID",
}
```

In `_PLAINTEXT_KEYS` (around line 90):

```python
    "ELI_ENABLED_DEFAULT",
    "STYLE_PRESET_ENABLED_DEFAULT",
    "ACTIVE_STYLE_PRESET_ID",
}
```

In `_DEFAULTS` (around line 115):

```python
    "ELI_ENABLED_DEFAULT": "true",
    "STYLE_PRESET_ENABLED_DEFAULT": "true",
    "ACTIVE_STYLE_PRESET_ID": "",
```

- [ ] **Step 9: Verify settings registration with a test**

Add to `backend/tests/test_eli_enabled_default_setting.py` (it already exists for the parallel pattern):

```python
def test_style_preset_enabled_default_is_allowed():
    from api.settings import ALLOWED_KEYS
    assert "STYLE_PRESET_ENABLED_DEFAULT" in ALLOWED_KEYS


def test_style_preset_enabled_default_has_default_true():
    from api.settings import _DEFAULTS
    assert _DEFAULTS.get("STYLE_PRESET_ENABLED_DEFAULT") == "true"


def test_active_style_preset_id_is_allowed():
    from api.settings import ALLOWED_KEYS
    assert "ACTIVE_STYLE_PRESET_ID" in ALLOWED_KEYS


def test_active_style_preset_id_default_empty():
    from api.settings import _DEFAULTS
    assert _DEFAULTS.get("ACTIVE_STYLE_PRESET_ID") == ""
```

Run: `cd backend && uv run pytest tests/test_eli_enabled_default_setting.py -v`
Expected: all PASS.

- [ ] **Step 10: Run the full backend test suite to confirm no regressions**

Run: `cd backend && uv run pytest -x`
Expected: all PASS.

- [ ] **Step 11: Commit**

```bash
git add backend/models/style_preset.py backend/models/project_config.py backend/database.py backend/api/settings.py backend/api/__init__.py backend/tests/test_project_config.py backend/tests/test_eli_enabled_default_setting.py
git commit -m "Add StylePreset model + ProjectConfig.style_preset_enabled field"
```

---

## Task 2: Image-gen client gains a style_reference_path parameter

**Files:**
- Modify: `backend/integrations/google_image_client.py`
- Test: `backend/tests/test_image_gen_with_style_preset.py` (new)

- [ ] **Step 1: Write failing test verifying style ref is attached as a Part**

Create `backend/tests/test_image_gen_with_style_preset.py`:

```python
"""Tests for style_reference_path threading through generate_image()."""

from unittest.mock import MagicMock, patch

import pytest


@pytest.fixture
def fake_gemini_response():
    """A fake Gemini response with one inline_data Part containing tiny PNG bytes."""
    response = MagicMock()
    part = MagicMock()
    part.inline_data = MagicMock()
    # 1x1 PNG: minimal valid PNG header + IHDR + IDAT + IEND
    part.inline_data.data = (
        b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01\x00\x00\x00\x01"
        b"\x08\x06\x00\x00\x00\x1f\x15\xc4\x89\x00\x00\x00\rIDATx\x9cc\xfc\xcf"
        b"\xc0\x00\x00\x00\x05\x00\x01\xa6\xff\xa9\x9b\x00\x00\x00\x00IEND\xaeB`\x82"
    )
    response.parts = [part]
    return response


def test_generate_image_passes_style_reference_as_part(tmp_path, fake_gemini_response):
    """When style_reference_path is set, generate_image attaches it as a Part."""
    from integrations import google_image_client

    style_ref = tmp_path / "style.png"
    style_ref.write_bytes(b"fakepng")

    captured_contents = []

    def fake_call(client, contents, aspect, script_id=None, max_retries=3):
        captured_contents.append(contents)
        # Return a writable temp path with bytes
        out = tmp_path / "out.png"
        out.write_bytes(fake_gemini_response.parts[0].inline_data.data)
        return str(out)

    with patch.object(google_image_client, "_call_gemini", side_effect=fake_call), \
         patch.object(google_image_client, "get_google_client", return_value=MagicMock()), \
         patch.object(google_image_client, "record_usage"):
        google_image_client.generate_image(
            prompt="a scene",
            style_reference_path=str(style_ref),
        )

    assert len(captured_contents) == 1
    contents = captured_contents[0]
    # Last item must be the prompt string
    assert contents[-1] == "a scene"
    # First items must be Parts (one for the style ref, since no character ref provided)
    assert len(contents) == 2  # 1 style ref + 1 prompt


def test_generate_image_without_style_reference_omits_part(tmp_path, fake_gemini_response):
    from integrations import google_image_client

    captured_contents = []

    def fake_call(client, contents, aspect, script_id=None, max_retries=3):
        captured_contents.append(contents)
        out = tmp_path / "out.png"
        out.write_bytes(fake_gemini_response.parts[0].inline_data.data)
        return str(out)

    with patch.object(google_image_client, "_call_gemini", side_effect=fake_call), \
         patch.object(google_image_client, "get_google_client", return_value=MagicMock()), \
         patch.object(google_image_client, "record_usage"):
        google_image_client.generate_image(prompt="a scene")

    contents = captured_contents[0]
    assert contents == ["a scene"]


def test_generate_image_with_both_char_and_style_refs(tmp_path, fake_gemini_response):
    """When both refs are present, char ref comes first, style ref second, prompt last."""
    from integrations import google_image_client

    char_ref = tmp_path / "char.png"
    char_ref.write_bytes(b"charpng")
    style_ref = tmp_path / "style.png"
    style_ref.write_bytes(b"stylepng")

    captured_contents = []

    def fake_call(client, contents, aspect, script_id=None, max_retries=3):
        captured_contents.append(contents)
        out = tmp_path / "out.png"
        out.write_bytes(fake_gemini_response.parts[0].inline_data.data)
        return str(out)

    with patch.object(google_image_client, "_call_gemini", side_effect=fake_call), \
         patch.object(google_image_client, "get_google_client", return_value=MagicMock()), \
         patch.object(google_image_client, "record_usage"):
        google_image_client.generate_image(
            prompt="a scene",
            reference_image_path=str(char_ref),
            style_reference_path=str(style_ref),
        )

    contents = captured_contents[0]
    # 2 parts (char + style) + prompt = 3 items
    assert len(contents) == 3
    assert contents[-1] == "a scene"
```

- [ ] **Step 2: Run tests and verify they fail**

Run: `cd backend && uv run pytest tests/test_image_gen_with_style_preset.py -v`
Expected: FAIL with `TypeError: generate_image() got an unexpected keyword argument 'style_reference_path'`.

- [ ] **Step 3: Add style_reference_path parameter to generate_image**

Modify `backend/integrations/google_image_client.py`. Update the `generate_image` signature and body. Replace the entire `generate_image` function with:

```python
def generate_image(
    prompt: str,
    width: int = IMAGE_WIDTH,
    height: int = IMAGE_HEIGHT,
    seed: int | None = None,
    reference_image_path: str | None = None,
    style_reference_path: str | None = None,
    original_prompt: str | None = None,
    script_id: str | None = None,
) -> str:
    """Generate an image via Gemini and return the path to a temp file.

    If reference_image_path is provided, the image is loaded as a multi-modal
    Part so Gemini can use it as a visual reference for character/style consistency.

    If style_reference_path is provided, it is attached as an additional Part
    after the character reference. Used to enforce a global art style across
    videos when the project has Eli disabled and style preset enabled.

    original_prompt is the raw visual description before style guide was prepended.
    Used for retry when Gemini blocks the full prompt.

    Falls back to Google Image scraper only when IMAGE_SCRAPER_FALLBACK_ENABLED
    is explicitly enabled.
    """
    client = get_google_client()
    aspect = _closest_aspect_ratio(width, height)
    logger.info(
        "Generating image via Gemini (aspect=%s, has_char_ref=%s, has_style_ref=%s)",
        aspect, reference_image_path is not None, style_reference_path is not None,
    )

    # Build reference image parts (reusable across retries)
    ref_parts: list = []
    if reference_image_path:
        mime = "image/png" if reference_image_path.lower().endswith(".png") else "image/jpeg"
        with open(reference_image_path, "rb") as f:
            ref_parts.append(types.Part.from_bytes(data=f.read(), mime_type=mime))
        logger.info("Including character reference image: %s", reference_image_path)
    if style_reference_path:
        mime = "image/png" if style_reference_path.lower().endswith(".png") else "image/jpeg"
        with open(style_reference_path, "rb") as f:
            ref_parts.append(types.Part.from_bytes(data=f.read(), mime_type=mime))
        logger.info("Including style reference image: %s", style_reference_path)

    # First attempt with full prompt
    contents: list = list(ref_parts)
    contents.append(prompt)

    try:
        result = _call_gemini(client, contents, aspect, script_id=script_id)
        if result:
            return result
    except Exception:
        logger.warning("First Gemini attempt raised, will retry with simplified prompt")

    # Retry with original visual prompt (no style guide preamble)
    retry_prompt = (
        f"Educational illustration, flat 2D cartoon style, absolutely no text or letters in the image: {original_prompt}"
        if original_prompt
        else f"Educational illustration, flat 2D cartoon style, absolutely no text or letters in the image: {prompt[:500]}"
    )
    logger.warning(
        "Gemini returned empty response (content filter?), retrying with simplified prompt: %s",
        retry_prompt[:200],
    )

    contents = list(ref_parts)
    contents.append(retry_prompt)

    try:
        result = _call_gemini(client, contents, aspect, script_id=script_id)
        if result:
            return result
    except Exception:
        logger.warning("Second Gemini attempt also raised")

    scraper_fallback_enabled = _setting_enabled(os.environ.get("IMAGE_SCRAPER_FALLBACK_ENABLED"))
    if not scraper_fallback_enabled:
        raise RuntimeError(
            f"Gemini returned empty response on both attempts. Scraped web-image fallback "
            f"is disabled; use stock-photo routing or enable IMAGE_SCRAPER_FALLBACK_ENABLED "
            f"if web scraping is acceptable for this project. Prompt: {prompt[:200]}"
        )

    # Last resort: Google Image scraper (unchanged)
    from integrations.google_image_scraper import scrape_google_image_sync

    search_query = (original_prompt or prompt)[:120]
    logger.warning(
        "Gemini failed on both attempts, using opt-in Google Image scraper fallback: %s",
        search_query,
    )
    fd, tmp_path = tempfile.mkstemp(suffix=".png")
    os.close(fd)
    scraped = scrape_google_image_sync(
        query=search_query,
        output_path=tmp_path,
        width=width,
        height=height,
    )
    if scraped:
        logger.warning("Using scraped web image as fallback for: %s", search_query)
        _write_source_metadata(scraped, {
            "source_type": "scraped_web_image",
            "provider": "google_images_scraper",
            "query": search_query,
            "reason": "Gemini image generation failed after retries",
            "license_note": "Scraped web image; verify usage rights before publishing.",
            "opt_in_setting": "IMAGE_SCRAPER_FALLBACK_ENABLED",
            "fallback": True,
        })
        return scraped

    if os.path.exists(tmp_path):
        os.unlink(tmp_path)

    raise RuntimeError(
        f"Gemini returned empty response on both attempts and Google Image scraper "
        f"also failed. Prompt: {prompt[:200]}"
    )
```

- [ ] **Step 4: Update the image_client.py router to forward the new parameter**

Check whether `backend/integrations/image_client.py` is a router/wrapper:

Run: `grep -n "def generate_image\|reference_image_path" backend/integrations/image_client.py`

If it accepts `**kwargs` or already forwards `reference_image_path`, no change needed. Otherwise add the new parameter to its signature and forward to the underlying provider call. Read the file and update accordingly.

- [ ] **Step 5: Run the test to verify it passes**

Run: `cd backend && uv run pytest tests/test_image_gen_with_style_preset.py -v`
Expected: all 3 tests PASS.

- [ ] **Step 6: Commit**

```bash
git add backend/integrations/google_image_client.py backend/integrations/image_client.py backend/tests/test_image_gen_with_style_preset.py
git commit -m "Add style_reference_path parameter to generate_image"
```

---

## Task 3: Style preset resolver helpers in image_gen.py

**Files:**
- Modify: `backend/pipeline/image_gen.py`
- Test: `backend/tests/test_style_preset_resolve.py` (new)

- [ ] **Step 1: Write failing tests for the resolver**

Create `backend/tests/test_style_preset_resolve.py`:

```python
"""Tests for the style-preset resolution helpers."""

from unittest.mock import patch


def test_resolve_returns_none_when_eli_enabled(tmp_path):
    from pipeline.image_gen import _resolve_style_preset

    # Even if a preset would normally be active, Eli takes precedence
    with patch("pipeline.image_gen._active_style_preset_path", return_value=str(tmp_path / "x.png")):
        assert _resolve_style_preset(eli_enabled=True, project_style_enabled=True) is None


def test_resolve_returns_none_when_project_disabled(tmp_path):
    from pipeline.image_gen import _resolve_style_preset

    with patch("pipeline.image_gen._active_style_preset_path", return_value=str(tmp_path / "x.png")):
        assert _resolve_style_preset(eli_enabled=False, project_style_enabled=False) is None


def test_resolve_returns_none_when_no_active_preset():
    from pipeline.image_gen import _resolve_style_preset

    with patch("pipeline.image_gen._active_style_preset_path", return_value=None):
        assert _resolve_style_preset(eli_enabled=False, project_style_enabled=True) is None


def test_resolve_returns_path_when_eligible(tmp_path):
    from pipeline.image_gen import _resolve_style_preset

    expected = str(tmp_path / "preset.png")
    with patch("pipeline.image_gen._active_style_preset_path", return_value=expected):
        assert _resolve_style_preset(eli_enabled=False, project_style_enabled=True) == expected


def test_active_path_returns_none_when_setting_empty():
    from pipeline.image_gen import _active_style_preset_path

    with patch("pipeline.image_gen._read_app_setting", return_value=""):
        assert _active_style_preset_path() is None


def test_active_path_returns_none_when_file_missing(tmp_path):
    from pipeline.image_gen import _active_style_preset_path

    with patch("pipeline.image_gen._read_app_setting", return_value="abc-123"), \
         patch("pipeline.image_gen.DATA_DIR", tmp_path):
        # File does not exist
        assert _active_style_preset_path() is None


def test_active_path_returns_path_when_file_exists(tmp_path):
    from pipeline.image_gen import _active_style_preset_path

    presets_dir = tmp_path / "style" / "presets"
    presets_dir.mkdir(parents=True)
    (presets_dir / "abc-123.png").write_bytes(b"fakepng")

    with patch("pipeline.image_gen._read_app_setting", return_value="abc-123"), \
         patch("pipeline.image_gen.DATA_DIR", tmp_path):
        result = _active_style_preset_path()
        assert result is not None
        assert result.endswith("abc-123.png")
```

- [ ] **Step 2: Run tests and verify they fail**

Run: `cd backend && uv run pytest tests/test_style_preset_resolve.py -v`
Expected: FAIL with `ImportError: cannot import name '_resolve_style_preset'`.

- [ ] **Step 3: Add resolver helpers to image_gen.py**

Modify `backend/pipeline/image_gen.py`. Add these helpers near the top of the file, just below the existing `_eli_reference_path` and `_project_character_reference_path` definitions:

```python
def _read_app_setting(key: str) -> str:
    """Read a setting value from AppSettings; empty string if missing."""
    from sqlmodel import Session
    from database import engine
    from models.settings import AppSetting

    with Session(engine) as session:
        row = session.get(AppSetting, key)
        return row.value if row else ""


def _active_style_preset_path() -> str | None:
    """Return path to the active style preset image, or None if unset/missing."""
    preset_id = _read_app_setting("ACTIVE_STYLE_PRESET_ID").strip()
    if not preset_id:
        return None
    p = DATA_DIR / "style" / "presets" / f"{preset_id}.png"
    return str(p) if p.exists() else None


def _resolve_style_preset(
    *,
    eli_enabled: bool,
    project_style_enabled: bool,
) -> str | None:
    """Return the active style preset path or None.

    Returns None when:
      - Eli is enabled (style preset never applies to Eli videos)
      - The project's style_preset_enabled toggle is False
      - No preset is active or the active preset's image file is missing
    """
    if eli_enabled or not project_style_enabled:
        return None
    return _active_style_preset_path()
```

- [ ] **Step 4: Run resolver tests**

Run: `cd backend && uv run pytest tests/test_style_preset_resolve.py -v`
Expected: all 7 tests PASS.

- [ ] **Step 5: Commit**

```bash
git add backend/pipeline/image_gen.py backend/tests/test_style_preset_resolve.py
git commit -m "Add style preset resolver helpers in image_gen"
```

---

## Task 4: Wire style preset into scene + frame generation

**Files:**
- Modify: `backend/pipeline/image_gen.py`
- Test: `backend/tests/test_image_gen_with_style_preset.py` (extend)

- [ ] **Step 1: Write failing tests asserting style ref flows through scene generation**

Add to `backend/tests/test_image_gen_with_style_preset.py`:

```python
def test_generate_scene_image_threads_style_ref_when_eli_off(tmp_path, monkeypatch):
    """When eli_enabled is False and a preset is active, generate_image gets style_reference_path."""
    from pipeline import image_gen

    monkeypatch.setattr(image_gen, "DATA_DIR", tmp_path)

    # Stub out the project context: Eli OFF, style enabled, no main character
    monkeypatch.setattr(
        image_gen,
        "_load_project_character_context",
        lambda script_id: (False, None, None),
    )
    monkeypatch.setattr(
        image_gen,
        "_load_project_style_enabled",
        lambda script_id: True,
    )
    monkeypatch.setattr(
        image_gen,
        "_active_style_preset_path",
        lambda: str(tmp_path / "preset.png"),
    )

    # Create the preset file so resolver finds it
    (tmp_path / "preset.png").write_bytes(b"fakepng")

    captured = {}

    def fake_generate_image(prompt, **kwargs):
        captured.update(kwargs)
        out = tmp_path / "out.png"
        out.write_bytes(b"fakepng")
        return str(out)

    monkeypatch.setattr(image_gen, "generate_image", fake_generate_image)

    image_gen.generate_scene_image(
        scene_id="s1",
        visual_prompt="a tree",
        script_id="proj-1",
        contains_person=False,
    )

    assert captured.get("style_reference_path") == str(tmp_path / "preset.png")


def test_generate_scene_image_omits_style_ref_when_eli_on(tmp_path, monkeypatch):
    from pipeline import image_gen

    monkeypatch.setattr(image_gen, "DATA_DIR", tmp_path)
    monkeypatch.setattr(
        image_gen,
        "_load_project_character_context",
        lambda script_id: (True, None, None),
    )
    monkeypatch.setattr(image_gen, "_load_project_style_enabled", lambda script_id: True)
    monkeypatch.setattr(image_gen, "_active_style_preset_path", lambda: str(tmp_path / "preset.png"))
    (tmp_path / "preset.png").write_bytes(b"fakepng")

    captured = {}

    def fake_generate_image(prompt, **kwargs):
        captured.update(kwargs)
        out = tmp_path / "out.png"
        out.write_bytes(b"fakepng")
        return str(out)

    monkeypatch.setattr(image_gen, "generate_image", fake_generate_image)

    image_gen.generate_scene_image(
        scene_id="s1",
        visual_prompt="a tree",
        script_id="proj-1",
        contains_person=False,
    )

    assert captured.get("style_reference_path") is None
```

- [ ] **Step 2: Run tests and verify they fail**

Run: `cd backend && uv run pytest tests/test_image_gen_with_style_preset.py -v`
Expected: the new tests FAIL with `AttributeError: module 'pipeline.image_gen' has no attribute '_load_project_style_enabled'`.

- [ ] **Step 3: Add the project-style loader helper**

In `backend/pipeline/image_gen.py`, add this helper next to `_load_project_character_context`:

```python
def _load_project_style_enabled(script_id: str) -> bool:
    """Read the project's style_preset_enabled flag, defaulting to True if missing."""
    from sqlmodel import Session
    from database import engine
    from models.project_config import get_project_config

    with Session(engine) as session:
        cfg = get_project_config(session, script_id)
    return cfg.style_preset_enabled
```

- [ ] **Step 4: Wire style ref into generate_scene_image**

In `backend/pipeline/image_gen.py`, modify `generate_scene_image` so it resolves the style ref and includes it in the prompt cache marker AND forwards it to `generate_image`. Apply these targeted edits:

After the existing `eli_enabled, main_character_url, main_character_obj = _load_project_character_context(script_id)` line, add:

```python
    project_style_enabled = _load_project_style_enabled(script_id)
    style_reference_path = _resolve_style_preset(
        eli_enabled=eli_enabled,
        project_style_enabled=project_style_enabled,
    )
```

Below the existing block that appends `[char_ref:...]` to the prompt for cache invalidation, add a parallel block:

```python
    if style_reference_path:
        try:
            mtime = int(Path(style_reference_path).stat().st_mtime)
            prompt += f"\n[style_ref:{style_reference_path}:{mtime}]"
        except OSError:
            pass
```

Then update the `generate_image(...)` call inside `generate_scene_image` to forward the new kwarg:

```python
        tmp_path = generate_image(
            prompt, width=width, height=height,
            original_prompt=visual_prompt,
            reference_image_path=reference_image_path,
            style_reference_path=style_reference_path,
            script_id=script_id,
        )
```

- [ ] **Step 5: Wire style ref into generate_scene_frames**

In the same file, apply the same three changes inside `generate_scene_frames`:

After `reference_image_path, character_text = _resolve_character_reference(...)`, add the project-style-enabled load and the resolver call (same lines as above).

Inside the per-frame loop, after the existing `if reference_image_path:` cache-marker block, add:

```python
        if style_reference_path:
            try:
                mtime = int(Path(style_reference_path).stat().st_mtime)
                prompt += f"\n[style_ref:{style_reference_path}:{mtime}]"
            except OSError:
                pass
```

Update the `generate_image(...)` call inside the loop to add `style_reference_path=style_reference_path`.

- [ ] **Step 6: Wire style ref into generate_scene_frames_v2**

Same treatment as Step 5: load the project style enabled flag once at the top, resolve the style ref once at the top, then within the per-frame loop append the cache marker and pass `style_reference_path=style_reference_path` to `generate_image(...)`.

- [ ] **Step 7: Run scene-image tests**

Run: `cd backend && uv run pytest tests/test_image_gen_with_style_preset.py -v`
Expected: all PASS.

- [ ] **Step 8: Run full image-gen test suite to confirm no regressions**

Run: `cd backend && uv run pytest tests/test_image_gen* tests/test_visual_beat* -v 2>/dev/null || cd backend && uv run pytest tests/ -k "image_gen or visual_beat" -v`
Expected: all PASS.

- [ ] **Step 9: Commit**

```bash
git add backend/pipeline/image_gen.py backend/tests/test_image_gen_with_style_preset.py
git commit -m "Wire style preset into scene + frame image generation"
```

---

## Task 5: Style-preset generation pipeline + background jobs

**Files:**
- Create: `backend/pipeline/style_presets.py`
- Test: `backend/tests/test_style_preset_pipeline.py` (new)

- [ ] **Step 1: Write failing test for generate_preset**

Create `backend/tests/test_style_preset_pipeline.py`:

```python
"""Tests for style_presets.generate_preset orchestration."""

from unittest.mock import patch

import pytest


def test_generate_preset_writes_image_and_db_row(tmp_path, monkeypatch):
    from pipeline import style_presets

    monkeypatch.setattr(style_presets, "DATA_DIR", tmp_path)

    fake_tmp = tmp_path / "gemini_tmp.png"
    fake_tmp.write_bytes(b"fakepng")

    with patch.object(
        style_presets, "generate_image", return_value=str(fake_tmp)
    ):
        preset_id = style_presets.generate_preset(
            prompt="a 16:9 reference sheet of cartoon people and objects",
            name="Saturday Cartoon",
        )

    # The preset image should be moved into data/style/presets/<id>.png
    assert (tmp_path / "style" / "presets" / f"{preset_id}.png").exists()

    # And a DB row should be readable
    from sqlmodel import Session
    from database import engine
    from models.style_preset import StylePreset

    with Session(engine) as session:
        row = session.get(StylePreset, preset_id)
        assert row is not None
        assert row.name == "Saturday Cartoon"
        assert row.prompt == "a 16:9 reference sheet of cartoon people and objects"


def test_generate_preset_propagates_gemini_failure(tmp_path, monkeypatch):
    from pipeline import style_presets

    monkeypatch.setattr(style_presets, "DATA_DIR", tmp_path)

    with patch.object(
        style_presets, "generate_image", side_effect=RuntimeError("Gemini blocked")
    ):
        with pytest.raises(RuntimeError, match="Gemini blocked"):
            style_presets.generate_preset(prompt="x", name="y")
```

- [ ] **Step 2: Run test and verify it fails**

Run: `cd backend && uv run pytest tests/test_style_preset_pipeline.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'pipeline.style_presets'`.

- [ ] **Step 3: Create the pipeline module**

Create `backend/pipeline/style_presets.py`:

```python
"""Style preset generation pipeline.

Orchestrates Gemini image generation for user-defined style reference images
and persists them as files on disk plus rows in the style_presets table.

Background-job tracking mirrors backend/pipeline/render_jobs.py.
"""

from __future__ import annotations

import logging
import shutil
import threading
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path

from sqlmodel import Session

from config import DATA_DIR
from database import engine
from integrations.image_client import generate_image
from models.style_preset import StylePreset

logger = logging.getLogger(__name__)


_PRESET_IMAGE_WIDTH = 1920
_PRESET_IMAGE_HEIGHT = 1080


def _presets_dir() -> Path:
    p = DATA_DIR / "style" / "presets"
    p.mkdir(parents=True, exist_ok=True)
    return p


def generate_preset(prompt: str, name: str) -> str:
    """Generate a style preset image and persist it. Returns the new preset id.

    The user's prompt is sent to Gemini as-is. No programmatic wrapping.
    Raises RuntimeError if generation fails.
    """
    preset_id = str(uuid.uuid4())
    logger.info("Generating style preset id=%s name=%r", preset_id, name)

    tmp_path = generate_image(
        prompt=prompt,
        width=_PRESET_IMAGE_WIDTH,
        height=_PRESET_IMAGE_HEIGHT,
    )

    final_path = _presets_dir() / f"{preset_id}.png"
    shutil.move(tmp_path, str(final_path))

    with Session(engine) as session:
        row = StylePreset(
            id=preset_id,
            name=name or "Untitled",
            prompt=prompt,
            created_at=datetime.now(timezone.utc),
        )
        session.add(row)
        session.commit()

    logger.info("Style preset saved id=%s path=%s", preset_id, final_path)
    return preset_id


# --- Background job tracking ---

@dataclass
class PresetJob:
    job_id: str
    status: str = "pending"  # pending | running | completed | failed
    preset_id: str | None = None
    error: str | None = None
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))


_jobs: dict[str, PresetJob] = {}
_jobs_lock = threading.Lock()


def submit_preset_job(prompt: str, name: str) -> str:
    """Spawn a background thread to generate a preset; return job_id immediately."""
    job_id = str(uuid.uuid4())
    job = PresetJob(job_id=job_id)
    with _jobs_lock:
        _jobs[job_id] = job

    def _worker() -> None:
        with _jobs_lock:
            job.status = "running"
        try:
            preset_id = generate_preset(prompt=prompt, name=name)
            with _jobs_lock:
                job.preset_id = preset_id
                job.status = "completed"
        except Exception as exc:
            logger.error("Preset generation job %s failed: %s", job_id, exc, exc_info=True)
            with _jobs_lock:
                job.error = str(exc)[:500]
                job.status = "failed"

    threading.Thread(target=_worker, name=f"style-preset-{job_id[:8]}", daemon=True).start()
    return job_id


def get_job(job_id: str) -> PresetJob | None:
    with _jobs_lock:
        return _jobs.get(job_id)
```

- [ ] **Step 4: Run pipeline tests**

Run: `cd backend && uv run pytest tests/test_style_preset_pipeline.py -v`
Expected: all PASS.

- [ ] **Step 5: Commit**

```bash
git add backend/pipeline/style_presets.py backend/tests/test_style_preset_pipeline.py
git commit -m "Add style preset generation pipeline and background jobs"
```

---

## Task 6: Style preset API router

**Files:**
- Create: `backend/api/style.py`
- Modify: `backend/api/__init__.py`
- Test: `backend/tests/test_style_preset_api.py` (new)

- [ ] **Step 1: Write failing API tests**

Create `backend/tests/test_style_preset_api.py`:

```python
"""Tests for /api/style endpoints."""

from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient


@pytest.fixture
def client():
    from api import app
    return TestClient(app)


def test_list_presets_empty(client):
    response = client.get("/api/style/presets")
    assert response.status_code == 200
    # Initial state may be non-empty if other tests run first; just assert structure
    assert isinstance(response.json(), list)


def test_create_preset_returns_job_id(client):
    with patch("api.style.submit_preset_job", return_value="job-123") as mock_submit:
        response = client.post(
            "/api/style/presets",
            json={"prompt": "a reference sheet", "name": "test"},
        )
    assert response.status_code == 200
    assert response.json() == {"job_id": "job-123"}
    mock_submit.assert_called_once_with(prompt="a reference sheet", name="test")


def test_get_active_returns_null_when_unset(client):
    # Ensure unset
    client.put("/api/style/active", json={"preset_id": None})
    response = client.get("/api/style/active")
    assert response.status_code == 200
    assert response.json() is None


def test_set_active_then_get_active(client, tmp_path, monkeypatch):
    from pipeline import style_presets
    from sqlmodel import Session
    from database import engine
    from models.style_preset import StylePreset
    from datetime import datetime, timezone

    monkeypatch.setattr(style_presets, "DATA_DIR", tmp_path)

    # Insert a preset directly
    preset_id = "test-preset-id"
    presets_dir = tmp_path / "style" / "presets"
    presets_dir.mkdir(parents=True)
    (presets_dir / f"{preset_id}.png").write_bytes(b"fakepng")
    with Session(engine) as session:
        session.add(StylePreset(
            id=preset_id, name="Test", prompt="x",
            created_at=datetime.now(timezone.utc),
        ))
        session.commit()

    # Set active
    response = client.put("/api/style/active", json={"preset_id": preset_id})
    assert response.status_code == 200

    # Get active
    response = client.get("/api/style/active")
    assert response.status_code == 200
    body = response.json()
    assert body is not None
    assert body["id"] == preset_id

    # Cleanup
    with Session(engine) as session:
        session.delete(session.get(StylePreset, preset_id))
        session.commit()
    client.put("/api/style/active", json={"preset_id": None})


def test_delete_preset_clears_active_if_was_active(client, tmp_path, monkeypatch):
    from pipeline import style_presets
    from sqlmodel import Session
    from database import engine
    from models.style_preset import StylePreset
    from datetime import datetime, timezone

    monkeypatch.setattr(style_presets, "DATA_DIR", tmp_path)
    preset_id = "delete-me"
    presets_dir = tmp_path / "style" / "presets"
    presets_dir.mkdir(parents=True, exist_ok=True)
    (presets_dir / f"{preset_id}.png").write_bytes(b"fakepng")
    with Session(engine) as session:
        session.add(StylePreset(id=preset_id, name="x", prompt="x",
                                 created_at=datetime.now(timezone.utc)))
        session.commit()

    client.put("/api/style/active", json={"preset_id": preset_id})

    # Delete should also clear the active id
    response = client.delete(f"/api/style/presets/{preset_id}")
    assert response.status_code == 200

    response = client.get("/api/style/active")
    assert response.json() is None
```

- [ ] **Step 2: Run tests and verify they fail**

Run: `cd backend && uv run pytest tests/test_style_preset_api.py -v`
Expected: FAIL with 404s (router not registered).

- [ ] **Step 3: Create the router**

Create `backend/api/style.py`:

```python
"""Style preset endpoints.

GET    /api/style/presets               -> list all
POST   /api/style/presets               -> kick off background generation
GET    /api/style/presets/jobs/{job_id} -> poll job status
DELETE /api/style/presets/{id}          -> delete (also clears active if was active)
GET    /api/style/active                -> active preset or null
PUT    /api/style/active                -> set active preset by id (or null to clear)
"""

import logging
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException
from sqlmodel import Session, select

from config import DATA_DIR
from database import get_session
from models.settings import AppSetting
from models.style_preset import (
    CreateStylePresetRequest,
    GeneratePresetJobResponse,
    SetActivePresetRequest,
    StylePreset,
    StylePresetResponse,
)
from pipeline.style_presets import get_job, submit_preset_job

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/style", tags=["style"])


_ACTIVE_KEY = "ACTIVE_STYLE_PRESET_ID"


def _to_response(preset: StylePreset) -> StylePresetResponse:
    return StylePresetResponse(
        id=preset.id,
        name=preset.name,
        prompt=preset.prompt,
        image_url=f"/static/style/presets/{preset.id}.png",
        created_at=preset.created_at,
    )


def _read_active_id(session: Session) -> str:
    row = session.get(AppSetting, _ACTIVE_KEY)
    return (row.value if row else "").strip()


def _write_active_id(session: Session, preset_id: str | None) -> None:
    row = session.get(AppSetting, _ACTIVE_KEY)
    if row is None:
        row = AppSetting(key=_ACTIVE_KEY, value=preset_id or "")
    else:
        row.value = preset_id or ""
    session.add(row)
    session.commit()


@router.get("/presets", response_model=list[StylePresetResponse])
def list_presets(session: Session = Depends(get_session)):
    presets = session.exec(select(StylePreset).order_by(StylePreset.created_at.desc())).all()
    return [_to_response(p) for p in presets]


@router.post("/presets", response_model=GeneratePresetJobResponse)
def create_preset(req: CreateStylePresetRequest):
    if not req.prompt.strip():
        raise HTTPException(status_code=400, detail="prompt is required")
    job_id = submit_preset_job(prompt=req.prompt, name=req.name or "Untitled")
    return GeneratePresetJobResponse(job_id=job_id)


@router.get("/presets/jobs/{job_id}")
def get_preset_job(job_id: str, session: Session = Depends(get_session)):
    job = get_job(job_id)
    if job is None:
        raise HTTPException(status_code=404, detail="job not found")
    payload = {
        "job_id": job.job_id,
        "status": job.status,
        "error": job.error,
        "preset_id": job.preset_id,
    }
    if job.status == "completed" and job.preset_id:
        preset = session.get(StylePreset, job.preset_id)
        if preset:
            payload["preset"] = _to_response(preset).model_dump(mode="json")
    return payload


@router.delete("/presets/{preset_id}")
def delete_preset(preset_id: str, session: Session = Depends(get_session)):
    preset = session.get(StylePreset, preset_id)
    if preset is None:
        raise HTTPException(status_code=404, detail="preset not found")

    # Delete file
    image_path = DATA_DIR / "style" / "presets" / f"{preset_id}.png"
    if image_path.exists():
        image_path.unlink()

    # Delete row
    session.delete(preset)

    # Clear active id if it pointed at this preset
    active_id = _read_active_id(session)
    if active_id == preset_id:
        _write_active_id(session, None)

    session.commit()
    return {"ok": True}


@router.get("/active", response_model=StylePresetResponse | None)
def get_active(session: Session = Depends(get_session)):
    preset_id = _read_active_id(session)
    if not preset_id:
        return None
    preset = session.get(StylePreset, preset_id)
    if preset is None:
        return None
    return _to_response(preset)


@router.put("/active")
def set_active(req: SetActivePresetRequest, session: Session = Depends(get_session)):
    if req.preset_id is not None:
        preset = session.get(StylePreset, req.preset_id)
        if preset is None:
            raise HTTPException(status_code=404, detail="preset not found")
    _write_active_id(session, req.preset_id)
    return {"ok": True, "active_id": req.preset_id}
```

- [ ] **Step 4: Register router and add static mount**

Modify `backend/api/__init__.py`. Add the import alongside other routers:

```python
from api.style import router as style_router
```

Add the include_router call in the cluster around line 124:

```python
app.include_router(style_router)
```

Add a static mount alongside the others (after the character mount):

```python
_style_dir = DATA_DIR / "style" / "presets"
_style_dir.mkdir(parents=True, exist_ok=True)
app.mount("/static/style", StaticFiles(directory=str(DATA_DIR / "style")), name="style-assets")
```

- [ ] **Step 5: Run API tests**

Run: `cd backend && uv run pytest tests/test_style_preset_api.py -v`
Expected: all PASS.

- [ ] **Step 6: Run full backend test suite to confirm no regressions**

Run: `cd backend && uv run pytest -x`
Expected: all PASS.

- [ ] **Step 7: Commit**

```bash
git add backend/api/style.py backend/api/__init__.py backend/tests/test_style_preset_api.py
git commit -m "Add style preset API router and static mount"
```

---

## Task 7: Wire style preset into thumbnail and cinematic chapters

**Files:**
- Modify: `backend/pipeline/thumbnail.py`
- Modify: `backend/pipeline/formats/title_cards/cinematic_chapters.py`
- Test: `backend/tests/test_thumbnail_with_style_preset.py` (new)

**Important context:** `thumbnail.py` does NOT call `generate_image()` directly — it calls `transform_with_references()`, which already accepts a list of image paths. The integration point is to *append* the style preset path to that list. Same approach for `enhance_split_progression` in `cinematic_chapters.py`. The two `transform_with_references` call sites in `thumbnail.py` are at lines 193 and 504 (verify with `grep -n "transform_with_references" backend/pipeline/thumbnail.py`).

- [ ] **Step 1: Add resolver helper to thumbnail.py**

In `backend/pipeline/thumbnail.py`, near the top of the file (after the existing imports), add:

```python
def _resolve_thumbnail_style_ref(script_id: str) -> str | None:
    """Return the active style preset path for this project, or None.

    Mirrors pipeline.image_gen._resolve_style_preset's behavior:
      - None when Eli is enabled for the project
      - None when the project's style_preset_enabled flag is False
      - None when no preset is active or its image file is missing
      - Otherwise the absolute path to the active preset image
    """
    from sqlmodel import Session
    from database import engine
    from models.project_config import get_project_config
    from pipeline.image_gen import _resolve_style_preset

    with Session(engine) as session:
        cfg = get_project_config(session, script_id)

    return _resolve_style_preset(
        eli_enabled=cfg.eli_enabled,
        project_style_enabled=cfg.style_preset_enabled,
    )
```

- [ ] **Step 2: Write failing tests**

Create `backend/tests/test_thumbnail_with_style_preset.py`:

```python
"""Tests confirming thumbnail and cinematic-chapters paths thread the style preset
into transform_with_references' image_paths list.
"""

from unittest.mock import patch


def test_resolver_returns_path_when_eli_off_and_style_on(tmp_path, monkeypatch):
    """The thumbnail resolver delegates to image_gen._resolve_style_preset
    using the project's eli_enabled and style_preset_enabled flags."""
    from pipeline import thumbnail as thumb_module

    monkeypatch.setattr(thumb_module, "DATA_DIR", tmp_path)

    class FakeCfg:
        eli_enabled = False
        style_preset_enabled = True

    def fake_get_cfg(session, script_id):
        return FakeCfg()

    monkeypatch.setattr("models.project_config.get_project_config", fake_get_cfg)

    expected = str(tmp_path / "preset.png")
    with patch("pipeline.image_gen._resolve_style_preset", return_value=expected):
        result = thumb_module._resolve_thumbnail_style_ref(script_id="proj-1")

    assert result == expected


def test_resolver_returns_none_when_eli_on(tmp_path, monkeypatch):
    from pipeline import thumbnail as thumb_module

    monkeypatch.setattr(thumb_module, "DATA_DIR", tmp_path)

    class FakeCfg:
        eli_enabled = True
        style_preset_enabled = True

    def fake_get_cfg(session, script_id):
        return FakeCfg()

    monkeypatch.setattr("models.project_config.get_project_config", fake_get_cfg)

    with patch("pipeline.image_gen._resolve_style_preset", return_value=None) as mock_resolve:
        result = thumb_module._resolve_thumbnail_style_ref(script_id="proj-1")

    assert result is None
    mock_resolve.assert_called_once_with(eli_enabled=True, project_style_enabled=True)


def test_cinematic_split_progression_appends_style_ref(tmp_path, monkeypatch):
    """When a style preset is active, enhance_split_progression includes it in image_paths."""
    from pipeline.formats.title_cards import cinematic_chapters

    captured = {}

    def fake_transform(prompt, image_paths, **kwargs):
        captured["image_paths"] = list(image_paths)
        out = tmp_path / "enhanced.png"
        out.write_bytes(b"fakepng")
        return str(out)

    style_ref = tmp_path / "preset.png"
    style_ref.write_bytes(b"fakepng")

    monkeypatch.setattr(
        cinematic_chapters, "transform_with_references", fake_transform,
    )
    monkeypatch.setattr(
        "pipeline.thumbnail._resolve_thumbnail_style_ref",
        lambda script_id: str(style_ref),
    )

    # Set up minimal inputs for enhance_split_progression. Adapt these to whatever
    # the function's actual signature is (read it from cinematic_chapters.py).
    clean = tmp_path / "clean.png"
    clean.write_bytes(b"fakepng")
    out_path = tmp_path / "split.png"

    cinematic_chapters.enhance_split_progression(
        script_id="proj-1",
        clean_path=clean,
        out_path=out_path,
        left_level=1,
        right_level=5,
    )

    assert any(str(style_ref) in p for p in captured["image_paths"])
```

> NOTE: The `enhance_split_progression` call signature in this test mirrors the function as described in the spec. If the actual signature in `cinematic_chapters.py` differs, adapt the kwargs — the key assertion (style ref appears in image_paths) stays the same.

- [ ] **Step 3: Run tests and verify they fail**

Run: `cd backend && uv run pytest tests/test_thumbnail_with_style_preset.py -v`
Expected: FAIL — `_resolve_thumbnail_style_ref` exists from Step 1, but the cinematic-chapters wiring does not yet append the style ref.

- [ ] **Step 4: Wire style ref into thumbnail.py's transform_with_references call sites**

In `backend/pipeline/thumbnail.py`, locate each `transform_with_references(...)` call (lines ~193 and ~504; verify with grep). At each site, before the call, build a new image_paths list that includes the style ref, then pass it through:

```python
        style_ref = _resolve_thumbnail_style_ref(script_id)
        existing_image_paths = [<the list/args this call previously used>]
        if style_ref:
            existing_image_paths.append(style_ref)

        result_path = transform_with_references(
            prompt=...,                  # unchanged
            image_paths=existing_image_paths,
            ...,                         # other args unchanged
        )
```

If `script_id` is not in scope at one of the call sites, lift it from the surrounding function arguments — both call sites live inside thumbnail-generation functions that receive `script_id`.

- [ ] **Step 5: Wire style ref into cinematic_chapters.py enhance_split_progression**

In `backend/pipeline/formats/title_cards/cinematic_chapters.py`:

Add the import at the top:

```python
from pipeline.thumbnail import _resolve_thumbnail_style_ref
```

Inside `enhance_split_progression` (find via `grep -n "transform_with_references" cinematic_chapters.py`), modify the image_paths construction:

```python
    image_paths = [str(clean_path)]
    style_ref = _resolve_thumbnail_style_ref(script_id)
    if style_ref:
        image_paths.append(style_ref)

    result_path = transform_with_references(
        prompt=SPLIT_PROGRESSION_PROMPT.format(left_level=left, right_level=right),
        image_paths=image_paths,
        ...,  # other args unchanged
    )
```

Note: chapter-card generation in `cinematic_chapters.py` calls `generate_scene_image` directly — that path already picks up the style ref via Task 4's wiring, so no change is needed there.

- [ ] **Step 6: Run thumbnail tests**

Run: `cd backend && uv run pytest tests/test_thumbnail_with_style_preset.py -v`
Expected: all PASS.

- [ ] **Step 7: Run full backend suite**

Run: `cd backend && uv run pytest -x`
Expected: all PASS.

- [ ] **Step 8: Commit**

```bash
git add backend/pipeline/thumbnail.py backend/pipeline/formats/title_cards/cinematic_chapters.py backend/tests/test_thumbnail_with_style_preset.py
git commit -m "Apply style preset to thumbnails and cinematic split-progression"
```

---

## Task 8: ProjectConfig and script-generation endpoints accept style_preset_enabled

**Files:**
- Modify: `backend/api/project_config.py`
- Modify: `backend/api/scripts.py`
- Modify: `backend/models/project_config.py` (extend `get_or_create_project_config` signature)
- Test: `backend/tests/test_project_config_api.py` (extend)

- [ ] **Step 1: Read the existing project_config.py and scripts.py to see how `eli_enabled` flows**

Run: `grep -n "eli_enabled" backend/api/project_config.py backend/api/scripts.py backend/models/project_config.py`

This shows where to add the parallel `style_preset_enabled` handling.

- [ ] **Step 2: Extend get_or_create_project_config**

In `backend/models/project_config.py`, update the function signature:

```python
def get_or_create_project_config(
    session: Session, script_id: str, *, eli_enabled: bool, style_preset_enabled: bool = True
) -> ProjectConfig:
    """Insert a config row if missing, else return the existing row unchanged."""
    existing = session.exec(
        select(ProjectConfig).where(ProjectConfig.script_id == script_id)
    ).first()
    if existing is not None:
        return existing
    row = ProjectConfig(
        script_id=script_id,
        eli_enabled=eli_enabled,
        style_preset_enabled=style_preset_enabled,
    )
    session.add(row)
    return row
```

- [ ] **Step 3: Write failing test for the new field in the project_config API**

Add to `backend/tests/test_project_config_api.py`:

```python
def test_get_project_config_includes_style_preset_enabled(client):
    # Create a script first via factory or fixture used by other tests in this file
    # ... (re-use the existing pattern)
    response = client.get(f"/api/project-config/{script_id}")
    assert response.status_code == 200
    body = response.json()
    assert "style_preset_enabled" in body
    assert body["style_preset_enabled"] is True


def test_put_project_config_updates_style_preset_enabled(client):
    # ... create a script
    response = client.put(
        f"/api/project-config/{script_id}",
        json={"style_preset_enabled": False},
    )
    assert response.status_code == 200

    response = client.get(f"/api/project-config/{script_id}")
    assert response.json()["style_preset_enabled"] is False
```

> NOTE: Reuse the existing fixture pattern in this file — adapt the factory call to whatever already exists.

- [ ] **Step 4: Run tests and verify they fail**

Run: `cd backend && uv run pytest tests/test_project_config_api.py -v`
Expected: the new tests FAIL.

- [ ] **Step 5: Update project_config.py API endpoint**

In `backend/api/project_config.py`:

- Add `style_preset_enabled: bool` to the response schema (and request schema for PUT).
- Set it from the `ProjectConfig` row in GET handler.
- Accept and persist it in the PUT handler.

Specific edits depend on the file's exact shape — apply in parallel to how `eli_enabled` is handled. Search for `eli_enabled` and add a sibling line for `style_preset_enabled` next to each occurrence.

- [ ] **Step 6: Update scripts.py to accept style_preset_enabled**

In `backend/api/scripts.py`:

- Add `style_preset_enabled: bool | None = None` to the script-generation request schema.
- When creating the ProjectConfig row, pass it through. If omitted, fall back to `AppSettings["STYLE_PRESET_ENABLED_DEFAULT"]`:

```python
# Resolve default from AppSettings if not provided
if req.style_preset_enabled is None:
    style_setting = session.get(AppSetting, "STYLE_PRESET_ENABLED_DEFAULT")
    style_preset_enabled = (style_setting.value if style_setting else "true").lower() == "true"
else:
    style_preset_enabled = req.style_preset_enabled

get_or_create_project_config(
    session,
    script_id=script.id,
    eli_enabled=eli_enabled,
    style_preset_enabled=style_preset_enabled,
)
```

- [ ] **Step 7: Run tests**

Run: `cd backend && uv run pytest tests/test_project_config_api.py tests/test_script_generation_eli_flag.py -v`
Expected: all PASS.

- [ ] **Step 8: Run full backend suite**

Run: `cd backend && uv run pytest -x`
Expected: all PASS.

- [ ] **Step 9: Commit**

```bash
git add backend/api/project_config.py backend/api/scripts.py backend/models/project_config.py backend/tests/test_project_config_api.py
git commit -m "Thread style_preset_enabled through project config + script generation"
```

---

## Task 9: Frontend API client + types + StylePresetContext

**Files:**
- Modify: `frontend/src/api.ts`
- Create: `frontend/src/contexts/StylePresetContext.tsx`
- Modify: `frontend/src/App.tsx`

- [ ] **Step 1: Add types and API functions to api.ts**

In `frontend/src/api.ts`, add the type and the six functions. Place near other domain types:

```ts
export type StylePreset = {
  id: string;
  name: string;
  prompt: string;
  image_url: string;
  created_at: string;
};

export type StylePresetJobStatus = {
  job_id: string;
  status: "pending" | "running" | "completed" | "failed";
  error: string | null;
  preset_id: string | null;
  preset?: StylePreset;
};

export async function listStylePresets(): Promise<StylePreset[]> {
  const res = await fetch(`${API_BASE}/api/style/presets`);
  if (!res.ok) throw new Error("Failed to list style presets");
  return res.json();
}

export async function createStylePreset(
  prompt: string,
  name: string,
): Promise<{ job_id: string }> {
  const res = await fetch(`${API_BASE}/api/style/presets`, {
    method: "POST",
    headers: { "content-type": "application/json" },
    body: JSON.stringify({ prompt, name }),
  });
  if (!res.ok) throw new Error("Failed to create style preset");
  return res.json();
}

export async function getStylePresetJob(jobId: string): Promise<StylePresetJobStatus> {
  const res = await fetch(`${API_BASE}/api/style/presets/jobs/${jobId}`);
  if (!res.ok) throw new Error("Failed to fetch preset job status");
  return res.json();
}

export async function pollStylePresetJob(
  jobId: string,
  onUpdate?: (status: StylePresetJobStatus) => void,
): Promise<StylePreset> {
  while (true) {
    const status = await getStylePresetJob(jobId);
    onUpdate?.(status);
    if (status.status === "completed" && status.preset) return status.preset;
    if (status.status === "failed") {
      throw new Error(status.error || "Preset generation failed");
    }
    await new Promise((r) => setTimeout(r, 1500));
  }
}

export async function deleteStylePreset(id: string): Promise<void> {
  const res = await fetch(`${API_BASE}/api/style/presets/${id}`, { method: "DELETE" });
  if (!res.ok) throw new Error("Failed to delete style preset");
}

export async function getActiveStylePreset(): Promise<StylePreset | null> {
  const res = await fetch(`${API_BASE}/api/style/active`);
  if (!res.ok) throw new Error("Failed to fetch active style preset");
  return res.json();
}

export async function setActiveStylePreset(presetId: string | null): Promise<void> {
  const res = await fetch(`${API_BASE}/api/style/active`, {
    method: "PUT",
    headers: { "content-type": "application/json" },
    body: JSON.stringify({ preset_id: presetId }),
  });
  if (!res.ok) throw new Error("Failed to set active style preset");
}
```

> NOTE: The existing file uses an `API_BASE` or similar constant. Use whatever pattern the file currently uses (Electron IPC fallback or fetch).

- [ ] **Step 2: Create StylePresetContext**

Create `frontend/src/contexts/StylePresetContext.tsx`:

```tsx
import { createContext, useCallback, useContext, useEffect, useState, type ReactNode } from "react";
import { getActiveStylePreset, type StylePreset } from "../api";

type StylePresetContextValue = {
  activePreset: StylePreset | null;
  loading: boolean;
  refresh: () => Promise<void>;
};

const StylePresetContext = createContext<StylePresetContextValue>({
  activePreset: null,
  loading: false,
  refresh: async () => {},
});

export function StylePresetProvider({ children }: { children: ReactNode }) {
  const [activePreset, setActivePreset] = useState<StylePreset | null>(null);
  const [loading, setLoading] = useState(true);

  const refresh = useCallback(async () => {
    setLoading(true);
    try {
      const preset = await getActiveStylePreset();
      setActivePreset(preset);
    } catch (err) {
      console.error("Failed to load active style preset", err);
      setActivePreset(null);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    refresh();
  }, [refresh]);

  return (
    <StylePresetContext.Provider value={{ activePreset, loading, refresh }}>
      {children}
    </StylePresetContext.Provider>
  );
}

export function useStylePreset() {
  return useContext(StylePresetContext);
}
```

- [ ] **Step 3: Wrap App with the provider**

Modify `frontend/src/App.tsx`. Import the provider and wrap the existing root render. Find the top-level component return and add `<StylePresetProvider>` around the existing tree:

```tsx
import { StylePresetProvider } from "./contexts/StylePresetContext";

// inside the App component's return:
return (
  <StylePresetProvider>
    {/* existing tree */}
  </StylePresetProvider>
);
```

- [ ] **Step 4: Verify the frontend still builds**

Run: `cd frontend && npm run build`
Expected: build succeeds with no TypeScript errors.

- [ ] **Step 5: Commit**

```bash
git add frontend/src/api.ts frontend/src/contexts/StylePresetContext.tsx frontend/src/App.tsx
git commit -m "Add style preset frontend client, types, and provider"
```

---

## Task 10: Shared StylePresetToggle component

**Files:**
- Create: `frontend/src/components/shared/StylePresetToggle.tsx`

- [ ] **Step 1: Create the component**

Create `frontend/src/components/shared/StylePresetToggle.tsx`:

```tsx
import type { ReactNode } from "react";

type StylePresetToggleProps = {
  /** Current value of the project's eli_enabled flag (or global default). */
  eliEnabled: boolean;
  /** Current value of the style_preset_enabled flag. */
  enabled: boolean;
  /** Called when user flips the toggle. Ignored when Eli is enabled. */
  onChange: (enabled: boolean) => void;
  /** Name of the active global preset, or null if none is selected. */
  activePresetName: string | null;
};

/**
 * Project-level toggle for "use the active global style preset for this video."
 *
 * - When Eli is enabled, this toggle is forced off and visually greyed out.
 * - When the toggle is on but no preset is active, a warning state is shown.
 * - Inline descriptive text always renders so users see the resulting behavior
 *   *before* flipping the switch.
 */
export function StylePresetToggle({
  eliEnabled,
  enabled,
  onChange,
  activePresetName,
}: StylePresetToggleProps) {
  const greyed = eliEnabled;
  const effectivelyOn = !greyed && enabled;
  const noActivePreset = effectivelyOn && !activePresetName;

  let descriptor: ReactNode;
  if (greyed) {
    descriptor = (
      <span className="text-neutral-500">
        Style presets only apply when Eli is disabled for this video.
      </span>
    );
  } else if (noActivePreset) {
    descriptor = (
      <span className="text-amber-400">
        ⚠ No active preset. Pick one in Settings → Style Presets, or generate a new one.
      </span>
    );
  } else if (effectivelyOn) {
    descriptor = (
      <span className="text-neutral-400">
        Applies the preset across all scenes, frames, thumbnails, and chapter cards.
      </span>
    );
  } else {
    descriptor = (
      <span className="text-neutral-400">No style preset will be used.</span>
    );
  }

  const checkboxState = greyed ? false : enabled;

  return (
    <div
      className={`flex flex-col gap-1 rounded-md border border-neutral-800 bg-neutral-900 p-3 ${
        greyed ? "opacity-60" : ""
      }`}
    >
      <label className="flex items-center gap-2 text-sm font-medium text-neutral-100">
        <input
          type="checkbox"
          checked={checkboxState}
          disabled={greyed}
          onChange={(e) => onChange(e.target.checked)}
          className="h-4 w-4 rounded border-neutral-700 bg-neutral-800 text-violet-500 focus:ring-violet-500"
        />
        <span>Style preset</span>
        {effectivelyOn && activePresetName && (
          <span className="text-xs font-normal text-neutral-400">
            Active: <span className="text-neutral-200">"{activePresetName}"</span>
          </span>
        )}
        {greyed && (
          <span className="text-xs font-normal text-neutral-500">(Eli is on)</span>
        )}
      </label>
      <div className="pl-6 text-xs leading-relaxed">{descriptor}</div>
    </div>
  );
}
```

- [ ] **Step 2: Verify the frontend still builds**

Run: `cd frontend && npm run build`
Expected: build succeeds.

- [ ] **Step 3: Commit**

```bash
git add frontend/src/components/shared/StylePresetToggle.tsx
git commit -m "Add shared StylePresetToggle component with explicit state descriptors"
```

---

## Task 11: Settings → Style Presets section

**Files:**
- Create: `frontend/src/components/settings/StylePresetCreateModal.tsx`
- Create: `frontend/src/components/settings/StylePresetsSection.tsx`
- Modify: `frontend/src/components/settings/SettingsPage.tsx`

- [ ] **Step 1: Create the create-modal component**

Create `frontend/src/components/settings/StylePresetCreateModal.tsx`:

```tsx
import { useState } from "react";
import { createStylePreset, pollStylePresetJob, type StylePreset } from "../../api";

const PROMPT_PLACEHOLDER =
  "A 16:9 reference sheet showing 6 diverse people in different poses, 4 everyday objects, and 2 environments — all in 90s Nickelodeon style with thick outlines and muted earth tones.";

type Props = {
  onClose: () => void;
  onCreated: (preset: StylePreset) => void;
};

export function StylePresetCreateModal({ onClose, onCreated }: Props) {
  const [name, setName] = useState("");
  const [prompt, setPrompt] = useState("");
  const [generating, setGenerating] = useState(false);
  const [previewPreset, setPreviewPreset] = useState<StylePreset | null>(null);
  const [error, setError] = useState<string | null>(null);

  const handleGenerate = async () => {
    if (!prompt.trim()) {
      setError("Prompt is required");
      return;
    }
    setError(null);
    setGenerating(true);
    try {
      const { job_id } = await createStylePreset(prompt, name || "Untitled");
      const preset = await pollStylePresetJob(job_id);
      setPreviewPreset(preset);
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err));
    } finally {
      setGenerating(false);
    }
  };

  const handleSave = () => {
    if (previewPreset) {
      onCreated(previewPreset);
      onClose();
    }
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/60">
      <div className="w-full max-w-2xl rounded-lg border border-neutral-800 bg-neutral-950 p-6 shadow-xl">
        <h2 className="mb-4 text-lg font-semibold text-neutral-100">New style preset</h2>

        <div className="mb-4 space-y-2">
          <label className="block text-xs font-medium text-neutral-400">Name</label>
          <input
            type="text"
            value={name}
            onChange={(e) => setName(e.target.value)}
            placeholder="e.g. Saturday Cartoon"
            className="w-full rounded border border-neutral-700 bg-neutral-900 px-3 py-2 text-sm text-neutral-100 focus:border-violet-500 focus:outline-none"
          />
        </div>

        <div className="mb-2 rounded border border-neutral-800 bg-neutral-900/50 p-3 text-xs text-neutral-400">
          This prompt is sent to Gemini as-is. Tip: include multiple subjects (people, objects, environments) so the reference can guide many kinds of scene generations.
        </div>

        <div className="mb-4 space-y-2">
          <label className="block text-xs font-medium text-neutral-400">Prompt</label>
          <textarea
            value={prompt}
            onChange={(e) => setPrompt(e.target.value)}
            placeholder={PROMPT_PLACEHOLDER}
            rows={5}
            className="w-full rounded border border-neutral-700 bg-neutral-900 px-3 py-2 text-sm text-neutral-100 focus:border-violet-500 focus:outline-none"
          />
        </div>

        {previewPreset && (
          <div className="mb-4">
            <div className="mb-2 text-xs text-neutral-400">Preview</div>
            <img
              src={previewPreset.image_url}
              alt={previewPreset.name}
              className="w-full rounded border border-neutral-700"
            />
          </div>
        )}

        {error && <div className="mb-4 text-sm text-red-400">{error}</div>}

        <div className="flex justify-end gap-2">
          <button
            onClick={onClose}
            className="rounded border border-neutral-700 px-4 py-2 text-sm text-neutral-300 hover:bg-neutral-800 transition-colors"
          >
            Cancel
          </button>
          {previewPreset ? (
            <>
              <button
                onClick={() => {
                  setPreviewPreset(null);
                  handleGenerate();
                }}
                disabled={generating}
                className="rounded border border-neutral-700 px-4 py-2 text-sm text-neutral-300 hover:bg-neutral-800 transition-colors disabled:opacity-50"
              >
                Regenerate
              </button>
              <button
                onClick={handleSave}
                className="rounded bg-violet-600 px-4 py-2 text-sm text-white hover:bg-violet-500 transition-colors"
              >
                Save
              </button>
            </>
          ) : (
            <button
              onClick={handleGenerate}
              disabled={generating || !prompt.trim()}
              className="rounded bg-violet-600 px-4 py-2 text-sm text-white hover:bg-violet-500 transition-colors disabled:opacity-50"
            >
              {generating ? "Generating…" : "Generate"}
            </button>
          )}
        </div>
      </div>
    </div>
  );
}
```

- [ ] **Step 2: Create the settings section component**

Create `frontend/src/components/settings/StylePresetsSection.tsx`:

```tsx
import { useEffect, useState } from "react";
import {
  deleteStylePreset,
  getActiveStylePreset,
  listStylePresets,
  setActiveStylePreset,
  type StylePreset,
} from "../../api";
import { useStylePreset } from "../../contexts/StylePresetContext";
import { StylePresetCreateModal } from "./StylePresetCreateModal";

export function StylePresetsSection() {
  const [presets, setPresets] = useState<StylePreset[]>([]);
  const [activeId, setActiveId] = useState<string | null>(null);
  const [showModal, setShowModal] = useState(false);
  const { refresh: refreshActive } = useStylePreset();

  const loadAll = async () => {
    const [list, active] = await Promise.all([
      listStylePresets(),
      getActiveStylePreset(),
    ]);
    setPresets(list);
    setActiveId(active?.id ?? null);
  };

  useEffect(() => {
    loadAll();
  }, []);

  const handleSetActive = async (id: string | null) => {
    await setActiveStylePreset(id);
    setActiveId(id);
    await refreshActive();
  };

  const handleDelete = async (id: string) => {
    await deleteStylePreset(id);
    if (activeId === id) {
      setActiveId(null);
      await refreshActive();
    }
    await loadAll();
  };

  return (
    <section className="space-y-4">
      <header>
        <h2 className="text-lg font-semibold text-neutral-100">Style Presets</h2>
        <p className="text-sm text-neutral-400">
          A reference image attached to AI image generation. Used to enforce a consistent visual art style across all videos. Only applies when Eli is disabled for a video.
        </p>
      </header>

      <div className="rounded-md border border-neutral-800 bg-neutral-900 p-4">
        <label className="mb-1 block text-xs font-medium text-neutral-400">
          Active preset
        </label>
        <select
          value={activeId ?? ""}
          onChange={(e) => handleSetActive(e.target.value || null)}
          className="w-full rounded border border-neutral-700 bg-neutral-800 px-3 py-2 text-sm text-neutral-100"
        >
          <option value="">None</option>
          {presets.map((p) => (
            <option key={p.id} value={p.id}>{p.name || "Untitled"}</option>
          ))}
        </select>
        <p className="mt-2 text-xs text-neutral-500">
          All non-Eli projects with the style toggle on will use this preset.
        </p>
      </div>

      <div className="grid grid-cols-3 gap-3">
        {presets.map((p) => (
          <div
            key={p.id}
            className={`relative rounded-md border bg-neutral-900 p-3 ${
              p.id === activeId ? "border-violet-500" : "border-neutral-800"
            }`}
          >
            <img
              src={p.image_url}
              alt={p.name}
              className="mb-2 aspect-video w-full rounded object-cover"
            />
            <div className="flex items-center justify-between gap-2">
              <div className="min-w-0 flex-1">
                <div className="truncate text-sm font-medium text-neutral-100">{p.name || "Untitled"}</div>
                <div className="truncate text-xs text-neutral-400" title={p.prompt}>{p.prompt}</div>
              </div>
              {p.id === activeId && (
                <span className="rounded bg-violet-500/20 px-2 py-0.5 text-xs text-violet-300">Active</span>
              )}
            </div>
            <button
              onClick={() => handleDelete(p.id)}
              className="mt-2 w-full rounded border border-red-900 px-2 py-1 text-xs text-red-400 hover:bg-red-950 transition-colors"
            >
              Delete
            </button>
          </div>
        ))}
        <button
          onClick={() => setShowModal(true)}
          className="flex aspect-[4/3] items-center justify-center rounded-md border-2 border-dashed border-neutral-700 text-sm text-neutral-400 hover:border-violet-500 hover:text-violet-400 transition-colors"
        >
          + New preset
        </button>
      </div>

      {showModal && (
        <StylePresetCreateModal
          onClose={() => setShowModal(false)}
          onCreated={async () => {
            await loadAll();
          }}
        />
      )}
    </section>
  );
}
```

- [ ] **Step 3: Add the section to SettingsPage**

Modify `frontend/src/components/settings/SettingsPage.tsx`. Import the new section and render it alongside existing sections (e.g., after `MiscSection`):

```tsx
import { StylePresetsSection } from "./StylePresetsSection";

// inside the render tree:
<StylePresetsSection />
```

Match the existing section spacing/styling pattern in the file.

- [ ] **Step 4: Verify the frontend builds**

Run: `cd frontend && npm run build`
Expected: build succeeds.

- [ ] **Step 5: Commit**

```bash
git add frontend/src/components/settings/StylePresetCreateModal.tsx frontend/src/components/settings/StylePresetsSection.tsx frontend/src/components/settings/SettingsPage.tsx
git commit -m "Add Settings → Style Presets section with create modal"
```

---

## Task 12: Per-project surfaces (Misc default, Ideation, ScriptGeneration, Timeline badge)

**Files:**
- Modify: `frontend/src/components/settings/MiscSection.tsx`
- Modify: `frontend/src/components/script/useScriptGeneration.ts`
- Modify: `frontend/src/components/script/ScriptGenerationPage.tsx`
- Modify: `frontend/src/components/ideation/IdeationPage.tsx`
- Modify: `frontend/src/components/timeline/TimelinePage.tsx`

- [ ] **Step 1: Settings → Misc — add toggle pair for default**

In `frontend/src/components/settings/MiscSection.tsx`, locate where `ELI_ENABLED_DEFAULT` is read/written. Add the parallel toggle for `STYLE_PRESET_ENABLED_DEFAULT`:

- Read `STYLE_PRESET_ENABLED_DEFAULT` from settings (string `"true"`/`"false"` → bool).
- Render the StylePresetToggle next to the existing Eli toggle, with `eliEnabled` bound to the global Eli default. Pass `activePresetName` from `useStylePreset()`.

```tsx
import { useStylePreset } from "../../contexts/StylePresetContext";
import { StylePresetToggle } from "../shared/StylePresetToggle";

// inside the component:
const { activePreset } = useStylePreset();
const stylePresetEnabledDefault = (settings.STYLE_PRESET_ENABLED_DEFAULT ?? "true") === "true";

const handleStyleDefaultChange = async (next: boolean) => {
  await updateSetting("STYLE_PRESET_ENABLED_DEFAULT", next ? "true" : "false");
};

// in the render:
<div className="space-y-2">
  <h3 className="text-sm font-medium text-neutral-200">Default for new projects</h3>
  <p className="text-xs text-neutral-400">
    These defaults apply when you create a new project. They can still be overridden per project.
  </p>
  {/* existing Eli toggle */}
  <StylePresetToggle
    eliEnabled={eliEnabledDefault}
    enabled={stylePresetEnabledDefault}
    onChange={handleStyleDefaultChange}
    activePresetName={activePreset?.name ?? null}
  />
</div>
```

> NOTE: Adapt `updateSetting` and `settings` to whatever the file already uses to read/write AppSettings.

- [ ] **Step 2: useScriptGeneration — add stylePresetEnabled state**

In `frontend/src/components/script/useScriptGeneration.ts`, locate the existing `eliEnabled` / `setEliEnabled` state. Add a parallel pair:

```ts
const [stylePresetEnabled, setStylePresetEnabled] = useState(true);
```

Initialize it from `STYLE_PRESET_ENABLED_DEFAULT` if the hook reads settings on mount (parallel to how `eliEnabled` is initialized).

In the request bodies at lines 317 and 449 (`eli_enabled: eliEnabled,`), add the sibling field:

```ts
style_preset_enabled: stylePresetEnabled,
```

Return `stylePresetEnabled` and `setStylePresetEnabled` from the hook so pages can render the toggle.

- [ ] **Step 3: ScriptGenerationPage — render the toggle next to Eli**

In `frontend/src/components/script/ScriptGenerationPage.tsx`, locate the existing Eli toggle. Add the StylePresetToggle next to it:

```tsx
import { useStylePreset } from "../../contexts/StylePresetContext";
import { StylePresetToggle } from "../shared/StylePresetToggle";

const { activePreset } = useStylePreset();

// in the render, alongside the Eli toggle:
<div className="flex flex-col gap-2 sm:flex-row">
  {/* existing Eli toggle */}
  <StylePresetToggle
    eliEnabled={eliEnabled}
    enabled={stylePresetEnabled}
    onChange={setStylePresetEnabled}
    activePresetName={activePreset?.name ?? null}
  />
</div>
```

- [ ] **Step 4: IdeationPage — same treatment**

In `frontend/src/components/ideation/IdeationPage.tsx`, locate the Eli toggle and add the StylePresetToggle next to it. The state lives in whatever hook/local state IdeationPage already uses for `eli_enabled`. Mirror that for `style_preset_enabled` and include it in any payload the page submits.

- [ ] **Step 5: TimelinePage — add read-only badge**

In `frontend/src/components/timeline/TimelinePage.tsx`, locate the header area (around the existing `eliDisabledForProject` derivation, line ~549). Render a small badge:

```tsx
import { useStylePreset } from "../../contexts/StylePresetContext";

// inside the component:
const { activePreset } = useStylePreset();

// in the JSX header, near other status indicators:
<div className="flex items-center gap-2 text-xs text-neutral-400">
  <span>Eli: {eliDisabledForProject ? "off" : "on"}</span>
  {!eliDisabledForProject ? null : (
    <>
      <span>·</span>
      <span>
        Style:{" "}
        {projectConfig?.style_preset_enabled && activePreset
          ? activePreset.name
          : "off"}
      </span>
    </>
  )}
</div>
```

The badge is informational; it's a navigation aid, not an editor. Optional: wrap with a `<button>` that links to Settings → Style Presets.

- [ ] **Step 6: Verify the frontend builds**

Run: `cd frontend && npm run build`
Expected: build succeeds with no TypeScript errors.

- [ ] **Step 7: Manual smoke test (run dev server)**

Run: `npm run dev`
Then in the running app:
1. Visit Settings → Style Presets → click "+ New preset" → enter prompt → Generate → Save.
2. Set the new preset as Active.
3. Settings → Misc shows the global default toggle pair, both enabled.
4. Visit Ideation page; toggle Eli off; confirm the Style preset toggle becomes interactive and shows the active preset name.
5. Toggle Eli back on; confirm the Style preset toggle greys out with the explanation text.
6. Generate a script with Eli off + style preset on; open the timeline; confirm the badge shows "Eli: off · Style: <preset name>".
7. Generate a scene image; confirm visually it picks up the style.

- [ ] **Step 8: Final commit**

```bash
git add frontend/src/components/settings/MiscSection.tsx frontend/src/components/script/useScriptGeneration.ts frontend/src/components/script/ScriptGenerationPage.tsx frontend/src/components/ideation/IdeationPage.tsx frontend/src/components/timeline/TimelinePage.tsx
git commit -m "Wire style preset toggle into all per-project surfaces"
```

---

## Final Verification

- [ ] **Step 1: Run the full backend test suite**

Run: `cd backend && uv run pytest`
Expected: all PASS.

- [ ] **Step 2: Build the frontend**

Run: `cd frontend && npm run build`
Expected: build succeeds.

- [ ] **Step 3: End-to-end smoke test**

Run: `npm run dev` and exercise the full flow described in Task 12 Step 7.

- [ ] **Step 4: Push to main and run the auto-commit review loop**

Per `CLAUDE.md`, push and dispatch the review subagent. Address any FAIL/WARN findings until LGTM.
