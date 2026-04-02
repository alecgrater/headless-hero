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
Pick the 20-30% MOST IMPACTFUL words from the narration. These are single emphasis words that flash on screen one at a time — NOT subtitles.

For each word, specify:
- **word**: The exact word from the narration
- **start_frame**: Frame number within the scene where the word appears (at 30fps)
- **end_frame**: Frame number where the word finishes (typically start_frame + 20-40 frames)
- **style**: One of 5 animation styles (MUST vary — never use the same style 3x in a row):
  - `scale_pop` — spring scale 80%→100% (punchy, confident)
  - `color_flash` — violet accent color pulse (highlighting, drawing attention)
  - `size_burst` — 3x font size springs down to 1x (dramatic, shocking)
  - `shake` — 2px random offset for ~10 frames (dangerous, alarming)
  - `underline_draw` — animated underline draws left→right (important, factual)

**Rules:**
- Time words to match when they'd be spoken in the narration (estimate based on word position and scene duration)
- Space words at least 30 frames apart so only one is visible at a time
- Pick words that MEAN something — numbers, key nouns, surprising adjectives
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
          { "word": "billion", "start_frame": 45, "end_frame": 75, "style": "size_burst" },
          { "word": "destroyed", "start_frame": 120, "end_frame": 150, "style": "shake" }
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


def generate_fx(content: ScriptContent) -> list[dict]:
    """Generate FX assignments for all scenes in a script.

    Returns a list of dicts with {id, fx} for each scene.
    """
    scenes_summary = []
    scene_index = 0
    total_scenes = sum(len(seg.scenes) for seg in content.segments)

    for seg_idx, seg in enumerate(content.segments):
        for sc_idx, scene in enumerate(seg.scenes):
            duration = scene.audio_duration_seconds or scene.duration_estimate_seconds
            scenes_summary.append({
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
                "narration": scene.narration,  # full narration for accurate word picking
                "duration_seconds": duration,
                "duration_frames": round(duration * 30),
                "has_multiple_frames": bool(scene.frame_urls and len(scene.frame_urls) > 1),
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

    result = []
    for entry in fx_list:
        if not isinstance(entry, dict) or "id" not in entry:
            continue
        fx_data = entry.get("fx", {})
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
    SceneFX.model_validate(fx_data)
    return {"id": entry.get("id", scene_data.get("id")), "fx": fx_data}
