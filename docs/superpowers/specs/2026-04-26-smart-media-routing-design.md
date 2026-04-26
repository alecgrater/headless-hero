# Smart Media Routing — Post-Script Media Analyzer

## Context

The multi-source media system (gameplay clips via Twitch, stock photos via Pexels, AI-generated via Gemini) is already implemented. However, the current UX requires the user to specify game names **before** the script exists. For topics that span multiple games or where specific game references emerge during writing (e.g., "Why the 6th Generation Was the Golden Age of Gaming"), this is backwards — the user can't know which games they need footage for until the script mentions them.

This feature replaces the upfront game-name input with an intelligent post-script analysis step. After the script is generated, Claude analyzes the full script content, identifies every game, real-world entity, and abstract concept per scene, and assigns the optimal media source for each scene. The user reviews and approves the assignments before image generation begins.

**Supersedes:** The prompt-injection approach in `2026-04-25-multi-source-media-design.md` §Script Generation Pipeline. The data model, pipeline dispatch, Remotion rendering, and storage layout from that spec remain unchanged.

## Design Decisions

1. **Fully automatic routing** — Claude decides which scenes get gameplay, stock photos, or AI art based on script content. No manual game-name input required.
2. **Post-script analysis step** — A dedicated pipeline step runs after script generation, separate from both the scriptwriter and image generation. Follows the same pattern as FX generation.
3. **Smart routing across all sources** — The analyzer considers all enabled sources (gameplay, stock photo, AI) holistically, choosing the best visual medium for each scene's content.
4. **Pre-script toggles become opt-in guards** — The Media Sources UI on the script generation page keeps the checkboxes (gated by API keys) but removes the game name input. If neither is checked, the analyzer is skipped entirely.
5. **Review step before image generation** — A new MediaReviewPanel shows the analyzer's assignments with inline editing, so the user can approve or override before committing to image generation.
6. **Timeline overrides preserved** — The existing per-scene media source controls in the timeline properties panel continue to work for post-generation tweaks.

## New Pipeline Step: Media Analyzer

### Module

`backend/pipeline/media_analyzer.py`

### Function Signature

```python
def analyze_media_sources(
    script_content: ScriptContent,
    gameplay_enabled: bool = True,
    stock_photo_enabled: bool = True,
) -> list[MediaAssignment]:
```

### MediaAssignment Schema

```python
@dataclass
class MediaAssignment:
    scene_id: str
    media_source: str  # "ai" | "gameplay_video" | "stock_photo"
    game_name: str | None  # Specific game title for gameplay scenes
    search_query: str | None  # Optimized Pexels search query for stock photo scenes
    reasoning: str  # Brief explanation of why this source was chosen
```

### Claude Prompt

The system prompt tells Claude it is a media routing specialist analyzing a video script. It receives:
- The full script as structured JSON (all scenes with narration, visual prompts, segment titles)
- Which media sources are enabled (`gameplay_enabled`, `stock_photo_enabled`)
- Instructions for when each source is appropriate:
  - **Gameplay video** — When a specific game is being discussed, demonstrated, or referenced. Claude should extract the most specific game name possible (e.g., "Grand Theft Auto III" not "GTA games").
  - **Stock photo** — When real-world objects, events, places, people, or products are discussed. Claude should generate an optimized Pexels search query (e.g., "PlayStation 2 console product photo black background" rather than "PS2").
  - **AI-generated** — When the visual is abstract, metaphorical, stylized, or when no real-world reference exists. Also the fallback when other sources don't fit.
- Instruction to only assign sources that are enabled — if `gameplay_enabled=False`, never assign `"gameplay_video"`
- Instruction to return a JSON array matching the `MediaAssignment` schema

### Response Format

Claude returns a JSON array:
```json
[
  {
    "scene_id": "scene_1",
    "media_source": "stock_photo",
    "game_name": null,
    "search_query": "PlayStation 2 console product photo",
    "reasoning": "Scene discusses the PS2 hardware launch - a real product photo is more compelling than AI art"
  },
  {
    "scene_id": "scene_3",
    "media_source": "gameplay_video",
    "game_name": "Grand Theft Auto III",
    "search_query": null,
    "reasoning": "Scene narrates GTA3's open-world innovation - actual gameplay footage demonstrates the point"
  },
  {
    "scene_id": "scene_5",
    "media_source": "ai",
    "game_name": null,
    "search_query": null,
    "reasoning": "Scene discusses abstract concept of 'innovation in game design' - no specific game or real object to show"
  }
]
```

