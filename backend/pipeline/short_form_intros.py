"""Short-form intro voiceover pipeline.

Generates per-segment intro voiceovers ("{stripped video title} — {segment name}")
via ElevenLabs and persists ShortIntro metadata into ScriptContent.short_intros.
"""

import logging
import re

logger = logging.getLogger(__name__)


def strip_leading_number(title: str) -> str:
    """Strip leading digit(s) followed by whitespace from a title.

    Examples:
        "8 Unsolved Crimes ..." -> "Unsolved Crimes ..."
        "How to Train Your Dragon" -> "How to Train Your Dragon"
        "8Track Memories" -> "8Track Memories"  (no following whitespace)
    """
    return re.sub(r"^\d+\s+", "", title)


def build_display_text(video_title: str, segment_name: str) -> str:
    """Build the display string spoken by Eli and rendered on the title card.

    Format: "{stripped video title} — {segment name}"
    The em-dash (U+2014) is the spoken/visual handoff between the two zones.
    """
    return f"{strip_leading_number(video_title)} — {segment_name}"
