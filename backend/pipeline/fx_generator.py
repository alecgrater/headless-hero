"""FX generator — uses Claude to assign visual effects to each scene.

Simplified to zoom punches only — 3-6 per video, asymmetric scale hits on key moments.

Chapter markers are computed deterministically in remotion_render.py — no AI needed.
"""

import json
import logging

from config import strip_markdown_fences
from integrations.claude_client import chat
from models.script import SceneFX

logger = logging.getLogger(__name__)

FX_SYSTEM_PROMPT = """You are a visual effects director for educational YouTube videos. You assign camera drift, zoom punches, and scene-boundary transitions to each scene.

## Camera Drift (drift)
Slow continuous camera motion over the entire scene duration. Assigned to **every** image scene to eliminate static frames.

For each drift, specify:
- **motion**: One of "zoom_in", "zoom_out", "pan_left", "pan_right", "drift_diagonal"
  - zoom_in — slow push toward the anchor point
  - zoom_out — slow pull back from the anchor point
  - pan_left — slow lateral slide left (anchor sets vertical position)
  - pan_right — slow lateral slide right (anchor sets vertical position)
  - drift_diagonal — slow diagonal slide toward/away from anchor corner (RAREST — only for scenes with a clear corner-weighted subject)
- **intensity**: 0.05-0.08 (percent of total movement). Vary per scene — do NOT use the same intensity every time.
- **anchor**: 9-point grid position — "top-left", "top-center", "top-right", "center-left", "center", "center-right", "bottom-left", "bottom-center", "bottom-right". For zoom_in, anchor at the focal point. For zoom_out, start at the focal point and pull back. For pans, anchor sets the vertical band.

**Rules:**
- Assign drift to EVERY image scene (static, continuous, quick_cuts, montage).
- NO drift on "aha_subtitle" scenes (text on black) or title_card scenes.
- **Never repeat the same motion type on consecutive scenes.** If the previous scene used "zoom_in", this scene MUST use something else.
- drift_diagonal is the RAREST pick — reserve for scenes with a clear corner-weighted subject.
- Vary intensity across scenes (don't always pick 0.06).
- If "previous_drift" is provided, read its motion type and choose a DIFFERENT one.

## Zoom Punches (zoom_punch)
A quick 4-7% scale hit for emphasis. Use sparingly — 3-6 per ENTIRE video.

For each zoom punch, specify:
- **trigger_frame**: Frame within the scene where the punch triggers
- **scale**: Scale factor (1.04-1.07). Use 1.04-1.05 for subtle emphasis, 1.06-1.07 for dramatic reveals.

**Rules:**
- MOST scenes should have NO zoom punch (null).
- Reserve for: shocking statistics, dramatic reveals, key turning points.
- Never zoom punch on title card scenes or gameplay clips.
- Never zoom punch on "aha_subtitle" scenes (no image to zoom — these are text-on-black).
- Never zoom punch 2 consecutive scenes.

## Scene-Boundary Transitions (transition_in)
A visual transition effect that plays when entering this scene. The outgoing scene mirrors the transition as an exit effect. Use sparingly — 3-5 non-cut transitions per ENTIRE video.

Options:
- **"cut"** — instant switch (default, most common)
- **"fade_black"** — fade through black (0.33s each direction)
- **"flash_white"** — flash to white then fade back (dramatic, 0.13s exit + 0.27s enter)
- **"wipe"** — horizontal wipe (0.40s each direction)

**Rules:**
- MOST scenes should be "cut" — only 3-5 non-cut transitions per video total.
- **fade_black** — for somber/reflective tone shifts, contemplative pauses, or sad reveals.
- **flash_white** — for shocking facts, energy spikes, or dramatic reveals. The most intense option.
- **wipe** — for clean topic pivots, "meanwhile" moments, or switching to a new angle.
- **NEVER** on the first scene of a segment (chapter transition already handles it).
- **NEVER** on title_card or aha_subtitle scenes.
- **NEVER** use the same non-cut transition type on consecutive scene boundaries.
- If "previous_transition" is provided and is non-cut, this scene MUST be "cut" or a different type.

## Visual Beat Context
Each scene includes a "visual_beat" field indicating its presentation type:
- "static" — single image, standard FX rules
- "continuous" — smooth frame progression, standard FX rules
- "quick_cuts" — independent shots with hard cuts, zoom_punch can trigger on one frame
- "aha_subtitle" — text on black, NO drift, zoom_punch, or non-cut transition allowed
- "montage" — mixed real/AI frames, standard FX rules

## Output Format

Return a JSON array with one object per scene (same order as input). Each object has the scene "id", an "fx" object, and a "transition_in" field:

```json
[
  {
    "id": "scene_id_here",
    "fx": {
      "drift": { "motion": "pan_left", "intensity": 0.06, "anchor": "center" },
      "zoom_punch": null
    },
    "transition_in": "cut"
  },
  {
    "id": "scene_with_transition",
    "fx": {
      "drift": { "motion": "zoom_in", "intensity": 0.07, "anchor": "center-right" },
      "zoom_punch": { "trigger_frame": 30, "scale": 1.06 }
    },
    "transition_in": "fade_black"
  },
  {
    "id": "aha_subtitle_scene",
    "fx": {
      "drift": null,
      "zoom_punch": null
    },
    "transition_in": "cut"
  }
]
```

Return ONLY the JSON array, no explanation."""


def generate_scene_fx(scene_data: dict, script_id: str | None = None) -> dict:
    """Generate FX for a single scene. Used for per-scene regeneration.

    Takes a scene summary dict (same format as in batch), returns {id, fx}.
    """
    scene_id = scene_data.get("id", "unknown")
    logger.info("[%s] Generating FX for scene %s (beat=%s, duration=%.1fs)",
                script_id or "no-id", scene_id,
                scene_data.get("visual_beat", "unknown"),
                scene_data.get("duration_seconds", 0))

    user_message = json.dumps([scene_data], indent=2)

    response = chat(
        system=FX_SYSTEM_PROMPT,
        user_message=user_message,
        max_tokens=2048,
        script_id=script_id,
    )

    cleaned = strip_markdown_fences(response)
    fx_list = json.loads(cleaned)

    if not isinstance(fx_list, list) or len(fx_list) == 0:
        raise ValueError("Expected non-empty JSON array from Claude FX generator")

    entry = fx_list[0]
    fx_data = entry.get("fx", {})
    transition_in = entry.get("transition_in", "cut")

    SceneFX.model_validate(fx_data)

    has_zoom = fx_data.get("zoom_punch") is not None
    has_drift = fx_data.get("drift") is not None
    logger.info("[%s] FX assigned for scene %s: drift=%s zoom_punch=%s transition_in=%s",
                script_id or "no-id", scene_id, has_drift, has_zoom, transition_in)
    return {"id": entry.get("id", scene_data.get("id")), "fx": fx_data, "transition_in": transition_in}