### How Assignments Are Persisted

The analyzer patches each `Scene` in the `ScriptContent` blob:
- Sets `media_source` field
- Sets `gameplay_game_override` for gameplay scenes (the specific game name)
- For stock photo scenes: stores the optimized search query in `visual_prompt` and preserves the original AI-art prompt in a new `original_visual_prompt` field on Scene
- Saved via existing `PUT /api/scripts/{id}` mechanism

### Model Choice

Uses the same Claude client as FX generation (`backend/integrations/claude_client.py`). The full script context fits easily in a single call. Uses Sonnet for cost efficiency — this is a structured routing task, not creative writing.

## API Endpoint

### `POST /api/media/analyze/{script_id}`

Triggers the media analysis for a given script. Returns the list of `MediaAssignment` objects so the frontend can display the review panel.

**Request body:** None (reads script content from DB)

**Response:**
```json
{
  "assignments": [
    {
      "scene_id": "scene_1",
      "media_source": "stock_photo",
      "game_name": null,
      "search_query": "PlayStation 2 console product photo",
      "reasoning": "Scene discusses the PS2 hardware launch..."
    }
  ],
  "summary": {
    "ai": 7,
    "gameplay_video": 3,
    "stock_photo": 2
  }
}
```

**Side effect:** Patches scene fields on the ScriptContent and persists to DB.

### `POST /api/media/apply/{script_id}`

Applies a (potentially user-modified) set of assignments. The frontend sends back the assignment list after the user has made edits in the review panel.

**Request body:**
```json
{
  "assignments": [
    {
      "scene_id": "scene_1",
      "media_source": "gameplay_video",
      "game_name": "Final Fantasy X",
      "search_query": null
    }
  ]
}
```

**Response:** `{ "ok": true }`

**Side effect:** Patches scene fields and persists.

## Script Generation Page Changes

### Current UI
- Checkbox: "Gameplay clips" (gated by Twitch keys) + game name text input
- Checkbox: "Stock photos" (gated by Pexels key)

### New UI
- Checkbox: "Gameplay clips" (gated by Twitch keys) — **no game name input**
- Checkbox: "Stock photos" (gated by Pexels key)
- Collapsed summary: "AI-generated only" / "AI + Gameplay" / "AI + Stock" / "AI + Gameplay + Stock"

### What Gets Removed
- `gameplay_game_name` field from `GenerateScriptRequest`
- The game name `<input>` in `ScriptGenerationPage.tsx`
- The `gameplay_game_name` parameter from `generate_script()` in `scriptwriter.py`
- The prompt injection in `scriptwriter.py` that tells Claude to assign `media_source` during script generation (lines 148-179) — this responsibility moves to the analyzer

### What Stays
- `gameplay_enabled` and `stock_photo_enabled` flags on `ScriptContent` — these gate whether the analyzer runs
- `gameplay_game_name` field on `ScriptContent` model — deprecated but kept for backward compatibility with existing scripts
- API key gating for checkbox visibility

## Media Review Panel

### Component

`frontend/src/components/timeline/MediaReviewPanel.tsx`

### When It Appears

In the timeline page, after media analysis completes. Renders conditionally when:
1. The script has `gameplay_enabled` or `stock_photo_enabled` set to true
2. Media analysis has been run (assignments exist)
3. Image generation has not yet started

### What It Shows

- **Summary bar** at top: "12 scenes: 7 AI, 3 Gameplay, 2 Stock Photo"
- **Scene list** — each row shows:
  - Scene number + narration snippet (first ~60 chars)
  - Media source badge (color-coded: purple for AI, green for Gameplay, blue for Stock Photo)
  - For gameplay scenes: game name (editable inline text input)
  - For stock photo scenes: search query (editable inline text input)
  - Reasoning as tooltip on hover
  - Dropdown to change media source for any scene
- **Action buttons:**
  - "Approve & Generate Images" — applies assignments and triggers image generation
  - "Re-analyze" — re-runs the analyzer (useful if user edited the script)

### After Approval

The review panel dismisses. Per-scene overrides remain available in the timeline properties panel for later individual changes.

## Integration with Image Generation

### No Changes to Dispatch Logic

`image_gen.py`'s `generate_batch()` already dispatches based on `scene.media_source`:
- `"ai"` → Gemini image generation
- `"gameplay_video"` → Twitch/yt-dlp pipeline
- `"stock_photo"` → Pexels pipeline

This dispatch logic is unchanged. The only difference is that `media_source` is now populated by the post-script analyzer instead of during script generation.

