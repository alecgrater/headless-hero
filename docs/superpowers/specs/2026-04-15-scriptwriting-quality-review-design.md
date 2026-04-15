# Scriptwriting Quality & Review Loop Design

**Date:** 2026-04-15

## Context

The current scriptwriting pipeline uses two large, overlapping prompt files (`scriptwriting_guide.md` ~1800 words + `script_system.md` ~1200 words) plus injected title card instructions. Scripts are generated via a single Claude call with no quality gate — whatever Claude returns (after post-processing) becomes the final script.

The user wants to:
1. **Improve script writing quality** by integrating 5 specific craft skillsets into the prompt
2. **Add a quality review loop** where Gemini (`gemini-3.1-pro-preview`) independently evaluates scripts against the skillsets and triggers regeneration on failure (up to 3 attempts)
3. **Simplify prompt maintenance** by merging the two prompt files into one cohesive document

## The 5 Skillsets

1. **Payoff Promise** — Open with what viewers will walk away with and why it matters. Partially deliver a surprising insight in the first 30 seconds so the brain stays for what it's already receiving.

2. **Mosaic Structure** — Drop viewers into the middle of an interesting idea. Let threads dangle (open loops) and weave them together later. Each answered loop opens a new one until the final payoff closes them all simultaneously.

3. **Steel-Manning** — Present the strongest version of the opposing view before dismantling it. Acknowledge complexity rather than hiding it. Signals confidence and builds deep credibility.

4. **Concrete Before Abstract** — Every big claim is preceded by a specific, vivid, human-scale example. Concrete details activate memory encoding; abstraction alone slides off.

5. **Callback Economy** — Plant a detail, phrase, or visual element early that seems incidental, then bring it back at a pivotal moment. Rewards attentive watching and creates emotional resonance at key beats.

## Design

### 1. Merged Script Prompt

**New file:** `backend/prompts/script_prompt.md`
**Replaces:** `scriptwriting_guide.md` + `script_system.md`

Three sections:

**Section A: Writing Craft** — The 5 skillsets woven together with the existing staccato-educational style into a single cohesive voice guide. Overlapping concepts are merged, not duplicated:
- Existing "Nope Moment" + new "Payoff Promise" → unified hook framework
- Existing "Plant and Pay Off" + new "Callback Economy" → unified callback system
- Existing "Ground It in Story" + new "Concrete Before Abstract" → unified grounding approach
- New "Mosaic Structure" → added as structural principle (replaces linear default)
- New "Steel-Manning" → added as intellectual honesty requirement

**Section B: Visual Direction** — Shot types, visual beats, frame directives, visual storytelling arc. Carried forward unchanged from current `scriptwriting_guide.md`.

**Section C: Output Format** — JSON schema, scene/segment structure. Carried forward unchanged.

Title card instructions continue to be injected separately via `TITLE_CARD_PROMPT_INSTRUCTIONS` (no change to that mechanism).

### 2. Gemini Review Loop

**New file:** `backend/integrations/google_text_client.py`
Thin wrapper for Gemini text generation using the existing `google-genai` SDK. Mirrors the pattern of `google_image_client.py`:
- `_get_client()` reuses `GOOGLE_AI_KEY`
- `generate_text(prompt, model="gemini-3.1-pro-preview", max_tokens=4096) -> str`

**New file:** `backend/pipeline/script_reviewer.py`
Contains:
- `REVIEW_RUBRIC` — System prompt for Gemini with the 5 skillsets as scoring criteria
- `review_script(content: ScriptContent) -> ReviewResult` — Sends full script narration to Gemini, returns structured feedback
- `ReviewResult` — Pydantic model with per-skillset pass/fail + critique text + overall pass boolean

