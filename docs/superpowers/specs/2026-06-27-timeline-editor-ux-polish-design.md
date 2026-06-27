# Timeline Editor UX Polish — Design

**Date:** 2026-06-27
**Scope:** `frontend/src/components/timeline/TimelinePage.tsx` (project editor)
**Type:** Visual / UX polish (no workflow or pipeline change)

## Problem

A Staff-Designer pass over the project editor (`TimelinePage`) surfaces two
high-impact weaknesses, judged against Apple HIG principles (clear hierarchy,
purposeful empty states, reduced clutter):

1. **The idle preview region is dead space.** When no scene is selected — which
   is the *default* state every time the editor loads — the entire region below
   the timeline (roughly 45% of the window) renders a single line of muted text,
   `"Select a scene to preview"`, centered in a void. It neither orients the user
   nor offers a next action. HIG: empty states should educate and guide, not sit
   blank.

2. **The page title is typographically under-weighted.** The project title — the
   single most important identifier on the page — renders at `text-base` (16px,
   `font-semibold`), the same scale as body chrome. The top navigation row
   (Back · Title · Upload) has no deliberate hierarchy, so the eye has no clear
   anchor. HIG: the subject of a view should be its most prominent text.

These two are the highest combined impact on UX, ease of use, and perceived
beauty because (1) is the largest and most-seen empty surface on the page, and
(2) is the most-viewed text element — both are seen on every visit.

## Improvement 1 — Project Overview idle panel

Replace the `"Select a scene to preview"` empty state (the `else` branch at the
bottom of the timeline view) with a focused, beautiful **Project Overview**
panel. It turns dead space into an at-a-glance production status + a clear next
action, while still inviting scene selection.

### Layout

A vertically-centered, `max-w-2xl` container (constrained width per HIG optimal
line length; avoids stretching across ultrawide displays), scrollable if short:

- **Header line:** small uppercase eyebrow `PROJECT OVERVIEW`, then a headline
  `"<N> of 7 steps complete"` with a slim full-width progress meter
  (violet fill, `bg-neutral-800` track, `transition-all`). Completion is derived
  from the seven pipeline steps already computed in `TimelineEditor`.

- **Next-step card (primary):** the first incomplete step, presented as a framed
  card (`border-violet-500/40 bg-violet-500/5`, matching the project's framed
  section-header idiom) with the step name, a one-line description, and a single
  primary button (`bg-violet-600 hover:bg-violet-500`) that triggers that step's
  existing handler. When that step is busy, the button shows a spinner and is
  disabled. When *all* steps are done, this card becomes a success state
  (emerald) reading "Production complete — ready to upload" with an Upload CTA.

- **Step checklist:** a two-column grid of the seven steps, each a compact row
  with an icon, label, and a status pill: `Done ✓` (emerald), `N left` (amber),
  or `Not started` (neutral). Glanceable progress without opening anything.

- **Footer hint:** muted helper text — "Select any scene in the timeline above to
  edit its visuals, voice, and timing" with a subtle `← →` keyboard hint chip.

### The seven steps (matching the existing pipeline + finalization rows)

`Thumbnails`, `Audio`, `Images`, `FX`, `Character` (Eli/main character),
`SEO`, `Export`. For each, `TimelineEditor` already computes a done boolean, a
missing count, a busy flag, and a confirm/generate handler:

| Step       | done                 | missing                  | busy                    | action                       |
|------------|----------------------|--------------------------|-------------------------|------------------------------|
| Thumbnails | `allThumbnailsDone`  | `missingThumbnailCount`  | `thumbnailsBusy`        | `confirmAndGenerateThumbnails` |
| Audio      | `allAudioGenerated`  | `missingAudioCount`      | `state.batchGeneratingAudio` | `confirmAndGenerateAudio` |
| Images     | `allImagesGenerated` | `missingImageCount`      | `state.batchGenerating` | `confirmAndGenerateImages`   |
| FX         | `allFXGenerated`     | `missingFXCount`         | `generatingFX`          | `confirmAndGenerateFX`       |
| Character  | `allEliGenerated` or `eliDisabledForProject`-aware | `missingEliCount` | `generatingEli` | `confirmAndGenerateEli` |
| SEO        | `allSeoDone`         | `missingSeoCount`        | `seoBusy`               | `confirmAndGenerateSeo`      |
| Export     | `allExportsDone`     | `missingExportCount`     | `exportBusy`            | `confirmAndExport`           |

### Component boundary

New presentational component
`frontend/src/components/timeline/ProjectOverviewPanel.tsx`. It is **pure**: it
receives a typed `steps` array (`OverviewStep[]`) plus summary stats
(`segmentCount`, `sceneCount`, `durationStr`, `totalWords`) and an
`onOpenUploadSuite` callback. It owns no business logic — `TimelineEditor`
assembles the `steps` array from values already in scope and passes it in. This
keeps `TimelinePage.tsx` from growing more logic and makes the panel testable in
isolation.

`OverviewStep = { key, label, Icon, description, done, missingCount, busy, onRun }`.

The "next step" is the first step in array order with `done === false`. The
character step is filtered out of the array entirely when Eli is disabled *and*
there is nothing to generate (so it neither blocks "complete" nor misleads).

### Edge cases / safety

- Triggering an action reuses the exact existing confirm handlers (which already
  handle overwrite confirmation modals and voice setup gating), so no new
  generation logic is introduced and no double-trigger risk beyond what the
  header buttons already have.
- Buttons disable while their step is busy; the next-step CTA disables while any
  step it represents is busy.
- The panel never renders when a scene IS selected (the `PropertiesPanel`
  branch is unchanged).

## Improvement 2 — Header title hierarchy

Refine the top navigation row (`Back · Title · Upload`) so the title anchors the
page.

- **Title scale:** `text-base` → `text-lg font-semibold tracking-tight`
  (`leading-tight`), keeping `truncate` + `min-w-0` so long titles still
  ellipsize. The edit `<input>` in editing mode is bumped to match
  (`text-lg`, taller `h-9`) so the swap is visually stable.
- **Edit affordance:** the pencil button stays visible (discoverability) but is
  restyled as a quieter ghost control that strengthens on hover — it should read
  as secondary to the title, not compete with it.
- **Row balance:** keep the existing `Back` and `Upload` controls; adjust the row
  gap/padding so the title has clear breathing room and is the dominant element.
  No new data plumbing.

This is deliberately scoped to typography and spacing — low risk, touching only
the title row JSX — and complements Improvement 1's clearer "what is this
project / where am I" story.

## Out of scope

- Pipeline step button layout, utility bar, timeline lanes/ruler, thumbnail
  preview, and all generation logic are unchanged.
- No backend, API, or data-model changes.

## Testing & verification

- `cd frontend && npm run build` must pass (TypeScript strict).
- `npm run test:frontend` must pass.
- Visual verification via the running dev app (`:5173`) with Playwright at
  desktop and a narrower width: confirm the overview panel renders on load,
  the next-step CTA reflects real status, the checklist pills are correct, and
  the elevated title truncates and edits correctly.
- Test Lab / dev-dashboard logs: not applicable (no generation/render/export
  behavior change).
