# Split-Progression Thumbnail Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace the cinematic-chapters thumbnail (single iconic image + Pillow title overlay) with a Gemini-enhanced "split-progression" thumbnail showing two contrasting levels with diagonal divider and "LEVEL X" / "LEVEL Y" labels — without adding any net Gemini calls.

**Architecture:** Reuse the existing `cinematic_thumbnail_clean.png` Gemini call as both the level 1 chapter card image and the source for the new split-progression enhancement. Drop the Pillow title overlay step entirely (no title text on thumbnail). Skip Claude generation of `levels[0].image_prompt` since it's redundant with `cinematic_thumbnail_prompt`. Persist random level pair selection to a sidecar so re-renders stay consistent.

**Tech Stack:** Python 3.12, FastAPI, Pillow, Gemini (`google-genai` via existing `transform_with_references` helper), pytest, SQLModel.

**Spec:** `docs/superpowers/specs/2026-05-20-split-progression-thumbnail-design.md`

---

## File Structure

| File | Change |
|---|---|
| `backend/prompts.py` | Add `SPLIT_PROGRESSION_PROMPT` constant (Task 1). Update `LIFE_AS_A_OUTLINE_INSTRUCTIONS` and `LIFE_AS_A_SCRIPT_SYSTEM` so Claude no longer emits `image_prompt` for level 1 (Task 6). |
| `backend/models/script.py` | `LevelMeta.image_prompt: str = ""` (default empty, optional) (Task 6). |
| `backend/pipeline/thumbnail.py` | Add `enhance_split_progression()` and `_pick_level_pair()` + sidecar helpers (Task 3, 4). Remove now-unused `composite_title_overlay()` (Task 5). |
| `backend/pipeline/formats/title_cards/cinematic_chapters.py` | Rewrite `prepare_thumbnail` (Task 7). Update `_thumbnail_paths` (Task 7). |
| `backend/pipeline/formats/life_as_a.py` | Update `enforce_life_as_a_constraints` to fall back to `cinematic_thumbnail_prompt` when `levels[0].image_prompt` is empty (Task 6). |
| `backend/tests/pipeline/test_thumbnail.py` | Add tests for level pair selection, sidecar persistence, fallback, and prompt templating (Tasks 2, 3, 4). |
| `backend/tests/pipeline/test_cinematic_chapters_strategy.py` | New file — tests for the rewritten `prepare_thumbnail` (Task 8). |
| `backend/tests/pipeline/test_formats_registry.py` | Update existing test to match new behavior (Task 6). |

---

## Task 1: Add `SPLIT_PROGRESSION_PROMPT` constant

**Files:**
- Modify: `backend/prompts.py` (add new constant near `IMAGE_CTR_EXPRESSION_GUIDANCE`)

- [ ] **Step 1: Locate the existing `IMAGE_CTR_EXPRESSION_GUIDANCE` definition**

Run: `grep -n "IMAGE_CTR_EXPRESSION_GUIDANCE = register" backend/prompts.py`

Note the line number — add the new constant immediately after this block ends.

- [ ] **Step 2: Add `SPLIT_PROGRESSION_PROMPT` constant**

