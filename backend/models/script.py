"""Script data models — matches PRD section 7.2 JSON structure."""

import uuid
from datetime import datetime, timezone
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field as PydanticField, field_validator, model_validator
from sqlmodel import Column, Field, SQLModel, Text

from pipeline.flipflop_actions import FlipflopAction, normalize_flipflop_action
from pipeline.renderer_context import RendererContext, normalize_renderer_context

# --- Pydantic models for the script JSON structure ---

ALLOWED_TRANSITIONS = {"cut", "fade_black", "flash_white", "wipe"}
VISUAL_MODES = {"video", "full_frame", "multi_frame", "continuous", "captions", "popup_sequence", "flipflop", "comparison_board", "stat_card"}
VISUAL_TREATMENTS = {"full_frame", "popup_sequence", "flipflop", "comparison_board", "stat_card"}
VISUAL_LAYER_TYPES = {"image"}
VISUAL_ASSET_KINDS = {"full_frame", "panel", "cutout"}
VISUAL_LAYER_ANIMATIONS = {"none", "pop_in"}
SUBTITLE_STYLES = {"auto", "clean", "kinetic", "burst", "none"}
VisualMode = Literal["video", "full_frame", "multi_frame", "continuous", "captions", "popup_sequence", "flipflop", "comparison_board", "stat_card"]
VisualTreatment = Literal["full_frame", "popup_sequence", "flipflop", "comparison_board", "stat_card"]
FlipflopActionValue = FlipflopAction
RendererContextValue = RendererContext
VisualLayerType = Literal["image"]
VisualAssetKind = Literal["full_frame", "panel", "cutout"]
VisualLayerAnimation = Literal["none", "pop_in"]
SubtitleStyle = Literal["auto", "clean", "kinetic", "burst", "none"]

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


class VisualCanvas(BaseModel):
    """Video-level static canvas rendered beneath every scene."""

    background_color: str = "#F6C54A"

    @field_validator("background_color", mode="before")
    @classmethod
    def normalize_background_color(_cls, value: object) -> str:
        if not isinstance(value, str):
            return "#F6C54A"
        text = value.strip().upper()
        if not text.startswith("#"):
            text = f"#{text}"
        if len(text) == 7 and all(ch in "0123456789ABCDEF" for ch in text[1:]):
            return text
        return "#F6C54A"


class VisualLayer(BaseModel):
    """A renderer-facing layer used by layered animation types."""

    id: str
    type: VisualLayerType = "image"
    asset_kind: VisualAssetKind = "panel"
    image_url: str = ""
    prompt: str = ""
    label: str = ""
    placement: str = "center"
    enter_at_seconds: float = 0.0
    exit_at_seconds: float | None = None
    animation: VisualLayerAnimation = "none"
    visual_source_metadata: dict | None = None

    @field_validator("type", mode="before")
    @classmethod
    def normalize_type(_cls, value: object) -> str:
        return value if isinstance(value, str) and value in VISUAL_LAYER_TYPES else "image"

    @field_validator("asset_kind", mode="before")
    @classmethod
    def normalize_asset_kind(_cls, value: object) -> str:
        return value if isinstance(value, str) and value in VISUAL_ASSET_KINDS else "panel"

    @field_validator("animation", mode="before")
    @classmethod
    def normalize_animation(_cls, value: object) -> str:
        return value if isinstance(value, str) and value in VISUAL_LAYER_ANIMATIONS else "none"


class EliOverlay(BaseModel):
    """Eli character overlay configuration for a scene — single pose per scene."""
    enabled: bool = True
    corner: Literal["TL", "TR", "BL", "BR"] = "BR"
    frame_id: str = ""

class WordTimestamp(BaseModel):
    """A single word with its millisecond start/end markers from the TTS engine."""
    word: str
    start_ms: int
    end_ms: int


class PhraseTimestamp(BaseModel):
    """A phrase grouping derived from word_timestamps via gap detection."""
    start_ms: int
    end_ms: int


