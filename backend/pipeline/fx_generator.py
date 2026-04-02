"""FX generator — uses Claude to assign visual effects to each scene.

Simplified to 2 per-scene effects:
  1. Kinetic captions — emphasis words from narration with frame-precise timing
  2. Zoom punches — 3-6 per video, asymmetric scale hits on key moments

Chapter markers are computed deterministically in remotion_render.py — no AI needed.
"""

import json
import logging

from config import strip_markdown_fences
from integrations.claude_client import chat
from models.script import SceneFX, ScriptContent

logger = logging.getLogger(__name__)

FX_SYSTEM_PROMPT = """You are a visual effects director for educational YouTube videos. You assign 2 types of per-scene effects: kinetic emphasis captions and zoom punches.

## Available Effects

### Kinetic Captions (kinetic_captions)
Pick 3-8 of the MOST IMPACTFUL words per scene (~1 every 3-5 seconds of narration). These are single emphasis words that flash on screen one at a time — NOT subtitles.

**Category-first selection:** Before picking a word, categorize it:
- `stat` — numbers, percentages, measurements ("billion", "97%", "3x")
- `key_noun` — core subject nouns that name what the scene is about ("mitochondria", "algorithm")
- `emotional` — words that carry emotional weight ("devastating", "miraculous", "terrifying")
- `action_verb` — strong verbs describing change or impact ("destroys", "transforms", "erupts")
- `contrast` — words that signal opposition or surprise ("but", "however", "unlike")
- `keyword` — other important words that don't fit above categories

**Anti-patterns — NEVER pick these:**
- Generic verbs: is, was, were, have, has, had, been, being, do, does, did, get, got, make, made
- Articles and prepositions: the, a, an, of, in, on, at, to, for, with, from, by
- Vague adjectives: very, really, quite, some, many, much, good, bad, big, small
- Pronouns: it, they, them, he, she, this, that, these, those

For each word, specify:
- **word**: The exact word from the narration
- **word_index**: 0-based index of this word in the narration text (split by whitespace). The scene data includes `word_timestamps` if audio exists — use those indices.
- **style**: One of 12 animation styles (MUST vary — never use the same style 3x in a row):
  - `scale_pop` — spring scale 80%→100% (punchy, confident)
  - `color_flash` — violet accent color pulse (highlighting, drawing attention)
  - `size_burst` — 3x font size springs down to 1x (dramatic, shocking)
  - `shake` — 2px random offset for ~10 frames (dangerous, alarming)
  - `underline_draw` — animated underline draws left→right (important, factual)
  - `glow_pulse` — neon glow that pulses 2-3x (mystical, ethereal)
  - `typewriter` — characters revealed one at a time left-to-right (methodical, technical)
  - `slide_up` — slides up from below with spring easing (emergence, growth)
  - `bounce_in` — drops from above with bouncy spring (playful, surprising)
  - `rotate_in` — rotates from -15deg to 0 while scaling up (dynamic, energetic)
  - `glitch` — RGB split + position jitter then clean (digital, disruption, error)
  - `gradient_sweep` — color gradient sweeps across word (premium, flashy)
- **category**: The word's category from the list above
- **font_size**: 48-120px. Guidelines:
  - 48px — subtle emphasis, background detail
  - 64px — standard emphasis (default)
  - 80-96px — statistics, key reveals
  - 120px — rare dramatic peak (max 1 per video)
- **position**: Where the word appears on screen:
  - `bottom_center` — default position, good for most words
  - `bottom_left` / `bottom_right` — use to vary position in sequences of words
  - `center` — reserved for the MOST dramatic moment per scene (max 1 per scene)
  - `top_center` — use sparingly for contrast or callbacks

**Category→style affinities (suggestions, not hard rules):**
- `stat` → `size_burst`, `scale_pop`
- `emotional` → `glow_pulse`, `color_flash`
- `action_verb` → `shake`, `bounce_in`
- `key_noun` → `underline_draw`, `typewriter`
- `contrast` → `glitch`, `slide_up`

**Rules:**
- Do NOT return `start_frame` or `end_frame` — timing is computed from word_timestamps automatically.
- Space words apart — avoid picking consecutive words from the narration.
- Not every scene needs captions. Quiet/reflective scenes can have 0 words.
- Title card scenes should have 0 captions.

### Zoom Punches (zoom_punch)
A quick 4-7% scale hit for emphasis. Use sparingly — 3-6 per ENTIRE video.

For each zoom punch, specify:
- **trigger_frame**: Frame within the scene where the punch triggers
- **scale**: Scale factor (1.04-1.07). Use 1.04-1.05 for subtle emphasis, 1.06-1.07 for dramatic reveals.

**Rules:**
- MOST scenes should have NO zoom punch (null).
- Reserve for: shocking statistics, dramatic reveals, key turning points.
- Never zoom punch on title card scenes or gameplay clips.
- Never zoom punch 2 consecutive scenes.

## Output Format

Return a JSON array with one object per scene (same order as input). Each object has the scene "id" and an "fx" object:

```json
[
  {
    "id": "scene_id_here",
    "fx": {
      "kinetic_captions": {
        "words": [
          { "word": "billion", "word_index": 5, "style": "size_burst", "category": "stat", "font_size": 88, "position": "bottom_center" },
          { "word": "destroyed", "word_index": 18, "style": "shake", "category": "action_verb", "font_size": 72, "position": "bottom_center" }
        ]
      },
      "zoom_punch": null
    }
  },
  {
    "id": "scene_with_zoom",
    "fx": {
      "kinetic_captions": { "words": [] },
      "zoom_punch": { "trigger_frame": 30, "scale": 1.06 }
    }
  }
]
```

Return ONLY the JSON array, no explanation."""


