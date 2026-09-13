"""Remotion rendering pipeline — orchestrates Remotion CLI to produce videos."""

import json
import logging
import math
import os
import re
import subprocess
import time
from pathlib import Path
from typing import Any, Callable

from config import BACKEND_PORT, DATA_DIR, FPS, VIDEO_HEIGHT, VIDEO_WIDTH
from models.script import ChapterMarker, Scene, SceneFX, Script, ScriptContent, WordTimestamp
from pipeline.export_paths import copy_to_project_downloads, longform_filename
from pipeline.process_manager import register_process, run_tracked, terminate_process_group, unregister_process

logger = logging.getLogger(__name__)

ProgressCallback = Callable[[float, str], None] | None
CancelCheck = Callable[[], None] | None

# Path to the remotion project at repo root
REMOTION_DIR = Path(__file__).resolve().parents[2] / "remotion"
REMOTION_ENTRY = REMOTION_DIR / "src" / "index.ts"


BACKEND_STATIC_BASE = f"http://localhost:{BACKEND_PORT}/static/projects"
BACKEND_STYLE_STATIC_BASE = f"http://localhost:{BACKEND_PORT}/static/style"
MAX_AI_VIDEO_SLOWDOWN_RATIO = 1.25
SUBTITLE_ROUTER_VERSION = "standard-subtitle-router-v1"
RENDERER_CONTEXT_STAGE_VERSION = "renderer-context-stage-v4"
# Bump to invalidate every prior blink render (overlay geometry / detection changes).
BLINK_RENDERER_VERSION = "full-frame-blink-v1"
# Bump to invalidate every prior camera-drift render (CameraDrift transform math changes).
CAMERA_DRIFT_RENDERER_VERSION = "camera-drift-cover-v1"
SUBTITLE_COVERAGE_MODES = {"all", "punchy"}
SUBTITLE_STYLES = ("clean", "kinetic", "burst")


def _to_remotion_path(abs_path: str) -> str:
    """Convert absolute data path to a URL served by the FastAPI backend."""
    projects_dir = str(DATA_DIR / "projects")
    if abs_path.startswith(projects_dir):
        relative = abs_path[len(projects_dir):]
        return f"{BACKEND_STATIC_BASE}{relative}"
    style_dir = str(DATA_DIR / "style")
    if abs_path.startswith(style_dir):
        relative = abs_path[len(style_dir):]
        return f"{BACKEND_STYLE_STATIC_BASE}{relative}"
    return abs_path


def _renders_dir(script_id: str) -> Path:
    d = DATA_DIR / "projects" / script_id / "renders"
    d.mkdir(parents=True, exist_ok=True)
    return d


def _scene_image_path(script_id: str, scene_id: str, image_url: str | None = None) -> str | None:
    """Resolve local filesystem path for a scene image. Returns None if not found."""
    base = DATA_DIR / "projects" / script_id / "images"

    if image_url:
        resolved = _project_static_asset_path(script_id, image_url)
        if resolved is not None:
            return resolved
        resolved = _style_static_asset_path(image_url)
        if resolved is not None:
            return resolved
        filename = image_url.rsplit("/", 1)[-1]
        custom = base / filename
        if custom.exists():
            return _to_remotion_path(str(custom))

    plain = base / f"{scene_id}.png"
    if plain.exists():
        return _to_remotion_path(str(plain))
    f0 = base / f"{scene_id}_f0.png"
    if f0.exists():
        return _to_remotion_path(str(f0))
    return None


def _project_static_asset_path(script_id: str, image_url: str) -> str | None:
    marker = f"/static/projects/{script_id}/"
    marker_index = image_url.find(marker)
    if marker_index < 0:
        return None

    relative = image_url[marker_index + len(marker):]
    if not relative or ".." in Path(relative).parts:
        return None

    path = DATA_DIR / "projects" / script_id / relative
    if path.exists():
        return _to_remotion_path(str(path))
    return None


def _style_static_asset_path(image_url: str) -> str | None:
    marker = "/static/style/"
    marker_index = image_url.find(marker)
    if marker_index < 0:
        return None

    relative = image_url[marker_index + len(marker):]
    if not relative or ".." in Path(relative).parts:
        return None

    path = DATA_DIR / "style" / relative
    if path.exists():
        return _to_remotion_path(str(path))
    return None


def _scene_audio_path(script_id: str, scene_id: str) -> str | None:
    """Resolve local filesystem path for a scene audio file. Returns None if not found."""
    path = DATA_DIR / "projects" / script_id / "audio" / f"{scene_id}.mp3"
    return _to_remotion_path(str(path)) if path.exists() else None


def _scene_frame_paths(script_id: str, scene: Scene) -> list[str]:
    """Resolve local filesystem paths for multi-frame scene images.

    For frames with source == "subtitle" (via frame_directives), appends
    an empty string so Remotion renders text-on-black instead of loading an image.
    """
    paths = []
    directives = scene.frame_directives or []

    if scene.frame_urls:
        for i, frame_url in enumerate(scene.frame_urls):
            # Check if this frame is a subtitle (no image needed)
            if i < len(directives) and directives[i].source == "subtitle":
                paths.append("")
                continue
            resolved = _project_static_asset_path(script_id, frame_url)
            if resolved is not None:
                paths.append(resolved)
                continue
            fp = DATA_DIR / "projects" / script_id / "images" / f"{scene.id}_f{i}.png"
            if fp.exists():
                paths.append(_to_remotion_path(str(fp)))
            else:
                paths.append("")
    return paths


