# Visual Opportunity Planning Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add script-type-agnostic visual opportunity planning before segmented scene generation so visual modes are considered early enough to shape scene boundaries and duration.

**Architecture:** Extend `backend/pipeline/visual_mode_policy.py`, which already owns visual-mode duration policy, with canonical opportunity guidance and small formatting helpers. Thread that guidance into the segmented outline and per-segment scene prompts in `backend/pipeline/scriptwriter.py`, while keeping format-specific prompts focused on voice and structure. Add tests that lock prompt behavior, policy coverage, and post-generation non-rebalancing constraints.

**Tech Stack:** Python 3.12, Pydantic/SQLModel models, existing prompt registry, backend pytest via `uv run --project backend pytest`.

---

## File Structure

- Modify: `backend/pipeline/visual_mode_policy.py`
  - Owns canonical visual-mode opportunity policy and prompt guidance helpers.
- Modify: `backend/pipeline/scriptwriter.py`
  - Threads opportunity guidance into segmented outline generation and per-segment scene generation.
  - Logs planned/final mode summary diagnostics.
- Modify: `backend/prompts/script.py`
  - Updates outline prompt schemas to request `visual_opportunities`.
  - Updates per-segment prompts to consume the segment opportunity plan without hard quotas.
- Modify: `backend/tests/pipeline/test_visual_mode_policy.py`
  - Tests canonical opportunity policy coverage and prompt guidance.
- Modify: `backend/tests/pipeline/test_scriptwriter_visual_beats.py`
  - Tests global and format prompts include the planning contract.
- Modify: `backend/tests/pipeline/test_scriptwriter_segmented.py` or create if missing.
  - Tests segmented generation passes segment-level opportunities into the per-segment prompt without mutating final scenes.
- Modify: `AGENTS.md` only if implementation reveals a new convention not already captured by the design commit.

---

### Task 1: Add Canonical Visual Opportunity Policy

**Files:**
- Modify: `backend/pipeline/visual_mode_policy.py`
- Test: `backend/tests/pipeline/test_visual_mode_policy.py`

- [ ] **Step 1: Write failing policy tests**

Add these tests to `backend/tests/pipeline/test_visual_mode_policy.py`:

```python
from pipeline.visual_mode_policy import (
    CANONICAL_VISUAL_MODES,
    opportunity_policy_for_mode,
    prompt_visual_opportunity_guidance,
    prompt_visual_opportunity_schema_guidance,
)


def test_opportunity_policy_covers_all_canonical_visual_modes():
    for mode in CANONICAL_VISUAL_MODES:
        policy = opportunity_policy_for_mode(mode)
        assert policy.visual_mode == mode
        assert policy.purpose
        assert policy.opportunity_cues
        assert policy.avoid_when
        assert policy.frequency_guidance


def test_visual_opportunity_guidance_is_script_type_agnostic_and_pre_scene():
    text = prompt_visual_opportunity_guidance(projected_scene_count=90)

    assert "script-type agnostic" in text
    assert "before final scenes are written" in text
    assert "Scene boundaries, narration length, duration estimates, and mode-specific fields" in text
    assert "full_frame remains dominant" in text
    assert "flipflop and captions" in text
    assert "common expressive rhythm opportunities" in text
    assert "popup_sequence, comparison_board, and stat_card" in text
    assert "actively scan" in text
    assert "Do not force a quota" in text


def test_visual_opportunity_schema_guidance_requests_segment_opportunities():
    text = prompt_visual_opportunity_schema_guidance()

    assert '"visual_opportunities"' in text
    assert '"mode"' in text
    assert '"beat"' in text
    assert '"duration_profile"' in text
    assert '"priority"' in text
    assert "Do not include scenes" in text
```

- [ ] **Step 2: Run tests to verify they fail**

Run:

```bash
uv run --project backend pytest backend/tests/pipeline/test_visual_mode_policy.py -q
```

Expected: FAIL because `opportunity_policy_for_mode`, `prompt_visual_opportunity_guidance`, and `prompt_visual_opportunity_schema_guidance` do not exist.