class FrameDirective(BaseModel):
    """Per-frame generation directive for the Visual Beat System."""
    prompt: str
    source: str = "ai_generated"       # "ai_generated"; legacy "subtitle" accepted for old frame data
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

    model_config = ConfigDict(validate_assignment=True)

    id: str
    narration: str
    tts_narration: str = ""               # legacy hidden TTS variant; no longer used for generated project voiceover
    visual_prompt: str
    duration_estimate_seconds: float = 8.0
    is_title_card: bool = False
    image_url: str = ""
    audio_url: str = ""
    audio_duration_seconds: float = 0.0
    word_timestamps: list[WordTimestamp] | None = None
    phrase_timestamps: list[PhraseTimestamp] | None = None
    title_card_zoom_target: dict | None = None  # {"x": int, "y": int, "radius": int} for zoompan
    frame_urls: list[str] = []        # web-relative paths to frame images
    fx: SceneFX | None = None          # assigned by FX generator, used by Remotion
    eli_overlay: EliOverlay | None = None  # Eli character animation keyframes
    visual_beat: str = "static"        # "static" | "continuous" | "multi_frame" | "captions" plus legacy aliases
    frame_directives: list[FrameDirective] = []
    contains_person: bool = False       # true if any frame depicts a human figure
    visual_mode: VisualMode = "full_frame"
    visual_layers: list[VisualLayer] = PydanticField(default_factory=list)
    flipflop_action: FlipflopActionValue | str = ""
    renderer_context: RendererContextValue | str = "plain"
    caption_text: str = ""
    caption_emphasis: str = ""
    stat_value: str = ""
    stat_label: str = ""
    subtitle_style: SubtitleStyle = "auto"
    # --- Scene-boundary transition ---
    transition_in: str = "cut"  # "cut" | "fade_black" | "flash_white" | "wipe"
    # --- Micro-timeline visual timing overrides ---
    frame_timings: list[float] | None = None  # seconds into scene when each frame starts; None = even split
    visual_in_seconds: float = 0.0      # visual appears this many seconds into the audio
    visual_out_seconds: float = 0.0     # visual ends this many seconds before audio ends
    # --- AI video ---
    video_url: str = ""                 # web-relative path to AI-generated video clip
    original_visual_prompt: str = ""    # deprecated
    visual_source_metadata: dict | None = None  # provider/source details for generated or fallback visuals

    def __setattr__(self, name: str, value: object) -> None:
        super().__setattr__(name, value)
        if name in {"visual_mode", "visual_beat"}:
            self._sync_visual_mode_fields_from_assignment(name)
        if name == "flipflop_action" and self.visual_mode != "flipflop":
            super().__setattr__("flipflop_action", "")

    @model_validator(mode="before")
    @classmethod
    def normalize_visual_mode_fields(_cls, data: object) -> object:
        if not isinstance(data, dict):
            return data
        normalized = dict(data)
        mode = _resolve_visual_mode(
            normalized.get("visual_mode"),
            normalized.get("media_source"),
            normalized.get("visual_treatment"),
            normalized.get("visual_beat"),
        )
        normalized["visual_mode"] = mode
        normalized["flipflop_action"] = (
            normalize_flipflop_action(normalized.get("flipflop_action"))
            if mode == "flipflop"
            else ""
        )
        normalized["renderer_context"] = normalize_renderer_context(normalized.get("renderer_context"))
        visual_beat = _visual_beat_for_visual_mode(mode)
        if visual_beat is not None:
            normalized["visual_beat"] = visual_beat
        if mode in {"video", "popup_sequence", "flipflop", "comparison_board", "stat_card"}:
            normalized["frame_urls"] = []
        if mode != "stat_card":
            normalized["stat_value"] = ""
            normalized["stat_label"] = ""
        if mode == "stat_card":
            normalized["caption_text"] = ""
            normalized["caption_emphasis"] = ""
            normalized["image_url"] = ""
            normalized["video_url"] = ""
        return normalized

    @field_validator("transition_in", mode="before")
    @classmethod
    def normalize_transition_in(_cls, value: object) -> str:
        """Treat missing, null, or unknown transitions as the default cut."""
        if isinstance(value, str) and value in ALLOWED_TRANSITIONS:
            return value
        return "cut"

    @field_validator("visual_mode", mode="before")
    @classmethod
    def normalize_visual_mode(_cls, value: object) -> str:
        if isinstance(value, str) and value in VISUAL_MODES:
            return value
        return "full_frame"

    @field_validator("flipflop_action", mode="before")
    @classmethod
    def normalize_flipflop_action_value(_cls, value: object) -> str:
        return normalize_flipflop_action(value)

    @field_validator("renderer_context", mode="before")
    @classmethod
    def normalize_renderer_context_value(_cls, value: object) -> str:
        return normalize_renderer_context(value)

    @field_validator("subtitle_style", mode="before")
    @classmethod
    def normalize_subtitle_style(_cls, value: object) -> str:
        if isinstance(value, str) and value in SUBTITLE_STYLES:
            return value
        return "auto"

    def set_visual_mode(self, visual_mode: str) -> None:
        mode = _resolve_visual_mode(visual_mode, None, None)
        self._sync_visual_mode_fields(mode)

    @property
    def media_source(self) -> str:
        return "ai_video" if self.visual_mode == "video" else "ai"

    @property
    def visual_treatment(self) -> VisualTreatment:
        return self.visual_mode if self.visual_mode in {"popup_sequence", "flipflop", "comparison_board", "stat_card"} else "full_frame"

    def _sync_visual_mode_fields_from_assignment(self, assigned_field: str) -> None:
        if assigned_field == "visual_mode":
            mode = _resolve_visual_mode(self.visual_mode, None, None)
        else:
            if self.visual_mode in {"video", "popup_sequence", "flipflop", "comparison_board", "stat_card"}:
                mode = self.visual_mode
            else:
                mode = _resolve_visual_mode(None, None, None, self.visual_beat)
        self._sync_visual_mode_fields(mode)

    def _sync_visual_mode_fields(self, visual_mode: VisualMode) -> None:
        super().__setattr__("visual_mode", visual_mode)
        visual_beat = _visual_beat_for_visual_mode(visual_mode)
        if visual_beat is not None:
            super().__setattr__("visual_beat", visual_beat)
        if visual_mode in {"video", "popup_sequence", "flipflop", "comparison_board", "stat_card"}:
            super().__setattr__("frame_urls", [])
        if visual_mode != "flipflop":
            super().__setattr__("flipflop_action", "")
        if visual_mode != "stat_card":
            super().__setattr__("stat_value", "")
            super().__setattr__("stat_label", "")
        if visual_mode == "stat_card":
            super().__setattr__("caption_text", "")
            super().__setattr__("caption_emphasis", "")
            super().__setattr__("image_url", "")
            super().__setattr__("video_url", "")


