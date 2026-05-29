# Script Types Reference Page — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a read-only Settings → Reference → "Script Types" page that compares every video format's structure, narration rules, and visual-mode compatibility, driven entirely by the backend format registry.

**Architecture:** Extend the declarative `VideoFormat` dataclass with two reference fields (`supported_visual_modes`, `reference_notes`), surface them through the existing `/api/formats` endpoint, and render a comparison matrix + per-format gotchas panel on the frontend from `getFormats()`. Adding a future format requires only filling in those fields on its `VideoFormat`.

**Tech Stack:** Python 3.12 / FastAPI / Pydantic / SQLModel (backend, via `uv`); React 19 / TypeScript / Tailwind 4 / Vitest (frontend). Backend tests run with `uv run --project backend pytest`.

**Spec:** `docs/superpowers/specs/2026-05-29-script-types-reference-page-design.md`

---

## File Structure

**Backend (create/modify):**
- Modify `backend/pipeline/formats/base.py` — add `FormatNote` dataclass + two `VideoFormat` fields.
- Modify `backend/pipeline/formats/youtube_listicle.py` — fill in the two new fields.
- Modify `backend/pipeline/formats/life_as_a.py` — fill in the two new fields.
- Modify `backend/api/formats.py` — widen `FormatSummary` + `_summarize`.
- Modify `backend/tests/pipeline/test_formats_registry.py` — assert new fields.
- Create `backend/tests/test_formats_endpoint.py` — assert endpoint serialization.

**Frontend (create/modify):**
- Modify `frontend/src/types/format.ts` — extend `VideoFormat` interface.
- Create `frontend/src/components/settings/script-types/modes.ts` — pure helper deriving supported/disabled mode chips.
- Create `frontend/src/components/settings/script-types/modes.test.ts` — unit test for the helper.
- Create `frontend/src/components/settings/script-types/ScriptTypesSection.tsx` — matrix + gotchas panel.
- Create `frontend/src/components/settings/script-types/ScriptTypesSection.test.tsx` — render test.
- Modify `frontend/src/components/settings/SettingsPage.tsx` — register the section.

---

## Task 1: Add reference fields to the `VideoFormat` dataclass

**Files:**
- Modify: `backend/pipeline/formats/base.py`
- Test: `backend/tests/pipeline/test_formats_registry.py`

- [ ] **Step 1: Write the failing test**

Add to `backend/tests/pipeline/test_formats_registry.py`:

```python
def test_video_format_reference_fields_default_empty():
    """New reference fields must default to empty so existing formats stay valid."""
    from pipeline.formats.base import FormatNote, VideoFormat

    # FormatNote is a simple (category, text) record.
    note = FormatNote(category="Narration", text="example rule")
    assert note.category == "Narration"
    assert note.text == "example rule"

    # The fields exist on the dataclass and default to empty tuples.
    import dataclasses
    field_names = {f.name for f in dataclasses.fields(VideoFormat)}
    assert "supported_visual_modes" in field_names
    assert "reference_notes" in field_names
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run --project backend pytest tests/pipeline/test_formats_registry.py::test_video_format_reference_fields_default_empty -v`
Expected: FAIL with `ImportError: cannot import name 'FormatNote'`.

- [ ] **Step 3: Write minimal implementation**

In `backend/pipeline/formats/base.py`, add the `FormatNote` dataclass after the imports (near `VisualBeatRules`):

```python
@dataclass(frozen=True)
class FormatNote:
    """One curated reference gotcha for a format, grouped by category.

    category: "Openings" | "Narration" | "Visuals" | "Title cards"
              | "Scene length" | "Short-form" | "AI video"
    """

    category: str
    text: str
```

Then add two fields to the end of the `VideoFormat` dataclass (after `enforce_post_processing`). Because `VideoFormat` has required fields, the new fields MUST have defaults:

```python
    # Reference-only metadata (drives the Script Types settings page; not enforced)
    supported_visual_modes: tuple[str, ...] = ()
    reference_notes: tuple[FormatNote, ...] = ()
```

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run --project backend pytest tests/pipeline/test_formats_registry.py::test_video_format_reference_fields_default_empty -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add backend/pipeline/formats/base.py backend/tests/pipeline/test_formats_registry.py
git commit -m "Add reference metadata fields to VideoFormat"
```

---

## Task 2: Populate the two registered formats

**Files:**
- Modify: `backend/pipeline/formats/youtube_listicle.py`
- Modify: `backend/pipeline/formats/life_as_a.py`
- Test: `backend/tests/pipeline/test_formats_registry.py`

- [ ] **Step 1: Write the failing test**

Add to `backend/tests/pipeline/test_formats_registry.py`:

```python
def test_supported_visual_modes_are_known():
    """Every declared supported mode must be a canonical visual mode id."""
    from models.script import VISUAL_MODES
    from pipeline.formats import list_formats

    for fmt in list_formats():
        assert fmt.supported_visual_modes, f"{fmt.id} declares no supported modes"
        unknown = set(fmt.supported_visual_modes) - VISUAL_MODES
        assert not unknown, f"{fmt.id} has unknown visual modes: {unknown}"


def test_life_as_a_disables_caption_and_stat_modes():
    """captions and stat_card are disabled in life-as-a; they must be absent."""
    from pipeline.formats import get_format

    fmt = get_format("life-as-a")
    assert "captions" not in fmt.supported_visual_modes
    assert "stat_card" not in fmt.supported_visual_modes
    assert "full_frame" in fmt.supported_visual_modes


def test_formats_have_reference_notes():
    from pipeline.formats import list_formats

    for fmt in list_formats():
        assert fmt.reference_notes, f"{fmt.id} has no reference notes"
        for note in fmt.reference_notes:
            assert note.category and note.text
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run --project backend pytest tests/pipeline/test_formats_registry.py::test_supported_visual_modes_are_known tests/pipeline/test_formats_registry.py::test_formats_have_reference_notes -v`
Expected: FAIL — both formats currently declare empty `supported_visual_modes` / `reference_notes`.

- [ ] **Step 3: Write minimal implementation**

In `backend/pipeline/formats/youtube_listicle.py`, update the import line:

```python
from .base import FormatNote, VideoFormat, VisualBeatRules
```

Then add these two keyword arguments to the `VideoFormat(...)` call (after `enforce_post_processing=...`):

```python
    supported_visual_modes=(
        "full_frame", "multi_frame", "continuous", "video",
        "popup_sequence", "flipflop", "comparison_board",
        "stat_card", "captions", "dossier",
    ),
    reference_notes=(
        FormatNote(category="Openings",
                   text="Cold-open candidates are generated, hook-scored, and refined before the full script is written."),
        FormatNote(category="Narration",
                   text="Every segment must stand alone as a short. Keep whole-video recaps, subscribe requests, and 'come back next week' CTAs out of scene narration; outro_cta is editor metadata only."),
        FormatNote(category="Visuals",
                   text="The full visual-mode vocabulary is available. full_frame stays the majority; variety modes (multi_frame, popup_sequence, flipflop, comparison_board, stat_card, captions, dossier) are spaced out and never run back-to-back."),
        FormatNote(category="Short-form",
                   text="Any segment can be exported as a standalone short; short-form upload titles are deterministic '{project title} - {segment title}'."),
    ),
