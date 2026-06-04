# Flip-Flop Cutout Animation Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace full-frame flip-flop panels with cropped subject cutouts that alternate ABABAB over the visual canvas color.

**Architecture:** Keep `visual_mode="flipflop"` and `visual_layers`, but make flip-flop layers `asset_kind="cutout"` everywhere. Extract reusable chroma-key trimming into a production helper, add a flip-flop cutout generator beside popup/comparison cutout generation, route all production/Test Lab generation through it, and update Remotion to render flip-flop cutouts centered over the canvas.

**Tech Stack:** Python 3.12/FastAPI/SQLModel/Pillow/Gemini image client, React 19/Vite/TypeScript, Remotion 4, Vitest, pytest via `uv`.

---

## File Map

- Create `backend/pipeline/cutout_chroma.py`: reusable chroma-key and trim helpers currently embedded in Test Lab popup crop code.
- Modify `backend/pipeline/test_lab_popup_crop.py`: import the shared helper instead of owning duplicate keying code.
- Modify `backend/pipeline/visual_treatments.py`: make flip-flop layer defaults cutouts and rename prompt helper to cutout semantics.
- Modify `backend/pipeline/image_gen.py`: add `generate_flipflop_cutouts`, route batch scene visual generation through it, and stop using `generate_visual_layer_panels` for flip-flop.
- Modify `backend/api/visuals.py`: route manual scene visual-layer generation through `generate_flipflop_cutouts`.
- Modify `backend/pipeline/test_lab.py`: make Test Lab fallback flip-flop layers cutouts and use cutout prompt wording.
- Modify `remotion/src/scenes/TreatmentRenderer.tsx`: render flip-flop active layers as centered cutouts, with a static one-layer fallback.
- Modify `frontend/src/components/test-lab/TestLabControls.tsx` and `frontend/src/components/settings/visual-modes/catalog.ts`: update UI/docs copy from full-bleed panels to cropped subject cutouts.
- Modify `backend/prompts/script.py`, `backend/pipeline/visual_mode_policy.py`, `docs/visual-mode-design-guardrails.md`, `AGENTS.md`, and `CLAUDE.md`: align routing/docs with cutout body-language behavior.
- Add/modify backend tests in `backend/tests/test_cutout_chroma.py`, `backend/tests/test_visual_treatments.py`, and image generation/API tests already covering visual layers.
- Modify Remotion tests in `frontend/src/remotion/TreatmentRenderer.test.ts`.
- Modify frontend tests in `frontend/src/components/test-lab/TestLabControls.test.tsx` and visual-mode settings tests if existing assertions mention panels.

---

### Task 1: Extract Reusable Chroma Cutout Helper

**Files:**
- Create: `backend/pipeline/cutout_chroma.py`
- Modify: `backend/pipeline/test_lab_popup_crop.py`
- Test: `backend/tests/test_cutout_chroma.py`

- [ ] **Step 1: Write failing tests for shared chroma trimming**

Create `backend/tests/test_cutout_chroma.py`:

```python
from pathlib import Path

from PIL import Image, ImageDraw

from pipeline.cutout_chroma import save_keyed_trimmed_cutout


def test_save_keyed_trimmed_cutout_removes_corner_sampled_background(tmp_path: Path):
    source = Image.new("RGBA", (120, 90), (0, 255, 0, 255))
    draw = ImageDraw.Draw(source)
    draw.rectangle((40, 25, 75, 65), fill=(200, 20, 20, 255))

    output_path = tmp_path / "cutout.png"

    trim_box = save_keyed_trimmed_cutout(source, output_path, padding=4)

    assert trim_box == [36, 21, 80, 70]
    with Image.open(output_path) as result:
        assert result.mode == "RGBA"
        assert result.size == (44, 49)
        assert result.getbbox() is not None
        assert result.getpixel((0, 0))[3] == 0


def test_save_keyed_trimmed_cutout_handles_empty_cutout(tmp_path: Path):
    source = Image.new("RGBA", (40, 40), (0, 255, 0, 255))
    output_path = tmp_path / "empty.png"

    trim_box = save_keyed_trimmed_cutout(source, output_path)

    assert trim_box == [0, 0, 40, 40]
    with Image.open(output_path) as result:
        assert result.size == (40, 40)
```

- [ ] **Step 2: Run the tests to verify they fail**

Run:

```bash
uv run --project backend pytest backend/tests/test_cutout_chroma.py -q
```

Expected: FAIL with `ModuleNotFoundError: No module named 'pipeline.cutout_chroma'`.

- [ ] **Step 3: Add the shared helper**

Create `backend/pipeline/cutout_chroma.py`:

```python
"""Reusable chroma-key cutout helpers for generated visual layers."""

from __future__ import annotations

from pathlib import Path

from PIL import Image


def save_keyed_trimmed_cutout(
    image: Image.Image,
    output_path: Path,
    *,
    padding: int = 24,
    tolerance: int = 70,
) -> list[int]:
    keyed = key_out_background(image.convert("RGBA"), tolerance=tolerance)
    bbox = keyed.getbbox()
    if bbox is None:
        keyed.save(output_path)
        return [0, 0, keyed.width, keyed.height]

    left, top, right, bottom = bbox
    padded = [
        max(0, left - padding),
        max(0, top - padding),
        min(keyed.width, right + padding),
        min(keyed.height, bottom + padding),
    ]
    keyed.crop(tuple(padded)).save(output_path)
    return padded


def key_out_background(image: Image.Image, *, tolerance: int = 70) -> Image.Image:
    bg = sample_background_rgb(image)
    data = bytearray(image.tobytes())
    for index in range(0, len(data), 4):
        red, green, blue, alpha = data[index:index + 4]
        distance = ((red - bg[0]) ** 2 + (green - bg[1]) ** 2 + (blue - bg[2]) ** 2) ** 0.5
        if distance <= tolerance:
            data[index + 3] = 0
        else:
            data[index + 3] = alpha
    return Image.frombytes("RGBA", image.size, bytes(data))


def sample_background_rgb(image: Image.Image) -> tuple[int, int, int]:
    corner_size = max(1, min(image.width, image.height, 24))
    corners = [
        image.crop((0, 0, corner_size, corner_size)),
        image.crop((image.width - corner_size, 0, image.width, corner_size)),
        image.crop((0, image.height - corner_size, corner_size, image.height)),
        image.crop((image.width - corner_size, image.height - corner_size, image.width, image.height)),
    ]
    samples = []
    for corner in corners:
        data = corner.convert("RGB").tobytes()
        samples.extend((data[index], data[index + 1], data[index + 2]) for index in range(0, len(data), 3))
    red = round(sum(pixel[0] for pixel in samples) / len(samples))
    green = round(sum(pixel[1] for pixel in samples) / len(samples))
    blue = round(sum(pixel[2] for pixel in samples) / len(samples))
    return red, green, blue
```

- [ ] **Step 4: Move Test Lab popup crop to the shared helper**

Modify `backend/pipeline/test_lab_popup_crop.py`:

```python
from pipeline.cutout_chroma import key_out_background, sample_background_rgb, save_keyed_trimmed_cutout
```

Replace `_save_keyed_trimmed_cutout(crop, output_path)` calls with `save_keyed_trimmed_cutout(crop, output_path)`.

Replace local helper bodies with compatibility aliases so existing imports do not break during this task:

```python
def _save_keyed_trimmed_cutout(image: Image.Image, output_path: Path, *, padding: int = 24) -> list[int]:
    return save_keyed_trimmed_cutout(image, output_path, padding=padding)


def _key_out_background(image: Image.Image, *, tolerance: int = 70) -> Image.Image:
    return key_out_background(image, tolerance=tolerance)


def _sample_background_rgb(image: Image.Image) -> tuple[int, int, int]:
    return sample_background_rgb(image)
```

- [ ] **Step 5: Run focused tests**

Run:

```bash
uv run --project backend pytest backend/tests/test_cutout_chroma.py backend/tests/test_test_lab.py -q
```

Expected: PASS.

- [ ] **Step 6: Commit**

```bash
git add backend/pipeline/cutout_chroma.py backend/pipeline/test_lab_popup_crop.py backend/tests/test_cutout_chroma.py
git commit -m "Add shared chroma cutout helper"
```

---

### Task 2: Make Flip-Flop Layer Defaults Cutouts

**Files:**
- Modify: `backend/pipeline/visual_treatments.py`
- Modify: `backend/pipeline/test_lab.py`
- Test: `backend/tests/test_visual_treatments.py`
- Test: `backend/tests/test_test_lab.py`

- [ ] **Step 1: Update tests to expect cutout layers**

In `backend/tests/test_visual_treatments.py`, update `test_analyze_visual_treatments_assigns_flipflop_for_same_subject_micro_action` assertions:

```python
assert len(assignment.visual_layers) == 2
assert [layer.id for layer in assignment.visual_layers] == ["s1_state_a", "s1_state_b"]
assert all(layer.asset_kind == "cutout" for layer in assignment.visual_layers)
for layer in assignment.visual_layers:
    prompt = layer.prompt.lower()
    assert "flip-flop transparent cutout" in prompt
    assert "solid chroma" in prompt
    assert "no full background scene" in prompt
    assert "full-bleed" not in prompt
    assert "framed panel" not in prompt
```

Add a legacy-staleness unit test near the flip-flop tests:

