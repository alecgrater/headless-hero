"""Script data models — matches PRD section 7.2 JSON structure."""

import uuid
from datetime import datetime, timezone

from pydantic import BaseModel, Field as PydanticField
from sqlmodel import Column, Field, SQLModel, Text

# --- Pydantic models for the script JSON structure ---

# --- FX models (used by Remotion renderer) ---

class EmphasisWord(BaseModel):
    """A single emphasis word with frame-precise timing and animation style."""

    word: str
    start_frame: int = 0
    end_frame: int = 0
    style: str = "scale_pop"  # scale_pop | color_flash | size_burst | shake | underline_draw | glow_pulse | typewriter | slide_up | bounce_in | rotate_in | glitch | gradient_sweep
    category: str = "keyword"  # stat | key_noun | emotional | action_verb | contrast | keyword
    font_size: int = 64  # 48-120
    position: str = "bottom_center"  # bottom_center | bottom_left | bottom_right | center | top_center
    word_index: int = 0  # 0-based index into narration word list (for timestamp lookup)
    intensity: int = 2  # 1 (supporting), 2 (important), 3 (peak moment)
    reason: str = ""  # why this word matters (e.g. "shocking statistic", "thesis reversal")

class KineticCaptionsFX(BaseModel):
    """Kinetic emphasis captions — frame-timed emphasis words from narration."""

    words: list[EmphasisWord] = []

class ZoomPunchFX(BaseModel):
    """Zoom punch — quick asymmetric scale hit on key moments."""

    trigger_frame: int = 0
    scale: float = 1.06  # 1.04-1.07

class SceneFX(BaseModel):
    """Complete FX configuration for a scene, assigned by Claude."""

    kinetic_captions: KineticCaptionsFX | None = None
    zoom_punch: ZoomPunchFX | None = None

class ChapterMarker(BaseModel):
    """A chapter marker for the global progress bar."""

    segment_index: int
    label: str
    frame_offset: int  # global frame where this chapter starts

class VideoFX(BaseModel):
    """Video-level FX computed deterministically from segment boundaries."""

    chapter_markers: list[ChapterMarker] = []

class Scene(BaseModel):
    """A single scene within a segment."""

    id: str
    narration: str
    visual_prompt: str
    text_overlay: str = ""
    duration_estimate_seconds: float = 8.0
    is_title_card: bool = False
    image_url: str = ""
    audio_url: str = ""
    audio_duration_seconds: float = 0.0
    word_timestamps: list[dict] | None = None
    media_type: str = "ai_generated"  # "ai_generated" | "gameplay_clip" | "hardware_image"
    search_query: str = ""            # YouTube search query for yt-dlp
    video_clip_url: str = ""          # web-relative path to downloaded clip
    title_card_zoom_target: dict | None = None  # {"x": int, "y": int, "radius": int} for zoompan
    frame_prompts: list[str] = []     # per-frame visual prompts for multi-frame scenes
    frame_urls: list[str] = []        # web-relative paths to frame images
    frame_count: int = 0              # desired frame count (1-8), 0 = use legacy single-image
    fx: dict | None = None             # SceneFX dict — assigned by FX generator, used by Remotion

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
    card_title: str = ""                  # condensed title for composite title card (e.g. "TYPES OF DREAMS")
    card_title_highlight_word: str = ""   # word to render in accent color (e.g. "DREAMS")
    video_fx: dict | None = None          # VideoFX dict — computed deterministically at render time

# --- SQLModel table for persistence ---

class Script(SQLModel, table=True):
    """Persisted script stored in SQLite."""

    __tablename__ = "scripts"

    id: str = Field(default_factory=lambda: uuid.uuid4().hex, primary_key=True)
    brand_id: str = Field(index=True)
    topic_title: str = Field(default="")
    topic_description: str = Field(default="", sa_column=Column(Text))
    script_json: str = Field(default="{}", sa_column=Column(Text))  # serialised ScriptContent
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

# --- Request / response schemas ---

class GenerateScriptRequest(BaseModel):
    topic: str = PydanticField(..., min_length=1, description="Video topic / title")
    description: str = PydanticField(default="", description="Optional topic description or angle")
    brand_id: str = PydanticField(..., description="Brand profile ID for style context")
    segment_count: int | None = PydanticField(
        default=None, ge=2, le=8, description="Desired number of segments (Claude decides if omitted)"
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