def _resolve_visual_mode(
    visual_mode: object,
    media_source: object,
    visual_treatment: object,
    visual_beat: object = None,
) -> VisualMode:
    if isinstance(visual_mode, str) and visual_mode in VISUAL_MODES:
        return visual_mode  # type: ignore[return-value]
    if media_source == "ai_video":
        return "video"
    if isinstance(visual_treatment, str) and visual_treatment in VISUAL_TREATMENTS:
        return visual_treatment  # type: ignore[return-value]
    if visual_beat in {"quick_cuts", "montage", "multi_frame"}:
        return "multi_frame"
    if visual_beat == "continuous":
        return "continuous"
    if visual_beat in {"aha_subtitle", "captions"}:
        return "captions"
    return "full_frame"


def _visual_beat_for_visual_mode(visual_mode: VisualMode) -> str | None:
    if visual_mode == "full_frame":
        return "static"
    if visual_mode in {
        "multi_frame",
        "continuous",
        "captions",
        "popup_sequence",
        "flipflop",
        "comparison_board",
        "stat_card",
    }:
        return visual_mode
    return None

class LevelMeta(BaseModel):
    """Per-level metadata used only by the cinematic-chapters strategy."""
    number: int
    descriptor: str
    image_prompt: str = ""  # Empty for level 1 — covered by cinematic_thumbnail_prompt instead.

class Segment(BaseModel):
    """A named segment (e.g. "Caffeine") containing multiple scenes."""

    name: str
    short_name: str = ""                # 3-word-max label for thumbnail/title card display
    scenes: list[Scene]
    circle_color: str = ""              # hex color for composite title card circle background
    title_card_image_prompt: str = ""   # visual prompt for AI-generated circle image

class MainCharacter(BaseModel):
    name: str
    appearance: str
    vibe: str = ""


class ScriptRatingCriterion(BaseModel):
    """A single 1-10 script rating criterion."""

    score: int = PydanticField(ge=1, le=10)
    note: str = ""


class ScriptRatingCategory(BaseModel):
    """A weighted script-rating category with criterion-level scores."""

    average: float
    explanation: str
    criteria: dict[str, ScriptRatingCriterion]


