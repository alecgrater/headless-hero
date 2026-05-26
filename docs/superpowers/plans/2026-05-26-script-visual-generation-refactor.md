# Script Visual Generation Refactor Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace scattered script visual selection with a canonical post-voiceover visual planner that works across listicle and life-as-a projects.

**Architecture:** Script generation produces short single-beat scenes and visual intent only. A new `pipeline.visual_mode_planner` runs after voiceover timing exists, uses one high-quality project-level LLM call, validates/repairs canonical mode assignments, then downstream generation/rendering dispatches by `visual_mode`. Hook scoring is removed from generated-project flow.

**Tech Stack:** Python 3.12/FastAPI/SQLModel/Pydantic, React 19/TypeScript/Vite, Remotion 4, pytest, Vitest.

---

## File Structure

- Modify `backend/models/script.py`: canonical mode fields, hook-score removal, summary shape.
- Modify `backend/pipeline/formats/base.py`: replace `VisualBeatRules` with shared scene cleanup and `VisualModeRules`.
- Modify `backend/pipeline/formats/youtube_listicle.py`: listicle visual rules and shared short-scene cleanup config.
- Modify `backend/pipeline/formats/life_as_a.py`: keep life-as-a voice/chapter cleanup, remove visual beat coercion, call shared cleanup.
- Create `backend/pipeline/scene_cleanup.py`: shared short single-beat scene cleanup and split helpers.
- Create `backend/pipeline/visual_mode_planner.py`: planner request/response models, voiceover gate, LLM call, validation, repair, apply.
- Modify `backend/prompts/script.py`: remove final visual mode assignment and legacy visual vocabulary from script prompts.
- Create `backend/prompts/visual_mode_planner.py`: visual planner prompt.
- Modify `backend/integrations/llm_client.py`, `backend/api/settings.py`, `frontend/src/components/settings/GeneralSection.tsx`: add `visual_planner` model route; remove hook route if no longer used.
- Modify `backend/api/scripts.py`: remove hook scoring and pre-voiceover media analysis from generation.
- Create `backend/api/visual_modes.py`: unified visual planner endpoints.
- Modify `backend/api/__init__.py`: register visual modes router.
- Modify or remove `backend/api/media.py` and `backend/api/visual_treatments.py`: delegate to planner during migration or remove callers.
- Modify `backend/pipeline/media_analyzer.py` and `backend/pipeline/visual_treatments.py`: retire or turn into compatibility wrappers.
- Modify `backend/pipeline/image_gen.py`, `backend/api/visuals.py`, `backend/pipeline/remotion_render.py`: dispatch by `visual_mode`.
- Modify `backend/pipeline/fx_generator.py`, `backend/api/fx.py`: assign generic FX only for `full_frame`.
- Modify frontend timeline/media-review/visual-treatment/Test Lab components to expose one visual mode flow.
- Modify `AGENTS.md` and docs authoring references.

---

### Task 1: Add Canonical Visual Planner Settings Route

**Files:**
- Modify: `backend/integrations/llm_client.py`
- Modify: `backend/api/settings.py`
- Modify: `frontend/src/components/settings/GeneralSection.tsx`
- Test: `backend/tests/test_llm_routing.py`
- Test: frontend settings test if one exists near `frontend/src/components/settings`

- [ ] **Step 1: Write failing backend test**

Add to `backend/tests/test_llm_routing.py`:

```python
def test_visual_planner_uses_script_quality_defaults(monkeypatch):
    from integrations.llm_client import LLM_TASKS, _resolve_model, _resolve_openai_reasoning_effort, _resolve_provider

    monkeypatch.delenv("VISUAL_PLANNER_LLM_PROVIDER", raising=False)
    monkeypatch.delenv("VISUAL_PLANNER_MODEL", raising=False)
    monkeypatch.delenv("OPENAI_REASONING_EFFORT_VISUAL_PLANNER", raising=False)

    task = LLM_TASKS["visual_planner"]

    assert task["label"] == "Visual planner"
    assert task["provider_key"] == "VISUAL_PLANNER_LLM_PROVIDER"
    assert task["model_key"] == "VISUAL_PLANNER_MODEL"
    assert _resolve_provider("visual_planner") == "anthropic"
    assert _resolve_model("visual_planner").startswith("claude-")
    assert _resolve_openai_reasoning_effort("visual_planner") == "low"
```

- [ ] **Step 2: Run test to verify it fails**

Run:

```bash
uv run --project backend pytest backend/tests/test_llm_routing.py::test_visual_planner_uses_script_quality_defaults -q
```

Expected: fail with `KeyError: 'visual_planner'`.

- [ ] **Step 3: Add backend task config**

In `backend/integrations/llm_client.py`, add:

```python
"visual_planner": {
    "label": "Visual planner",
    "provider_key": "VISUAL_PLANNER_LLM_PROVIDER",
    "model_key": "VISUAL_PLANNER_MODEL",
    "default_provider": "anthropic",
    "default_anthropic_model": DEFAULT_CLAUDE_MODEL,
    "default_openai_model": DEFAULT_OPENAI_MODEL,
    "openai_reasoning_effort": "low",
},
```

In `backend/api/settings.py`, ensure the task-loop defaults expose `VISUAL_PLANNER_LLM_PROVIDER`, `VISUAL_PLANNER_MODEL`, and `OPENAI_REASONING_EFFORT_VISUAL_PLANNER`; the existing task loop should do this once the new task exists.

- [ ] **Step 4: Add frontend settings row**

In `frontend/src/components/settings/GeneralSection.tsx`, add an `LLM_TASKS` item:

```ts
{
  id: "visual_planner",
  label: "Visual planner",
  description: "Chooses scene visual modes and mode-specific generation plans after voiceover timing exists.",
  providerKey: "VISUAL_PLANNER_LLM_PROVIDER",
  modelKey: "VISUAL_PLANNER_MODEL",
  reasoningKey: "OPENAI_REASONING_EFFORT_VISUAL_PLANNER",
  defaultProvider: "anthropic",
  defaultModel: DEFAULT_MODEL,
  openaiDefaultModel: "gpt-5.5",
  ollamaDefaultModel: "qwen3:14b",
  defaultReasoning: "low",
},
```

- [ ] **Step 5: Verify**

Run:

```bash
uv run --project backend pytest backend/tests/test_llm_routing.py -q
cd frontend && npm run test -- --run
```

Expected: backend routing tests pass; frontend tests pass or no matching tests run without new failures.

---

### Task 2: Remove Generated-Project Hook Scoring

**Files:**
- Modify: `backend/models/script.py`
- Modify: `backend/api/scripts.py`
- Modify: `backend/api/formats.py`
- Modify: `backend/pipeline/formats/base.py`
- Modify: `backend/pipeline/formats/youtube_listicle.py`
- Modify: `backend/pipeline/formats/life_as_a.py`
- Modify: `frontend/src/types/script.ts`
- Modify: `frontend/src/types/format.ts`
- Modify: `frontend/src/components/dashboard/ProjectDashboard.tsx`
- Delete or orphan no-longer-used: `frontend/src/components/script/useHookScore.ts`, `frontend/src/components/script/HookScoreCard.tsx` if unused after cold-open cleanup
- Test: `backend/tests/pipeline/test_formats_registry.py`
- Test: `backend/tests/test_script_summaries.py`

- [ ] **Step 1: Write failing backend tests**

Update `backend/tests/pipeline/test_formats_registry.py` so formats no longer expose hook scoring:

```python
def test_formats_do_not_expose_hook_scoring_flag():
    from pipeline.formats import list_formats

    for fmt in list_formats():
        assert not hasattr(fmt, "supports_hook_scoring")
```

Add to `backend/tests/test_script_summaries.py`:

```python
def test_script_summary_no_longer_exposes_hook_score():
    from models.script import ScriptSummary

    assert "hook_score_overall" not in ScriptSummary.model_fields
```

- [ ] **Step 2: Run tests to verify failure**

Run:

```bash
uv run --project backend pytest backend/tests/pipeline/test_formats_registry.py::test_formats_do_not_expose_hook_scoring_flag backend/tests/test_script_summaries.py::test_script_summary_no_longer_exposes_hook_score -q
```

Expected: both fail because hook scoring fields still exist.

- [ ] **Step 3: Remove backend script hook scoring**

In `backend/api/scripts.py`:

- remove `HookScore` import
- remove `from pipeline.hook_scorer import score_hook`
- remove `supports_hook_scoring = fmt.supports_hook_scoring`
- delete the auto-score block beginning with `# Auto-score the hook on the final generated script`
- delete `HookScoreResponse`
- delete `hook_score_endpoint`
- remove `hook_score_overall=...` from summaries

In `backend/models/script.py`:

- remove `HookScoreDimension`
- remove `HookScore`
- remove `hook_score: dict | None`
- remove `hook_score_overall` from `ScriptSummary`

In `backend/pipeline/formats/base.py`:

- remove `supports_hook_scoring: bool`

In format registrations:

```python
# delete these arguments
supports_hook_scoring=True
supports_hook_scoring=False
```

In `backend/api/formats.py` and `frontend/src/types/format.ts`, remove `supports_hook_scoring`.

- [ ] **Step 4: Remove generated-project hook UI**

In `frontend/src/components/dashboard/ProjectDashboard.tsx`, remove `HookRatingBadge` and all `project.hook_score_overall` display branches.

In `frontend/src/types/script.ts`, remove `HookScore`, `HookScoreDimension`, `hook_score`, and `hook_score_overall`.

In `frontend/src/api.ts`, remove `scoreHook` and related script hook-score types.

If `HookScoreCard` is still used only by cold-open/idea features, remove those usages in the same task and replace with simple cold-open status text. If cold-open generation still needs hook text, keep cold-open generation but remove hook scoring/refinement display.

- [ ] **Step 5: Verify hook references**

Run:

```bash
rg -n "hook_score|HookScore|scoreHook|supports_hook_scoring|hook-score" backend frontend docs/formats/AUTHORING.md AGENTS.md
```

Expected: only historical docs under `docs/superpowers/` may mention old hook scoring. Runtime backend/frontend code should not.

- [ ] **Step 6: Run tests**

Run:

```bash
uv run --project backend pytest backend/tests/pipeline/test_formats_registry.py backend/tests/test_script_summaries.py -q
cd frontend && npm run test -- --run
```

Expected: all pass.

---

### Task 3: Introduce Shared Short-Scene Cleanup

**Files:**
- Create: `backend/pipeline/scene_cleanup.py`
- Modify: `backend/pipeline/formats/base.py`
- Modify: `backend/pipeline/formats/life_as_a.py`
- Modify: `backend/pipeline/scriptwriter.py`
- Test: `backend/tests/pipeline/test_scene_cleanup.py`
- Test: `backend/tests/pipeline/test_life_as_a_post_processing.py`

- [ ] **Step 1: Write failing shared cleanup tests**

Create `backend/tests/pipeline/test_scene_cleanup.py`:

```python
from models.script import Scene, ScriptContent, Segment
from pipeline.scene_cleanup import enforce_short_single_beat_scenes


def _scene(scene_id: str, narration: str, duration: float = 14.0) -> Scene:
    return Scene(
        id=scene_id,
        narration=narration,
        visual_prompt="[ESTABLISHING] A clean full-bleed visual moment.",
        duration_estimate_seconds=duration,
        visual_mode="full_frame",
    )


def test_cleanup_splits_multi_sentence_overlong_scene_and_resets_assets():
    content = ScriptContent(
        title="Test",
        format_id="youtube-listicle",
        segments=[
            Segment(
                name="Segment",
                scenes=[
                    _scene(
                        "scene_001",
                        "First the room goes quiet. Then the phone lights up. Finally the mistake becomes obvious.",
                    )
                ],
            )
        ],
    )

    changed = enforce_short_single_beat_scenes(content, target_seconds=8, max_seconds=12)

    scenes = content.segments[0].scenes
    assert changed == 1
    assert len(scenes) == 3
    assert [scene.id for scene in scenes] == ["scene_001", "scene_002", "scene_003"]
    assert all(scene.audio_url == "" for scene in scenes)
    assert all(scene.audio_duration_seconds == 0 for scene in scenes)
    assert all(scene.word_timestamps is None for scene in scenes)
    assert all(scene.visual_mode == "full_frame" for scene in scenes)


def test_cleanup_keeps_single_beat_scene_under_soft_limit():
    content = ScriptContent(
        title="Test",
        format_id="life-as-a",
        segments=[Segment(name="Level", scenes=[_scene("scene_001", "You stare at the same locked door.", 9.0)])],
    )

    changed = enforce_short_single_beat_scenes(content, target_seconds=8, max_seconds=12)

    assert changed == 0
    assert len(content.segments[0].scenes) == 1
```

- [ ] **Step 2: Run tests to verify failure**

Run:

```bash
uv run --project backend pytest backend/tests/pipeline/test_scene_cleanup.py -q
```

Expected: fail because `pipeline.scene_cleanup` does not exist.

- [ ] **Step 3: Implement shared cleanup module**

Create `backend/pipeline/scene_cleanup.py`:

```python
"""Shared scene cleanup for short, single-beat generation."""

from __future__ import annotations

import copy
import re

from models.script import Scene, ScriptContent

_SENTENCE_RE = re.compile(r"[^.!?]+[.!?]+|[^.!?]+$")


def split_sentences(text: str) -> list[str]:
    return [part.strip() for part in _SENTENCE_RE.findall(text or "") if part.strip()]


def should_split_scene(scene: Scene, *, max_seconds: float) -> bool:
    if scene.is_title_card:
        return False
    sentences = split_sentences(scene.narration)
    return scene.duration_estimate_seconds > max_seconds and len(sentences) > 1


def reset_generated_state(scene: Scene) -> None:
    scene.image_url = ""
    scene.audio_url = ""
    scene.audio_duration_seconds = 0.0
    scene.word_timestamps = None
    scene.phrase_timestamps = None
    scene.frame_urls = []
    scene.frame_directives = []
    scene.visual_layers = []
    scene.video_url = ""
    scene.fx = None
    scene.set_visual_mode("full_frame")


def _renumber_scenes(content: ScriptContent) -> None:
    index = 1
    for segment in content.segments:
        for scene in segment.scenes:
            if scene.is_title_card and scene.id.startswith("chapter_"):
                continue
            scene.id = f"scene_{index:03d}"
            index += 1


def enforce_short_single_beat_scenes(
    content: ScriptContent,
    *,
    target_seconds: float = 8.0,
    max_seconds: float = 12.0,
) -> int:
    changed = 0
    for segment in content.segments:
        next_scenes: list[Scene] = []
        for scene in segment.scenes:
            if not should_split_scene(scene, max_seconds=max_seconds):
                next_scenes.append(scene)
                continue
            sentences = split_sentences(scene.narration)
            per_scene_duration = min(target_seconds, max(scene.duration_estimate_seconds / len(sentences), 4.0))
            for sentence in sentences:
                chunk = copy.deepcopy(scene)
                chunk.narration = sentence
                chunk.duration_estimate_seconds = per_scene_duration
                reset_generated_state(chunk)
                next_scenes.append(chunk)
            changed += 1
        segment.scenes = next_scenes
    if changed:
        _renumber_scenes(content)
    return changed
```

- [ ] **Step 4: Wire shared cleanup into scriptwriter**

In `backend/pipeline/formats/base.py`, add fields:

```python
scene_target_seconds: float = 8.0
scene_max_seconds: float = 12.0
```

In `backend/pipeline/scriptwriter.py`, after format-specific post-processing and before script rating happens in API code, call:

```python
from pipeline.scene_cleanup import enforce_short_single_beat_scenes

enforce_short_single_beat_scenes(
    content,
    target_seconds=fmt.scene_target_seconds,
    max_seconds=fmt.scene_max_seconds,
)
```

In `backend/pipeline/formats/life_as_a.py`, remove duplicated long-scene chunking when it conflicts with the shared cleanup and keep only life-as-a-specific chapter/narration cleanup.

- [ ] **Step 5: Verify**

Run:

```bash
uv run --project backend pytest backend/tests/pipeline/test_scene_cleanup.py backend/tests/pipeline/test_life_as_a_post_processing.py -q
```

Expected: all pass after updating life-as-a tests away from visual beat assumptions.

---

### Task 4: Remove Legacy Visual Vocabulary From Script Generation

**Files:**
- Modify: `backend/prompts/script.py`
- Modify: `backend/pipeline/scriptwriter.py`
- Modify: `backend/pipeline/formats/base.py`
- Modify: `backend/pipeline/formats/youtube_listicle.py`
- Modify: `backend/pipeline/formats/life_as_a.py`
- Test: `backend/tests/pipeline/test_scriptwriter_visual_beats.py` renamed to `backend/tests/pipeline/test_scriptwriter_visual_intent.py`
- Test: `backend/tests/pipeline/test_formats_registry.py`

- [ ] **Step 1: Write failing prompt test**

Replace prompt vocabulary tests with:

```python
from prompts import script as script_prompt


def test_script_prompts_do_not_request_final_visual_modes_or_legacy_fields():
    prompt_text = "\n".join(
        prompt.template
        for prompt in [
            script_prompt.SCRIPT_SYSTEM,
            script_prompt.SCRIPT_SEGMENT_SCENES_INSTRUCTIONS,
        ]
    )

    forbidden = [
        "visual_beat",
        "media_source",
        "visual_treatment",
        "frame_directives",
        "aha_subtitle",
        "quick_cuts",
        "montage",
        '"static"',
        "ai_video",
    ]
    for token in forbidden:
        assert token not in prompt_text
```