def _visual_layers_to_input_props(scene: Scene, script_id: str) -> list[dict[str, Any]]:
    """Convert animation type layers to Remotion input props."""
    layers: list[dict[str, Any]] = []
    for layer in scene.visual_layers:
        layer_props = layer.model_dump()
        image_url = layer_props.get("image_url")
        layer_props["image_path"] = (
            _scene_image_path(script_id, scene.id, image_url)
            if image_url
            else None
        )
        layers.append(layer_props)
    return layers


def _scene_video_path(script_id: str, scene: Scene) -> Path | None:
    """Resolve the local filesystem path for video-backed scenes."""
    if scene.visual_mode != "video":
        return None

    ai_video_path = DATA_DIR / "projects" / script_id / "videos" / f"{scene.id}.mp4"
    if ai_video_path.exists():
        return ai_video_path

    return None


def _read_video_metadata_duration(video_path: Path) -> float | None:
    metadata_path = video_path.with_suffix(".source.json")
    if not metadata_path.exists():
        return None
    try:
        metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        logger.warning("Could not read video metadata duration from %s", metadata_path)
        return None

    duration = metadata.get("duration_seconds")
    if isinstance(duration, (int, float)) and duration > 0:
        return float(duration)
    return None


def _probe_video_duration(video_path: Path) -> float | None:
    try:
        result = run_tracked(
            [
                "ffprobe",
                "-v",
                "error",
                "-show_entries",
                "format=duration",
                "-of",
                "default=noprint_wrappers=1:nokey=1",
                str(video_path),
            ],
            label=f"FFprobe video duration: {video_path.name}",
            capture_output=True,
            text=True,
            timeout=15,
        )
        if result.returncode == 0:
            duration = float(result.stdout.strip())
            if duration > 0:
                return duration
    except Exception as exc:
        logger.warning("Could not probe video duration for %s: %s", video_path, exc)
    return None


def _video_clip_duration(video_path: Path) -> float | None:
    """Return the actual clip duration, falling back to provider metadata."""
    return _probe_video_duration(video_path) or _read_video_metadata_duration(video_path)


def _base_scene_duration(scene: Scene) -> float:
    return scene.audio_duration_seconds if scene.audio_duration_seconds > 0 else scene.duration_estimate_seconds


def _scene_video_render_plan(
    scene: Scene,
    script_id: str,
    video_path: Path | None = None,
) -> tuple[float, bool, float | None]:
    """Return (duration_seconds, use_video, video_playback_rate)."""
    duration = _base_scene_duration(scene)
    local_video_path = video_path or _scene_video_path(script_id, scene)
    if not local_video_path:
        return duration, False, None

    clip_duration = _video_clip_duration(local_video_path)
    if not clip_duration or clip_duration + (1 / FPS) >= duration:
        return duration, True, None

    if scene.visual_mode == "video":
        slowdown_ratio = duration / clip_duration
        if slowdown_ratio <= MAX_AI_VIDEO_SLOWDOWN_RATIO:
            playback_rate = clip_duration / duration
            logger.warning(
                "[AI_VIDEO] slowed scene %s; audio_duration=%.1fs clip_duration=%.1fs slowdown=%.2fx max=%.2fx",
                scene.id,
                duration,
                clip_duration,
                slowdown_ratio,
                MAX_AI_VIDEO_SLOWDOWN_RATIO,
            )
            return duration, True, playback_rate

        logger.warning(
            "[AI_VIDEO] downgraded scene %s to image render; reason=clip_duration %.1fs requires slowdown %.2fx > max %.2fx for audio_duration %.1fs",
            scene.id,
            clip_duration,
            slowdown_ratio,
            MAX_AI_VIDEO_SLOWDOWN_RATIO,
            duration,
        )
        return duration, False, None

    logger.info(
        "Capping video scene %s duration from %.3fs to clip duration %.3fs",
        scene.id,
        duration,
        clip_duration,
    )
    return clip_duration, True, None


def _scene_render_duration(scene: Scene, script_id: str, video_path: Path | None = None) -> float:
    """Return the Remotion sequence duration for a scene.

    AI video may slow down slightly or fall back to its anchor image; other
    video-backed scenes end at the clip boundary when the clip is shorter.
    """
    duration, _use_video, _playback_rate = _scene_video_render_plan(scene, script_id, video_path)
    return duration


def _title_card_image_path(script_id: str) -> str | None:
    """Resolve path to the title card composite image."""
    notitle = DATA_DIR / "projects" / script_id / "images" / "composite_title_card_notitle.png"
    if notitle.exists():
        return _to_remotion_path(str(notitle))
    withtitle = DATA_DIR / "projects" / script_id / "images" / "composite_title_card.png"
    return _to_remotion_path(str(withtitle)) if withtitle.exists() else None


