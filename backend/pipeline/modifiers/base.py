"""Base class and metadata for content modifiers."""

from dataclasses import dataclass


@dataclass
class ModifierMeta:
    """Metadata describing a content modifier for UI display."""

    id: str  # "real_media", "animated_subtitles", "title_cards"
    name: str  # Human-readable name
    description: str  # One-liner for UI card
    icon: str  # Emoji for frontend display


class ContentModifier:
    """Base class for content modifiers.

    Subclasses override only the hooks they need. The pipeline calls each
    hook in registration order for all active modifiers on the brand.
    """

    meta: ModifierMeta

    def modify_script_prompt(self, system_prompt: str, user_message: str) -> tuple[str, str]:
        """Inject modifier instructions into Claude script generation prompt."""
        return system_prompt, user_message

    def modify_script_post(self, content: "ScriptContent", brand: dict) -> "ScriptContent":
        """Post-process the generated script (e.g. insert title cards)."""
        return content

    def modify_scene_pre_render(self, scene: "Scene", script_id: str, brand: dict) -> "Scene":
        """Pre-render hook per scene (e.g. generate title card images)."""
        return scene

    def get_render_override(self, scene: "Scene", script_id: str, **kwargs) -> list[str] | None:
        """Return custom FFmpeg command, or None to use default renderer."""
        return None

    def get_full_render_override(self, script_id: str, content: "ScriptContent", **kwargs) -> str | None:
        """Provide an alternate full-video render. Return web path or None."""
        return None

    def get_router(self) -> "APIRouter | None":
        """Return a FastAPI APIRouter with modifier-specific endpoints, or None."""
        return None
