"""Script data models — matches PRD section 7.2 JSON structure."""

import uuid
from datetime import datetime, timezone

from pydantic import BaseModel, Field as PydanticField
from sqlmodel import Column, Field, SQLModel, Text

# --- Pydantic models for the script JSON structure ---

class KenBurnsConfig(BaseModel):
    """Ken Burns motion effect configuration for a scene."""

    effect: str = "none"  # none|zoom_in|zoom_out|pan_left|pan_right|pan_up|pan_down
    intensity: str = "moderate"  # subtle|moderate|dramatic

class TextOverlayConfig(BaseModel):
    """Text overlay styling and animation configuration."""

    position: str = "lower_third"  # top|center|bottom|lower_third
    style: str = "default"  # default|bold|subtitle|title_card
    animation: str = "fade_in"  # none|fade_in|slide_up|typewriter
    show_at: float = 0.0  # seconds offset
    duration: float = 0.0  # 0 = full scene duration

class Scene(BaseModel):
    """A single scene within a segment."""

    id: str
    narration: str
    visual_prompt: str
    text_overlay: str = ""
    duration_estimate_seconds: float = 8.0
    is_title_card: bool = False
    is_animated: bool = False
    visual_prompt_b: str = ""
    image_url: str = ""
    image_url_b: str = ""
    audio_url: str = ""
    audio_duration_seconds: float = 0.0
    ken_burns: KenBurnsConfig | None = None
    text_overlay_config: TextOverlayConfig | None = None
    word_timestamps: list[dict] | None = None
    media_type: str = "ai_generated"  # "ai_generated" | "gameplay_clip" | "hardware_image"
    search_query: str = ""            # YouTube search query for yt-dlp
    video_clip_url: str = ""          # web-relative path to downloaded clip
    title_card_zoom_target: dict | None = None  # {"x": int, "y": int, "radius": int} for zoompan
    frame_prompts: list[str] = []     # per-frame visual prompts for multi-frame scenes
    frame_urls: list[str] = []        # web-relative paths to frame images
    frame_count: int = 0              # desired frame count (1-8), 0 = use legacy single-image
    frame_seed: int | None = None     # seed for visual consistency across frames
    scene_transition: str = ""        # "" | "crossfade" | "slide_left" | "slide_right" | "push_up"

class Segment(BaseModel):
    """A named segment (e.g. "Caffeine") containing multiple scenes."""

    name: str
    scenes: list[Scene]
    circle_color: str = ""              # hex color for composite title card circle background
    title_card_image_prompt: str = ""   # visual prompt for AI-generated circle image

class ScriptContent(BaseModel):
    """The full script payload matching PRD section 7.2."""

    title: str
    segments: list[Segment]
    intro_hook: str = ""
    outro_cta: str = ""
    format: str = "youtube"
    card_title: str = ""                  # condensed title for composite title card (e.g. "TYPES OF DREAMS")
    card_title_highlight_word: str = ""   # word to render in accent color (e.g. "DREAMS")

# --- SQLModel table for persistence ---

class Script(SQLModel, table=True):
    """Persisted script stored in SQLite."""

    __tablename__ = "scripts"

    id: str = Field(default_factory=lambda: uuid.uuid4().hex, primary_key=True)
    brand_id: str = Field(index=True)
    topic_title: str = Field(default="")
    topic_description: str = Field(default="", sa_column=Column(Text))
    script_json: str = Field(default="{}", sa_column=Column(Text))  # serialised ScriptContent
    content_format: str = Field(default="youtube")  # kept for backward compat (unused)
    shortform_platforms: str = Field(default="")  # kept for backward compat (unused)
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

# --- Request / response schemas ---

class GenerateScriptRequest(BaseModel):
    topic: str = PydanticField(..., min_length=1, description="Video topic / title")
    description: str = PydanticField(default="", description="Optional topic description or angle")
    brand_id: str = PydanticField(..., description="Brand profile ID for style context")
    segment_count: int | None = PydanticField(
        default=None, ge=2, le=30, description="Desired number of segments (Claude decides if omitted)"
    )
    animated_scene_count: int = PydanticField(
        default=5, ge=0, le=50, description="Number of scenes to make animated A/B flip (0 = none)"
    )

class GenerateScriptResponse(BaseModel):
    id: str
    script: ScriptContent

class UpdateScriptRequest(BaseModel):
    script: ScriptContent

class RefineSceneRequest(BaseModel):
    segment_index: int
    scene_id: str

class RefineSceneResponse(BaseModel):
    scene: Scene

class ScriptRead(BaseModel):
    id: str
    brand_id: str
    topic_title: str
    topic_description: str
    script: ScriptContent
    created_at: datetime


class ScriptSummary(BaseModel):
    """Lightweight summary for the project dashboard list view."""

    id: str
    brand_id: str
    topic_title: str
    topic_description: str
    created_at: datetime
    segment_count: int
    scene_count: int
    image_count: int
    audio_count: int
    has_renders: bool
    thumbnail_url: str
    status: str  # "script" | "images" | "audio" | "exported"
