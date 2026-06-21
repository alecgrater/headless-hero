# Project Blink Review Design

## Purpose

Add a project-level manual review step for production full-frame blink. The blink detector finds safe candidates, and the user decides which eligible blinks actually render/export. Rendering and exporting are blocked until that review is complete, so blink quality is never left to an automatic frequency gate.

This design is implemented by the project Blink Review feature.

## Product Decision

Replace automatic production blink selection with a manual project review flow.

The existing Blink Audit remains the lab/debug surface for checking detector behavior across fixture projects. Production projects get their own page in the project workflow, next to tabs such as Segments, Visual Modes, Timeline, Thumbnails, and SEO. The page follows the Blink Audit visual pattern: still image on the left, blink preview on the right, scene id/narration/status underneath.

## Project Tab

Add a project tab named `Blink Review`.

The tab shows current-project full-frame blink candidates after scene images exist. It uses the same backend detector and preview geometry as production render/export. It does not introduce separate preview-only eligibility logic.

Each eligible scene card shows:

- scene id
- scene narration excerpt
- still preview
- blink preview
- a clear manual decision control: `Enable blink` or `Disable blink`
- review status: unreviewed, enabled, or disabled

Rejected scenes are not part of the required manual queue by default. The page includes a non-blocking rejected diagnostics filter only if it can reuse the same candidate data without extra generation work.

If no eligible scenes exist, the review is complete automatically and the tab says that no safe blink candidates were found.

## Data Model

Store detector output and manual review decisions on each scene's `visual_source_metadata.full_frame_blink`.

Exact shape:

```json
{
  "enabled": true,
  "action": "blink",
  "fingerprint": "sha256:image-url-and-anchor",
  "anchor": {"detected": true},
  "review": {
    "status": "enabled",
    "reviewed_at": "2026-06-21T00:00:00+00:00"
  }
}
```

Use these review statuses:

- `unreviewed`: the scene is eligible but the user has not decided yet
- `enabled`: render/export should blink this scene
- `disabled`: render/export should not blink this scene

The renderer treats blink as enabled only when the quality detector passed and review status is `enabled`. Eligible but unreviewed scenes must not silently blink.

## Candidate Refresh And Staleness

Blink Review refreshes candidates from current scene image metadata. If a scene image changes, its prior blink review decision is stale and must be cleared back to `unreviewed` when the detector finds a new eligible anchor.

Cache validity is based on enough stable image/anchor metadata to avoid applying a manual decision to the wrong image. Store a fingerprint on the blink metadata that changes when the scene image URL or anchor data changes.

## Render And Export Guard

Before long-form render, short-form render, export, and any render-status/export path that can reuse cached media, validate project blink review state.

Blocking condition:

- at least one current full-frame scene is eligible for blink
- at least one eligible scene has missing/stale/unreviewed blink review status

When blocked, return a user-visible error that says Blink Review must be completed before rendering/exporting. The frontend shows this as a clear warning/modal and routes the user toward the Blink Review tab. The render/export job does not start.

If every eligible scene is reviewed, rendering/exporting can proceed. Rendered output should include blink only for reviewed `enabled` scenes.

## Relationship To Blink Audit

Blink Audit and Blink Review should share the same backend detector, quality rejection reasons, and preview geometry.

Blink Audit remains useful for bulk detector tuning. Blink Review is the production readiness step for a specific project.

The old deterministic 50% production frequency gate no longer decides final render behavior once Blink Review exists. Manual review replaces it. A deterministic sample gate can remain only as a lab/debug signal, and it must not affect production render/export.

## Documentation And Conventions

Update `AGENTS.md` and in-app workflow docs with the new rule:

- production full-frame blink requires manual project Blink Review
- rendering/exporting is blocked until eligible blink candidates are reviewed
- render/export uses only manually enabled blink candidates
- Blink Audit is a detector lab, not the final production approval surface

## Testing

Backend tests should cover:

- candidate refresh creates unreviewed eligible blink metadata
- manual enable/disable decisions persist on scenes
- stale image/anchor metadata clears prior decisions
- blink metadata fingerprints change when scene image URL or anchor data changes
- render/export guard blocks when eligible candidates are unreviewed
- render/export guard passes when all eligible candidates are reviewed
- renderer props include blink metadata only for manually enabled scenes

Frontend tests should cover:

- the project tab appears in the project workflow
- eligible scenes show still/blink previews and manual controls
- enabling/disabling a scene updates the displayed status
- empty eligible state marks review complete
- render/export blocked responses surface a clear warning that directs the user to Blink Review
