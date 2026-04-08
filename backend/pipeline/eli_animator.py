"""Eli animator — uses Claude to generate per-scene character animation keyframes.

For each scene, Claude selects which Eli pose/expression to show and when,
synchronized to the narration timing. Mouth state (open/closed) is NOT part
of the animation document — it's computed deterministically in Remotion from
word_timestamps.
"""

import json
import logging

from config import strip_markdown_fences
from integrations.claude_client import chat
from pipeline.character_frames import get_manifest

logger = logging.getLogger(__name__)

ELI_SYSTEM_PROMPT = """You are an animation director for "Eli," a recurring animated host character in educational YouTube videos. Eli appears as a character overlay (like a webcam box) in the corner of the screen.

Your job: for each scene, create a keyframe timeline selecting which pose/expression Eli should show and when.

## Available Poses

You will be given a list of available frame IDs with their expression, pose, and gesture tags. Select from ONLY these IDs.

## Rules

1. **Match emotional tone**: If the narration is exciting, use excited poses. If thoughtful, use thinking poses. If explaining, use explaining poses.
2. **Natural movement rhythm**: Don't hold the same pose for more than 2-4 seconds (~60-120 frames at 30fps). Switch poses frequently to feel alive and reactive, like a real streamer.
3. **Content-aware gestures**: Use pointing when the narration directs attention ("look at this", "over here"). Use explaining gestures during explanations. Use shrugging for uncertainty. Use reaction poses (facepalm, jaw_drop, double_take) for surprising or funny moments.
4. **Start neutral**: Most scenes should begin with a neutral or standing pose, then shift as the emotional tone changes.
5. **Transitions**: Use "cut" for most transitions. Use "crossfade" for smooth emotional shifts (calm→excited).
6. **Cover full duration**: Keyframes must cover the entire scene duration. The first keyframe should start at frame 0. The last keyframe's end_frame should equal the scene's total frames.
7. **4-10 keyframes per scene**: Most scenes need 5-8 pose changes to feel dynamic and expressive. Very short scenes (< 3 seconds) can have 2-3. Think of Eli as an animated streamer who's always reacting to what's being said.

## Output Format

Return a JSON object with the scene "id" and an "eli_overlay" object:

```json
{
  "id": "scene_id_here",
  "eli_overlay": {
    "enabled": true,
    "keyframes": [
      {
        "start_frame": 0,
        "end_frame": 90,
        "frame_id": "neutral_standingneutral",
        "transition": "cut",
        "reason": "opening neutral stance"
      },
      {
        "start_frame": 90,
        "end_frame": 180,
        "frame_id": "excited_handsup",
        "transition": "crossfade",
        "reason": "narration builds excitement about the topic"
      }
    ]
  }
}
```

Return ONLY the JSON object, no explanation."""


def generate_scene_eli(scene_data: dict) -> dict:
    """Generate Eli animation keyframes for a single scene.

    Takes a scene summary dict, returns {id, eli_overlay}.
    """
    manifest = get_manifest()
    if not manifest or not manifest.get("frames"):
        raise RuntimeError("No character frame library found. Generate frames first.")

    # Build available frames summary for Claude
    available_frames = []
    for frame in manifest["frames"]:
        available_frames.append({
            "id": frame["id"],
            "expression": frame["expression"],
            "pose": frame["pose"],
            "gesture": frame["gesture"],
        })

    user_message = json.dumps({
        "scene": scene_data,
        "available_frames": available_frames,
    }, indent=2)

    response = chat(
        system=ELI_SYSTEM_PROMPT,
        user_message=user_message,
        max_tokens=2048,
    )

    cleaned = strip_markdown_fences(response)
    result = json.loads(cleaned)

    if not isinstance(result, dict):
        raise ValueError("Expected JSON object from Claude Eli animator")

    eli_overlay = result.get("eli_overlay", {})

    # Post-process: validate and clamp keyframes
    duration_frames = scene_data.get("duration_frames", int(scene_data.get("duration_seconds", 8) * 30))
    keyframes = eli_overlay.get("keyframes", [])

    valid_ids = {f["id"] for f in manifest["frames"]}

    validated_keyframes = []
    for kf in keyframes:
        # Validate frame_id exists
        if kf.get("frame_id") not in valid_ids:
            logger.warning("Unknown frame_id %s, skipping keyframe", kf.get("frame_id"))
            continue

        # Clamp to scene duration
        start = max(0, min(kf.get("start_frame", 0), duration_frames))
        end = max(start + 1, min(kf.get("end_frame", duration_frames), duration_frames))

        validated_keyframes.append({
            "start_frame": start,
            "end_frame": end,
            "frame_id": kf["frame_id"],
            "transition": kf.get("transition", "cut"),
            "reason": kf.get("reason", ""),
        })

    # Fill gaps: ensure keyframes cover full duration
    if validated_keyframes:
        # Sort by start_frame
        validated_keyframes.sort(key=lambda k: k["start_frame"])

        # Ensure first keyframe starts at 0
        if validated_keyframes[0]["start_frame"] > 0:
            validated_keyframes[0]["start_frame"] = 0

        # Ensure last keyframe extends to end
        validated_keyframes[-1]["end_frame"] = duration_frames

        # Fill gaps between keyframes
        for i in range(len(validated_keyframes) - 1):
            gap = validated_keyframes[i + 1]["start_frame"] - validated_keyframes[i]["end_frame"]
            if gap > 0:
                # Extend current keyframe to fill gap
                validated_keyframes[i]["end_frame"] = validated_keyframes[i + 1]["start_frame"]
    else:
        # No valid keyframes — use neutral standing for full duration
        validated_keyframes = [{
            "start_frame": 0,
            "end_frame": duration_frames,
            "frame_id": manifest["frames"][0]["id"] if manifest["frames"] else "neutral_standingneutral",
            "transition": "cut",
            "reason": "fallback — no valid keyframes generated",
        }]

    eli_overlay["enabled"] = True
    eli_overlay["keyframes"] = validated_keyframes

    return {
        "id": result.get("id", scene_data.get("id")),
        "eli_overlay": eli_overlay,
    }