Add this constant in `backend/prompts.py` (placement: directly after `IMAGE_CTR_EXPRESSION_GUIDANCE`'s `register(...)` block):

```python
SPLIT_PROGRESSION_PROMPT = register(PromptDef(
    name="SPLIT_PROGRESSION_PROMPT",
    domain="IMAGE",
    purpose="Transform a single iconic life-as-a thumbnail into a split-progression thumbnail (LEVEL X vs LEVEL Y).",
    target_model="gemini",
    expected_output_format="A single PNG image (1920x1080) — the final thumbnail.",
    template="""\
You are an elite YouTube thumbnail redesign artist specializing in HIGH CTR transformation thumbnails.

Your task is to transform the uploaded thumbnail into a dramatically improved "split progression" thumbnail while preserving the original topic and branding style.

CORE GOAL:
Create a thumbnail that instantly communicates:
- progression
- escalation
- transformation
- contrast
- consequences
- curiosity

The final thumbnail should feel optimized for viral YouTube CTR.

IMPORTANT:
The progression does NOT always need to become "better."

Depending on the topic, the progression may become:
- more successful
- more dangerous
- more depressing
- more chaotic
- more extreme
- more wealthy
- more addicted
- more powerful
- more unstable
- more luxurious
- more miserable
- more intense

The right side should represent the MOST EXTREME or MOST ADVANCED version of the topic — not automatically the "best" version.

Examples:
- "Every Level of Software Engineer" → right side may feel elite/successful.
- "Every Level of Drug Addiction" → right side may feel dark/destructive/chaotic.
- "Every Level of Prison" → right side may feel dangerous/intimidating.
- "Every Level of Wealth" → right side may feel luxurious/powerful.
- "Every Level of Burnout" → right side may feel exhausted/collapsed.

The emotional direction should match the topic.

========================
LAYOUT RULES
========================

1. Convert the thumbnail into a TWO-SIDED SPLIT DESIGN.

2. Use a DRAMATIC DIAGONAL DIVIDER through the middle.
- NOT vertical.
- The diagonal should create motion and tension.
- Add glow/light along the divider.

3. Each side must have its own label:
- Left side: "LEVEL {left_level}"
- Right side: "LEVEL {right_level}"

These labels should:
- be huge
- bold
- simple
- instantly readable

========================
TEXT MINIMALISM (CRITICAL)
========================

IMPORTANT:
Do NOT include the full video title in the thumbnail unless absolutely necessary.

Prefer minimal text.

The thumbnail should rely primarily on:
- visual storytelling
- emotional contrast
- progression
- curiosity

Use only:
- "LEVEL {left_level}"
- "LEVEL {right_level}"
- and optionally ONE very short supporting phrase if it significantly improves clarity.

Prioritize larger visuals and cleaner composition over extra text.

========================
LEFT SIDE RULES (LEVEL {left_level})
========================

The left side should represent:
- the beginner / earlier-progression stage
- lower intensity
- earlier progression
- less experience
- less extreme conditions

This can mean:
- weaker
- poorer
- happier
- more innocent
- less skilled
- less corrupted
- less dangerous
- less advanced

depending on the topic.

Use environmental storytelling to communicate the difference instantly.

========================
RIGHT SIDE RULES (LEVEL {right_level})
========================

The right side should represent:
- the more advanced stage
- the peak version
- the extreme outcome
- the highest intensity state shown

The emotional tone depends entirely on the topic.

If the topic is aspirational:
- make the right side feel elite, luxurious, successful, powerful.

If the topic is destructive:
- make the right side feel chaotic, dangerous, depressing, unstable, dark, or tragic.

If the topic is absurd/funny:
- exaggerate the chaos and humor dramatically.

The right side should ALWAYS feel:
- more intense
- more emotionally charged
- more visually dramatic
than the left side.

EXAGGERATE for CTR.
Do not aim for realism.
Aim for emotional impact.

========================
VISUAL CONTRAST RULES
========================

The two sides should feel dramatically different using:
- lighting
- color palette
- facial expression
- environment
- composition
- posture
- atmosphere
- props
- clothing
- energy level

Examples:
- calm vs chaotic
- clean vs dirty
- poor vs rich
- hopeful vs hopeless
- small vs dominant
- relaxed vs overwhelmed
- normal vs insane

The contrast should be understandable instantly without needing to read.

========================
CTR OPTIMIZATION RULES
========================

The thumbnail must:
- be readable at tiny mobile sizes
- have extremely clear focal points
- create instant curiosity
- feel emotionally intense
- communicate progression instantly
- look visually "expensive"
- tell a story in under 1 second

Prioritize:
1. readability
2. emotional contrast
3. curiosity
4. simplicity
5. visual storytelling

Avoid:
- clutter
- tiny details
- flat lighting
- weak contrast
- realistic dullness
- excessive text

========================
STYLE RULES
========================

Style should resemble:
- modern viral YouTube thumbnails
- documentary/commentary channels
- transformation/progression content
- highly polished digital illustration

Use:
- cinematic lighting
- dramatic shadows
- glow effects
- strong rim lighting
- high saturation
- sharp contrast
- dynamic composition

Faces and subjects should be:
- larger
- clearer
- more expressive
- instantly recognizable

========================
IMPORTANT
========================

Do NOT simply split the original image in half.

Completely REIMAGINE both sides so they feel like:
- early stage vs extreme stage
- beginner vs advanced
- before vs after
- normal vs transformed

while still clearly belonging to the same overall world/topic.

The final thumbnail should immediately make viewers think:
"What happened between Level {left_level} and Level {right_level}?"
""",
    retention=RetentionMeta(
        goal="Maximize CTR through split-progression thumbnails for life-as-a videos",
        failure_mode="Mundane single-image thumbnails with title text that bury the progression hook",
        metrics_to_watch=["thumbnail_ctr"],
    ),
))
```

- [ ] **Step 3: Verify the constant imports cleanly**

Run: `cd backend && uv run python -c "from prompts import SPLIT_PROGRESSION_PROMPT; print(SPLIT_PROGRESSION_PROMPT.template.format(left_level=1, right_level=4)[:200])"`

Expected: prints the first 200 chars of the formatted prompt with `LEVEL 1` and `LEVEL 4` substituted. No exceptions.

- [ ] **Step 4: Commit**

```bash
git add backend/prompts.py
git commit -m "Add SPLIT_PROGRESSION_PROMPT for life-as-a thumbnail enhancement"
```

---

## Task 2: Test for `_pick_level_pair` selection logic

**Files:**
- Modify: `backend/tests/pipeline/test_thumbnail.py`

- [ ] **Step 1: Write failing tests for level pair selection**

Append to `backend/tests/pipeline/test_thumbnail.py`:

```python
import pytest

from pipeline.thumbnail import _pick_level_pair


def test_pick_level_pair_two_levels_is_deterministic():
    # N == 2 → only valid pair is (1, 2)
    assert _pick_level_pair(2) == (1, 2)


def test_pick_level_pair_three_levels_yields_valid_pair():
    # N == 3 → valid pairs: (1,2), (1,3), (2,3) — all have left < right and both in [1, 3]
    for _ in range(50):
        left, right = _pick_level_pair(3)
        assert 1 <= left < right <= 3
        assert (left, right) in {(1, 2), (1, 3), (2, 3)}


def test_pick_level_pair_four_levels_uses_endpoints():
    # N == 4 → left ∈ {1, 2}, right ∈ {3, 4}, left < right
    seen: set[tuple[int, int]] = set()
    for _ in range(200):
        pair = _pick_level_pair(4)
        seen.add(pair)
        left, right = pair
        assert left in {1, 2}
        assert right in {3, 4}
        assert left < right
    # Over 200 trials all 4 combinations should appear
    assert seen == {(1, 3), (1, 4), (2, 3), (2, 4)}


def test_pick_level_pair_seven_levels_uses_endpoints():
    # N == 7 → left ∈ {1, 2}, right ∈ {6, 7}, left < right
    for _ in range(50):
        left, right = _pick_level_pair(7)
        assert left in {1, 2}
        assert right in {6, 7}
        assert left < right


def test_pick_level_pair_one_level_raises():
    # N < 2 → cannot form a pair
    with pytest.raises(ValueError):
        _pick_level_pair(1)


def test_pick_level_pair_zero_raises():
    with pytest.raises(ValueError):
        _pick_level_pair(0)
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd backend && uv run pytest tests/pipeline/test_thumbnail.py -k "_pick_level_pair" -v`

Expected: FAIL with `ImportError: cannot import name '_pick_level_pair' from 'pipeline.thumbnail'` (or AttributeError).

- [ ] **Step 3: Implement `_pick_level_pair`**

Add to `backend/pipeline/thumbnail.py` (after the existing imports, before `_cache_bust`):

```python
def _pick_level_pair(n_levels: int) -> tuple[int, int]:
    """Pick (left_level, right_level) for split-progression thumbnail labels.

    - left_level chosen from {1, 2}, clamped to ≤ n_levels.
    - right_level chosen from {n_levels - 1, n_levels}, clamped to ≥ 1.
    - Constraint: left_level < right_level (re-roll if violated).

    Raises ValueError if n_levels < 2 (no valid pair exists).
    """
    if n_levels < 2:
        raise ValueError(f"_pick_level_pair requires n_levels >= 2, got {n_levels}")

    if n_levels == 2:
        return (1, 2)

    left_choices = [n for n in (1, 2) if n <= n_levels]
    right_choices = [n for n in (n_levels - 1, n_levels) if n >= 1]

    # Re-roll until left < right (always terminates fast — at least one valid pair exists for n >= 2).
    for _ in range(20):
        left = random.choice(left_choices)
        right = random.choice(right_choices)
        if left < right:
            return (left, right)

    # Defensive fallback — should not be reached for n >= 2.
    return (1, n_levels)
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd backend && uv run pytest tests/pipeline/test_thumbnail.py -k "_pick_level_pair" -v`

Expected: 6 PASSED.

- [ ] **Step 5: Commit**

```bash
git add backend/pipeline/thumbnail.py backend/tests/pipeline/test_thumbnail.py
git commit -m "Add _pick_level_pair for split-progression thumbnail labels"
```

---

## Task 3: Sidecar persistence for level pair

**Files:**
- Modify: `backend/pipeline/thumbnail.py`
- Modify: `backend/tests/pipeline/test_thumbnail.py`

- [ ] **Step 1: Write failing tests for sidecar persistence**

Append to `backend/tests/pipeline/test_thumbnail.py`:

```python
import json

from pipeline.thumbnail import _read_level_pair_sidecar, _write_level_pair_sidecar


def test_write_and_read_level_pair_sidecar(tmp_path):
    sidecar = tmp_path / "thumb.levels.json"
    _write_level_pair_sidecar(sidecar, 1, 4)
    assert _read_level_pair_sidecar(sidecar) == (1, 4)


def test_read_level_pair_sidecar_missing_returns_none(tmp_path):
    sidecar = tmp_path / "missing.json"
    assert _read_level_pair_sidecar(sidecar) is None


def test_read_level_pair_sidecar_corrupt_returns_none(tmp_path):
    sidecar = tmp_path / "corrupt.json"
    sidecar.write_text("not json {{{")
    assert _read_level_pair_sidecar(sidecar) is None


def test_read_level_pair_sidecar_missing_keys_returns_none(tmp_path):
    sidecar = tmp_path / "partial.json"
    sidecar.write_text(json.dumps({"left_level": 1}))
    assert _read_level_pair_sidecar(sidecar) is None
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd backend && uv run pytest tests/pipeline/test_thumbnail.py -k "sidecar" -v`

Expected: FAIL with ImportError on `_read_level_pair_sidecar` / `_write_level_pair_sidecar`.

- [ ] **Step 3: Implement sidecar helpers**

Add to `backend/pipeline/thumbnail.py` (just below `_pick_level_pair`):

```python
import json


def _write_level_pair_sidecar(path: Path, left_level: int, right_level: int) -> None:
    """Persist the chosen level pair next to the thumbnail."""
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps({"left_level": left_level, "right_level": right_level}))


def _read_level_pair_sidecar(path: Path) -> tuple[int, int] | None:
    """Read a previously-persisted level pair. Returns None if missing/corrupt/incomplete."""
    if not path.exists():
        return None
    try:
        data = json.loads(path.read_text())
    except (OSError, json.JSONDecodeError):
        return None
    left = data.get("left_level")
    right = data.get("right_level")
    if not isinstance(left, int) or not isinstance(right, int):
        return None
    return (left, right)
```

If `json` is already imported at module top, reuse it instead of re-importing inside the helper. Verify with: `grep -n "^import json" backend/pipeline/thumbnail.py`. If absent, move the import to the top of the file.

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd backend && uv run pytest tests/pipeline/test_thumbnail.py -k "sidecar" -v`

Expected: 4 PASSED.

- [ ] **Step 5: Commit**

```bash
git add backend/pipeline/thumbnail.py backend/tests/pipeline/test_thumbnail.py
git commit -m "Add level-pair sidecar persistence helpers"
```

---

## Task 4: `enhance_split_progression` Gemini call

**Files:**
- Modify: `backend/pipeline/thumbnail.py`
- Modify: `backend/tests/pipeline/test_thumbnail.py`

- [ ] **Step 1: Write failing tests for `enhance_split_progression`**

Append to `backend/tests/pipeline/test_thumbnail.py`:

```python
def test_enhance_split_progression_calls_gemini_with_templated_prompt(tmp_path, monkeypatch):
    clean_path = tmp_path / "clean.png"
    output_path = tmp_path / "final.png"
    Image.new("RGB", (32, 32), (10, 20, 30)).save(clean_path)

    captured: dict[str, object] = {}

    def fake_transform(prompt: str, image_paths: list[str], script_id: str | None = None) -> str:
        captured["prompt"] = prompt
        captured["image_paths"] = image_paths
        # Simulate Gemini producing a temp output
        result = tmp_path / "gemini_temp.png"
        Image.new("RGB", (32, 32), (200, 100, 50)).save(result)
        return str(result)

    monkeypatch.setattr("integrations.google_image_client.transform_with_references", fake_transform)

    result = thumbnail.enhance_split_progression(
        clean_image_path=clean_path,
        output_path=output_path,
        left_level=1,
        right_level=4,
        script_id="script-1",
    )

    assert result == output_path
    assert output_path.exists()
    assert "LEVEL 1" in captured["prompt"]
    assert "LEVEL 4" in captured["prompt"]
    assert "What happened between Level 1 and Level 4" in captured["prompt"]
    assert captured["image_paths"] == [str(clean_path)]


def test_enhance_split_progression_falls_back_on_gemini_error(tmp_path, monkeypatch):
    clean_path = tmp_path / "clean.png"
    output_path = tmp_path / "final.png"
    Image.new("RGB", (32, 32), (50, 50, 50)).save(clean_path)

    def failing_transform(prompt: str, image_paths: list[str], script_id: str | None = None) -> str:
        raise RuntimeError("Gemini exploded")

    monkeypatch.setattr("integrations.google_image_client.transform_with_references", failing_transform)

    result = thumbnail.enhance_split_progression(
        clean_image_path=clean_path,
        output_path=output_path,
        left_level=1,
        right_level=4,
        script_id="script-1",
    )

    # Fallback: output is a copy of the clean image
    assert result == output_path
    assert output_path.exists()
    assert output_path.read_bytes() == clean_path.read_bytes()


def test_enhance_split_progression_caches_by_mtime(tmp_path, monkeypatch):
    clean_path = tmp_path / "clean.png"
    output_path = tmp_path / "final.png"
    Image.new("RGB", (32, 32), (10, 20, 30)).save(clean_path)

    call_count = {"n": 0}

    def fake_transform(prompt: str, image_paths: list[str], script_id: str | None = None) -> str:
        call_count["n"] += 1
        result = tmp_path / f"gemini_{call_count['n']}.png"
        Image.new("RGB", (32, 32), (call_count["n"] * 10, 0, 0)).save(result)
        return str(result)

    monkeypatch.setattr("integrations.google_image_client.transform_with_references", fake_transform)

    # First call generates
    thumbnail.enhance_split_progression(clean_image_path=clean_path, output_path=output_path, left_level=1, right_level=3, script_id="s1")
    assert call_count["n"] == 1

    # Second call with unchanged source uses cache
    thumbnail.enhance_split_progression(clean_image_path=clean_path, output_path=output_path, left_level=1, right_level=3, script_id="s1")
    assert call_count["n"] == 1

    # Bumping source mtime invalidates cache
    import os
    new_mtime = output_path.stat().st_mtime + 10
    os.utime(clean_path, (new_mtime, new_mtime))
    thumbnail.enhance_split_progression(clean_image_path=clean_path, output_path=output_path, left_level=1, right_level=3, script_id="s1")
    assert call_count["n"] == 2

    # force=True also invalidates cache
    thumbnail.enhance_split_progression(clean_image_path=clean_path, output_path=output_path, left_level=1, right_level=3, script_id="s1", force=True)
    assert call_count["n"] == 3
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd backend && uv run pytest tests/pipeline/test_thumbnail.py -k "enhance_split_progression" -v`

Expected: FAIL with `AttributeError: module 'pipeline.thumbnail' has no attribute 'enhance_split_progression'`.

- [ ] **Step 3: Implement `enhance_split_progression`**

Add to `backend/pipeline/thumbnail.py` (after the sidecar helpers):

```python
def enhance_split_progression(
    clean_image_path: Path,
    output_path: Path,
    left_level: int,
    right_level: int,
    script_id: str | None = None,
    force: bool = False,
) -> Path:
    """Transform a single iconic life-as-a thumbnail into a split-progression thumbnail.

    Sends the clean image to Gemini with the SPLIT_PROGRESSION_PROMPT (with
    {left_level} / {right_level} substituted) and writes the result to output_path.

    Caches by mtime: re-runs only if output is missing, source is newer, or force=True.
    On Gemini failure, falls back to copying the clean image to output_path.
    """
    from integrations.google_image_client import transform_with_references
    from prompts import SPLIT_PROGRESSION_PROMPT

    # mtime cache check
    if not force and output_path.exists():
        try:
            if output_path.stat().st_mtime >= clean_image_path.stat().st_mtime:
                logger.info(
                    "[%s] split-progression cache hit: %s",
                    script_id or "no-id", output_path,
                )
                return output_path
        except OSError:
            pass  # Fall through and regenerate

    prompt = SPLIT_PROGRESSION_PROMPT.template.format(
        left_level=left_level,
        right_level=right_level,
    )

    output_path.parent.mkdir(parents=True, exist_ok=True)

    try:
        result_path = transform_with_references(
            prompt=prompt,
            image_paths=[str(clean_image_path)],
            script_id=script_id,
        )
        shutil.copy2(result_path, str(output_path))
        logger.info(
            "[%s] split-progression thumbnail written: %s (LEVEL %d / LEVEL %d)",
            script_id or "no-id", output_path, left_level, right_level,
        )
        return output_path
    except Exception as exc:
        logger.warning(
            "[%s] split-progression Gemini call failed (%s); falling back to clean image",
            script_id or "no-id", exc,
        )
        shutil.copy2(str(clean_image_path), str(output_path))
        return output_path
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd backend && uv run pytest tests/pipeline/test_thumbnail.py -k "enhance_split_progression" -v`

Expected: 3 PASSED.

- [ ] **Step 5: Commit**

```bash
git add backend/pipeline/thumbnail.py backend/tests/pipeline/test_thumbnail.py
git commit -m "Add enhance_split_progression thumbnail Gemini step"
```

---

## Task 5: Remove dead `composite_title_overlay` function

**Files:**
- Modify: `backend/pipeline/thumbnail.py`

- [ ] **Step 1: Verify no other callers exist**

Run: `grep -rn "composite_title_overlay" backend --include="*.py"`

Expected: only the function definition in `backend/pipeline/thumbnail.py` and the import + call in `backend/pipeline/formats/title_cards/cinematic_chapters.py`. (The call site in `cinematic_chapters.py` will be removed in Task 7. We delete the function here first because it's clearer; if Task 7 hasn't run yet, the import will be temporarily broken — but since we always commit Task 5 + Task 7 in sequence, this is fine. **However, to keep each commit independently buildable, swap order:** do Task 7 first if running them in sequence. Note: tasks in this plan ARE intended to be run in numerical order; if you're running them out of order, do Task 7 before Task 5.)

Actually — to guarantee each commit leaves the tree green, **defer Task 5 until after Task 7**. If you reach Task 5 with `composite_title_overlay` still imported in `cinematic_chapters.py`, abort Task 5 and complete Task 7 first.

- [ ] **Step 2: Run the test suite to confirm baseline is green**

Run: `cd backend && uv run pytest tests/pipeline/ -q`

Expected: all tests pass. (If they don't, stop and fix before continuing.)

- [ ] **Step 3: Delete the function and its helper**

In `backend/pipeline/thumbnail.py`, delete:
- The entire `_load_overlay_font` function (its only caller is `composite_title_overlay`).
- The entire `composite_title_overlay` function.

Verify no remaining import of `_load_overlay_font` anywhere:

Run: `grep -rn "_load_overlay_font\|composite_title_overlay" backend --include="*.py"`

Expected: no matches.

- [ ] **Step 4: Run tests to confirm nothing broke**

Run: `cd backend && uv run pytest tests/pipeline/ -q`

Expected: all tests pass.

- [ ] **Step 5: Commit**

```bash
git add backend/pipeline/thumbnail.py
git commit -m "Remove unused composite_title_overlay helper"
```

---

## Task 6: Drop `levels[0].image_prompt` requirement

**Files:**
- Modify: `backend/models/script.py`
- Modify: `backend/prompts.py`
- Modify: `backend/pipeline/formats/life_as_a.py`
- Modify: `backend/tests/pipeline/test_formats_registry.py`

- [ ] **Step 1: Make `LevelMeta.image_prompt` optional with empty default**

In `backend/models/script.py`, change:

```python
class LevelMeta(BaseModel):
    """Per-level metadata used only by the cinematic-chapters strategy."""
    number: int
    descriptor: str
    image_prompt: str
```

to:

```python
class LevelMeta(BaseModel):
    """Per-level metadata used only by the cinematic-chapters strategy."""
    number: int
    descriptor: str
    image_prompt: str = ""  # Empty for level 1 — covered by cinematic_thumbnail_prompt instead.
```

- [ ] **Step 2: Update `LIFE_AS_A_OUTLINE_INSTRUCTIONS` prompt**

In `backend/prompts.py`, find the `LIFE_AS_A_OUTLINE_INSTRUCTIONS` `template=` string. Two edits:

(a) In the "Per-level metadata" section, change:

```
- `image_prompt` — a vivid one-line scene description for the chapter-card image. Begins with one of `[ESTABLISHING]`, `[CLOSE-UP]`, `[REACTION]`, `[METAPHOR]`.
```

to:

```
- `image_prompt` — a vivid one-line scene description for the chapter-card image. Begins with one of `[ESTABLISHING]`, `[CLOSE-UP]`, `[REACTION]`, `[METAPHOR]`. **Required for levels 2..N. Omit (or set to empty string) for level 1** — level 1's chapter card image is reused from the cinematic thumbnail.
```

(b) In the inline JSON shape, change:

```
"levels": [
    {
      "number": 1,
      "descriptor": "occasional",
      "topic_summary": "2-3 sentences for context.",
      "image_prompt": "[ESTABLISHING] vivid one-line description."
    }
  ],
```

to:

```
"levels": [
    {
      "number": 1,
      "descriptor": "occasional",
      "topic_summary": "2-3 sentences for context."
    },
    {
      "number": 2,
      "descriptor": "regular",
      "topic_summary": "2-3 sentences for context.",
      "image_prompt": "[ESTABLISHING] vivid one-line description."
    }
  ],
```

- [ ] **Step 3: Update `LIFE_AS_A_SCRIPT_SYSTEM` prompt**

In `backend/prompts.py`, find the `LIFE_AS_A_SCRIPT_SYSTEM` `template=` string (around line 528-575). The inline JSON shape includes `"image_prompt"` for levels.

Change the inline `levels` example to make level 1's `image_prompt` optional. Replace:

```
"levels": [
    {
      "number": 1,
      "descriptor": "occasional",
      "image_prompt": "Vivid one-line scene description for the chapter card image."
    }
  ],
```

with:

```
"levels": [
    {
      "number": 1,
      "descriptor": "occasional"
    },
    {
      "number": 2,
      "descriptor": "regular",
      "image_prompt": "Vivid one-line scene description for the chapter card image."
    }
  ],
```

Then add to the "Output rules" bullet list (around the line `- Visual prompts must NEVER request text...`):

```
- `levels[0]` (level 1) does NOT need an `image_prompt`; the chapter-card image for level 1 is reused from the cinematic thumbnail. Levels 2..N require `image_prompt`.
```

- [ ] **Step 4: Update `enforce_life_as_a_constraints` fallback for level 1**

In `backend/pipeline/formats/life_as_a.py`, find the chapter-card scene insertion logic (around line 51-76). Update the `image_prompt` resolution to fall back to `cinematic_thumbnail_prompt` for level 1 specifically. Replace:

```python
            image_prompt = (
                (level.image_prompt if level and level.image_prompt else None)
                or segment.title_card_image_prompt
                or descriptor
            )
```

with:

```python
            image_prompt = (
                (level.image_prompt if level and level.image_prompt else None)
                or (content.cinematic_thumbnail_prompt if level_num == 1 else None)
                or segment.title_card_image_prompt
                or descriptor
            )
```

- [ ] **Step 5: Update the `synthesize levels[]` block to handle level 1 fallback**

In the same file, find the `if not content.levels:` block (around line 79-87). It uses `seg.title_card_image_prompt` as a default, which is fine. But for level 1 (`i == 0`), if the segment also has no title_card_image_prompt, we'd get an empty string. That's now legal because the model field defaults to `""`. **No code change needed for this block** — verify by re-reading lines 79-87.

- [ ] **Step 6: Update the existing test `test_segmented_life_as_a_preserves_outline_fields`**

In `backend/tests/pipeline/test_formats_registry.py`, find the test (line 96 onward). The test currently provides `image_prompt` for level 0 in the mocked outline. Update the outline mock to omit `image_prompt` for level 0, and assert it deserializes as empty string.

Replace lines 110-113:

```python
        "levels": [
            {"number": 1, "descriptor": "entry", "image_prompt": "a door"},
            {"number": 2, "descriptor": "drift", "image_prompt": "a hallway"},
        ],
```

with:

```python
        "levels": [
            {"number": 1, "descriptor": "entry"},
            {"number": 2, "descriptor": "drift", "image_prompt": "a hallway"},
        ],
```

Replace lines 143-144:

```python
    assert content.levels[0].descriptor == "entry"
    assert content.levels[0].image_prompt == "a door"
```

with:

```python
    assert content.levels[0].descriptor == "entry"
    assert content.levels[0].image_prompt == ""  # Level 1's chapter image comes from cinematic_thumbnail_prompt.
```

- [ ] **Step 7: Add a new test for the level 1 fallback in `enforce_life_as_a_constraints`**

Append to `backend/tests/pipeline/test_formats_registry.py`:

```python
def test_enforce_life_as_a_falls_back_to_cinematic_prompt_for_level_1():
    """When levels[0].image_prompt is empty, the level-1 chapter scene should
    use cinematic_thumbnail_prompt as its visual_prompt fallback."""
    from models.script import LevelMeta, Scene, ScriptContent, Segment
    from pipeline.formats.life_as_a import enforce_life_as_a_constraints

    content = ScriptContent(
        title="Your Life As A Test",
        format_id="life-as-a",
        cinematic_thumbnail_prompt="a door at dawn",
        levels=[
            LevelMeta(number=1, descriptor="entry", image_prompt=""),
            LevelMeta(number=2, descriptor="drift", image_prompt="a hallway"),
        ],
        segments=[
            Segment(name="Level 1, the entry", scenes=[
                Scene(id="s1", narration="walking", visual_prompt="[ESTABLISHING] something",
                      duration_estimate_seconds=10, is_title_card=False),
            ]),
            Segment(name="Level 2, the drift", scenes=[
                Scene(id="s2", narration="drifting", visual_prompt="[ESTABLISHING] something",
                      duration_estimate_seconds=10, is_title_card=False),
            ]),
        ],
    )

    enforce_life_as_a_constraints(content)

    # Level 1 chapter card scene was inserted at index 0 of segment 0
    level_1_chapter = content.segments[0].scenes[0]
    assert level_1_chapter.is_title_card is True
    assert "a door at dawn" in level_1_chapter.visual_prompt

    # Level 2 chapter card uses its own image_prompt
    level_2_chapter = content.segments[1].scenes[0]
    assert level_2_chapter.is_title_card is True
    assert "a hallway" in level_2_chapter.visual_prompt
```

- [ ] **Step 8: Run tests**

Run: `cd backend && uv run pytest tests/pipeline/test_formats_registry.py -v`

Expected: all tests pass (including the updated and new one).

Run: `cd backend && uv run pytest tests/ -q`

Expected: full suite passes.

- [ ] **Step 9: Commit**

```bash
git add backend/models/script.py backend/prompts.py backend/pipeline/formats/life_as_a.py backend/tests/pipeline/test_formats_registry.py
git commit -m "Drop image_prompt requirement for life-as-a level 1"
```

---

## Task 7: Rewrite `CinematicChaptersStrategy.prepare_thumbnail`

**Files:**
- Modify: `backend/pipeline/formats/title_cards/cinematic_chapters.py`

- [ ] **Step 1: Replace `_thumbnail_paths` to return only (clean, final)**

In `backend/pipeline/formats/title_cards/cinematic_chapters.py`, replace:

```python
def _thumbnail_paths(script_id: str) -> tuple[Path, Path]:
    """Returns (clean_path, with_title_path) for the cinematic thumbnail.

    - clean_path: the AI-generated bare image (no overlay)
    - with_title_path: the final composited thumbnail with title overlay (frontend reads this)
    """
    base = DATA_DIR / "projects" / script_id / "images"
    return base / "cinematic_thumbnail_clean.png", base / "cinematic_thumbnail.png"
```

with:

```python
def _thumbnail_paths(script_id: str) -> tuple[Path, Path, Path]:
    """Returns (clean_path, final_path, sidecar_path) for the cinematic thumbnail.

    - clean_path: AI-generated iconic image. Also reused as chapter_1.png.
    - final_path: split-progression enhanced thumbnail (frontend reads this).
    - sidecar_path: persisted level-pair JSON for re-render consistency.
    """
    base = DATA_DIR / "projects" / script_id / "images"
    return (
        base / "cinematic_thumbnail_clean.png",
        base / "cinematic_thumbnail.png",
        base / "cinematic_thumbnail.levels.json",
    )
```

- [ ] **Step 2: Rewrite `prepare_thumbnail`**

Replace the entire `prepare_thumbnail` method body in `CinematicChaptersStrategy`:

```python
    def prepare_thumbnail(
        self,
        script_id: str,
        content: ScriptContent,
        accent_color: str,
        force: bool = False,
        job_id: str | None = None,
    ) -> None:
        # ``job_id`` is part of the strategy protocol contract for cancellation /
        # progress tracking. The cinematic-chapters pipeline does not yet wire
        # job_id into its sub-steps; accepted here as a no-op for future use.
        del job_id, accent_color  # accent_color was used by the old Pillow title overlay.

        from pipeline.thumbnail import (
            _pick_level_pair,
            _read_level_pair_sidecar,
            _write_level_pair_sidecar,
            enhance_split_progression,
        )

        clean_path, final_path, sidecar_path = _thumbnail_paths(script_id)
        clean_path.parent.mkdir(parents=True, exist_ok=True)

        thumb_prompt = content.cinematic_thumbnail_prompt or content.title
        if not thumb_prompt:
            raise RuntimeError(
                "cinematic-chapters: cinematic_thumbnail_prompt missing on ScriptContent"
            )

        # 1. Generate the iconic image (Gemini call)
        generate_scene_image(
            scene_id="cinematic_thumbnail_clean",
            visual_prompt=thumb_prompt,
            script_id=script_id,
            force=force,
        )

        # 2. Reuse it as chapter_1.png — copy if missing or older than the source.
        chapter_1_path = _chapter_image_path(script_id, 1)
        if (
            force
            or not chapter_1_path.exists()
            or chapter_1_path.stat().st_mtime < clean_path.stat().st_mtime
        ):
            chapter_1_path.parent.mkdir(parents=True, exist_ok=True)
            import shutil
            shutil.copy2(str(clean_path), str(chapter_1_path))
            logger.info(
                "cinematic-chapters: copied cinematic image -> chapter_1 for script %s",
                script_id,
            )

        # 3. Generate chapter images for levels 2..N from levels[i].image_prompt.
        if not content.levels:
            logger.warning(
                "cinematic-chapters: content.levels is empty; no chapter images generated"
            )
            return

        for level in content.levels[1:]:
            if not level.image_prompt:
                logger.warning(
                    "cinematic-chapters: level %d missing image_prompt — skipping",
                    level.number,
                )
                continue
            generate_scene_image(
                scene_id=f"chapter_{level.number}",
                visual_prompt=level.image_prompt,
                script_id=script_id,
                force=force,
            )

        # 4. Decide level pair (cached in sidecar for re-render consistency).
        n_levels = len(content.levels)
        if n_levels < 2:
            logger.warning(
                "cinematic-chapters: only %d level(s) — skipping split-progression "
                "enhancement, using clean image as final thumbnail",
                n_levels,
            )
            import shutil
            shutil.copy2(str(clean_path), str(final_path))
            return

        cached_pair = None if force else _read_level_pair_sidecar(sidecar_path)
        if cached_pair is None:
            left_level, right_level = _pick_level_pair(n_levels)
            _write_level_pair_sidecar(sidecar_path, left_level, right_level)
        else:
            left_level, right_level = cached_pair

        # 5. Split-progression enhancement (Gemini call).
        enhance_split_progression(
            clean_image_path=clean_path,
            output_path=final_path,
            left_level=left_level,
            right_level=right_level,
            script_id=script_id,
            force=force,
        )
```

- [ ] **Step 3: Remove the old `composite_title_overlay` import**

In `backend/pipeline/formats/title_cards/cinematic_chapters.py`, find any import like `from pipeline.thumbnail import composite_title_overlay` and delete it. (The import was previously inside `prepare_thumbnail` at line 69.)

Run: `grep -n "composite_title_overlay" backend/pipeline/formats/title_cards/cinematic_chapters.py`

Expected: no matches.

- [ ] **Step 4: Run existing tests to confirm nothing else broke**

Run: `cd backend && uv run pytest tests/pipeline/ -q`

Expected: all existing tests pass. (Strategy-specific tests in Task 8 will be added next.)

- [ ] **Step 5: Commit**

```bash
git add backend/pipeline/formats/title_cards/cinematic_chapters.py
git commit -m "Rewrite cinematic-chapters thumbnail to use split-progression"
```

---

## Task 8: Integration test for `CinematicChaptersStrategy.prepare_thumbnail`

**Files:**
- Create: `backend/tests/pipeline/test_cinematic_chapters_strategy.py`

- [ ] **Step 1: Write integration tests**

Create `backend/tests/pipeline/test_cinematic_chapters_strategy.py`:

```python
"""Integration tests for the rewritten CinematicChaptersStrategy.prepare_thumbnail."""
from pathlib import Path

import pytest
from PIL import Image

from models.script import LevelMeta, Scene, ScriptContent, Segment
from pipeline.formats.title_cards.cinematic_chapters import (
    CINEMATIC_CHAPTERS,
    _thumbnail_paths,
    _chapter_image_path,
)


def _make_content(n_levels: int) -> ScriptContent:
    levels = [
        LevelMeta(
            number=i + 1,
            descriptor=f"stage{i + 1}",
            image_prompt="" if i == 0 else f"chapter prompt {i + 1}",
        )
        for i in range(n_levels)
    ]
    segments = [
        Segment(name=f"Level {i + 1}, the stage{i + 1}", scenes=[
            Scene(id=f"chapter_{i+1:02d}", narration="x", visual_prompt="[ESTABLISHING] x",
                  duration_estimate_seconds=4.0, is_title_card=True, visual_beat="static"),
            Scene(id=f"s_{i+1}_a", narration="x", visual_prompt="[ESTABLISHING] x",
                  duration_estimate_seconds=10.0, is_title_card=False, visual_beat="static"),
        ])
        for i in range(n_levels)
    ]
    return ScriptContent(
        title="Your Life As A Test",
        format_id="life-as-a",
        cinematic_thumbnail_prompt="iconic test image",
        levels=levels,
        segments=segments,
    )


@pytest.fixture
def patched_data_dir(tmp_path, monkeypatch):
    """Redirect DATA_DIR for the strategy and its helpers to tmp_path."""
    monkeypatch.setattr("pipeline.formats.title_cards.cinematic_chapters.DATA_DIR", tmp_path)
    monkeypatch.setattr("pipeline.thumbnail.DATA_DIR", tmp_path)
    return tmp_path


@pytest.fixture
def fake_image_gen(monkeypatch):
    """Replace generate_scene_image with a stub that writes a dummy PNG."""
    import pipeline.formats.title_cards.cinematic_chapters as cinematic_module
    calls: list[tuple[str, str]] = []

    def fake_generate(scene_id: str, visual_prompt: str, script_id: str, force: bool = False, **_kwargs) -> str:
        calls.append((scene_id, visual_prompt))
        from config import DATA_DIR as real_data_dir  # re-imported within module patch

        # Use the patched DATA_DIR via the module reference
        from pipeline.formats.title_cards.cinematic_chapters import DATA_DIR
        out = DATA_DIR / "projects" / script_id / "images" / f"{scene_id}.png"
        out.parent.mkdir(parents=True, exist_ok=True)
        Image.new("RGB", (32, 32), (123, 45, 67)).save(out)
        return str(out)

    monkeypatch.setattr(cinematic_module, "generate_scene_image", fake_generate)
    return calls


@pytest.fixture
def fake_gemini_transform(monkeypatch, tmp_path):
    """Stub transform_with_references to write a marker PNG."""
    transform_calls: list[dict] = []

    def fake_transform(prompt: str, image_paths: list[str], script_id: str | None = None) -> str:
        transform_calls.append({"prompt": prompt, "image_paths": image_paths, "script_id": script_id})
        out = tmp_path / "gemini_out.png"
        Image.new("RGB", (32, 32), (200, 200, 200)).save(out)
        return str(out)

    monkeypatch.setattr("integrations.google_image_client.transform_with_references", fake_transform)
    return transform_calls


def test_prepare_thumbnail_generates_clean_chapter1_and_split(
    patched_data_dir, fake_image_gen, fake_gemini_transform,
):
    script_id = "test-1"
    content = _make_content(n_levels=4)

    CINEMATIC_CHAPTERS.prepare_thumbnail(
        script_id=script_id,
        content=content,
        accent_color="#ff0066",
        force=False,
    )

    clean_path, final_path, sidecar_path = _thumbnail_paths(script_id)

    # Clean cinematic image was generated
    assert clean_path.exists()
    assert any(scene_id == "cinematic_thumbnail_clean" for scene_id, _ in fake_image_gen)

    # Chapter 1 was COPIED (not generated)
    chapter_1 = _chapter_image_path(script_id, 1)
    assert chapter_1.exists()
    assert chapter_1.read_bytes() == clean_path.read_bytes()
    assert not any(scene_id == "chapter_1" for scene_id, _ in fake_image_gen)

    # Chapters 2..4 WERE generated
    for n in (2, 3, 4):
        assert _chapter_image_path(script_id, n).exists()
        assert any(scene_id == f"chapter_{n}" for scene_id, _ in fake_image_gen)

    # Split-progression Gemini call ran with the clean image
    assert len(fake_gemini_transform) == 1
    call = fake_gemini_transform[0]
    assert call["image_paths"] == [str(clean_path)]
    assert "LEVEL " in call["prompt"]

    # Final thumbnail and sidecar both exist
    assert final_path.exists()
    assert sidecar_path.exists()


def test_prepare_thumbnail_caches_level_pair_across_runs(
    patched_data_dir, fake_image_gen, fake_gemini_transform,
):
    script_id = "test-2"
    content = _make_content(n_levels=5)

    CINEMATIC_CHAPTERS.prepare_thumbnail(script_id=script_id, content=content, accent_color="#ff0066")
    _, _, sidecar_path = _thumbnail_paths(script_id)
    import json
    first_pair = json.loads(sidecar_path.read_text())

    # Second run without force should reuse the same level pair (sidecar unchanged)
    CINEMATIC_CHAPTERS.prepare_thumbnail(script_id=script_id, content=content, accent_color="#ff0066")
    second_pair = json.loads(sidecar_path.read_text())
    assert first_pair == second_pair


def test_prepare_thumbnail_falls_back_when_one_level(
    patched_data_dir, fake_image_gen, fake_gemini_transform,
):
    script_id = "test-3"
    content = _make_content(n_levels=1)

    CINEMATIC_CHAPTERS.prepare_thumbnail(script_id=script_id, content=content, accent_color="#ff0066")

    clean_path, final_path, sidecar_path = _thumbnail_paths(script_id)
    # Final exists and equals clean (no Gemini enhancement performed)
    assert final_path.exists()
    assert final_path.read_bytes() == clean_path.read_bytes()
    # No sidecar written (no pair to record)
    assert not sidecar_path.exists()
    # No Gemini transform call happened
    assert len(fake_gemini_transform) == 0
```

- [ ] **Step 2: Run the new test file**

Run: `cd backend && uv run pytest tests/pipeline/test_cinematic_chapters_strategy.py -v`

Expected: 3 PASSED.

- [ ] **Step 3: Run the full test suite to confirm nothing regressed**

Run: `cd backend && uv run pytest tests/ -q`

Expected: full suite passes.

- [ ] **Step 4: Commit**

```bash
git add backend/tests/pipeline/test_cinematic_chapters_strategy.py
git commit -m "Add integration tests for CinematicChaptersStrategy thumbnail flow"
```

---

## Task 9: Manual end-to-end verification

**Files:** none (manual)

- [ ] **Step 1: Start the dev environment**

Run: `npm run dev`

Wait for backend (uvicorn on :8420) and frontend (Vite on :5173) to come up.

- [ ] **Step 2: Generate a life-as-a project end-to-end**

In the UI:
1. Create a new "Your Life As A..." project with any topic.
2. Run script generation through to scene/image generation.
3. Trigger thumbnail generation (via Export panel or whatever surface this codebase uses for the thumbnail action — check `frontend/src/components/timeline/ExportPanel.tsx` if unsure).

- [ ] **Step 3: Verify file layout on disk**

Inspect `data/projects/{script_id}/images/`. Expected files:

| File | Expected |
|---|---|
| `cinematic_thumbnail_clean.png` | Single iconic AI image. |
| `chapter_1.png` | Byte-identical copy of `cinematic_thumbnail_clean.png`. |
| `chapter_2.png` … `chapter_N.png` | Per-level AI images. |
| `cinematic_thumbnail.png` | Split-progression result with diagonal divider, "LEVEL X" / "LEVEL Y" labels, no video title. |
| `cinematic_thumbnail.levels.json` | `{"left_level": <int>, "right_level": <int>}` with `left < right`. |

Verify byte identity:

```bash
diff -q data/projects/<script_id>/images/cinematic_thumbnail_clean.png data/projects/<script_id>/images/chapter_1.png
```

Expected: no output (files identical).

- [ ] **Step 4: Verify the rendered thumbnail in the UI**

In the export panel preview, the thumbnail should:
- Be split diagonally with a glow on the divider.
- Show "LEVEL X" on the left and "LEVEL Y" on the right matching the sidecar JSON.
- Not contain the full video title.

- [ ] **Step 5: Verify re-render uses cached pair**

Trigger thumbnail regeneration without `force=True`. Open `cinematic_thumbnail.levels.json` again — values should be unchanged.

- [ ] **Step 6: Verify force regeneration**

Trigger a `force=True` regeneration (whatever surface the codebase exposes — likely a "regenerate" button passing `force=true`). New `cinematic_thumbnail.png` should be produced; sidecar may have a new pair.

- [ ] **Step 7: Note manual verification result in the commit message**

If everything looks good, no code changes. If an issue is found, file it as a follow-up task and stop here.

---

## Self-Review

**1. Spec coverage:**

| Spec section | Implemented in |
|---|---|
| Pipeline step 1 (cinematic gen) | Task 7 step 2 |
| Pipeline step 2 (copy → chapter_1) | Task 7 step 2 |
| Pipeline step 3 (chapters 2..N) | Task 7 step 2 |
| Pipeline step 4 (level pair selection) | Task 2 + Task 7 step 2 |
| Pipeline step 5 (Gemini enhancement) | Task 4 + Task 7 step 2 |
| Gemini call count (N+1 unchanged) | Task 7 step 2 |
| File layout (clean / chapter_N / final / sidecar) | Task 7 + Task 8 verification |
| `_thumbnail_paths` returns (clean, final, sidecar) | Task 7 step 1 |
| Level pair selection rules + edge cases | Task 2 |
| Sidecar caching + invalidation | Task 3 + Task 4 |
| Caching by mtime | Task 4 |
| `SPLIT_PROGRESSION_PROMPT` with templated levels | Task 1 |
| Minimal-text section in prompt | Task 1 |
| Code touch points: `prompts.py` | Task 1, Task 6 |
| Code touch points: `thumbnail.py` | Tasks 2-5 |
| Code touch points: `cinematic_chapters.py` | Task 7 |
| Code touch points: scriptwriter prompt | Task 6 |
| `LevelMeta.image_prompt` optional | Task 6 |
| Frontend unchanged | (verified by Task 8 — no FE changes) |
| Error handling: enhance fallback to clean | Task 4 |
| Error handling: N<2 fallback | Task 7 step 2 + Task 8 test |
| Sidecar I/O never raises | Task 3 |
| Test: level pair selection | Task 2 |
| Test: sidecar persistence | Task 3 |
| Test: N<2 fallback | Task 8 |
| Test: prompt forwards level numbers | Task 4 |
| Test: scriptwriter test update | Task 6 |
| Migration: existing projects rendered with old layout | Spec section "Migration" — no code change needed; force=true regenerates |

All spec items covered.

**2. Placeholder scan:** no TBD/TODO/"implement later" — every code block is concrete. Every test step shows the actual assertion code. Every command shows expected output.

**3. Type/symbol consistency:**
- `_pick_level_pair(int) -> tuple[int, int]` — defined Task 2, used Task 7. ✓
- `_read_level_pair_sidecar(Path) -> tuple[int, int] | None` — defined Task 3, used Task 7. ✓
- `_write_level_pair_sidecar(Path, int, int) -> None` — defined Task 3, used Task 7. ✓
- `enhance_split_progression(clean_image_path, output_path, left_level, right_level, script_id, force)` — defined Task 4, used Task 7. ✓
- `_thumbnail_paths` returns 3-tuple — Task 7 step 1; consistent with Task 8 unpacking. ✓
- `LevelMeta.image_prompt: str = ""` — Task 6 step 1; tests update accordingly Task 6 step 6, Task 8 fixture. ✓

All consistent. Plan is ready.
