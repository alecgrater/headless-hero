"""Character frame library generation — creates Eli character overlay frames.

Generates ~300 frames (150 pose combos x 2 mouth states) for the Eli character
overlay system. Uses Gemini image generation with reference image chaining
for cross-frame consistency. Supports reference candidate selection workflow.
"""

import json
import logging
import shutil
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable

from config import DATA_DIR
from integrations.google_image_client import generate_image
from prompts import (
    CHARACTER_SPEC,
    FRAME_DEFINITIONS,
    FRAMING_INSTRUCTION,
    GREEN_BG_INSTRUCTION,
    REFERENCE_CONSISTENCY_INSTRUCTION,
    THUMBNAIL_FRAME_DEFINITIONS,
    VARIANT_PROMPTS,
    build_frame_prompt,
    build_variant_prompt,
)

logger = logging.getLogger(__name__)

# --- Variant tier configuration ---
TIER_1_EXPRESSIONS = {"neutral", "thinking", "excited", "explaining", "curious", "smiling"}
TIER_2_EXPRESSIONS = {"surprised", "confused", "skeptical", "serious", "worried"}


def variant_count_for_expression(expression: str) -> int:
    """Return how many body micro-variants a given expression should have."""
    if expression in TIER_1_EXPRESSIONS:
        return 5
    if expression in TIER_2_EXPRESSIONS:
        return 3
    return 1


# Local alias for private usage
_VARIANT_PROMPTS = VARIANT_PROMPTS

CHARACTER_DIR = DATA_DIR / "character"
FRAMES_DIR = CHARACTER_DIR / "frames"
REFERENCES_DIR = CHARACTER_DIR / "references"
MANIFEST_PATH = CHARACTER_DIR / "manifest.json"
REFERENCE_SELECTION_PATH = CHARACTER_DIR / "reference_selection.json"
SELECTED_REFERENCE_PATH = FRAMES_DIR / "selected_reference.png"

# Local aliases for private usage
_build_prompt = build_frame_prompt
_build_variant_prompt = build_variant_prompt


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


def _chroma_key_green(img: "Image.Image") -> "Image.Image":
    """Replace green-ish background pixels with transparent using numpy.

    Handles both pure green (#00FF00) and the muted sage/pastel greens
    that Gemini often generates instead. Uses HSV color space for robust
    detection of any green-dominant background.
    """
    import numpy as np

    arr = np.array(img.convert("RGBA"), dtype=np.uint8)
    rgb = arr[:, :, :3].astype(np.float32)
    r, g, b = rgb[:, :, 0], rgb[:, :, 1], rgb[:, :, 2]

    # Method 1: Pure green (original) — g high, r and b low
    pure_green = (g > 180) & (r < 100) & (b < 100)

    # Method 2: Muted/sage green — green is dominant channel by a margin
    # Catches backgrounds like (140, 190, 130), (120, 180, 120), etc.
    green_dominant = (g > 120) & (g > r + 20) & (g > b + 20) & (r < 200) & (b < 200)

    # Method 3: Pastel/light green — lighter backgrounds where all channels are
    # high but green still leads. E.g. (170, 210, 160)
    pastel_green = (g > 150) & (g > r) & (g > b) & (r > 100) & (b > 100) & ((g - r) > 10) & ((g - b) > 10)

    mask = pure_green | green_dominant | pastel_green
    pixels_removed = int(np.sum(mask))
    total_pixels = arr.shape[0] * arr.shape[1]

    logger.info(
        "Chroma key: %d/%d pixels (%.1f%%) matched green — pure=%d, dominant=%d, pastel=%d",
        pixels_removed, total_pixels, pixels_removed / total_pixels * 100,
        int(np.sum(pure_green)), int(np.sum(green_dominant)), int(np.sum(pastel_green)),
    )

    arr[mask, 3] = 0  # set alpha to 0
    from PIL import Image as PILImage
    return PILImage.fromarray(arr, "RGBA")