```python
def test_explicit_flipflop_replaces_legacy_panel_layers_with_cutouts():
    scene = scene_with_words("s1", "His hands open and close while he talks.")
    scene.set_visual_mode("flipflop")
    scene.visual_layers = [
        VisualLayer(id="old_a", asset_kind="panel", prompt="Old full frame A"),
        VisualLayer(id="old_b", asset_kind="panel", prompt="Old full frame B"),
    ]
    content = content_with_scenes(scene)

    assignments = analyze_visual_treatments(content, script_id="script-legacy-flipflop")

    assignment = assignments[0]
    assert assignment.visual_mode == "flipflop"
    assert [layer.id for layer in assignment.visual_layers] == ["s1_state_a", "s1_state_b"]
    assert all(layer.asset_kind == "cutout" for layer in assignment.visual_layers)
```

- [ ] **Step 2: Run tests to verify failure**

Run:

```bash
uv run --project backend pytest backend/tests/test_visual_treatments.py::test_analyze_visual_treatments_assigns_flipflop_for_same_subject_micro_action backend/tests/test_visual_treatments.py::test_explicit_flipflop_replaces_legacy_panel_layers_with_cutouts -q
```

Expected: FAIL because current flip-flop layers default to `panel` and prompts say full-bleed.

- [ ] **Step 3: Change flip-flop layer construction and prompt helper**

In `backend/pipeline/visual_treatments.py`, update explicit flip-flop preservation to regenerate when stored layers are missing or not cutouts:

```python
if scene.visual_mode == "flipflop":
    existing_layers = [layer for layer in scene.visual_layers if layer.asset_kind == "cutout"]
    return VisualTreatmentAssignment(
        scene_id=scene.id,
        visual_mode="flipflop",
        reasoning="Scene is explicitly marked for flip-flop cutout rendering.",
        visual_layers=existing_layers if len(existing_layers) >= 2 else _flipflop_layers(scene, _state_b_enter_at(scene, [])),
    )
```

Update `_flipflop_layers`:

```python
def _flipflop_layers(scene: Scene, state_b_enter_at: float) -> list[VisualLayer]:
    return [
        VisualLayer(
            id=f"{scene.id}_state_a",
            asset_kind="cutout",
            prompt=flipflop_cutout_prompt(scene.visual_prompt, scene.narration, "state A"),
            placement="center",
            enter_at_seconds=0.0,
            animation="none",
        ),
        VisualLayer(
            id=f"{scene.id}_state_b",
            asset_kind="cutout",
            prompt=flipflop_cutout_prompt(scene.visual_prompt, scene.narration, "state B"),
            placement="center",
            enter_at_seconds=0.0,
            animation="none",
        ),
    ]
```

Replace `flipflop_panel_prompt` with `flipflop_cutout_prompt`, keeping a backwards-compatible alias for imports until all callers are updated:

```python
def flipflop_cutout_prompt(visual_prompt: str, narration: str, focus: str) -> str:
    base_prompt = visual_prompt.strip() or narration.strip()
    state_direction = (
        "Initial pose or expression before the small movement changes."
        if "a" in focus.lower()
        else "Next compatible pose or expression; keep identity, scale, camera angle, and style consistent with State A."
    )
    return (
        f"Flip-flop transparent cutout for {focus}: {base_prompt}. "
        f"{state_direction} "
        "Generate one isolated human or character subject whenever possible, waist-up or full-body depending on the action. "
        "Use a solid chroma background color that does not appear in the subject. "
        "Keep a clean closed silhouette for automatic cropping. "
        "No full background scene, scenery, split-screen, decorative border, picture frame, mat, white margin, "
        "inset panel, UI chrome, caption box, poster edge, speech bubble, labels, or text."
    )


def flipflop_panel_prompt(visual_prompt: str, narration: str, focus: str) -> str:
    return flipflop_cutout_prompt(visual_prompt, narration, focus)
```

- [ ] **Step 4: Update Test Lab fallback layer prompts**

In `backend/pipeline/test_lab.py`, import `flipflop_cutout_prompt` instead of `flipflop_panel_prompt`, and update flip-flop fallback layers to set `asset_kind="cutout"` and `animation="none"`.

- [ ] **Step 5: Run focused tests**

Run:

```bash
uv run --project backend pytest backend/tests/test_visual_treatments.py backend/tests/test_test_lab.py -q
```

Expected: PASS.

- [ ] **Step 6: Commit**

```bash
git add backend/pipeline/visual_treatments.py backend/pipeline/test_lab.py backend/tests/test_visual_treatments.py backend/tests/test_test_lab.py
git commit -m "Use cutout layers for flip-flop scenes"
```

---

### Task 3: Add Production Flip-Flop Cutout Generation

**Files:**
- Modify: `backend/pipeline/image_gen.py`
- Test: `backend/tests/test_visual_treatments.py` or create `backend/tests/pipeline/test_flipflop_cutout_generation.py`

- [ ] **Step 1: Write tests for the new generator**

Create `backend/tests/pipeline/test_flipflop_cutout_generation.py`:

```python
from pathlib import Path

from PIL import Image

from pipeline import image_gen


def test_generate_flipflop_cutouts_generates_transparent_cutout_layers(monkeypatch, tmp_path: Path):
    generated_paths: list[Path] = []

    def fake_generate_image(*args, **kwargs):
        index = len(generated_paths)
        path = tmp_path / f"source_{index}.png"
        image = Image.new("RGBA", (120, 120), (0, 255, 0, 255))
        for x in range(45, 75):
            for y in range(25 + index * 4, 95 + index * 4):
                if y < 120:
                    image.putpixel((x, y), (20, 20, 220, 255))
        image.save(path)
        generated_paths.append(path)
        return str(path)

    monkeypatch.setattr(image_gen, "generate_image", fake_generate_image)
    monkeypatch.setattr(image_gen, "DATA_DIR", tmp_path)

    layers = [
        {"id": "s1_state_a", "type": "image", "asset_kind": "cutout", "prompt": "State A"},
        {"id": "s1_state_b", "type": "image", "asset_kind": "cutout", "prompt": "State B"},
    ]

    result = image_gen.generate_flipflop_cutouts(
        scene_id="s1",
        layers=layers,
        script_id="script-1",
        scene_prompt="A character talking",
    )

    assert len(result) == 2
    assert all(layer["asset_kind"] == "cutout" for layer in result)
    assert all(layer["image_url"].endswith(".png") for layer in result)
    assert all(layer["visual_source_metadata"]["source_type"] == "flipflop_cutout" for layer in result)
    assert len(generated_paths) == 2
    with Image.open(tmp_path / "projects" / "script-1" / "images" / "s1_state_a_cutout.png") as cutout:
        assert cutout.mode == "RGBA"
        assert cutout.getbbox() is not None
        assert cutout.getpixel((0, 0))[3] == 0


def test_generate_flipflop_cutouts_preserves_non_image_layers(monkeypatch, tmp_path: Path):
    monkeypatch.setattr(image_gen, "DATA_DIR", tmp_path)

    layers = [{"id": "note", "type": "text", "asset_kind": "cutout", "prompt": "ignored"}]

    assert image_gen.generate_flipflop_cutouts("s1", layers, "script-1") == layers
```

- [ ] **Step 2: Run tests to verify failure**

Run:

```bash
uv run --project backend pytest backend/tests/pipeline/test_flipflop_cutout_generation.py -q
```

Expected: FAIL because `generate_flipflop_cutouts` does not exist.

- [ ] **Step 3: Implement `generate_flipflop_cutouts`**

In `backend/pipeline/image_gen.py`, import the helper:

```python
from pipeline.cutout_chroma import save_keyed_trimmed_cutout
```

Add the generator near other visual-layer generators:

```python
def generate_flipflop_cutouts(
    scene_id: str,
    layers: list[dict],
    script_id: str,
    width: int = IMAGE_WIDTH,
    height: int = IMAGE_HEIGHT,
    force: bool = False,
    contains_person: bool = True,
    scene_prompt: str = "",
) -> list[dict]:
    images_dir = DATA_DIR / "projects" / script_id / "images"
    images_dir.mkdir(parents=True, exist_ok=True)

    processed_layers: list[dict] = []
    previous_cutout_source_path: Path | None = None
    for index, layer in enumerate(layers):
        if not isinstance(layer, dict):
            processed_layers.append(layer)
            continue
        if layer.get("type", "image") != "image":
            processed_layers.append(layer)
            continue

        layer_id = str(layer.get("id") or f"{scene_id}_state_{index + 1}")
        prompt = str(layer.get("prompt") or scene_prompt or "").strip()
        if not prompt:
            logger.info("[FLIPFLOP_CUTOUT] skipped empty prompt scene=%s layer=%s", scene_id, layer_id)
            processed_layers.append({**layer, "id": layer_id, "asset_kind": "cutout"})
            continue

        filename = f"{layer_id}_cutout.png"
        source_filename = f"{layer_id}_source.png"
        local_path = images_dir / filename
        source_path = images_dir / source_filename
        prompt_marker = images_dir / f"{filename}.prompt"
        web_path = f"/static/projects/{script_id}/images/{filename}"
        composed_prompt, reference_image_path, style_reference_path = _compose_image_prompt_context(
            visual_prompt=_compose_flipflop_cutout_generation_prompt(prompt, index),
            script_id=script_id,
            contains_person=bool(layer.get("contains_person", contains_person)),
        )
        if index > 0 and previous_cutout_source_path is not None:
            reference_image_path = str(previous_cutout_source_path)
            try:
                mtime = int(previous_cutout_source_path.stat().st_mtime)
                composed_prompt += f"\n[flipflop_cutout_ref:{previous_cutout_source_path}:{mtime}]"
            except OSError:
                pass

        next_layer = dict(layer)
        next_layer["id"] = layer_id
        next_layer["asset_kind"] = "cutout"
        next_layer["animation"] = "none"
        next_layer["enter_at_seconds"] = 0.0
        if not force and local_path.exists() and prompt_marker.exists():
            cached_prompt = prompt_marker.read_text(encoding="utf-8")
            if cached_prompt == composed_prompt:
                logger.info("[FLIPFLOP_CUTOUT] cache hit scene=%s layer=%s", scene_id, layer_id)
                next_layer["image_url"] = web_path
                source_metadata = _read_source_metadata(local_path)
                if source_metadata:
                    next_layer["visual_source_metadata"] = source_metadata
                processed_layers.append(next_layer)
                previous_cutout_source_path = source_path if source_path.exists() else local_path
                continue

        logger.info("[FLIPFLOP_CUTOUT] generating cutout scene=%s layer=%s", scene_id, layer_id)
        tmp_path = generate_image(
            composed_prompt,
            width=width,
            height=height,
            reference_image_path=reference_image_path,
            original_prompt=prompt,
            style_reference_path=style_reference_path,
            script_id=script_id,
        )
        shutil.copyfile(tmp_path, source_path)
        with Image.open(tmp_path) as generated:
            trim_box = save_keyed_trimmed_cutout(generated, local_path)
        metadata = {
            "source_type": "flipflop_cutout",
            "provider": os.environ.get("IMAGE_PROVIDER", "google"),
            "fallback": False,
            "source_path": str(source_path),
            "trim_box": trim_box,
        }
        _write_source_metadata(local_path, metadata)
        prompt_marker.write_text(composed_prompt, encoding="utf-8")
        next_layer["image_url"] = web_path
        next_layer["visual_source_metadata"] = _read_source_metadata(local_path) or metadata
        processed_layers.append(next_layer)
        previous_cutout_source_path = source_path

    return processed_layers
```

