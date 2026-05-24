# Character Asset Service Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a reusable backend character asset service that preserves original character references and produces transparent cropped cutouts for style-preset characters, project sync, and Popup Crop Lab anchors.

**Architecture:** Add a focused `pipeline.character_assets` module that processes a single character source image into a reference/cutout/metadata bundle. Existing character generation remains in `pipeline.main_character`, but delegates copy/process work to the new service. Popup Crop Lab keeps item-sheet cropping local and uses the shared service only for the single anchor character workflow.

**Tech Stack:** Python 3.12, FastAPI, SQLModel, Pillow, Pydantic, React 19, TypeScript, Tailwind 4, pytest via `uv run --project backend pytest`.

---

## File Map

- Create `backend/pipeline/character_assets.py`: single-character reference/cutout processing, metadata, warning heuristics, URL/path helpers.
- Create `backend/tests/test_character_assets.py`: unit tests for chroma removal, trimming, metadata, warnings, and missing-file behavior.
- Modify `backend/models/style_preset_character.py`: add `cutout_image_url` to the DB model and API response.
- Modify `backend/pipeline/main_character.py`: add cutout path helpers, process generated preset characters, copy/repair project cutouts, process project/global variants where needed.
- Modify `backend/api/test_lab.py`: pass through anchor warnings and keep endpoint shape stable.
- Modify `backend/pipeline/test_lab_popup_crop.py`: replace one-off anchor chroma path with the shared character asset service; keep item-sheet helpers unchanged.
- Modify `backend/tests/test_style_preset_characters.py`: assert created/synced characters include cutout URLs/files and repair missing cutouts.
- Modify `backend/tests/test_test_lab.py`: assert Popup Crop Lab anchors use shared service output and warnings.
- Modify `frontend/src/api.ts`: add `cutout_image_url` to `StylePresetCharacter`.
- Modify `frontend/src/types/testLab.ts`: add optional `warnings` fields for popup crop anchor/chroma responses.
- Modify `frontend/src/components/settings/StylePresetsSection.tsx`: optionally show the selected character cutout on a checkerboard preview without replacing the reference-card UI.
- Modify `frontend/src/components/test-lab/PopupCropLab.tsx`: rename anchor preview copy from "Chroma" to "Cutout", display warnings when present, and keep item-sheet copy as chroma-key.
- Modify `AGENTS.md`: add the new convention that original character references and transparent cutouts are both persisted, with references canonical and cutouts derived.

---

### Task 1: Add The Character Asset Processor

**Files:**
- Create: `backend/pipeline/character_assets.py`
- Test: `backend/tests/test_character_assets.py`

- [ ] **Step 1: Write failing processor tests**

Create `backend/tests/test_character_assets.py` with:

```python
from pathlib import Path

import pytest
from PIL import Image


def _save_chroma_character(path: Path) -> None:
    image = Image.new("RGB", (200, 200), (0, 255, 0))
    image.paste((220, 40, 40), (70, 50, 130, 160))
    image.save(path)


def test_process_character_asset_bundle_preserves_reference_and_writes_cutout(tmp_path):
    from pipeline.character_assets import process_character_asset_bundle

    source = tmp_path / "source.png"
    bundle_dir = tmp_path / "bundle"
    _save_chroma_character(source)

    result = process_character_asset_bundle(
        source_path=source,
        output_dir=bundle_dir,
        reference_filename="reference.png",
        cutout_filename="cutout.png",
        prompt_fingerprint="prompt-a",
    )

    assert result.reference_path == bundle_dir / "reference.png"
    assert result.cutout_path == bundle_dir / "cutout.png"
    assert result.metadata_path == bundle_dir / "metadata.json"
    assert result.reference_path.exists()
    assert result.cutout_path.exists()
    assert result.trim_box[0] < 70
    assert result.trim_box[1] < 50
    assert result.trim_box[2] > 130
    assert result.trim_box[3] > 160
    assert result.warnings == []

    with Image.open(result.cutout_path) as cutout:
        assert cutout.mode == "RGBA"
        assert cutout.size[0] < 120
        assert cutout.size[1] < 160
        assert cutout.getpixel((0, 0))[3] == 0


def test_process_character_asset_bundle_records_metadata(tmp_path):
    import json

    from pipeline.character_assets import process_character_asset_bundle

    source = tmp_path / "source.png"
    _save_chroma_character(source)

    result = process_character_asset_bundle(
        source_path=source,
        output_dir=tmp_path / "bundle",
        reference_filename="reference.png",
        cutout_filename="cutout.png",
        prompt_fingerprint="prompt-a",
    )

    metadata = json.loads(result.metadata_path.read_text(encoding="utf-8"))
    assert metadata["version"] == 1
    assert metadata["source_path"] == "reference.png"
    assert metadata["cutout_path"] == "cutout.png"
    assert metadata["prompt_fingerprint"] == "prompt-a"
    assert metadata["background_removal_method"] == "chroma_corner_sample"
    assert metadata["trim_box"] == result.trim_box
    assert len(metadata["source_sha256"]) == 64
    assert len(metadata["cutout_sha256"]) == 64
    assert metadata["warnings"] == []


def test_process_character_asset_bundle_warns_when_alpha_stays_full_frame(tmp_path):
    from pipeline.character_assets import process_character_asset_bundle

    source = tmp_path / "solid.png"
    Image.new("RGB", (160, 120), (255, 0, 0)).save(source)

    result = process_character_asset_bundle(
        source_path=source,
        output_dir=tmp_path / "bundle",
        reference_filename="reference.png",
        cutout_filename="cutout.png",
    )

    assert "cutout_bounds_touch_image_edge" in result.warnings
    assert "cutout_visible_area_large" in result.warnings


def test_process_character_asset_bundle_rejects_missing_source(tmp_path):
    from pipeline.character_assets import process_character_asset_bundle

    with pytest.raises(FileNotFoundError, match="character source image not found"):
        process_character_asset_bundle(
            source_path=tmp_path / "missing.png",
            output_dir=tmp_path / "bundle",
            reference_filename="reference.png",
            cutout_filename="cutout.png",
        )


def test_process_character_asset_bundle_rejects_output_path_collisions(tmp_path):
    from pipeline.character_assets import process_character_asset_bundle

    source = tmp_path / "source.png"
    Image.new("RGB", (200, 200), (0, 255, 0)).save(source)

    with pytest.raises(ValueError, match="output paths must be distinct"):
        process_character_asset_bundle(
            source_path=source,
            output_dir=tmp_path / "bundle",
            reference_filename="reference.png",
            cutout_filename="reference.png",
        )
```

