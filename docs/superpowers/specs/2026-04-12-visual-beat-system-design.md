# Visual Beat System — Design Spec

## Context

The current multi-frame image generation system produces frames that are far too visually similar. The root cause: reference-image chaining tells Gemini to "change ONLY the following" from the previous frame, resulting in near-identical compositions even when the narration calls for completely different shots.

Beyond similarity, the system lacks visual vocabulary. Real YouTube editors use a mix of techniques — hard cuts between different shots, full-screen text cards for dramatic reveals, montages mixing real footage with illustrations, and smooth animation only where motion genuinely matters. Currently the system has two modes: single static image or multi-frame crossfade. This limits retention and engagement.

This overhaul introduces a **Visual Beat System** that gives the scriptwriter AI a rich vocabulary of visual presentation techniques, structured per-frame control over image source and transitions, and a new Google Images scraping pipeline for real-world photography.

## Goals

- Eliminate the "too similar frames" problem by giving each beat type appropriate generation strategy
- Introduce 5 distinct visual beat types that map to real YouTube editing techniques
- Add real photo scraping from Google Images as a frame source
- Add full-screen subtitle scenes for "aha moment" reveals
- Give the AI per-frame control over transitions (hard cut, crossfade, fade-to-black)
- Distribute beat types evenly across videos for maximum viewer retention
- Maintain full backwards compatibility with existing scripts

## Non-Goals

- Manual per-scene beat type selection in the timeline UI (fully AI-driven for now)
- Video clip scraping (only still photos from Google Images)
- New Remotion scene components beyond extending MultiFrameScene + adding SubtitleScene

---

## Data Model

### New: `FrameDirective` (Pydantic model in `backend/models/script.py`)

```python
class FrameDirective(BaseModel):
    prompt: str                        # Visual description OR subtitle text
    source: str = "ai_generated"       # "ai_generated" | "real_photo" | "subtitle"
    search_query: str = ""             # Google Images query (for real_photo source)
    transition: str = "crossfade"      # "cut" | "crossfade" | "fade_black"
    reference_previous: bool = True    # Whether to use previous frame as Gemini reference
```

### New Scene fields (added to `Scene` in `backend/models/script.py`)

```python
visual_beat: str = "static"            # "static" | "continuous" | "quick_cuts" | "aha_subtitle" | "montage"
frame_directives: list[dict] = []      # List of FrameDirective dicts in JSON blob; validated via FrameDirective(**d) at runtime
```

### Beat Type Definitions

| Beat | Description | Frame count | Reference chaining | Transitions | Image source |
|------|-------------|-------------|-------------------|-------------|--------------|
| `static` | Single image with gentle zoom | 1 | N/A | N/A | ai_generated |
| `continuous` | Subtle motion progression across frames | 2-4 | Yes (`reference_previous: true`) | crossfade | ai_generated |
| `quick_cuts` | Independent shots, maximum visual variety | 3-8 | No (`reference_previous: false`) | cut (primarily) | ai_generated |
| `aha_subtitle` | Full-screen text on black, no image | 1 | N/A | fade_black | subtitle |
| `montage` | Mix of AI art and real photos, rapid succession | 4-8 | No | cut / crossfade mix | ai_generated + real_photo |

### Backwards Compatibility

- `frame_directives: []` + `visual_beat: "static"` = current single-image behavior
- Pipeline checks for `frame_directives` first; if empty, falls back to legacy `frame_prompts`
- Old scripts with `frame_prompts` continue to work unchanged

---

## Scriptwriter Prompt Changes

**File:** `backend/pipeline/scriptwriter.py`

The existing multi-frame guidelines section is replaced with a Visual Beat System section. Key additions to the prompt:

### Beat Type Vocabulary

The scriptwriter learns when to use each beat type:

- **`static`** — Standard explanation scenes where a single strong image suffices. Default fallback. Aim for <30% of non-title-card scenes.
- **`continuous`** — When narration describes a physical process that unfolds over time (pouring, growing, building). Frames show subtle progression. 2-4 frames with `reference_previous: true`.
- **`quick_cuts`** — When narration covers multiple examples, lists, comparisons, or rapid context switches. Each frame is a completely different shot — different subject, angle, composition. 3-8 frames with `reference_previous: false`. This is the primary tool for visual energy.
- **`aha_subtitle`** — When a sentence delivers a shocking stat, counterintuitive fact, or "wait, really?" moment. Pure white text on black. Aim for 5-6 per video, no more than 7. Must be preceded and followed by image-bearing beats for contrast.
- **`montage`** — When real-world authenticity adds impact (real places, real products, real events). Mix of `ai_generated` and `real_photo` sources. 4-8 frames. Each `real_photo` frame includes a `search_query` for Google Images.

### Distribution Rules

Enforced via the prompt:

1. Never use the same beat type 3+ times consecutively
2. `quick_cuts` + `montage` should comprise 30-50% of non-title-card scenes
3. `aha_subtitle` must be sandwiched between image-bearing beats
4. `continuous` reserved for genuine motion progression — not the default for multi-frame
5. `static` is the minority, not the majority
6. Vary transitions within quick_cuts scenes — mostly `cut` but occasional `crossfade` to avoid monotony

### Output Format

The scriptwriter outputs `frame_directives` (list of FrameDirective objects) instead of `frame_prompts` for each scene. The `visual_prompt` field remains as the anchor description. Examples:

**Quick cuts:**
```json
{
  "visual_beat": "quick_cuts",
  "visual_prompt": "[CLOSE-UP] A child reaching for a coffee mug",
  "frame_directives": [
    {"prompt": "[CLOSE-UP] A child's small hand reaching toward a steaming coffee mug on a kitchen counter", "source": "ai_generated", "transition": "cut", "reference_previous": false},
    {"prompt": "[REACTION] A parent's alarmed face, eyes wide, mouth open mid-shout", "source": "ai_generated", "transition": "cut", "reference_previous": false},
    {"prompt": "[DETAIL] Parent's hand firmly gripping the mug handle, pulling it away", "source": "ai_generated", "transition": "cut", "reference_previous": false}
  ]
}
```

**Aha subtitle:**
```json
{
  "visual_beat": "aha_subtitle",
  "visual_prompt": "",
  "frame_directives": [
    {"prompt": "A single cup of coffee contains enough caffeine to kill a small bird.", "source": "subtitle", "transition": "fade_black"}
  ]
}
```

**Montage (mixed sources):**
```json
{
  "visual_beat": "montage",
  "visual_prompt": "[ESTABLISHING] Coffee farms around the world",
  "frame_directives": [
    {"prompt": "Aerial view of lush green coffee plantation in Colombia", "source": "real_photo", "search_query": "coffee plantation aerial Colombia", "transition": "cut", "reference_previous": false},
    {"prompt": "[DETAIL] Ripe red coffee cherries on a branch with morning dew", "source": "ai_generated", "transition": "cut", "reference_previous": false},
    {"prompt": "Workers hand-picking coffee beans in Ethiopia", "source": "real_photo", "search_query": "coffee harvesting Ethiopia workers", "transition": "cut", "reference_previous": false},
    {"prompt": "[CLOSE-UP] Roasted beans tumbling in an industrial roaster", "source": "ai_generated", "transition": "crossfade", "reference_previous": false}
  ]
}
```

**Continuous (motion progression):**
```json
{
  "visual_beat": "continuous",
  "visual_prompt": "[CLOSE-UP] A coffee plant seedling pushing through dark soil",
  "frame_directives": [
    {"prompt": "Tiny green shoot barely breaking the soil surface", "source": "ai_generated", "transition": "crossfade", "reference_previous": false},
    {"prompt": "Seedling now 2 inches tall with first pair of leaves unfurling", "source": "ai_generated", "transition": "crossfade", "reference_previous": true},
    {"prompt": "Young plant with 4 leaves and visible stem, soil cracked around base", "source": "ai_generated", "transition": "crossfade", "reference_previous": true}
  ]
}
```