def _resolve_zoom_punch_frame(
    fx: SceneFX | None,
    word_timestamps: list[WordTimestamp] | None,
    duration_seconds: float,
) -> dict | None:
    """Resolve trigger_word → trigger_frame on zoom_punch FX.

    If trigger_word is set and word_timestamps exist, looks up the word's
    start_ms and converts to a frame number. Falls back to mid-scene if the
    word is not found. Returns fx unchanged if no zoom_punch or no trigger_word.
    """
    if not fx or not fx.zoom_punch:
        return fx.model_dump() if fx else None
    out = fx.model_dump()
    zp = out["zoom_punch"]
    trigger_word = zp.get("trigger_word")
    if not trigger_word:
        return out

    # Try to find the word in timestamps
    if word_timestamps:
        lower = re.sub(r"[^a-z0-9]", "", trigger_word.lower())
        for wt in word_timestamps:
            wt_word = re.sub(r"[^a-z0-9]", "", wt.word.lower())
            if wt_word == lower:
                zp["trigger_frame"] = round(wt.start_ms / 1000 * FPS)
                return out

    # Fallback: estimate from word position in narration (mid-scene if no narration context)
    zp["trigger_frame"] = round(duration_seconds / 2 * FPS)
    return out


def _coerce_legacy_blink_scene(scene: Scene) -> Scene:
    """Normalize legacy blink scenes for rendering.

    Old project JSON used visual_mode="blink" with generated state_a/state_b
    cutout visual_layers. Those scenes now load as full_frame (see
    models.script normalization); this drops their stale cutout layers so old
    generated assets are never rendered. Blink is rebuilt purely from
    full_frame_blink metadata when a safe anchor exists.
    """
    if scene.visual_mode == "full_frame" and any(
        layer.asset_kind == "cutout" for layer in scene.visual_layers
    ):
        return scene.model_copy(update={"visual_layers": []})
    return scene


def _scene_to_input_props(
    scene: Scene,
    script_id: str,
    subtitle_style: str | None = None,
) -> dict[str, Any]:
    """Convert a Scene model to the input props expected by Remotion."""
    scene = _coerce_legacy_blink_scene(scene)
    # Resolve asset paths
    text_only_caption = (
        scene.visual_mode == "captions"
        and not scene.visual_prompt.strip()
        and not scene.image_url
        and not scene.frame_urls
    )
    if text_only_caption:
        image_path = None
        frame_paths = []
    else:
        image_path = _scene_image_path(script_id, scene.id, scene.image_url or None)
        frame_paths = _scene_frame_paths(script_id, scene)
        if image_path is None:
            image_path = next((path for path in frame_paths if path), None)
    audio_path = _scene_audio_path(script_id, scene.id)

    # Detect AI-generated video scenes
    video_path: str | None = None
    local_video_path = _scene_video_path(script_id, scene)
    media_type = "image"
    duration, use_video, video_playback_rate = _scene_video_render_plan(scene, script_id, local_video_path)
    if local_video_path and use_video:
        video_path = _to_remotion_path(str(local_video_path))
        media_type = "video"

    # For title cards, use the composite image
    if scene.is_title_card and scene.title_card_zoom_target:
        tc_path = _title_card_image_path(script_id)
        if tc_path:
            image_path = tc_path

    # Parse FX if stored as dict — resolve trigger_word → trigger_frame
    fx = _resolve_zoom_punch_frame(scene.fx, scene.word_timestamps, duration)

    # Eli overlay passes through as a dict for the Remotion JSON payload
    eli_overlay = scene.eli_overlay.model_dump() if scene.eli_overlay else None

    # Suppress eli overlay when Eli is already in the generated image
    if eli_overlay and scene.contains_person:
        eli_overlay = {**eli_overlay, "enabled": False}

    # Cinematic-chapters chapter overlay (sourced from visual_source_metadata)
    metadata = scene.visual_source_metadata or {}
    chapter_overlay = metadata.get("chapter_overlay")
    full_frame_blink = None
    raw_blink = metadata.get("full_frame_blink")
    if (
        scene.visual_mode == "full_frame"
        and isinstance(raw_blink, dict)
        and raw_blink.get("enabled") is True
    ):
        raw_anchor = raw_blink.get("anchor")
        full_frame_blink = {
            "enabled": True,
            "action": "blink" if raw_blink.get("action") == "blink" else "",
            "anchor": raw_anchor if isinstance(raw_anchor, dict) else None,
        }

    return {
        "id": scene.id,
        "narration": scene.narration,
        "duration_seconds": duration,
        "is_title_card": scene.is_title_card,
        "image_path": image_path,
        "frame_paths": frame_paths if frame_paths else None,
        "audio_path": audio_path,
        "title_card_zoom_target": scene.title_card_zoom_target,
        "fx": fx,
        "eli_overlay": eli_overlay,
        "character_frames_base_url": f"http://localhost:{BACKEND_PORT}/static/character/frames",
        "word_timestamps": [w.model_dump() for w in scene.word_timestamps] if scene.word_timestamps and not scene.is_title_card else None,
        "phrase_timestamps": [p.model_dump() for p in scene.phrase_timestamps] if scene.phrase_timestamps and not scene.is_title_card else None,
        "visual_beat": scene.visual_beat,
        "visual_mode": scene.visual_mode,
        "blink_action": scene.blink_action,
        "full_frame_blink": full_frame_blink,
        "renderer_context": scene.renderer_context,
        "subtitle_style": subtitle_style or scene.subtitle_style,
        "caption_text": scene.caption_text,
        "caption_emphasis": scene.caption_emphasis,
        "stat_value": scene.stat_value,
        "stat_label": scene.stat_label,
        "visual_layers": _visual_layers_to_input_props(scene, script_id),
        "frame_directives": [d.model_dump() for d in scene.frame_directives] if scene.frame_directives else None,
        "frame_timings": scene.frame_timings,
        "visual_in_seconds": scene.visual_in_seconds,
        "visual_out_seconds": scene.visual_out_seconds,
        "transition_in": scene.transition_in if scene.transition_in != "cut" else None,
        "media_type": media_type if media_type != "image" else None,
        "video_path": video_path,
        "video_playback_rate": video_playback_rate,
        "chapter_overlay": chapter_overlay,
    }