- [ ] **Step 3: Implement minimal policy helpers**

In `backend/pipeline/visual_mode_policy.py`, add:

```python
@dataclass(frozen=True)
class VisualModeOpportunityPolicy:
    visual_mode: str
    purpose: str
    frequency_guidance: str
    opportunity_cues: tuple[str, ...]
    avoid_when: tuple[str, ...]


_OPPORTUNITY_POLICIES: dict[str, VisualModeOpportunityPolicy] = {
    "full_frame": VisualModeOpportunityPolicy(
        visual_mode="full_frame",
        purpose="Default full-bleed image for one clear lived moment, object, atmosphere, character beat, or metaphor.",
        frequency_guidance="Dominant fallback; most scenes may remain full_frame when no specialized mode clearly improves the beat.",
        opportunity_cues=("single location or object", "quiet character moment", "atmosphere", "simple metaphor"),
        avoid_when=("multiple distinct examples are needed", "same-scene progression is central", "renderer-owned text or board structure is the point"),
    ),
    "multi_frame": VisualModeOpportunityPolicy(
        visual_mode="multi_frame",
        purpose="Several independent generated frames inside one narration scene.",
        frequency_guidance="Common variety mode when narration naturally contains multiple examples, routines, or sensory cuts.",
        opportunity_cues=("multiple examples", "repeated routines", "fast context shifts", "several memories"),
        avoid_when=("one coherent progression should stay continuous", "one strong image is clearer", "cutouts or renderer-owned typography are required"),
    ),
    "continuous": VisualModeOpportunityPolicy(
        visual_mode="continuous",
        purpose="Same-scene progression where one subject, action, or environment changes over time.",
        frequency_guidance="Common variety mode for physical progression, time passage, and transformations.",
        opportunity_cues=("time passes in one place", "object changes state", "person repeats an action", "environment gradually shifts"),
        avoid_when=("frames are unrelated examples", "the scene is only a static realization", "side-by-side comparison is clearer"),
    ),
    "flipflop": VisualModeOpportunityPolicy(
        visual_mode="flipflop",
        purpose="Same-subject A/B micro-animation using compatible full-bleed states.",
        frequency_guidance="Common expressive rhythm opportunity in long scripts; consider several uses when repeated gestures or simple A/B motion exist.",
        opportunity_cues=("hands opening and closing", "typing or sorting", "door open and closed", "nodding or pacing", "same subject toggles between two compatible states"),
        avoid_when=("contrast is only conceptual", "subjects are unrelated", "a true side-by-side comparison is needed"),
    ),
    "captions": VisualModeOpportunityPolicy(
        visual_mode="captions",
        purpose="Renderer-owned editorial text beat for a realization, reversal, label, or key claim.",
        frequency_guidance="Common expressive rhythm opportunity in long scripts; plan several when exact narration phrases deserve large in-scene text.",
        opportunity_cues=("quotable realization", "short emotional label", "turning-point sentence", "clear reversal", "key claim"),
        avoid_when=("caption text would need paraphrasing", "ordinary subtitles are enough", "the scene is too short for context"),
    ),
    "popup_sequence": VisualModeOpportunityPolicy(
        visual_mode="popup_sequence",
        purpose="Anchor subject with concrete item/tool/document/object cutouts appearing around it.",
        frequency_guidance="Low-count and meaning-driven; actively scan for concrete item clusters before accepting zero.",
        opportunity_cues=("small set of tools", "documents", "possessions", "symptoms", "ingredients", "objects around a person"),
        avoid_when=("items are abstract", "the list is too long", "a multi-frame montage communicates better"),
    ),
    "comparison_board": VisualModeOpportunityPolicy(
        visual_mode="comparison_board",
        purpose="Renderer-owned two- or three-way comparison with cutout subjects and board layout.",
        frequency_guidance="Low-count and meaning-driven; actively scan for true comparisons before accepting zero.",
        opportunity_cues=("before vs after", "then vs now", "choice vs consequence", "two roles", "two outcomes"),
        avoid_when=("only one environment or event matters", "same-subject micro-animation is enough", "process progression is clearer"),
    ),
    "stat_card": VisualModeOpportunityPolicy(
        visual_mode="stat_card",
        purpose="One decisive number rendered as dominant typography.",
        frequency_guidance="Low-count and capped; actively scan for decisive numbers before accepting zero, but use only 1-2 in most videos.",
        opportunity_cues=("money amount", "percentage", "duration", "ranking", "odds", "population count"),
        avoid_when=("multiple numbers compete", "setting or character emotion matters more", "the number is incidental"),
    ),
    "video": VisualModeOpportunityPolicy(
        visual_mode="video",
        purpose="Planned AI-video scene when motion clearly improves the beat before timing validation.",
        frequency_guidance="Timing-sensitive planned mode; do not let it crowd out stronger renderer-owned opportunities.",
        opportunity_cues=("meaningful motion", "gesture", "physical transformation", "environmental movement", "reveal"),
        avoid_when=("static text or board is required", "title card", "captions scene", "motion does not add clarity"),
    ),
}


_missing_opportunity_policies = VISUAL_MODES - set(_OPPORTUNITY_POLICIES)
_unknown_opportunity_policies = set(_OPPORTUNITY_POLICIES) - VISUAL_MODES
if _missing_opportunity_policies or _unknown_opportunity_policies:
    raise RuntimeError(
        "Visual mode opportunity policies must exactly match models.script.VISUAL_MODES: "
        f"missing={sorted(_missing_opportunity_policies)}, unknown={sorted(_unknown_opportunity_policies)}"
    )


def opportunity_policy_for_mode(visual_mode: str | None) -> VisualModeOpportunityPolicy:
    return _OPPORTUNITY_POLICIES.get(visual_mode or "", _OPPORTUNITY_POLICIES["full_frame"])


def prompt_visual_opportunity_guidance(projected_scene_count: int | None = None) -> str:
    scene_hint = (
        f"For a projected script of about {projected_scene_count} scenes, "
        if projected_scene_count and projected_scene_count > 0
        else "For the projected script, "
    )
    lines = [
        "Visual opportunity planning is script-type agnostic and happens before final scenes are written.",
        "Scene boundaries, narration length, duration estimates, and mode-specific fields must be shaped together.",
        f"{scene_hint}full_frame remains dominant; do not force a quota or distort narration for visual variety.",
        "Treat flipflop and captions as common expressive rhythm opportunities in long scripts when the narration supports them.",
        "Keep popup_sequence, comparison_board, and stat_card low-count and meaning-driven, but actively scan for them before accepting zero.",
        "Post-generation checks may validate or downgrade invalid modes, but must not redistribute modes into already-cut short scenes.",
    ]
    for mode in CANONICAL_VISUAL_MODES:
        policy = opportunity_policy_for_mode(mode)
        cues = ", ".join(policy.opportunity_cues[:4])
        avoids = ", ".join(policy.avoid_when[:2])
        lines.append(f"{mode}: {policy.frequency_guidance} Cues: {cues}. Avoid when: {avoids}.")
    return "\n".join(f"- {line}" for line in lines)


def prompt_visual_opportunity_schema_guidance() -> str:
    return """\
Add a compact "visual_opportunities" array to every outline segment. Do not include scenes or narration body.
Each opportunity object must use this shape:
{
  "mode": "captions|flipflop|multi_frame|continuous|popup_sequence|comparison_board|stat_card|video|full_frame",
  "beat": "Short natural-language description of the future scene beat.",
  "why": "Why this mode strengthens the beat without hurting script quality.",
  "duration_profile": "normal|medium|extended|planned",
  "priority": "strong|possible"
}
Use opportunities as planning notes only. They guide future scene boundaries; they are not final scene JSON.
"""
```

