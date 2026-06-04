"""Export-test pipeline phases (audio → image → FX → Eli → render → copy).

Extracted from api/render.py so the FastAPI module stays focused on routing.
The phases share an ExportContext and progress-mapping helpers, and read/write
ScriptContent from the DB on their own (background-thread safe).
"""

import json
import logging
import threading
import time
from dataclasses import dataclass, field

from sqlmodel import Session

from config import DATA_DIR, FPS
from models.script import Script, ScriptContent
from pipeline.export_paths import copy_to_project_downloads, shortform_video_filename
from pipeline.remotion_render import render_full_video
from pipeline.render_jobs import RenderJob, estimate_render_time, is_cancelled, update_job
from pipeline.script_utils import find_scene_in_content

logger = logging.getLogger(__name__)


@dataclass
class ExportContext:
    script_id: str
    job: RenderJob
    scenes: list[dict]
    seg_name: str
    total_scenes: int
    voice_id: str
    brand_dict: dict
    project_title: str
    title: str
    total_segments: int
    regen_images: bool
    regen_audio: bool
    regen_fx: bool
    regen_eli: bool
    phase_ranges: dict[str, tuple[float, float]] = field(default_factory=dict)
    video_url: str = ""


def _phase_progress(ctx: ExportContext, phase_name: str, frac: float) -> float:
    """Map a 0-1 fraction within a phase to the global progress range."""
    start, end = ctx.phase_ranges[phase_name]
    return start + frac * (end - start)


def _build_phase_ranges(ctx: ExportContext) -> None:
    """Compute phase_weights and set ctx.phase_ranges."""
    phase_weights: dict[str, int] = {}
    if ctx.regen_audio:
        phase_weights["audio"] = 25
    if ctx.regen_images:
        phase_weights["images"] = 18
    if ctx.regen_images or ctx.regen_audio:
        phase_weights["persist"] = 2
    if ctx.regen_fx:
        phase_weights["fx"] = 15
    if ctx.regen_eli:
        phase_weights["eli"] = 12
    phase_weights["render"] = 23
    phase_weights["copy"] = 3

    total_weight = sum(phase_weights.values())
    phase_ranges: dict[str, tuple[float, float]] = {}
    cursor = 0.0
    for phase_name in ["audio", "images", "persist", "fx", "eli", "render", "copy"]:
        if phase_name in phase_weights:
            start = cursor
            span = phase_weights[phase_name] / total_weight
            cursor += span
            phase_ranges[phase_name] = (start, start + span)

    ctx.phase_ranges = phase_ranges


def _check_cancelled(job_id: str) -> None:
    """Raise RuntimeError if the job has been cancelled."""
    if is_cancelled(job_id):
        raise RuntimeError("Job cancelled")


def _reload_content(script_id: str) -> ScriptContent:
    """Load fresh ScriptContent from DB (for use in background threads)."""
    from database import engine
    with Session(engine) as session:
        record = session.get(Script, script_id)
        if not record:
            raise RuntimeError(f"Script {script_id} not found")
        return ScriptContent.model_validate(json.loads(record.script_json))


