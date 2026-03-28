"""Auto-editing pipeline — uses Claude to generate an editing timeline, then renders via FFmpeg."""

import json
import logging
import os
import subprocess
from pathlib import Path
from typing import Callable

from integrations.claude_client import chat
from models.auto_edit import AutoEditTimeline, SceneTimeline, TextPhrase
from models.script import ScriptContent
from pipeline.ffmpeg_builder import build_auto_edit_scene_cmd, build_concat_with_transitions_cmd

log = logging.getLogger(__name__)

_data_dir = Path(os.environ.get("YAM_DATA_DIR", Path(__file__).resolve().parents[2] / "data"))

ProgressCallback = Callable[[float, str], None] | None

_GUIDE_PATH = Path(__file__).resolve().parent.parent / "prompts" / "video_editing_guide.md"
_STYLE_GUIDE = _GUIDE_PATH.read_text() if _GUIDE_PATH.exists() else ""

_SYSTEM_PROMPT = (_STYLE_GUIDE + "\n\n" if _STYLE_GUIDE else "") + """\
You are generating an editing timeline for a faceless educational YouTube video.

Given a scene manifest, produce a JSON object with creative editing decisions.

Rules:
- Alternate motion_profile between "slow_zoom_in" and "slow_zoom_out" on consecutive scenes to create visual breathing. Occasionally use "slow_pan" for variety.
- Use "hard_cut" for 85% of transitions. Use "dip_to_black" for punchline or dramatic moments.
- TEXT POPS — Be SELECTIVE. Only create text_phrases for the most impactful moments:
  - Key facts, surprising statistics, punchlines, important terms, emotional hooks
  - Aim for 2-4 phrases per scene MAXIMUM — most of the video should have NO on-screen text
  - Choose an animation style per phrase: "pop" (bouncy overshoot), "slam" (instant hard cut), "scale_up" (grow in), "fade_in" (alpha fade)
  - Set uppercase to true for impact phrases, false for softer/subtle ones
  - Use the word_timestamps to set precise start_ms/end_ms timing
- Set accent_color to a vibrant color that complements the video topic (e.g. neon cyan, electric blue, hot pink).
- For sfx_triggers, assign appropriate categories: "impact" on scene entry, "ui" on text phrase appearance, "accent" on individual word highlights, "microdrop" on punchlines, "transition" on dip_to_black cuts.

Output ONLY valid JSON matching this exact schema — no markdown fences, no commentary:
{
  "accent_color": "#00FFFF",
  "scenes": [
    {
      "scene_id": "...",
      "motion_profile": "slow_zoom_in",
      "transition": "hard_cut",
      "text_phrases": [
        {
          "words": ["surprising", "fact", "here"],
          "start_ms": 2400,
          "end_ms": 3800,
          "highlight_color": "#00FFFF",
          "animation": "pop",
          "uppercase": true
        }
      ],
      "sfx_triggers": [
        {"category": "impact", "trigger_time_ms": 0, "selection": "random"}
      ]
    }
  ]
}
"""


def _build_scene_manifest(content: ScriptContent) -> str:
    """Build a compact scene manifest for Claude to make editing decisions on."""
    scenes_data = []
    for seg in content.segments:
        for scene in seg.scenes:
            duration = scene.audio_duration_seconds if scene.audio_duration_seconds > 0 else scene.duration_estimate_seconds
            scene_info: dict = {
                "scene_id": scene.id,
                "narration": scene.narration,
                "duration_seconds": duration,
                "visual_description": scene.visual_prompt[:200],
                "is_title_card": scene.is_title_card,
            }
            if scene.word_timestamps:
                scene_info["word_timestamps"] = scene.word_timestamps
            scenes_data.append(scene_info)

    return json.dumps({"title": content.title, "scene_count": len(scenes_data), "scenes": scenes_data}, indent=2)


def generate_edit_timeline(content: ScriptContent) -> AutoEditTimeline:
    """Call Claude to generate an AutoEditTimeline from a script's scene manifest.

    Falls back to a deterministic default timeline if Claude fails to parse.
    """
    manifest = _build_scene_manifest(content)

    raw = chat(
        system=_SYSTEM_PROMPT,
        user_message=f"Generate an editing timeline for this video:\n\n{manifest}",
        max_tokens=8192,
    )

    # Strip markdown fences if present
    text = raw.strip()
    if text.startswith("```"):
        text = text.split("\n", 1)[1] if "\n" in text else text[3:]
    if text.endswith("```"):
        text = text[:-3]
    text = text.strip()

    try:
        data = json.loads(text)
        return AutoEditTimeline.model_validate(data)
    except (json.JSONDecodeError, Exception) as e:
        log.warning("Failed to parse Claude timeline response, using fallback: %s", e)
        return _fallback_timeline(content)