- [ ] **Step 4: Run policy tests to verify they pass**

Run:

```bash
uv run --project backend pytest backend/tests/pipeline/test_visual_mode_policy.py -q
```

Expected: PASS.

---

### Task 2: Update Prompt Contracts For Outline-Time Opportunities

**Files:**
- Modify: `backend/prompts/script.py`
- Test: `backend/tests/pipeline/test_scriptwriter_visual_beats.py`

- [ ] **Step 1: Write failing prompt tests**

Add tests to `backend/tests/pipeline/test_scriptwriter_visual_beats.py`:

```python
def test_outline_prompts_request_visual_opportunities_before_scenes():
    for prompt in (
        script_prompt.SCRIPT_OUTLINE_INSTRUCTIONS.template,
        script_prompt.LIFE_AS_A_OUTLINE_INSTRUCTIONS.template,
    ):
        assert '"visual_opportunities"' in prompt
        assert "before any scenes are written" in prompt
        assert "Do not include any scenes" in prompt or "NO scenes" in prompt
        assert "not final scene JSON" in prompt


def test_segment_prompts_consume_visual_opportunities_without_quotas():
    for prompt in (
        script_prompt.SCRIPT_SEGMENT_SCENES_INSTRUCTIONS.template,
        script_prompt.LIFE_AS_A_LEVEL_SCENES_INSTRUCTIONS.template,
    ):
        assert "visual_opportunities" in prompt
        assert "shape scene boundaries" in prompt
        assert "Do not force" in prompt
        assert "format voice" in prompt
        assert "duration" in prompt
```