def voice_engine_fingerprint() -> str:
    """Stable identity of the active TTS engine, for render cache markers.

    A video voiced locally must not reuse renders produced from ElevenLabs
    audio, and switching between two local voices must re-render too.
    """
    from integrations.local_models import active_model, modality_source

    if modality_source("voice") != "local":
        return "elevenlabs"
    return f"local:{active_model('voice').id}"


def subtitle_render_fingerprint(content: ScriptContent) -> dict[str, Any]:
    """Return content-sensitive subtitle routing inputs for render cache metadata."""
    return {
        "subtitle_router_version": SUBTITLE_ROUTER_VERSION,
        "renderer_context_stage_version": RENDERER_CONTEXT_STAGE_VERSION,
        "blink_renderer_version": BLINK_RENDERER_VERSION,
        "camera_drift_renderer_version": CAMERA_DRIFT_RENDERER_VERSION,
        "voice_engine": voice_engine_fingerprint(),
        "settings": subtitle_settings_from_env(),
        "scenes": [
            {
                "id": scene.id,
                "subtitle_style": scene.subtitle_style,
                "visual_mode": scene.visual_mode,
                "renderer_context": scene.renderer_context if scene.visual_mode in {"popup_sequence", "comparison_board", "stat_card", "captions"} else "",
                "stat_value": scene.stat_value if scene.visual_mode == "stat_card" else "",
                "stat_label": scene.stat_label if scene.visual_mode == "stat_card" else "",
                "stat_card_icon": _stat_card_icon_fingerprint(scene),
                "full_frame_blink": _full_frame_blink_fingerprint(scene),
            }
            for scene in content.all_scenes()
        ],
    }


def _full_frame_blink_fingerprint(scene: Scene) -> dict[str, Any] | None:
    if scene.visual_mode != "full_frame":
        return None
    metadata = scene.visual_source_metadata or {}
    raw_blink = metadata.get("full_frame_blink")
    if not isinstance(raw_blink, dict) or raw_blink.get("enabled") is not True:
        return None
    raw_anchor = raw_blink.get("anchor")
    return {
        "enabled": True,
        "action": "blink" if raw_blink.get("action") == "blink" else "",
        "fingerprint": raw_blink.get("fingerprint"),
        "anchor": raw_anchor if isinstance(raw_anchor, dict) else None,
    }


def _stat_card_icon_fingerprint(scene: Scene) -> dict[str, str] | None:
    if scene.visual_mode != "stat_card":
        return None
    for layer in scene.visual_layers or []:
        if layer.type == "image":
            return {"prompt": layer.prompt, "image_url": layer.image_url}
    return None


def _setting_enabled(value: str | None, default: bool = True) -> bool:
    if value is None:
        return default
    return value.strip().lower() not in {"", "0", "false", "no", "off"}


def subtitle_settings_from_env() -> dict[str, Any]:
    coverage = os.getenv("SUBTITLE_COVERAGE_MODE", "all").strip().lower()
    if coverage not in SUBTITLE_COVERAGE_MODES:
        coverage = "all"
    enabled_styles = [
        style
        for style in SUBTITLE_STYLES
        if _setting_enabled(os.getenv(f"SUBTITLE_STYLE_{style.upper()}_ENABLED"), True)
    ]
    return {
        "coverage": coverage,
        "enabled_styles": enabled_styles,
    }


def _subtitle_scene_eligible(scene: Scene) -> bool:
    return not (
        scene.is_title_card
        or scene.visual_mode == "captions"
        or scene.visual_mode == "stat_card"
        or scene.visual_beat == "aha_subtitle"
    )