def _has_background(img: "Image.Image", filename: str = "") -> bool:
    """Detect whether an RGBA image still has a non-transparent background.

    Samples corners and edges. Returns True if significant opaque areas are
    found in regions that should be transparent background.
    """
    import numpy as np

    w, h = img.size
    arr = np.array(img.convert("RGBA"), dtype=np.uint8)
    alpha = arr[:, :, 3]

    # Sample multiple points in corners and edges (areas likely to be background)
    sample_points = [
        # Corners (multiple points per corner for robustness)
        (2, 2), (5, 5), (10, 10),
        (w - 3, 2), (w - 6, 5), (w - 11, 10),
        (2, h - 3), (5, h - 6), (10, h - 11),
        (w - 3, h - 3), (w - 6, h - 6), (w - 11, h - 11),
        # Edge midpoints
        (w // 2, 2), (w // 2, h - 3),  # top/bottom center
        (2, h // 2), (w - 3, h // 2),  # left/right center
    ]

    opaque_count = 0
    for x, y in sample_points:
        if 0 <= x < w and 0 <= y < h and alpha[y, x] > 200:
            opaque_count += 1

    # Also check what fraction of the top 10 rows are opaque (a strong background signal)
    top_strip = alpha[:10, :]
    top_opaque_frac = float(np.mean(top_strip > 200))

    # Check overall image transparency ratio
    total_opaque_frac = float(np.mean(alpha > 200))

    has_bg = opaque_count >= 8 or top_opaque_frac > 0.8

    logger.info(
        "Background check [%s]: opaque_samples=%d/%d, top_strip_opaque=%.1f%%, "
        "total_opaque=%.1f%% → %s",
        filename, opaque_count, len(sample_points),
        top_opaque_frac * 100, total_opaque_frac * 100,
        "HAS BACKGROUND" if has_bg else "ok",
    )

    return has_bg


def _check_body_coverage(img: "Image.Image", filename: str = "") -> bool:
    """Check if the image has enough opaque content to include a body (not just a head).

    Returns True if the image likely has a full chest-up character,
    False if it's probably just a floating head.
    """
    import numpy as np

    arr = np.array(img.convert("RGBA"), dtype=np.uint8)
    alpha = arr[:, :, 3]
    h, w = alpha.shape

    # Check the lower half of the image — a chest-up frame should have
    # significant opaque content in the bottom half (shoulders/chest)
    lower_half = alpha[h // 2 :, :]
    lower_opaque_frac = float(np.mean(lower_half > 50))

    # Also check overall opaque fraction
    total_opaque_frac = float(np.mean(alpha > 50))

    # A full chest-up character should have at least 8% opaque in the lower half
    # and at least 10% opaque overall. A floating head typically has < 5% lower half.
    has_body = lower_opaque_frac > 0.08 and total_opaque_frac > 0.10

    logger.info(
        "Body coverage check [%s]: lower_half_opaque=%.1f%%, total_opaque=%.1f%% → %s",
        filename,
        lower_opaque_frac * 100,
        total_opaque_frac * 100,
        "HAS BODY" if has_body else "HEAD ONLY",
    )

    return has_body


def _remove_background(src_path: str, dst_path: str) -> None:
    """Remove background from generated image using chroma key first, rembg fallback.

    Chroma key is preferred because we request a green (#00FF00) background,
    and rembg can be overly aggressive — stripping the character's body/arms
    along with the background, leaving only a floating head.
    """
    from PIL import Image

    src_name = src_path.rsplit("/", 1)[-1] if "/" in src_path else src_path
    logger.info("Background removal starting: %s → %s", src_name, dst_path)

    img = Image.open(src_path).convert("RGBA")

    # Step 1: Try chroma key first (preserves body/arms much better)
    chroma_result = _chroma_key_green(img)

    if not _has_background(chroma_result, f"chroma-key:{src_name}"):
        logger.info("Chroma key fully removed background: %s", src_name)
        chroma_result.save(dst_path, "PNG")
        return

    # Step 2: Chroma key left residual background — try rembg
    logger.warning("Chroma key left residual background, trying rembg: %s", src_name)
    try:
        import io
        from rembg import remove

        with open(src_path, "rb") as f:
            input_bytes = f.read()

        output_bytes = remove(input_bytes)
        rembg_result = Image.open(io.BytesIO(output_bytes)).convert("RGBA")

        # Check if rembg preserved the body or just kept the head
        if _check_body_coverage(rembg_result, f"rembg:{src_name}"):
            # rembg kept the body — use its result, apply chroma key for any residual green
            if _has_background(rembg_result, f"rembg-output:{src_name}"):
                rembg_result = _chroma_key_green(rembg_result)
            rembg_result.save(dst_path, "PNG")
            logger.info("Used rembg result (body preserved): %s", src_name)
        else:
            # rembg stripped the body — fall back to chroma key result even if imperfect
            logger.warning(
                "rembg stripped body/arms, falling back to chroma key result: %s", src_name
            )
            chroma_result.save(dst_path, "PNG")
    except (ImportError, Exception):
        logger.warning("rembg unavailable/failed, using chroma key result: %s", src_name, exc_info=True)
        chroma_result.save(dst_path, "PNG")


def get_manifest() -> dict | None:
    """Read the frame manifest, or None if not generated yet.

    Backfills variant_count for frames generated before the variant system was added.
    """
    if not MANIFEST_PATH.exists():
        return None
    manifest = json.loads(MANIFEST_PATH.read_text())
    dirty = False
    for frame in manifest.get("frames", []):
        if "variant_count" not in frame:
            frame["variant_count"] = variant_count_for_expression(frame.get("expression", ""))
            dirty = True
    if dirty:
        MANIFEST_PATH.write_text(json.dumps(manifest, indent=2))
    return manifest


def clear_all_frames() -> dict[str, int]:
    """Delete all frames, references, manifest, and selection. Returns counts."""
    deleted_frames = 0
    deleted_refs = 0

    # Delete all frame PNGs (including selected_reference.png)
    if FRAMES_DIR.exists():
        for f in FRAMES_DIR.glob("*.png"):
            f.unlink()
            deleted_frames += 1

    # Delete references
    if REFERENCES_DIR.exists():
        for f in REFERENCES_DIR.glob("*.png"):
            f.unlink()
            deleted_refs += 1

    # Delete manifest and selection metadata
    if MANIFEST_PATH.exists():
        MANIFEST_PATH.unlink()
    if REFERENCE_SELECTION_PATH.exists():
        REFERENCE_SELECTION_PATH.unlink()

    logger.info("Cleared all frames (%d) and references (%d)", deleted_frames, deleted_refs)
    return {"deleted_frames": deleted_frames, "deleted_references": deleted_refs}


# ---------------------------------------------------------------------------
# Reference candidate generation & selection
# ---------------------------------------------------------------------------

# Subtle variation dimensions for reference candidates
_REFERENCE_VARIATIONS = [
    "slightly warmer color palette with golden undertones",
    "slightly cooler color palette with blue undertones",
    "thinner line weight with more delicate outlines",
    "thicker bolder line weight with chunky outlines",
    "slightly rounder face shape and softer features",
    "slightly more angular face shape and sharper features",
    "slightly larger eyes in anime-influenced proportion",
    "slightly smaller more realistic eye proportions",
    "more voluminous fluffy curly hair",
    "tighter neater shorter curly hair",
    "slightly more saturated vibrant clothing colors",
    "slightly more muted desaturated clothing colors",
    "softer cel-shading with gentle gradients",
    "harder cel-shading with sharp flat color blocks",
    "standard balanced design as described",
]


def generate_reference_candidates(
    count: int = 15,
    on_progress: Callable[[int, int, str], None] | None = None,
) -> list[dict[str, Any]]:
    """Generate reference candidate images for user selection.

    Creates `count` independent character images with subtle style variations.
    No reference image chaining — each is generated from scratch.
    No background removal — user is just picking the look.

    Returns list of {"filename": "reference_01.png", "index": 1}.
    """
    REFERENCES_DIR.mkdir(parents=True, exist_ok=True)

    # Clear existing candidates
    for existing in REFERENCES_DIR.glob("reference_*.png"):
        existing.unlink()

    candidates: list[dict[str, Any]] = []

    for i in range(count):
        idx = i + 1
        filename = f"reference_{idx:02d}.png"
        output_path = REFERENCES_DIR / filename
        label = f"Reference candidate {idx}/{count}"

        variation = _REFERENCE_VARIATIONS[i % len(_REFERENCE_VARIATIONS)]

        prompt = (
            f"Generate a chest-up character illustration on a solid bright green (#00FF00) background.\n\n"
            f"{CHARACTER_SPEC}\n\n"
            f"Pose: shoulders relaxed, neutral calm expression, looking forward at camera\n"
            f"Mouth: mouth closed\n\n"
            f"Style variation: {variation}\n\n"
            f"IMPORTANT: {GREEN_BG_INSTRUCTION} "
            f"{FRAMING_INSTRUCTION} "
            f"16:9 aspect ratio composition. Flat 2D cartoon style with bold outlines."
        )

        logger.info("Generating reference candidate %d/%d", idx, count)

        try:
            tmp_path = generate_image(
                prompt=prompt,
                width=768,
                height=432,
                reference_image_path=None,
            )
            shutil.copy2(tmp_path, str(output_path))
            candidates.append({"filename": filename, "index": idx})
        except Exception:
            logger.error("Failed to generate reference candidate %d", idx, exc_info=True)

        if on_progress:
            on_progress(idx, count, label)

    return candidates


def get_reference_candidates() -> list[str]:
    """Return sorted list of reference candidate filenames."""
    if not REFERENCES_DIR.exists():
        return []
    return sorted(f.name for f in REFERENCES_DIR.glob("reference_*.png"))


def get_selected_reference() -> str | None:
    """Return filename of selected reference, or None if none selected."""
    if not REFERENCE_SELECTION_PATH.exists():
        return None
    data = json.loads(REFERENCE_SELECTION_PATH.read_text())
    return data.get("selected")


def select_reference(filename: str) -> str:
    """Select a reference candidate as the canonical reference for frame generation.

    Copies the chosen file to FRAMES_DIR/selected_reference.png and writes selection metadata.
    Returns the path to the selected reference.
    """
    src = REFERENCES_DIR / filename
    if not src.exists():
        raise FileNotFoundError(f"Reference candidate not found: {filename}")

    FRAMES_DIR.mkdir(parents=True, exist_ok=True)
    shutil.copy2(str(src), str(SELECTED_REFERENCE_PATH))

    REFERENCE_SELECTION_PATH.write_text(json.dumps({
        "selected": filename,
        "selected_at": datetime.now(timezone.utc).isoformat(),
    }, indent=2))

    logger.info("Selected reference: %s -> %s", filename, SELECTED_REFERENCE_PATH)
    return str(SELECTED_REFERENCE_PATH)


def generate_frame_library(
    reference_path: str | None = None,
    on_progress: Callable[[int, int, str], None] | None = None,
) -> dict:
    """Generate the full Eli character frame library.

    If reference_path is provided, use it as the canonical reference for ALL frames
    (skip auto-generating the first frame as canonical).
    If None, check for selected_reference.png, then fall back to auto-generating first frame.

    on_progress(completed, total, current_label) is called after each frame.
    Returns the manifest dict.
    """
    FRAMES_DIR.mkdir(parents=True, exist_ok=True)

    # Resolve reference path
    if reference_path is None and SELECTED_REFERENCE_PATH.exists():
        reference_path = str(SELECTED_REFERENCE_PATH)

    frame_ids = _make_unique_ids(FRAME_DEFINITIONS)
    total = len(FRAME_DEFINITIONS) * 2  # 2 mouth states each
    completed = 0
    canonical_path: str | None = reference_path

    manifest_frames: list[dict[str, Any]] = []

    for i, (defn, frame_id) in enumerate(zip(FRAME_DEFINITIONS, frame_ids)):
        # Only treat first frame as canonical if no reference was provided
        is_first_without_ref = (i == 0 and reference_path is None)

        for mouth_state in ["closed", "open"]:
            filename = f"{frame_id}_{mouth_state}.png"
            output_path = FRAMES_DIR / filename
            label = f"{frame_id} ({mouth_state})"

            logger.info("Generating frame %d/%d: %s", completed + 1, total, label)

            needs_canonical_prompt = is_first_without_ref and mouth_state == "closed"
            prompt = _build_prompt(defn, mouth_state, needs_canonical_prompt)
            ref_path = None if needs_canonical_prompt else canonical_path

            try:
                tmp_path = generate_image(
                    prompt=prompt,
                    width=768,
                    height=432,
                    reference_image_path=ref_path,
                )
                _remove_background(tmp_path, str(output_path))

                # Set canonical path from the first generated frame (only if no reference provided)
                if needs_canonical_prompt:
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
            "variant_count": variant_count_for_expression(defn["expression"]),
        })

    # Write manifest
    manifest = {
        "canonical_frame": f"{frame_ids[0]}_closed.png",
        "reference_source": "selected_reference" if reference_path else "auto_generated",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "frames": manifest_frames,
    }
    MANIFEST_PATH.write_text(json.dumps(manifest, indent=2))
    logger.info("Frame library generated: %d frames, manifest at %s", total, MANIFEST_PATH)

    return manifest


def regenerate_frame(frame_id: str) -> dict:
    """Regenerate a single frame (both mouth states) using canonical reference.

    Checks for selected_reference.png first, then falls back to manifest canonical_frame.
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

    # Prefer selected reference over manifest canonical
    if SELECTED_REFERENCE_PATH.exists():
        canonical_path = str(SELECTED_REFERENCE_PATH)
    else:
        canonical_path = str(FRAMES_DIR / manifest["canonical_frame"])

    for mouth_state in ["closed", "open"]:
        filename = f"{frame_id}_{mouth_state}.png"
        output_path = FRAMES_DIR / filename

        prompt = _build_prompt(defn, mouth_state, False)
        tmp_path = generate_image(
            prompt=prompt,
            width=768,
            height=432,
            reference_image_path=canonical_path,
        )
        _remove_background(tmp_path, str(output_path))

        # Validate body coverage — retry once if only a floating head remains
        from PIL import Image as PILImage
        result_img = PILImage.open(str(output_path)).convert("RGBA")
        if not _check_body_coverage(result_img, f"regenerate:{filename}"):
            logger.warning("Body missing after generation, retrying: %s", filename)
            tmp_path = generate_image(
                prompt=prompt,
                width=768,
                height=432,
                reference_image_path=canonical_path,
            )
            _remove_background(tmp_path, str(output_path))

    # Update manifest timestamp
    manifest["generated_at"] = datetime.now(timezone.utc).isoformat()
    MANIFEST_PATH.write_text(json.dumps(manifest, indent=2))

    return {
        "id": frame_id,
        "file_closed": f"{frame_id}_closed.png",
        "file_open": f"{frame_id}_open.png",
        "expression": defn["expression"],
        "pose": defn["pose"],
        "gesture": defn["gesture"],
        "variant_count": variant_count_for_expression(defn["expression"]),
    }


def count_missing_frames() -> int:
    """Count how many frame definitions are missing one or both PNG files on disk."""
    frame_ids = _make_unique_ids(FRAME_DEFINITIONS)
    missing = 0
    for frame_id in frame_ids:
        closed = FRAMES_DIR / f"{frame_id}_closed.png"
        opened = FRAMES_DIR / f"{frame_id}_open.png"
        if not closed.exists() or not opened.exists():
            missing += 1
    return missing


def count_existing_variant_frames() -> int:
    """Count how many variant frame files already exist on disk."""
    manifest = get_manifest()
    if not manifest:
        return 0
    frame_ids = _make_unique_ids(FRAME_DEFINITIONS)
    frames_by_id = {f["id"]: f for f in manifest.get("frames", [])}
    existing = 0
    for frame_id in frame_ids:
        frame_entry = frames_by_id.get(frame_id)
        if not frame_entry:
            continue
        vc = frame_entry.get("variant_count", 1)
        if vc <= 1:
            continue
        for v in range(2, vc + 1):
            closed = FRAMES_DIR / f"{frame_id}_v{v}_closed.png"
            opened = FRAMES_DIR / f"{frame_id}_v{v}_open.png"
            if closed.exists() and opened.exists():
                existing += 1
    return existing


def count_total_variant_frames() -> int:
    """Count total expected variant frames (frames with variant_count > 1)."""
    manifest = get_manifest()
    if not manifest:
        return 0
    total = 0
    for frame in manifest.get("frames", []):
        vc = frame.get("variant_count", 1)
        if vc > 1:
            total += vc - 1  # variants 2..N
    return total


def generate_missing_frames(
    on_progress: Callable[[int, int, str], None] | None = None,
) -> dict:
    """Generate only frames whose PNG files are missing from disk.

    Skips any frame where both closed and open mouth PNGs already exist.
    Uses selected_reference.png as the canonical reference.
    Returns the manifest dict.
    """
    FRAMES_DIR.mkdir(parents=True, exist_ok=True)

    # Resolve reference
    if SELECTED_REFERENCE_PATH.exists():
        canonical_path = str(SELECTED_REFERENCE_PATH)
    else:
        manifest = get_manifest()
        if manifest and manifest.get("canonical_frame"):
            canonical_path = str(FRAMES_DIR / manifest["canonical_frame"])
        else:
            raise RuntimeError("No reference image available. Select a reference first.")

    frame_ids = _make_unique_ids(FRAME_DEFINITIONS)

    # Identify which frames need generation
    missing: list[tuple[int, str]] = []  # (defn_index, frame_id)
    for i, frame_id in enumerate(frame_ids):
        closed = FRAMES_DIR / f"{frame_id}_closed.png"
        opened = FRAMES_DIR / f"{frame_id}_open.png"
        if not closed.exists() or not opened.exists():
            missing.append((i, frame_id))

    total = len(missing) * 2  # 2 mouth states each
    completed = 0

    for defn_idx, frame_id in missing:
        defn = FRAME_DEFINITIONS[defn_idx]

        for mouth_state in ["closed", "open"]:
            filename = f"{frame_id}_{mouth_state}.png"
            output_path = FRAMES_DIR / filename
            label = f"{frame_id} ({mouth_state})"

            # Skip if this specific file already exists (e.g. only one mouth state was missing)
            if output_path.exists():
                completed += 1
                if on_progress:
                    on_progress(completed, total, label)
                continue

            logger.info("Generating missing frame %d/%d: %s", completed + 1, total, label)

            prompt = _build_prompt(defn, mouth_state, False)

            try:
                tmp_path = generate_image(
                    prompt=prompt,
                    width=768,
                    height=432,
                    reference_image_path=canonical_path,
                )
                _remove_background(tmp_path, str(output_path))
            except Exception:
                logger.error("Failed to generate frame %s", label, exc_info=True)

            completed += 1
            if on_progress:
                on_progress(completed, total, label)

    # Rebuild manifest with all frame definitions
    manifest_frames = []
    for frame_id, defn in zip(frame_ids, FRAME_DEFINITIONS):
        manifest_frames.append({
            "id": frame_id,
            "file_closed": f"{frame_id}_closed.png",
            "file_open": f"{frame_id}_open.png",
            "expression": defn["expression"],
            "pose": defn["pose"],
            "gesture": defn["gesture"],
            "variant_count": variant_count_for_expression(defn["expression"]),
        })

    manifest = {
        "canonical_frame": f"{frame_ids[0]}_closed.png",
        "reference_source": "selected_reference",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "frames": manifest_frames,
    }
    MANIFEST_PATH.write_text(json.dumps(manifest, indent=2))
    logger.info("Missing frames generated: %d frames filled in", len(missing))

    return manifest


def load_variant_counts() -> dict[str, int]:
    """Read manifest and return a map of {frame_id: variant_count}.

    Checks actual files on disk rather than trusting manifest values,
    so we never return a count for variants that don't exist.

    Returns empty dict if manifest doesn't exist.
    """
    manifest = get_manifest()
    if not manifest:
        return {}
    frames_dir = FRAMES_DIR
    counts: dict[str, int] = {}
    for f in manifest.get("frames", []):
        fid = f["id"]
        actual = 1  # base file always exists
        for v in range(2, f.get("variant_count", 1) + 1):
            if (frames_dir / f"{fid}_v{v}_closed.png").exists():
                actual = v
            else:
                break
        counts[fid] = actual
    return counts


def generate_variants(
    on_progress: Callable[[int, int, str], None] | None = None,
) -> dict:
    """Generate body micro-variants for all frames that need them.

    Reads the manifest to find frames with variant_count > 1, then generates
    variants 2..N for each. Uses the existing frame (variant 1) as reference
    image for consistency.

    Returns the updated manifest.
    """
    manifest = get_manifest()
    if not manifest:
        raise RuntimeError("No frame library exists. Generate the full library first.")

    frame_ids = _make_unique_ids(FRAME_DEFINITIONS)
    frames_by_id = {f["id"]: f for f in manifest.get("frames", [])}

    # Build work list: (defn_index, frame_id, variant_num)
    work: list[tuple[int, str, int]] = []
    for i, frame_id in enumerate(frame_ids):
        frame_entry = frames_by_id.get(frame_id)
        if not frame_entry:
            continue
        vc = frame_entry.get("variant_count", 1)
        if vc <= 1:
            continue
        for v in range(2, vc + 1):
            # Skip if variant files already exist
            suffix = f"_v{v}"
            closed = FRAMES_DIR / f"{frame_id}{suffix}_closed.png"
            opened = FRAMES_DIR / f"{frame_id}{suffix}_open.png"
            if closed.exists() and opened.exists():
                continue
            work.append((i, frame_id, v))

    total = len(work) * 2  # 2 mouth states each
    completed = 0

    for defn_idx, frame_id, variant_num in work:
        defn = FRAME_DEFINITIONS[defn_idx]
        variant_suffix = f"_v{variant_num}"

        # Use the original frame (variant 1, closed mouth) as reference for consistency
        ref_path = str(FRAMES_DIR / f"{frame_id}_closed.png")
        if not Path(ref_path).exists():
            logger.warning("Original frame missing for %s, skipping variants", frame_id)
            completed += 2
            if on_progress:
                on_progress(completed, total, f"{frame_id} v{variant_num} (skipped)")
            continue

        for mouth_state in ["closed", "open"]:
            filename = f"{frame_id}{variant_suffix}_{mouth_state}.png"
            output_path = FRAMES_DIR / filename
            label = f"{frame_id} v{variant_num} ({mouth_state})"

            logger.info("Generating variant %d/%d: %s", completed + 1, total, label)

            prompt = _build_variant_prompt(defn, mouth_state, variant_num)

            try:
                tmp_path = generate_image(
                    prompt=prompt,
                    width=768,
                    height=432,
                    reference_image_path=ref_path,
                )
                _remove_background(tmp_path, str(output_path))
            except Exception:
                logger.error("Failed to generate variant %s", label, exc_info=True)

            completed += 1
            if on_progress:
                on_progress(completed, total, label)

    # Update manifest timestamp
    manifest["generated_at"] = datetime.now(timezone.utc).isoformat()
    MANIFEST_PATH.write_text(json.dumps(manifest, indent=2))
    logger.info("Variant generation complete: %d variant frames generated", len(work) * 2)

    return manifest


def generate_frame_variants(frame_id: str) -> dict:
    """Generate variants for a single frame.

    Uses the original frame (variant 1) as reference.
    Returns the updated frame entry.
    """
    manifest = get_manifest()
    if not manifest:
        raise RuntimeError("No frame library exists. Generate the full library first.")

    frame_ids = _make_unique_ids(FRAME_DEFINITIONS)
    defn_idx = None
    for i, fid in enumerate(frame_ids):
        if fid == frame_id:
            defn_idx = i
            break

    if defn_idx is None:
        raise ValueError(f"Unknown frame_id: {frame_id}")

    defn = FRAME_DEFINITIONS[defn_idx]
    vc = variant_count_for_expression(defn["expression"])

    if vc <= 1:
        raise ValueError(f"Frame {frame_id} (expression: {defn['expression']}) has no variants (tier 3)")

    ref_path = str(FRAMES_DIR / f"{frame_id}_closed.png")
    if not Path(ref_path).exists():
        raise RuntimeError(f"Original frame not found: {ref_path}")

    for v in range(2, vc + 1):
        variant_suffix = f"_v{v}"
        for mouth_state in ["closed", "open"]:
            filename = f"{frame_id}{variant_suffix}_{mouth_state}.png"
            output_path = FRAMES_DIR / filename

            prompt = _build_variant_prompt(defn, mouth_state, v)
            tmp_path = generate_image(
                prompt=prompt,
                width=768,
                height=432,
                reference_image_path=ref_path,
            )
            _remove_background(tmp_path, str(output_path))

    # Update manifest timestamp
    manifest["generated_at"] = datetime.now(timezone.utc).isoformat()
    MANIFEST_PATH.write_text(json.dumps(manifest, indent=2))

    return {
        "id": frame_id,
        "file_closed": f"{frame_id}_closed.png",
        "file_open": f"{frame_id}_open.png",
        "expression": defn["expression"],
        "pose": defn["pose"],
        "gesture": defn["gesture"],
        "variant_count": vc,
    }


def reprocess_backgrounds(
    on_progress: Callable[[int, int, str], None] | None = None,
) -> int:
    """Re-run background removal on frames that still have non-transparent backgrounds.

    Scans all PNGs in FRAMES_DIR (excluding selected_reference.png),
    uses multi-point sampling to detect backgrounds, and re-runs chroma key
    + rembg on affected frames.

    Returns count of frames reprocessed.
    """
    from PIL import Image

    if not FRAMES_DIR.exists():
        logger.warning("FRAMES_DIR does not exist: %s", FRAMES_DIR)
        return 0

    all_pngs = [
        f for f in sorted(FRAMES_DIR.glob("*.png"))
        if f.name != "selected_reference.png"
    ]
    total = len(all_pngs)
    reprocessed = 0
    skipped = 0

    logger.info("=== Background reprocessing started: scanning %d frames in %s ===", total, FRAMES_DIR)

    for i, png_path in enumerate(all_pngs):
        label = png_path.stem
        try:
            img = Image.open(str(png_path)).convert("RGBA")
            logger.debug("Checking frame %d/%d: %s (size=%s)", i + 1, total, png_path.name, img.size)

            if _has_background(img, png_path.name):
                logger.info(">>> Reprocessing frame with background: %s", png_path.name)

                # First try chroma key (fast, handles green backgrounds)
                fixed = _chroma_key_green(img)

                if _has_background(fixed, f"after-chroma:{png_path.name}"):
                    # Chroma key wasn't enough, try rembg
                    logger.info("Chroma key insufficient for %s, trying rembg", png_path.name)
                    try:
                        from rembg import remove
                        import io

                        with open(str(png_path), "rb") as f:
                            input_bytes = f.read()
                        output_bytes = remove(input_bytes)
                        fixed = Image.open(io.BytesIO(output_bytes)).convert("RGBA")

                        if _has_background(fixed, f"after-rembg:{png_path.name}"):
                            # rembg wasn't enough either, apply chroma key on top
                            logger.warning("rembg insufficient, applying chroma key on rembg output: %s", png_path.name)
                            fixed = _chroma_key_green(fixed)
                    except ImportError:
                        logger.warning("rembg not installed, using chroma key result for %s", png_path.name)
                    except Exception:
                        logger.error("rembg failed for %s, using chroma key result", png_path.name, exc_info=True)

                fixed.save(str(png_path), "PNG")
                reprocessed += 1
                logger.info("Saved reprocessed frame: %s", png_path.name)
            else:
                skipped += 1
                logger.debug("Frame OK (no background detected): %s", png_path.name)
        except Exception:
            logger.error("Failed to check/reprocess %s", png_path.name, exc_info=True)

        if on_progress:
            on_progress(i + 1, total, label)

    logger.info(
        "=== Background reprocessing complete: %d reprocessed, %d already OK, %d total ===",
        reprocessed, skipped, total,
    )

    # Always update manifest timestamp so frontend cache-busting refreshes images
    if MANIFEST_PATH.exists():
        manifest = json.loads(MANIFEST_PATH.read_text())
        manifest["generated_at"] = datetime.now(timezone.utc).isoformat()
        MANIFEST_PATH.write_text(json.dumps(manifest, indent=2))
        logger.info("Updated manifest timestamp for cache busting")

    return reprocessed


# ---------------------------------------------------------------------------
# Thumbnail frame generation
# ---------------------------------------------------------------------------


def _make_unique_thumb_ids(definitions: list[dict[str, str]]) -> list[str]:
    """Generate unique frame IDs for thumbnail frames, prefixed with 'thumb_'."""
    ids: list[str] = []
    seen: dict[str, int] = {}
    for d in definitions:
        base = f"thumb_{_frame_id(d)}"
        if base in seen:
            seen[base] += 1
            ids.append(f"{base}_{seen[base]}")
        else:
            seen[base] = 0
            ids.append(base)
    return ids


def get_thumbnail_frames() -> list[dict[str, Any]]:
    """Return the thumbnail_frames list from manifest, or [] if none exist."""
    manifest = get_manifest()
    if not manifest:
        return []
    return manifest.get("thumbnail_frames", [])


def generate_thumbnail_frames(
    on_progress: Callable[[int, int, str], None] | None = None,
) -> dict:
    """Generate the 9 high-CTR thumbnail expression frames (18 images total).

    Requires a selected reference image. Writes results to manifest["thumbnail_frames"].
    Returns the updated manifest dict.
    """
    FRAMES_DIR.mkdir(parents=True, exist_ok=True)

    # Resolve reference
    if SELECTED_REFERENCE_PATH.exists():
        canonical_path = str(SELECTED_REFERENCE_PATH)
    else:
        manifest = get_manifest()
        if manifest and manifest.get("canonical_frame"):
            canonical_path = str(FRAMES_DIR / manifest["canonical_frame"])
        else:
            raise RuntimeError("No reference image available. Select a reference first.")

    thumb_ids = _make_unique_thumb_ids(THUMBNAIL_FRAME_DEFINITIONS)
    total = len(THUMBNAIL_FRAME_DEFINITIONS) * 2  # 2 mouth states each
    completed = 0

    thumb_frames: list[dict[str, Any]] = []

    for defn, frame_id in zip(THUMBNAIL_FRAME_DEFINITIONS, thumb_ids):
        for mouth_state in ["closed", "open"]:
            filename = f"{frame_id}_{mouth_state}.png"
            output_path = FRAMES_DIR / filename
            label = f"{frame_id} ({mouth_state})"

            logger.info("Generating thumbnail frame %d/%d: %s", completed + 1, total, label)

            prompt = _build_prompt(defn, mouth_state, False)

            try:
                tmp_path = generate_image(
                    prompt=prompt,
                    width=768,
                    height=432,
                    reference_image_path=canonical_path,
                )
                _remove_background(tmp_path, str(output_path))
            except Exception:
                logger.error("Failed to generate thumbnail frame %s", label, exc_info=True)

            completed += 1
            if on_progress:
                on_progress(completed, total, label)

        thumb_frames.append({
            "id": frame_id,
            "file_closed": f"{frame_id}_closed.png",
            "file_open": f"{frame_id}_open.png",
            "expression": defn["expression"],
            "pose": defn["pose"],
            "gesture": defn["gesture"],
        })

    # Update manifest — preserve existing data, add/replace thumbnail_frames
    manifest = get_manifest() or {
        "canonical_frame": None,
        "reference_source": "selected_reference",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "frames": [],
    }
    manifest["thumbnail_frames"] = thumb_frames
    manifest["generated_at"] = datetime.now(timezone.utc).isoformat()
    MANIFEST_PATH.write_text(json.dumps(manifest, indent=2))
    logger.info("Thumbnail frames generated: %d frames", len(thumb_frames))

    return manifest


def regenerate_thumbnail_frame(frame_id: str) -> dict:
    """Regenerate a single thumbnail frame (both mouth states).

    Returns the updated frame entry.
    """
    manifest = get_manifest()
    if not manifest:
        raise RuntimeError("No frame library exists. Generate the full library first.")

    # Find the thumbnail frame definition
    thumb_ids = _make_unique_thumb_ids(THUMBNAIL_FRAME_DEFINITIONS)
    defn_idx = None
    for i, tid in enumerate(thumb_ids):
        if tid == frame_id:
            defn_idx = i
            break

    if defn_idx is None:
        raise ValueError(f"Unknown thumbnail frame_id: {frame_id}")

    defn = THUMBNAIL_FRAME_DEFINITIONS[defn_idx]

    # Prefer selected reference over manifest canonical
    if SELECTED_REFERENCE_PATH.exists():
        canonical_path = str(SELECTED_REFERENCE_PATH)
    else:
        canonical_path = str(FRAMES_DIR / manifest["canonical_frame"])

    for mouth_state in ["closed", "open"]:
        filename = f"{frame_id}_{mouth_state}.png"
        output_path = FRAMES_DIR / filename

        prompt = _build_prompt(defn, mouth_state, False)
        tmp_path = generate_image(
            prompt=prompt,
            width=768,
            height=432,
            reference_image_path=canonical_path,
        )
        _remove_background(tmp_path, str(output_path))

        # Validate body coverage — retry once if only a floating head remains
        from PIL import Image as PILImage
        result_img = PILImage.open(str(output_path)).convert("RGBA")
        if not _check_body_coverage(result_img, f"regenerate-thumb:{filename}"):
            logger.warning("Body missing after generation, retrying: %s", filename)
            tmp_path = generate_image(
                prompt=prompt,
                width=768,
                height=432,
                reference_image_path=canonical_path,
            )
            _remove_background(tmp_path, str(output_path))

    # Update manifest timestamp
    manifest["generated_at"] = datetime.now(timezone.utc).isoformat()
    MANIFEST_PATH.write_text(json.dumps(manifest, indent=2))

    return {
        "id": frame_id,
        "file_closed": f"{frame_id}_closed.png",
        "file_open": f"{frame_id}_open.png",
        "expression": defn["expression"],
        "pose": defn["pose"],
        "gesture": defn["gesture"],
    }