- [ ] **Step 2: Run tests to verify they fail**

Run:

```bash
uv run --project backend pytest backend/tests/pipeline/test_scriptwriter_visual_beats.py::test_outline_prompts_request_visual_opportunities_before_scenes backend/tests/pipeline/test_scriptwriter_visual_beats.py::test_segment_prompts_consume_visual_opportunities_without_quotas -q
```

Expected: FAIL because prompt text does not yet request or consume `visual_opportunities`.

- [ ] **Step 3: Update listicle outline prompt**

In `SCRIPT_OUTLINE_INSTRUCTIONS.template`, add `visual_opportunities` to the segment schema:

```json
"visual_opportunities": [
  {
    "mode": "captions",
    "beat": "A short realization or reversal that should land as renderer-owned text.",
    "why": "This strengthens the scene without adding a new argument beat.",
    "duration_profile": "extended",
    "priority": "strong"
  }
]
```

Add this rule below the schema:

```text
For each segment, include a compact "visual_opportunities" array before any scenes are written. These are planning notes, not final scene JSON. Identify natural opportunities for all canonical visual modes early enough that scene boundaries and duration can be shaped later. Do not force opportunities or invent extra segment beats; preserve script quality first.
```

- [ ] **Step 4: Update life-as-a outline prompt**

In `LIFE_AS_A_OUTLINE_INSTRUCTIONS.template`, add `visual_opportunities` to each object in both `levels` and parallel `segments` examples. The `segments[i].visual_opportunities` should mirror the level opportunities because the existing segmented machinery reads `segments`.

Use this wording:

```text
For every level and its parallel segment object, include "visual_opportunities". These are not scenes. They are early planning notes for likely visual modes so the later per-level scene phase can write narration at the right length for the selected mode. Do not turn the level into a listicle or add beats only to satisfy variety.
```

- [ ] **Step 5: Update per-segment prompts**

In `SCRIPT_SEGMENT_SCENES_INSTRUCTIONS.template`, add a rule:

```text
- The outline may include "visual_opportunities" for this segment. Use them as pre-scene planning notes to shape scene boundaries, narration length, duration estimates, and mode-specific fields from the start. Strong opportunities should normally become scenes when they still fit the narration. Ignore weak opportunities when they would hurt script quality, format voice, or standalone-short clarity. Do not force a quota.
```

In `LIFE_AS_A_LEVEL_SCENES_INSTRUCTIONS.template`, add the analogous rule:

```text
- The outline may include "visual_opportunities" for this level. Use them as pre-scene planning notes to shape scene boundaries, narration length, duration estimates, and mode-specific fields from the start. Strong opportunities should normally become scenes when they still fit the lived progression. Ignore weak opportunities when they would hurt script quality, format voice, protagonist continuity, or the level's emotional arc. Do not force a quota.
```