def _subtitle_punch_score(scene: Scene) -> float:
    timestamps = scene.word_timestamps or []
    narration = scene.narration.lower()
    words = timestamps or re.findall(r"\b[\w']+\b", scene.narration)
    word_count = len(words)
    if timestamps:
        spoken_ms = max(1, timestamps[-1].end_ms - timestamps[0].start_ms)
        average_word_ms = spoken_ms / max(1, len(timestamps))
    else:
        average_word_ms = max(1.0, _base_scene_duration(scene) * 1000 / max(1, word_count))

    score = 0.0
    if average_word_ms <= 190:
        score += 4.0
    elif average_word_ms <= 240:
        score += 2.0
    if any(cue in narration for cue in ("but", "then", "suddenly", "the catch", "the real reason", "finally", "turns out")):
        score += 4.0
    if word_count <= 6 and re.search(r"[!?]$", scene.narration.strip()):
        score += 2.0
    if scene.visual_mode in {"multi_frame", "popup_sequence", "comparison_board", "video"}:
        score += 1.0
    return score


def _subtitle_styles_for_render(content: ScriptContent) -> dict[str, str]:
    settings = subtitle_settings_from_env()
    eligible = [scene for scene in content.all_scenes() if _subtitle_scene_eligible(scene)]
    if settings["coverage"] == "all":
        return {scene.id: scene.subtitle_style or "auto" for scene in eligible}

    selected_count = max(1, math.ceil(len(eligible) * 0.2)) if eligible else 0
    indexed = list(enumerate(eligible))
    selected_ids = {
        scene.id
        for _index, scene in sorted(
            indexed,
            key=lambda item: (_subtitle_punch_score(item[1]), -item[0]),
            reverse=True,
        )[:selected_count]
    }
    return {scene.id: ((scene.subtitle_style or "auto") if scene.id in selected_ids else "none") for scene in eligible}


def _render_metadata_path(render_path: Path) -> Path:
    return render_path.with_suffix(f"{render_path.suffix}.json")


def _write_render_metadata(render_path: Path, content: ScriptContent) -> None:
    _render_metadata_path(render_path).write_text(
        json.dumps({"subtitle_render_fingerprint": subtitle_render_fingerprint(content)}, indent=2),
        encoding="utf-8",
    )


def is_render_metadata_current(render_path: Path, content: ScriptContent) -> bool:
    metadata_path = _render_metadata_path(render_path)
    if not metadata_path.is_file():
        return False
    try:
        metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return False
    return metadata.get("subtitle_render_fingerprint") == subtitle_render_fingerprint(content)


def _write_input_props(props: dict[str, Any], output_path: Path) -> Path:
    """Write input props JSON file for Remotion to consume."""
    props_path = output_path.parent / f"{output_path.stem}_props.json"
    props_path.write_text(json.dumps(props, indent=2, default=str))
    return props_path


CHAPTER_TRANSITION_FRAMES = 60  # 2 seconds at 30fps


def _compute_chapter_markers(
    content: ScriptContent,
    script_id: str,
    fps: int = FPS,
) -> tuple[list[dict], int]:
    """Compute chapter markers and total frame count from segment boundaries.

    Returns (chapter_markers, total_frames) accounting for chapter transition inserts.
    """
    markers: list[dict] = []
    current_frame = 0
    prev_seg_idx = -1

    for seg in content.segments:
        seg_idx = content.segments.index(seg)
        # Insert chapter transition before each segment (except first)
        if seg_idx > 0:
            markers.append({
                "segment_index": seg_idx,
                "label": seg.name,
                "frame_offset": current_frame,
            })
            current_frame += CHAPTER_TRANSITION_FRAMES

        if seg_idx == 0:
            markers.append({
                "segment_index": 0,
                "label": seg.name,
                "frame_offset": 0,
            })

        for scene in seg.scenes:
            duration = _scene_render_duration(scene, script_id)
            scene_frames = max(fps, int(duration * fps))
            current_frame += scene_frames

    return markers, current_frame


def _build_chapter_map(
    content: ScriptContent,
    script_id: str,
) -> dict | None:
    """Build chapter map data from title card composite and zoom target data.

    Returns a dict with image_path and circles for the AnimatedChapterMap component,
    or None if no title card data is available.
    """
    tc_image = _title_card_image_path(script_id)
    if not tc_image:
        return None

    circles = []
    for seg in content.segments:
        # Find the title card scene in this segment (first scene with is_title_card)
        for scene in seg.scenes:
            if scene.is_title_card and scene.title_card_zoom_target:
                target = scene.title_card_zoom_target
                circles.append({
                    "x": target.get("x", 0),
                    "y": target.get("y", 0),
                    "radius": target.get("radius", 100),
                    "label": seg.name,
                })
                break

    if not circles:
        return None

    return {
        "image_path": tc_image,
        "circles": circles,
    }


