# Script Rating Design

## Goal

Add an honest post-generation script scorecard that runs in a fresh LLM call after each script is created, persists with the script, and is visible both on the project dashboard and the timeline/script page.

## Current State

`backend/pipeline/script_reviewer.py` and `SCRIPT_REVIEW_RUBRIC` were an unused pass/fail Gemini review experiment. They are not called by generation, not persisted, and not shown in the UI. This feature removes that legacy path and replaces it with a persisted numeric scorecard.

Existing hook scoring stays separate. Hook scoring evaluates only the opening on a 0-100 retention scale. Script rating evaluates the full script on a 1-10 rubric.

## Architecture

Create `backend/pipeline/script_rating.py` as the single backend scoring unit. It builds a compact full-script payload, calls the routed LLM client once with `task="script_rating"`, parses strict JSON, validates the 14 criterion scores, computes category averages and weighted overall locally, and returns a Pydantic `ScriptRating`.

Store the rating in the existing `ScriptContent` JSON blob as `script_rating`. No SQL migration is needed. Generation calls the rating after the script has been persisted, near the existing hook scoring stage, and saves the updated JSON. Rating failures are logged and non-blocking so script generation still completes.

Add a dedicated LLM task:

- key: `script_rating`
- label: `Script rating`
- default provider: `openai`
- default OpenAI model: `gpt-5-mini`
- OpenAI reasoning effort: `minimal`
- Anthropic fallback: balanced Claude
- Ollama fallback: configured local model

The prompt explicitly tells the evaluator it is in a fresh context with no memory of generation and must judge against top-performing educational YouTube channels.

## Data Model

Add these concepts to `backend/models/script.py`:

- `ScriptRatingCriterion`: `{score: int, note: str = ""}`
- `ScriptRatingCategory`: `{average: float, explanation: str, criteria: dict[str, ScriptRatingCriterion]}`
- `ScriptRating`: category objects for viewer retention, narrative quality, script craft, audience fit, and SEO alignment, plus `overall: float`, `model: str`, `version: str`

Add `script_rating: ScriptRating | None = None` to `ScriptContent`.

Add `script_rating_overall: float | None = None` to `ScriptSummary` so dashboard cards can display it without loading another endpoint.

## Rubric

Viewer Retention, 30%:
- hook_strength
- curiosity_gaps
- pacing_variance

Narrative Quality, 15%:
- coherence
- throughline

Script Craft, 25%:
- sentence_variety
- specificity
- redundancy
- word_economy

Audience Fit, 20%:
- assumed_knowledge_level
- relatability
- tone_consistency
- emotional_range

SEO Alignment, 10%:
- title_hook_match
- search_intent_match
- rewatch_value

The LLM returns scores and explanations. Backend code recomputes averages and weighted overall so malformed arithmetic from the model cannot corrupt the saved score.

## UI

Dashboard project cards show a compact `Script {overall}` badge beside the existing hook badge when present.

The timeline/script page shows a `Script Rating` card with:

- overall score out of 10
- five weighted category scores
- criterion breakdown in compact text
- one short explanatory paragraph per category

Styling follows the existing dark Tailwind UI and uses hover/tooltips only where helpful.

## Testing

Backend tests cover:

- parsing and recomputing a rating response
- invalid/missing criterion scores raising a parse error
- `ScriptContent` serialization round-trip with `script_rating`
- script summaries exposing `script_rating_overall`
- generation persisting rating after script creation using monkeypatched scorer

Frontend tests/types cover:

- TypeScript `ScriptRating` shape
- rating card rendering with overall, categories, criteria, and explanations

## Non-Goals

- No rating history or SQL table.
- No automatic script regeneration from ratings.
- No use of the old pass/fail `script_reviewer.py`.
- No blocking script generation when the rating model is unavailable.