- [ ] **Step 6: Run prompt tests**

Run:

```bash
uv run --project backend pytest backend/tests/pipeline/test_scriptwriter_visual_beats.py::test_outline_prompts_request_visual_opportunities_before_scenes backend/tests/pipeline/test_scriptwriter_visual_beats.py::test_segment_prompts_consume_visual_opportunities_without_quotas -q
```

Expected: PASS.

---

### Task 3: Thread Canonical Opportunity Guidance Through Segmented Generation

**Files:**
- Modify: `backend/pipeline/scriptwriter.py`
- Test: create or modify `backend/tests/pipeline/test_scriptwriter_segmented.py`

- [ ] **Step 1: Write failing unit tests for message construction helpers**

If `backend/tests/pipeline/test_scriptwriter_segmented.py` does not exist, create it. Add:

```python
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from pipeline.scriptwriter import (
    _build_segment_scene_user_message,
    _visual_opportunity_summary,
)


def test_segment_scene_message_includes_segment_visual_opportunities():
    outline = {
        "segments": [
            {
                "name": "Segment One",
                "topic_summary": "A segment about drift.",
                "visual_opportunities": [
                    {
                        "mode": "captions",
                        "beat": "This is the road.",
                        "why": "A realization lands as text.",
                        "duration_profile": "extended",
                        "priority": "strong",
                    }
                ],
            }
        ]
    }

    message = _build_segment_scene_user_message(
        outline=outline,
        segment_index=0,
        trailing_context="",
        segment_scenes_instructions="SEGMENT INSTRUCTIONS",
        level_label="segment",
    )

    assert "VISUAL OPPORTUNITIES FOR THIS SEGMENT" in message
    assert "This is the road." in message
    assert "captions" in message
    assert "SEGMENT INSTRUCTIONS" in message


def test_visual_opportunity_summary_counts_planned_modes():
    outline = {
        "segments": [
            {"visual_opportunities": [{"mode": "captions"}, {"mode": "flipflop"}]},
            {"visual_opportunities": [{"mode": "captions"}, {"mode": "stat_card"}]},
        ]
    }

    assert _visual_opportunity_summary(outline) == {
        "captions": 2,
        "flipflop": 1,
        "stat_card": 1,
    }
```

- [ ] **Step 2: Run tests to verify they fail**

Run:

```bash
uv run --project backend pytest backend/tests/pipeline/test_scriptwriter_segmented.py -q
```

Expected: FAIL because `_build_segment_scene_user_message` and `_visual_opportunity_summary` do not exist.

- [ ] **Step 3: Implement message helper and summary helper**

In `backend/pipeline/scriptwriter.py`, import:

```python
from pipeline.visual_mode_policy import (
    prompt_visual_opportunity_guidance,
    prompt_visual_opportunity_schema_guidance,
)
```

Add helpers near segmented-generation functions:

```python
def _visual_opportunity_summary(outline: dict) -> dict[str, int]:
    counts: dict[str, int] = {}
    for segment in outline.get("segments", []):
        for opportunity in segment.get("visual_opportunities") or []:
            mode = str(opportunity.get("mode", "")).strip()
            if not mode:
                continue
            counts[mode] = counts.get(mode, 0) + 1
    return counts


def _segment_visual_opportunities_block(segment: dict, section_upper: str) -> str:
    opportunities = segment.get("visual_opportunities") or []
    if not opportunities:
        return (
            f"VISUAL OPPORTUNITIES FOR THIS {section_upper}: none provided. "
            "Still actively scan for earned flipflop, captions, popup_sequence, "
            "comparison_board, and stat_card opportunities before defaulting to zero.\n\n"
        )
    return (
        f"VISUAL OPPORTUNITIES FOR THIS {section_upper} (planning notes, not mandatory final scenes):\n"
        f"```json\n{json.dumps(opportunities, indent=2)}\n```\n\n"
    )


def _build_segment_scene_user_message(
    outline: dict,
    segment_index: int,
    trailing_context: str,
    segment_scenes_instructions: str,
    level_label: str = "segment",
) -> str:
    segment = outline["segments"][segment_index]
    section_label = level_label.strip() or "segment"
    section_title = section_label.title()
    section_upper = section_label.upper()
    seg_name = segment.get("name", f"{section_title} {segment_index + 1}")
    total = len(outline["segments"])
    outline_json = json.dumps(outline, indent=2)
    metadata_lines = [
        f"WRITE SCENES FOR {section_upper} {segment_index + 1}/{total}: \"{seg_name}\"",
        f"Topic summary: {segment.get('topic_summary', '')}",
    ]
    if segment.get("circle_color"):
        metadata_lines.append(f"Circle color: {segment.get('circle_color')}")
    if segment.get("title_card_image_prompt"):
        metadata_lines.append(f"Title card image prompt: {segment.get('title_card_image_prompt')}")

    return (
        f"FULL SCRIPT OUTLINE (for context — do NOT write scenes for other {section_label}s):\n"
        f"```json\n{outline_json}\n```\n\n"
        f"{chr(10).join(metadata_lines)}\n\n"
        f"{_segment_visual_opportunities_block(segment, section_upper)}"
        f"{trailing_context}"
        f"{segment_scenes_instructions}"
    )
```