def _run_remotion(
    composition_id: str,
    props_path: Path,
    output_path: Path,
    width: int = VIDEO_WIDTH,
    height: int = VIDEO_HEIGHT,
    fps: int = FPS,
    log_level: str = "warn",
) -> None:
    """Run Remotion render via npx subprocess with streamed progress."""
    cmd = [
        "npx",
        "remotion",
        "render",
        str(REMOTION_ENTRY),
        composition_id,
        str(output_path),
        f"--props={props_path}",
        f"--width={width}",
        f"--height={height}",
        f"--fps={fps}",
        "--codec=h264-mkv",
        f"--log={log_level}",
        "--overwrite",
    ]

    logger.info("Running Remotion: %s", " ".join(cmd))

    t0 = time.monotonic()
    last_progress_log = t0
    stderr_tail: list[str] = []

    proc = subprocess.Popen(
        cmd,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        cwd=str(REMOTION_DIR),
        env={**os.environ, "NODE_OPTIONS": "--max-old-space-size=4096"},
        start_new_session=os.name == "posix",
    )
    register_process(proc, f"Remotion render: {output_path.name}")

    try:
        assert proc.stderr is not None
        for line in proc.stderr:
            line = line.rstrip()
            if not line:
                continue
            stderr_tail.append(line)
            if len(stderr_tail) > 50:
                stderr_tail.pop(0)

            # Log Remotion progress lines (contain %) at most every 10s
            now = time.monotonic()
            if "%" in line and now - last_progress_log >= 10:
                logger.info("Remotion progress: %s", line.strip())
                last_progress_log = now
            elif "error" in line.lower() or "warn" in line.lower():
                logger.warning("Remotion: %s", line.strip())

        proc.wait(timeout=3600)
    except subprocess.TimeoutExpired:
        terminate_process_group(proc, f"Remotion render: {output_path.name}")
        raise RuntimeError("Remotion render timed out after 60 minutes")
    finally:
        unregister_process(proc)

    elapsed = time.monotonic() - t0

    if proc.returncode != 0:
        tail = "\n".join(stderr_tail[-20:])
        logger.error("Remotion stderr tail:\n%s", tail)
        raise RuntimeError(
            f"Remotion render failed (exit {proc.returncode}): {tail[-500:]}"
        )

    logger.info("Remotion render complete in %.1fs: %s", elapsed, output_path)


def _apply_speed(input_path: Path, output_path: Path, speed: float) -> None:
    """Re-encode video at a different playback speed using FFmpeg.

    Uses setpts for video and atempo for audio so pitch stays natural.
    """
    cmd = [
        "ffmpeg", "-y",
        "-i", str(input_path),
        "-filter_complex",
        f"[0:v]setpts=PTS/{speed}[v];[0:a]atempo={speed}[a]",
        "-map", "[v]", "-map", "[a]",
        str(output_path),
    ]
    logger.info("Applying speed %.2fx: %s", speed, " ".join(cmd))
    result = run_tracked(cmd, label=f"FFmpeg speed: {output_path.name}", capture_output=True, timeout=600)
    if result.returncode != 0:
        logger.error("FFmpeg stderr: %s", result.stderr)
        raise RuntimeError(f"FFmpeg speed filter failed (exit {result.returncode}): {result.stderr[-500:]}")
    logger.info("Speed adjustment complete: %s", output_path)


def _verify_video(video_path: Path) -> bool:
    """Spot-check video integrity by decoding 5 seconds from the middle."""
    try:
        probe = run_tracked(
            ["ffprobe", "-v", "error", "-show_entries", "format=duration",
             "-of", "csv=p=0", str(video_path)],
            label=f"FFprobe verify: {video_path.name}",
            capture_output=True, text=True, timeout=30,
        )
        duration = float(probe.stdout.strip()) if probe.returncode == 0 else 10.0
        mid = max(0, duration / 2 - 2.5)
    except Exception:
        mid = 0

    cmd = [
        "ffmpeg", "-y",
        "-ss", f"{mid:.1f}",
        "-i", str(video_path),
        "-t", "5",
        "-f", "null", "/dev/null",
    ]
    result = run_tracked(cmd, label=f"FFmpeg verify: {video_path.name}", capture_output=True, timeout=60)
    if result.returncode != 0:
        logger.error("Video verification FAILED: %s", result.stderr[-300:])
        return False
    logger.info("Video verification passed: %s", video_path)
    return True


def _reencode_h264(input_path: Path, output_path: Path) -> bool:
    """Re-encode to H.264 with controlled keyframe interval and pixel format."""
    cmd = [
        "ffmpeg", "-y",
        "-i", str(input_path),
        "-c:v", "libx264",
        "-g", "60",
        "-crf", "18",
        "-preset", "fast",
        "-pix_fmt", "yuv420p",
        "-movflags", "faststart",
        "-c:a", "copy",
        str(output_path),
    ]
    logger.info("Re-encoding with proper keyframes: %s", " ".join(cmd))
    result = run_tracked(cmd, label=f"FFmpeg re-encode: {output_path.name}", capture_output=True, timeout=3600)
    if result.returncode != 0:
        logger.error("Re-encode failed (exit %d): %s", result.returncode, result.stderr[-500:])
        return False
    logger.info("Re-encode complete: %s", output_path)
    return True


# Visual modes whose render REQUIRES a generated scene image/frames. If one of
# these reaches render with no image, the renderer draws a "No image" placeholder.
_IMAGE_BACKED_RENDER_MODES = {"full_frame", "multi_frame", "continuous"}


