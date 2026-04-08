"""Character frame library generation — creates Eli character overlay frames.

Generates ~50 frames (25 pose combos × 2 mouth states) for the Eli character
overlay system. Uses Gemini image generation with reference image chaining
for cross-frame consistency.
"""

import json
import logging
import shutil
from pathlib import Path
from typing import Any, Callable

from config import DATA_DIR
from integrations.google_image_client import generate_image

logger = logging.getLogger(__name__)

CHARACTER_DIR = DATA_DIR / "character"
FRAMES_DIR = CHARACTER_DIR / "frames"
MANIFEST_PATH = CHARACTER_DIR / "manifest.json"

# Character spec for prompt generation (from character.md)
CHARACTER_SPEC = """Character: "Eli" — young adult male, early-to-mid 20s, medium-brown skin, short slightly messy dark curly hair, round glasses with thin frames, warm brown eyes. Slightly large head relative to body (cartoon proportions — approx 1:5 head-to-body ratio), lean build. Wearing a muted teal crewneck t-shirt layered under an open charcoal gray zip hoodie, dark jeans, clean white sneakers. Flat 2D cartoon style, bold outlines, cel-shaded."""

FRAME_DEFINITIONS: list[dict[str, str]] = [
    # expression, pose, gesture, prompt_detail
    {"expression": "neutral", "pose": "standing_neutral", "gesture": "none", "prompt": "standing straight with arms relaxed at sides, neutral calm expression, looking forward"},
    {"expression": "smiling", "pose": "standing_neutral", "gesture": "none", "prompt": "standing straight with arms at sides, warm friendly smile, looking forward"},
    {"expression": "curious", "pose": "standing_neutral", "gesture": "none", "prompt": "standing straight, raised eyebrows with curious interested expression, head slightly tilted"},
    {"expression": "thinking", "pose": "hand_on_chin", "gesture": "none", "prompt": "one hand on chin in thinking pose, one eyebrow raised, slight smirk, thoughtful expression"},
    {"expression": "surprised", "pose": "leaning_back", "gesture": "none", "prompt": "leaning back slightly, mouth open in surprise, glasses slightly askew, wide eyes"},
    {"expression": "excited", "pose": "hands_up", "gesture": "none", "prompt": "both hands raised up, big excited grin, wide happy eyes, energetic pose"},
    {"expression": "serious", "pose": "standing_neutral", "gesture": "none", "prompt": "standing straight, concerned serious expression, slight frown, attentive eyes"},
    {"expression": "amused", "pose": "standing_neutral", "gesture": "none", "prompt": "standing with slight lean, amused smirk, one eyebrow slightly raised"},
    {"expression": "neutral", "pose": "explaining_forward", "gesture": "palm_up", "prompt": "one hand extended forward with palm up in explaining gesture, calm neutral expression"},
    {"expression": "smiling", "pose": "explaining_forward", "gesture": "palm_up", "prompt": "one hand extended forward with palm up, warm smile while explaining"},
    {"expression": "curious", "pose": "explaining_forward", "gesture": "finger_up", "prompt": "one hand raised with index finger up making a point, curious raised eyebrows"},
    {"expression": "excited", "pose": "hands_spread", "gesture": "none", "prompt": "both hands spread wide presenting something, excited wide eyes and big grin"},
    {"expression": "neutral", "pose": "pointing_side", "gesture": "pointing", "prompt": "one arm extended pointing to the side, neutral expression directing attention"},
    {"expression": "smiling", "pose": "pointing_side", "gesture": "pointing", "prompt": "one arm extended pointing to the side, friendly smile while directing attention"},
    {"expression": "thinking", "pose": "arms_crossed", "gesture": "none", "prompt": "arms crossed over chest, thoughtful expression, one eyebrow raised"},
    {"expression": "neutral", "pose": "shrugging", "gesture": "hands_spread", "prompt": "shoulders raised in shrug, hands spread palms up, neutral questioning expression"},
    {"expression": "excited", "pose": "counting_fingers", "gesture": "counting", "prompt": "one hand raised counting on fingers, excited expression listing things"},
    {"expression": "neutral", "pose": "waving", "gesture": "waving", "prompt": "one hand raised waving hello, friendly neutral expression"},
    {"expression": "serious", "pose": "explaining_forward", "gesture": "finger_up", "prompt": "one hand raised with index finger up, serious focused expression making an important point"},
    {"expression": "surprised", "pose": "hands_up", "gesture": "none", "prompt": "both hands raised near face, surprised wide eyes, mouth open in shock"},
    {"expression": "curious", "pose": "hand_on_chin", "gesture": "none", "prompt": "hand on chin, curious expression, head tilted, examining something interesting"},
    {"expression": "amused", "pose": "explaining_forward", "gesture": "palm_up", "prompt": "one hand extended with palm up, amused smirk, slight lean forward"},
    {"expression": "neutral", "pose": "relaxed", "gesture": "none", "prompt": "standing in relaxed pose, arms loosely at sides, calm neutral expression"},
    {"expression": "smiling", "pose": "relaxed", "gesture": "none", "prompt": "standing relaxed, arms loose at sides, warm gentle smile"},
    {"expression": "excited", "pose": "explaining_forward", "gesture": "palm_up", "prompt": "leaning forward with palm up explaining, excited expression, bright eyes"},
]