**Review rubric prompt structure:**
```
You are a script quality reviewer for educational YouTube videos.
Evaluate the script narration against these 5 craft skillsets.
For each, return pass or fail with a one-sentence explanation.

1. Payoff Promise: Does the opening deliver a surprising insight
   in the first segment? Does it partially deliver value before
   asking for viewer commitment?

2. Mosaic Structure: Are there open loops that create tension?
   Do threads weave together? Or is it a flat A→B→C progression?

3. Steel-Manning: When claims are made, does the script acknowledge
   the strongest counterarguments? Or does it bulldoze?

4. Concrete Before Abstract: Do big claims follow specific,
   human-scale examples? Or are they stated abstractly first?

5. Callback Economy: Are there planted details that recur with
   new meaning later? Or is it a flat list of unconnected facts?

Return JSON:
{
  "overall_pass": true/false,
  "skillsets": {
    "payoff_promise": {"pass": true/false, "critique": "..."},
    "mosaic_structure": {"pass": true/false, "critique": "..."},
    "steel_manning": {"pass": true/false, "critique": "..."},
    "concrete_before_abstract": {"pass": true/false, "critique": "..."},
    "callback_economy": {"pass": true/false, "critique": "..."}
  }
}
```

Gemini receives the narration text (extracted from all scenes, ordered) — not the full JSON blob with visual prompts. This keeps the review focused on writing quality.

### 3. Integration into scriptwriter.py

**Modified file:** `backend/pipeline/scriptwriter.py`

Changes to `generate_script()`:
1. Load merged prompt from `script_prompt.md` instead of two files
2. After generating and post-processing the script, call `review_script(content)`
3. If review passes → return content as normal
4. If review fails → inject Gemini's critique into a new user message and regenerate
5. Repeat up to 3 total attempts, accepting the final result regardless

The critique injection prepends to the user message:
```
IMPORTANT: A previous version of this script was reviewed and found
lacking in these areas. Address each one:
{critique_text}

Now write a full segmented video script for: "{topic}"
...
```

Progress callback reports review/retry state:
- "Reviewing script quality..." (during Gemini call)
- "Review: 3/5 skillsets passed. Regenerating (attempt 2/3)..." (on failure)
- "Script quality review passed" (on success)

**Error handling:** If Gemini API fails during review (network error, rate limit, etc.), log the error and accept the current script — don't block generation on a reviewer outage. The review loop is a quality enhancement, not a hard gate.

**Segmented mode:** The review loop wraps the final `ScriptContent` output regardless of generation mode (single-call or segmented). On retry, the full script is regenerated from scratch using the same mode.

### 4. File Changes

| File | Action | Description |
|------|--------|-------------|
| `backend/prompts/script_prompt.md` | Create | Merged prompt with 5 skillsets integrated |
| `backend/prompts/scriptwriting_guide.md` | Delete | Merged into script_prompt.md |
| `backend/prompts/script_system.md` | Delete | Merged into script_prompt.md |
| `backend/integrations/google_text_client.py` | Create | Gemini text generation wrapper |
| `backend/pipeline/script_reviewer.py` | Create | Review logic, rubric, scoring |
| `backend/pipeline/scriptwriter.py` | Modify | Load merged prompt, add review loop |

### 5. What Doesn't Change

- Script data model (no changes to `models/script.py`)
- API endpoints (no changes to `api/scripts.py`)
- Frontend (review loop is invisible — same polling, just potentially longer wait)
- Visual beat system, frame directives, title card system
- Segmented vs non-segmented generation modes
- FX generation, Eli animation
- Post-processing (`enforce_title_cards_and_min_scenes`)

## Verification

1. **Unit test the reviewer**: Call `review_script()` with a known-weak script (flat structure, no callbacks) and verify it fails the right skillsets
2. **End-to-end test**: Generate a script via `POST /api/scripts/generate`, verify logs show the review loop executing and progress messages updating
3. **Quality comparison**: Generate scripts for the same topic before and after the change, compare narration quality
4. **Retry behavior**: Temporarily make the rubric extremely strict to force retries, verify it caps at 3 attempts and accepts the final result
5. **No regressions**: Verify visual beats, title cards, frame directives are unaffected by the prompt merge