def _persist_repaired_scene_images(
    script_id: str,
    content: ScriptContent,
    scene_ids: list[str],
) -> None:
    """Merge repaired scene image fields back into the stored full script JSON.

    `content` may be a filtered subset (e.g. a single-segment export-test copy),
    so we merge per-scene into the DB's full content rather than overwriting it.
    """
    from database import engine
    from sqlmodel import Session
    from pipeline.script_utils import find_scene_in_content

    repaired = {sid: find_scene_in_content(content, sid) for sid in scene_ids}
    with Session(engine) as session:
        record = session.get(Script, script_id)
        if not record:
            return
        full = ScriptContent.model_validate_json(record.script_json)
        changed = False
        for sid, src in repaired.items():
            if src is None:
                continue
            dst = find_scene_in_content(full, sid)
            if dst is None:
                continue
            dst.visual_prompt = src.visual_prompt
            dst.image_url = src.image_url
            dst.frame_urls = src.frame_urls
            dst.visual_source_metadata = src.visual_source_metadata
            changed = True
        if changed:
            record.script_json = full.model_dump_json()
            session.add(record)
            session.commit()


def ensure_renderable_scene_images(script_id: str, content: ScriptContent) -> int:
    """Guarantee every image-backed scene has a renderable image before render.

    A scene can reach render in an image-backed visual_mode (full_frame /
    multi_frame / continuous) with no generated image — e.g. a captions /
    stat_card / comparison_board scene that was promoted to full_frame without
    regenerating assets, or a scene-length split chunk that lost its prompt.
    The renderer would otherwise draw the gray "No image" placeholder into the
    final MP4.

    For each such scene this backfills an empty ``visual_prompt`` from the
    scene's caption_text/narration, generates the missing image, mutates
    ``content`` in place, and persists the repaired scenes to the DB. Returns
    the count of scenes repaired. Scenes with no usable source text are left
    as-is and logged as errors so the gap is observable on the dev dashboard.
    """
    from pipeline.image_gen import generate_scene_image

    repaired_ids: list[str] = []
    for scene in content.all_scenes():
        if scene.is_title_card:
            continue
        if scene.visual_mode not in _IMAGE_BACKED_RENDER_MODES:
            continue
        if scene.image_url or scene.frame_urls or scene.video_url:
            continue

        fallback = (scene.caption_text or "").strip() or (scene.narration or "").strip()
        prompt = (scene.visual_prompt or "").strip() or fallback
        if not prompt:
            logger.error(
                "[ENSURE_IMAGES] %s scene %s is %s with no image and no prompt/narration to "
                "generate from; render will show a blank frame",
                script_id, scene.id, scene.visual_mode,
            )
            continue

        backfilled = not (scene.visual_prompt or "").strip()
        if backfilled:
            scene.visual_prompt = prompt
        logger.warning(
            "[ENSURE_IMAGES] %s scene %s (%s) has no generated image; generating from %s "
            "to avoid a blank frame",
            script_id, scene.id, scene.visual_mode,
            "scene narration" if backfilled else "visual prompt",
        )
        try:
            image_url, _, source_metadata = generate_scene_image(
                scene_id=scene.id,
                visual_prompt=scene.visual_prompt,
                script_id=script_id,
                contains_person=bool(scene.contains_person),
                force=True,
            )
        except Exception as exc:  # noqa: BLE001 — keep rendering other scenes
            logger.error(
                "[ENSURE_IMAGES] %s failed to generate fallback image for scene %s: %s",
                script_id, scene.id, exc, exc_info=True,
            )
            continue
        scene.image_url = image_url
        scene.frame_urls = []
        if source_metadata:
            scene.visual_source_metadata = source_metadata
        repaired_ids.append(scene.id)

    if repaired_ids:
        _persist_repaired_scene_images(script_id, content, repaired_ids)
    return len(repaired_ids)


