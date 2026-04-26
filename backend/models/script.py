"""Script data models — matches PRD section 7.2 JSON structure."""

import uuid
from datetime import datetime, timezone
from typing import Literal

from pydantic import BaseModel, Field as PydanticField
from sqlmodel import Column, Field, SQLModel, Text

# --- Pydantic models for the script JSON structure ---

# --- FX models (used by Remotion renderer) ---

class ZoomPunchFX(BaseModel):
    """Zoom punch — quick asymmetric scale hit on key moments."""

    trigger_word: str | None = None
    trigger_frame: int = 0
    scale: float = 1.06  # 1.04-1.07

class DriftFX(BaseModel):
    """Camera drift — slow continuous camera motion over the entire scene."""

    motion: str  # "zoom_in" | "zoom_out" | "pan_left" | "pan_right" | "drift_diagonal"
    intensity: float  # 0.05-0.08
    anchor: str  # 9-point grid: "top-left" | "top-center" | ... | "bottom-right"

class SceneFX(BaseModel):
    """Complete FX configuration for a scene, assigned by Claude."""

    zoom_punch: ZoomPunchFX | None = None
    drift: DriftFX | None = None

class EliKeyframe(BaseModel):
    """A keyframe in the Eli animation timeline."""
    start_frame: int
    end_frame: int
    frame_id: str       # matches manifest frame id (e.g., "neutral_standing")
    transition: str = "cut"  # "cut" | "crossfade"
    mood: str | None = None              # "ambient" | "reaction"
    position_hint: str | None = None     # deprecated — kept for old scripts

class EliOverlay(BaseModel):
    """Eli character overlay configuration for a scene."""
    enabled: bool = True
    corner: Literal["TL", "TR", "BL", "BR"] = "BR"
    keyframes: list[EliKeyframe] = []

class FrameDirective(BaseModel):
    """Per-frame generation directive for the Visual Beat System."""
    prompt: str
    source: str = "ai_generated"       # "ai_generated" | "real_photo" | "subtitle" | "gameplay_video" | "stock_photo" | "user_upload"
    search_query: str = ""
    transition: str = "crossfade"      # "cut" | "crossfade" | "fade_black"
    reference_previous: bool = True
    contains_person: bool = False      # true when frame depicts a human figure


class ChapterMarker(BaseModel):
    """A chapter marker for the global progress bar."""

    segment_index: int
    label: str
    frame_offset: int  # global frame where this chapter starts

class VideoFX(BaseModel):
    """Video-level FX computed deterministically from segment boundaries."""

    chapter_markers: list[ChapterMarker] = []

class HookScoreDimension(BaseModel):
    """A single scored dimension of the hook."""
    score: int  # 0-100
    reasoning: str

class HookScore(BaseModel):
    """30-second hook retention score."""
    promise: HookScoreDimension
    tension: HookScoreDimension
    payoff_hint: HookScoreDimension
    overall: int  # 0-100
    suggestions: list[str] = []

class Scene(BaseModel):
    """A single scene within a segment."""

    id: str
    narration: str
    visual_prompt: str
    duration_estimate_seconds: float = 8.0
    is_title_card: bool = False
    image_url: str = ""
    audio_url: str = ""
    audio_duration_seconds: float = 0.0
    word_timestamps: list[dict] | None = None
    phrase_timestamps: list[dict] | None = None
    title_card_zoom_target: dict | None = None  # {"x": int, "y": int, "radius": int} for zoompan
    frame_urls: list[str] = []        # web-relative paths to frame images
    fx: dict | None = None             # SceneFX dict — assigned by FX generator, used by Remotion
    eli_overlay: dict | None = None    # EliOverlay dict — Eli character animation keyframes
    visual_beat: str = "static"        # "static" | "continuous" | "quick_cuts" | "aha_subtitle" | "montage"
    frame_directives: list[dict] = []  # FrameDirective dicts; validated at runtime
    contains_person: bool = False       # true if any frame depicts a human figure
    # --- Scene-boundary transition ---
    transition_in: str = "cut"  # "cut" | "fade_black" | "flash_white" | "wipe"
    # --- Micro-timeline visual timing overrides ---
    frame_timings: list[float] | None = None  # seconds into scene when each frame starts; None = even split
    visual_in_seconds: float = 0.0      # visual appears this many seconds into the audio
    visual_out_seconds: float = 0.0     # visual ends this many seconds before audio ends
    # --- Multi-source media ---
    media_source: str = "ai"            # "ai" | "gameplay_video" | "stock_photo" | "user_upload"
    gameplay_game_override: str = ""    # per-scene game name override (falls back to script-level)
    video_url: str = ""                 # web-relative path to gameplay/uploaded video clip
    upload_url: str = ""                # web-relative path to user-uploaded media
    original_visual_prompt: str = ""    # preserved AI-art prompt when analyzer overwrites visual_prompt

class Segment(BaseModel):
    """A named segment (e.g. "Caffeine") containing multiple scenes."""

    name: str
    short_name: str = ""                # 3-word-max label for thumbnail/title card display
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
    card_subtitle: str = ""              # action subtitle below title (e.g. "RE-WRITING HISTORY")
    video_fx: dict | None = None          # VideoFX dict — computed deterministically at render time
    eli_position: dict | None = None      # Per-video Eli overlay position override {x, y}
    segment_timer_enabled: bool = True    # Global toggle for segment countdown timer overlay
    subtitle_highlight_enabled: bool = True  # Global toggle for active word highlight in subtitles
    seo_metadata: dict | None = None      # Generated SEO metadata (title, description, tags)
    hook_score: dict | None = None        # 30-second hook retention score (HookScore dict)
    # --- Multi-source media ---
    gameplay_enabled: bool = False
    stock_photo_enabled: bool = False
    gameplay_game_name: str = ""

    def all_scenes(self) -> list["Scene"]:
        """Flatten all scenes from all segments in order."""
        return [scene for seg in self.segments for scene in seg.scenes]

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
    brand_id: str | None = PydanticField(default=None, description="Brand profile ID (auto-resolved if omitted)")
    animated_scene_count: int = PydanticField(
        default=5, ge=0, le=50, description="Number of scenes to make animated A/B flip (0 = none)"
    )
    model: str | None = PydanticField(default=None, description="Override SCRIPT_MODEL setting for this request")
    segmented: bool = PydanticField(default=False, description="Use two-phase segmented generation (one API call per segment)")
    cold_open_text: str | None = PydanticField(default=None, description="Pre-selected cold open text to inject into script generation")
    gameplay_enabled: bool = PydanticField(default=False, description="Enable gameplay video clips for some scenes")
    stock_photo_enabled: bool = PydanticField(default=False, description="Enable stock photos for some scenes")

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
    hook_score_overall: int | None = None
