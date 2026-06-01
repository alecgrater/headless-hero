# Visual Mode Duration Policy Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make scene duration, visual-mode variety, and the Timeline/Settings workflow follow a universal visual-mode policy before voiceover generation.

**Architecture:** Add one backend policy module that owns mode duration profiles and planning guidance. Wire it into prompts, generic scene splitting, life-as-a chunking, media validation, Timeline helpers, and Settings -> Reference copy so behavior is automatic and obvious without adding manual duration controls.

**Tech Stack:** Python 3.12/FastAPI/SQLModel backend, React 19/Vite/TypeScript/Tailwind 4 frontend, pytest, Vitest.

---

## File Map

- Create `backend/pipeline/visual_mode_policy.py`: single backend source of truth for duration profiles, planning text, and validation labels.
- Create `backend/tests/pipeline/test_visual_mode_policy.py`: unit coverage for all canonical modes and helper text.
- Modify `backend/pipeline/scriptwriter.py`: import policy constants, include policy guidance in generation prompts, and make generic scene splitting profile-aware.
- Modify `backend/pipeline/formats/life_as_a.py`: make life-as-a splitting profile-aware and update reference note text.
- Modify `backend/pipeline/formats/youtube_listicle.py`: update reference note text to explain universal mode-duration policy.
- Modify `backend/prompts/script.py`: update static prompt sections/examples so LLMs can plan `video` and longer renderer-owned modes before voiceover.
- Modify `backend/pipeline/media_analyzer.py`: preserve planned `video` when valid, downgrade with clear reasons, and update comments/logs away from "promotion only".
- Modify `frontend/src/components/settings/visual-modes/catalog.ts`: add duration profile metadata and workflow copy to the Visual Modes reference data.
- Modify `frontend/src/components/settings/visual-modes/VisualModesSection.tsx`: add a Reference workflow explanation section.
- Modify `frontend/src/components/settings/visual-modes/VisualModeDetail.tsx`: display duration profile for the selected mode.
- Modify `frontend/src/components/timeline/VisualTreatmentReviewPanel.tsx`: rename/reframe review language around validation/preparation, include duration profile labels in mode catalog.
- Modify `frontend/src/components/timeline/MediaSourcesTab.tsx`: rename button/copy from re-analyze to validate/prepare.
- Modify `frontend/src/components/timeline/PropertiesPanel.tsx`: show selected mode duration profile and add mode option tooltip/label hints.
- Modify `frontend/src/components/timeline/TimelineBlock.tsx`: expose compact mode-profile markers for image-lane blocks.
- Modify or add frontend tests near existing settings/timeline tests to cover visible workflow text and duration profile labels.
- Modify `docs/formats/AUTHORING.md`: update format authoring guidance so all formats defer duration behavior to the universal visual-mode policy.
- Modify `AGENTS.md` only if implementation changes establish a narrower convention than the spec already added.

## Task 1: Backend Policy Module

**Files:**
- Create: `backend/pipeline/visual_mode_policy.py`
- Test: `backend/tests/pipeline/test_visual_mode_policy.py`

- [ ] **Step 1: Write failing tests for canonical profiles**

Create `backend/tests/pipeline/test_visual_mode_policy.py`:

```python
from pipeline.visual_mode_policy import (
    CANONICAL_VISUAL_MODES,
    duration_profile_for_mode,
    duration_target_for_mode,
    prompt_duration_guidance,
)


def test_duration_policy_covers_all_canonical_visual_modes():
    assert CANONICAL_VISUAL_MODES == (
        "full_frame",
        "continuous",
        "multi_frame",
        "video",
        "popup_sequence",
        "flipflop",
        "comparison_board",
        "captions",
        "stat_card",
    )

    for mode in CANONICAL_VISUAL_MODES:
        policy = duration_target_for_mode(mode)
        assert policy.visual_mode == mode
        assert policy.profile in {"normal", "medium", "extended", "planned"}
        assert policy.min_seconds > 0
        assert policy.target_seconds >= policy.min_seconds
        assert policy.max_seconds >= policy.target_seconds
        assert policy.ui_label
        assert policy.prompt_guidance


def test_renderer_owned_modes_have_longer_targets_than_full_frame():
    normal = duration_target_for_mode("full_frame")

    assert duration_target_for_mode("captions").target_seconds > normal.target_seconds
    assert duration_target_for_mode("comparison_board").target_seconds > normal.target_seconds
    assert duration_target_for_mode("popup_sequence").target_seconds > normal.target_seconds
    assert duration_target_for_mode("stat_card").target_seconds > normal.target_seconds


def test_unknown_modes_fall_back_to_full_frame_policy():
    assert duration_profile_for_mode("legacy_mode") == "normal"
    assert duration_target_for_mode("legacy_mode") == duration_target_for_mode("full_frame")


def test_prompt_duration_guidance_mentions_extended_and_video_policy():
    text = prompt_duration_guidance()

    assert "captions" in text
    assert "comparison_board" in text
    assert "video" in text
    assert "before voiceover" in text
```

- [ ] **Step 2: Run the failing policy tests**

Run:

```bash
uv run --project backend pytest backend/tests/pipeline/test_visual_mode_policy.py -q
```

Expected: FAIL because `pipeline.visual_mode_policy` does not exist.

- [ ] **Step 3: Implement the shared policy module**

Create `backend/pipeline/visual_mode_policy.py`:

```python
"""Shared duration and planning policy for scene visual modes."""

from __future__ import annotations

from dataclasses import dataclass

CANONICAL_VISUAL_MODES: tuple[str, ...] = (
    "full_frame",
    "continuous",
    "multi_frame",
    "video",
    "popup_sequence",
    "flipflop",
    "comparison_board",
    "captions",
    "stat_card",
)


@dataclass(frozen=True)
class VisualModeDurationTarget:
    visual_mode: str
    profile: str
    min_seconds: float
    target_seconds: float
    max_seconds: float
    ui_label: str
    prompt_guidance: str


_TARGETS: dict[str, VisualModeDurationTarget] = {
    "full_frame": VisualModeDurationTarget(
        visual_mode="full_frame",
        profile="normal",
        min_seconds=5.0,
        target_seconds=8.0,
        max_seconds=14.0,
        ui_label="Normal target · 5-9s",
        prompt_guidance="Use about 5-9 seconds of narration for one clear visual beat.",
    ),
    "continuous": VisualModeDurationTarget(
        visual_mode="continuous",
        profile="normal",
        min_seconds=5.0,
        target_seconds=8.0,
        max_seconds=14.0,
        ui_label="Normal target · 5-9s",
        prompt_guidance="Use about 5-9 seconds while one coherent progression unfolds.",
    ),
    "multi_frame": VisualModeDurationTarget(
        visual_mode="multi_frame",
        profile="normal",
        min_seconds=5.0,
        target_seconds=8.0,
        max_seconds=14.0,
        ui_label="Normal target · 5-9s",
        prompt_guidance="Use about 5-9 seconds unless several concrete examples require a little more room.",
    ),
    "flipflop": VisualModeDurationTarget(
        visual_mode="flipflop",
        profile="normal",
        min_seconds=5.0,
        target_seconds=8.0,
        max_seconds=14.0,
        ui_label="Normal target · 5-9s",
        prompt_guidance="Use about 5-9 seconds for simple same-subject A/B motion.",
    ),
    "captions": VisualModeDurationTarget(
        visual_mode="captions",
        profile="extended",
        min_seconds=12.0,
        target_seconds=16.0,
        max_seconds=20.0,
        ui_label="Extended target · 14-18s",
        prompt_guidance="Use about 14-18 seconds so the editorial text lands with enough narration context.",
    ),
    "comparison_board": VisualModeDurationTarget(
        visual_mode="comparison_board",
        profile="extended",
        min_seconds=14.0,
        target_seconds=20.0,
        max_seconds=26.0,
        ui_label="Extended target · 16-24s",
        prompt_guidance="Use about 16-24 seconds so viewers can compare two or three columns clearly.",
    ),
    "popup_sequence": VisualModeDurationTarget(
        visual_mode="popup_sequence",
        profile="extended",
        min_seconds=12.0,
        target_seconds=17.0,
        max_seconds=22.0,
        ui_label="Extended target · 14-20s",
        prompt_guidance="Use about 14-20 seconds so each popup item has time to appear and register.",
    ),
    "stat_card": VisualModeDurationTarget(
        visual_mode="stat_card",
        profile="medium",
        min_seconds=8.0,
        target_seconds=12.0,
        max_seconds=16.0,
        ui_label="Medium target · 10-14s",
        prompt_guidance="Use about 10-14 seconds unless the statistic is only a quick punch.",
    ),
    "video": VisualModeDurationTarget(
        visual_mode="video",
        profile="planned",
        min_seconds=5.0,
        target_seconds=8.0,
        max_seconds=14.0,
        ui_label="Planned video · validated after voiceover",
        prompt_guidance="Plan video before voiceover only when motion clearly improves the scene; validation may downgrade unsafe choices after timing exists.",
    ),
}


def duration_target_for_mode(visual_mode: str | None) -> VisualModeDurationTarget:
    return _TARGETS.get(visual_mode or "", _TARGETS["full_frame"])


def duration_profile_for_mode(visual_mode: str | None) -> str:
    return duration_target_for_mode(visual_mode).profile


def max_scene_seconds_for_mode(visual_mode: str | None) -> float:
    return duration_target_for_mode(visual_mode).max_seconds


def target_scene_seconds_for_mode(visual_mode: str | None) -> float:
    return duration_target_for_mode(visual_mode).target_seconds


def prompt_duration_guidance() -> str:
    lines = [
        "Scene duration is driven by visual_mode, not script type, and is planned before voiceover.",
        "Use full_frame, multi_frame, continuous, and flipflop as normal short scenes around 5-9 seconds.",
        "Use captions around 14-18 seconds so the editorial text has context.",
        "Use comparison_board around 16-24 seconds so viewers can compare the columns.",
        "Use popup_sequence around 14-20 seconds so item layers can appear clearly.",
        "Use stat_card around 10-14 seconds unless it is a very fast numerical punch.",
        "Plan video scenes before voiceover when motion clearly improves the beat; later validation may downgrade unsafe video choices.",
    ]
    return "\n".join(f"- {line}" for line in lines)
```

