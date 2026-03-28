"""Real media content modifier (gaming clips + hardware images).

Injects real media guidelines into script generation prompts and
overrides scene rendering for gameplay clip scenes.
"""

import os
from pathlib import Path

from models.script import Scene, ScriptContent, TextOverlayConfig
from pipeline.modifiers.base import ContentModifier, ModifierMeta

_data_dir = Path(os.environ.get("YAM_DATA_DIR", Path(__file__).resolve().parents[3] / "data"))

# Instructions previously hardcoded in scriptwriter.SYSTEM_PROMPT lines 76-90
_REAL_MEDIA_PROMPT_INSTRUCTIONS = """\

Real media guidelines (gaming/hardware content):
- Each scene has a "media_type" field: "ai_generated" (default), "gameplay_clip", or "hardware_image".
- Each scene has a "search_query" field (empty string by default).
- When the video topic involves gaming, video games, consoles, or gaming hardware:
  - Tag scenes showing actual gameplay footage as "gameplay_clip" with a specific YouTube \
search query (e.g. "Halo Infinite gameplay 4K", "GTA V PC gameplay 60fps"). The search \
query should be specific enough to find relevant footage.
  - Tag scenes showing physical hardware (consoles, controllers, headsets, GPUs) as \
"hardware_image" with a search query (e.g. "PlayStation 5 console close up review", \
"RTX 4090 unboxing"). These will extract a still frame from a YouTube video.
  - All other scenes (conceptual, explanatory, metaphorical, title cards) should remain \
"ai_generated" with an empty search_query — AI illustration is better for abstract concepts.
- Only use real media types when showing specific, recognizable games or hardware. If a scene \
is about a general concept (e.g. "the evolution of gaming"), keep it as ai_generated.
- Include "media_type" and "search_query" in each scene object in the JSON output."""

# JSON schema fields to add when real media is active
_REAL_MEDIA_SCHEMA_ADDITION = """\
          "media_type": "ai_generated",
          "search_query": \"\""""


class RealMediaModifier(ContentModifier):
    meta = ModifierMeta(
        id="real_media",
        name="Real Media (Gaming)",
        description="Use real gameplay clips and hardware images from YouTube instead of AI art.",
        icon="🎮",
    )

    def modify_script_prompt(self, system_prompt: str, user_message: str) -> tuple[str, str]:
        return system_prompt + _REAL_MEDIA_PROMPT_INSTRUCTIONS, user_message

    def get_render_override(self, scene: Scene, script_id: str, **kwargs) -> list[str] | None:
        if getattr(scene, "media_type", "ai_generated") != "gameplay_clip":
            return None

        clip_path = str(_data_dir / "projects" / script_id / "clips" / f"{scene.id}.mp4")
        audio_path = str(_data_dir / "projects" / script_id / "audio" / f"{scene.id}.mp3")

        if not os.path.exists(clip_path):
            raise FileNotFoundError(f"Gameplay clip not found: {clip_path}")
        if not os.path.exists(audio_path):
            raise FileNotFoundError(f"Audio not found: {audio_path}")

        width = kwargs.get("width", 1920)
        height = kwargs.get("height", 1080)
        fade_out = kwargs.get("fade_out", 0.3)
        speed = kwargs.get("speed", 1.0)

        duration = scene.audio_duration_seconds if scene.audio_duration_seconds > 0 else scene.duration_estimate_seconds
        toc = scene.text_overlay_config or TextOverlayConfig()

        from pipeline.ffmpeg_builder import build_video_clip_scene_cmd

        return build_video_clip_scene_cmd(
            clip_path=clip_path,
            audio_path=audio_path,
            output_path=kwargs["output_path"],
            duration=duration,
            width=width,
            height=height,
            text_overlay=scene.text_overlay,
            overlay_position=toc.position,
            overlay_style=toc.style,
            overlay_animation=toc.animation,
            overlay_show_at=toc.show_at,
            overlay_duration=toc.duration,
            fade_out_duration=fade_out,
            speed=speed,
        )

    def get_router(self):
        from api.media import router
        return router
