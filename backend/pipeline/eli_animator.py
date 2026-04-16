"""Eli animator — uses Claude to generate per-scene character animation keyframes.

For each scene, Claude selects which Eli pose/expression to show and when,
synchronized to the narration timing. Mouth state (open/closed) is NOT part
of the animation document — it's computed deterministically in Remotion from
word_timestamps.
"""

import json
import logging

from config import FPS, strip_markdown_fences
from integrations.claude_client import chat
from pipeline.character_frames import get_manifest

logger = logging.getLogger(__name__)

ELI_SYSTEM_PROMPT = """You are an animation director for "Eli," a recurring animated host character in educational YouTube videos. Eli appears as a character overlay (like a webcam box) in the corner of the screen.

Your job: for each scene, create a keyframe timeline selecting which pose/expression Eli should show and when.

## Core Philosophy

Eli is like a real YouTube presenter. A good presenter holds a comfortable resting pose (neutral, soft smile, attentive) for most of the narration and only shifts expression for genuinely significant emotional beats — surprises, punchlines, revelations, emphasis. Constant fidgeting looks robotic, not lively.

Think of it this way: if you watch a real person talking, they hold a baseline expression 70-80% of the time, with brief, well-timed reactions for the remaining 20-30%.

## Available Poses

You will be given a list of available frame IDs with their expression, pose, and gesture tags. Select from ONLY these IDs.

## Rules

1. **Ambient vs reaction**: Most keyframes should be "ambient" — comfortable baseline poses (neutral, soft smile, attentive, explaining). Only mark a keyframe as "reaction" when Eli is genuinely reacting to something surprising, funny, or emotionally significant. Ambient keyframes get gentle crossfades; reaction keyframes get snappier, punchier transitions.

2. **Pacing**: No more than 1 significant expression change per 3 seconds (~90 frames at 30fps). Ambient shifts (neutral → soft smile → neutral) don't count as significant. Significant = changing to a clearly different emotional register (neutral → excited, explaining → surprised).

3. **Keyframe count guidelines**:
   - Short scenes (<5s / <150 frames): 2-4 keyframes
   - Medium scenes (5-15s / 150-450 frames): 3-6 keyframes
   - Long, emotionally varied scenes (>15s / >450 frames): 5-8 keyframes
   Quality over quantity — a well-timed reaction beats constant fidgeting.

4. **Content-aware gestures**: Use pointing when the narration directs attention. Use explaining gestures during explanations. Use reaction poses (facepalm, jaw_drop, double_take) sparingly for genuinely surprising or funny moments.

5. **Start neutral**: Begin with a neutral or attentive pose, then shift only as the emotional content warrants.

6. **Transitions**: Default to "crossfade" for all transitions. Reserve "cut" only for sharp dramatic moments (surprise reactions, punchlines). Most scenes should have 0-1 cuts at most.

7. **Cover full duration**: Keyframes must cover the entire scene. First keyframe starts at frame 0. Last keyframe's end_frame equals the scene's total frames.

8. **Minimum keyframe duration**: Every keyframe must be at least 15 frames (~0.5s). Shorter keyframes look like glitches.

9. **Position hints** (optional): If the scene's visual content occupies the default corner where Eli sits, you may add `"position_hint": "left"` or `"position_hint": "center"` to shift Eli. Use sparingly — most keyframes should NOT include a position_hint (Eli stays in the default right position).

10. **Content-directing poses**: When the narration references, introduces, or describes the on-screen visual (e.g., "take a look at this," "as you can see," "this shows," or when a new image appears), use a "look at content" pose — pointing, presenting, or glancing toward the visual. Check `toward_content_direction` in the input to know whether to pick `_left` or `_right` variants. Use at most 1-2 content-directing poses per scene. These work best at the start of a scene (introducing the visual) or at key "look at this" moments in narration.

## Output Format

Return a JSON object with the scene "id" and an "eli_overlay" object. Each keyframe must include a "mood" field ("ambient" or "reaction"):

```json
{
  "id": "scene_id_here",
  "eli_overlay": {
    "enabled": true,
    "keyframes": [
      {
        "start_frame": 0,
        "end_frame": 120,
        "frame_id": "neutral_standingneutral",
        "transition": "cut",
        "mood": "ambient",
        "reason": "opening neutral stance — holding baseline"
      },
      {
        "start_frame": 120,
        "end_frame": 240,
        "frame_id": "excited_handsup",
        "transition": "crossfade",
        "mood": "reaction",
        "reason": "narration reveals surprising fact — genuine reaction beat"
      }
    ]
  }
}
```

Return ONLY the JSON object, no explanation."""