- [ ] **Step 4: Run the policy tests**

Run:

```bash
uv run --project backend pytest backend/tests/pipeline/test_visual_mode_policy.py -q
```

Expected: PASS.

- [ ] **Step 5: Commit the backend policy module**

Run:

```bash
git add backend/pipeline/visual_mode_policy.py backend/tests/pipeline/test_visual_mode_policy.py
git commit -m "Add visual mode duration policy"
```

## Task 2: Prompt And Scene Splitting Integration

**Files:**
- Modify: `backend/pipeline/scriptwriter.py`
- Modify: `backend/pipeline/formats/life_as_a.py`
- Modify: `backend/pipeline/formats/youtube_listicle.py`
- Modify: `backend/prompts/script.py`
- Modify: `docs/formats/AUTHORING.md`
- Test: `backend/tests/pipeline/test_scriptwriter_visual_beats.py`
- Test: `backend/tests/pipeline/test_life_as_a_post_processing.py`

- [ ] **Step 1: Write failing tests for profile-aware splitting**

Append to `backend/tests/pipeline/test_scriptwriter_visual_beats.py`:

```python
def test_scene_granularity_preserves_extended_visual_mode_scene():
    content = ScriptContent(
        title="Test",
        intro_hook="",
        outro_cta="",
        segments=[
            Segment(
                name="Segment",
                scenes=[
                    Scene(
                        id="scene_001",
                        narration=(
                            "The old choice looks safe from the outside. "
                            "The new choice costs more up front. "
                            "By the end of the month, the cheap option is the expensive one."
                        ),
                        visual_prompt="Two choices compared side by side.",
                        duration_estimate_seconds=20.0,
                        visual_mode="comparison_board",
                    )
                ],
            )
        ],
    )

    changed = _ensure_scene_granularity(content)

    assert changed == 0
    assert len(content.segments[0].scenes) == 1
    assert content.segments[0].scenes[0].visual_mode == "comparison_board"
```

