"""Audio split pipeline — splits an MP3 at a timestamp with word-boundary snapping."""

import logging
import subprocess
import uuid
from pathlib import Path

from config import DATA_DIR

logger = logging.getLogger(__name__)


def _snap_to_word_boundary(
    word_timestamps: list[dict],
    split_time_ms: int,
) -> tuple[int, int]:
    """Find the word boundary (end_ms) closest to split_time_ms.

    Returns (split_word_index, actual_split_ms) where split_word_index is the
    last word in the first half (0-based).  Clamps so neither half is empty.
    """
    if not word_timestamps or len(word_timestamps) < 2:
        return 0, split_time_ms

    best_idx = 0
    best_dist = abs(word_timestamps[0]["end_ms"] - split_time_ms)

    for i, wt in enumerate(word_timestamps):
        dist = abs(wt["end_ms"] - split_time_ms)
        if dist < best_dist:
            best_dist = dist
            best_idx = i

    # Clamp: at least one word in each half
    best_idx = max(0, min(best_idx, len(word_timestamps) - 2))

    return best_idx, word_timestamps[best_idx]["end_ms"]


def _split_mp3(
    input_path: Path,
    out_a: Path,
    out_b: Path,
    split_seconds: float,
) -> None:
    """Re-encode split an MP3 into two halves at the given timestamp."""
    # First half: 0 → split_seconds
    subprocess.run(
        [
            "ffmpeg", "-y",
            "-i", str(input_path),
            "-ss", "0",
            "-to", str(split_seconds),
            "-c:a", "libmp3lame",
            "-b:a", "192k",
            str(out_a),
        ],
        capture_output=True,
        check=True,
    )

    # Second half: split_seconds → end
    subprocess.run(
        [
            "ffmpeg", "-y",
            "-i", str(input_path),
            "-ss", str(split_seconds),
            "-c:a", "libmp3lame",
            "-b:a", "192k",
            str(out_b),
        ],
        capture_output=True,
        check=True,
    )


def split_scene_audio(
    script_id: str,
    scene: dict,
    split_time_ms: int,
) -> tuple[dict, dict]:
    """Split a scene's audio, word timestamps, and narration at a timestamp.

    Returns (scene_a, scene_b) dicts ready to be spliced into the segment.
    """
    word_timestamps = scene.get("word_timestamps") or []
    audio_url = scene.get("audio_url", "")

    if not audio_url:
        raise ValueError("Scene has no audio to split")

    # Snap to word boundary
    split_idx, actual_ms = _snap_to_word_boundary(word_timestamps, split_time_ms)
    split_seconds = actual_ms / 1000.0

    logger.info(
        "Splitting scene %s at %dms (snapped from %dms, word_idx=%d)",
        scene["id"], actual_ms, split_time_ms, split_idx,
    )

    # Split audio files
    # audio_url is like /static/projects/{script_id}/audio/{scene_id}.mp3
    audio_filename = audio_url.split("/")[-1]
    audio_dir = DATA_DIR / "projects" / script_id / "audio"
    input_path = audio_dir / audio_filename

    new_id_b = uuid.uuid4().hex[:12]
    scene_a_id = scene["id"]
    scene_b_id = f"scene-{new_id_b}"

    out_a = audio_dir / f"{scene_a_id}.mp3"
    out_b = audio_dir / f"{scene_b_id}.mp3"

    _split_mp3(input_path, out_a, out_b, split_seconds)

    # Split word timestamps
    # First half: words 0..split_idx (inclusive), unchanged
    # Second half: words split_idx+1..end, zero-rebased
    wt_a = word_timestamps[: split_idx + 1]
    wt_b_raw = word_timestamps[split_idx + 1 :]

    wt_b = [
        {
            "word": wt["word"],
            "start_ms": wt["start_ms"] - actual_ms,
            "end_ms": wt["end_ms"] - actual_ms,
        }
        for wt in wt_b_raw
    ]

    # Reconstruct narration from word tokens
    narration_a = " ".join(wt["word"] for wt in wt_a)
    narration_b = " ".join(wt["word"] for wt in wt_b)

    # Compute durations
    duration_a = split_seconds
    if wt_b:
        duration_b = wt_b[-1]["end_ms"] / 1000.0
    else:
        orig_duration = scene.get("audio_duration_seconds", 0) or 0
        duration_b = max(0, orig_duration - split_seconds)

    # Build scene A (keeps original scene id, image, fx)
    scene_a = {
        **scene,
        "narration": narration_a,
        "audio_url": f"/static/projects/{script_id}/audio/{scene_a_id}.mp3",
        "audio_duration_seconds": duration_a,
        "duration_estimate_seconds": duration_a,
        "word_timestamps": wt_a,
    }

    # Build scene B (new id, clears visuals since narration changed)
    scene_b = {
        **scene,
        "id": scene_b_id,
        "narration": narration_b,
        "visual_prompt": scene.get("visual_prompt", ""),
        "audio_url": f"/static/projects/{script_id}/audio/{scene_b_id}.mp3",
        "audio_duration_seconds": duration_b,
        "duration_estimate_seconds": duration_b,
        "word_timestamps": wt_b,
        "image_url": "",
        "frame_urls": [],
        "fx": None,
        "eli_overlay": None,
    }

    logger.info(
        "Split complete: A=%s (%.1fs, %d words), B=%s (%.1fs, %d words)",
        scene_a_id, duration_a, len(wt_a),
        scene_b_id, duration_b, len(wt_b),
    )

    return scene_a, scene_b
