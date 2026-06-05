# Visual Opportunity Coverage Design

## Problem

Visual opportunity planning now happens before scene writing, but generated long-form scripts can still underuse renderer-owned visual modes. The current prompt says to avoid quotas and says not every mode or segment needs an opportunity. That protects script quality, but it also gives the model permission to silently accept zero or near-zero opportunities for `captions`, `popup_sequence`, `comparison_board`, and `stat_card` even in scripts with many content scenes.

The issue is not final mode validation. The issue is outline-time discovery being too conservative.

## Goal

Make outline-time visual opportunity planning more permissive for extended and medium target modes while keeping final scene assignment contextual and script-quality-first.

## Non-Goals

- Do not add hard final visual-mode quotas.
- Do not rebalance visual modes after scenes are already written.
- Do not force every script to include every specialized mode.
- Do not weaken mode-specific validity rules for captions, popup sequences, comparison boards, or stat cards.
- Do not introduce script-type-specific visual-mode rules.

## Design

Add script-type-agnostic soft opportunity discovery expectations to the shared visual-mode policy.

For long scripts, the outline phase should usually find multiple plausible candidate opportunities for renderer-owned modes:

- `captions`: usually at least two strong or possible exact-phrase editorial beats.
- `popup_sequence`: usually at least two concrete item/object cluster candidates.
- `comparison_board`: usually at least two true contrast candidates.
- `stat_card`: usually one or two decisive-number candidates.
- `flipflop`: several character/body-language rhythm candidates.

These are candidate discovery expectations, not final scene quotas. If the topic truly lacks a mode shape, the outline may include fewer candidates, but it must make that absence explicit in a compact `visual_opportunity_coverage` note. This prevents silent zeros while preserving nuance.

## Prompt Flow

The outline prompt receives the shared policy guidance and asks for two fields:

- `visual_opportunities`: per-segment candidate opportunities.
- `visual_opportunity_coverage`: a global note summarizing whether the outline found enough candidates for each specialized mode and why any mode is under the soft expectation.

The per-segment scene prompt continues to consume only the segment's opportunity notes. It should honor strong opportunities when they still fit the narration and may ignore weak opportunities when they would hurt script quality, format voice, protagonist continuity, or standalone-short clarity.

## Documentation

Update `AGENTS.md` and the in-app workflow/visual-mode docs to explain the invisible behavior: long scripts use soft candidate discovery expectations before scene cutting, but final mode usage remains contextual rather than quota-driven.

## Testing

Add backend prompt/policy tests for:

- long-script guidance includes soft candidate expectations for extended and medium modes,
- the outline schema requests `visual_opportunity_coverage`,
- standard and life-as-a outline prompts include the coverage field,
- segment prompts still frame opportunities as contextual and not hard quotas.

Add frontend tests for the in-app docs text if the visible docs are updated.