- [ ] **Step 2: Run tests to verify they fail**

Run:

```bash
npm run test:backend -- backend/tests/test_character_assets.py -v
```

Expected: FAIL with `ModuleNotFoundError: No module named 'pipeline.character_assets'`.

- [ ] **Step 3: Implement `pipeline.character_assets`**

Create `backend/pipeline/character_assets.py`:

```python
"""Reusable character reference and cutout asset processing."""

from __future__ import annotations

import hashlib
import json
import logging
import shutil
from dataclasses import dataclass
from pathlib import Path

from PIL import Image

logger = logging.getLogger(__name__)

PROCESSOR_VERSION = 1
DEFAULT_PADDING = 24
DEFAULT_TOLERANCE = 70


@dataclass(frozen=True)
class CharacterAssetResult:
    reference_path: Path
    cutout_path: Path
    metadata_path: Path
    trim_box: list[int]
    warnings: list[str]


def process_character_asset_bundle(
    *,
    source_path: Path,
    output_dir: Path,
    reference_filename: str,
    cutout_filename: str,
    metadata_filename: str = "metadata.json",
    prompt_fingerprint: str = "",
    padding: int = DEFAULT_PADDING,
    tolerance: int = DEFAULT_TOLERANCE,
) -> CharacterAssetResult:
    """Copy a character source image and create a transparent trimmed cutout."""
    if not source_path.exists():
        raise FileNotFoundError(f"character source image not found: {source_path}")

    output_dir.mkdir(parents=True, exist_ok=True)
    reference_path = output_dir / reference_filename
    cutout_path = output_dir / cutout_filename
    metadata_path = output_dir / metadata_filename
    _validate_distinct_output_paths(
        reference_path=reference_path,
        cutout_path=cutout_path,
        metadata_path=metadata_path,
    )

    if source_path.resolve() != reference_path.resolve():
        shutil.copy2(source_path, reference_path)

    logger.info("Processing character cutout from %s", reference_path)
    with Image.open(reference_path) as image:
        rgba = image.convert("RGBA")
        keyed, background_warning = _key_out_chroma_background(rgba, tolerance=tolerance)
        trim_box, warnings = _save_trimmed_cutout(
            keyed,
            cutout_path,
            fallback_image=rgba,
            padding=padding,
        )

    if background_warning:
        warnings.insert(0, background_warning)

    metadata = {
        "version": PROCESSOR_VERSION,
        "source_path": reference_path.name,
        "cutout_path": cutout_path.name,
        "source_sha256": _sha256(reference_path),
        "cutout_sha256": _sha256(cutout_path),
        "prompt_fingerprint": prompt_fingerprint,
        "background_removal_method": "chroma_corner_sample",
        "trim_box": trim_box,
        "padding": padding,
        "warnings": warnings,
    }
    metadata_path.write_text(json.dumps(metadata, indent=2, sort_keys=True), encoding="utf-8")
    if warnings:
        logger.warning("Character cutout warnings for %s: %s", cutout_path, ", ".join(warnings))
    return CharacterAssetResult(
        reference_path=reference_path,
        cutout_path=cutout_path,
        metadata_path=metadata_path,
        trim_box=trim_box,
        warnings=warnings,
    )


def _validate_distinct_output_paths(
    *,
    reference_path: Path,
    cutout_path: Path,
    metadata_path: Path,
) -> None:
    resolved_paths = {
        reference_path.resolve(),
        cutout_path.resolve(),
        metadata_path.resolve(),
    }
    if len(resolved_paths) != 3:
        raise ValueError("character asset output paths must be distinct")


def _save_trimmed_cutout(
    image: Image.Image,
    output_path: Path,
    *,
    fallback_image: Image.Image,
    padding: int,
) -> tuple[list[int], list[str]]:
    bbox = image.getbbox()
    warnings: list[str] = []
    if bbox is None:
        fallback_bbox = fallback_image.getbbox()
        if fallback_bbox is None:
            image.save(output_path)
            return [0, 0, image.width, image.height], ["cutout_visible_area_empty"]
        bbox = fallback_bbox
        image = fallback_image

    left, top, right, bottom = bbox
    padded = [
        max(0, left - padding),
        max(0, top - padding),
        min(image.width, right + padding),
        min(image.height, bottom + padding),
    ]
    visible_area = (right - left) * (bottom - top)
    total_area = image.width * image.height
    if visible_area / total_area < 0.02:
        warnings.append("cutout_visible_area_small")
    if visible_area / total_area > 0.90:
        warnings.append("cutout_visible_area_large")
    if left <= 0 or top <= 0 or right >= image.width or bottom >= image.height:
        warnings.append("cutout_bounds_touch_image_edge")

    image.crop(tuple(padded)).save(output_path)
    return padded, warnings


def _key_out_chroma_background(image: Image.Image, *, tolerance: int) -> tuple[Image.Image, str | None]:
    background, warning = _sample_background_rgb(image)
    data = bytearray(image.tobytes())
    for index in range(0, len(data), 4):
        red, green, blue, alpha = data[index:index + 4]
        distance = ((red - background[0]) ** 2 + (green - background[1]) ** 2 + (blue - background[2]) ** 2) ** 0.5
        if distance <= tolerance:
            data[index + 3] = 0
        else:
            data[index + 3] = alpha
    return Image.frombytes("RGBA", image.size, bytes(data)), warning


def _sample_background_rgb(image: Image.Image) -> tuple[tuple[int, int, int], str | None]:
    corner_size = max(1, min(image.width, image.height, 24))
    corners = [
        image.crop((0, 0, corner_size, corner_size)),
        image.crop((image.width - corner_size, 0, image.width, corner_size)),
        image.crop((0, image.height - corner_size, corner_size, image.height)),
        image.crop((image.width - corner_size, image.height - corner_size, image.width, image.height)),
    ]
    corner_colors: list[tuple[int, int, int]] = []
    all_samples: list[tuple[int, int, int]] = []
    for corner in corners:
        data = corner.convert("RGB").tobytes()
        samples = [(data[index], data[index + 1], data[index + 2]) for index in range(0, len(data), 3)]
        all_samples.extend(samples)
        corner_colors.append(_average_rgb(samples))

    background = _average_rgb(all_samples)
    max_distance = max(_rgb_distance(background, color) for color in corner_colors)
    warning = "background_corner_samples_inconsistent" if max_distance > 45 else None
    return background, warning


def _average_rgb(samples: list[tuple[int, int, int]]) -> tuple[int, int, int]:
    return (
        round(sum(pixel[0] for pixel in samples) / len(samples)),
        round(sum(pixel[1] for pixel in samples) / len(samples)),
        round(sum(pixel[2] for pixel in samples) / len(samples)),
    )


def _rgb_distance(a: tuple[int, int, int], b: tuple[int, int, int]) -> float:
    return ((a[0] - b[0]) ** 2 + (a[1] - b[1]) ** 2 + (a[2] - b[2]) ** 2) ** 0.5


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()
```