### Monotony Warning Update

The existing `_warn_visual_monotony()` function is extended to also warn on 3+ consecutive identical `visual_beat` types, not just shot types.

---

## Image Generation Pipeline

**File:** `backend/pipeline/image_gen.py`

### Refactored `generate_scene_frames`

The function is updated to dispatch per-directive based on `source` and `reference_previous`:

```
For each FrameDirective in scene.frame_directives:

  if directive.source == "ai_generated":
    if directive.reference_previous AND previous_frame_path exists:
      → Gemini image-to-image with previous frame as reference (current behavior)
    else:
      → Gemini text-to-image with full prompt (independent generation)

  elif directive.source == "real_photo":
    → Call Google Images scraper with directive.search_query
    → Download top result, resize/crop to 1920x1080
    → On failure: fall back to Gemini text-to-image using search_query as prompt

  elif directive.source == "subtitle":
    → Skip image generation entirely
    → Store empty string in frame_urls slot (Remotion handles rendering)
```

### Key behavioral change

The "too similar" problem is solved by `reference_previous: false` on quick_cuts and montage frames. Each frame gets independent text-to-image generation with its own unique prompt — completely different compositions.

### Fallback path

If `frame_directives` is empty but `frame_prompts` is not, the legacy code path runs unchanged. This preserves old script compatibility.

---

## Google Images Scraper

**New file:** `backend/integrations/google_image_scraper.py`

### Interface

```python
async def scrape_google_image(
    query: str,
    output_path: str,
    width: int = 1920,
    height: int = 1080,
) -> str | None:
    """
    Search Google Images, download top result, resize to target dimensions.
    Returns output_path on success, None on failure.
    """
```

### Implementation

1. Build Google Images search URL with query
2. HTTP GET with browser-like User-Agent via httpx
3. Parse image URLs from response HTML
4. Download the highest-resolution candidate
5. Resize and center-crop to 1920x1080 using Pillow
6. Save to `output_path`
7. Return path on success, `None` on failure

### Fallback

When scraping fails (blocked, no results, download error), the caller (`image_gen.py`) falls back to Gemini text-to-image generation using the `search_query` as the prompt. Real photo frames never break the pipeline.

### Caching

Same `.prompt` marker file pattern as AI-generated images. The marker stores the search query — if unchanged, skip re-scraping.

---

## Remotion Rendering Changes

### Type definitions (`remotion/src/types.ts`)

```typescript
interface FrameDirective {
  prompt: string;
  source: "ai_generated" | "real_photo" | "subtitle";
  transition: "cut" | "crossfade" | "fade_black";
  reference_previous: boolean;
}

// Added to SceneInput:
visual_beat: "static" | "continuous" | "quick_cuts" | "aha_subtitle" | "montage";
frame_directives: FrameDirective[];
```

### Scene dispatch (`remotion/src/scenes/SceneRenderer.tsx`)

Updated priority order:

1. `isVideoClip` → `VideoClipScene`
2. `isTitleCard` → `TitleCardScene`
3. `visual_beat === "aha_subtitle"` → **`SubtitleScene`** (new)
4. `hasMultipleFrames` → `MultiFrameScene` (updated)
5. Default → `StaticImageScene`

### New: `SubtitleScene` (`remotion/src/scenes/SubtitleScene.tsx`)

- Pure black background (`#000000`)
- White text, large and centered (72-96px depending on text length)
- Spring-animated pop-in effect (scale from 0.8 to 1.0 with overshoot)
- Optional word-by-word reveal synced to audio timestamps if available
- Full scene duration — text appears and holds

### Updated: `MultiFrameScene` (`remotion/src/scenes/MultiFrameScene.tsx`)

Per-frame transition support replacing the hardcoded 12-frame crossfade:

| Transition | Behavior |
|-----------|----------|
| `"cut"` | Instant switch (0 transition frames) |
| `"crossfade"` | Current 12-frame opacity interpolation |
| `"fade_black"` | 6-frame fade out → 3-frame black hold → 6-frame fade in |

The component reads `frame_directives[i].transition` to determine how to transition into each frame. If no directives exist (legacy), defaults to `"crossfade"` for all frames.

Subtitle frames within a multi-frame scene (if `source === "subtitle"`) render text-on-black instead of loading an image path.

### Data bridge (`backend/pipeline/remotion_render.py`)

- `visual_beat` mapped directly to Remotion props
- `frame_directives` serialized alongside `frame_paths` — each frame path paired with its directive metadata
- Subtitle frames: no file path resolved, `prompt` text passed through for rendering

---

## FX Integration

**File:** `backend/pipeline/fx_generator.py`

Beat type is included in the scene context sent to Claude for FX assignment:

- **`aha_subtitle`** scenes: No `zoom_punch` (no image to zoom). Kinetic captions still generated — the subtitle text itself benefits from emphasis styling.
- **`quick_cuts`** scenes: `zoom_punch` can trigger on one cut frame for extra impact. Kinetic captions applied normally.
- **`montage`** scenes: Standard FX rules. `zoom_punch` works on any frame.
- **`continuous`** scenes: Standard FX rules.
- **`static`** scenes: Standard FX rules.

The FX prompt context for each scene includes `"visual_beat": "{beat_type}"` so Claude can make informed FX decisions.

---

## Files Modified

| File | Change |
|------|--------|
| `backend/models/script.py` | Add `FrameDirective` model, add `visual_beat` and `frame_directives` to `Scene` |
| `backend/pipeline/scriptwriter.py` | Replace multi-frame guidelines with Visual Beat System prompt section |
| `backend/pipeline/image_gen.py` | Refactor `generate_scene_frames` to dispatch per-directive |
| `backend/integrations/google_image_scraper.py` | **New file** — Google Images search + download |
| `backend/pipeline/remotion_render.py` | Map new fields to Remotion props |
| `backend/pipeline/fx_generator.py` | Add beat type to scene context |
| `backend/api/visuals.py` | Accept `frame_directives` in request, pass to pipeline |
| `remotion/src/types.ts` | Add `FrameDirective` type, new scene fields |
| `remotion/src/scenes/SceneRenderer.tsx` | Add `aha_subtitle` → `SubtitleScene` dispatch |
| `remotion/src/scenes/SubtitleScene.tsx` | **New file** — text-on-black scene renderer |
| `remotion/src/scenes/MultiFrameScene.tsx` | Per-frame transition support, subtitle frame rendering |

---

## Verification Plan

1. **Script generation** — Generate a test script via `npm run dev` + UI. Verify JSON contains varied `visual_beat` types and structured `frame_directives`. Check distribution: no 3+ consecutive same beats, quick_cuts/montage at 30-50%.

2. **Image generation** — Generate visuals for the test script. Verify:
   - Quick-cut frames are visually distinct (completely different compositions)
   - Continuous frames still show subtle progression via reference chaining
   - Real photo frames download from Google Images successfully
   - Subtitle frames skip image generation (no Gemini calls)
   - Fallback works: if Google Images fails, Gemini generates instead

3. **Scene preview** — Render a preview for each beat type:
   - `static`: single image with gentle zoom
   - `continuous`: smooth crossfade between similar frames
   - `quick_cuts`: hard cuts between distinct images
   - `aha_subtitle`: white text on black with pop-in animation
   - `montage`: rapid mix of real photos and AI art

4. **Full video render** — Render a complete video and verify:
   - Visual variety feels engaging across the whole video
   - Transitions match directives (cuts are instant, crossfades are smooth, fade_black works)
   - No regression in existing features (FX, Eli overlay, audio sync, title cards)

5. **Backwards compatibility** — Load an existing script (no `frame_directives`). Verify it renders identically to before the changes.
