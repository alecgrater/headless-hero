# Script Types Reference Page — Design

**Date:** 2026-05-29
**Status:** Approved (design)

## Goal

Add a read-only **Script Types** page under Settings → Reference that details the
differences and compatibility "gotchas" between video formats (currently
`youtube-listicle` and `life-as-a`). Designed so that adding a new script type
later requires no frontend edits — the page is driven entirely by the backend
format registry.

## Source of truth

Backend-declarative. The `VideoFormat` registry (`backend/pipeline/formats/`) is
already the single source of truth for format orchestration. We extend it with
two declarative reference fields and expose them through the existing
`/api/formats` endpoint. The frontend renders the page purely from that payload,
so registering a new `VideoFormat` automatically adds a matrix column and a
gotchas entry.

## Backend changes

### 1. `VideoFormat` dataclass (`backend/pipeline/formats/base.py`)

Add a small frozen `FormatNote` dataclass and two fields to `VideoFormat`:

```python
@dataclass(frozen=True)
class FormatNote:
    category: str   # "Openings" | "Narration" | "Visuals" | "Title cards"
                    # | "Scene length" | "Short-form" | "AI video"
    text: str       # one curated gotcha / rule, plain prose

@dataclass(frozen=True)
class VideoFormat:
    ...
    supported_visual_modes: tuple[str, ...] = ()   # modes this format may emit
    reference_notes: tuple[FormatNote, ...] = ()    # curated gotchas, grouped
```

Both default to empty so the field addition is non-breaking for any future
format that has not yet filled them in.

### 2. Fill in the two registered formats

- `youtube_listicle.py` — `supported_visual_modes` = the full set:
  `full_frame, multi_frame, continuous, popup_sequence, flipflop,
  comparison_board, stat_card, captions`. `reference_notes` capture
  listicle gotchas, e.g.:
  - Openings: "Cold-open candidate scenes are hook-scored and refined before the script is written."
  - Narration: "Every segment must stand alone as a short — no whole-video recaps, subscribe requests, or 'come back next week' CTAs in scene narration. `outro_cta` is editor metadata only."
  - Short-form: "Each segment can be exported as a standalone short; SEO titles are `{project title} - {segment title}`."

- `life_as_a.py` — `supported_visual_modes` = `full_frame, continuous,
  multi_frame`. `reference_notes` capture life-as-a gotchas, e.g.:
  - Visuals: "`captions` and `stat_card` are disabled in v1 — no editorial caption or stat-number scenes."
  - Openings: "Uses a life-as-a-specific cold-open prompt/rubric (second-person immersion, role fantasy); NOT hook-scored. Openings are long-form-only and trimmed from short #1 via `hook_scene_count`."
  - Narration: "Second-person, literary register; no listicle cadence (no 'Hey guys', no rule-of-three, no mic drops). Chapter-card narration stores the descriptor phrase only — TTS adds 'Level N' at audio time."
  - Scene length: "Non-title scenes target 5–9s and one beat; overlong scenes are split deterministically before voiceover."
  - Short-form: "Shorts show `Part {n}/{total}` on the title card; upload titles stay deterministic with no `(Part …)` suffix."
  - AI video: "Animation is eligible only for active-protagonist scenes."

The exact note wording is authored from the documented rules in
`backend/prompts/script.py` and `CLAUDE.md`; the list above is representative,
not exhaustive — the spec author fills the full set during implementation.

### 3. `/api/formats` payload (`backend/api/formats.py`)

Extend `FormatSummary` with:

```python
supported_visual_modes: list[str]
allowed_visual_beats: list[str]          # from visual_beat_rules.allowed_beats (sorted)
max_consecutive_same_beat: int           # from visual_beat_rules
target_distribution: dict[str, list[float]]  # beat -> [lo, hi], {} if run-driven
reference_notes: list[dict[str, str]]    # [{category, text}, ...]
```

`_summarize()` maps these from the dataclass. No new endpoint; `getFormats()`
already consumes this route.

## Frontend changes

### 1. Types (`frontend/src/types/format.ts`)

Extend the existing `VideoFormat` TS interface with the new fields
(`supported_visual_modes`, `allowed_visual_beats`, `max_consecutive_same_beat`,
`target_distribution`, `reference_notes: { category: string; text: string }[]`).

### 2. New page (`frontend/src/components/settings/script-types/`)

Mirror the `visual-modes/` structure:

- `ScriptTypesSection.tsx` — fetches `getFormats()` on mount (loading + error
  states matching existing settings sections). Renders:
  1. **Comparison matrix** — rows = dimensions, columns = formats. Dimensions:
     One-liner (`short_description`), Structure (`{level_count} {level_label}s`,
     e.g. "8 segments" vs "4–7 levels"), Title cards
     (`title_card_strategy_kind`), Segmented generation, Cold open, Hook scoring,
     Visual rhythm (`allowed_visual_beats` + `max consecutive`), Visual modes
     (count supported / count disabled). Differences are the point; columns
     scroll horizontally past ~3 formats.
  2. **Per-format gotchas panel** — one card per format showing
     `reference_notes` grouped by category as readable callouts, plus a
     visual-mode **chip row**: supported modes as normal chips, disabled modes
     (full Visual Modes catalog minus `supported_visual_modes`) struck-through /
     dimmed. The panel header cross-links to the Visual Modes reference page.
- Disabled-mode derivation reuses the mode id list from the existing
  `visual-modes/catalog.ts` (import `VISUAL_MODE_CATALOG`), keeping the two
  reference pages consistent and avoiding a second hard-coded mode list.

### 3. Register the section (`SettingsPage.tsx`)

Add `{ id: "script-types", label: "Script Types",
description: "Compare every script format — structure, narration rules, and visual-mode compatibility.",
icon: <a list icon, e.g. ListTree>, group: "Reference" }` to `SECTIONS`, and a
render branch `{activeSection === "script-types" && <ScriptTypesSection />}`.
Place it before "Visual Modes" in the Reference group.

## Out of scope (noted future opportunity)

`supported_visual_modes` becoming a declared field opens the door to
**enforcing** disabled modes during generation (coercing a disallowed mode back
to `full_frame` with a dev-dashboard warning), which would prevent drift between
this reference data and actual generation. This is intentionally NOT part of this
change — the page is reference-only. If desired later, it is a separate,
well-scoped follow-up.

## Testing

- **Backend:** extend `/api/formats` coverage to assert the new fields serialize
  for both formats and that every `supported_visual_modes` entry is a known
  visual mode id.
- **Frontend:** `ScriptTypesSection.test.tsx` (Vitest, matching
  `SubtitlesSection.test.tsx`) mocks `getFormats()` and asserts the matrix renders
  a column per format, the gotchas panel renders notes, and disabled modes show
  as struck-through.

## Observability

None. Read-only reference page, consistent with the Visual Modes page (no
generation/render/export/integration state touched).

## Extensibility summary

Adding a new script type = register its `VideoFormat` with
`supported_visual_modes` and `reference_notes` filled in. The matrix gains a
column and the gotchas panel gains a card automatically; no frontend changes.