- [ ] **Step 4: Use helper in `_generate_segment_scenes`**

Replace the existing inline user message construction in `_generate_segment_scenes` with:

```python
    user_msg = _build_segment_scene_user_message(
        outline=outline,
        segment_index=segment_index,
        trailing_context=trailing_context,
        segment_scenes_instructions=segment_scenes_instructions,
        level_label=level_label,
    )
```

- [ ] **Step 5: Add outline-phase guidance**

In `_generate_outline`, before building `outline_msg`, append canonical guidance:

```python
    outline_msg = (
        user_message
        + "\n\n## CANONICAL VISUAL OPPORTUNITY PLANNING\n"
        + prompt_visual_opportunity_guidance()
        + "\n\n## VISUAL OPPORTUNITY OUTLINE SCHEMA\n"
        + prompt_visual_opportunity_schema_guidance()
        + "\n\n"
        + outline_instructions
    )
```

- [ ] **Step 6: Log planned/final summaries**

After outline generation in `_generate_segmented`, log:

```python
    planned_opportunities = _visual_opportunity_summary(outline)
    if planned_opportunities:
        logger.info("SEGMENTED: Planned visual opportunities by mode: %s", planned_opportunities)
```

Before returning content in `_generate_segmented`, log final counts:

```python
    final_mode_counts: dict[str, int] = {}
    for scene in content.all_scenes():
        if scene.is_title_card:
            continue
        mode = scene.visual_mode or "full_frame"
        final_mode_counts[mode] = final_mode_counts.get(mode, 0) + 1
    logger.info("SEGMENTED: Final visual modes by mode: %s", final_mode_counts)
```

- [ ] **Step 7: Run segmented helper tests**

Run:

```bash
uv run --project backend pytest backend/tests/pipeline/test_scriptwriter_segmented.py -q
```

Expected: PASS.

---

### Task 4: Lock Post-Generation Non-Rebalancing Behavior

**Files:**
- Modify: `backend/tests/pipeline/test_scriptwriter_visual_beats.py`
- Optionally modify: `backend/pipeline/scriptwriter.py` only if tests reveal existing code violates the contract.

- [ ] **Step 1: Add regression test for no post-generation redistribution**

Add to `backend/tests/pipeline/test_scriptwriter_visual_beats.py`:

```python
def test_visual_monotony_fix_does_not_force_extended_modes_into_short_scenes():
    content = ScriptContent(
        title="Test",
        format_id="youtube-listicle",
        segments=[
            Segment(
                name="Segment",
                scenes=[_static_scene(f"scene_{i:03d}") for i in range(1, 8)],
            )
        ],
    )

    _fix_visual_monotony(content, VisualBeatRules(
        allowed_beats=frozenset({"static", "continuous", "multi_frame"}),
        monotony_threshold=3,
    ))

    modes = [scene.visual_mode for scene in content.all_scenes()]
    assert "captions" not in modes
    assert "comparison_board" not in modes
    assert "popup_sequence" not in modes
    assert "stat_card" not in modes
```