- [ ] **Step 4: Run processor tests**

Run:

```bash
npm run test:backend -- backend/tests/test_character_assets.py -v
```

Expected: PASS.

- [ ] **Step 5: Commit**

Run:

```bash
git add backend/pipeline/character_assets.py backend/tests/test_character_assets.py
git commit -m "Add character asset cutout processor"
```

---

### Task 2: Add Cutout URLs To Style Preset Characters

**Files:**
- Modify: `backend/database.py`
- Modify: `backend/models/style_preset_character.py`
- Modify: `backend/pipeline/main_character.py`
- Modify: `backend/tests/test_database_migrations.py`
- Modify: `backend/tests/test_style_preset_characters.py`

- [ ] **Step 1: Write failing model/API assertions**

In `backend/tests/test_style_preset_characters.py`, update `test_create_character_scopes_it_to_the_requested_preset` after `assert created["active"] is True`:

```python
    assert created["reference_image_url"].endswith(f"/characters/{created['id']}.png")
    assert created["cutout_image_url"].endswith(f"/characters/{created['id']}.cutout.png")
```

Also add this assertion after the existing reference file assertion:

```python
    assert (tmp_path / "style" / "presets" / "preset-a" / "characters" / f"{created['id']}.cutout.png").exists()
```

In the same test, replace the existing `fake_tmp.write_bytes(...)` setup with a valid generated image inside `fake_generate`:

```python
    calls: list[dict[str, object]] = []

    def fake_generate(prompt, script_id, style_reference_path):
        from PIL import Image

        fake_tmp = tmp_path / f"generated-character-{len(calls) + 1}.png"
        image = Image.new("RGB", (200, 200), (0, 255, 0))
        image.paste((220, 40, 40), (70, 50, 130, 160))
        image.save(fake_tmp)
        calls.append(
            {
                "prompt": prompt,
                "script_id": script_id,
                "style_reference_path": style_reference_path,
            }
        )
        return str(fake_tmp)
```

- [ ] **Step 2: Run the targeted test to verify it fails**

Run:

```bash
npm run test:backend -- backend/tests/test_style_preset_characters.py::test_create_character_scopes_it_to_the_requested_preset -v
```

Expected: FAIL with `KeyError: 'cutout_image_url'`.

- [ ] **Step 3: Add the response/model field**

In `backend/models/style_preset_character.py`, add `cutout_image_url` to both classes:

```python
class StylePresetCharacter(SQLModel, table=True):
    __tablename__ = "style_preset_characters"

    id: str = Field(primary_key=True)
    style_preset_id: str = Field(index=True)
    name: str = Field(default="")
    appearance: str = Field(default="")
    vibe: str = Field(default="")
    reference_image_url: str = Field(default="")
    cutout_image_url: str = Field(default="")
    created_at: datetime = Field(default_factory=_utcnow)
```

```python
class StylePresetCharacterResponse(BaseModel):
    id: str
    style_preset_id: str
    name: str
    appearance: str
    vibe: str
    reference_image_url: str
    cutout_image_url: str = ""
    created_at: datetime
    active: bool = False
```