def _phase_images(ctx: ExportContext) -> None:
    """Generate images for all scenes (skips title cards)."""
    from pipeline.image_gen import (
        generate_comparison_board_cutouts,
        generate_flipflop_cutouts,
        generate_popup_sequence_cutouts,
        generate_scene_frames_v2,
        generate_scene_image,
        generate_stat_card_cutout,
        generate_visual_layer_panels,
    )

    non_tc = [sc for sc in ctx.scenes if not sc.get("is_title_card")]
    scene_count = len(non_tc)
    content_now = _reload_content(ctx.script_id)
    logger.info("[%s] Phase: images — generating %d scene images", ctx.script_id, scene_count)
    for i, sc_info in enumerate(non_tc):
        _check_cancelled(ctx.job.id)
        p = _phase_progress(ctx, "images", i / scene_count)
        update_job(ctx.job.id, progress=p, current_step=f"Generating image ({i+1}/{scene_count})...")
        sid = sc_info["scene_id"]
        scene_now = find_scene_in_content(content_now, sid)
        visual_layers = sc_info.get("visual_layers")
        if visual_layers is None and scene_now is not None:
            visual_layers = [layer.model_dump() for layer in scene_now.visual_layers]
        visual_layers = visual_layers or []
        visual_mode = sc_info.get("visual_mode") or (scene_now.visual_mode if scene_now is not None else "full_frame")
        treatment = visual_mode if visual_mode in {"video", "popup_sequence", "flipflop", "comparison_board", "stat_card"} else "full_frame"
        if treatment != "full_frame":
            logger.info(
                "[%s] Skipping full scene image for %s scene %s (%d/%d)",
                ctx.script_id,
                treatment,
                sid,
                i + 1,
                scene_count,
            )
            sc_info["_image_url"] = ""
            sc_info["_frame_urls"] = []
        elif visual_mode in {"multi_frame", "continuous"} and scene_now is not None and scene_now.frame_directives:
            logger.info("[%s] Generating %s frames for scene %s (%d/%d)", ctx.script_id, visual_mode, sid, i + 1, scene_count)
            frame_results = generate_scene_frames_v2(
                scene_id=sid,
                frame_directives=[directive.model_dump() for directive in scene_now.frame_directives],
                script_id=ctx.script_id,
                visual_prompt=sc_info.get("visual_prompt") or scene_now.visual_prompt,
                contains_person=bool(sc_info.get("contains_person") or scene_now.contains_person),
                force=True,
            )
            frame_urls = [url for url, _, _ in frame_results]
            sc_info["_image_url"] = next((url for url in frame_urls if url), "")
            sc_info["_frame_urls"] = frame_urls
        elif visual_mode == "captions" and not str(
            sc_info.get("visual_prompt") or (scene_now.visual_prompt if scene_now else "")
        ).strip():
            logger.info(
                "[%s] Skipping image generation for text-only captions scene %s (%d/%d)",
                ctx.script_id,
                sid,
                i + 1,
                scene_count,
            )
            sc_info["_image_url"] = ""
            sc_info["_frame_urls"] = []
        else:
            logger.info("[%s] Generating image for scene %s (%d/%d)", ctx.script_id, sid, i + 1, scene_count)
            image_url, _, _ = generate_scene_image(sid, sc_info["visual_prompt"], ctx.script_id, force=True)
            sc_info["_image_url"] = image_url
            sc_info["_frame_urls"] = None
        if treatment in {"popup_sequence", "flipflop", "comparison_board", "stat_card"} and visual_layers:
            logger.info(
                "[ANIMATION_TYPE] generating panels scene=%s animation_type=%s layers=%d",
                sid,
                treatment,
                len(visual_layers),
            )
            layer_dicts = [
                layer.model_dump() if hasattr(layer, "model_dump") else dict(layer)
                for layer in visual_layers
            ]
            contains_person = bool(sc_info.get("contains_person") or (scene_now.contains_person if scene_now is not None else False))
            if treatment == "popup_sequence":
                sc_info["_visual_layers"] = generate_popup_sequence_cutouts(
                    scene_id=sid,
                    layers=layer_dicts,
                    script_id=ctx.script_id,
                    scene_prompt=sc_info.get("visual_prompt") or (scene_now.visual_prompt if scene_now is not None else ""),
                    force=True,
                    contains_person=contains_person,
                )
            elif treatment == "comparison_board":
                sc_info["_visual_layers"] = generate_comparison_board_cutouts(
                    scene_id=sid,
                    layers=layer_dicts,
                    script_id=ctx.script_id,
                    scene_prompt=sc_info.get("visual_prompt") or (scene_now.visual_prompt if scene_now is not None else ""),
                    force=True,
                )
            elif treatment == "flipflop":
                sc_info["_visual_layers"] = generate_flipflop_cutouts(
                    scene_id=sid,
                    layers=layer_dicts,
                    script_id=ctx.script_id,
                    scene_prompt=sc_info.get("visual_prompt") or (scene_now.visual_prompt if scene_now is not None else ""),
                    force=True,
                    contains_person=contains_person,
                )
            elif treatment == "stat_card":
                sc_info["_visual_layers"] = generate_stat_card_cutout(
                    scene_id=sid,
                    layers=layer_dicts,
                    script_id=ctx.script_id,
                    scene_prompt=sc_info.get("visual_prompt") or (scene_now.visual_prompt if scene_now is not None else ""),
                    force=True,
                )
            else:
                sc_info["_visual_layers"] = generate_visual_layer_panels(
                    sid,
                    layer_dicts,
                    ctx.script_id,
                    force=True,
                    contains_person=contains_person,
                    visual_treatment=treatment,
                )
    logger.info("[%s] Phase: images — complete (%d scenes)", ctx.script_id, scene_count)