- [ ] **Step 2: Run regression test**

Run:

```bash
uv run --project backend pytest backend/tests/pipeline/test_scriptwriter_visual_beats.py::test_visual_monotony_fix_does_not_force_extended_modes_into_short_scenes -q
```

Expected: PASS if current monotony fixer is already safe.

---

### Task 5: Run Focused Backend Verification

**Files:**
- No edits unless failures reveal a real issue.

- [ ] **Step 1: Run focused tests**

Run:

```bash
uv run --project backend pytest \
  backend/tests/pipeline/test_visual_mode_policy.py \
  backend/tests/pipeline/test_scriptwriter_visual_beats.py \
  backend/tests/pipeline/test_scriptwriter_segmented.py \
  -q
```

Expected: PASS.

- [ ] **Step 2: Run full backend suite**

Run:

```bash
npm run test:backend
```

Expected: PASS.

- [ ] **Step 3: Check diff hygiene**

Run:

```bash
git diff --check
git status --short
```

Expected: no whitespace errors. Status should show only intentional files modified or created, plus pre-existing untracked `data/` and old plan docs if still present.

---

### Task 6: Commit, Push, And Auto-Review Loop

**Files:**
- Stage only intentional files:
  - `backend/pipeline/visual_mode_policy.py`
  - `backend/pipeline/scriptwriter.py`
  - `backend/prompts/script.py`
  - backend test files changed/created
  - `docs/superpowers/plans/2026-06-03-visual-opportunity-planning.md`
  - `AGENTS.md` only if changed during implementation

- [ ] **Step 1: Stage and commit**

Run:

```bash
git add backend/pipeline/visual_mode_policy.py backend/pipeline/scriptwriter.py backend/prompts/script.py backend/tests/pipeline/test_visual_mode_policy.py backend/tests/pipeline/test_scriptwriter_visual_beats.py backend/tests/pipeline/test_scriptwriter_segmented.py docs/superpowers/plans/2026-06-03-visual-opportunity-planning.md
git commit -m "Add visual opportunity planning"
```

Expected: commit succeeds.

- [ ] **Step 2: Push to main**

Run:

```bash
git push origin main
```

Expected: push succeeds.

- [ ] **Step 3: Dispatch required code review**

Use Codex agent delegation tooling with this exact prompt from `AGENTS.md`:

```text
Review the most recent commit on the main branch of this project.
Run `git diff HEAD~1..HEAD` to see the changes and `git show --stat HEAD` for context.
Read the full affected files (not just the diff) to understand surrounding code.
Check for: correctness bugs, error handling gaps, security issues, naive/aware datetime mismatches, unhandled promise rejections, race conditions, and style problems.
Return a structured verdict: either LGTM or NEEDS CHANGES.
If NEEDS CHANGES, provide a numbered list of findings with severity (FAIL/WARN), file:line, and a specific description of what's wrong and how to fix it.
```

Expected: Review returns `LGTM` or actionable findings.

- [ ] **Step 4: Apply review findings if needed**

If review returns `NEEDS CHANGES`, immediately:

```bash
# edit files with apply_patch
uv run --project backend pytest \
  backend/tests/pipeline/test_visual_mode_policy.py \
  backend/tests/pipeline/test_scriptwriter_visual_beats.py \
  backend/tests/pipeline/test_scriptwriter_segmented.py \
  -q
npm run test:backend
git add <changed files>
git commit -m "fix: address review findings"
git push origin main
```

Then dispatch the same review prompt again. Repeat until `LGTM`.

---

## Self-Review Notes

- Spec coverage: The plan implements canonical policy, outline-time opportunities, per-segment consumption, non-rebalancing validation, dev logs, tests, and documentation/commit workflow.
- Completeness scan: No banned incomplete-step patterns or vague “add tests” steps remain.
- Type consistency: New helpers are all Python functions in `pipeline.visual_mode_policy` or `pipeline.scriptwriter`, and tests import those exact names.
