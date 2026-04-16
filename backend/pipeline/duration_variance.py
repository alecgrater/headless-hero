"""Duration variance — tighten overlong high-energy scenes after voiceover.

After batch voiceover, checks quick_cuts and aha_subtitle scenes against a
duration threshold. If any exceed it, rewrites narration via Claude and
re-voices in a single pass.
"""

import json
import logging

from config import DEFAULT_TTS_MODEL, strip_markdown_fences
from integrations.claude_client import chat
from models.script import Scene, Script, ScriptContent
from pipeline.voiceover import generate_scene_audio

logger = logging.getLogger(__name__)

HIGH_ENERGY_BEATS = {"quick_cuts", "aha_subtitle"}
MAX_DURATION_SECONDS = 10.0


def _flag_overlong_scenes(content: ScriptContent) -> list[Scene]:
    """Return high-energy scenes whose audio exceeds the duration threshold."""
    flagged: list[Scene] = []
    for scene in content.all_scenes():
        if (
            scene.visual_beat in HIGH_ENERGY_BEATS
            and scene.audio_duration_seconds > MAX_DURATION_SECONDS
        ):
            flagged.append(scene)
    return flagged