def _frame_id(definition: dict[str, str]) -> str:
    """Generate a frame ID from definition fields."""
    expr = definition["expression"]
    pose = definition["pose"].replace("_", "")
    return f"{expr}_{pose}"


def _make_unique_ids(definitions: list[dict[str, str]]) -> list[str]:
    """Generate unique frame IDs, appending suffix for duplicates."""
    ids: list[str] = []
    seen: dict[str, int] = {}
    for d in definitions:
        base = _frame_id(d)
        if base in seen:
            seen[base] += 1
            ids.append(f"{base}_{seen[base]}")
        else:
            seen[base] = 0
            ids.append(base)
    return ids


def _build_prompt(definition: dict[str, str], mouth_state: str, is_canonical: bool) -> str:
    """Build the image generation prompt for a frame."""
    mouth_desc = "mouth open, speaking" if mouth_state == "open" else "mouth closed"

    if is_canonical:
        return (
            f"Generate a full-body character illustration on a solid bright green (#00FF00) background.\n\n"
            f"{CHARACTER_SPEC}\n\n"
            f"Pose: {definition['prompt']}\n"
            f"Mouth: {mouth_desc}\n\n"
            f"IMPORTANT: Solid flat green (#00FF00) background with NO other elements. "
            f"Full body visible from head to feet. Flat 2D cartoon style with bold outlines."
        )
    else:
        return (
            f"Using the reference image as the character design reference, render the EXACT same character "
            f"in a different pose. Maintain identical character design, proportions, outfit colors, glasses, "
            f"hair style, and rendering style.\n\n"
            f"Pose: {definition['prompt']}\n"
            f"Mouth: {mouth_desc}\n\n"
            f"IMPORTANT: Solid flat green (#00FF00) background with NO other elements. "
            f"Full body visible from head to feet. Same flat 2D cartoon style as reference."
        )


def _remove_background(src_path: str, dst_path: str) -> None:
    """Remove background from generated image using rembg, falling back to simple copy."""
    try:
        from rembg import remove
        from PIL import Image
        import io

        with open(src_path, "rb") as f:
            input_bytes = f.read()
        output_bytes = remove(input_bytes)
        img = Image.open(io.BytesIO(output_bytes))
        img.save(dst_path, "PNG")
        logger.info("Background removed via rembg: %s", dst_path)
    except ImportError:
        logger.warning("rembg not installed, copying raw frame (green background preserved)")
        shutil.copy2(src_path, dst_path)
    except Exception:
        logger.warning("rembg failed, copying raw frame", exc_info=True)
        shutil.copy2(src_path, dst_path)


def get_manifest() -> dict | None:
    """Read the frame manifest, or None if not generated yet."""
    if not MANIFEST_PATH.exists():
        return None
    return json.loads(MANIFEST_PATH.read_text())