Append to `backend/tests/pipeline/test_life_as_a_post_processing.py`:

```python
def test_life_as_a_chunking_preserves_extended_visual_mode_scene(monkeypatch):
    monkeypatch.setenv("LIFE_AS_A_CHUNKING_ENABLED", "true")
    content = ScriptContent(
        title="Your Life As A Night Guard",
        intro_hook="",
        outro_cta="",
        format_id="life-as-a",
        segments=[
            Segment(
                name="Level 1, the occasional",
                scenes=[
                    Scene(
                        id="scene_001",
                        narration="The occasional.",
                        visual_prompt="",
                        duration_estimate_seconds=4.0,
                        is_title_card=True,
                    ),
                    Scene(
                        id="scene_002",
                        narration=(
                            "On the left is the guard you thought you would be. "
                            "On the right is the person who keeps checking the same hallway. "
                            "The difference is only visible after midnight."
                        ),
                        visual_prompt="[REACTION] A night guard comparison scene.",
                        duration_estimate_seconds=20.0,
                        visual_mode="comparison_board",
                    ),
                ],
            )
        ],
    )

    changed = _split_life_as_a_scenes(content)

    assert changed == 0
    assert len(content.segments[0].scenes) == 2
    assert content.segments[0].scenes[1].visual_mode == "comparison_board"
```

- [ ] **Step 2: Run the failing split tests**

Run:

```bash
uv run --project backend pytest \
  backend/tests/pipeline/test_scriptwriter_visual_beats.py::test_scene_granularity_preserves_extended_visual_mode_scene \
  backend/tests/pipeline/test_life_as_a_post_processing.py::test_life_as_a_chunking_preserves_extended_visual_mode_scene \
  -q
```

Expected: FAIL because current splitting uses the normal max for all modes.

- [ ] **Step 3: Make generic scene splitting profile-aware**

In `backend/pipeline/scriptwriter.py`, import the policy:

```python
from pipeline.visual_mode_policy import (
    max_scene_seconds_for_mode,
    prompt_duration_guidance,
    target_scene_seconds_for_mode,
)
```

Change `_scene_granularity_duration` to use the mode target:

```python
def _scene_granularity_duration(scene: Scene, sentence_count: int) -> float:
    target_seconds = target_scene_seconds_for_mode(scene.visual_mode)
    if scene.duration_estimate_seconds > 0:
        if scene.duration_estimate_seconds <= target_seconds and sentence_count > 2:
            return sentence_count * target_seconds
        return float(scene.duration_estimate_seconds)
    return sentence_count * target_seconds
```

Change `_ensure_scene_granularity` so the max and chunk target are mode-specific:

```python
            target_seconds = target_scene_seconds_for_mode(scene.visual_mode)
            max_seconds = max_scene_seconds_for_mode(scene.visual_mode)
            should_split = len(sentences) > 2 and estimated_duration > max_seconds
            if not should_split or len(sentences) <= 1:
                rewritten.append(scene)
                continue

            chunk_count = max(2, int((estimated_duration + target_seconds - 1) // target_seconds))
```

Keep the existing chunk copy behavior after that block.

- [ ] **Step 4: Make life-as-a chunking profile-aware**

In `backend/pipeline/formats/life_as_a.py`, import:

```python
from pipeline.visual_mode_policy import max_scene_seconds_for_mode, target_scene_seconds_for_mode
```

Change `_scene_estimated_duration` to:

```python
def _scene_estimated_duration(scene: Scene, *, target_seconds: int) -> float:
    mode_target_seconds = target_scene_seconds_for_mode(scene.visual_mode)
    sentence_count = len(_split_sentences(scene.narration))
    if scene.duration_estimate_seconds > 0:
        if scene.duration_estimate_seconds <= mode_target_seconds and sentence_count > 2:
            return sentence_count * float(mode_target_seconds)
        return float(scene.duration_estimate_seconds)
    return max(float(mode_target_seconds), sentence_count * float(mode_target_seconds))
```