Add the prompt composer:

```python
def _compose_flipflop_cutout_generation_prompt(prompt: str, index: int) -> str:
    state_name = "State A" if index <= 0 else "State B"
    continuity = (
        "Create the first pose/state of a two-state cutout animation."
        if index <= 0
        else "Create the second pose/state of the same subject. Use the reference image for identity, style, scale, and crop; only change the mouth, expression, posture, hands, or small action state."
    )
    return "\n".join(
        [
            f"Flip-flop cutout {state_name}.",
            continuity,
            "Generate one isolated human or character subject whenever possible.",
            "Prefer waist-up or full-body framing depending on the action.",
            "Use a solid flat chroma key background across the entire image, preferably bright green unless the subject contains green.",
            "The chroma color must not appear anywhere within the subject.",
            "Keep a crisp closed silhouette with no soft glow, feathering, or color bleed.",
            "No full background scene, scenery, props unless requested, frames, borders, labels, captions, speech bubbles, arrows, or text.",
            "Leave a little empty margin around the subject so automatic trimming does not clip the pose.",
            "",
            "Subject direction:",
            prompt.strip(),
        ]
    ).strip()
```

- [ ] **Step 4: Run focused tests**

Run:

```bash
uv run --project backend pytest backend/tests/pipeline/test_flipflop_cutout_generation.py -q
```

Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add backend/pipeline/image_gen.py backend/tests/pipeline/test_flipflop_cutout_generation.py
git commit -m "Generate flip-flop cutout assets"
```

---

### Task 4: Route All Visual Generation Through Flip-Flop Cutouts

**Files:**
- Modify: `backend/api/visuals.py`
- Modify: `backend/pipeline/image_gen.py`
- Test: add focused tests in existing API/image tests or `backend/tests/test_visuals_api.py`

- [ ] **Step 1: Write routing tests**

Add a unit-level test that monkeypatches `generate_flipflop_cutouts` and verifies `_generate_scene_visual_layers` uses it:

```python
def test_generate_scene_visual_layers_routes_flipflop_to_cutouts(monkeypatch):
    from api import visuals
    from models.script import ScriptContent, Scene, Segment

    calls = []

    def fake_generate_flipflop_cutouts(**kwargs):
        calls.append(kwargs)
        return [{"id": "s1_state_a", "asset_kind": "cutout", "image_url": "/x.png"}]

    monkeypatch.setattr(visuals, "generate_flipflop_cutouts", fake_generate_flipflop_cutouts)
    content = ScriptContent(
        title="Test",
        segments=[
            Segment(
                name="Seg",
                scenes=[
                    Scene(
                        id="s1",
                        narration="His hands open and close.",
                        visual_prompt="A host talking",
                        visual_mode="flipflop",
                        visual_layers=[
                            {"id": "s1_state_a", "asset_kind": "cutout", "prompt": "A"},
                            {"id": "s1_state_b", "asset_kind": "cutout", "prompt": "B"},
                        ],
                    )
                ],
            )
        ],
    )

    result = visuals._generate_scene_visual_layers(
        content=content,
        scene_id="s1",
        script_id="script-1",
        width=1920,
        height=1080,
    )

    assert result == [{"id": "s1_state_a", "asset_kind": "cutout", "image_url": "/x.png"}]
    assert calls[0]["scene_id"] == "s1"
    assert calls[0]["scene_prompt"] == "A host talking"
