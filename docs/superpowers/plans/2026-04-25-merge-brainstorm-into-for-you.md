# Merge Brainstorm into For You — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Combine brainstorm's 5-strategy niche generation with For You's personalized idea pipeline into a single "Generate Ideas" flow, remove the 3-script gate, reorder Discover tabs, and remove the Brainstorm nav entry.

**Architecture:** Merge the brainstorm prompt strategies into `SMART_IDEATION_SYSTEM`, make the pipeline work with or without a content profile, update the frontend to remove gating and brainstorm nav. One merged Claude call produces concrete `SmartIdea` objects using all 5 brainstorm strategies.

**Tech Stack:** Python/FastAPI backend, React/TypeScript frontend, Claude API for idea generation

---

## File Structure

| File | Action | Responsibility |
|------|--------|----------------|
| `backend/prompts.py` | Modify (lines 1447-1478) | Rewrite `SMART_IDEATION_SYSTEM` prompt with 5 strategies |
| `backend/pipeline/smart_ideation.py` | Modify | Make profile optional, accept script_titles fallback |
| `backend/api/trending.py` | Modify | Drop 3-script gate, load titles as fallback, update SmartIdea model |
| `frontend/src/types/trending.ts` | Modify | `style_match_score: number \| null`, add `signals: string[]` |
| `frontend/src/components/trending/SmartIdeaCard.tsx` | Modify | Handle null match score, render signals chips |
| `frontend/src/components/trending/ForYouTab.tsx` | Modify | Remove gated/setup states, conditional profile card |
| `frontend/src/components/trending/DiscoverPage.tsx` | Modify | Swap tab order, default to for-you |
| `frontend/src/App.tsx` | Modify | Remove brainstorm nav + view |

---

### Task 1: Rewrite SMART_IDEATION_SYSTEM prompt

**Files:**
- Modify: `backend/prompts.py:1447-1478`

- [ ] **Step 1: Replace the SMART_IDEATION_SYSTEM prompt definition**

Replace lines 1447-1478 in `backend/prompts.py` with:

```python
SMART_IDEATION_SYSTEM = register(PromptDef(
    name="SMART_IDEATION_SYSTEM",
    domain="IDEATION",
    purpose="Generate personalized video ideas from trending data, optional creator profile, and 5 brainstorm strategies",
    target_model="claude",
    expected_output_format="JSON array: [{title, description, segments_est, keywords, trending_source, style_match_score, reasoning, angle, signals}]",
    template="""\
You are a YouTube content strategist generating specific, actionable video ideas.

You will receive:
1. Current trending topics from multiple sources (Hacker News, Wikipedia, Reddit, YouTube, news, etc.)
2. Optionally: a creator's content profile (style, topics, audience) OR just their past video titles
3. A requested idea count

Apply ALL of these strategies to generate a diverse set of ideas:
- **Trending + Expertise overlap**: Topics the creator has covered (or would cover) that are currently trending
- **Adjacent niches**: Topics close to but distinct from their usual content, riding a trend
- **Evergreen deep-dives**: Perennially searchable topics in their domain that haven't been covered
- **Counter-intuitive angles**: Surprising takes on familiar topics that generate curiosity clicks
- **Gap-filling**: Topics their audience would expect but that are missing from their catalog

If a creator profile is provided, blend ideas with their established style so each idea feels natural \
for their audience. If only past video titles are provided (or nothing), focus on trending data and \
the strategies above to generate broadly appealing educational content ideas.

For each idea return a JSON object with these exact fields:
- title: compelling YouTube title (50-70 chars)
- description: 2-3 sentence video description
- segments_est: estimated segment count (8)
- keywords: list of 3-5 SEO keywords
- trending_source: which trending topic(s) inspired this idea
- style_match_score: 0-100 how well this fits the creator's style (null if no profile provided)
- reasoning: 1-2 sentences on why this suits the audience
- angle: the unique hook or perspective
- signals: list of 1-3 source citations (e.g. "trending on YouTube", "evergreen search volume", "gap in catalog", "adjacent to past content")

Return ONLY a JSON array of objects — no markdown fences, no commentary.
""",
    retention=RetentionMeta(
        goal="Surface high-potential video topics at the intersection of creator expertise and audience demand",
        failure_mode="Generic ideas that don't leverage creator history or current trends; forced trending overlaps",
        metrics_to_watch=["impressions", "search_ranking", "click_through_rate"],
    ),
))
```