def _phase_audio(ctx: ExportContext) -> None:
    """Generate audio for all scenes."""
    from pipeline.voiceover import generate_scene_audio, prepare_tts_text, resolve_tts_model_and_settings

    scene_count = len(ctx.scenes)
    model_id, voice_settings = resolve_tts_model_and_settings(None, None)
    logger.info("[%s] Phase: audio — generating %d scene audio clips (voice %s)", ctx.script_id, scene_count, ctx.voice_id)
    for i, sc_info in enumerate(ctx.scenes):
        _check_cancelled(ctx.job.id)
        p = _phase_progress(ctx, "audio", i / scene_count)
        update_job(ctx.job.id, progress=p, current_step=f"Generating audio ({i+1}/{scene_count})...")
        logger.info("[%s] Generating audio for scene %s (%d/%d)", ctx.script_id, sc_info["scene_id"], i + 1, scene_count)
        narration = prepare_tts_text(
            sc_info["narration"],
            model_id=model_id,
            is_title_card=bool(sc_info.get("is_title_card")),
            level_number=int(sc_info.get("segment_index", 0)) + 1 if sc_info.get("is_title_card") else None,
        )
        audio_url, audio_duration, word_timestamps, phrase_timestamps = generate_scene_audio(
            sc_info["scene_id"],
            narration,
            ctx.voice_id,
            ctx.script_id,
            model_id=model_id,
            voice_settings=voice_settings,
        )
        sc_info["_audio_url"] = audio_url
        sc_info["_audio_duration"] = audio_duration
        sc_info["_word_timestamps"] = word_timestamps
        sc_info["_phrase_timestamps"] = phrase_timestamps
    logger.info("[%s] Phase: audio — complete (%d scenes)", ctx.script_id, scene_count)


def _phase_persist(ctx: ExportContext) -> None:
    """Persist regenerated assets to DB in a single write."""
    logger.info("[%s] Phase: persist — saving %d scene assets to DB", ctx.script_id, len(ctx.scenes))
    update_job(ctx.job.id, progress=_phase_progress(ctx, "persist", 0), current_step="Saving scene data...")

    from database import engine
    from models.script import VisualLayer

    with Session(engine) as session:
        record = session.get(Script, ctx.script_id)
        if not record:
            return
        content = ScriptContent.model_validate(json.loads(record.script_json))
        scene_map = {sc.id: sc for seg in content.segments for sc in seg.scenes}

        for sc_info in ctx.scenes:
            sc = scene_map.get(sc_info["scene_id"])
            if not sc:
                continue
            # Fill in missing fields from existing data if not regenerated
            if "_image_url" not in sc_info:
                sc_info["_image_url"] = sc.image_url
                sc_info["_frame_urls"] = sc.frame_urls
            if "_audio_url" not in sc_info:
                sc_info["_audio_url"] = sc.audio_url
                sc_info["_audio_duration"] = sc.audio_duration_seconds
                sc_info["_word_timestamps"] = sc.word_timestamps
                sc_info["_phrase_timestamps"] = sc.phrase_timestamps

            if "_image_url" in sc_info:
                sc.image_url = sc_info["_image_url"] or ""
            if "_frame_urls" in sc_info:
                sc.frame_urls = sc_info["_frame_urls"] or []
            sc.audio_url = sc_info.get("_audio_url", sc.audio_url)
            sc.audio_duration_seconds = sc_info.get("_audio_duration", sc.audio_duration_seconds)
            sc.word_timestamps = sc_info.get("_word_timestamps", sc.word_timestamps)
            sc.phrase_timestamps = sc_info.get("_phrase_timestamps", sc.phrase_timestamps)
            if "_visual_layers" in sc_info:
                sc.visual_layers = [VisualLayer.model_validate(layer) for layer in sc_info["_visual_layers"]]
            if "_visual_mode_override" in sc_info:
                sc.set_visual_mode(sc_info["_visual_mode_override"])

        record.script_json = content.model_dump_json()
        session.add(record)
        session.commit()