def render_full_video(
    script_id: str,
    content: ScriptContent,
    width: int = VIDEO_WIDTH,
    height: int = VIDEO_HEIGHT,
    on_progress: ProgressCallback = None,
    cancel_check: CancelCheck = None,
    title: str = "",
    speed: float = 1.0,
    brand: dict | None = None,
) -> str:
    """Render the full video as a single Remotion composition.

    Returns the web-relative path to the final MP4.
    """
    scenes = content.all_scenes()
    total = len(scenes)

    def check_cancelled() -> None:
        if cancel_check:
            cancel_check()

    logger.info(
        "[%s] render_full_video started — %d scenes, speed=%.1fx, title=%r",
        script_id, total, speed, title or content.title,
    )

    # Remotion spawns Chromium, which is the largest memory consumer in the app.
    # Any local model still resident would be competing with it for the same
    # unified memory, so evict before the renderer starts. No-op in cloud mode.
    from pipeline.local_runtime import unload_all as _unload_local_models
    _unload_local_models()

    # Always prepare title card scenes (title cards are always active)
    from pipeline.formats import resolve_format
    fmt = resolve_format(content.format_id)
    strategy = fmt.title_card_strategy
    brand_dict = brand or {}
    for i, scene in enumerate(scenes):
        check_cancelled()
        if on_progress:
            on_progress(0.3 * (i + 1) / total, f"Preparing scene {i + 1}/{total}")
        logger.info("[%s] Preparing scene %d/%d (scene_id=%s)", script_id, i + 1, total, scene.id)
        scenes[i] = strategy.prepare_title_card_scene(scene, script_id, content, brand_dict)

    check_cancelled()
    repaired_count = ensure_renderable_scene_images(script_id, content)
    if repaired_count:
        logger.warning(
            "[%s] generated %d missing image-backed scene image(s) before render",
            script_id, repaired_count,
        )

    check_cancelled()
    if on_progress:
        on_progress(0.3, "Building Remotion composition...")

    # Build input props for the full video
    subtitle_settings = subtitle_settings_from_env()
    subtitle_styles = _subtitle_styles_for_render(content)
    segments_props = []
    for seg in content.segments:
        seg_scenes = []
        for sc in seg.scenes:
            seg_scenes.append(_scene_to_input_props(sc, script_id, subtitle_styles.get(sc.id)))
        segments_props.append({
            "name": seg.name,
            "scenes": seg_scenes,
        })

    # Compute chapter markers and chapter map
    chapter_markers, total_frames = _compute_chapter_markers(content, script_id)
    chapter_map = _build_chapter_map(content, script_id)
    logger.info(
        "[%s] Chapter markers: %d markers, %d total frames (%.1fs at %d fps)",
        script_id, len(chapter_markers), total_frames, total_frames / FPS, FPS,
    )

    props = {
        "segments": segments_props,
        "title": title or content.title,
        "fps": FPS,
        "width": width,
        "height": height,
        "visual_canvas": content.visual_canvas.model_dump(),
        "video_fx": {"chapter_markers": chapter_markers},
        "chapter_map": chapter_map,
        "segment_timer": {"enabled": True} if content.segment_timer_enabled else None,
        "subtitle_highlight": {"enabled": True} if content.subtitle_highlight_enabled else None,
        "subtitle_router_version": SUBTITLE_ROUTER_VERSION,
        "subtitle_settings": subtitle_settings,
    }

    renders = _renders_dir(script_id)
    speed_suffix = f"_{speed}x" if speed != 1.0 else ""
    output_filename = f"full_youtube{speed_suffix}.mp4"
    output_path = renders / output_filename

    # Remotion always renders to a temp file; we re-encode to the final output
    needs_speed = speed != 1.0
    raw_output = renders / f"full_youtube{speed_suffix}_raw.mkv"
    reencode_output = renders / f"full_youtube{speed_suffix}_enc.mp4" if needs_speed else output_path

    logger.info(
        "[VISUAL_CANVAS] render props script=%s color=%s",
        script_id,
        content.visual_canvas.background_color,
    )
    props_path = _write_input_props(props, raw_output)

    check_cancelled()
    if on_progress:
        on_progress(0.4, "Rendering video with Remotion...")

    try:
        render_start = time.monotonic()
        _run_remotion(
            composition_id="FullVideo",
            props_path=props_path,
            output_path=raw_output,
            width=width,
            height=height,
            log_level="verbose",
        )
        render_elapsed = time.monotonic() - render_start
        logger.info(
            "[%s] Remotion render finished in %.1fs — output: %s",
            script_id, render_elapsed, raw_output,
        )

        # Verify Remotion's output is decodable
        check_cancelled()
        if not _verify_video(raw_output):
            logger.warning("[%s] Raw output corrupt — retrying Remotion render once", script_id)
            if on_progress:
                on_progress(0.5, "First render corrupt, retrying...")
            check_cancelled()
            _run_remotion(
                composition_id="FullVideo",
                props_path=props_path,
                output_path=raw_output,
                width=width,
                height=height,
                log_level="verbose",
            )
            check_cancelled()
            if not _verify_video(raw_output):
                raise RuntimeError(
                    f"Remotion produced corrupt video on both attempts for {script_id}"
                )

        # Re-encode with controlled H.264 settings (keyframes, pixel format, faststart)
        check_cancelled()
        if on_progress:
            on_progress(0.8, "Re-encoding with proper keyframes...")
        if not _reencode_h264(raw_output, reencode_output):
            raise RuntimeError(f"H.264 re-encode failed for {script_id}")

        if needs_speed:
            check_cancelled()
            if on_progress:
                on_progress(0.9, f"Applying {speed}x speed...")
            _apply_speed(reencode_output, output_path, speed)
    finally:
        try:
            props_path.unlink()
        except OSError:
            pass
        try:
            raw_output.unlink()
        except OSError:
            pass
        if needs_speed:
            try:
                reencode_output.unlink()
            except OSError:
                pass

    if on_progress:
        on_progress(1.0, "Complete")

    web_path = f"/static/projects/{script_id}/renders/{output_filename}"
    _write_render_metadata(output_path, content)

    if title:
        try:
            speed_label = f" ({speed}x)" if speed != 1.0 else ""
            _copy_to_downloads(
                title,
                str(output_path),
                longform_filename("Video", f"{title}{speed_label}", ".mp4"),
            )
        except Exception:
            logger.warning("Failed to copy to downloads", exc_info=True)

    return web_path


def _copy_to_downloads(title: str, src_path: str, dest_name: str) -> str:
    """Copy a rendered file to the standard project Downloads folder."""
    dest = copy_to_project_downloads(title, src_path, dest_name)
    logger.info("Copied to downloads: %s", dest)
    return dest