- [ ] **Step 2: Run test to verify failure**

Run:

```bash
uv run --project backend pytest backend/tests/pipeline/test_scriptwriter_visual_intent.py::test_script_prompts_do_not_request_final_visual_modes_or_legacy_fields -q
```

Expected: fail because prompt still contains legacy terms.

- [ ] **Step 3: Update prompts**

In `backend/prompts/script.py`, replace the visual mode section with visual intent instructions:

```text
### Visual Intent
For each non-title scene, write a shot-labeled `visual_prompt` that describes the best full-bleed imageable moment for that scene.

Do not assign final visual modes. A post-voiceover visual planner will choose between video, full-frame image, multi-frame sequence, continuous progression, popup sequence, flip-flop, and renderer-owned captions after timing exists.

Do not include fields named visual_mode, visual_beat, media_source, visual_treatment, or frame_directives in script output.
```

Update JSON examples to remove final mode fields and frame directives.

- [ ] **Step 4: Remove scriptwriter visual beat repair**

In `backend/pipeline/scriptwriter.py`, remove:

- `ALL_BEAT_TYPES`
- `_canonical_visual_beat`
- `_directive_mode`
- `_synthesize_frame_directives`
- `_ensure_visual_beat_directives`
- `_fix_visual_monotony`
- generation calls to those functions

Keep script validation, title-card enforcement, format cleanup, and script rating flow intact.

- [ ] **Step 5: Replace format visual beat rules**

In `backend/pipeline/formats/base.py`, replace `VisualBeatRules` with:

```python
@dataclass(frozen=True)
class VisualModeRules:
    allowed_modes: frozenset[str]
    target_distribution: dict[str, tuple[float, float]] = field(default_factory=dict)
    require_no_adjacent_duplicates: bool = True
```

Update listicle and life-as-a format registrations to provide `visual_mode_rules`.

- [ ] **Step 6: Verify**

Run:

```bash
uv run --project backend pytest backend/tests/pipeline/test_scriptwriter_visual_intent.py backend/tests/pipeline/test_formats_registry.py -q
```

Expected: all pass with canonical mode rules and no legacy prompt terms.

---

### Task 5: Build Unified Visual Mode Planner

**Files:**
- Create: `backend/prompts/visual_mode_planner.py`
- Create: `backend/pipeline/visual_mode_planner.py`
- Test: `backend/tests/pipeline/test_visual_mode_planner.py`

- [ ] **Step 1: Write failing planner tests**

Create `backend/tests/pipeline/test_visual_mode_planner.py`:

```python
import json

import pytest

from models.script import Scene, ScriptContent, Segment, WordTimestamp
from pipeline.visual_mode_planner import (
    VisualModePlanError,
    apply_visual_mode_plan,
    plan_visual_modes,
    require_visual_planning_voiceover,
)


def _timed_scene(scene_id: str, narration: str, mode: str = "full_frame") -> Scene:
    words = narration.rstrip(".").split()
    timestamps = [
        WordTimestamp(word=word, start_ms=i * 300, end_ms=(i + 1) * 300)
        for i, word in enumerate(words)
    ]
    return Scene(
        id=scene_id,
        narration=narration,
        visual_prompt="[CLOSE-UP] A clean visual.",
        audio_duration_seconds=max(len(words) * 0.3, 1.0),
        word_timestamps=timestamps,
        visual_mode=mode,
    )


def _content() -> ScriptContent:
    return ScriptContent(
        title="Test",
        format_id="youtube-listicle",
        segments=[
            Segment(
                name="Segment",
                scenes=[
                    _timed_scene("scene_001", "A door opens."),
                    _timed_scene("scene_002", "Numbers stack up quickly."),
                    _timed_scene("scene_003", "The machine keeps growing."),
                ],
            )
        ],
    )


def test_voiceover_gate_requires_duration_and_word_timing():
    content = _content()
    content.segments[0].scenes[0].word_timestamps = None

    with pytest.raises(VisualModePlanError):
        require_visual_planning_voiceover(content)


def test_plan_visual_modes_repairs_adjacent_duplicate_modes(monkeypatch):
    content = _content()

    def fake_chat(**kwargs):
        return json.dumps({
            "assignments": [
                {"scene_id": "scene_001", "visual_mode": "full_frame", "reasoning": "simple image"},
                {"scene_id": "scene_002", "visual_mode": "full_frame", "reasoning": "duplicate from model"},
                {"scene_id": "scene_003", "visual_mode": "continuous", "reasoning": "progression"},
            ]
        })

    monkeypatch.setattr("pipeline.visual_mode_planner.chat", fake_chat)

    assignments = plan_visual_modes(content, script_id="script-test", eli_enabled=True)
    apply_visual_mode_plan(content, assignments)

    modes = [scene.visual_mode for scene in content.all_scenes()]
    assert modes[0] == "full_frame"
    assert modes[1] != "full_frame"
    assert all(left != right for left, right in zip(modes, modes[1:]))


def test_captions_assignment_clears_image_prompt_when_text_only(monkeypatch):
    content = _content()

    def fake_chat(**kwargs):
        return json.dumps({
            "assignments": [
                {
                    "scene_id": "scene_001",
                    "visual_mode": "captions",
                    "caption_text": "This changes everything",
                    "caption_emphasis": "everything",
                    "visual_prompt": "",
                    "reasoning": "punch line",
                },
                {"scene_id": "scene_002", "visual_mode": "multi_frame", "reasoning": "examples"},
                {"scene_id": "scene_003", "visual_mode": "continuous", "reasoning": "progression"},
            ]
        })

    monkeypatch.setattr("pipeline.visual_mode_planner.chat", fake_chat)

    assignments = plan_visual_modes(content, script_id="script-test", eli_enabled=False)
    apply_visual_mode_plan(content, assignments)

    scene = content.segments[0].scenes[0]
    assert scene.visual_mode == "captions"
    assert scene.caption_text == "This changes everything"
    assert scene.caption_emphasis == "everything"
    assert scene.frame_directives == []
```