In `_split_life_as_a_scenes`, replace the single `effective_max_seconds` check with mode-specific max:

```python
            mode_target_seconds = target_scene_seconds_for_mode(scene.visual_mode)
            mode_max_seconds = max_scene_seconds_for_mode(scene.visual_mode)
            estimated_duration = _scene_estimated_duration(scene, target_seconds=target_seconds)
            sentences = _split_sentences(scene.narration)
            effective_max_seconds = min(max(mode_max_seconds, float(max_seconds)), 26.0)
            if estimated_duration <= effective_max_seconds or len(sentences) <= 1:
                logger.info(
                    "[LIFE_AS_A_CHUNKING] kept scene %s; reason=duration %.1fs within target",
                    scene.id,
                    estimated_duration,
                )
                rewritten.append(scene)
                continue

            chunk_count = min(len(sentences), max(2, math.ceil(estimated_duration / mode_target_seconds)))
```

- [ ] **Step 5: Add duration policy guidance to prompts**

In `backend/pipeline/scriptwriter.py`, find the prompt assembly where visual-mode instructions are appended. Add:

```python
        "\n\n## VISUAL MODE DURATION POLICY\n"
        f"{prompt_duration_guidance()}\n"
```

In `backend/prompts/script.py`, update the visual mode vocabulary text:

```markdown
- "video" — Plan this before voiceover when motion clearly improves the scene. Later validation may downgrade the scene if real timing, adjacency, duration, or assets make video unsafe. Aim for at least three planned video scenes per project when the topic naturally supports motion, but never force video into static diagrams, title cards, captions, or scenes that need precise readable text.
```

Also replace every unconditional `~5-9s` non-title instruction with:

```markdown
Normal modes (`full_frame`, `multi_frame`, `continuous`, `flipflop`) target ~5-9s. Renderer-owned modes use their visual-mode duration policy: `captions` ~14-18s, `comparison_board` ~16-24s, `popup_sequence` ~14-20s, and `stat_card` ~10-14s. Plan these durations before voiceover.
```

- [ ] **Step 6: Update format reference notes and authoring docs**

In `backend/pipeline/formats/life_as_a.py`, replace the Scene length note with:

```python
        FormatNote(category="Scene length",
                   text="Scene length follows the universal visual-mode policy: normal modes stay short, while renderer-owned modes such as captions and comparison_board may carry longer narration before voiceover."),
```

In `backend/pipeline/formats/youtube_listicle.py`, add a reference note:

```python
        FormatNote(category="Scene length",
                   text="Scene length follows the universal visual-mode policy, so comparison boards, captions, popup sequences, stat cards, and planned video scenes can be longer than normal full-frame beats."),
```

In `docs/formats/AUTHORING.md`, replace the sentence that says life-as-a has a format-specific chunker for 5-9 second single-beat scenes with:

```markdown
**Important:** Per scene, narration length and beat distribution start in the prompt, but the orchestrator also enforces scene-length protection before voiceover. Scene-length protection is visual-mode-aware for every format: normal modes stay short, while renderer-owned modes such as `captions`, `comparison_board`, `popup_sequence`, and `stat_card` may remain longer single scenes when their mode profile calls for it. Do not add post-voiceover narration rewrites for pacing.
```

- [ ] **Step 7: Run split and prompt-related backend tests**

Run:

```bash
uv run --project backend pytest \
  backend/tests/pipeline/test_visual_mode_policy.py \
  backend/tests/pipeline/test_scriptwriter_visual_beats.py \
  backend/tests/pipeline/test_life_as_a_post_processing.py \
  backend/tests/pipeline/test_formats_registry.py \
  -q
```

Expected: PASS.

- [ ] **Step 8: Commit prompt and splitting integration**

Run:

```bash
git add \
  backend/pipeline/scriptwriter.py \
  backend/pipeline/formats/life_as_a.py \
  backend/pipeline/formats/youtube_listicle.py \
  backend/prompts/script.py \
  backend/tests/pipeline/test_scriptwriter_visual_beats.py \
  backend/tests/pipeline/test_life_as_a_post_processing.py \
  docs/formats/AUTHORING.md
git commit -m "Apply visual mode duration policy to script planning"
```