def _apply_word_timestamps(
    fx_data: dict,
    word_timestamps: list[dict] | None,
    duration_frames: int,
) -> dict:
    """Post-process FX to set start_frame/end_frame from actual word timestamps.

    If word_timestamps is available, uses the actual spoken timing.
    Otherwise falls back to position-based estimation from word_index.
    """
    captions = fx_data.get("kinetic_captions")
    if not captions:
        return fx_data

    words = captions.get("words", [])
    if not words:
        return fx_data

    # Build timestamp lookup: index → start_ms
    ts_by_index: dict[int, float] = {}
    ts_by_word: dict[str, float] = {}
    if word_timestamps:
        for i, ts in enumerate(word_timestamps):
            ts_by_index[i] = ts.get("start_ms", 0)
            w = ts.get("word", "").strip().lower()
            if w and w not in ts_by_word:
                ts_by_word[w] = ts.get("start_ms", 0)

    # Count total narration words for fallback estimation
    total_words = len(word_timestamps) if word_timestamps else max((w.get("word_index", 0) for w in words), default=0) + 1

    prev_end_frame = -30  # ensure first word can always appear

    for w in words:
        word_index = w.get("word_index", 0)
        start_ms = None

        # Primary: look up by index in word_timestamps
        if word_index in ts_by_index:
            start_ms = ts_by_index[word_index]
        # Fuzzy fallback: match by word text
        elif word_timestamps:
            clean_word = w.get("word", "").strip().lower()
            if clean_word in ts_by_word:
                start_ms = ts_by_word[clean_word]

        if start_ms is not None:
            start_frame = round(start_ms / 1000 * 30)
        else:
            # Position-based fallback: estimate from word_index / total_words
            if total_words > 0:
                fraction = word_index / total_words
            else:
                fraction = 0.5
            start_frame = round(fraction * duration_frames)

        # Enforce minimum 30-frame gap between consecutive words
        if start_frame < prev_end_frame + 30:
            start_frame = prev_end_frame + 30

        # Clamp to scene duration
        start_frame = min(start_frame, max(0, duration_frames - 25))

        end_frame = start_frame + 25  # ~0.8s display buffer at 30fps

        w["start_frame"] = start_frame
        w["end_frame"] = end_frame
        prev_end_frame = end_frame

    return fx_data