- [ ] **Step 2: Run tests to verify failure**

Run:

```bash
uv run --project backend pytest backend/tests/pipeline/test_visual_mode_planner.py -q
```

Expected: fail because `pipeline.visual_mode_planner` does not exist.

- [ ] **Step 3: Add planner prompt**

Create `backend/prompts/visual_mode_planner.py` with a `PromptDef` that instructs:

```text
You are the visual planner for a faceless educational video. Choose exactly one canonical visual_mode per non-title scene.

Allowed modes: video, full_frame, multi_frame, continuous, popup_sequence, flipflop, captions.

Hard rules:
- no adjacent non-title scenes may share the same visual_mode
- title cards stay full_frame
- captions text is renderer-owned; never ask image generation to render readable words
- normal images, frames, and panels are full-bleed with no borders, cards, margins, labels, or text
- protagonist scenes depict Eli when Eli is enabled, otherwise the active style-preset character

Return only JSON:
{"assignments":[{"scene_id":"scene_001","visual_mode":"full_frame","reasoning":"..."}]}
```

- [ ] **Step 4: Implement planner module**

Create `backend/pipeline/visual_mode_planner.py` with:

```python
from __future__ import annotations

from dataclasses import dataclass
import json
import logging

from pydantic import BaseModel, Field

from integrations.llm_client import chat
from models.script import FrameDirective, ScriptContent, VISUAL_MODES, VisualLayer
from prompts.visual_mode_planner import VISUAL_MODE_PLANNER_SYSTEM

logger = logging.getLogger(__name__)


class VisualModePlanError(RuntimeError):
    pass


class VisualModeAssignment(BaseModel):
    scene_id: str
    visual_mode: str
    reasoning: str = ""
    frame_directives: list[FrameDirective] = Field(default_factory=list)
    visual_layers: list[VisualLayer] = Field(default_factory=list)
    caption_text: str = ""
    caption_emphasis: str = ""
    visual_prompt: str | None = None


def require_visual_planning_voiceover(content: ScriptContent) -> None:
    missing = [
        scene.id
        for scene in content.all_scenes()
        if not scene.is_title_card and (scene.audio_duration_seconds <= 0 or not scene.word_timestamps)
    ]
    if missing:
        raise VisualModePlanError(
            "Generate voiceover first so visual planning can use scene durations and word timing. "
            f"Missing timing for {len(missing)} scene(s): {', '.join(missing[:5])}"
        )


def _scene_summary(content: ScriptContent) -> list[dict]:
    rows: list[dict] = []
    for segment in content.segments:
        for scene in segment.scenes:
            rows.append({
                "scene_id": scene.id,
                "segment": segment.name,
                "narration": scene.narration,
                "visual_prompt": scene.visual_prompt,
                "is_title_card": scene.is_title_card,
                "duration": scene.audio_duration_seconds or scene.duration_estimate_seconds,
                "word_count": len(scene.word_timestamps or []),
                "contains_person": scene.contains_person,
                "caption_text": scene.caption_text,
                "caption_emphasis": scene.caption_emphasis,
            })
    return rows


def _fallback_mode(index: int, previous: str | None) -> str:
    candidates = ["full_frame", "multi_frame", "continuous", "captions", "popup_sequence", "flipflop", "video"]
    for offset in range(len(candidates)):
        candidate = candidates[(index + offset) % len(candidates)]
        if candidate != previous:
            return candidate
    return "full_frame"


def _repair_assignments(content: ScriptContent, assignments: list[VisualModeAssignment]) -> list[VisualModeAssignment]:
    by_id = {assignment.scene_id: assignment for assignment in assignments}
    repaired: list[VisualModeAssignment] = []
    previous_mode: str | None = None
    for index, scene in enumerate(content.all_scenes()):
        if scene.is_title_card:
            assignment = VisualModeAssignment(scene_id=scene.id, visual_mode="full_frame", reasoning="Title card")
        else:
            assignment = by_id.get(scene.id) or VisualModeAssignment(
                scene_id=scene.id,
                visual_mode=_fallback_mode(index, previous_mode),
                reasoning="Deterministic fallback",
            )
            if assignment.visual_mode not in VISUAL_MODES:
                assignment.visual_mode = _fallback_mode(index, previous_mode)
            if assignment.visual_mode == previous_mode:
                assignment.visual_mode = _fallback_mode(index, previous_mode)
        repaired.append(assignment)
        if not scene.is_title_card:
            previous_mode = assignment.visual_mode
    return repaired


def plan_visual_modes(content: ScriptContent, *, script_id: str, eli_enabled: bool) -> list[VisualModeAssignment]:
    require_visual_planning_voiceover(content)
    payload = {
        "title": content.title,
        "format_id": content.format_id,
        "eli_enabled": eli_enabled,
        "scenes": _scene_summary(content),
    }
    response = chat(
        system=VISUAL_MODE_PLANNER_SYSTEM.template,
        user_message=json.dumps(payload, indent=2),
        max_tokens=16384,
        script_id=script_id,
        json_mode=True,
        task="visual_planner",
    )
    data = json.loads(response)
    assignments = [VisualModeAssignment.model_validate(item) for item in data.get("assignments", [])]
    return _repair_assignments(content, assignments)


def apply_visual_mode_plan(content: ScriptContent, assignments: list[VisualModeAssignment]) -> None:
    scenes = {scene.id: scene for scene in content.all_scenes()}
    for assignment in assignments:
        scene = scenes.get(assignment.scene_id)
        if scene is None:
            continue
        scene.set_visual_mode(assignment.visual_mode)
        scene.visual_layers = list(assignment.visual_layers) if scene.visual_mode in {"popup_sequence", "flipflop"} else []
        scene.frame_directives = list(assignment.frame_directives)
        if scene.visual_mode == "captions":
            scene.caption_text = assignment.caption_text or scene.caption_text or scene.narration
            scene.caption_emphasis = assignment.caption_emphasis or scene.caption_emphasis
            if assignment.visual_prompt is not None:
                scene.visual_prompt = assignment.visual_prompt
            if not scene.visual_prompt.strip():
                scene.frame_directives = []
```

