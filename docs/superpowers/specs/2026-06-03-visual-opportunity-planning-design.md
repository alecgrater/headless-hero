# Visual Opportunity Planning Design

## Problem

Visual mode selection currently happens inside scene-writing prompts and post-processing validation. This lets `full_frame`, `multi_frame`, and `continuous` dominate naturally, but it can underuse expressive modes such as `flipflop` and `captions`, and it can miss low-count opportunities for `popup_sequence`, `comparison_board`, and `stat_card`.

The tempting fix is a post-generation rebalancer, but that would be wrong for modes with longer duration targets. Once a scene is already cut as a short `full_frame` beat, converting it into a `captions`, `comparison_board`, `popup_sequence`, or `stat_card` scene can create narration-length mismatches or missing mode-specific fields.

## Goal

Add a script-type-agnostic visual opportunity planning layer that runs before final scenes are written. It should identify natural opportunities for all canonical visual modes early enough that scene boundaries, narration length, duration estimates, and mode-specific fields are shaped together.

## Non-Goals

- Do not add a hard quota system.
- Do not automatically redistribute visual modes after final scenes are generated.
- Do not add a post-audio narration rewrite pass.
- Do not make format-specific definitions for canonical visual modes.
- Do not degrade script voice, pacing, callbacks, hooks, or topic structure to satisfy visual variety.

## Current Pipeline Context

Both registered script formats support segmented generation:

- `youtube-listicle` uses an outline prompt plus per-segment scene prompts.
- `life-as-a` uses an outline prompt plus per-level scene prompts.

Both formats expose the full canonical visual-mode vocabulary. Visual-mode duration policy is already universal: normal modes target shorter beats, while renderer-owned modes can intentionally carry longer narration.

## Proposed Flow

### 1. Canonical Policy

Create a shared visual opportunity policy in the pipeline. The policy owns script-type-agnostic guidance for:

- each visual mode's purpose,
- soft usage expectations by projected scene count,
- opportunity cues,
- avoidance rules,
- duration-profile constraints,
- spacing constraints.

`full_frame` remains dominant and the fallback. `multi_frame` and `continuous` remain common variety modes. `flipflop` and `captions` are expressive rhythm tools and should normally appear several times in long scripts when supported by the narration. `popup_sequence`, `comparison_board`, and `stat_card` remain low-count and meaning-driven, but the pipeline should actively scan for them before accepting zero.

### 2. Outline-Time Visual Opportunities

During segmented outline generation, each outline segment gets a compact `visual_opportunities` field. This field is not final scene JSON. It is a planning note that identifies likely mode opportunities before scenes are cut.

Example shape:

```json
{
  "mode": "captions",
  "beat": "A short realization that the job is no longer temporary",
  "why": "The narration should land as a renderer-owned editorial text beat.",
  "duration_profile": "extended",
  "priority": "strong"
}
```

The outline can include zero opportunities for a mode when none fit, but it should make that decision after scanning for candidates. For long scripts, `flipflop` and `captions` should be considered common rhythm opportunities, not exceptional modes.

### 3. Segment Scene Generation Consumes Its Plan

Each per-segment scene-generation call receives:

- the full outline for context,
- the segment's own `visual_opportunities`,
- the canonical visual-mode policy,
- the format-specific scene-writing instructions.

The scene writer may ignore weak opportunities if the narration does not earn them, but strong opportunities should shape scene boundaries from the start. A `captions` scene should be written with enough phrase material for `caption_text`; a `comparison_board` scene should hold the actual contrast in one scene; a `stat_card` scene should revolve around one decisive number.

### 4. Post-Generation Validation

After scenes are generated, validation checks consistency:

- `captions` scenes need exact `caption_text` and in-phrase `caption_emphasis`.
- `stat_card` scenes need one decisive `stat_value`.
- `comparison_board` and `popup_sequence` scenes need a compatible narrative shape.
- extended modes should not be assigned to scenes that are too short or structurally thin.
- non-title specialized modes should avoid invalid adjacency.

Validation may downgrade invalid modes to safer modes, but it should not rebalance the whole script or force missing modes into already-cut scenes.

### 5. Dev Observability

Generation should log a concise visual opportunity summary:

- projected total scene count,
- planned opportunity counts by mode,
- final generated counts by mode,
- warnings for suspicious underuse when strong opportunities existed but disappeared.

Warnings are diagnostics, not automatic rewrites.

## Script Quality Guardrails

Visual planning is subordinate to script quality. The outline must establish story, argument, progression, callbacks, stakes, and segment structure first. Visual opportunities annotate those beats; they must not invent extra beats or stretch narration just to satisfy mode variety.

Prompt and tests should preserve these rules:

- no hard quotas,
- full-frame dominance,
- format voice remains primary,
- visual opportunities must be earned by narration,
- extended modes must follow duration policy,
- post-generation validation must not rewrite narration.

## Testing Strategy

Add backend tests that prove:

- the canonical policy includes all visual modes and uses script-type-agnostic language,
- outline prompts request `visual_opportunities`,
- per-segment prompts consume segment-level opportunities,
- prompt text says `flipflop` and `captions` are common rhythm tools without making quotas,
- prompt text says `popup_sequence`, `comparison_board`, and `stat_card` should be actively scanned for but remain meaning-driven,
- validation/audit text forbids post-generation redistribution into already-short scenes,
- both `youtube-listicle` and `life-as-a` segmented prompts inherit the same canonical policy.

## Documentation

Update `AGENTS.md` to record the convention: visual-mode distribution guidance is script-type agnostic and should happen before final scene cutting. If the implementation changes in-app workflow or visible docs, update the relevant in-app docs in the same change.

## Acceptance Criteria

- Visual opportunity planning happens before final scene writing in segmented generation.
- The policy is shared across script formats.
- Scene boundaries and mode choices are planned together.
- `flipflop` and `captions` are treated as normal expressive rhythm options for long scripts.
- `popup_sequence`, `comparison_board`, and `stat_card` are actively considered, but not forced.
- Post-generation checks validate and downgrade invalid modes without rebalancing already-cut scenes.
- Tests cover prompt/policy behavior for both current formats.