class ScriptRating(BaseModel):
    """Full-script quality scorecard generated after script creation."""

    viewer_retention: ScriptRatingCategory
    narrative_quality: ScriptRatingCategory
    script_craft: ScriptRatingCategory
    audience_fit: ScriptRatingCategory
    seo_alignment: ScriptRatingCategory
    overall: float
    model: str = ""
    version: str = "2026-05-25"


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
    visual_canvas: VisualCanvas = PydanticField(default_factory=VisualCanvas)
    eli_position: dict | None = None      # Per-video Eli overlay position override {x, y}
    main_character: MainCharacter | None = None  # Per-project main character (name, appearance, vibe)
    segment_timer_enabled: bool = True    # Global toggle for segment countdown timer overlay
    subtitle_highlight_enabled: bool = True  # Global toggle for active word highlight in subtitles
    seo_metadata: dict | None = None      # Generated SEO metadata (title, description, tags)
    short_form_seo_metadata: dict | None = None  # Generated per-short metadata for Shorts/TikTok/Reels
    hook_score: dict | None = None        # 30-second hook retention score (HookScore dict)
    script_rating: ScriptRating | None = None  # Full-script 1-10 quality scorecard
    hook_scene_count: int | None = None  # Number of leading scenes in segment 0 that are hook teasers; skipped from short #1
    # --- Media source routing ---
    ai_video_enabled: bool = False
    # --- Format awareness ---
    format_id: str = "youtube-listicle"
    cinematic_thumbnail_prompt: str | None = None
    levels: list[LevelMeta] | None = None

    def all_scenes(self) -> list["Scene"]:
        """Flatten all scenes from all segments in order."""
        return [scene for seg in self.segments for scene in seg.scenes]

# --- SQLModel table for persistence ---

class Script(SQLModel, table=True):
    """Persisted script stored in SQLite."""

    __tablename__ = "scripts"

    id: str = Field(default_factory=lambda: uuid.uuid4().hex, primary_key=True)
    brand_id: str = Field(index=True)
    format_id: str = Field(default="youtube-listicle", index=True)
    is_test_lab: bool = Field(default=False, index=True)
    topic_title: str = Field(default="")
    topic_description: str = Field(default="", sa_column=Column(Text))
    script_json: str = Field(default="{}", sa_column=Column(Text))  # serialised ScriptContent
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

# --- Request / response schemas ---

class GenerateScriptRequest(BaseModel):
    topic: str = PydanticField(..., min_length=1, description="Video topic / title")
    description: str = PydanticField(default="", description="Optional topic description or angle")
    creator_guidance: str | None = PydanticField(
        default=None,
        max_length=2000,
        description="Optional creator constraints from idea generation to preserve through script generation",
    )
    format_id: str = PydanticField(..., description="Video format ID (e.g. 'youtube-listicle' | 'life-as-a')")
    brand_id: str | None = PydanticField(default=None, description="Brand profile ID (auto-resolved if omitted)")
    animated_scene_count: int = PydanticField(
        default=5, ge=0, le=50, description="Number of scenes to make animated A/B flip (0 = none)"
    )
    model: str | None = PydanticField(default=None, description="Override SCRIPT_MODEL setting for this request")
    segmented: bool = PydanticField(default=False, description="Use two-phase segmented generation (one API call per segment)")
    cold_open_text: str | None = PydanticField(default=None, description="Pre-selected cold open text to inject into script generation")
    eli_enabled: bool | None = PydanticField(
        default=None,
        description="Whether Eli is enabled for this project. None falls back to ELI_ENABLED_DEFAULT app setting.",
    )
    style_preset_enabled: bool | None = PydanticField(
        default=None,
        description="Whether the global style preset is enabled for this project. None falls back to STYLE_PRESET_ENABLED_DEFAULT app setting.",
    )

class GenerateScriptResponse(BaseModel):
    id: str
    script: ScriptContent

class UpdateScriptRequest(BaseModel):
    script: ScriptContent

class UpdateScriptTitleRequest(BaseModel):
    title: str = PydanticField(..., min_length=1, max_length=200, description="Video/project title")

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


class UploadTracking(BaseModel):
    """Per-project upload status across platforms."""
    longform_youtube: bool = False
    shortform_youtube: bool = False
    shortform_instagram: bool = False
    shortform_tiktok: bool = False


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
    format_id: str
    status: str  # "script" | "images" | "audio" | "exported"
    hook_score_overall: int | None = None
    script_rating_overall: float | None = None
    upload_tracking: UploadTracking = PydanticField(default_factory=UploadTracking)