def generate_scene_eli(scene_data: dict, script_id: str | None = None, eli_position: dict | None = None) -> dict:
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
        "toward_content_direction": "left" if (eli_position.get("x", 1410) if eli_position else 1410) > 960 else "right",
    }, indent=2)

    response = chat(
        system=ELI_SYSTEM_PROMPT,
        user_message=user_message,
        max_tokens=2048,
        script_id=script_id,
    )

    cleaned = strip_markdown_fences(response)
    result = json.loads(cleaned)

    if not isinstance(result, dict):
        raise ValueError("Expected JSON object from Claude Eli animator")

    eli_overlay = result.get("eli_overlay", {})

    # Post-process: validate and clamp keyframes
    duration_frames = scene_data.get("duration_frames", int(scene_data.get("duration_seconds", 8) * FPS))
    keyframes = eli_overlay.get("keyframes", [])

    valid_ids = {f["id"] for f in manifest["frames"]}
    valid_moods = {"ambient", "reaction"}
    valid_positions = {"left", "right", "center"}

    validated_keyframes = []
    for kf in keyframes:
        # Validate frame_id exists
        if kf.get("frame_id") not in valid_ids:
            logger.warning("Unknown frame_id %s, skipping keyframe", kf.get("frame_id"))
            continue

        # Clamp to scene duration
        start = max(0, min(kf.get("start_frame", 0), duration_frames))
        end = max(start + 1, min(kf.get("end_frame", duration_frames), duration_frames))

        entry: dict = {
            "start_frame": start,
            "end_frame": end,
            "frame_id": kf["frame_id"],
            "transition": kf.get("transition", "crossfade"),
            "reason": kf.get("reason", ""),
        }

        # Preserve mood tag (validated)
        mood = kf.get("mood")
        if mood in valid_moods:
            entry["mood"] = mood

        # Preserve position hint (validated)
        pos_hint = kf.get("position_hint")
        if pos_hint in valid_positions:
            entry["position_hint"] = pos_hint

        validated_keyframes.append(entry)

    # Fill gaps: ensure keyframes cover full duration
    if validated_keyframes:
        # Sort by start_frame
        validated_keyframes.sort(key=lambda k: k["start_frame"])

        # Collapse overlaps: if keyframe[i] overlaps keyframe[i+1], trim i's end
        for i in range(len(validated_keyframes) - 1):
            if validated_keyframes[i]["end_frame"] > validated_keyframes[i + 1]["start_frame"]:
                validated_keyframes[i]["end_frame"] = validated_keyframes[i + 1]["start_frame"]

        # Remove any keyframes that became zero-length after overlap collapse
        validated_keyframes = [kf for kf in validated_keyframes if kf["end_frame"] > kf["start_frame"]]

        # Enforce minimum 15-frame keyframe duration: merge short keyframes into neighbors
        MIN_KF_FRAMES = 15
        merged = []
        for kf in validated_keyframes:
            duration = kf["end_frame"] - kf["start_frame"]
            if duration < MIN_KF_FRAMES:
                if merged:
                    # Absorb into previous keyframe
                    merged[-1]["end_frame"] = kf["end_frame"]
                else:
                    # Short first keyframe — skip it; gap-fill will cover its range
                    continue
            else:
                merged.append(kf)
        validated_keyframes = merged

        if not validated_keyframes:
            # All keyframes collapsed — fall back to neutral standing
            validated_keyframes = [{
                "start_frame": 0,
                "end_frame": duration_frames,
                "frame_id": manifest["frames"][0]["id"] if manifest["frames"] else "neutral_standingneutral",
                "transition": "cut",
            }]

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

    if len(validated_keyframes) > 8:
        logger.warning(
            "Scene %s has %d Eli keyframes (target max 8) — may look fidgety",
            scene_data.get("id"), len(validated_keyframes),
        )

    return {
        "id": result.get("id", scene_data.get("id")),
        "eli_overlay": eli_overlay,
    }
