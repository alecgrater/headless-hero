# Scene Duration Variance — Design Spec

## Problem

High-energy scenes (`quick_cuts`, `aha_subtitle`) should feel punchy and fast, but Claude currently generates narration with no duration guidance for these beats. The result is high-energy scenes that can drift to 12-15 seconds — undermining the pacing they're meant to create.

## Solution

Two-layer approach:

1. **Upfront prompt guidance** — Tell Claude to write shorter narration for high-energy beats during script generation.
2. **Post-voiceover safety net** — After batch voiceover, check actual audio durations. If any high-energy scene exceeds 10 seconds, re-prompt Claude to rewrite the narration shorter, then re-voice only the changed scenes.

## Scope

**In scope:**
- Scriptwriter prompt changes for `quick_cuts` and `aha_subtitle` duration guidance
- New `backend/pipeline/duration_variance.py` module
- Integration into batch voiceover endpoint

**Out of scope:**
- No UI changes (no new buttons, badges, or indicators)
- No configurable thresholds from frontend (hardcoded 10s)
- No retry loops (single pass only)
- No duration constraints on other beat types (static, continuous, montage)
- No changes to single-scene voiceover endpoint (batch only)

---

## 1. Scriptwriter Prompt Changes

**File:** `backend/prompts/script_prompt.md`

Update the beat type definitions (lines 104-106) to add duration guidance:

- **quick_cuts** (line 104): Append "Narration should be 1 short punchy sentence — aim for under 8 seconds of speech."
- **aha_subtitle** (line 105): Append "Narration should be 1 short sentence — a single stat or fact, under 8 seconds of speech."

No other beat types are changed. The 8-second guidance leaves headroom below the 10-second hard threshold.

---

## 2. Duration Variance Module

**New file:** `backend/pipeline/duration_variance.py`

### Constants

```python
HIGH_ENERGY_BEATS = {"quick_cuts", "aha_subtitle"}
MAX_DURATION_SECONDS = 10.0
```

### Public API

```python
def check_and_tighten(
    script_id: str,
    session: Session,
    voice_id: str,
    model_id: str = DEFAULT_TTS_MODEL,
    voice_settings: dict | None = None,
) -> list[str]:
    """
    Check high-energy scenes for duration overruns and rewrite if needed.
    Returns list of scene IDs that were rewritten and re-voiced.
    """
```

### Logic

1. Load the script's `ScriptContent` from DB via `script_id`.
2. Collect all scenes where `visual_beat in HIGH_ENERGY_BEATS` AND `audio_duration_seconds > MAX_DURATION_SECONDS`.
3. If none flagged, log and return empty list.
4. Build a single Claude call with the flagged scenes:
   - Input: list of `{scene_id, visual_beat, narration, current_duration_seconds}`
   - Prompt: "These high-energy scenes are too long. Rewrite each narration to be shorter and punchier while preserving the core message. Return JSON mapping scene_id to new_narration."
   - Uses existing `claude_client` integration.
5. Parse Claude's JSON response. For each rewritten scene:
   - Update `scene.narration` in the `ScriptContent` object.
6. Re-voice only the changed scenes via `generate_scene_audio()` from `backend/pipeline/voiceover.py`.
   - Update `audio_url`, `audio_duration_seconds`, `word_timestamps` on each scene.
7. Persist the updated `ScriptContent` back to the script's `script_json` blob.
8. Return list of rewritten scene IDs.

### Claude Rewrite Prompt

System prompt (concise, focused):
```
You are a script editor. You will receive high-energy video scenes whose narration is too long.
Rewrite each narration to be shorter and punchier while preserving the core fact or message.
- quick_cuts scenes: 1 short punchy sentence
- aha_subtitle scenes: 1 short sentence with the key stat or fact
Return ONLY valid JSON: {"scene_id": "new narration", ...}
```

### Dependencies

- `backend/integrations/claude_client.py` — for the rewrite call
- `backend/pipeline/voiceover.py` — `generate_scene_audio()` for re-voicing
- `backend/models/script.py` — `ScriptContent`, `Scene`
- `backend/api/_helpers.py` — `update_scene()` is NOT used here; we update the full blob directly since we may change multiple scenes

---

## 3. Integration into Voiceover Batch Endpoint

**File:** `backend/api/voiceover.py`

In the `generate_audio_batch` endpoint (line 130), after persisting batch results to DB (line 166), add:

```python
from backend.pipeline.duration_variance import check_and_tighten

# After batch persist, check high-energy scene durations
tightened = check_and_tighten(body.script_id, session)
if tightened:
    logger.info("Duration variance: rewrote %d scenes: %s", len(tightened), tightened)
```

The call is synchronous within the same request. Batch voiceover is already a long-running sequential call, so one Claude rewrite + a few re-voices doesn't meaningfully change latency.

The response model (`GenerateBatchAudioResponse`) stays unchanged. The frontend already re-reads script data after voiceover completes, so it picks up the updated narrations and durations automatically.

### Voice Settings Passthrough

`check_and_tighten` needs the voice_id and voice settings to re-voice scenes. These are passed through from the batch request:

```python
tightened = check_and_tighten(
    script_id=body.script_id,
    session=session,
    voice_id=body.voice_id,
    model_id=body.model_id,
    voice_settings=body.voice_settings,
)
```

Updated function signature:

```python
def check_and_tighten(
    script_id: str,
    session: Session,
    voice_id: str,
    model_id: str = "eleven_multilingual_v2",
    voice_settings: dict | None = None,
) -> list[str]:
```

---

## Data Flow

```
Script Generation (Claude)
  ↓ prompt now includes "aim for under 8s" for quick_cuts/aha_subtitle
Batch Voiceover (ElevenLabs)
  ↓ all scenes voiced, actual durations measured
Duration Variance Check
  ↓ flag high-energy scenes > 10s
  ↓ if any: single Claude call to rewrite narrations
  ↓ re-voice only changed scenes
  ↓ persist updated script_json
Response to Frontend
  ↓ frontend re-reads script, sees updated narrations + durations
```

## Error Handling

- If the Claude rewrite call fails, log the error and return empty list (don't block the voiceover response).
- If re-voicing a scene fails, log the error, keep the original audio, skip that scene.
- The feature is best-effort — a failure in the tighten pass should never cause the batch voiceover endpoint to return an error.