```

In `backend/pipeline/formats/life_as_a.py`, find the `from .base import ...` line and add `FormatNote` to it (it currently imports `TitleCardStrategy, VideoFormat, VisualBeatRules` or a subset — add `FormatNote` to whichever import pulls from `.base`). Verify with:

```bash
grep -n "from .base import" backend/pipeline/formats/life_as_a.py
```

Ensure `FormatNote` is included, e.g.:

```python
from .base import FormatNote, VideoFormat, VisualBeatRules
```

Then add these keyword arguments to the `LIFE_AS_A = _register(VideoFormat(...))` call (after `enforce_post_processing=...`):

```python
    supported_visual_modes=("full_frame", "continuous", "multi_frame", "video"),
    reference_notes=(
        FormatNote(category="Openings",
                   text="Uses a life-as-a-specific cold-open prompt and rubric (second-person immersion, role fantasy, stakes) — NOT listicle hook scoring. Openings are long-form-only and trimmed from short #1 via hook_scene_count."),
        FormatNote(category="Narration",
                   text="Second-person, literary register. No listicle cadence: no 'Hey guys', no rule-of-three escalation, no mic drops."),
        FormatNote(category="Title cards",
                   text="Chapter-card narration stores the descriptor phrase only (e.g. 'The occasional.'); the TTS layer adds 'Level N' at audio time."),
        FormatNote(category="Visuals",
                   text="captions and stat_card are disabled in v1 — no editorial caption or stat-number scenes. Visual rhythm is balanced full_frame / continuous / multi_frame."),
        FormatNote(category="Scene length",
                   text="Non-title scenes target 5–9s and one beat; overlong scenes are split deterministically on sentence boundaries before voiceover."),
        FormatNote(category="Short-form",
                   text="Shorts show 'Part {n}/{total}' on the title card and above the thumbnail; upload titles stay deterministic with no '(Part …)' suffix."),
        FormatNote(category="AI video",
                   text="AI-video animation is eligible only for active-protagonist scenes."),
    ),
```

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run --project backend pytest tests/pipeline/test_formats_registry.py -v`
Expected: PASS (all registry tests, including the three new ones).

- [ ] **Step 5: Commit**

```bash
git add backend/pipeline/formats/youtube_listicle.py backend/pipeline/formats/life_as_a.py backend/tests/pipeline/test_formats_registry.py
git commit -m "Declare supported visual modes and reference notes per format"
```

---

## Task 3: Widen the `/api/formats` payload

**Files:**
- Modify: `backend/api/formats.py`
- Test: `backend/tests/test_formats_endpoint.py`

- [ ] **Step 1: Write the failing test**

Create `backend/tests/test_formats_endpoint.py`:

```python
"""Tests for the /api/formats payload (reference-page fields)."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))


def test_formats_endpoint_includes_reference_fields():
    from api.formats import list_formats_endpoint

    summaries = {s.id: s for s in list_formats_endpoint()}

    listicle = summaries["youtube-listicle"]
    life = summaries["life-as-a"]

    # Supported modes round-trip as a list.
    assert "captions" in listicle.supported_visual_modes
    assert "captions" not in life.supported_visual_modes
    assert "stat_card" not in life.supported_visual_modes

    # Visual-beat rules surface for the rhythm row.
    assert set(listicle.allowed_visual_beats) == {"static", "continuous", "multi_frame"}
    assert listicle.max_consecutive_same_beat == 3
    assert life.max_consecutive_same_beat == 2

    # target_distribution serializes as beat -> [lo, hi].
    assert life.target_distribution["static"] == [0.45, 0.60]
    assert listicle.target_distribution == {}

    # Reference notes serialize as a list of {category, text}.
    assert life.reference_notes
    assert all(set(n.keys()) == {"category", "text"} for n in life.reference_notes)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run --project backend pytest tests/test_formats_endpoint.py -v`
Expected: FAIL with `AttributeError`/validation error — `FormatSummary` has no `supported_visual_modes`.

- [ ] **Step 3: Write minimal implementation**

Replace the body of `backend/api/formats.py` with:

```python
"""Format discovery endpoint — drives the frontend selector and reference page."""

from fastapi import APIRouter
from pydantic import BaseModel

from pipeline.formats import list_formats

router = APIRouter(prefix="/api/formats", tags=["formats"])


class FormatSummary(BaseModel):
    id: str
    display_name: str
    short_description: str
    level_count_min: int
    level_count_max: int
    level_label: str
    supports_cold_open: bool
    supports_hook_scoring: bool
    supports_segmented_generation: bool
    title_card_strategy_kind: str
    supported_visual_modes: list[str]
    allowed_visual_beats: list[str]
    max_consecutive_same_beat: int
    target_distribution: dict[str, list[float]]
    reference_notes: list[dict[str, str]]


def _summarize(fmt) -> FormatSummary:
    if isinstance(fmt.level_count, int):
        lo = hi = fmt.level_count
    else:
        lo, hi = fmt.level_count
    rules = fmt.visual_beat_rules
    return FormatSummary(
        id=fmt.id,
        display_name=fmt.display_name,
        short_description=fmt.short_description,
        level_count_min=lo,
        level_count_max=hi,
        level_label=fmt.level_label,
        supports_cold_open=fmt.supports_cold_open,
        supports_hook_scoring=fmt.supports_hook_scoring,
        supports_segmented_generation=fmt.supports_segmented_generation,
        title_card_strategy_kind=fmt.title_card_strategy.kind,
        supported_visual_modes=list(fmt.supported_visual_modes),
        allowed_visual_beats=sorted(rules.allowed_beats),
        max_consecutive_same_beat=rules.max_consecutive_same_beat,
        target_distribution={k: [lo_, hi_] for k, (lo_, hi_) in rules.target_distribution.items()},
        reference_notes=[{"category": n.category, "text": n.text} for n in fmt.reference_notes],
    )


@router.get("", response_model=list[FormatSummary])
def list_formats_endpoint() -> list[FormatSummary]:
    return [_summarize(f) for f in list_formats()]
```

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run --project backend pytest tests/test_formats_endpoint.py -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add backend/api/formats.py backend/tests/test_formats_endpoint.py
git commit -m "Serialize reference fields in /api/formats payload"
```

---

## Task 4: Extend the frontend `VideoFormat` type

**Files:**
- Modify: `frontend/src/types/format.ts`

- [ ] **Step 1: Update the interface**

Replace the contents of `frontend/src/types/format.ts` with:

```ts
export interface FormatNote {
  category: string;
  text: string;
}

export interface VideoFormat {
  id: string;
  display_name: string;
  short_description: string;
  level_count_min: number;
  level_count_max: number;
  level_label: string;        // "segment" | "level"
  supports_cold_open: boolean;
  supports_hook_scoring: boolean;
  supports_segmented_generation: boolean;
  title_card_strategy_kind: "composite-grid" | "cinematic-chapters";
  supported_visual_modes: string[];
  allowed_visual_beats: string[];
  max_consecutive_same_beat: number;
  target_distribution: Record<string, number[]>;
  reference_notes: FormatNote[];
}
```

- [ ] **Step 2: Verify the frontend still type-checks**

Run: `cd frontend && npx tsc --noEmit`
Expected: no errors (existing `getFormats()` consumers only read pre-existing fields).

- [ ] **Step 3: Commit**

```bash
git add frontend/src/types/format.ts
git commit -m "Extend VideoFormat type with reference fields"
```

---

## Task 5: Mode-chip derivation helper

**Files:**
- Create: `frontend/src/components/settings/script-types/modes.ts`
- Test: `frontend/src/components/settings/script-types/modes.test.ts`

- [ ] **Step 1: Write the failing test**

Create `frontend/src/components/settings/script-types/modes.test.ts`:

```ts
import { describe, expect, it } from "vitest";
import type { VideoFormat } from "../../../types/format";
import { allVisualModes, modeChipsForFormat } from "./modes";

function fmt(id: string, modes: string[]): VideoFormat {
  return {
    id,
    display_name: id,
    short_description: "",
    level_count_min: 1,
    level_count_max: 1,
    level_label: "segment",
    supports_cold_open: true,
    supports_hook_scoring: true,
    supports_segmented_generation: true,
    title_card_strategy_kind: "composite-grid",
    supported_visual_modes: modes,
    allowed_visual_beats: [],
    max_consecutive_same_beat: 3,
    target_distribution: {},
    reference_notes: [],
  };
}