- [ ] **Step 2: Verify the prompt file is valid Python**

Run: `cd ~/git/headless-hero && uv run python -c "import prompts; print('OK')"`
Expected: `OK`

- [ ] **Step 3: Commit**

```bash
git add backend/prompts.py
git commit -m "Rewrite SMART_IDEATION_SYSTEM prompt with 5 brainstorm strategies"
```

---

### Task 2: Update smart_ideation pipeline to support profile-less mode

**Files:**
- Modify: `backend/pipeline/smart_ideation.py`

- [ ] **Step 1: Rewrite generate_smart_ideas to accept optional profile and script_titles**

Replace the entire contents of `backend/pipeline/smart_ideation.py` with:

```python
"""Smart ideation pipeline — generates video ideas from trending data + optional profile."""

import json
import logging

from config import strip_markdown_fences
from integrations.claude_client import chat
from prompts import SMART_IDEATION_SYSTEM

logger = logging.getLogger(__name__)


def generate_smart_ideas(
    trending_topics: list[dict],
    count: int = 10,
    profile: dict | None = None,
    script_titles: list[str] | None = None,
) -> list[dict]:
    """Generate video ideas combining trending data with optional creator context.

    When profile is provided, full personalization is applied.
    When only script_titles are provided, lighter context is used.
    When neither is provided, ideas are based purely on trending data + strategies.
    """
    if not trending_topics:
        return []

    trending_context = [
        {
            "title": t["title"],
            "source": t["source"],
            "score": t.get("score", 0),
            "evidence": t.get("evidence", ""),
            "breakout": t.get("is_breakout", False),
        }
        for t in trending_topics[:20]
    ]

    has_profile = profile is not None

    if has_profile:
        creator_context = {
            "creator_profile": {
                "common_topics": profile.get("common_topics", []),
                "narration_style": profile.get("narration_style", ""),
                "visual_approach": profile.get("visual_approach", ""),
                "audience_profile": profile.get("audience_profile", ""),
                "typical_keywords": profile.get("typical_keywords", []),
                "avg_segments": profile.get("avg_segment_count", 8),
            },
        }
    elif script_titles:
        creator_context = {
            "past_video_titles": script_titles,
        }
    else:
        creator_context = {}

    user_msg = json.dumps({
        **creator_context,
        "trending_topics": trending_context,
        "count": count,
    }, indent=2)

    logger.info(
        "Generating %d ideas (profile=%s, titles=%d, trending=%d)",
        count,
        "yes" if has_profile else "no",
        len(script_titles or []),
        len(trending_context),
    )

    raw = chat(
        SMART_IDEATION_SYSTEM.template,
        f"Generate {count} video ideas:\n{user_msg}",
        max_tokens=4096,
    )

    try:
        ideas = json.loads(strip_markdown_fences(raw))
    except json.JSONDecodeError:
        logger.error("Failed to parse smart ideas response")
        return []

    validated = []
    for idea in ideas:
        score_raw = idea.get("style_match_score")
        style_match_score = (
            max(0, min(100, float(score_raw)))
            if score_raw is not None and has_profile
            else None
        )

        validated.append({
            "title": idea.get("title", "Untitled"),
            "description": idea.get("description", ""),
            "segments_est": idea.get("segments_est", 8),
            "keywords": idea.get("keywords", [])[:5],
            "trending_source": idea.get("trending_source", ""),
            "style_match_score": style_match_score,
            "reasoning": idea.get("reasoning", ""),
            "angle": idea.get("angle", ""),
            "signals": idea.get("signals", [])[:3],
        })

    logger.info("Generated %d ideas", len(validated))
    return validated[:count]
```

- [ ] **Step 2: Verify the module imports cleanly**

Run: `cd ~/git/headless-hero && uv run python -c "from pipeline.smart_ideation import generate_smart_ideas; print('OK')"`
Expected: `OK`

- [ ] **Step 3: Commit**

```bash
git add backend/pipeline/smart_ideation.py
git commit -m "Update smart ideation pipeline to work with or without content profile"
```

---

### Task 3: Update API endpoint and SmartIdea model

**Files:**
- Modify: `backend/api/trending.py:56-70` (SmartIdea model), `backend/api/trending.py:210-253` (endpoint)

- [ ] **Step 1: Update the SmartIdea model**

In `backend/api/trending.py`, replace the `SmartIdea` class (lines 57-66):