def _phase_fx(ctx: ExportContext) -> None:
    """Generate FX for all scenes (skips title cards), persist in a single write."""
    from pipeline.fx_generator import generate_scene_fx

    non_tc = [sc for sc in ctx.scenes if not sc.get("is_title_card")]
    scene_count = len(non_tc)
    logger.info("[%s] Phase: fx — generating FX for %d scenes", ctx.script_id, scene_count)

    # Generate FX for each scene, collecting results
    content_now = _reload_content(ctx.script_id)
    fx_updates: dict[str, dict] = {}
    for i, sc_info in enumerate(non_tc):
        _check_cancelled(ctx.job.id)
        p = _phase_progress(ctx, "fx", i / scene_count)
        update_job(ctx.job.id, progress=p, current_step=f"Generating FX ({i+1}/{scene_count})...")
        scene_now = find_scene_in_content(content_now, sc_info["scene_id"])
        duration = scene_now.audio_duration_seconds or scene_now.duration_estimate_seconds
        scene_data = {
            "id": sc_info["scene_id"],
            "segment": ctx.seg_name,
            "segment_index": 0,
            "scene_index_in_segment": sc_info["sc_idx"],
            "global_index": sc_info["global_idx"],
            "is_first_scene": sc_info["global_idx"] == 0,
            "is_last_scene": sc_info["global_idx"] == ctx.total_scenes - 1,
            "is_first_in_segment": sc_info["sc_idx"] == 0,
            "is_title_card": False,
            "narration": scene_now.narration,
            "duration_seconds": duration,
            "duration_frames": int(duration * FPS),
            "has_multiple_frames": bool(scene_now.frame_urls and len(scene_now.frame_urls) > 1),
            "visual_mode": scene_now.visual_mode,
            "visual_beat": scene_now.visual_beat or "static",
        }
        if scene_now.word_timestamps:
            scene_data["word_timestamps"] = [w.model_dump() for w in scene_now.word_timestamps]
        try:
            fx_result = generate_scene_fx(scene_data)
            fx_updates[sc_info["scene_id"]] = fx_result
        except Exception as e:
            logger.warning("Failed FX for scene %s: %s", sc_info["scene_id"], e)

    # Persist all FX in a single DB write
    if fx_updates:
        from database import engine
        with Session(engine) as session:
            record = session.get(Script, ctx.script_id)
            if record:
                content = ScriptContent.model_validate(json.loads(record.script_json))
                _apply_fx_results(content, fx_updates)
                record.script_json = content.model_dump_json()
                session.add(record)
                session.commit()


def _apply_fx_results(content: ScriptContent, fx_results: dict[str, dict]) -> None:
    scene_map = {sc.id: sc for seg in content.segments for sc in seg.scenes}
    for scene_id, result in fx_results.items():
        sc = scene_map.get(scene_id)
        if sc:
            sc.fx = result["fx"]
            sc.transition_in = result.get("transition_in", "cut")