### Gameplay Pipeline

`gameplay.py`'s `generate_gameplay_clip()` already reads `gameplay_game_override` from the scene. The analyzer populates this field with the extracted game name, so the existing code works without modification.

### Stock Photo Pipeline

`stock_photo.py`'s `generate_stock_photo()` already uses `visual_prompt` as the Pexels search query. The analyzer writes an optimized search query into `visual_prompt`, improving search quality without touching this module.

## Data Model Changes

### Scene (backend/models/script.py)

New field:
```python
original_visual_prompt: str = ""  # Preserved AI-art prompt when analyzer overwrites visual_prompt with stock search query
```

All other Scene fields (`media_source`, `gameplay_game_override`, `video_url`, `upload_url`) already exist.

### ScriptContent (backend/models/script.py)

`gameplay_game_name` field is deprecated — kept for backward compatibility but no longer populated by new scripts. The analyzer extracts game names per-scene into `gameplay_game_override` instead.

### GenerateScriptRequest (backend/models/script.py)

Remove `gameplay_game_name` field. Keep `gameplay_enabled` and `stock_photo_enabled`.

## Automatic Triggering

After script generation completes successfully, if `gameplay_enabled` or `stock_photo_enabled` is true on the ScriptContent, the backend automatically triggers the media analyzer as a background job (same threading pattern as render jobs in `render_jobs.py`). The frontend polls `GET /api/media/analyze/status/{job_id}` for completion using the existing `usePollJob` hook.

Flow:
1. Script generation completes → script saved to DB
2. Backend checks `gameplay_enabled` or `stock_photo_enabled` → if either is true, spawns background thread running `analyze_media_sources()`
3. Frontend receives script generation response with `media_analysis_job_id` → starts polling
4. Analysis completes → frontend receives assignments → shows MediaReviewPanel
5. User reviews/edits → clicks "Approve & Generate Images"
6. Frontend calls `POST /api/media/apply/{script_id}` with final assignments → triggers image generation

## Files Changed

| File | Change |
|------|--------|
| `backend/pipeline/media_analyzer.py` | **New** — Claude-powered media source analyzer |
| `backend/api/media.py` | **New** — `POST /api/media/analyze/{script_id}` and `POST /api/media/apply/{script_id}` endpoints |
| `backend/api/__init__.py` | Register media router |
| `backend/models/script.py` | Add `original_visual_prompt` to Scene; remove `gameplay_game_name` from `GenerateScriptRequest` |
| `backend/pipeline/scriptwriter.py` | Remove media source prompt injection (lines 148-179); remove `gameplay_game_name` parameter |
| `backend/api/scripts.py` | Remove `gameplay_game_name` from generate endpoint; trigger analyzer after script gen |
| `frontend/src/components/script/ScriptGenerationPage.tsx` | Remove game name input; simplify Media Sources section |
| `frontend/src/components/script/useScriptGeneration.ts` | Remove `gameplayGameName` state; remove from API call |
| `frontend/src/components/timeline/MediaReviewPanel.tsx` | **New** — Review panel component |
| `frontend/src/components/timeline/TimelinePage.tsx` | Integrate MediaReviewPanel conditionally |
| `frontend/src/types/script.ts` | Add `original_visual_prompt` to Scene interface |
| `frontend/src/api.ts` | Add `analyzeMedia()` and `applyMediaAssignments()` functions |

## Verification

1. **Script gen page:** Verify game name input is removed. Toggles still appear when API keys configured.
2. **Analyzer runs:** Generate a script about gaming with gameplay enabled → verify analyzer runs automatically after script gen completes.
3. **Assignments quality:** Check that Claude correctly identifies games, chooses stock photos for real-world subjects, and falls back to AI art for abstract concepts.
4. **Review panel:** Verify panel appears in timeline with correct assignments, badges, game names, search queries.
5. **Inline editing:** Change a scene's source in the review panel → verify it persists when approved.
6. **Approve flow:** Click "Approve & Generate Images" → verify image generation dispatches correctly per source type.
7. **Re-analyze:** Edit the script text → click "Re-analyze" → verify fresh analysis reflects changes.
8. **Timeline override:** After approval, change a scene's source in properties panel → regenerate → verify correct pipeline runs.
9. **Backward compat:** Open an existing script with `gameplay_game_name` set → verify it still works (game name shown but field is read-only/deprecated).
10. **AI-only mode:** Generate a script with both toggles off → verify no analyzer runs, all scenes get AI art, no review panel appears.