- [ ] **Step 5: Verify**

Run:

```bash
uv run --project backend pytest backend/tests/pipeline/test_visual_mode_planner.py -q
```

Expected: pass.

---

### Task 6: Add Unified Visual Planning API

**Files:**
- Create: `backend/api/visual_modes.py`
- Modify: `backend/api/__init__.py`
- Modify: `backend/api/media.py`
- Modify: `backend/api/visual_treatments.py`
- Test: `backend/tests/test_visual_mode_api.py`

- [ ] **Step 1: Write failing API tests**

Create `backend/tests/test_visual_mode_api.py`:

```python
import json

from fastapi.testclient import TestClient

from api import app
from models.script import Script, ScriptContent, Segment
from tests.pipeline.test_visual_mode_planner import _timed_scene


def test_visual_mode_analyze_blocks_without_voiceover(session):
    content = ScriptContent(
        title="Test",
        segments=[Segment(name="Segment", scenes=[_timed_scene("scene_001", "A door opens.")])],
    )
    content.segments[0].scenes[0].word_timestamps = None
    script = Script(id="script-visual-api", brand_id="brand", script_json=content.model_dump_json())
    session.add(script)
    session.commit()

    client = TestClient(app)
    response = client.post("/api/visual-modes/analyze/script-visual-api")

    assert response.status_code == 400
    assert "Generate voiceover first" in response.json()["detail"]
```

- [ ] **Step 2: Run test to verify failure**

Run:

```bash
uv run --project backend pytest backend/tests/test_visual_mode_api.py -q
```

Expected: fail with 404 because the endpoint does not exist.

- [ ] **Step 3: Implement endpoint**

Create `backend/api/visual_modes.py`:

```python
import json

from fastapi import APIRouter, Depends, HTTPException
from sqlmodel import Session

from database import get_session
from models.script import Script, ScriptContent
from pipeline.render_jobs import UserFacingJobError, create_job, run_job, update_job
from pipeline.visual_mode_planner import (
    VisualModePlanError,
    apply_visual_mode_plan,
    plan_visual_modes,
    require_visual_planning_voiceover,
)

router = APIRouter(prefix="/api/visual-modes", tags=["visual-modes"])


@router.post("/analyze/{script_id}")
def analyze_visual_modes(script_id: str, session: Session = Depends(get_session)):
    record = session.get(Script, script_id)
    if not record:
        raise HTTPException(status_code=404, detail="Script not found")
    content = ScriptContent.model_validate(json.loads(record.script_json))
    try:
        require_visual_planning_voiceover(content)
    except VisualModePlanError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    job = create_job()

    def _work() -> None:
        update_job(job.id, current_step="Planning visual modes...")
        assignments = plan_visual_modes(content, script_id=script_id, eli_enabled=True)
        apply_visual_mode_plan(content, assignments)
        record.script_json = content.model_dump_json()
        session.add(record)
        session.commit()
        update_job(job.id, output_data=json.dumps([assignment.model_dump() for assignment in assignments]))
        return None

    run_in_background(job.id, _work)
    return {"job_id": job.id}
```

Register in `backend/api/__init__.py`:

```python
from api.visual_modes import router as visual_modes_router
app.include_router(visual_modes_router)
```

Add the status endpoint:

```python
@router.get("/analyze/status/{job_id}")
def visual_mode_analyze_status(job_id: str):
    job = get_job(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    result = job.to_dict()
    if job.status == "completed" and job.output_data:
        result["assignments"] = json.loads(job.output_data)
    return result
```

- [ ] **Step 4: Delegate old endpoints**

Make `/api/media/analyze/{script_id}` and `/api/visual-treatments/{script_id}/analyze` call the same planner or return a clear deprecation response consumed by updated frontend callers.

- [ ] **Step 5: Verify**

Run:

```bash
uv run --project backend pytest backend/tests/test_visual_mode_api.py backend/tests/test_media_analysis_flags.py backend/tests/test_media_source_dispatch.py -q
```

Expected: visual API tests pass; old media/treatment tests are rewritten or removed where they assert legacy behavior.

---

### Task 7: Integrate Planner Into Frontend Timeline Flow

**Files:**
- Modify: `frontend/src/api.ts`
- Modify: `frontend/src/components/timeline/useMediaReview.ts`
- Modify: `frontend/src/components/timeline/MediaSourcesTab.tsx`
- Modify: `frontend/src/components/timeline/MediaReviewPanel.tsx`
- Modify: `frontend/src/components/timeline/VisualTreatmentReviewPanel.tsx`
- Modify: `frontend/src/types/script.ts`
- Test: focused frontend tests near timeline components

- [ ] **Step 1: Write failing frontend test**

Add or update a timeline test:

```ts
it("blocks visual planning until voiceover timing exists", async () => {
  const content = {
    title: "Test",
    segments: [{ name: "Segment", scenes: [{ id: "scene_001", narration: "Hi.", audio_duration_seconds: 0 }] }],
  } as unknown as ScriptContent;

  const reason = getVisualPlanningBlockedReason(content);

  expect(reason).toContain("Generate voiceover first");
});
```

- [ ] **Step 2: Run test to verify failure**

Run:

```bash
cd frontend && npm run test -- --run
```