## Task 3: Post-Voiceover Validation Semantics

**Files:**
- Modify: `backend/pipeline/media_analyzer.py`
- Modify: `backend/api/media.py`
- Modify: `backend/api/visual_treatments.py`
- Test: `backend/tests/test_media_analysis_flags.py`

- [ ] **Step 1: Write failing validation test for planned video preservation**

Append to `backend/tests/test_media_analysis_flags.py`:

```python
def test_media_analysis_preserves_planned_video_when_valid(monkeypatch):
    content = ScriptContent(
        title="Test",
        intro_hook="",
        outro_cta="",
        segments=[
            Segment(
                name="Segment",
                scenes=[
                    Scene(
                        id="scene_001",
                        narration="The room starts moving around him.",
                        visual_prompt="[REACTION] A person stepping through a moving room.",
                        duration_estimate_seconds=8.0,
                        audio_duration_seconds=5.8,
                        visual_mode="video",
                        contains_person=True,
                    )
                ],
            )
        ],
    )

    assignments = analyze_media_sources(
        content,
        animated_scene_count=3,
        ai_video_enabled=True,
        ai_video_scenes_per_segment=3,
        script_id="test",
    )

    assert assignments[0].visual_mode == "video"
```

Patch the existing analyzer chat call inside the test so it returns `{"assignments": [{"scene_id": "scene_001", "visual_mode": "full_frame", "reasoning": "No change"}]}`. That proves existing script-owned `video` is preserved when valid even if the analyzer response tries to fall back to `full_frame`.

- [ ] **Step 2: Run the failing validation test**

Run:

```bash
uv run --project backend pytest backend/tests/test_media_analysis_flags.py::test_media_analysis_preserves_planned_video_when_valid -q
```

Expected: FAIL if planned video is downgraded or if comments still assume video is only analyzer-selected.

- [ ] **Step 3: Update media analyzer language and preservation rules**

In `backend/pipeline/media_analyzer.py`:

- Update comments/docstrings from "promotion only" to "planned video validation".
- Ensure `_valid_existing_script_mode(scene)` returns `video` when the scene is valid and `ai_video_available` is true.
- In assignment normalization, keep planned `video` when `_is_ai_video_eligible(...)` returns true and spacing/caps permit it.
- When downgrading planned `video`, set reasoning text:

```python
reasoning="Planned AI video was downgraded because real voiceover timing, adjacency, duration, or scene content made it ineligible."
```

In `backend/api/media.py` and `backend/api/visual_treatments.py`, update user-facing job text from "analyze/re-analyze visual modes" toward "validate visual modes" where the endpoint is post-voiceover.

- [ ] **Step 4: Run media tests**

Run:

```bash
uv run --project backend pytest backend/tests -q
```

Expected: PASS. If the whole suite is too slow, run the exact media analyzer/API files first, then run the full backend suite before final completion.

- [ ] **Step 5: Commit validation semantics**

Run:

```bash
git add backend/pipeline/media_analyzer.py backend/api/media.py backend/api/visual_treatments.py backend/tests
git commit -m "Validate planned visual modes after voiceover"
```

## Task 4: Frontend Policy Metadata And Timeline UI

**Files:**
- Modify: `frontend/src/components/settings/visual-modes/catalog.ts`
- Modify: `frontend/src/components/settings/visual-modes/VisualModeDetail.tsx`
- Modify: `frontend/src/components/timeline/VisualTreatmentReviewPanel.tsx`
- Modify: `frontend/src/components/timeline/MediaSourcesTab.tsx`
- Modify: `frontend/src/components/timeline/PropertiesPanel.tsx`
- Modify: `frontend/src/components/timeline/TimelineBlock.tsx`
- Test: `frontend/src/components/settings/visual-modes/VisualModesSection.test.tsx`
- Test: `frontend/src/components/timeline/VisualTreatmentReviewPanel.test.tsx`