describe("mode chip derivation", () => {
  it("builds the ordered universe as the union across formats", () => {
    const formats = [
      fmt("a", ["full_frame", "captions"]),
      fmt("b", ["full_frame", "continuous"]),
    ];
    expect(allVisualModes(formats)).toEqual(["full_frame", "captions", "continuous"]);
  });

  it("splits supported vs disabled against the universe", () => {
    const formats = [
      fmt("listicle", ["full_frame", "captions"]),
      fmt("life", ["full_frame"]),
    ];
    const universe = allVisualModes(formats);
    const life = modeChipsForFormat(formats[1], universe);
    expect(life.supported.map((c) => c.id)).toEqual(["full_frame"]);
    expect(life.disabled.map((c) => c.id)).toEqual(["captions"]);
  });

  it("flags whether a mode has a Visual Modes detail entry", () => {
    const universe = ["full_frame", "dossier"];
    const chips = modeChipsForFormat(fmt("x", ["full_frame", "dossier"]), universe);
    const byId = Object.fromEntries(chips.supported.map((c) => [c.id, c]));
    expect(byId["full_frame"].hasDetail).toBe(true);   // in VISUAL_MODE_CATALOG
    expect(byId["dossier"].hasDetail).toBe(false);     // not in catalog yet
    expect(byId["full_frame"].label).toBe("Full Frame");
  });
});
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd frontend && npx vitest run src/components/settings/script-types/modes.test.ts`
Expected: FAIL — `./modes` does not exist.

- [ ] **Step 3: Write minimal implementation**

Create `frontend/src/components/settings/script-types/modes.ts`:

```ts
import type { VideoFormat } from "../../../types/format";
import { VISUAL_MODE_CATALOG } from "../visual-modes/catalog";

export interface ModeChip {
  id: string;
  label: string;
  hasDetail: boolean; // true if the Visual Modes reference page has an entry to link to
}

const CATALOG_BY_ID = new Map(VISUAL_MODE_CATALOG.map((e) => [e.id as string, e]));

function humanize(id: string): string {
  return id
    .split("_")
    .map((w) => w.charAt(0).toUpperCase() + w.slice(1))
    .join(" ");
}

function toChip(id: string): ModeChip {
  const entry = CATALOG_BY_ID.get(id);
  return { id, label: entry ? entry.label : humanize(id), hasDetail: Boolean(entry) };
}

/** Ordered union of every format's supported modes (first-appearance order). */
export function allVisualModes(formats: VideoFormat[]): string[] {
  const seen: string[] = [];
  for (const fmt of formats) {
    for (const mode of fmt.supported_visual_modes) {
      if (!seen.includes(mode)) seen.push(mode);
    }
  }
  return seen;
}

export function modeChipsForFormat(
  format: VideoFormat,
  universe: string[],
): { supported: ModeChip[]; disabled: ModeChip[] } {
  const supportedSet = new Set(format.supported_visual_modes);
  const supported: ModeChip[] = [];
  const disabled: ModeChip[] = [];
  for (const id of universe) {
    (supportedSet.has(id) ? supported : disabled).push(toChip(id));
  }
  return { supported, disabled };
}
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd frontend && npx vitest run src/components/settings/script-types/modes.test.ts`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add frontend/src/components/settings/script-types/modes.ts frontend/src/components/settings/script-types/modes.test.ts
git commit -m "Add mode-chip derivation helper for Script Types page"
```

---

## Task 6: ScriptTypesSection component

**Files:**
- Create: `frontend/src/components/settings/script-types/ScriptTypesSection.tsx`
- Test: `frontend/src/components/settings/script-types/ScriptTypesSection.test.tsx`

- [ ] **Step 1: Write the failing test**

Create `frontend/src/components/settings/script-types/ScriptTypesSection.test.tsx`:

```tsx
import { render, screen, waitFor } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import type { VideoFormat } from "../../../types/format";
import ScriptTypesSection from "./ScriptTypesSection";

const FORMATS: VideoFormat[] = [
  {
    id: "youtube-listicle",
    display_name: "Educational Listicle",
    short_description: "8 things…",
    level_count_min: 8,
    level_count_max: 8,
    level_label: "segment",
    supports_cold_open: true,
    supports_hook_scoring: true,
    supports_segmented_generation: true,
    title_card_strategy_kind: "composite-grid",
    supported_visual_modes: ["full_frame", "captions", "stat_card"],
    allowed_visual_beats: ["continuous", "multi_frame", "static"],
    max_consecutive_same_beat: 3,
    target_distribution: {},
    reference_notes: [{ category: "Narration", text: "Segments stand alone." }],
  },
  {
    id: "life-as-a",
    display_name: "Your Life As A...",
    short_description: "A walk through stages…",
    level_count_min: 4,
    level_count_max: 7,
    level_label: "level",
    supports_cold_open: true,
    supports_hook_scoring: false,
    supports_segmented_generation: true,
    title_card_strategy_kind: "cinematic-chapters",
    supported_visual_modes: ["full_frame"],
    allowed_visual_beats: ["continuous", "multi_frame", "static"],
    max_consecutive_same_beat: 2,
    target_distribution: { static: [0.45, 0.6] },
    reference_notes: [{ category: "Visuals", text: "captions and stat_card are disabled." }],
  },
];

vi.mock("../../../api", () => ({
  getFormats: vi.fn(async () => FORMATS),
}));

describe("ScriptTypesSection", () => {
  it("renders a column per format and the gotchas notes", async () => {
    render(<ScriptTypesSection />);
    await waitFor(() => expect(screen.getByText("Educational Listicle")).toBeInTheDocument());
    expect(screen.getByText("Your Life As A...")).toBeInTheDocument();
    // gotcha note text from reference_notes renders in the panel
    expect(screen.getByText("captions and stat_card are disabled.")).toBeInTheDocument();
    // disabled mode for life-as-a shows captions as a disabled chip (struck-through)
    const disabledChip = screen.getByTestId("disabled-mode-life-as-a-captions");
    expect(disabledChip).toBeInTheDocument();
  });
});
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd frontend && npx vitest run src/components/settings/script-types/ScriptTypesSection.test.tsx`
Expected: FAIL — `./ScriptTypesSection` does not exist.

- [ ] **Step 3: Write minimal implementation**

Create `frontend/src/components/settings/script-types/ScriptTypesSection.tsx`:

```tsx
import { useEffect, useState } from "react";
import { getFormats } from "../../../api";
import type { VideoFormat } from "../../../types/format";
import { allVisualModes, modeChipsForFormat, type ModeChip } from "./modes";

interface MatrixRow {
  label: string;
  render: (f: VideoFormat) => string;
}

const ROWS: MatrixRow[] = [
  { label: "Summary", render: (f) => f.short_description },
  {
    label: "Structure",
    render: (f) =>
      f.level_count_min === f.level_count_max
        ? `${f.level_count_min} ${f.level_label}s`
        : `${f.level_count_min}–${f.level_count_max} ${f.level_label}s`,
  },
  {
    label: "Title cards",
    render: (f) => (f.title_card_strategy_kind === "composite-grid" ? "Composite grid" : "Cinematic chapters"),
  },
  { label: "Cold open", render: (f) => (f.supports_cold_open ? "Yes" : "No") },
  { label: "Hook scoring", render: (f) => (f.supports_hook_scoring ? "Yes" : "No") },
  { label: "Segmented generation", render: (f) => (f.supports_segmented_generation ? "Yes" : "No") },
  {
    label: "Visual rhythm",
    render: (f) => `${f.allowed_visual_beats.join(", ")} · max ${f.max_consecutive_same_beat} in a row`,
  },
  {
    label: "Visual modes",
    render: (f) => `${f.supported_visual_modes.length} supported`,
  },
];

function Chip({ chip, disabled, formatId }: { chip: ModeChip; disabled?: boolean; formatId: string }) {
  return (
    <span
      data-testid={disabled ? `disabled-mode-${formatId}-${chip.id}` : `mode-${formatId}-${chip.id}`}
      className={`inline-block rounded-md px-2 py-0.5 text-[11px] font-medium transition-colors ${
        disabled
          ? "bg-neutral-900 text-neutral-600 line-through"
          : "bg-neutral-800 text-neutral-200"
      }`}
      title={chip.hasDetail ? "See the Visual Modes reference for details" : undefined}
    >
      {chip.label}
    </span>
  );
}

export default function ScriptTypesSection() {
  const [formats, setFormats] = useState<VideoFormat[] | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    getFormats()
      .then(setFormats)
      .catch(() => setError("Could not load script formats."));
  }, []);

  if (error) return <div className="px-6 py-5 text-sm text-rose-400">{error}</div>;
  if (!formats) return <div className="px-6 py-5 text-sm text-neutral-500">Loading…</div>;

  const universe = allVisualModes(formats);

  return (
    <div className="px-6 py-5 space-y-6">
      <div>
        <h2 className="text-base font-semibold text-neutral-100">Script Types</h2>
        <p className="text-[11px] text-neutral-500">
          Read-only reference — how each script format differs in structure, narration, and visual-mode
          compatibility. Mode chips link conceptually to the Visual Modes reference page.
        </p>
      </div>

      {/* Comparison matrix */}
      <div className="overflow-x-auto">
        <table className="w-full border-collapse text-sm">
          <thead>
            <tr>
              <th className="w-44 border-b border-neutral-800 px-3 py-2 text-left text-[11px] font-semibold uppercase tracking-wide text-neutral-500">
                Dimension
              </th>
              {formats.map((f) => (
                <th key={f.id} className="border-b border-neutral-800 px-3 py-2 text-left font-semibold text-neutral-100">
                  {f.display_name}
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {ROWS.map((row) => (
              <tr key={row.label}>
                <td className="border-b border-neutral-900 px-3 py-2 align-top text-[11px] font-medium uppercase tracking-wide text-neutral-500">
                  {row.label}
                </td>
                {formats.map((f) => (
                  <td key={f.id} className="border-b border-neutral-900 px-3 py-2 align-top text-neutral-300">
                    {row.render(f)}
                  </td>
                ))}
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      {/* Per-format gotchas + mode chips */}
      <div className="grid gap-4 md:grid-cols-2">
        {formats.map((f) => {
          const { supported, disabled } = modeChipsForFormat(f, universe);
          return (
            <div key={f.id} className="rounded-lg border border-neutral-800 bg-neutral-900/40 p-4 space-y-3">
              <div className="text-sm font-semibold text-neutral-100">{f.display_name}</div>

              <div className="space-y-1.5">
                <div className="text-[10px] font-semibold uppercase tracking-wider text-neutral-500">Supported modes</div>
                <div className="flex flex-wrap gap-1.5">
                  {supported.map((c) => (
                    <Chip key={c.id} chip={c} formatId={f.id} />
                  ))}
                </div>
                {disabled.length > 0 && (
                  <>
                    <div className="pt-1 text-[10px] font-semibold uppercase tracking-wider text-neutral-600">Disabled here</div>
                    <div className="flex flex-wrap gap-1.5">
                      {disabled.map((c) => (
                        <Chip key={c.id} chip={c} disabled formatId={f.id} />
                      ))}
                    </div>
                  </>
                )}
              </div>

              <div className="space-y-2">
                {f.reference_notes.map((note, i) => (
                  <div key={i} className="text-xs">
                    <span className="font-semibold text-neutral-400">{note.category}: </span>
                    <span className="text-neutral-400">{note.text}</span>
                  </div>
                ))}
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
}
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd frontend && npx vitest run src/components/settings/script-types/ScriptTypesSection.test.tsx`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add frontend/src/components/settings/script-types/ScriptTypesSection.tsx frontend/src/components/settings/script-types/ScriptTypesSection.test.tsx
git commit -m "Add ScriptTypesSection comparison + gotchas component"
```

---

## Task 7: Register the section in Settings

**Files:**
- Modify: `frontend/src/components/settings/SettingsPage.tsx`

- [ ] **Step 1: Add the import**

In `frontend/src/components/settings/SettingsPage.tsx`, add to the lucide-react import block the icon `GitCompare`, and add a component import after the `VisualModesSection` import:

```tsx
import ScriptTypesSection from "./script-types/ScriptTypesSection";
```

The lucide import block becomes (insert `GitCompare` alphabetically, after `Folder`):

```tsx
import {
  Archive,
  Brain,
  Captions,
  Folder,
  GitCompare,
  Image,
  Key,
  LayoutGrid,
  Mic,
  Palette,
  SlidersHorizontal,
  Sparkles,
  Upload,
  type LucideIcon,
} from "lucide-react";
```

- [ ] **Step 2: Register the section metadata**

In the `SECTIONS` array, add this entry immediately BEFORE the existing `visual-modes` entry (so "Script Types" sorts first in the Reference group):

```tsx
  { id: "script-types", label: "Script Types", description: "Compare every script format — structure, narration rules, and visual-mode compatibility.", icon: GitCompare, group: "Reference" },