```python
class SmartIdea(BaseModel):
    title: str
    description: str
    segments_est: int
    keywords: list[str]
    trending_source: str
    style_match_score: float | None = None
    reasoning: str
    angle: str
    signals: list[str] = []
```

- [ ] **Step 2: Rewrite the smart-ideas endpoint to drop the 3-script gate**

In `backend/api/trending.py`, replace the `generate_smart_ideas` endpoint function (lines 211-253) with:

```python
@router.post("/smart-ideas", response_model=SmartIdeasResponse)
async def generate_smart_ideas(
    body: SmartIdeasRequest,
    session: Session = Depends(get_session),
):
    """Generate video ideas combining trending topics with optional content profile."""
    from pipeline.content_profile import get_cached_profile, analyze_content_profile
    from pipeline.smart_ideation import generate_smart_ideas as _generate

    # Try to load profile — but don't require it
    profile = None
    script_titles: list[str] = []

    cached = get_cached_profile()
    if cached and cached.get("script_count", 0) >= 3:
        if cached.get("is_stale"):
            profile = analyze_content_profile() or None
        else:
            profile = cached
    else:
        # No profile or not enough scripts — fall back to titles
        scripts = session.exec(select(Script)).all()
        script_titles = [s.topic_title for s in scripts if s.topic_title]

    # Load top trending topics
    stmt = select(TrendingTopic).where(
        TrendingTopic.status == "new"
    ).order_by(TrendingTopic.score.desc()).limit(20)
    topics = session.exec(stmt).all()

    trending_data = [
        {
            "title": t.title,
            "source": t.source,
            "score": t.score,
            "evidence": t.evidence_snippet,
            "is_breakout": t.is_breakout,
        }
        for t in topics
    ]

    ideas = _generate(
        trending_topics=trending_data,
        count=body.count,
        profile=profile,
        script_titles=script_titles if not profile else None,
    )

    return SmartIdeasResponse(
        ideas=[SmartIdea(**idea) for idea in ideas],
        profile_used=profile is not None,
        trending_topics_used=len(trending_data),
    )
```

- [ ] **Step 3: Add the missing Script import at the top of the file**

In `backend/api/trending.py`, update the import from `models.script` (add it near line 9 with the other imports):

```python
from models.script import Script
```

- [ ] **Step 4: Verify endpoint module loads**

Run: `cd ~/git/headless-hero && uv run python -c "from api.trending import router; print('OK')"`
Expected: `OK`

- [ ] **Step 5: Commit**

```bash
git add backend/api/trending.py
git commit -m "Drop 3-script gate from smart ideas endpoint, add signals field"
```

---

### Task 4: Update frontend SmartIdea type

**Files:**
- Modify: `frontend/src/types/trending.ts:40-49`

- [ ] **Step 1: Update the SmartIdea interface**

In `frontend/src/types/trending.ts`, replace the `SmartIdea` interface (lines 40-49):

```typescript
export interface SmartIdea {
  title: string;
  description: string;
  segments_est: number;
  keywords: string[];
  trending_source: string;
  style_match_score: number | null;
  reasoning: string;
  angle: string;
  signals: string[];
}
```

- [ ] **Step 2: Commit**

```bash
git add frontend/src/types/trending.ts
git commit -m "Update SmartIdea type with nullable style_match_score and signals"
```

---

### Task 5: Update SmartIdeaCard to handle null score and show signals

**Files:**
- Modify: `frontend/src/components/trending/SmartIdeaCard.tsx`

- [ ] **Step 1: Update StyleMatchBadge to handle null**

In `frontend/src/components/trending/SmartIdeaCard.tsx`, the `StyleMatchBadge` component (lines 11-27) stays as-is — it only renders when score is non-null. The change is in how it's called.

- [ ] **Step 2: Update the SmartIdeaCard component to conditionally render the badge and show signals**

Replace the `SmartIdeaCard` component body (lines 62-158) with:

```tsx
export default function SmartIdeaCard({ idea, index, onUseIdea, onDismiss }: Props) {
  const [expanded, setExpanded] = useState(false);
  const hasDetails = idea.keywords.length > 0 || idea.trending_source || idea.reasoning || idea.angle || idea.signals.length > 0;

  return (
    <div
      className="group relative bg-neutral-800/50 border border-neutral-700/60 rounded-xl p-3 hover:border-neutral-600/80 hover:bg-neutral-800/70 transition-all duration-200"
      style={{
        animation: "fadeSlideUp 0.35s ease-out both",
        animationDelay: `${index * 60}ms`,
      }}
    >
      <div
        className={`flex gap-3 ${hasDetails ? "cursor-pointer" : ""}`}
        onClick={() => hasDetails && setExpanded(!expanded)}
      >
        {/* Style match badge — only when profile-based score exists */}
        {idea.style_match_score != null && (
          <div className="shrink-0">
            <StyleMatchBadge score={idea.style_match_score} />
          </div>
        )}

        {/* Content */}
        <div className="flex-1 min-w-0 space-y-1">
          {/* Title row with inline actions */}
          <div className="flex items-start gap-2">
            <h3 className="flex-1 text-[15px] font-semibold text-neutral-100 leading-snug">
              {idea.title}
              {hasDetails && (
                <svg
                  className={`inline-block ml-1.5 w-3.5 h-3.5 text-neutral-500 transition-transform duration-200 ${expanded ? "rotate-180" : ""}`}
                  fill="none"
                  viewBox="0 0 24 24"
                  stroke="currentColor"
                  strokeWidth={2}
                >
                  <path strokeLinecap="round" strokeLinejoin="round" d="M19 9l-7 7-7-7" />
                </svg>
              )}
            </h3>
            <div className="flex items-center gap-1.5 shrink-0">
              <button
                onClick={(e) => { e.stopPropagation(); onUseIdea(idea); }}
                className="text-xs px-3 py-1 rounded-lg font-medium bg-violet-600 hover:bg-violet-500 text-white transition-colors"
              >
                Use Idea →
              </button>
              <button
                onClick={(e) => { e.stopPropagation(); onDismiss(idea); }}
                className="text-xs px-2 py-1 rounded-lg text-neutral-500 hover:text-neutral-300 hover:bg-neutral-700/50 transition-colors"
              >
                ×
              </button>
            </div>
          </div>

          {/* Description — truncated when collapsed */}
          <p className={`text-xs text-neutral-300 leading-relaxed ${!expanded ? "line-clamp-2" : ""}`}>
            {idea.description}
          </p>

          {/* Expanded details */}
          {expanded && (
            <div className="space-y-1.5 pt-1">
              {idea.keywords.length > 0 && (
                <div className="flex flex-wrap gap-1">
                  {idea.keywords.map((kw) => (
                    <span
                      key={kw}
                      className="text-[10px] px-2 py-0.5 rounded-md bg-neutral-700/50 text-neutral-400"
                    >
                      {kw}
                    </span>
                  ))}
                </div>
              )}

              {idea.signals.length > 0 && (
                <div className="flex flex-wrap gap-1.5">
                  <span className="text-[10px] text-neutral-500">Signals:</span>
                  {idea.signals.map((signal) => (
                    <span
                      key={signal}
                      className="text-[10px] font-medium px-1.5 py-0.5 rounded-md bg-violet-500/10 text-violet-300 border border-violet-500/15"
                    >
                      {signal}
                    </span>
                  ))}
                </div>
              )}

              {idea.trending_source && (
                <TrendingSourceChips source={idea.trending_source} />
              )}

              {idea.reasoning && (
                <p className="text-xs italic text-neutral-400 leading-relaxed">
                  {idea.reasoning}
                </p>
              )}

              {idea.angle && (
                <p className="text-[11px] text-neutral-500">
                  <span className="font-medium text-neutral-400">Angle:</span> {idea.angle}
                </p>
              )}
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
```

- [ ] **Step 3: Verify TypeScript compiles**

Run: `cd ~/git/headless-hero/frontend && npx tsc --noEmit --pretty 2>&1 | head -20`
Expected: No errors related to SmartIdeaCard or SmartIdea

- [ ] **Step 4: Commit**

```bash
git add frontend/src/components/trending/SmartIdeaCard.tsx
git commit -m "Handle null style_match_score and render signals in SmartIdeaCard"
```

---

### Task 6: Simplify ForYouTab — remove gating and setup states

**Files:**
- Modify: `frontend/src/components/trending/ForYouTab.tsx`

- [ ] **Step 1: Rewrite ForYouTab to remove gated/setup states**

Replace the entire contents of `frontend/src/components/trending/ForYouTab.tsx` with:

```tsx
import { useEffect, useState } from "react";
import {
  getContentProfile,
  refreshContentProfile,
  generateSmartIdeas,
} from "../../api";
import type { VideoIdea } from "../../types/idea";
import type { ContentProfile, SmartIdea } from "../../types/trending";
import ContentProfileCard from "./ContentProfileCard";
import SmartIdeaCard from "./SmartIdeaCard";

interface Props {
  onGenerateIdeas: (ideas: VideoIdea[], niche: string) => void;
}

export default function ForYouTab({ onGenerateIdeas }: Props) {
  const [profile, setProfile] = useState<ContentProfile | null>(null);
  const [ideas, setIdeas] = useState<SmartIdea[]>([]);
  const [loadingProfile, setLoadingProfile] = useState(true);
  const [loadingIdeas, setLoadingIdeas] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    getContentProfile()
      .then((p) => setProfile(p))
      .catch(() => {})
      .finally(() => setLoadingProfile(false));
  }, []);

  const handleRefreshProfile = async () => {
    setLoadingProfile(true);
    setError(null);
    try {
      const p = await refreshContentProfile();
      setProfile(p);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to refresh profile");
    } finally {
      setLoadingProfile(false);
    }
  };

  const handleGenerate = async () => {
    setLoadingIdeas(true);
    setError(null);
    try {
      const result = await generateSmartIdeas(10);
      setIdeas(result.ideas);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to generate ideas");
    } finally {
      setLoadingIdeas(false);
    }
  };

  const handleUseIdea = (idea: SmartIdea) => {
    const videoIdea: VideoIdea = {
      title: idea.title,
      description: idea.description,
      segments_est: idea.segments_est,
      keywords: idea.keywords,
    };
    onGenerateIdeas([videoIdea], idea.title);
  };

  const handleDismiss = (idea: SmartIdea) => {
    setIdeas((prev) => prev.filter((i) => i.title !== idea.title));
  };

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-start justify-between">
        <div>
          <h2 className="text-2xl font-bold mb-1">For You</h2>
          <p className="text-neutral-400 text-sm">
            AI-powered video ideas from trending data and brainstorm strategies
          </p>
        </div>
        <button
          onClick={handleGenerate}
          disabled={loadingIdeas}
          className="flex items-center gap-2 text-sm px-4 py-2 rounded-lg font-medium bg-violet-600 hover:bg-violet-500 disabled:opacity-50 disabled:cursor-not-allowed text-white transition-colors"
        >
          {loadingIdeas ? (
            <svg className="w-4 h-4 animate-spin" fill="none" viewBox="0 0 24 24">
              <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
              <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z" />
            </svg>
          ) : (
            <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" strokeWidth={1.8} stroke="currentColor">
              <path strokeLinecap="round" strokeLinejoin="round" d="M9.813 15.904L9 18.75l-.813-2.846a4.5 4.5 0 00-3.09-3.09L2.25 12l2.846-.813a4.5 4.5 0 003.09-3.09L9 5.25l.813 2.846a4.5 4.5 0 003.09 3.09L15.75 12l-2.846.813a4.5 4.5 0 00-3.09 3.09z" />
            </svg>
          )}
          {loadingIdeas ? "Generating..." : "Generate Ideas"}
        </button>
      </div>

      {/* Content profile card — only when profile exists */}
      {profile && (
        <ContentProfileCard
          profile={profile}
          loading={loadingProfile}
          onRefresh={handleRefreshProfile}
        />
      )}

      {/* Error */}
      {error && (
        <div className="rounded-lg border border-red-500/30 bg-red-500/10 px-4 py-3 text-sm text-red-300">
          {error}
        </div>
      )}

      {/* Loading skeletons */}
      {loadingIdeas && ideas.length === 0 && (
        <div className="space-y-3">
          {[0, 1, 2].map((i) => (
            <div key={i} className="bg-neutral-800/50 border border-neutral-700/40 rounded-xl p-5 animate-pulse">
              <div className="flex gap-4">
                <div className="w-12 h-12 rounded-xl bg-neutral-700/50 shrink-0" />
                <div className="flex-1 space-y-3">
                  <div className="h-4 bg-neutral-700/50 rounded w-3/4" />
                  <div className="h-3 bg-neutral-700/50 rounded w-full" />
                  <div className="flex gap-1.5">
                    <div className="h-4 w-16 bg-neutral-700/50 rounded" />
                    <div className="h-4 w-12 bg-neutral-700/50 rounded" />
                  </div>
                </div>
              </div>
            </div>
          ))}
        </div>
      )}

      {/* Smart idea cards */}
      {ideas.length > 0 && (
        <div className="space-y-3">
          <p className="text-xs text-neutral-500">
            {ideas.length} idea{ideas.length !== 1 ? "s" : ""} generated
          </p>
          {ideas.map((idea, i) => (
            <SmartIdeaCard
              key={`${idea.title}-${i}`}
              idea={idea}
              index={i}
              onUseIdea={handleUseIdea}
              onDismiss={handleDismiss}
            />
          ))}
        </div>
      )}

      {/* Empty state */}
      {!loadingIdeas && ideas.length === 0 && (
        <div className="text-center py-12 space-y-3">
          <p className="text-neutral-400">
            Hit &ldquo;Generate Ideas&rdquo; to get AI-powered video suggestions
          </p>
          <p className="text-xs text-neutral-500">
            Combines trending data from 7 sources with 5 brainstorm strategies
          </p>
        </div>
      )}
    </div>
  );
}
```