def _fallback_timeline(content: ScriptContent) -> AutoEditTimeline:
    """Generate a deterministic timeline when Claude parsing fails."""
    scenes: list[SceneTimeline] = []
    motions = ["slow_zoom_in", "slow_zoom_out"]

    for i, seg in enumerate(content.segments):
        for j, scene in enumerate(seg.scenes):
            flat_idx = sum(len(s.scenes) for s in content.segments[:i]) + j
            motion = motions[flat_idx % 2]

            # Build text phrases from word_timestamps — selective (key moments only)
            phrases: list[TextPhrase] = []
            animations = ["pop", "slam", "scale_up", "fade_in"]
            if scene.word_timestamps:
                # Chunk words into groups of 4
                chunks: list[list[dict]] = []
                chunk: list[dict] = []
                for wt in scene.word_timestamps:
                    chunk.append(wt)
                    if len(chunk) >= 4:
                        chunks.append(chunk)
                        chunk = []
                if chunk:
                    chunks.append(chunk)

                # Select ~25% of chunks: every 4th + any containing numbers/stats
                for ci, c in enumerate(chunks):
                    text = " ".join(w["word"] for w in c)
                    has_number = any(ch.isdigit() for ch in text)
                    if has_number or ci % 4 == 0:
                        phrases.append(TextPhrase(
                            words=[w["word"] for w in c],
                            start_ms=c[0]["start_ms"],
                            end_ms=c[-1]["end_ms"],
                            animation=animations[len(phrases) % len(animations)],
                            uppercase=True,
                        ))

            # Use dip_to_black every 5th scene for variety
            transition = "dip_to_black" if flat_idx > 0 and flat_idx % 5 == 0 else "hard_cut"

            scenes.append(SceneTimeline(
                scene_id=scene.id,
                motion_profile=motion,
                transition=transition,
                text_phrases=phrases,
            ))

    return AutoEditTimeline(accent_color="#00FFFF", scenes=scenes)


def _scene_image_path(script_id: str, scene_id: str) -> str:
    return str(_data_dir / "projects" / script_id / "images" / f"{scene_id}.png")


def _scene_audio_path(script_id: str, scene_id: str) -> str:
    return str(_data_dir / "projects" / script_id / "audio" / f"{scene_id}.mp3")


def _renders_dir(script_id: str) -> Path:
    d = _data_dir / "projects" / script_id / "renders"
    d.mkdir(parents=True, exist_ok=True)
    return d


def _run_ffmpeg(cmd: list[str]) -> None:
    log.info("Running: %s", " ".join(cmd))
    result = subprocess.run(cmd, capture_output=True, text=True, timeout=600)
    if result.returncode != 0:
        log.error("FFmpeg stderr: %s", result.stderr)
        raise RuntimeError(f"FFmpeg failed (exit {result.returncode}): {result.stderr[-500:]}")


def render_auto_edit_video(
    script_id: str,
    content: ScriptContent,
    timeline: AutoEditTimeline,
    width: int = 1920,
    height: int = 1080,
    on_progress: ProgressCallback = None,
    title: str = "",
    speed: float = 1.0,
) -> str:
    """Render full auto-edited video using the Claude-generated timeline.

    Phase A: Render each scene with motion + word-synced text.
    Phase B: Concatenate with transitions (hard cut / dip-to-black).
    Phase C: Output final video.

    Returns web-relative path to the output MP4.
    """
    # Build a lookup from scene_id to timeline entry
    timeline_map = {st.scene_id: st for st in timeline.scenes}

    # Flatten all scenes in order
    all_scenes = []
    for seg in content.segments:
        for sc in seg.scenes:
            all_scenes.append(sc)

    total = len(all_scenes)
    clip_paths: list[str] = []
    transitions: list[str] = []

    renders = _renders_dir(script_id)
    autoedit_dir = renders / "autoedit_scenes"
    autoedit_dir.mkdir(parents=True, exist_ok=True)

    # Phase A: Render each scene
    for i, scene in enumerate(all_scenes):
        if on_progress:
            on_progress(i / (total + 1), f"Auto-editing scene {i + 1}/{total}")

        image_path = _scene_image_path(script_id, scene.id)
        audio_path = _scene_audio_path(script_id, scene.id)

        if not os.path.exists(image_path):
            raise FileNotFoundError(f"Image not found: {image_path}")
        if not os.path.exists(audio_path):
            raise FileNotFoundError(f"Audio not found: {audio_path}")

        duration = scene.audio_duration_seconds if scene.audio_duration_seconds > 0 else scene.duration_estimate_seconds

        st = timeline_map.get(scene.id)
        motion = st.motion_profile if st else "slow_zoom_in"
        transition = st.transition if st else "hard_cut"
        text_phrases = [p.model_dump() for p in st.text_phrases] if st else []

        output_path = str(autoedit_dir / f"{scene.id}.mp4")

        cmd = build_auto_edit_scene_cmd(
            image_path=image_path,
            audio_path=audio_path,
            output_path=output_path,
            duration=duration,
            motion_profile=motion,
            text_phrases=text_phrases if text_phrases else None,
            accent_color=timeline.accent_color,
            width=width,
            height=height,
            speed=speed,
        )
        _run_ffmpeg(cmd)

        clip_paths.append(output_path)
        transitions.append(transition)

    # Phase B: Concatenate with transitions
    if on_progress:
        on_progress(0.9, "Concatenating with transitions...")

    speed_suffix = f"_{speed}x" if speed != 1.0 else ""
    output_filename = f"full_youtube_autoedit{speed_suffix}.mp4"
    final_path = str(renders / output_filename)

    cmd, list_file = build_concat_with_transitions_cmd(
        clip_paths=clip_paths,
        transitions=transitions,
        output_path=final_path,
    )
    try:
        _run_ffmpeg(cmd)
    finally:
        if list_file:
            try:
                os.unlink(list_file)
            except OSError:
                pass

    if on_progress:
        on_progress(1.0, "Complete")

    web_path = f"/static/projects/{script_id}/renders/{output_filename}"

    # Copy to downloads
    if title:
        try:
            from pipeline.video_render import copy_to_downloads, _sanitize_filename
            speed_label = f" ({speed}x)" if speed != 1.0 else ""
            copy_to_downloads(title, final_path, f"{_sanitize_filename(title)} - YouTube AutoEdit{speed_label}.mp4")
        except Exception:
            log.warning("Failed to copy auto-edit to downloads", exc_info=True)

    return web_path