```

Add a batch test in `backend/tests/pipeline/test_flipflop_cutout_generation.py` or the existing batch tests to assert `_generate_single_scene_visual` calls `generate_flipflop_cutouts` when `visual_mode="flipflop"`.

- [ ] **Step 2: Run tests to verify failure**

Run:

```bash
uv run --project backend pytest backend/tests/test_visuals_api.py backend/tests/pipeline/test_flipflop_cutout_generation.py -q
```

Expected: FAIL until imports/routes are updated.

- [ ] **Step 3: Update API route**

In `backend/api/visuals.py`, import `generate_flipflop_cutouts` from `pipeline.image_gen`, and replace the flip-flop fallback branch:

```python
if treatment == "flipflop":
    return generate_flipflop_cutouts(
        scene_id=scene_id,
        layers=layers,
        script_id=script_id,
        scene_prompt=request_scene_prompt or (scene.visual_prompt if scene is not None else ""),
        width=width,
        height=height,
        contains_person=True,
    )
```

Keep `contains_person=True` for flip-flop because the mode strongly prefers characters/body-language even when the scene has not been classified.

- [ ] **Step 4: Update batch generation route**

In `backend/pipeline/image_gen.py`, in `_generate_single_scene_visual.with_visual_layers`, add a flip-flop branch before `comparison_board`:

```python
elif treatment == "flipflop":
    result["visual_layers"] = generate_flipflop_cutouts(
        scene_id=scene["scene_id"],
        layers=layer_dicts,
        script_id=script_id,
        scene_prompt=str(scene.get("visual_prompt") or ""),
        width=width,
        height=height,
        contains_person=True,
    )
```

Remove flip-flop reliance on `generate_visual_layer_panels`. `generate_visual_layer_panels` may keep generic panel support for non-flip-flop legacy callers.

- [ ] **Step 5: Run focused tests**

Run:

```bash
uv run --project backend pytest backend/tests/test_visuals_api.py backend/tests/pipeline/test_flipflop_cutout_generation.py backend/tests/test_visual_treatments.py -q
```

Expected: PASS.

- [ ] **Step 6: Commit**

```bash
git add backend/api/visuals.py backend/pipeline/image_gen.py backend/tests/test_visuals_api.py backend/tests/pipeline/test_flipflop_cutout_generation.py
git commit -m "Route flip-flop generation through cutouts"
```

---

### Task 5: Render Flip-Flop As Centered Cutouts

**Files:**
- Modify: `remotion/src/scenes/TreatmentRenderer.tsx`
- Modify: `frontend/src/remotion/TreatmentRenderer.test.ts`

- [ ] **Step 1: Update Remotion tests**

In `frontend/src/remotion/TreatmentRenderer.test.ts`, change flip-flop active layer test to use `itemLayer`, not `panelLayer`:

```ts
const layers = [
  { ...itemLayer("state-a"), enter_at_seconds: 0 },
  { ...itemLayer("state-b"), enter_at_seconds: 2.1 },
];
```

Add:

```ts
describe("flipflopLayerFrameStyle", () => {
  it("renders flip-flop cutouts centered over the canvas", () => {
    const style = flipflopLayerFrameStyle(itemLayer("state-a"));

    expect(style.position).toBe("absolute");
    expect(style.left).toBe("50%");
    expect(style.top).toBe("50%");
    expect(style.width).toBe(760);
    expect(style.height).toBe(820);
    expect(String(style.transform)).toContain("translate(-50%, -50%)");
    expect(style.inset).toBeUndefined();
  });
});
```

Update the import list to include `flipflopLayerFrameStyle`.

- [ ] **Step 2: Run tests to verify failure**

Run:

```bash
cd frontend && npm run test -- src/remotion/TreatmentRenderer.test.ts
```

Expected: FAIL because `flipflopLayerFrameStyle` is not exported.

- [ ] **Step 3: Implement flip-flop cutout layout**

In `remotion/src/scenes/TreatmentRenderer.tsx`, add:

```ts
export const flipflopLayerFrameStyle = (layer: VisualLayer): React.CSSProperties => {
  if (layer.asset_kind !== "cutout") {
    return layerFrameStyle(layer);
  }
  return {
    position: "absolute",
    left: "50%",
    top: "50%",
    width: 760,
    height: 820,
    transform: "translate(-50%, -50%)",
    transformOrigin: "center",
  };
};
```

Update `Flipflop` to use the helper:

```tsx
<div style={flipflopLayerFrameStyle(activeLayer)}>
```

Keep the existing single valid layer behavior: `flipflopActiveLayer` already returns the only layer for every interval when `layers.length === 1`.

- [ ] **Step 4: Run focused frontend tests**

Run:

```bash
cd frontend && npm run test -- src/remotion/TreatmentRenderer.test.ts
```

Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add remotion/src/scenes/TreatmentRenderer.tsx frontend/src/remotion/TreatmentRenderer.test.ts
git commit -m "Render flip-flop as canvas cutouts"
```

