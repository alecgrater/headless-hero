"""FX generator — uses Claude to assign visual effects to each scene."""

import json
import logging

from config import strip_markdown_fences
from integrations.claude_client import chat
from models.script import SceneFX, ScriptContent

logger = logging.getLogger(__name__)

FX_SYSTEM_PROMPT = """You are a visual effects director for educational YouTube videos. Your job is to assign appropriate visual effects (FX) to each scene in a video script.

You will receive a JSON array of scenes. For each scene, assign an FX configuration that enhances the storytelling.

## Available Effects

### Camera Effects (camera)
- **ken_burns**: Slow pan/zoom — the workhorse. Use direction: "in" (zoom in), "out" (zoom out), "left", "right", "up", "down"
- **zoom_punch**: Quick digital push-in for emphasis moments (stats, revelations, key facts)
- **parallax**: Foreground/background move at different rates — good for establishing shots
- **static**: No motion — use sparingly, only for already-busy visuals like gameplay clips

Intensity: "subtle" (barely noticeable), "moderate" (default, professional), "dramatic" (cinematic emphasis)
Easing: "spring" (organic, default), "linear" (mechanical), "ease_in_out" (smooth)

### Text Effects (text_effects)
- **lower_third**: Branded info bar that slides in — for introducing topics, names, facts
- **kinetic_caption**: Key words pop/scale for emphasis — specify which "words" to emphasize
- **word_reveal**: Word-by-word sync with voiceover — good for quotes or important statements
- **title_insert**: Oversized word slam — for section titles or dramatic reveals
- **source_citation**: Animated citation card — for when a source or statistic is mentioned

### Transitions (transition)
- **cut**: Hard cut (default, most common — don't overuse transitions)
- **crossfade**: Alpha dissolve — good between related scenes, topic continuation
- **slide**: Directional slide (direction: "left", "right") — good for comparison or lists
- **push**: Push transition (direction: "up", "left") — good for segment changes
- **smash_cut**: 2-4 frame black flash — for dramatic shifts, surprising reveals
- **zoom_punch**: Quick zoom transition — for energetic topic changes

### Overlays (overlays)
- **chapter_indicator**: Thin progress bar — use on first scene of each segment
- **film_grain**: Subtle film noise — use sparingly for cinematic feel
- **letterbox**: Cinematic bars — good for dramatic/emotional moments
- **vignette**: Dark edge vignette — subtle atmosphere enhancement

### Structural Elements (structural)
- **cold_open**: Bold question/hook in first 5 seconds — ONLY for the very first scene
- **chapter_transition**: Full-screen section title — use for first scene of major segments
- **recap**: Brief summary card — use between major sections
- **end_screen**: Subscribe/next-video CTA — ONLY for the very last scene

## Editorial Guidelines

1. **Vary camera effects** — don't repeat the same direction 3+ times in a row
2. **Most transitions should be hard cuts** — transitions are seasoning, not the main course. Use 60-70% hard cuts.
3. **Use chapter_indicator on first scene of each segment** to show progress
4. **Reserve dramatic effects for key moments** — a revelation, a surprising fact, a dramatic turn
5. **Kinetic captions should emphasize 1-3 key words per scene**, not every word
6. **Title card scenes** (is_title_card=true) should get zoom_punch camera and chapter_transition structural
7. **Gameplay clips** (media_type=gameplay_clip) should get static camera (the video provides motion)
8. **Educational content favors clean, readable typography** — don't overwhelm with effects
9. **Film grain and letterbox are global mood choices** — if used, apply consistently across many scenes
10. **The first scene should have cold_open if it has a hook/question in the narration**
11. **The last scene should have end_screen structural element**

## Output Format

Return a JSON array with one object per scene (same order as input). Each object has the scene "id" and an "fx" object matching this schema:

```json
[
  {
    "id": "scene_id_here",
    "fx": {
      "camera": { "type": "ken_burns", "direction": "in", "intensity": "moderate", "easing": "spring" },
      "text_effects": [
        { "type": "lower_third", "text": "Key Fact", "position": "lower_third", "enter_at": 1.0, "duration": 3.0 }
      ],
      "transition": { "type": "cut" },
      "overlays": [
        { "type": "chapter_indicator" }
      ],
      "structural": null
    }
  }
]
```

Only include fields that differ from defaults. Omit null/empty fields for brevity.
Return ONLY the JSON array, no explanation."""


def generate_fx(content: ScriptContent) -> list[dict]:
    """Generate FX assignments for all scenes in a script.

    Returns a list of dicts with {id, fx} for each scene.
    """
    # Build scene summary for Claude
    scenes_summary = []
    scene_index = 0
    total_scenes = sum(len(seg.scenes) for seg in content.segments)

    for seg_idx, seg in enumerate(content.segments):
        for sc_idx, scene in enumerate(seg.scenes):
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
                "narration": scene.narration[:200],  # truncate for token efficiency
                "visual_prompt": scene.visual_prompt[:100],
                "text_overlay": scene.text_overlay,
                "duration_seconds": scene.audio_duration_seconds or scene.duration_estimate_seconds,
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

    # Parse response
    cleaned = strip_markdown_fences(response)
    fx_list = json.loads(cleaned)

    if not isinstance(fx_list, list):
        raise ValueError("Expected JSON array from Claude FX generator")

    # Validate each entry has id and fx
    result = []
    for entry in fx_list:
        if not isinstance(entry, dict) or "id" not in entry:
            continue
        fx_data = entry.get("fx", {})
        # Validate against Pydantic model
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