def generate_frame_library(
    on_progress: Callable[[int, int, str], None] | None = None,
) -> dict:
    """Generate the full Eli character frame library.

    on_progress(completed, total, current_label) is called after each frame.
    Returns the manifest dict.
    """
    FRAMES_DIR.mkdir(parents=True, exist_ok=True)

    frame_ids = _make_unique_ids(FRAME_DEFINITIONS)
    total = len(FRAME_DEFINITIONS) * 2  # 2 mouth states each
    completed = 0
    canonical_path: str | None = None

    manifest_frames: list[dict[str, Any]] = []

    for i, (defn, frame_id) in enumerate(zip(FRAME_DEFINITIONS, frame_ids)):
        is_canonical = (i == 0)

        for mouth_state in ["closed", "open"]:
            filename = f"{frame_id}_{mouth_state}.png"
            output_path = FRAMES_DIR / filename
            label = f"{frame_id} ({mouth_state})"

            logger.info("Generating frame %d/%d: %s", completed + 1, total, label)

            prompt = _build_prompt(defn, mouth_state, is_canonical and mouth_state == "closed")
            ref_path = None if (is_canonical and mouth_state == "closed") else canonical_path

            try:
                tmp_path = generate_image(
                    prompt=prompt,
                    width=768,
                    height=768,
                    reference_image_path=ref_path,
                )
                _remove_background(tmp_path, str(output_path))

                # Set canonical path from the first generated frame
                if is_canonical and mouth_state == "closed":
                    canonical_path = str(output_path)

            except Exception:
                logger.error("Failed to generate frame %s", label, exc_info=True)

            completed += 1
            if on_progress:
                on_progress(completed, total, label)

        manifest_frames.append({
            "id": frame_id,
            "file_closed": f"{frame_id}_closed.png",
            "file_open": f"{frame_id}_open.png",
            "expression": defn["expression"],
            "pose": defn["pose"],
            "gesture": defn["gesture"],
        })

    # Write manifest
    from datetime import datetime, timezone
    manifest = {
        "canonical_frame": f"{frame_ids[0]}_closed.png",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "frames": manifest_frames,
    }
    MANIFEST_PATH.write_text(json.dumps(manifest, indent=2))
    logger.info("Frame library generated: %d frames, manifest at %s", total, MANIFEST_PATH)

    return manifest


def regenerate_frame(frame_id: str) -> dict:
    """Regenerate a single frame (both mouth states) using canonical reference.

    Returns the updated frame entry.
    """
    manifest = get_manifest()
    if not manifest:
        raise RuntimeError("No frame library exists. Generate the full library first.")

    # Find the frame definition
    frame_ids = _make_unique_ids(FRAME_DEFINITIONS)
    defn_idx = None
    for i, fid in enumerate(frame_ids):
        if fid == frame_id:
            defn_idx = i
            break

    if defn_idx is None:
        raise ValueError(f"Unknown frame_id: {frame_id}")

    defn = FRAME_DEFINITIONS[defn_idx]
    canonical_path = str(FRAMES_DIR / manifest["canonical_frame"])

    for mouth_state in ["closed", "open"]:
        filename = f"{frame_id}_{mouth_state}.png"
        output_path = FRAMES_DIR / filename

        prompt = _build_prompt(defn, mouth_state, False)
        tmp_path = generate_image(
            prompt=prompt,
            width=768,
            height=768,
            reference_image_path=canonical_path,
        )
        _remove_background(tmp_path, str(output_path))

    # Update manifest timestamp
    manifest["generated_at"] = __import__("datetime").datetime.now(
        __import__("datetime").timezone.utc
    ).isoformat()
    MANIFEST_PATH.write_text(json.dumps(manifest, indent=2))

    return {
        "id": frame_id,
        "file_closed": f"{frame_id}_closed.png",
        "file_open": f"{frame_id}_open.png",
        "expression": defn["expression"],
        "pose": defn["pose"],
        "gesture": defn["gesture"],
    }