Expected: fail because helper/API names do not exist yet.

- [ ] **Step 3: Add API client**

In `frontend/src/api.ts`, add:

```ts
export async function analyzeVisualModes(scriptId: string) {
  return api.post(`/api/visual-modes/analyze/${scriptId}`);
}

export async function getVisualModeAnalysisStatus(jobId: string) {
  return api.get(`/api/visual-modes/analyze/status/${jobId}`);
}
```

- [ ] **Step 4: Replace media/treatment review copy**

Rename UI concepts:

- “Media analysis” -> “Visual planning”
- “Media source” -> “Visual mode”
- “Animation type analysis” -> “Visual planning”

Keep one review surface that displays canonical mode, reasoning, and mode-specific fields.

- [ ] **Step 5: Verify**

Run:

```bash
cd frontend && npm run test -- --run
cd frontend && npm run build
```

Expected: tests and build pass.

---

### Task 8: Dispatch Visual Generation And Render By `visual_mode`

**Files:**
- Modify: `backend/pipeline/image_gen.py`
- Modify: `backend/api/visuals.py`
- Modify: `backend/pipeline/remotion_render.py`
- Modify: `remotion/src/types.ts`
- Modify: `frontend/src/types/script.ts`
- Test: `backend/tests/test_media_source_dispatch.py`
- Test: `backend/tests/pipeline/test_remotion_render.py`

- [ ] **Step 1: Write failing dispatch tests**

Add to `backend/tests/test_media_source_dispatch.py`:

```python
def test_image_generation_dispatches_video_from_visual_mode_not_media_source(monkeypatch, tmp_path):
    from pipeline import image_gen

    observed = {}

    def fake_generate_scene_video(**kwargs):
        observed["called"] = kwargs
        return "/static/projects/script/videos/scene.mp4", "prompt", {"source_type": "ai_video"}

    monkeypatch.setattr("pipeline.video_gen.generate_scene_video", fake_generate_scene_video)

    result = image_gen.generate_for_scene({
        "scene_id": "scene_001",
        "narration": "The machine starts moving.",
        "visual_prompt": "[CLOSE-UP] A machine starting.",
        "visual_mode": "video",
        "media_source": "ai",
        "audio_duration_seconds": 6.0,
    }, script_id="script", output_dir=tmp_path)

    assert result["video_url"] == "/static/projects/script/videos/scene.mp4"
    assert observed["called"]
```

- [ ] **Step 2: Run test to verify failure**

Run:

```bash
uv run --project backend pytest backend/tests/test_media_source_dispatch.py::test_image_generation_dispatches_video_from_visual_mode_not_media_source -q
```

Expected: fail because dispatch still contains legacy media-source branching.

- [ ] **Step 3: Update backend dispatch**

In `backend/pipeline/image_gen.py`, make `visual_mode = scene.get("visual_mode") or "full_frame"` the primary switch. Keep `media_source == "ai_video"` only in a normalization helper for old incoming payloads.

In `backend/api/visuals.py`, derive request mode from `body.visual_mode` first and stop using `body.media_source == "ai_video"` as a primary branch for new requests.

In `backend/pipeline/remotion_render.py`, render video scenes from `scene.visual_mode == "video"` first. Keep old fallback only in a clearly named compatibility helper.

- [ ] **Step 4: Update types**

In `remotion/src/types.ts` and `frontend/src/types/script.ts`, remove legacy visual beat union values and keep:

```ts
export type VisualMode = "video" | "full_frame" | "multi_frame" | "continuous" | "popup_sequence" | "flipflop" | "captions";
```

- [ ] **Step 5: Verify**

Run:

```bash
uv run --project backend pytest backend/tests/test_media_source_dispatch.py backend/tests/pipeline/test_remotion_render.py -q
cd frontend && npm run build
```

Expected: all pass.

---

### Task 9: Limit Generic FX To Full-Frame Scenes

**Files:**
- Modify: `backend/pipeline/fx_generator.py`
- Modify: `backend/api/fx.py`
- Test: `backend/tests/test_fx_transition_defaults.py`

- [ ] **Step 1: Write failing test**

Add:

```python
def test_fx_generation_skips_non_full_frame_visual_modes(monkeypatch):
    from models.script import Scene, ScriptContent, Segment
    from pipeline.fx_generator import assign_fx

    content = ScriptContent(
        title="Test",
        segments=[
            Segment(
                name="Segment",
                scenes=[
                    Scene(id="scene_001", narration="A still image.", visual_prompt="Image.", visual_mode="full_frame"),
                    Scene(id="scene_002", narration="Text lands.", visual_prompt="", visual_mode="captions"),
                    Scene(id="scene_003", narration="Clip moves.", visual_prompt="Clip.", visual_mode="video"),
                ],
            )
        ],
    )

    monkeypatch.setattr("pipeline.fx_generator.chat", lambda **_: '{"scenes":[{"scene_id":"scene_001","fx":{"drift":{"motion":"zoom_in","intensity":0.05,"anchor":"center"}}}]}')

    assign_fx(content, script_id="script-test")

    assert content.segments[0].scenes[0].fx is not None
    assert content.segments[0].scenes[1].fx is None
    assert content.segments[0].scenes[2].fx is None
```

- [ ] **Step 2: Run test to verify failure**

Run:

```bash
uv run --project backend pytest backend/tests/test_fx_transition_defaults.py::test_fx_generation_skips_non_full_frame_visual_modes -q
```

Expected: fail until FX input/output filters skip non-full-frame scenes.

- [ ] **Step 3: Update FX generator**

Filter FX assignment candidates:

```python
eligible_scenes = [scene for scene in content.all_scenes() if scene.visual_mode == "full_frame" and not scene.is_title_card]
```

When applying results, ignore any result whose target scene is not `full_frame`.

- [ ] **Step 4: Verify**

Run:

```bash
uv run --project backend pytest backend/tests/test_fx_transition_defaults.py -q
```

