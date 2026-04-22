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
from prompts import ELI_ANIMATOR_SYSTEM

logger = logging.getLogger(__name__)


def generate_scene_eli(scene_data: dict, script_id: str | None = None, previous_corner: str | None = None) -> dict:
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

    user_payload: dict = {
        "scene": scene_data,
        "available_frames": available_frames,
    }
    if previous_corner:
        user_payload["previous_corner"] = previous_corner

    user_message = json.dumps(user_payload, indent=2)

    response = chat(
        system=ELI_ANIMATOR_SYSTEM.template,
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

    # Parse corner assignment — enforce variation from previous corner
    valid_corners = {"TL", "TR", "BL", "BR"}
    corner = eli_overlay.get("corner", "BR")
    if corner not in valid_corners:
        corner = "BR"

    if previous_corner and corner == previous_corner:
        opposite_side = {"TL": "BR", "TR": "BL", "BL": "TR", "BR": "TL"}
        corner = opposite_side.get(previous_corner, "BR")
        logger.info("Overrode Claude's corner %s → %s (was same as previous)", eli_overlay.get("corner"), corner)

    eli_overlay["corner"] = corner

    if len(validated_keyframes) > 8:
        logger.warning(
            "Scene %s has %d Eli keyframes (target max 8) — may look fidgety",
            scene_data.get("id"), len(validated_keyframes),
        )

    return {
        "id": result.get("id", scene_data.get("id")),
        "eli_overlay": eli_overlay,
    }
