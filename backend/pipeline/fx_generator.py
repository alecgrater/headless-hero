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

FX_SYSTEM_PROMPT = """You are a visual effects director for educational YouTube videos. You assign zoom punches — quick camera scale hits for emphasis.

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

## Visual Beat Context
Each scene includes a "visual_beat" field indicating its presentation type:
- "static" — single image, standard FX rules
- "continuous" — smooth frame progression, standard FX rules
- "quick_cuts" — independent shots with hard cuts, zoom_punch can trigger on one frame
- "aha_subtitle" — text on black, NO zoom_punch allowed
- "montage" — mixed real/AI frames, standard FX rules

## Output Format

Return a JSON array with one object per scene (same order as input). Each object has the scene "id" and an "fx" object:

```json
[
  {
    "id": "scene_id_here",
    "fx": {
      "zoom_punch": null
    }
  },
  {
    "id": "scene_with_zoom",
    "fx": {
      "zoom_punch": { "trigger_frame": 30, "scale": 1.06 }
    }
  }
]
```

Return ONLY the JSON array, no explanation."""


def generate_scene_fx(scene_data: dict, script_id: str | None = None) -> dict:
    """Generate FX for a single scene. Used for per-scene regeneration.

    Takes a scene summary dict (same format as in batch), returns {id, fx}.
    """
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

    SceneFX.model_validate(fx_data)
    return {"id": entry.get("id", scene_data.get("id")), "fx": fx_data}
