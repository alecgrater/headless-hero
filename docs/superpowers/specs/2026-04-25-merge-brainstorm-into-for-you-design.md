# Merge Brainstorm into For You — Design Spec

**Date:** 2026-04-25

## Goal

Combine the brainstorm feature (niche prompt generation with 5 strategies) and the For You smart ideas feature (personalized video ideas from profile + trending) into a single "Generate Ideas" button on the Discover / For You page. Remove the Brainstorm nav entry. Reorder tabs so For You comes before Trending.

## Current State

- **Brainstorm** (`POST /api/brainstorm/generate`): Takes script titles + trending topics, uses 5 strategies (trending overlap, adjacent niches, evergreen deep-dives, counter-intuitive angles, gap-filling) to generate 8 abstract niche prompts. Works with zero scripts. 1 Claude call.
- **For You** (`POST /api/trending/smart-ideas`): Takes content profile + trending topics, generates 10 concrete video ideas with titles, descriptions, keywords, match scores. Requires 3+ scripts for content profile. 1-2 Claude calls.

## Design

### 1. Merged Prompt (`SMART_IDEATION_SYSTEM`)

Rewrite to incorporate brainstorm's 5 strategies as idea generation instructions. The prompt operates in two modes:

**With profile** (3+ scripts): Full context — profile topics, narration style, visual approach, audience, keywords, plus trending data. Outputs include `style_match_score` and `signals`.

**Without profile** (<3 scripts): Lighter context — just script titles (if any) and trending data. The prompt still applies all 5 strategies but skips style-matching. `style_match_score` is `null`, `signals` still populated.

### 2. Pipeline Changes (`smart_ideation.py`)

`generate_smart_ideas()` signature changes:

```python
def generate_smart_ideas(
    trending_topics: list[dict],
    count: int = 10,
    profile: dict | None = None,
    script_titles: list[str] | None = None,
) -> list[dict]:
```

- When `profile` is provided: builds full context (current behavior + strategies)
- When `profile` is `None`: builds lighter context from `script_titles` + trending only
- Both paths use the same merged prompt

### 3. API Endpoint Changes (`api/trending.py`)

`POST /api/trending/smart-ideas`:

- Drop the 3-script gate (`HTTPException 422`)
- Try to load cached profile; if stale, refresh it
- If no profile or not enough scripts for profile: load script titles instead, pass `profile=None`
- Always load trending topics (unchanged)
- Pass whichever context is available to the pipeline

### 4. SmartIdea Model Changes (`api/trending.py`)

```python
class SmartIdea(BaseModel):
    title: str
    description: str
    segments_est: int
    keywords: list[str]
    trending_source: str
    style_match_score: float | None = None  # null when no profile
    reasoning: str
    angle: str
    signals: list[str] = []  # data source citations (from brainstorm)
```

`SmartIdeasResponse` stays the same but `profile_used` will be `False` when no profile.

### 5. Frontend: ForYouTab

- Remove gated state (the `if (gated)` block)
- Remove "no profile yet — offer to analyze" state
- ContentProfileCard: only render when `profile` is non-null
- Generate button always visible and functional
- Empty state text: "Hit 'Generate Ideas' to get AI-powered video suggestions based on trending data"
- SmartIdeaCard: hide `StyleMatchBadge` when `style_match_score` is `null`; show `signals` as chips when present

### 6. Frontend: DiscoverPage

- Default `activeTab`: `"for-you"` (was `"trending"`)
- Tab button order: For You first (left), Trending second (right)

### 7. Frontend: App.tsx — Remove Brainstorm Nav

- Remove `"brainstorm"` from `View` type union
- Remove Brainstorm nav button from sidebar
- Remove `{view === "brainstorm" && <BrainstormPage ... />}` render case
- Keep `BrainstormPage`, `BrainstormCard` files (dead code, clean up later)

### 8. Types

`frontend/src/types/trending.ts` — update `SmartIdea` interface:
- `style_match_score: number | null`
- Add `signals: string[]`

## Files Changed

### Backend
- `backend/prompts.py` — Rewrite `SMART_IDEATION_SYSTEM` template to include 5 brainstorm strategies
- `backend/pipeline/smart_ideation.py` — Make `profile` optional, accept `script_titles`, build context for both modes
- `backend/api/trending.py` — Drop 3-script gate, load script titles as fallback, update `SmartIdea` model

### Frontend
- `frontend/src/components/trending/DiscoverPage.tsx` — Swap tab order, default to for-you
- `frontend/src/components/trending/ForYouTab.tsx` — Remove gated/setup states, conditional profile card
- `frontend/src/components/trending/SmartIdeaCard.tsx` — Handle null match score, render signals
- `frontend/src/types/trending.ts` — Update SmartIdea type
- `frontend/src/App.tsx` — Remove brainstorm nav + view

### Not Changed (dead code, cleanup later)
- `backend/api/brainstorm.py`
- `backend/pipeline/brainstorm.py`
- `backend/prompts.py` `BRAINSTORM_SYSTEM` (kept, just unused)
- `frontend/src/components/brainstorm/BrainstormPage.tsx`
- `frontend/src/components/brainstorm/BrainstormCard.tsx`
- `frontend/src/types/brainstorm.ts`