---

### Task 6: Tighten Routing, Prompts, UI Copy, And Docs

**Files:**
- Modify: `backend/prompts/script.py`
- Modify: `backend/pipeline/visual_mode_policy.py`
- Modify: `frontend/src/components/test-lab/TestLabControls.tsx`
- Modify: `frontend/src/components/settings/visual-modes/catalog.ts`
- Modify: `docs/visual-mode-design-guardrails.md`
- Modify: `AGENTS.md`
- Modify: `CLAUDE.md`
- Test: `backend/tests/pipeline/test_scriptwriter_visual_beats.py`
- Test: `backend/tests/pipeline/test_visual_mode_policy.py`
- Test: `frontend/src/components/test-lab/TestLabControls.test.tsx`
- Test: `frontend/src/components/settings/visual-modes/VisualModesSection.test.tsx` if copy assertions need updates

- [ ] **Step 1: Update prompt/policy tests first**

In `backend/tests/pipeline/test_scriptwriter_visual_beats.py`, strengthen the flip-flop test:

```python
def test_script_prompt_defines_flipflop_as_cutout_body_language_not_contrast():
    prompt_text = script_prompt.SCRIPT_SYSTEM.template

    assert '"flipflop"' in prompt_text
    assert "cropped subject" in prompt_text
    assert "body-language" in prompt_text
    assert "Do not use flipflop merely because a sentence contrasts" in prompt_text
```

In `backend/tests/pipeline/test_visual_mode_policy.py`, assert opportunity guidance mentions cutouts/body-language:

```python
def test_flipflop_policy_prefers_character_body_language():
    text = prompt_visual_opportunity_guidance(projected_scene_count=20)

    assert "cropped subject" in text
    assert "body-language" in text
    assert "conceptual" in text
```

- [ ] **Step 2: Run tests to verify failure**

Run:

```bash
uv run --project backend pytest backend/tests/pipeline/test_scriptwriter_visual_beats.py backend/tests/pipeline/test_visual_mode_policy.py -q
```

Expected: FAIL until wording is updated.

- [ ] **Step 3: Update backend prompt and policy wording**

Update the flip-flop lines in `backend/prompts/script.py` to use:

```text
- "flipflop" — When one human/character subject can read as cropped-subject micro-animation by alternating two compatible body-language/action states over the canvas: talking mouth changes, head tilt, hand gesture, pointing, leaning, shrugging, pacing, holding an object, opening/closing, typing, stirring, sorting, or counting. Strongly prefer character or human body language. Do not use flipflop merely because a sentence contrasts two ideas, time periods, emotional states, locations, or outcomes.
```

Update short format-specific references from “same-subject A/B micro-animation” to “cropped-subject character/body-language A/B micro-animation.”

In `backend/pipeline/visual_mode_policy.py`, update the flip-flop `purpose`, `opportunity_cues`, and `avoid_when`:

```python
purpose="Cropped-subject character/body-language A/B micro-animation using compatible transparent cutout states.",
opportunity_cues=(
    "talking mouth or expression changes",
    "head tilt or nodding",
    "hand gesture or pointing",
    "character leaning or shrugging",
    "explicit object action held by a person",
),
avoid_when=("contrast is only conceptual", "subjects are unrelated", "full environments change", "a true side-by-side comparison is needed"),
```

- [ ] **Step 4: Update UI/docs copy**

In `frontend/src/components/test-lab/TestLabControls.tsx`, change flip-flop description to:

```ts
description: "Generates two cropped character/body-language states that alternate over the canvas.",
bestFor: "Talking mouth changes, nodding, pointing, leaning, shrugging, and simple character actions.",
```

In `frontend/src/components/settings/visual-modes/catalog.ts`, change long description/routing to say cropped transparent cutouts over canvas, not full-bleed panels.

In `docs/visual-mode-design-guardrails.md`, replace the flip-flop section with:

```markdown
Use for same-subject cropped A/B micro-animation where compatible transparent character/body-language cutouts alternate from frame zero over the static canvas.

Do not use it for generic contrast between different ideas, time periods, unrelated emotional states, or full-environment changes. Prefer character/human body language; object-only flip-flops require explicit object-action narration.
```

In `AGENTS.md` and `CLAUDE.md`, replace the flip-flop convention with the same cropped cutout contract. Also update the “full-screen from frame zero” convention to “cutouts alternate from frame zero over canvas.”

- [ ] **Step 5: Run focused tests**

Run:

```bash
uv run --project backend pytest backend/tests/pipeline/test_scriptwriter_visual_beats.py backend/tests/pipeline/test_visual_mode_policy.py -q
cd frontend && npm run test -- src/components/test-lab/TestLabControls.test.tsx src/components/settings/visual-modes/VisualModesSection.test.tsx
```