- [ ] **Step 1: Write failing frontend tests for duration profile visibility**

Create `frontend/src/components/settings/visual-modes/VisualModesSection.test.tsx`:

```tsx
import { render, screen } from "@testing-library/react";
import VisualModesSection from "./VisualModesSection";

describe("VisualModesSection duration workflow", () => {
  it("explains that visual modes plan duration before voiceover", () => {
    render(<VisualModesSection />);

    expect(screen.getByText(/planned before voiceover/i)).toBeInTheDocument();
    expect(screen.getByText(/duration targets are tied to visual mode/i)).toBeInTheDocument();
  });
});
```

In `frontend/src/components/timeline/VisualTreatmentReviewPanel.test.tsx`, add:

```tsx
it("shows duration profile labels in the visual mode catalog", () => {
  render(
    <VisualModeCatalog counts={{ ...EMPTY_VISUAL_MODE_COUNTS, comparison_board: 1 }} />,
  );

  expect(screen.getByText(/Extended target/i)).toBeInTheDocument();
  expect(screen.getByText(/Comparison board/i)).toBeInTheDocument();
});
```

- [ ] **Step 2: Run failing frontend tests**

Run:

```bash
npm run test:frontend -- VisualModesSection VisualTreatmentReviewPanel
```

Expected: FAIL because the new workflow/profile text does not exist yet.

- [ ] **Step 3: Add frontend duration profile metadata**

In `frontend/src/components/settings/visual-modes/catalog.ts`, extend `VisualModeEntry`:

```ts
export type DurationProfile = "normal" | "medium" | "extended" | "planned";

export interface VisualModeEntry {
  id: VisualMode;
  label: string;
  shortDescription: string;
  longDescription: string;
  previewSrc: string;
  durationProfile: DurationProfile;
  durationLabel: string;
  durationDescription: string;
  requiredFields: string[];
  optionalFields: string[];
  compatibility: VisualModeCompatibility;
  distribution: string;
  routing: string;
  notCompatibleWith: string[];
  rendererPath: string;
}
```

Add helper functions:

```ts
export function visualModeEntry(mode: VisualMode): VisualModeEntry {
  return VISUAL_MODE_CATALOG.find((entry) => entry.id === mode) ?? VISUAL_MODE_CATALOG[0];
}

export function durationLabelForMode(mode: VisualMode): string {
  return visualModeEntry(mode).durationLabel;
}
```

Populate entries:

```ts
durationProfile: "extended",
durationLabel: "Extended target · 16-24s",
durationDescription: "Planned longer before voiceover so viewers can compare the board columns.",
```

Use equivalent labels from the spec for every entry.

- [ ] **Step 4: Show workflow copy in Settings -> Reference**

In `VisualModesSection.tsx`, add a top unboxed section below the header:

```tsx
<div className="rounded-lg border border-neutral-800 bg-neutral-900/60 p-4">
  <h3 className="text-sm font-semibold text-neutral-100">Selection workflow</h3>
  <p className="mt-2 text-xs leading-5 text-neutral-400">
    Script generation plans the intended visual rhythm before voiceover. Duration targets are tied to visual mode, not script type: normal modes stay short, while captions, comparison boards, popup sequences, and stat cards get more narration when the visual needs time to read.
  </p>
  <p className="mt-2 text-xs leading-5 text-neutral-500">
    After voiceover, validation fills timing and layer metadata and may downgrade planned video or layered modes that are not safe to render.
  </p>
</div>
```

- [ ] **Step 5: Show selected mode profile in VisualModeDetail**

In `VisualModeDetail.tsx`, add a small metadata row:

```tsx
<div className="rounded-md border border-neutral-800 bg-neutral-950/60 px-3 py-2">
  <p className="text-[10px] font-semibold uppercase text-neutral-500">Duration profile</p>
  <p className="mt-1 text-xs font-medium text-neutral-200">{entry.durationLabel}</p>
  <p className="mt-1 text-xs leading-5 text-neutral-500">{entry.durationDescription}</p>
</div>
```