- [ ] **Step 2: Verify TypeScript compiles**

Run: `cd ~/git/headless-hero/frontend && npx tsc --noEmit --pretty 2>&1 | head -20`
Expected: No errors related to ForYouTab

- [ ] **Step 3: Commit**

```bash
git add frontend/src/components/trending/ForYouTab.tsx
git commit -m "Remove 3-script gate and setup states from ForYouTab"
```

---

### Task 7: Reorder Discover tabs — For You first

**Files:**
- Modify: `frontend/src/components/trending/DiscoverPage.tsx`

- [ ] **Step 1: Change default tab and swap button order**

In `frontend/src/components/trending/DiscoverPage.tsx`:

1. Change the default state on line 11 from `"trending"` to `"for-you"`:

```typescript
const [activeTab, setActiveTab] = useState<"trending" | "for-you">("for-you");
```

2. Swap the tab buttons so the "For You" button (lines 38-50) comes before the "Trending" button (lines 26-37). Replace the entire tab switcher `<div>` (lines 24-51) with:

```tsx
      <div className="inline-flex items-center p-1 mb-8 bg-neutral-800/60 rounded-xl border border-neutral-700/40">
        <button
          onClick={() => setActiveTab("for-you")}
          className={`flex items-center gap-2 px-5 py-2 text-sm font-medium rounded-lg transition-all duration-200 ${
            activeTab === "for-you"
              ? "bg-neutral-700/80 text-white shadow-sm"
              : "text-neutral-400 hover:text-neutral-200"
          }`}
        >
          <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" strokeWidth={1.8} stroke="currentColor">
            <path strokeLinecap="round" strokeLinejoin="round" d="M9.813 15.904L9 18.75l-.813-2.846a4.5 4.5 0 00-3.09-3.09L2.25 12l2.846-.813a4.5 4.5 0 003.09-3.09L9 5.25l.813 2.846a4.5 4.5 0 003.09 3.09L15.75 12l-2.846.813a4.5 4.5 0 00-3.09 3.09zM18.259 8.715L18 9.75l-.259-1.035a3.375 3.375 0 00-2.455-2.456L14.25 6l1.036-.259a3.375 3.375 0 002.455-2.456L18 2.25l.259 1.035a3.375 3.375 0 002.455 2.456L21.75 6l-1.036.259a3.375 3.375 0 00-2.455 2.456z" />
          </svg>
          For You
        </button>
        <button
          onClick={() => setActiveTab("trending")}
          className={`flex items-center gap-2 px-5 py-2 text-sm font-medium rounded-lg transition-all duration-200 ${
            activeTab === "trending"
              ? "bg-neutral-700/80 text-white shadow-sm"
              : "text-neutral-400 hover:text-neutral-200"
          }`}
        >
          <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" strokeWidth={1.8} stroke="currentColor">
            <path strokeLinecap="round" strokeLinejoin="round" d="M2.25 18L9 11.25l4.306 4.307a11.95 11.95 0 015.814-5.519l2.74-1.22m0 0l-5.94-2.28m5.94 2.28l-2.28 5.941" />
          </svg>
          Trending
        </button>
      </div>
```

- [ ] **Step 2: Commit**

```bash
git add frontend/src/components/trending/DiscoverPage.tsx
git commit -m "Reorder Discover tabs so For You is first and default"
```

---

### Task 8: Remove Brainstorm nav and view from App.tsx

