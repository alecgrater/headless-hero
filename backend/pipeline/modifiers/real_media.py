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

Real media guidelines — mix real footage with AI art for visual variety:
- Each scene has a "media_type" field: "ai_generated" (default), "gameplay_clip", or "hardware_image".
- Each scene has a "search_query" field (empty string by default).
- Use a MIX of real media and AI-generated art throughout the video. Aim for visual variety \
by alternating between real footage and AI illustrations rather than using only one type.
- When to use "gameplay_clip": a scene references a **specific, recognizable game** by name \
(e.g. Halo, GTA V, Minecraft). Provide a specific YouTube search query like "Halo Infinite \
gameplay 4K" or "GTA V PC gameplay 60fps".
- When to use "hardware_image": a scene references a **specific, recognizable console or \
hardware product** by name (e.g. PlayStation 5, RTX 4090). Provide a search query like \
"PlayStation 5 console close up review" or "RTX 4090 unboxing". These extract a still frame \
from a YouTube video.
- When to use "ai_generated": everything else — general concepts, metaphors, transitions, \
explanations, historical overviews, abstract ideas, or any scene not about a specific named \
game or hardware product. Leave search_query as an empty string. AI illustration is better \
for abstract and conceptual visuals.
- A typical gaming video should have roughly 40-60% real media scenes and 40-60% AI scenes, \
depending on how many specific games/products are discussed.
- Include "media_type" and "search_query" in each scene object in the JSON output."""

_REAL_MEDIA_SHORTFORM_EXTRA = """
- For short-form content: gameplay clips MUST be 8 seconds or less. Keep clips punchy and fast-paced."""

# JSON schema fields to add when real media is active
_REAL_MEDIA_SCHEMA_ADDITION = """\
          "media_type": "ai_generated",
          "search_query": \"\""""


class RealMediaModifier(ContentModifier):
    meta = ModifierMeta(
        id="real_media",
        name="Real Media (Gaming)",
        description="Mix real gameplay clips and hardware images from YouTube with AI art.",
        icon="🎮",
    )

    def modify_script_prompt(self, system_prompt: str, user_message: str) -> tuple[str, str]:
        instructions = _REAL_MEDIA_PROMPT_INSTRUCTIONS
        if "short-form" in system_prompt.lower() or "shortform" in system_prompt.lower():
            instructions += _REAL_MEDIA_SHORTFORM_EXTRA
        return system_prompt + instructions, user_message

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
        is_shortform = height > width  # 9:16 portrait

        duration = scene.audio_duration_seconds if scene.audio_duration_seconds > 0 else scene.duration_estimate_seconds
        toc = scene.text_overlay_config or TextOverlayConfig()

        if is_shortform:
            # For shortform: center-crop 16:9 source to 9:16 portrait
            from pipeline.ffmpeg_builder import build_shortform_clip_scene_cmd

            return build_shortform_clip_scene_cmd(
                clip_path=clip_path,
                audio_path=audio_path,
                output_path=kwargs["output_path"],
                duration=duration,
                width=width,
                height=height,
                speed=speed,
            )

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