- [ ] **Step 6: Add profile hints to Timeline visual mode controls**

In `PropertiesPanel.tsx`, import `visualModeEntry`:

```ts
import { visualModeEntry } from "../settings/visual-modes/catalog";
```

Derive:

```ts
const modeEntry = visualModeEntry(visualMode);
```

Change button title:

```tsx
title={`${opt.label}: ${visualModeEntry(opt.value).durationLabel}`}
```

Add helper copy below the mode buttons:

```tsx
<p className="text-[10px] leading-snug text-neutral-500">
  {modeEntry.durationLabel}. {modeEntry.durationDescription}
</p>
```

In `TimelineBlock.tsx`, import `durationLabelForMode` and add a compact `title` to image blocks:

```tsx
title={laneType === "images" ? durationLabelForMode(scene.visual_mode ?? "full_frame") : undefined}
```

- [ ] **Step 7: Reframe post-voiceover review UI**

In `MediaSourcesTab.tsx`, change:

```ts
const visualTreatmentAnalyzeLabel = hasExistingVisualModeReview ? "Re-analyze Visual Modes" : "Analyze Visual Modes";
```

to:

```ts
const visualTreatmentAnalyzeLabel = hasExistingVisualModeReview ? "Re-validate Visual Modes" : "Validate Visual Modes";
```

Change helper text:

```tsx
<p className="text-xs text-neutral-500">
  Validate planned modes after voiceover, fill timing/layer metadata, and prepare assets for render.
</p>
```

In `VisualTreatmentReviewPanel.tsx`, update the header paragraph:

```tsx
Visual mode is planned before voiceover. This review validates timing, layers, and render readiness; it may downgrade modes that are not safe to render.
```

Add each catalog card's profile line using `visualModeEntry(mode).durationLabel`.

- [ ] **Step 8: Run frontend tests**

Run:

```bash
npm run test:frontend -- VisualModesSection VisualTreatmentReviewPanel
```

Expected: PASS.

- [ ] **Step 9: Commit frontend UI metadata**

Run:

```bash
git add frontend/src/components/settings/visual-modes frontend/src/components/timeline
git commit -m "Show visual mode duration workflow in UI"
```

## Task 5: Full Verification, Review Loop, And Push

**Files:**
- Verify all changed files.
- Update `AGENTS.md` only if implementation diverged from the existing convention.

- [ ] **Step 1: Run backend verification**

Run:

```bash
npm run test:backend
```

Expected: PASS.

- [ ] **Step 2: Run frontend verification**

Run:

```bash
npm run test:frontend
```

Expected: PASS.

- [ ] **Step 3: Build frontend**

Run:

```bash
cd frontend && npm run build
```

Expected: PASS.

- [ ] **Step 4: Inspect final diff**

Run:

```bash
git status --short
git diff --stat HEAD
```

Expected: only intended implementation files are modified.

- [ ] **Step 5: Commit any final doc/convention adjustments**

If `AGENTS.md` or docs changed after prior commits, run:

```bash
git add AGENTS.md docs frontend backend
git commit -m "Update visual mode duration documentation"
```

If there are no unstaged changes, skip this commit.

- [ ] **Step 6: Push main**

Run:

```bash
git push origin main
```

Expected: push succeeds.

- [ ] **Step 7: Run delegated code review per project rule**

Dispatch a code review agent with this exact prompt:

```text
Review the most recent commit on the main branch of this project.
Run `git diff HEAD~1..HEAD` to see the changes and `git show --stat HEAD` for context.
Read the full affected files (not just the diff) to understand surrounding code.
Check for: correctness bugs, error handling gaps, security issues, naive/aware datetime mismatches, unhandled promise rejections, race conditions, and style problems.
Return a structured verdict: either LGTM or NEEDS CHANGES.
If NEEDS CHANGES, provide a numbered list of findings with severity (FAIL/WARN), file:line, and a specific description of what's wrong and how to fix it.
```

Expected: LGTM or actionable findings. If NEEDS CHANGES, fix every FAIL and WARN finding, commit as `fix: address review findings`, push, and repeat this review step until LGTM.