**Files:**
- Modify: `frontend/src/App.tsx`

- [ ] **Step 1: Remove the BrainstormPage import**

In `frontend/src/App.tsx`, delete line 12:

```typescript
import BrainstormPage from "./components/brainstorm/BrainstormPage";
```

- [ ] **Step 2: Remove "brainstorm" from the View type**

On line 18, change:

```typescript
type View = "project-dashboard" | "ideation" | "script-generation" | "timeline" | "settings" | "discover" | "postits" | "brainstorm" | "catalog";
```

to:

```typescript
type View = "project-dashboard" | "ideation" | "script-generation" | "timeline" | "settings" | "discover" | "postits" | "catalog";
```

- [ ] **Step 3: Remove the Brainstorm nav button**

Delete the entire brainstorm button block (lines 261-273):

```tsx
            <button
              onClick={() => handleSetView("brainstorm")}
              className={`flex items-center gap-1.5 rounded-lg px-3 py-1.5 text-sm transition-colors ${
                view === "brainstorm"
                  ? "bg-violet-500/15 text-violet-300 font-semibold"
                  : "text-neutral-500 hover:bg-neutral-800 hover:text-neutral-200"
              }`}
            >
              <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" strokeWidth={1.5} stroke="currentColor">
                <path strokeLinecap="round" strokeLinejoin="round" d="M12 18v-5.25m0 0a6.01 6.01 0 001.5-.189m-1.5.189a6.01 6.01 0 01-1.5-.189m3.75 7.478a12.06 12.06 0 01-4.5 0m3.75 2.383a14.406 14.406 0 01-3 0M14.25 18v-.192c0-.983.658-1.823 1.508-2.316a7.5 7.5 0 10-7.517 0c.85.493 1.509 1.333 1.509 2.316V18" />
              </svg>
              Brainstorm
            </button>
```

- [ ] **Step 4: Remove "brainstorm" from the main content area class condition**

On line 384, change:

```tsx
      <main className={`flex-1 w-full ${view === "timeline" || view === "project-dashboard" || view === "settings" || view === "discover" || view === "postits" || view === "brainstorm" || view === "catalog" ? "" : "px-6 py-8 max-w-4xl mx-auto"}`}>
```

to:

```tsx
      <main className={`flex-1 w-full ${view === "timeline" || view === "project-dashboard" || view === "settings" || view === "discover" || view === "postits" || view === "catalog" ? "" : "px-6 py-8 max-w-4xl mx-auto"}`}>
```

- [ ] **Step 5: Remove the brainstorm view render block**

Delete lines 454-461:

```tsx
        {view === "brainstorm" && (
          <BrainstormPage
            onGenerateIdeas={(niche) => {
              setAutoGenerateNiche(niche);
              handleSetView("ideation");
            }}
          />
        )}
```

- [ ] **Step 6: Verify TypeScript compiles**

Run: `cd ~/git/headless-hero/frontend && npx tsc --noEmit --pretty 2>&1 | head -20`
Expected: No errors (there may be warnings about unused brainstorm files, that's fine)

- [ ] **Step 7: Commit**

```bash
git add frontend/src/App.tsx
git commit -m "Remove Brainstorm nav entry and view from App"
```

---

### Task 9: Manual smoke test

- [ ] **Step 1: Start the dev server**

Run: `cd ~/git/headless-hero && npm run dev`

- [ ] **Step 2: Verify Discover page opens to For You tab**

Navigate to the Discover page. Confirm:
- For You tab is selected by default (left tab)
- Trending tab is on the right
- No "Build Your Content Profile" gate or "Analyze My Content" button
- "Generate Ideas" button is visible and clickable
- If a content profile exists, the profile card shows; if not, it's absent (no error)

- [ ] **Step 3: Click Generate Ideas and verify output**

Click "Generate Ideas" and confirm:
- Ideas load (10 cards)
- Each idea has title, description, keywords, trending source, reasoning, angle
- `signals` chips appear in expanded view (violet-colored)
- If profile exists: style match badge shows on each card
- If no profile: no match badge, cards still render correctly
- "Use Idea →" navigates to ideation page with the idea pre-filled

- [ ] **Step 4: Verify Brainstorm nav is gone**

Confirm the "Brainstorm" button no longer appears in the sidebar navigation.

- [ ] **Step 5: Commit any fixes if needed**

If smoke testing revealed issues, fix and commit each fix separately.