Expected: PASS.

- [ ] **Step 6: Commit**

```bash
git add backend/prompts/script.py backend/pipeline/visual_mode_policy.py frontend/src/components/test-lab/TestLabControls.tsx frontend/src/components/settings/visual-modes/catalog.ts docs/visual-mode-design-guardrails.md AGENTS.md CLAUDE.md backend/tests/pipeline/test_scriptwriter_visual_beats.py backend/tests/pipeline/test_visual_mode_policy.py frontend/src/components/test-lab/TestLabControls.test.tsx frontend/src/components/settings/visual-modes/VisualModesSection.test.tsx
git commit -m "Update flip-flop cutout mode guidance"
```

---

### Task 7: Block Jitter-Prone Whole-Scene FX For Flip-Flop

**Files:**
- Modify: `remotion/src/scenes/SceneRenderer.tsx`
- Modify: `backend/pipeline/fx_generator.py`
- Test: `frontend/src/remotion/SceneRenderer.test.ts`
- Test: `backend/tests/test_fx_transition_defaults.py` or existing FX tests

- [ ] **Step 1: Update tests**

In `frontend/src/remotion/SceneRenderer.test.ts`, add:

```ts
expect(canApplyWholeSceneFx({ visual_mode: "flipflop" })).toBe(false);
```

In the backend FX test covering blocked visual modes, add:

```python
assert "flipflop" in _CAMERA_FX_BLOCKED_VISUAL_MODES
```

If `_CAMERA_FX_BLOCKED_VISUAL_MODES` is not imported in existing tests, add a focused test in `backend/tests/test_fx_transition_defaults.py` importing it from `pipeline.fx_generator`.

- [ ] **Step 2: Run tests to verify failure**

Run:

```bash
cd frontend && npm run test -- src/remotion/SceneRenderer.test.ts
uv run --project backend pytest backend/tests/test_fx_transition_defaults.py -q
```

Expected: FAIL until flip-flop is added to blocked sets.

- [ ] **Step 3: Add flip-flop to blocked sets**

In `remotion/src/scenes/SceneRenderer.tsx`:

```ts
const WHOLE_SCENE_FX_BLOCKED_VISUAL_MODES = new Set(["comparison_board", "popup_sequence", "flipflop"]);
```

In `backend/pipeline/fx_generator.py`:

```python
_CAMERA_FX_BLOCKED_VISUAL_MODES = {"comparison_board", "popup_sequence", "flipflop"}
```

- [ ] **Step 4: Run focused tests**

Run:

```bash
cd frontend && npm run test -- src/remotion/SceneRenderer.test.ts
uv run --project backend pytest backend/tests/test_fx_transition_defaults.py -q
```

Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add remotion/src/scenes/SceneRenderer.tsx backend/pipeline/fx_generator.py frontend/src/remotion/SceneRenderer.test.ts backend/tests/test_fx_transition_defaults.py
git commit -m "Block whole-scene FX for flip-flop cutouts"
```

---

### Task 8: Final Verification And Review Loop

**Files:**
- Modify: any file touched by a verification failure. Do not edit files when verification is already passing.

- [ ] **Step 1: Run backend tests**

Run:

```bash
npm run test:backend
```

Expected: PASS.

- [ ] **Step 2: Run frontend tests**

Run:

```bash
npm run test:frontend
```

Expected: PASS.

- [ ] **Step 3: Run frontend build**

Run:

```bash
cd frontend && npm run build
```

Expected: PASS.

- [ ] **Step 4: Inspect git status**

Run:

```bash
git status --short
```

Expected: only intentional changes are present, with no generated runtime assets staged.

- [ ] **Step 5: Commit final fixes if verification required edits**

If verification required edits, inspect the changed file list and stage exactly those intentional files. Example for a backend-only verification fix:

```bash
git add backend/pipeline/image_gen.py backend/tests/pipeline/test_flipflop_cutout_generation.py
git commit -m "Fix flip-flop cutout verification issues"
```

- [ ] **Step 6: Run the project auto-commit review loop**

Follow `AGENTS.md`: push `main`, dispatch delegated review for the most recent commit, apply all FAIL/WARN findings that are not optional, commit fixes as `fix: address review findings`, push, and repeat until the review verdict is LGTM.

Use the required review prompt exactly:

```text
Review the most recent commit on the main branch of this project.
Run `git diff HEAD~1..HEAD` to see the changes and `git show --stat HEAD` for context.
Read the full affected files (not just the diff) to understand surrounding code.
Check for: correctness bugs, error handling gaps, security issues, naive/aware datetime mismatches, unhandled promise rejections, race conditions, and style problems.
Return a structured verdict: either LGTM or NEEDS CHANGES.
If NEEDS CHANGES, provide a numbered list of findings with severity (FAIL/WARN), file:line, and a specific description of what's wrong and how to fix it.
```

Expected: final delegated review verdict is LGTM before summarizing to the user.
