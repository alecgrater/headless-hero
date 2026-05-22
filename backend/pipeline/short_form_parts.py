"""Short-form part indicator helpers."""

from models.script import ScriptContent


def short_form_part_indicator(content: ScriptContent, segment_idx: int) -> str:
    """Return the visible Part N/M label for life-as-a shorts."""
    if content.format_id != "life-as-a":
        return ""
    total = len(content.segments)
    if segment_idx < 0 or segment_idx >= total:
        return ""
    return f"Part {segment_idx + 1}/{total}"