- [ ] **Step 4: Add the SQLite migration**

In `backend/database.py`, add a migration for existing dev databases so `style_preset_characters.cutout_image_url` is created when `SQLModel.metadata.create_all()` cannot alter the table:

```python
def _ensure_style_preset_character_cutout_column(engine) -> None:
    with engine.begin() as connection:
        columns = {
            row[1]
            for row in connection.exec_driver_sql("PRAGMA table_info(style_preset_characters)")
        }
        if columns and "cutout_image_url" not in columns:
            connection.exec_driver_sql(
                "ALTER TABLE style_preset_characters ADD COLUMN cutout_image_url VARCHAR NOT NULL DEFAULT ''"
            )
```

Call the helper during database initialization after table creation, and add a migration test in `backend/tests/test_database_migrations.py` that creates the old table shape, runs initialization, and verifies the new column exists with an empty-string default.

- [ ] **Step 5: Add style-preset cutout path helpers and response wiring**

In `backend/pipeline/main_character.py`, add beside `style_preset_character_path`:

```python
def style_preset_character_cutout_path(preset_id: str, character_id: str) -> Path:
    return DATA_DIR / "style" / "presets" / preset_id / "characters" / f"{character_id}.cutout.png"


def style_preset_character_cutout_web_path(preset_id: str, character_id: str) -> str:
    return f"/static/style/presets/{preset_id}/characters/{character_id}.cutout.png"
```

Then update `_style_preset_character_response`:

```python
    cutout_url = character.cutout_image_url
    if not cutout_url and style_preset_character_cutout_path(character.style_preset_id, character.id).exists():
        cutout_url = style_preset_character_cutout_web_path(character.style_preset_id, character.id)
    return StylePresetCharacterResponse(
        id=character.id,
        style_preset_id=character.style_preset_id,
        name=character.name,
        appearance=character.appearance,
        vibe=character.vibe,
        reference_image_url=character.reference_image_url,
        cutout_image_url=cutout_url,
        created_at=character.created_at,
        active=character.id == active_id,
    )
```

- [ ] **Step 6: Process generated style characters through the shared service**

In `backend/pipeline/main_character.py`, update `create_style_preset_character` after `temp_path = _call_style_character_image_generator(...)`:

```python
    import hashlib

    from pipeline.character_assets import process_character_asset_bundle

    final_path = style_preset_character_path(preset_id, character_id)
    final_cutout_path = style_preset_character_cutout_path(preset_id, character_id)
    final_path.parent.mkdir(parents=True, exist_ok=True)
    process_character_asset_bundle(
        source_path=Path(temp_path),
        output_dir=final_path.parent,
        reference_filename=final_path.name,
        cutout_filename=final_cutout_path.name,
        metadata_filename=f"{character_id}.metadata.json",
        prompt_fingerprint=hashlib.sha256(prompt.encode("utf-8")).hexdigest(),
    )
```

Remove the old `shutil.move(temp_path, final_path)` line from this function.

When creating the row, add:

```python
        cutout_image_url=style_preset_character_cutout_web_path(preset_id, character_id),
```

- [ ] **Step 7: Run the targeted test**

Run:

```bash
npm run test:backend -- backend/tests/test_style_preset_characters.py::test_create_character_scopes_it_to_the_requested_preset -v
```

Expected: PASS.

- [ ] **Step 8: Commit**

Run:

```bash
git add backend/database.py backend/models/style_preset_character.py backend/pipeline/main_character.py backend/tests/test_database_migrations.py backend/tests/test_style_preset_characters.py
git commit -m "Add cutout URLs for style preset characters"
```

---

### Task 3: Copy And Repair Project Character Cutouts

**Files:**
- Modify: `backend/pipeline/main_character.py`
- Modify: `backend/api/project_config.py`
- Modify: `backend/tests/test_style_preset_characters.py`
- Modify: `backend/tests/test_project_config_api.py`

- [ ] **Step 1: Write failing project sync tests**

In `backend/tests/test_style_preset_characters.py`, update `test_sync_active_preset_character_to_project` after writing `source_ref`:

```python
    source_cutout = tmp_path / "style" / "presets" / "preset-a" / "characters" / f"{character_id}.cutout.png"
    source_cutout.write_bytes(b"preset-character-cutout")
```

When constructing `StylePresetCharacter`, add:

```python
                cutout_image_url=f"/static/style/presets/preset-a/characters/{character_id}.cutout.png",
```

After `project_ref = ...`, add:

```python
    project_cutout = tmp_path / "projects" / "script-a" / "character" / "cutout.png"
    assert project_cutout.read_bytes() == b"preset-character-cutout"
```

Add a new test below it:

```python
def test_sync_active_preset_character_repairs_missing_project_cutout(
    style_character_engine,
    tmp_path,
    monkeypatch,
):
    from PIL import Image

    from models.project_config import ProjectConfig
    from models.script import Script, ScriptContent
    from models.settings import AppSetting
    from models.style_preset_character import StylePresetCharacter
    from pipeline import main_character

    monkeypatch.setattr(main_character, "DATA_DIR", tmp_path)
    _insert_preset(style_character_engine, tmp_path, "preset-a", "Preset A")

    character_id = "char-a"
    source_ref = tmp_path / "style" / "presets" / "preset-a" / "characters" / f"{character_id}.png"
    source_ref.parent.mkdir(parents=True, exist_ok=True)
    image = Image.new("RGB", (200, 200), (0, 255, 0))
    image.paste((220, 40, 40), (70, 50, 130, 160))
    image.save(source_ref)

    with Session(style_character_engine) as session:
        session.add(
            StylePresetCharacter(
                id=character_id,
                style_preset_id="preset-a",
                name="Mara",
                appearance="short black hair",
                vibe="calm",
                reference_image_url=f"/static/style/presets/preset-a/characters/{character_id}.png",
                cutout_image_url="",
                created_at=datetime.now(timezone.utc),
            )
        )
        session.add(AppSetting(key="ACTIVE_STYLE_PRESET_ID", value="preset-a"))
        session.add(AppSetting(key=main_character.active_style_preset_character_key("preset-a"), value=character_id))
        session.add(
            Script(
                id="script-repair",
                brand_id="default",
                topic_title="Test",
                topic_description="",
                script_json=ScriptContent(title="Test", segments=[]).model_dump_json(),
            )
        )
        session.add(ProjectConfig(script_id="script-repair", eli_enabled=False))
        session.commit()

    with Session(style_character_engine) as session:
        changed = main_character.sync_global_main_character_to_project(session, "script-repair")
        session.commit()

    project_cutout = tmp_path / "projects" / "script-repair" / "character" / "cutout.png"
    assert changed is True
    assert project_cutout.exists()
    with Image.open(project_cutout) as cutout:
        assert cutout.mode == "RGBA"
        assert cutout.size[0] < 120
```

- [ ] **Step 2: Run sync tests to verify failure**

Run:

```bash
npm run test:backend -- backend/tests/test_style_preset_characters.py::test_sync_active_preset_character_to_project backend/tests/test_style_preset_characters.py::test_sync_active_preset_character_repairs_missing_project_cutout -v
```

Expected: FAIL because `data/projects/{script_id}/character/cutout.png` is not created.

- [ ] **Step 3: Add project cutout helpers**

In `backend/pipeline/main_character.py`, add near `character_reference_path`:

```python
def character_cutout_path(script_id: str) -> Path:
    """Absolute path to the project-local transparent character cutout."""
    return DATA_DIR / "projects" / script_id / "character" / "cutout.png"


def character_cutout_web_path(script_id: str) -> str:
    return f"/static/projects/{script_id}/character/cutout.png"
```

- [ ] **Step 4: Add project and global variant cutout helpers**

In `backend/pipeline/main_character.py`, add beside `_reference_variant_path` and `_global_reference_variant_path`:

```python
def _reference_variant_cutout_path(script_id: str, idx: int) -> Path:
    return character_reference_variants_dir(script_id) / f"{idx}.cutout.png"


def _reference_variant_cutout_web_path(script_id: str, idx: int) -> str:
    return f"/static/projects/{script_id}/character/references/{idx}.cutout.png"


def global_character_cutout_path() -> Path:
    return DATA_DIR / "character" / "main" / "cutout.png"


def global_character_cutout_web_path() -> str:
    return "/static/character/main/cutout.png"


def _global_reference_variant_cutout_path(idx: int) -> Path:
    return global_character_reference_variants_dir() / f"{idx}.cutout.png"


def _global_reference_variant_cutout_web_path(idx: int) -> str:
    return f"/static/character/main/references/{idx}.cutout.png"
```

In `list_character_reference_variants`, add the cutout URL when the file exists:

```python
        cutout_path = _reference_variant_cutout_path(script_id, idx)
        variants.append(
            {
                "idx": idx,
                "image_url": _reference_variant_web_path(script_id, idx),
                "cutout_image_url": _reference_variant_cutout_web_path(script_id, idx) if cutout_path.exists() else "",
                "active": idx == active_idx,
            }
        )
```

In `list_global_character_reference_variants`, add the equivalent global field:

```python
        cutout_path = _global_reference_variant_cutout_path(idx)
        variants.append(
            {
                "idx": idx,
                "image_url": _global_reference_variant_web_path(idx),
                "cutout_image_url": _global_reference_variant_cutout_web_path(idx) if cutout_path.exists() else "",
                "active": idx == active_idx,
            }
        )
```

- [ ] **Step 5: Process project/global generated variants**

In `generate_character_reference`, replace the `shutil.move(temp_path, variant_path)` block with:

```python
    import hashlib

    from pipeline.character_assets import process_character_asset_bundle

    process_character_asset_bundle(
        source_path=Path(temp_path),
        output_dir=variant_path.parent,
        reference_filename=variant_path.name,
        cutout_filename=_reference_variant_cutout_path(script_id, idx).name,
        metadata_filename=f"{idx}.metadata.json",
        prompt_fingerprint=hashlib.sha256(prompt.encode("utf-8")).hexdigest(),
    )
```

In `generate_global_character_reference`, replace the `shutil.move(temp_path, variant_path)` block with:

```python
    import hashlib

    from pipeline.character_assets import process_character_asset_bundle

    process_character_asset_bundle(
        source_path=Path(temp_path),
        output_dir=variant_path.parent,
        reference_filename=variant_path.name,
        cutout_filename=_global_reference_variant_cutout_path(idx).name,
        metadata_filename=f"{idx}.metadata.json",
        prompt_fingerprint=hashlib.sha256(prompt.encode("utf-8")).hexdigest(),
    )
```

In `select_character_reference_variant`, after copying the selected variant to `reference.png`, copy or repair the project cutout:

```python
    target_cutout = character_cutout_path(script_id)
    variant_cutout = _reference_variant_cutout_path(script_id, idx)
    if variant_cutout.exists():
        shutil.copy2(variant_cutout, target_cutout)
    else:
        from pipeline.character_assets import process_character_asset_bundle

        process_character_asset_bundle(
            source_path=target,
            output_dir=target.parent,
            reference_filename=target.name,
            cutout_filename=target_cutout.name,
            metadata_filename="metadata.json",
        )
```

In `select_global_character_reference_variant`, after copying the selected variant to `reference.png`, copy or repair the global cutout:

```python
    target_cutout = global_character_cutout_path()
    variant_cutout = _global_reference_variant_cutout_path(idx)
    if variant_cutout.exists():
        shutil.copy2(variant_cutout, target_cutout)
    else:
        from pipeline.character_assets import process_character_asset_bundle

        process_character_asset_bundle(
            source_path=target,
            output_dir=target.parent,
            reference_filename=target.name,
            cutout_filename=target_cutout.name,
            metadata_filename="metadata.json",
        )
```

- [ ] **Step 6: Update project sync to copy or repair cutouts**

In `sync_global_main_character_to_project`, after copying `source_ref` to `target`, add:

```python
    source_cutout = style_preset_character_cutout_path(preset_id, active_character_id)
    target_cutout = character_cutout_path(script_id)
    cutout_missing = not target_cutout.exists()
    target_cutout.parent.mkdir(parents=True, exist_ok=True)
    if source_cutout.exists():
        shutil.copy2(source_cutout, target_cutout)
        if cutout_missing:
            changed = True
    else:
        from pipeline.character_assets import process_character_asset_bundle

        process_character_asset_bundle(
            source_path=target,
            output_dir=target.parent,
            reference_filename=target.name,
            cutout_filename=target_cutout.name,
            metadata_filename="metadata.json",
        )
        changed = True
```

- [ ] **Step 7: Add `main_character_cutout_url` to project config responses**

In `backend/api/project_config.py`, add to `ProjectConfigResponse`:

```python
    main_character_cutout_url: str | None = None
```

Add a helper near the request models:

```python
def _project_character_cutout_url(script_id: str) -> str | None:
    from pipeline.main_character import character_cutout_path, character_cutout_web_path

    return character_cutout_web_path(script_id) if character_cutout_path(script_id).exists() else None
```

In every `ProjectConfigResponse(...)` constructor in this file, add:

```python
        main_character_cutout_url=_project_character_cutout_url(script_id),
```

- [ ] **Step 8: Add API response assertions and valid generated image fixtures**

In `backend/tests/test_project_config_api.py`, find the test that asserts:

```python
assert body["main_character_reference_url"] == "/static/projects/test-cfg-variants/character/reference.png"
```

Add:

```python
assert "main_character_cutout_url" in body
assert body["main_character_cutout_url"] == "/static/projects/test-cfg-variants/character/cutout.png"
assert body["main_character_reference_variants"][0]["cutout_image_url"] == "/static/projects/test-cfg-variants/character/references/2.cutout.png"
```

In the same test, replace the fake image writer:

```python
        path.write_bytes(f"png-{counter['value']}".encode())
```

with:

```python
        from PIL import Image

        image = Image.new("RGB", (200, 200), (0, 255, 0))
        image.paste((220, 40, 40), (70, 50, 130, 160))
        image.save(path)
```

In `test_legacy_global_main_character_endpoints_do_not_sync_to_project`, replace the fake image writer:

```python
        path.write_bytes(f"global-png-{counter['value']}".encode())
```

with the same valid Pillow image block.

After `assert body["main_character_reference_url"] == "/static/character/main/reference.png"`, add:

```python
    assert body["main_character_reference_variants"][0]["cutout_image_url"] == "/static/character/main/references/2.cutout.png"
```

- [ ] **Step 9: Run project config and sync tests**

Run:

```bash
npm run test:backend -- backend/tests/test_style_preset_characters.py backend/tests/test_project_config_api.py -v
```

Expected: PASS.

- [ ] **Step 10: Commit**

Run:

```bash
git add backend/pipeline/main_character.py backend/api/project_config.py backend/tests/test_style_preset_characters.py backend/tests/test_project_config_api.py
git commit -m "Sync project character cutouts"
```

---

### Task 4: Move Popup Crop Lab Anchor To Shared Character Assets

**Files:**
- Modify: `backend/pipeline/test_lab_popup_crop.py`
- Modify: `backend/api/test_lab.py`
- Modify: `backend/tests/test_test_lab.py`

- [ ] **Step 1: Write failing Popup Crop Lab assertions**

In `backend/tests/test_test_lab.py`, update `test_popup_crop_preview_generates_sheet_and_crops_fixed_grid`:

Replace:

```python
    assert (tmp_path / "projects" / "test-lab-popup-crops" / "crop-test" / "crop_01_anchor_character.png").exists()
```

with:

```python
    assert (tmp_path / "projects" / "test-lab-popup-crops" / "crop-test" / "anchor_source.png").exists()
    assert (tmp_path / "projects" / "test-lab-popup-crops" / "crop-test" / "anchor_cutout.png").exists()
    assert (tmp_path / "projects" / "test-lab-popup-crops" / "crop-test" / "anchor_metadata.json").exists()
```

Replace the following `Image.open(...)` path with `anchor_cutout.png`:

```python
    with Image.open(tmp_path / "projects" / "test-lab-popup-crops" / "crop-test" / "anchor_cutout.png") as crop:
```

In `test_popup_crop_split_endpoints_generate_and_chroma_separately`, update FakeChroma URL:

```python
                        "url": "/static/projects/test-lab-popup-crops/split-run/anchor_cutout.png",
                        "raw_url": "/static/projects/test-lab-popup-crops/split-run/anchor_source.png",
```

Update the assertion:

```python
        assert anchor_chroma.json()["crops"][0]["url"].endswith("/anchor_cutout.png")
```

- [ ] **Step 2: Run Popup Crop tests to verify failure**

Run:

```bash
npm run test:backend -- backend/tests/test_test_lab.py::test_popup_crop_preview_generates_sheet_and_crops_fixed_grid backend/tests/test_test_lab.py::test_popup_crop_split_endpoints_generate_and_chroma_separately -v
```

Expected: FAIL because anchor output still uses `crop_01_anchor_character.png`.

- [ ] **Step 3: Update popup crop result models for warnings**

In `backend/pipeline/test_lab_popup_crop.py`, add warnings fields:

```python
class PopupCropResultCrop(BaseModel):
    role: str
    label: str
    url: str
    raw_url: str
    box: list[int]
    trim_box: list[int]
    warnings: list[str] = Field(default_factory=list)
```

```python
class PopupCropAnchorResult(BaseModel):
    run_id: str
    anchor_prompt_used: str
    anchor_source_url: str
    anchor_cutout_url: str | None = None
    warnings: list[str] = Field(default_factory=list)
```

- [ ] **Step 4: Process anchor source with shared service**

In `backend/pipeline/test_lab_popup_crop.py`, replace `_process_anchor_source` with:

```python
def _process_anchor_source(anchor_path: Path, output_dir: Path) -> PopupCropResultCrop:
    from pipeline.character_assets import process_character_asset_bundle

    result = process_character_asset_bundle(
        source_path=anchor_path,
        output_dir=output_dir,
        reference_filename="anchor_source.png",
        cutout_filename="anchor_cutout.png",
        metadata_filename="anchor_metadata.json",
    )
    with Image.open(result.reference_path) as image:
        width, height = image.size
    return PopupCropResultCrop(
        role="anchor",
        label="Anchor character",
        url=_web_url(output_dir.name, "anchor_cutout.png"),
        raw_url=_web_url(output_dir.name, "anchor_source.png"),
        box=[0, 0, width, height],
        trim_box=result.trim_box,
        warnings=result.warnings,
    )
```

Update `generate_popup_crop_anchor` after copying `anchor_source_path`:

```python
    crop = _process_anchor_source(anchor_source_path, output_dir)
```

Return:

```python
    return PopupCropAnchorResult(
        run_id=safe_run_id,
        anchor_prompt_used=composed_anchor_prompt,
        anchor_source_url=_web_url(safe_run_id, "anchor_source.png"),
        anchor_cutout_url=crop.url,
        warnings=crop.warnings,
    )
```

Leave `chroma_popup_crop_anchor` in place for API compatibility, but it now returns the already processed shared-service cutout:

```python
def chroma_popup_crop_anchor(*, run_id: str) -> PopupCropChromaResult:
    safe_run_id = _safe_run_id(run_id)
    output_dir = _output_dir(safe_run_id, create=False)
    crop = _process_anchor_source(output_dir / "anchor_source.png", output_dir)
    return PopupCropChromaResult(run_id=safe_run_id, crops=[crop])
```

- [ ] **Step 5: Keep preview behavior stable**

In `generate_popup_crop_preview`, no caller changes are needed. It still generates anchor and sheet, then returns all crops. Confirm the anchor crop is produced by the shared service because `chroma_popup_crop_anchor` calls `_process_anchor_source`.

- [ ] **Step 6: Run Popup Crop tests**

Run:

```bash
npm run test:backend -- backend/tests/test_test_lab.py::test_popup_crop_preview_generates_sheet_and_crops_fixed_grid backend/tests/test_test_lab.py::test_popup_crop_split_endpoints_generate_and_chroma_separately -v
```

Expected: PASS.

- [ ] **Step 7: Commit**

Run:

```bash
git add backend/pipeline/test_lab_popup_crop.py backend/api/test_lab.py backend/tests/test_test_lab.py
git commit -m "Reuse character asset cutouts in popup crop lab"
```

---

### Task 5: Wire Frontend Types And Previews

**Files:**
- Modify: `frontend/src/api.ts`
- Modify: `frontend/src/types/testLab.ts`
- Modify: `frontend/src/components/settings/StylePresetsSection.tsx`
- Modify: `frontend/src/components/test-lab/PopupCropLab.tsx`

- [ ] **Step 1: Add frontend type fields**

In `frontend/src/api.ts`, update `StylePresetCharacter`:

```ts
export type StylePresetCharacter = {
  id: string;
  style_preset_id: string;
  name: string;
  appearance: string;
  vibe: string;
  reference_image_url: string;
  cutout_image_url: string;
  created_at: string;
  active: boolean;
};
```

In `frontend/src/types/testLab.ts`, update popup crop types:

```ts
export interface PopupCropPreviewCrop {
  role: "anchor" | "item";
  label: string;
  url: string;
  raw_url: string;
  box: number[];
  trim_box: number[];
  warnings?: string[];
}
```

```ts
export interface PopupCropAnchorResult {
  run_id: string;
  anchor_prompt_used: string;
  anchor_source_url: string;
  anchor_cutout_url?: string | null;
  warnings?: string[];
}
```

- [ ] **Step 2: Add selected-character cutout preview**

In `frontend/src/components/settings/StylePresetsSection.tsx`, below the main selected character reference image block, add:

```tsx
                      {viewedCharacter.cutout_image_url && (
                        <div className="grid gap-2 md:grid-cols-2">
                          <div className="rounded-md border border-neutral-800 bg-neutral-950 p-2">
                            <p className="mb-2 text-[11px] font-medium uppercase tracking-wide text-neutral-500">Reference</p>
                            <img
                              src={`${assetUrl(viewedCharacter.reference_image_url)}?t=${characterRefTs}`}
                              alt={`${viewedCharacter.name} reference`}
                              className="aspect-video w-full rounded object-cover"
                            />
                          </div>
                          <div
                            className="rounded-md border border-neutral-800 p-2"
                            style={{
                              backgroundColor: "#171717",
                              backgroundImage:
                                "linear-gradient(45deg, #262626 25%, transparent 25%), linear-gradient(-45deg, #262626 25%, transparent 25%), linear-gradient(45deg, transparent 75%, #262626 75%), linear-gradient(-45deg, transparent 75%, #262626 75%)",
                              backgroundPosition: "0 0, 0 8px, 8px -8px, -8px 0",
                              backgroundSize: "16px 16px",
                            }}
                          >
                            <p className="mb-2 text-[11px] font-medium uppercase tracking-wide text-neutral-500">Cutout</p>
                            <img
                              src={`${assetUrl(viewedCharacter.cutout_image_url)}?t=${characterRefTs}`}
                              alt={`${viewedCharacter.name} cutout`}
                              className="aspect-video w-full rounded object-contain"
                            />
                          </div>
                        </div>
                      )}
```

Keep the existing carousel controls in place; this two-panel detail preview appears below them and gives the user a direct reference-versus-cutout comparison.

- [ ] **Step 3: Rename Popup Crop anchor UI copy and show warnings**

In `frontend/src/components/test-lab/PopupCropLab.tsx`, update the anchor result labels:

```tsx
        <CropPreview title="Source" src={crop.raw_url} alt={`${crop.label} source`} />
        <CropPreview title="Transparent cutout" src={crop.url} alt={crop.label} checkerboard />
```

Below the trim box line in `CropCard`, add:

```tsx
      {crop.warnings && crop.warnings.length > 0 && (
        <div className="mt-2 rounded border border-amber-500/30 bg-amber-500/10 px-2 py-1 text-[11px] text-amber-200">
          {crop.warnings.join(", ")}
        </div>
      )}
```

Update the helper text near the top from:

```tsx
Generate each source first, then run chroma when you want to inspect the cleaned transparent cutouts.
```

to:

```tsx
Generate each source first, then process the transparent cutouts when you want to inspect composition-ready assets.
```

Keep item sheet text that specifically mentions chroma-keying.

- [ ] **Step 4: Run frontend build**

Run:

```bash
cd frontend && npm run build
```

Expected: PASS.

- [ ] **Step 5: Commit**

Run:

```bash
git add frontend/src/api.ts frontend/src/types/testLab.ts frontend/src/components/settings/StylePresetsSection.tsx frontend/src/components/test-lab/PopupCropLab.tsx
git commit -m "Show character cutout assets in the UI"
```

---

### Task 6: Add Project Convention And Full Verification

**Files:**
- Modify: `AGENTS.md`

- [ ] **Step 1: Add the convention**

In `AGENTS.md`, under **Key Patterns**, add:

```markdown
- **Character references keep originals and cutouts**: Character generation workflows persist both the original reference image and a transparent cropped cutout. The original reference remains canonical for image-model reference chaining and human review; the cutout is a derived compositing asset for Popup Crop Lab, Remotion layers, character walk-ons, thumbnails, and other staged visuals. Shared single-character background removal lives in `pipeline.character_assets`; do not add workflow-specific character removebg code.
```

- [ ] **Step 2: Run backend targeted tests**

Run:

```bash
npm run test:backend -- backend/tests/test_character_assets.py backend/tests/test_style_preset_characters.py backend/tests/test_test_lab.py backend/tests/test_project_config_api.py -v
```

Expected: PASS.

- [ ] **Step 3: Run full backend suite**

Run:

```bash
npm run test:backend
```

Expected: PASS.

- [ ] **Step 4: Run frontend build**

Run:

```bash
cd frontend && npm run build
```

Expected: PASS.

- [ ] **Step 5: Commit**

Run:

```bash
git add AGENTS.md
git commit -m "Document character asset convention"
```

- [ ] **Step 6: Push and run delegated review loop**

Follow the repository auto-commit rule:

```bash
git push origin main
```

Then dispatch a delegated code review of the most recent commit on `main` with the required AGENTS.md review prompt. If the review returns `NEEDS CHANGES`, implement every required fix, commit as `fix: address review findings`, push, and repeat delegated review until the verdict is `LGTM`.

---

## Final Verification Checklist

- [ ] `npm run test:backend -- backend/tests/test_character_assets.py backend/tests/test_style_preset_characters.py backend/tests/test_test_lab.py backend/tests/test_project_config_api.py -v` passes.
- [ ] `npm run test:backend` passes.
- [ ] `cd frontend && npm run build` passes.
- [ ] A new style-preset character response includes both `reference_image_url` and `cutout_image_url`.
- [ ] Project sync creates `data/projects/{script_id}/character/reference.png` and `data/projects/{script_id}/character/cutout.png`.
- [ ] Popup Crop Lab anchor output uses `anchor_source.png`, `anchor_cutout.png`, and `anchor_metadata.json`.
- [ ] Popup item-sheet crop behavior still produces fixed-grid item crops.
- [ ] `AGENTS.md` documents the new convention.