def generate_fx(content: ScriptContent) -> list[dict]:
    """Generate FX assignments for all scenes in a script.

    Returns a list of dicts with {id, fx} for each scene.
    """
    scenes_summary = []
    scene_index = 0
    total_scenes = sum(len(seg.scenes) for seg in content.segments)

    # Keep a parallel list of word_timestamps + duration_frames for post-processing
    scenes_meta: list[dict] = []

    for seg_idx, seg in enumerate(content.segments):
        for sc_idx, scene in enumerate(seg.scenes):
            duration = scene.audio_duration_seconds or scene.duration_estimate_seconds
            duration_frames = round(duration * 30)
            summary = {
                "id": scene.id,
                "segment": seg.name,
                "segment_index": seg_idx,
                "scene_index_in_segment": sc_idx,
                "global_index": scene_index,
                "is_first_scene": scene_index == 0,
                "is_last_scene": scene_index == total_scenes - 1,
                "is_first_in_segment": sc_idx == 0,
                "is_title_card": scene.is_title_card,
                "media_type": scene.media_type or "ai_generated",
                "narration": scene.narration,
                "duration_seconds": duration,
                "duration_frames": duration_frames,
                "has_multiple_frames": bool(scene.frame_urls and len(scene.frame_urls) > 1),
            }
            # Include word_timestamps if available (for Claude to see word indices)
            if scene.word_timestamps:
                summary["word_timestamps"] = scene.word_timestamps

            scenes_summary.append(summary)
            scenes_meta.append({
                "id": scene.id,
                "word_timestamps": scene.word_timestamps,
                "duration_frames": duration_frames,
            })
            scene_index += 1

    user_message = json.dumps(scenes_summary, indent=2)

    logger.info("Generating FX for %d scenes via Claude", len(scenes_summary))

    response = chat(
        system=FX_SYSTEM_PROMPT,
        user_message=user_message,
        max_tokens=8192,
    )

    cleaned = strip_markdown_fences(response)
    fx_list = json.loads(cleaned)

    if not isinstance(fx_list, list):
        raise ValueError("Expected JSON array from Claude FX generator")

    # Build meta lookup by scene id
    meta_by_id = {m["id"]: m for m in scenes_meta}

    result = []
    for entry in fx_list:
        if not isinstance(entry, dict) or "id" not in entry:
            continue
        fx_data = entry.get("fx", {})

        # Post-process: apply word timestamps to kinetic captions
        scene_id = entry["id"]
        meta = meta_by_id.get(scene_id)
        if meta:
            fx_data = _apply_word_timestamps(
                fx_data,
                meta["word_timestamps"],
                meta["duration_frames"],
            )

        try:
            SceneFX.model_validate(fx_data)
        except Exception as e:
            logger.warning("Invalid FX for scene %s: %s", entry["id"], e)
            continue
        result.append({"id": entry["id"], "fx": fx_data})

    logger.info("Generated FX for %d/%d scenes", len(result), len(scenes_summary))
    return result


def generate_scene_fx(scene_data: dict) -> dict:
    """Generate FX for a single scene. Used for per-scene regeneration.

    Takes a scene summary dict (same format as in batch), returns {id, fx}.
    """
    user_message = json.dumps([scene_data], indent=2)

    response = chat(
        system=FX_SYSTEM_PROMPT,
        user_message=user_message,
        max_tokens=2048,
    )

    cleaned = strip_markdown_fences(response)
    fx_list = json.loads(cleaned)

    if not isinstance(fx_list, list) or len(fx_list) == 0:
        raise ValueError("Expected non-empty JSON array from Claude FX generator")

    entry = fx_list[0]
    fx_data = entry.get("fx", {})

    # Post-process: apply word timestamps to kinetic captions
    fx_data = _apply_word_timestamps(
        fx_data,
        scene_data.get("word_timestamps"),
        scene_data.get("duration_frames", round(scene_data.get("duration_seconds", 8) * 30)),
    )

    SceneFX.model_validate(fx_data)
    return {"id": entry.get("id", scene_data.get("id")), "fx": fx_data}
