"""Remotion rendering pipeline — orchestrates Remotion CLI to produce videos."""

import json
import logging
import os
import re
import subprocess
import time
from pathlib import Path
from typing import Any, Callable

from config import BACKEND_PORT, DATA_DIR, FPS, VIDEO_HEIGHT, VIDEO_WIDTH
from models.script import ChapterMarker, Scene, SceneFX, ScriptContent, VideoFX, WordTimestamp
from pipeline.export_paths import copy_to_project_downloads, longform_filename
from pipeline.process_manager import register_process, run_tracked, terminate_process_group, unregister_process

logger = logging.getLogger(__name__)

ProgressCallback = Callable[[float, str], None] | None
CancelCheck = Callable[[], None] | None

# Path to the remotion project at repo root
REMOTION_DIR = Path(__file__).resolve().parents[2] / "remotion"
REMOTION_ENTRY = REMOTION_DIR / "src" / "index.ts"


BACKEND_STATIC_BASE = f"http://localhost:{BACKEND_PORT}/static/projects"
MAX_AI_VIDEO_SLOWDOWN_RATIO = 1.25


def _to_remotion_path(abs_path: str) -> str:
    """Convert absolute data path to a URL served by the FastAPI backend."""
    projects_dir = str(DATA_DIR / "projects")
    if abs_path.startswith(projects_dir):
        relative = abs_path[len(projects_dir):]
        return f"{BACKEND_STATIC_BASE}{relative}"
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

    if scene.frame_urls and len(scene.frame_urls) > 1:
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
    if scene.visual_mode != "video" and scene.media_source != "ai_video":
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

    if scene.visual_mode == "video" or scene.media_source == "ai_video":
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


def _scene_to_input_props(scene: Scene, script_id: str) -> dict[str, Any]:
    """Convert a Scene model to the input props expected by Remotion."""
    # Resolve asset paths
    image_path = _scene_image_path(script_id, scene.id, scene.image_url or None)
    audio_path = _scene_audio_path(script_id, scene.id)
    frame_paths = _scene_frame_paths(script_id, scene)

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
        "visual_treatment": scene.visual_treatment,
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
    if on_progress:
        on_progress(0.3, "Building Remotion composition...")

    # Build input props for the full video
    segments_props = []
    for seg in content.segments:
        seg_scenes = []
        for sc in seg.scenes:
            seg_scenes.append(_scene_to_input_props(sc, script_id))
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