def _phase_eli(ctx: ExportContext) -> None:
    """Generate Eli pose selection for all scenes (skips title cards)."""
    try:
        from pipeline.eli_animator import generate_eli_batch, generate_scene_eli
    except ImportError:
        logger.warning("eli_animator module not found — skipping Eli phase")
        return

    non_tc = [sc for sc in ctx.scenes if not sc.get("is_title_card")]
    scene_count = len(non_tc)
    logger.info("[%s] Phase: eli — generating Eli poses for %d scenes", ctx.script_id, scene_count)

    content_now = _reload_content(ctx.script_id)

    # Build batch payload, skipping scenes that already opted out via
    # contains_person.
    eligible: list = []
    for sc_info in non_tc:
        scene_now = find_scene_in_content(content_now, sc_info["scene_id"])
        if scene_now is None or scene_now.contains_person:
            continue
        eligible.append(scene_now)

    _check_cancelled(ctx.job.id)
    update_job(
        ctx.job.id,
        progress=_phase_progress(ctx, "eli", 0.0),
        current_step=f"Generating Eli ({len(eligible)} scenes)...",
    )

    scenes_payload = [{"id": sc.id, "narration": sc.narration or ""} for sc in eligible]
    eli_updates: dict[str, dict] = generate_eli_batch(scenes_payload, script_id=ctx.script_id)

    # Per-scene retry for any scene the batch couldn't deliver.
    previous_corner: str | None = None
    for sc in eligible:
        _check_cancelled(ctx.job.id)
        if sc.id in eli_updates:
            previous_corner = eli_updates[sc.id].get("corner")
            continue
        try:
            eli_result = generate_scene_eli(
                sc.narration,
                previous_corner=previous_corner,
                script_id=ctx.script_id,
            )
            eli_updates[sc.id] = eli_result
            previous_corner = eli_result.get("corner")
        except Exception as e:
            logger.warning("Failed Eli for scene %s: %s", sc.id, e)

    # Persist all Eli overlays in a single DB write
    if eli_updates:
        from database import engine
        with Session(engine) as session:
            record = session.get(Script, ctx.script_id)
            if record:
                content = ScriptContent.model_validate(json.loads(record.script_json))
                scene_map = {sc.id: sc for seg in content.segments for sc in seg.scenes}
                for scene_id, eli_overlay in eli_updates.items():
                    sc = scene_map.get(scene_id)
                    if sc:
                        sc.eli_overlay = eli_overlay
                record.script_json = content.model_dump_json()
                session.add(record)
                session.commit()


def _phase_render(ctx: ExportContext) -> None:
    """Render only the first segment via Remotion (always runs). Sets ctx.video_url.

    Creates a filtered ScriptContent containing only the first segment, so
    render_full_video produces a short clip instead of the entire video.
    Uses timer-based progress instead of Remotion's sparse on_progress callbacks.
    """
    render_start, render_end = ctx.phase_ranges["render"]
    update_job(ctx.job.id, progress=render_start, current_step="Rendering first segment...")
    content_now = _reload_content(ctx.script_id)

    # Filter to first segment only
    first_seg_content = content_now.model_copy(update={"segments": content_now.segments[:1]})
    render_scene_count = sum(len(s.scenes) for s in first_seg_content.segments)

    logger.info("[%s] Phase: render — starting Remotion render (first segment, %d scenes)", ctx.script_id, render_scene_count)
    estimated = estimate_render_time(render_scene_count)
    stop_timer = threading.Event()

    def _timer_updater():
        start = time.monotonic()
        while not stop_timer.is_set():
            elapsed = time.monotonic() - start
            frac = min(0.95, elapsed / estimated) if estimated > 0 else 0.5
            progress = render_start + frac * (render_end - render_start)
            update_job(ctx.job.id, progress=progress)
            stop_timer.wait(1.0)

    timer = threading.Thread(target=_timer_updater, daemon=True)
    timer.start()

    try:
        _check_cancelled(ctx.job.id)
        ctx.video_url = render_full_video(
            script_id=ctx.script_id,
            content=first_seg_content,
            on_progress=None,
            cancel_check=lambda: _check_cancelled(ctx.job.id),
            title="",  # Don't copy to Downloads inside render_full_video — _phase_copy handles it
            speed=1.25,
            brand=ctx.brand_dict,
        )
    finally:
        stop_timer.set()
        timer.join(timeout=2)

    _check_cancelled(ctx.job.id)
    update_job(ctx.job.id, progress=render_end)
    logger.info("[%s] Phase: render — Remotion complete (first segment), output: %s", ctx.script_id, ctx.video_url)


def _phase_copy_to_downloads(ctx: ExportContext) -> None:
    """Copy rendered video to Downloads folder (always runs)."""
    logger.info("[%s] Phase: copy — copying to Downloads", ctx.script_id)
    update_job(ctx.job.id, progress=ctx.phase_ranges["copy"][0], current_step="Copying to Downloads...")
    projects_prefix = "/static/projects/"
    if ctx.video_url.startswith(projects_prefix):
        relative = ctx.video_url[len(projects_prefix):]
        src_path = str(DATA_DIR / "projects" / relative)
    else:
        src_path = ctx.video_url

    dest_name = shortform_video_filename(ctx.seg_name, 1, ctx.total_segments)
    dest_path = copy_to_project_downloads(ctx.project_title, src_path, dest_name)
    logger.info("Export test copied to: %s", dest_path)