```

- [ ] **Step 3: Add the render branch**

In the content area, add a branch immediately before the `visual-modes` branch:

```tsx
          {activeSection === "script-types" && <ScriptTypesSection />}
```

- [ ] **Step 4: Verify type-check and tests**

Run: `cd frontend && npx tsc --noEmit && npx vitest run src/components/settings/script-types`
Expected: no type errors; all script-types tests PASS.

- [ ] **Step 5: Commit**

```bash
git add frontend/src/components/settings/SettingsPage.tsx
git commit -m "Register Script Types reference section in Settings"
```

---

## Task 8: Full verification + push + review loop

**Files:** none (verification only)

- [ ] **Step 1: Run the full backend suite**

Run: `uv run --project backend pytest tests/pipeline/test_formats_registry.py tests/test_formats_endpoint.py -v`
Expected: all PASS.

- [ ] **Step 2: Run the full frontend script-types suite + type-check + build**

Run: `cd frontend && npx tsc --noEmit && npx vitest run src/components/settings/script-types && npm run build`
Expected: type-check clean, tests PASS, production build succeeds.

- [ ] **Step 3: Push to main**

```bash
git push origin main
```

- [ ] **Step 4: Run the mandatory subagent review loop**

Follow the project CLAUDE.md auto-commit rule: dispatch a `superpowers:code-reviewer` Agent reviewing the new commits, apply every FAIL then WARN finding, commit as `fix: address review findings`, and repeat until LGTM. Then surface a single summary.

---

## Self-Review

**Spec coverage:**
- Backend declarative fields (`supported_visual_modes`, `reference_notes`) → Task 1, Task 2. ✓
- `/api/formats` payload widening → Task 3. ✓
- Frontend type → Task 4. ✓
- Matrix + gotchas panel layout → Task 6. ✓
- Mode chips (supported normal, disabled struck-through) + cross-link intent → Task 5 (`hasDetail`) + Task 6 (`Chip`). ✓
- Section registration under Reference → Task 7. ✓
- Backend test (fields serialize + valid modes) → Task 2 + Task 3. ✓
- Frontend test (matrix renders per format, gotchas, disabled chips) → Task 5 + Task 6. ✓
- Reference-only / no enforcement, no dev logging → respected (no enforcement or logging tasks). ✓

**Type consistency:**
- `FormatNote` (Python) ↔ `FormatNote` (TS) ↔ `reference_notes: [{category, text}]` JSON — consistent across Tasks 1, 3, 4.
- `ModeChip { id, label, hasDetail }` defined in Task 5, consumed in Task 6 — consistent.
- `allVisualModes` / `modeChipsForFormat` signatures match between Task 5 impl and Task 6 usage. ✓
- `getFormats()` returns `VideoFormat[]` (existing api.ts) — Task 6 mocks it accordingly. ✓

**Placeholder scan:** No TBD/TODO; every code step shows full content. ✓