Expected: pass.

---

### Task 10: Update Test Lab For Canonical Visual Modes

**Files:**
- Modify: `backend/pipeline/test_lab.py`
- Modify: `backend/api/test_lab.py`
- Modify: `frontend/src/components/test-lab/TestLabControls.tsx`
- Modify: `frontend/src/components/test-lab/TestLabPage.tsx`
- Modify: `frontend/src/types/testLab.ts`
- Test: `backend/tests/test_test_lab.py`
- Test: `frontend/src/components/test-lab/*.test.tsx`

- [ ] **Step 1: Write failing Test Lab regression**

Add backend test:

```python
def test_test_lab_uses_visual_mode_without_media_source_alias():
    from pipeline.test_lab import build_content_from_preset

    content = build_content_from_preset("coffee-brain", {"visual_mode": "video"})
    scene = content.segments[0].scenes[0]

    assert scene.visual_mode == "video"
    assert scene.media_source == "ai_video"
```

This keeps the compatibility mirror but confirms Test Lab chooses via `visual_mode`.

- [ ] **Step 2: Run test to verify current behavior**

Run:

```bash
uv run --project backend pytest backend/tests/test_test_lab.py::test_test_lab_uses_visual_mode_without_media_source_alias -q
```

Expected: fail until the test is added or until the backend fixture imports are corrected. If the behavior already passes, keep this test as coverage and continue with the frontend control cleanup.

- [ ] **Step 3: Update Test Lab controls**

Ensure the UI has one visual mode segmented control with:

- Full frame
- Multi-frame
- Continuous
- Video
- Popup sequence
- Flip-flop
- Captions

Do not rewrite narration or visual prompt on mode switch.

- [ ] **Step 4: Verify**

Run:

```bash
uv run --project backend pytest backend/tests/test_test_lab.py -q
cd frontend && npm run test -- --run
```

Expected: pass.

---

### Task 11: Update Documentation And Project Instructions

**Files:**
- Modify: `AGENTS.md`
- Modify: `docs/formats/AUTHORING.md`
- Modify: related current docs under `docs/` that describe active format authoring behavior

- [ ] **Step 1: Update AGENTS.md**

Replace old visual mode and hook scoring guidance with:

```markdown
- **Script generation emits visual intent, not final visual modes**: Script prompts create short single-beat scenes, narration, shot-labeled visual prompts, and optional caption hints. Final visual mode assignment belongs to the post-voiceover visual planner.
- **Visual mode planning runs after voiceover**: Do not assign `video`, `multi_frame`, `continuous`, `popup_sequence`, `flipflop`, or `captions` until every non-title scene has `audio_duration_seconds > 0` and word timing.
- **Canonical visual modes only**: New code may use only `video`, `full_frame`, `multi_frame`, `continuous`, `popup_sequence`, `flipflop`, and `captions`. Do not reintroduce `aha_subtitle`, `static`, `quick_cuts`, `montage`, or `ai_video` as selection vocabulary.
- **No adjacent duplicate visual modes**: The visual planner must repair assignments so no two adjacent non-title scenes use the same `visual_mode`.
- **Shared protagonist rules**: If Eli is enabled, protagonist/main-subject scenes depict Eli as the dominant subject. If Eli is disabled, they depict the active preset-scoped character. This applies to listicle and life-as-a, including AI video scenes.
- **Generic FX is full-frame only**: Non-full-frame modes own their motion or layout; do not apply normal camera FX to video, multi-frame, continuous, popup, flip-flop, or captions scenes.
- **Hook scoring is removed**: Do not add generated-project hook scoring, hook-score badges, hook-score endpoints, or hook-score settings back into the app.
- **One scene remains one voiceover unit**: Do not concatenate multiple scenes into one ElevenLabs request. Future throughput work may parallelize per-scene requests, but visual planning depends on per-scene audio and word timing.
```

- [ ] **Step 2: Update format authoring docs**

Replace `VisualBeatRules` documentation with `VisualModeRules`, remove `supports_hook_scoring`, and document shared cleanup hooks.

- [ ] **Step 3: Verify docs do not keep active legacy guidance**

Run:

```bash
rg -n "VisualBeatRules|supports_hook_scoring|aha_subtitle|quick_cuts|montage|media_source|visual_treatment|ai_video" AGENTS.md docs/formats/AUTHORING.md
```

Expected: no active guidance for removed concepts except explicit “do not reintroduce” warnings.

---

### Task 12: Final Verification

**Files:**
- All touched files

- [ ] **Step 1: Run backend tests**

Run:

```bash
uv run --project backend pytest
```

Expected: pass.

- [ ] **Step 2: Run frontend tests**

Run:

```bash
npm run test:frontend
```

Expected: pass.

- [ ] **Step 3: Build frontend**

Run:

```bash
cd frontend && npm run build
```

Expected: build succeeds.

- [ ] **Step 4: Search legacy runtime vocabulary**

Run:

```bash
rg -n "aha_subtitle|quick_cuts|montage|VisualBeatRules|supports_hook_scoring|hook_score|scoreHook|media_source == \"ai_video\"|media_source === \"ai_video\"" backend frontend remotion AGENTS.md docs/formats/AUTHORING.md
```

Expected:

- no generated-project hook scoring references
- no legacy mode names in runtime prompts/planners/types
- any remaining `media_source == "ai_video"` checks are isolated compatibility normalization and named as such

- [ ] **Step 5: Manual smoke path**

Run:

```bash
npm run dev
```

Manual checks:

- generate a listicle script
- generate a life-as-a script
- generate voiceover for each
- run visual planning
- confirm no adjacent non-title scenes share a mode
- generate visuals for at least one `full_frame`, `multi_frame`, `continuous`, `captions`, and layered mode
- confirm FX appears only on `full_frame`

Expected: both formats use the same visual planning flow and no removed hook score UI appears.
