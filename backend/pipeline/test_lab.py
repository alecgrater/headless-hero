"""Helpers for Test Lab presets and persisted run history."""

from __future__ import annotations

import json
import logging
import re
import shutil
import uuid
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, Field, field_validator, model_validator
from sqlmodel import Session, select

from config import DATA_DIR, FPS
from models.project_config import ProjectConfig
from models.script import (
    FrameDirective,
    MainCharacter,
    SUBTITLE_STYLES,
    Scene,
    Script,
    ScriptContent,
    Segment,
    VisualCanvas,
    VisualLayer,
)
from pipeline.blink_actions import BlinkAction, normalize_blink_action
from pipeline import full_frame_blink as full_frame_blink_mod
from pipeline.script_helpers import _usage_task_label
from pipeline.visual_treatments import comparison_cutout_prompt
from pipeline.renderer_context import infer_renderer_context, normalize_renderer_context

logger = logging.getLogger(__name__)

MAX_HISTORY = 20
TEST_LAB_DIRNAME = "test-lab"
__test__ = False
SAFE_RUN_ID_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_-]{0,127}$")
POPUP_SEQUENCE_TEXT_DEFAULTS = {
    "narration": (
        "Your brain treats every notification like a tiny mystery box: one might be a message, "
        "one might be a reward, and one might be nothing at all."
    ),
    "visual_prompt": (
        "[REACTION] Flat 2D cartoon person sitting at a desk at night, staring at a glowing smartphone "
        "while three floating notification bubbles hover around them like tempting mystery boxes, a chat "
        "bubble, a gift icon, and an empty gray bubble implied without readable text, calendar papers and "
        "unfinished work fading into the background, clean bold composition, expressive face, no words "
        "or letters."
    ),
}
BLINK_TEXT_DEFAULTS = {
    "narration": (
        "He tried to explain the rule calmly, but the longer he talked, the harder it became "
        "to hide how tired he was"
    ),
    "visual_prompt": (
        "Flat 2D cartoon person standing behind a small podium in a plain community room, holding an "
        "open book in one hand and gesturing with the other while speaking to people off-camera. The "
        "character looks tired but focused, with simple overhead lighting, a few chairs in the background, "
        "strong clear silhouette, bold outlines, expressive face, clean 2D cartoon aesthetic, no readable "
        "text or letters."
    ),
}

TEST_LAB_RENDERER_BLINK_ACTIONS: set[BlinkAction] = {
    "blink",
}
COMPARISON_BOARD_TEXT_DEFAULTS = {
    "narration": (
        "Before the promotion, every choice was about surviving the week; after it, every choice became "
        "about protecting what he had earned."
    ),
    "visual_prompt": (
        "[CONTRAST] Flat 2D cartoon comparison of the same person before and after a life-changing "
        "promotion, one version exhausted with worn clothes and empty pockets, the other version confident "
        "with a tidy uniform and keys in hand, clean bold silhouettes, no readable words or letters."
    ),
}
MULTI_FRAME_TEXT_DEFAULTS = {
    "narration": (
        "First the warning signs were tiny, then they were everywhere, and by the end nobody could pretend "
        "they had not seen them."
    ),
    "visual_prompt": (
        "[CONTRAST] Flat 2D cartoon sequence of escalating warning signs in a city, starting with a small "
        "cracked sidewalk, then a crowded notice board, then a wide street scene where everyone is reacting, "
        "bold outlines, clean staged compositions, no readable words or letters."
    ),
}
CONTINUOUS_TEXT_DEFAULTS = {
    "narration": (
        "The tiny crack spreads across the wall until the whole room feels like it is holding its breath."
    ),
    "visual_prompt": (
        "[CLOSE-UP] Flat 2D cartoon wall with a tiny crack slowly spreading outward through the same room, "
        "consistent camera angle, bold outline, simple dramatic lighting, no readable words or letters."
    ),
}
CAPTIONS_TEXT_DEFAULTS = {
    "narration": "Spending big in one area can hide how far behind you are in another.",
    "visual_prompt": (
        "[REACTION] Flat 2D cartoon person sitting beside a kitchen table with a receipt, "
        "a small luxury purchase on one side and overdue bills on the other, expressive worried face, "
        "bold clean composition, no readable words or letters."
    ),
    "caption_text": "Spending big while falling behind",
    "caption_emphasis": "falling behind",
}
STAT_CARD_NO_ICON_DEFAULTS = {
    "narration": "Roughly eighty-five percent of new users churn before the end of week one.",
    "visual_prompt": "",
    "stat_value": "85%",
    "stat_label": "of new users churn in week 1",
}
STAT_CARD_WITH_ICON_DEFAULTS = {
    "narration": "Online fraud quietly drains close to two million dollars from victims every single hour.",
    "visual_prompt": "Flat 2D cartoon padlock icon with a small alert symbol, bold outline, clean silhouette.",
    "stat_value": "$2M",
    "stat_label": "lost to fraud every hour",
}
VISUAL_TREATMENT_TEXT_DEFAULTS = {
    "multi_frame": MULTI_FRAME_TEXT_DEFAULTS,
    "continuous": CONTINUOUS_TEXT_DEFAULTS,
    "popup_sequence": POPUP_SEQUENCE_TEXT_DEFAULTS,
    "blink": BLINK_TEXT_DEFAULTS,
    "comparison_board": COMPARISON_BOARD_TEXT_DEFAULTS,
    "captions": CAPTIONS_TEXT_DEFAULTS,
    "stat_card": STAT_CARD_NO_ICON_DEFAULTS,
}


def utc_now_iso() -> str:
    """Return a UTC ISO timestamp suitable for stable manifest ordering."""
    return datetime.now(timezone.utc).isoformat()


class TestLabPreset(BaseModel):
    id: str
    title: str
    description: str
    format_id: str = "youtube-listicle"
    segment_name: str
    narration: str
    visual_prompt: str
    background_color: str = "#F6C54A"
    visual_mode: Literal[
        "video", "full_frame", "multi_frame", "continuous", "popup_sequence", "blink", "comparison_board", "captions", "stat_card"
    ] = "full_frame"
    caption_text: str = ""
    caption_emphasis: str = ""
    stat_value: str = ""
    stat_label: str = ""
    blink_action: str = "blink"
    renderer_context: str = "outdoor"
    duration_estimate_seconds: float = 7.0
    main_character: MainCharacter | None = None

    @property
    def media_source(self) -> str:
        return "ai_video" if self.visual_mode == "video" else "ai"


class TestLabAsset(BaseModel):
    kind: str
    path: str = ""
    url: str = ""
    label: str = ""
    created_at: str = Field(default_factory=utc_now_iso)

    @model_validator(mode="after")
    def sync_path_and_url(self) -> "TestLabAsset":
        if not self.url and self.path:
            self.url = self.path
        if not self.path and self.url:
            self.path = self.url
        return self


class TestLabLogEntry(BaseModel):
    level: Literal["debug", "info", "warning", "error"] = "info"
    stage: str = ""
    status: str = ""
    message: str
    created_at: str = Field(default_factory=utc_now_iso)


class TestLabRunManifest(BaseModel):
    run_id: str = Field(default_factory=lambda: uuid.uuid4().hex)
    script_id: str
    preset_id: str
    status: Literal["queued", "running", "completed", "failed", "cancelled"] = "queued"
    settings: dict = Field(default_factory=dict)
    assets: list[TestLabAsset] = Field(default_factory=list)
    logs: list[TestLabLogEntry] = Field(default_factory=list)
    render_url: str = ""
    total_cost: float = 0.0
    cost_breakdown: dict = Field(default_factory=dict)
    created_at: str = Field(default_factory=utc_now_iso)
    updated_at: str = Field(default_factory=utc_now_iso)

    @field_validator("run_id")
    @classmethod
    def validate_run_id(_cls, value: str) -> str:
        return validate_run_id(value)


@dataclass
class TestLabRunContext:
    engine: object
    run_id: str
    script_id: str
    preset_id: str
    settings: dict
    manifest: TestLabRunManifest
    job_id: str | None = None
    progress_start: float = 0.0
    progress_end: float = 1.0


TEST_LAB_PRESETS: list[TestLabPreset] = [
    TestLabPreset(
        id="blank",
        title="Blank",
        description="Write your own test script",
        segment_name="Custom scene",
        narration="",
        visual_prompt="",
        background_color="#111111",
    ),
    TestLabPreset(
        id="life-scribe",
        title="Your Life as a Medieval Scribe",
        description="A compact life-as-a beat for character and thumbnail experiments.",
        format_id="life-as-a",
        segment_name="The ink-stained morning",
        narration="Your day begins before sunrise, copying laws by candlelight while the city wakes outside the stone walls.",
        visual_prompt="Flat 2D cartoon of a young medieval scribe seated close to camera at a wooden desk, candle glow, parchment stacks, monastery window, expressive readable face.",
        background_color="#F6C54A",
        main_character=MainCharacter(
            name="Rowan",
            appearance="A tired young scribe with dark curly hair, ink-stained fingers, and a simple brown tunic.",
            vibe="Curious, focused, quietly overwhelmed.",
        ),
    ),
    TestLabPreset(
        id="coffee-brain",
        title="What Coffee Does to Your Brain",
        description="Science explainer scene with bold props and a clear central metaphor.",
        segment_name="The caffeine switch",
        narration="Caffeine does not create energy. It blocks the sleepy signal long enough for your brain to feel like the lights just came back on.",
        visual_prompt="Flat 2D cartoon brain control room with a giant coffee mug flipping a bright switch, sleepy icons pushed aside, clean educational composition.",
        background_color="#38BDF8",
    ),
    TestLabPreset(
        id="mars-minutes",
        title="Five Minutes on Mars",
        description="Space survival beat for testing hostile environments.",
        segment_name="The first breath",
        narration="On Mars, the danger is immediate: thin air, freezing dust, and a sky that looks calm while your suit does all the work.",
        visual_prompt="Flat 2D cartoon astronaut standing large in foreground on red Martian dust, frosty suit visor, tiny habitat in distance, pale orange sky.",
        background_color="#F97316",
        visual_mode="video",
    ),
    TestLabPreset(
        id="sleep-debt",
        title="Why Sleep Debt Feels Heavy",
        description="Health explainer with a strong visual analogy.",
        segment_name="The invisible backpack",
        narration="Missing sleep is like adding books to a backpack you cannot take off. Each hour makes simple decisions feel strangely heavier.",
        visual_prompt="Flat 2D cartoon person carrying an oversized transparent backpack filled with glowing clocks and books, morning bedroom, tired expression.",
        background_color="#8B5CF6",
    ),
    TestLabPreset(
        id="airplane-boarding",
        title="Why Airplane Boarding Is So Slow",
        description="Everyday logistics scene for crowd and motion tests.",
        segment_name="The aisle bottleneck",
        narration="Boarding slows down because one narrow aisle has to handle bags, seats, confusion, and everyone trying to move at once.",
        visual_prompt="Flat 2D cartoon airplane aisle viewed from front, passengers frozen in a funny bottleneck with bags overhead, clear depth and readable faces.",
        background_color="#10B981",
    ),
    TestLabPreset(
        id="ancient-library",
        title="Inside an Ancient Library",
        description="History scene with warm interiors and artifact detail.",
        segment_name="The room of scrolls",
        narration="An ancient library was not quiet by accident. It was a guarded machine for protecting knowledge from fire, theft, and time.",
        visual_prompt="Flat 2D cartoon ancient library with tall shelves of scrolls, bronze lamps, guarded doorway, scholar in foreground holding a tablet.",
        background_color="#EAB308",
    ),
    TestLabPreset(
        id="ocean-pressure",
        title="Ocean Pressure Explained",
        description="Physics explainer with a simple depth comparison.",
        segment_name="The crushing column",
        narration="Deep underwater, pressure is the weight of the ocean stacked above you, pressing from every direction at the same time.",
        visual_prompt="Flat 2D cartoon deep sea diver beside a vertical column of water pressure blocks, small submarine lights, dark blue ocean, friendly educational style.",
        background_color="#0EA5E9",
    ),
    TestLabPreset(
        id="money-inflation",
        title="Inflation in One Grocery Trip",
        description="Finance explainer with clear price-tag storytelling.",
        segment_name="The shrinking cart",
        narration="Inflation is easiest to feel at the grocery store, when the same cart, the same list, and the same paycheck stop lining up.",
        visual_prompt="Flat 2D cartoon grocery cart with familiar items and oversized changing price tags, shopper comparing receipt, bright aisle background.",
        background_color="#22C55E",
    ),
    TestLabPreset(
        id="castle-siege",
        title="How a Castle Siege Worked",
        description="Historical action scene for testing structured chaos.",
        segment_name="The waiting game",
        narration="A siege was less like one dramatic attack and more like a long contest of food, fear, engineering, and patience.",
        visual_prompt="Flat 2D cartoon castle under siege with defenders on walls, tents outside, supply barrels in foreground, dramatic but readable composition.",
        background_color="#EF4444",
        visual_mode="video",
    ),
    TestLabPreset(
        id="phone-addiction",
        title="Why Phones Steal Attention",
        description="Behavior explainer with a modern, high-contrast setup.",
        segment_name="The tiny reward loop",
        narration="Your phone keeps attention by offering tiny uncertain rewards, just often enough to make checking it feel automatic.",
        visual_prompt="Flat 2D cartoon person at desk pulled by glowing notification bubbles from a smartphone, calendar and work notes fading behind them.",
        background_color="#A855F7",
    ),
    TestLabPreset(
        id="caption-punch",
        title="Captions Punch Test",
        description="Editorial in-scene caption beat with red emphasis and optional side visual.",
        segment_name="The point",
        narration=CAPTIONS_TEXT_DEFAULTS["narration"],
        visual_prompt=CAPTIONS_TEXT_DEFAULTS["visual_prompt"],
        caption_text=CAPTIONS_TEXT_DEFAULTS["caption_text"],
        caption_emphasis=CAPTIONS_TEXT_DEFAULTS["caption_emphasis"],
        visual_mode="captions",
        background_color="#F6C54A",
    ),
    TestLabPreset(
        id="stat-card-no-icon",
        title="Stat Card — Text Only",
        description="Single dominant statistic rendered over the canvas with no supporting icon.",
        segment_name="The number",
        narration=STAT_CARD_NO_ICON_DEFAULTS["narration"],
        visual_prompt=STAT_CARD_NO_ICON_DEFAULTS["visual_prompt"],
        stat_value=STAT_CARD_NO_ICON_DEFAULTS["stat_value"],
        stat_label=STAT_CARD_NO_ICON_DEFAULTS["stat_label"],
        visual_mode="stat_card",
        background_color="#F6C54A",
    ),
    TestLabPreset(
        id="stat-card-with-icon",
        title="Stat Card — With Icon",
        description="Single dominant statistic with one transparent supporting icon cutout.",
        segment_name="The number",
        narration=STAT_CARD_WITH_ICON_DEFAULTS["narration"],
        visual_prompt=STAT_CARD_WITH_ICON_DEFAULTS["visual_prompt"],
        stat_value=STAT_CARD_WITH_ICON_DEFAULTS["stat_value"],
        stat_label=STAT_CARD_WITH_ICON_DEFAULTS["stat_label"],
        visual_mode="stat_card",
        background_color="#0F172A",
    ),
]


def test_lab_root() -> Path:
    return DATA_DIR / TEST_LAB_DIRNAME


def runs_dir() -> Path:
    return test_lab_root() / "runs"


def validate_run_id(run_id: str) -> str:
    if not isinstance(run_id, str) or not SAFE_RUN_ID_RE.fullmatch(run_id):
        raise ValueError("run_id must be a non-empty safe identifier using letters, numbers, underscores, or hyphens")
    return run_id


def _path_under(child: Path, parent: Path) -> bool:
    try:
        child.resolve().relative_to(parent.resolve())
    except ValueError:
        return False
    return True


def get_preset(preset_id: str) -> TestLabPreset:
    for preset in TEST_LAB_PRESETS:
        if preset.id == preset_id:
            return preset
    raise ValueError(f"Unknown Test Lab preset: {preset_id}")


def _deep_merge(base: dict, override: dict) -> dict:
    merged = dict(base)
    for key, value in override.items():
        if isinstance(value, dict) and isinstance(merged.get(key), dict):
            merged[key] = _deep_merge(merged[key], value)
        else:
            merged[key] = value
    return merged


def _setting(settings: dict, key: str, fallback):
    value = settings.get(key)
    return fallback if value is None else value


def _bool_setting(settings: dict, key: str, fallback: bool) -> bool:
    value = _setting(settings, key, fallback)
    if isinstance(value, str):
        normalized = value.strip().lower()
        if normalized in {"false", "0", "no", "off"}:
            return False
        if normalized in {"true", "1", "yes", "on"}:
            return True
    return bool(value)


def _main_character_from_settings(settings: dict, preset: TestLabPreset) -> MainCharacter | None:
    raw = settings.get("main_character")
    if isinstance(raw, MainCharacter):
        return raw.model_copy(deep=True)
    if isinstance(raw, dict):
        return MainCharacter.model_validate(raw)
    _ = preset
    return None


def _active_style_preset_main_character(session: Session) -> MainCharacter | None:
    from pipeline.main_character import get_active_style_preset_character, read_active_style_preset_id

    preset_id = read_active_style_preset_id(session)
    if not preset_id:
        return None
    character = get_active_style_preset_character(session, preset_id)
    if character is None:
        return None
    return MainCharacter(name=character.name, appearance=character.appearance, vibe=character.vibe)


def _visual_canvas_background_from_settings(settings: dict, preset: TestLabPreset) -> str:
    raw_canvas = settings.get("visual_canvas")
    if isinstance(raw_canvas, dict) and "background_color" in raw_canvas:
        return raw_canvas["background_color"]
    return _setting(settings, "background_color", preset.background_color)


def _scene_text_from_settings(settings: dict, preset: TestLabPreset, visual_mode: str, key: str) -> str:
    preset_value = getattr(preset, key)
    raw_value = settings.get(key)
    if isinstance(raw_value, str) and raw_value and raw_value != preset_value:
        return raw_value
    return _setting(settings, key, preset_value)


def _caption_setting_from_settings(settings: dict, preset: TestLabPreset, key: str, narration: str, visual_mode: str) -> str:
    raw_value = settings.get(key)
    preset_value = getattr(preset, key)
    derived_caption_text = _caption_text_from_narration(narration)
    narration_is_custom = narration not in {preset.narration, CAPTIONS_TEXT_DEFAULTS["narration"]}
    if not isinstance(raw_value, str):
        if visual_mode == "captions":
            return derived_caption_text if key == "caption_text" else _caption_emphasis_from_text(derived_caption_text)
        return _setting(settings, key, preset_value)
    if raw_value == "":
        return ""
    if visual_mode != "captions":
        return raw_value

    default_value = CAPTIONS_TEXT_DEFAULTS.get(key, "")
    raw_caption_text = settings.get("caption_text")
    resolved_caption_text = (
        raw_caption_text
        if isinstance(raw_caption_text, str) and _caption_text_matches(raw_caption_text, derived_caption_text)
        else derived_caption_text
    )
    if narration_is_custom and raw_value in {preset_value, default_value}:
        return derived_caption_text if key == "caption_text" else _caption_emphasis_from_text(derived_caption_text)
    if key == "caption_text" and not _caption_text_matches(raw_value, derived_caption_text):
        return derived_caption_text
    if key == "caption_emphasis" and not _caption_text_matches(raw_value, resolved_caption_text):
        return _caption_emphasis_from_text(resolved_caption_text)
    return raw_value


def _caption_text_from_narration(narration: str) -> str:
    return re.sub(r"\s+", " ", narration.strip(" ."))


def _caption_text_matches(value: str, text: str) -> bool:
    normalized_value = re.sub(r"\s+", " ", value.strip(" .")).casefold()
    normalized_text = re.sub(r"\s+", " ", text.strip(" .")).casefold()
    return bool(normalized_value) and normalized_value in normalized_text


def _caption_emphasis_from_text(caption_text: str) -> str:
    words = [
        re.sub(r"[^a-z0-9]+", "", word.casefold())
        for word in caption_text.split()
    ]
    content_words = [word for word in words if word and word not in {"a", "an", "and", "are", "is", "it", "of", "or", "that", "the", "to"}]
    return content_words[-1] if content_words else ""


def _stat_setting_from_settings(settings: dict, preset: TestLabPreset, key: str, visual_mode: str) -> str:
    raw_value = settings.get(key)
    preset_value = getattr(preset, key, "") or ""
    if not isinstance(raw_value, str):
        return preset_value if visual_mode == "stat_card" else ""
    if visual_mode != "stat_card":
        return ""
    return raw_value


def _visual_mode_from_settings(settings: dict, preset: TestLabPreset) -> str:
    if isinstance(settings.get("visual_mode"), str):
        return settings["visual_mode"]
    if settings.get("media_source") == "ai_video":
        return "video"
    if isinstance(settings.get("visual_treatment"), str):
        return settings["visual_treatment"]
    return preset.visual_mode


def _blink_action_from_settings(settings: dict, preset: TestLabPreset | None) -> str:
    action = (
        normalize_blink_action(settings.get("blink_action"))
        or (normalize_blink_action(preset.blink_action) if preset is not None else "")
        or "blink"
    )
    return action if action in TEST_LAB_RENDERER_BLINK_ACTIONS else "blink"


def _resolve_blink_action_for_settings(
    settings: dict, preset: TestLabPreset | None
) -> str:
    visual_mode = (
        _visual_mode_from_settings(settings, preset)
        if preset is not None
        else (settings.get("visual_mode") or settings.get("visual_treatment") or "")
    )
    if visual_mode != "blink":
        return ""
    return _blink_action_from_settings(settings, preset)


def _renderer_context_from_settings(settings: dict, preset: TestLabPreset | None) -> str:
    if "renderer_context" in settings:
        return normalize_renderer_context(settings.get("renderer_context"))
    if preset is not None:
        return normalize_renderer_context(preset.renderer_context)
    return "outdoor"


def _subtitle_style_from_settings(settings: dict) -> str:
    value = settings.get("subtitle_style")
    return value if isinstance(value, str) and value in SUBTITLE_STYLES else "auto"


def _sync_ai_video_enabled(content: ScriptContent) -> ScriptContent:
    content.ai_video_enabled = any(
        scene.visual_mode == "video"
        for segment in content.segments
        for scene in segment.scenes
    )
    return content


def _advanced_first_scene(settings: dict) -> dict | None:
    advanced_script = settings.get("advanced_script")
    if not isinstance(advanced_script, dict):
        return None
    segments = advanced_script.get("segments")
    if not isinstance(segments, list) or not segments:
        return None
    first_segment = segments[0]
    if not isinstance(first_segment, dict):
        return None
    scenes = first_segment.get("scenes")
    if not isinstance(scenes, list) or not scenes:
        return None
    first_scene = scenes[0]
    return first_scene if isinstance(first_scene, dict) else None


def _reapply_top_level_scene_settings(content: ScriptContent, settings: dict) -> None:
    advanced_scene = _advanced_first_scene(settings)
    if advanced_scene is None:
        return
    scene = _first_scene(content)
    visual_mode = settings.get("visual_mode")
    if isinstance(visual_mode, str) and "visual_mode" not in advanced_scene:
        scene.set_visual_mode(visual_mode)
    elif "visual_treatment" in settings and "visual_treatment" not in advanced_scene:
        scene.set_visual_mode(settings["visual_treatment"])
    if (
        "blink_action" in settings
        and "blink_action" not in advanced_scene
    ):
        scene.blink_action = normalize_blink_action(settings["blink_action"])
    if (
        "renderer_context" in settings
        and "renderer_context" not in advanced_scene
    ):
        scene.renderer_context = normalize_renderer_context(settings["renderer_context"])
    if (
        "visual_layers" in settings
        and "visual_layers" not in advanced_scene
        and isinstance(settings["visual_layers"], list)
    ):
        scene.visual_layers = [VisualLayer.model_validate(layer) for layer in settings["visual_layers"]]
    if (
        "frame_directives" in settings
        and "frame_directives" not in advanced_scene
        and isinstance(settings["frame_directives"], list)
    ):
        scene.frame_directives = [FrameDirective.model_validate(directive) for directive in settings["frame_directives"]]


def _normalize_ai_video_treatments(content: ScriptContent) -> None:
    for scene in content.all_scenes():
        if scene.visual_mode != "video":
            continue
        scene.set_visual_mode("video")
        scene.visual_layers = []


def build_content_from_preset(preset_id: str, settings: dict) -> ScriptContent:
    preset = get_preset(preset_id)
    visual_mode = _visual_mode_from_settings(settings, preset)
    narration = _scene_text_from_settings(settings, preset, visual_mode, "narration")
    visual_prompt = _scene_text_from_settings(settings, preset, visual_mode, "visual_prompt")
    stat_value = _stat_setting_from_settings(settings, preset, "stat_value", visual_mode)
    stat_label = _stat_setting_from_settings(settings, preset, "stat_label", visual_mode)
    blink_action = _blink_action_from_settings(settings, preset)
    renderer_context = _renderer_context_from_settings(settings, preset)
    visual_layers = settings.get("visual_layers") if isinstance(settings.get("visual_layers"), list) else []
    if visual_mode == "stat_card" and not visual_layers and visual_prompt.strip():
        visual_layers = [
            {
                "id": f"{preset.id}-stat-icon",
                "type": "image",
                "asset_kind": "cutout",
                "prompt": visual_prompt.strip(),
                "placement": "center",
                "animation": "pop_in",
            }
        ]
    scene = Scene(
        id=f"{preset.id}-scene-1",
        narration=narration,
        visual_prompt=visual_prompt,
        duration_estimate_seconds=float(
            _setting(settings, "duration_estimate_seconds", preset.duration_estimate_seconds)
        ),
        visual_mode=visual_mode,
        contains_person=bool(_setting(settings, "contains_person", preset.main_character is not None)),
        visual_layers=visual_layers,
        blink_action=blink_action if visual_mode == "blink" else "",
        renderer_context=renderer_context,
        caption_text=_caption_setting_from_settings(settings, preset, "caption_text", narration, visual_mode),
        caption_emphasis=_caption_setting_from_settings(settings, preset, "caption_emphasis", narration, visual_mode),
        stat_value=stat_value,
        stat_label=stat_label,
        subtitle_style=_subtitle_style_from_settings(settings),
    )
    if isinstance(settings.get("frame_directives"), list):
        scene.frame_directives = [FrameDirective.model_validate(directive) for directive in settings["frame_directives"]]
    content = ScriptContent(
        title=_setting(settings, "title", preset.title),
        segments=[
            Segment(
                name=_setting(settings, "segment_name", preset.segment_name),
                short_name=_setting(settings, "short_name", ""),
                scenes=[scene],
            )
        ],
        card_title=_setting(settings, "card_title", preset.title.upper()),
        card_title_highlight_word=_setting(settings, "card_title_highlight_word", ""),
        card_subtitle="",
        visual_canvas=VisualCanvas(
            background_color=_visual_canvas_background_from_settings(settings, preset),
        ),
        main_character=_main_character_from_settings(settings, preset),
        segment_timer_enabled=True,
        subtitle_highlight_enabled=True,
        ai_video_enabled=visual_mode == "video",
        format_id=_setting(settings, "format_id", preset.format_id),
    )
    advanced_script = settings.get("advanced_script")
    if isinstance(advanced_script, dict):
        content = ScriptContent.model_validate(_deep_merge(content.model_dump(), advanced_script))
        _reapply_top_level_scene_settings(content, settings)
        content.subtitle_highlight_enabled = True
    _normalize_ai_video_treatments(content)
    return _sync_ai_video_enabled(content)


def create_hidden_test_script(
    session: Session,
    *,
    run_id: str,
    preset_id: str,
    settings: dict,
) -> str:
    from database import get_default_brand_id

    safe_run_id = validate_run_id(run_id)
    script_id = f"test-lab-{safe_run_id}"
    content = build_content_from_preset(preset_id, settings)
    content.segment_timer_enabled = True
    content.subtitle_highlight_enabled = True
    brand_id = settings.get("brand_id") or get_default_brand_id(session)
    eli_enabled = _bool_setting(settings, "eli_enabled", False)
    style_preset_enabled = _bool_setting(settings, "style_preset_enabled", True)
    if not eli_enabled and style_preset_enabled and content.main_character is None:
        content.main_character = _active_style_preset_main_character(session)
    existing = session.get(Script, script_id)
    if existing is None:
        existing = Script(
            id=script_id,
            brand_id=brand_id,
            format_id=content.format_id,
            topic_title=content.title,
            topic_description=f"Test Lab run {safe_run_id}",
            script_json=content.model_dump_json(),
            is_test_lab=True,
        )
    else:
        existing.brand_id = brand_id
        existing.format_id = content.format_id
        existing.topic_title = content.title
        existing.topic_description = f"Test Lab run {safe_run_id}"
        existing.script_json = content.model_dump_json()
        existing.is_test_lab = True
    session.add(existing)

    cfg = session.get(ProjectConfig, script_id)
    if cfg is None:
        cfg = ProjectConfig(
            script_id=script_id,
            eli_enabled=eli_enabled,
            style_preset_enabled=style_preset_enabled,
        )
    else:
        cfg.eli_enabled = eli_enabled
        cfg.style_preset_enabled = style_preset_enabled
        cfg.main_character_reference_url = None
    session.add(cfg)
    return script_id


def build_cost_breakdown(session: Session, script_id: str) -> dict:
    from collections import defaultdict

    from models.api_usage import ApiUsage

    rows = session.exec(select(ApiUsage).where(ApiUsage.script_id == script_id)).all()
    raw_total_cost = sum(row.cost_estimate for row in rows)
    grouped = defaultdict(
        lambda: {
            "task": "",
            "service": "",
            "operation": "",
            "model": "",
            "call_count": 0,
            "input_tokens": 0,
            "output_tokens": 0,
            "characters": 0,
            "images": 0,
            "total_cost": 0.0,
        }
    )

    for row in rows:
        task = _usage_task_label(row.service, row.operation, row.metadata_json)
        key = (task, row.service, row.operation, row.model)
        item = grouped[key]
        item["task"] = task
        item["service"] = row.service
        item["operation"] = row.operation
        item["model"] = row.model
        item["call_count"] += 1
        item["input_tokens"] += row.input_tokens
        item["output_tokens"] += row.output_tokens
        item["characters"] += row.characters
        item["images"] += row.images
        item["total_cost"] += row.cost_estimate

    breakdown = sorted(grouped.values(), key=lambda item: item["total_cost"], reverse=True)
    for item in breakdown:
        item["total_cost"] = round(float(item["total_cost"]), 4)
    return {
        "total_cost": round(float(raw_total_cost), 4),
        "breakdown": breakdown,
    }


def log_stage(manifest: TestLabRunManifest, stage: str, status: str, message: str) -> None:
    level: Literal["debug", "info", "warning", "error"] = "info"
    if status == "failed":
        level = "error"
    elif status in {"skipped", "warning", "cancelled"}:
        level = "warning"
    manifest.logs.append(
        TestLabLogEntry(
            level=level,
            stage=stage,
            status=status,
            message=message,
        )
    )


def _enabled(settings: dict, stage: str, default: bool = True) -> bool:
    stages = settings.get("stages")
    if isinstance(stages, dict) and stage in stages:
        return _bool_setting(stages, stage, default)
    return _bool_setting(settings, stage, default)


def _load_content_for_script(session: Session, script_id: str) -> tuple[Script, ScriptContent]:
    record = session.get(Script, script_id)
    if record is None:
        raise RuntimeError(f"Test Lab script {script_id} not found")
    return record, ScriptContent.model_validate_json(record.script_json)


def _first_scene(content: ScriptContent) -> Scene:
    for scene in content.all_scenes():
        if not scene.is_title_card:
            return scene
    scenes = content.all_scenes()
    if not scenes:
        raise RuntimeError("Test Lab script has no scenes")
    return scenes[0]


def _save_content(session: Session, record: Script, content: ScriptContent) -> None:
    record.script_json = content.model_dump_json()
    session.add(record)
    session.commit()


def _check_cancelled(ctx: TestLabRunContext) -> None:
    if not ctx.job_id:
        return
    from pipeline.render_jobs import is_cancelled

    if is_cancelled(ctx.job_id):
        raise RuntimeError("Test Lab job was cancelled")


def _stage_character_reference(ctx: TestLabRunContext) -> None:
    from pipeline.main_character import missing_character_reference_reason, sync_global_main_character_to_project

    _check_cancelled(ctx)
    with Session(ctx.engine) as session:
        cfg = session.get(ProjectConfig, ctx.script_id)
        if cfg is None or cfg.eli_enabled or not cfg.style_preset_enabled:
            return
        if sync_global_main_character_to_project(session, ctx.script_id):
            session.commit()
            cfg = session.get(ProjectConfig, ctx.script_id)
        block_reason = missing_character_reference_reason(session, ctx.script_id)
        if block_reason:
            raise RuntimeError(block_reason)
        record, content = _load_content_for_script(session, ctx.script_id)
        _ = record
        if content.main_character is None:
            raise RuntimeError(
                "Global main character details are required. Set them in Settings → Style Presets → Main Character."
            )
        ctx.manifest.assets.append(
            TestLabAsset(kind="image", label="Main character reference", url=cfg.main_character_reference_url or "")
        )


def _voice_id_for_run(session: Session, _ctx: TestLabRunContext) -> str:
    from database import get_default_brand_id
    from models.brand import BrandProfile

    brand_id = get_default_brand_id(session)
    brand = session.get(BrandProfile, brand_id)
    if not brand or not brand.voice_id:
        raise RuntimeError("No voice configured - set a voice in Settings first")
    return brand.voice_id


def _stage_audio(ctx: TestLabRunContext) -> None:
    from pipeline.voiceover import generate_scene_audio, prepare_tts_text, resolve_tts_model_and_settings

    _check_cancelled(ctx)
    with Session(ctx.engine) as session:
        voice_id = _voice_id_for_run(session, ctx)
        record, content = _load_content_for_script(session, ctx.script_id)
        scene = _first_scene(content)
        model_id, voice_settings = resolve_tts_model_and_settings(None, None)
        narration = prepare_tts_text(
            scene.narration,
            model_id=model_id,
            is_title_card=scene.is_title_card,
            level_number=1 if scene.is_title_card else None,
        )
        audio_url, duration, word_timestamps, phrase_timestamps = generate_scene_audio(
            scene.id,
            narration,
            voice_id,
            ctx.script_id,
            model_id=model_id,
            voice_settings=voice_settings,
        )
        scene.audio_url = audio_url
        scene.audio_duration_seconds = duration
        scene.word_timestamps = word_timestamps
        scene.phrase_timestamps = phrase_timestamps
        _save_content(session, record, content)
        ctx.manifest.assets.append(TestLabAsset(kind="audio", label="Voiceover", url=audio_url))


def _stage_visual(ctx: TestLabRunContext) -> None:
    _check_cancelled(ctx)
    with Session(ctx.engine) as session:
        record, content = _load_content_for_script(session, ctx.script_id)
        scene = _first_scene(content)
        if scene.visual_mode in {"multi_frame", "continuous"} and not scene.frame_directives:
            scene.frame_directives = _frame_directives_for_visual_mode(scene)
        if scene.visual_mode in {"popup_sequence", "comparison_board", "stat_card"}:
            scene.image_url = ""
            scene.video_url = ""
            scene.frame_urls = []
            scene.visual_source_metadata = None
            _save_content(session, record, content)
            return

        from pipeline.image_gen import generate_scene_visual

        result = generate_scene_visual(
            {
                "scene_id": scene.id,
                "visual_prompt": scene.visual_prompt,
                "frame_directives": [directive.model_dump() for directive in scene.frame_directives],
                "contains_person": scene.contains_person,
                "visual_mode": scene.visual_mode,
                "blink_action": scene.blink_action,
                "renderer_context": scene.renderer_context,
                "audio_duration_seconds": scene.audio_duration_seconds or scene.duration_estimate_seconds,
                "visual_layers": [layer.model_dump() for layer in scene.visual_layers],
            },
            script_id=ctx.script_id,
        )
        if result.get("error"):
            raise RuntimeError(str(result["error"]))

        video_url = str(result.get("video_url") or "")
        frame_urls = [str(url or "") for url in result.get("frame_urls", [])]
        image_url = str(result.get("image_url") or "")
        source_metadata = result.get("visual_source_metadata")
        if video_url:
            scene.video_url = video_url
            scene.image_url = ""
            scene.frame_urls = []
            scene.visual_source_metadata = source_metadata if isinstance(source_metadata, dict) else None
            ctx.manifest.assets.append(TestLabAsset(kind="video", label="AI video", url=video_url))
            anchor_url = f"/static/projects/{ctx.script_id}/images/{scene.id}.png"
            ctx.manifest.assets.append(TestLabAsset(kind="image", label="Anchor image", url=anchor_url))
        elif frame_urls:
            scene.image_url = next((url for url in frame_urls if url), "")
            scene.video_url = ""
            scene.frame_urls = frame_urls
            scene.visual_source_metadata = source_metadata if isinstance(source_metadata, dict) else None
            for index, url in enumerate(frame_urls, start=1):
                if not url:
                    continue
                ctx.manifest.assets.append(TestLabAsset(kind="image", label=f"Frame {index}", url=url))
        elif image_url:
            scene.image_url = image_url
            scene.video_url = ""
            scene.frame_urls = []
            merged_metadata = source_metadata if isinstance(source_metadata, dict) else {}
            merged_metadata = dict(merged_metadata)
            merged_metadata.pop("full_frame_blink", None)
            if scene.visual_mode in full_frame_blink_mod.MEDIA_BACKED_BLINK_MODES:
                blink_meta = full_frame_blink_mod.build_full_frame_blink_metadata(
                    ctx.script_id, scene.id, image_url
                )
                if blink_meta:
                    merged_metadata["full_frame_blink"] = blink_meta
            scene.visual_source_metadata = merged_metadata or None
            ctx.manifest.assets.append(TestLabAsset(kind="image", label="Scene image", url=image_url))
        else:
            scene.image_url = ""
            scene.video_url = ""
            scene.frame_urls = []
            scene.visual_source_metadata = source_metadata if isinstance(source_metadata, dict) else None
        _save_content(session, record, content)


def _frame_directives_for_visual_mode(scene: Scene) -> list[dict]:
    base_prompt = scene.visual_prompt.strip() or scene.narration.strip()
    if scene.visual_mode == "continuous":
        return [
            {
                "prompt": f"Opening frame of the same continuous scene: {base_prompt}",
                "source": "ai_generated",
                "transition": "crossfade",
                "reference_previous": False,
                "contains_person": scene.contains_person,
            },
            {
                "prompt": f"Middle frame of the same continuous scene, same camera angle, visible progression: {base_prompt}",
                "source": "ai_generated",
                "transition": "crossfade",
                "reference_previous": True,
                "contains_person": scene.contains_person,
            },
            {
                "prompt": f"Final frame of the same continuous scene, same camera angle, completed progression: {base_prompt}",
                "source": "ai_generated",
                "transition": "crossfade",
                "reference_previous": True,
                "contains_person": scene.contains_person,
            },
        ]
    return [
        {
            "prompt": f"First full-bleed sequence image, simple clear setup: {base_prompt}",
            "source": "ai_generated",
            "transition": "cut",
            "reference_previous": False,
            "contains_person": scene.contains_person,
        },
        {
            "prompt": f"Second full-bleed sequence image, stronger escalation or contrasting example: {base_prompt}",
            "source": "ai_generated",
            "transition": "cut",
            "reference_previous": False,
            "contains_person": scene.contains_person,
        },
        {
            "prompt": f"Third full-bleed sequence image, final broad payoff composition: {base_prompt}",
            "source": "ai_generated",
            "transition": "cut",
            "reference_previous": False,
            "contains_person": scene.contains_person,
        },
    ]


def _stage_treatment_assets(ctx: TestLabRunContext) -> None:
    from pipeline.image_gen import (
        generate_comparison_board_cutouts,
        generate_popup_sequence_cutouts,
        generate_stat_card_cutout,
        generate_visual_layer_panels,
    )
    from pipeline.visual_treatments import analyze_visual_treatments, apply_visual_treatment_assignments

    _check_cancelled(ctx)
    with Session(ctx.engine) as session:
        record, content = _load_content_for_script(session, ctx.script_id)
        scene = _first_scene(content)
        if scene.visual_mode == "video":
            scene.set_visual_mode("video")
            scene.visual_layers = []
            _save_content(session, record, content)
            return
        requested_mode = ctx.settings.get("visual_mode") or ctx.settings.get("visual_treatment")
        if isinstance(requested_mode, str):
            scene.set_visual_mode(requested_mode)
        layer_based_treatment = scene.visual_mode in {"popup_sequence", "comparison_board", "stat_card"}
        explicit_treatment = "visual_mode" in ctx.settings or "visual_treatment" in ctx.settings or scene.visual_mode != "full_frame"
        if not explicit_treatment:
            assignments = analyze_visual_treatments(content, script_id=ctx.script_id)
            apply_visual_treatment_assignments(content, assignments)
            scene = _first_scene(content)
            layer_based_treatment = scene.visual_mode in {"popup_sequence", "comparison_board", "stat_card"}
        if scene.visual_mode == "full_frame":
            scene.visual_layers = []
            _save_content(session, record, content)
            return
        if not layer_based_treatment:
            _save_content(session, record, content)
            return
        requested_blink_action = (
            _resolve_blink_action_for_settings(ctx.settings, get_preset(ctx.preset_id))
            if requested_mode == "blink"
            else ""
        )
        if not scene.visual_layers:
            assignment = None
            if requested_mode == "blink" and requested_blink_action:
                scene.set_visual_mode("blink")
                scene.blink_action = requested_blink_action
                scene.contains_person = True
            elif scene.audio_duration_seconds > 0 and scene.word_timestamps:
                assignments = analyze_visual_treatments(content, script_id=ctx.script_id)
                assignment = _assignment_for_scene(assignments, scene.id)
                assignment_mode = assignment.visual_mode if assignment else ""
                if assignment and isinstance(requested_mode, str) and assignment_mode != requested_mode:
                    logger.info(
                        "[TEST_LAB] ignoring %s animation assets for explicitly selected %s scene=%s",
                        assignment_mode,
                        requested_mode,
                        scene.id,
                    )
                    assignment = None
            scene.visual_layers = (
                list(assignment.visual_layers)
                if assignment and assignment.visual_layers
                else _fallback_visual_layers_for_treatment(scene)
            )
            if isinstance(requested_mode, str):
                scene.set_visual_mode(requested_mode)
            if requested_mode == "blink" and requested_blink_action:
                scene.contains_person = True
        if scene.visual_layers:
            layer_dicts = [layer.model_dump() for layer in scene.visual_layers]
            if scene.visual_mode == "popup_sequence":
                generated_layers = generate_popup_sequence_cutouts(
                    scene_id=scene.id,
                    layers=layer_dicts,
                    script_id=ctx.script_id,
                    scene_prompt=scene.visual_prompt,
                    force=True,
                    contains_person=scene.contains_person,
                )
            elif scene.visual_mode == "comparison_board":
                generated_layers = generate_comparison_board_cutouts(
                    scene_id=scene.id,
                    layers=layer_dicts,
                    script_id=ctx.script_id,
                    scene_prompt=scene.visual_prompt,
                    force=True,
                )
            elif scene.visual_mode == "stat_card":
                generated_layers = generate_stat_card_cutout(
                    scene_id=scene.id,
                    layers=layer_dicts,
                    script_id=ctx.script_id,
                    scene_prompt=scene.visual_prompt,
                    force=True,
                )
            else:
                generated_layers = generate_visual_layer_panels(
                    scene.id,
                    layer_dicts,
                    ctx.script_id,
                    force=True,
                    contains_person=scene.contains_person,
                    visual_treatment=scene.visual_mode,
                )
            scene.visual_layers = [VisualLayer.model_validate(layer) for layer in generated_layers]
            for layer in scene.visual_layers:
                if layer.image_url:
                    ctx.manifest.assets.append(
                        TestLabAsset(kind="treatment_asset", label=f"Animation asset {layer.id}", url=layer.image_url)
                    )
        _save_content(session, record, content)


def _assignment_for_scene(assignments: list["VisualTreatmentAssignment"], scene_id: str):
    return next((assignment for assignment in assignments if assignment.scene_id == scene_id), None)


def _fallback_visual_layers_for_treatment(scene: Scene) -> list[VisualLayer]:
    base_prompt = scene.visual_prompt.strip() or scene.narration.strip()
    if scene.visual_mode == "popup_sequence":
        duration = scene.audio_duration_seconds or scene.duration_estimate_seconds
        second_enter_at = max(duration / 3, 0.5)
        third_enter_at = max((duration * 2) / 3, 1.0)
        return [
            VisualLayer(
                id=f"{scene.id}_popup_1",
                prompt=(
                    f"Popup item cutout prompt for first beat: {base_prompt}. "
                    "No decorative border, picture frame, mat, white margin, inset panel, UI chrome, caption box, or poster edge. "
                    "No text in image."
                ),
                placement="left",
                enter_at_seconds=0.0,
                animation="pop_in",
            ),
            VisualLayer(
                id=f"{scene.id}_popup_2",
                prompt=(
                    f"Popup item cutout prompt for second beat: {base_prompt}. "
                    "No decorative border, picture frame, mat, white margin, inset panel, UI chrome, caption box, or poster edge. "
                    "No text in image."
                ),
                placement="center",
                enter_at_seconds=second_enter_at,
                animation="pop_in",
            ),
            VisualLayer(
                id=f"{scene.id}_popup_3",
                prompt=(
                    f"Popup item cutout prompt for third beat: {base_prompt}. "
                    "No decorative border, picture frame, mat, white margin, inset panel, UI chrome, caption box, or poster edge. "
                    "No text in image."
                ),
                placement="right",
                enter_at_seconds=third_enter_at,
                animation="pop_in",
            ),
        ]
    if scene.visual_mode == "comparison_board":
        duration = scene.audio_duration_seconds or scene.duration_estimate_seconds
        return [
            VisualLayer(
                id=f"{scene.id}_compare_1",
                asset_kind="cutout",
                prompt=comparison_cutout_prompt(scene.visual_prompt, scene.narration, "left subject"),
                placement="left",
                enter_at_seconds=0.0,
                animation="pop_in",
            ),
            VisualLayer(
                id=f"{scene.id}_compare_2",
                asset_kind="cutout",
                prompt=comparison_cutout_prompt(scene.visual_prompt, scene.narration, "right subject"),
                placement="right",
                enter_at_seconds=max(duration / 2, 0.5),
                animation="pop_in",
            ),
        ]
    if scene.visual_mode == "stat_card":
        return []
    return []


def _stage_fx(ctx: TestLabRunContext) -> None:
    from pipeline.fx_generator import generate_scene_fx

    _check_cancelled(ctx)
    with Session(ctx.engine) as session:
        record, content = _load_content_for_script(session, ctx.script_id)
        scene = _first_scene(content)
        duration = scene.audio_duration_seconds or scene.duration_estimate_seconds
        scene_data = {
            "id": scene.id,
            "segment": content.segments[0].name if content.segments else "",
            "segment_index": 0,
            "scene_index_in_segment": 0,
            "global_index": 0,
            "is_first_scene": True,
            "is_last_scene": len(content.all_scenes()) == 1,
            "is_first_in_segment": True,
            "is_title_card": scene.is_title_card,
            "narration": scene.narration,
            "duration_seconds": duration,
            "duration_frames": int(duration * FPS),
            "has_multiple_frames": bool(scene.frame_urls and len(scene.frame_urls) > 1),
            "visual_mode": scene.visual_mode,
            "blink_action": scene.blink_action,
            "renderer_context": scene.renderer_context,
            "visual_beat": scene.visual_beat or "static",
        }
        if scene.word_timestamps:
            scene_data["word_timestamps"] = [word.model_dump() for word in scene.word_timestamps]
        fx_result = generate_scene_fx(scene_data)
        scene.fx = fx_result.get("fx")
        _save_content(session, record, content)


def _stage_eli(ctx: TestLabRunContext) -> None:
    from pipeline.eli_animator import generate_scene_eli

    _check_cancelled(ctx)
    with Session(ctx.engine) as session:
        cfg = session.get(ProjectConfig, ctx.script_id)
        if cfg is not None and not cfg.eli_enabled:
            return
        record, content = _load_content_for_script(session, ctx.script_id)
        scene = _first_scene(content)
        if scene.contains_person:
            return
        scene.eli_overlay = generate_scene_eli(
            scene.narration,
            previous_corner=None,
            script_id=ctx.script_id,
        )
        _save_content(session, record, content)


def _stage_render(ctx: TestLabRunContext) -> None:
    from pipeline.remotion_render import render_full_video
    from pipeline.render_jobs import update_job

    _check_cancelled(ctx)
    with Session(ctx.engine) as session:
        _record, content = _load_content_for_script(session, ctx.script_id)
        brand = {}
        script = session.get(Script, ctx.script_id)
        if script is not None:
            from models.brand import BrandProfile

            brand_row = session.get(BrandProfile, script.brand_id)
            if brand_row is not None:
                brand = {
                    "id": brand_row.id,
                    "name": brand_row.name,
                    "voice_id": brand_row.voice_id,
                    "youtube_channel_id": brand_row.youtube_channel_id,
                }

    def _on_progress(fraction: float, message: str = "") -> None:
        if not ctx.job_id:
            return
        bounded = max(0.0, min(1.0, float(fraction)))
        progress = ctx.progress_start + bounded * (ctx.progress_end - ctx.progress_start)
        update_job(ctx.job_id, progress=progress, current_step=message or None)

    render_url = render_full_video(
        script_id=ctx.script_id,
        content=content,
        on_progress=_on_progress,
        cancel_check=lambda: _check_cancelled(ctx),
        title="",
        speed=1.0,
        brand=brand,
    )
    ctx.manifest.render_url = render_url
    ctx.manifest.assets.append(TestLabAsset(kind="render", label="Remotion render", url=render_url))


def _stage_defaults(settings: dict) -> dict[str, bool]:
    eli_default = _bool_setting(settings, "eli_enabled", False)
    visual_mode = settings.get("visual_mode") or ("video" if settings.get("media_source") == "ai_video" else "full_frame")
    treatment_assets_enabled = visual_mode in {"popup_sequence", "comparison_board", "stat_card"}
    return {
        "audio": _enabled(settings, "audio", True),
        "visual": _enabled(settings, "visual", True),
        "treatment_assets": treatment_assets_enabled,
        "fx": _enabled(settings, "fx", False),
        "eli_derived": eli_default,
        "render": _enabled(settings, "render", True),
    }


def run_test_lab(
    *,
    engine,
    run_id: str,
    preset_id: str,
    settings: dict,
    job_id: str | None,
) -> list[str]:
    from pipeline.render_jobs import update_job

    safe_run_id = validate_run_id(run_id)
    settings = dict(settings or {})
    try:
        preset = get_preset(preset_id)
    except ValueError:
        preset = None
    settings["blink_action"] = _resolve_blink_action_for_settings(settings, preset)
    settings["renderer_context"] = _renderer_context_from_settings(settings, preset)
    script_id = f"test-lab-{safe_run_id}"
    manifest = TestLabRunManifest(
        run_id=safe_run_id,
        script_id=script_id,
        preset_id=preset_id,
        status="running",
        settings=settings,
    )
    ctx = TestLabRunContext(
        engine=engine,
        run_id=safe_run_id,
        script_id=script_id,
        preset_id=preset_id,
        settings=settings,
        manifest=manifest,
        job_id=job_id,
    )

    try:
        save_run_manifest(manifest)
        if job_id:
            update_job(job_id, status="running", progress=0.0, current_step="Starting Test Lab run...")

        with Session(engine) as session:
            script_id = create_hidden_test_script(
                session,
                run_id=safe_run_id,
                preset_id=preset_id,
                settings=settings,
            )
            session.commit()
        manifest.script_id = script_id
        ctx.script_id = script_id
        save_run_manifest(manifest)

        stages = [
            ("audio", _stage_audio),
            ("visual", _stage_visual),
            ("treatment_assets", _stage_treatment_assets),
            ("fx", _stage_fx),
            ("eli_derived", _stage_eli),
            ("render", _stage_render),
        ]
        default_settings = dict(settings)
        if not any(key in default_settings for key in ("visual_mode", "visual_treatment", "media_source")):
            default_settings["visual_mode"] = get_preset(preset_id).visual_mode
        enabled = _stage_defaults(default_settings)
        selected = [(name, fn) for name, fn in stages if enabled[name]]

        for index, (stage, fn) in enumerate(selected):
            log_stage(manifest, stage, "running", f"Starting {stage}")
            save_run_manifest(manifest)
            ctx.progress_start = index / max(len(selected), 1)
            ctx.progress_end = (index + 1) / max(len(selected), 1)
            _check_cancelled(ctx)
            if job_id:
                update_job(
                    job_id,
                    progress=ctx.progress_start,
                    current_step=f"Running Test Lab {stage}...",
                )
            fn(ctx)
            log_stage(manifest, stage, "completed", f"Completed {stage}")
            save_run_manifest(manifest)

        _update_manifest_cost(engine, manifest, script_id)
        manifest.status = "completed"
        save_run_manifest(manifest)
        if job_id:
            update_job(
                job_id,
                status="completed",
                progress=1.0,
                current_step="Test Lab run complete",
                output_urls=[manifest.render_url] if manifest.render_url else [],
                output_data=manifest.model_dump_json(),
            )
        return [manifest.render_url] if manifest.render_url else []
    except Exception as exc:
        logger.exception("Test Lab run %s failed", safe_run_id)
        cancelled = False
        if job_id:
            from pipeline.render_jobs import is_cancelled

            cancelled = is_cancelled(job_id)
        if cancelled:
            log_stage(manifest, "run", "cancelled", str(exc))
            _update_manifest_cost(engine, manifest, manifest.script_id)
            manifest.status = "cancelled"
            save_run_manifest(manifest)
            if job_id:
                update_job(job_id, status="cancelled", error=str(exc), current_step="Test Lab run cancelled")
        else:
            log_stage(manifest, "run", "failed", str(exc))
            _update_manifest_cost(engine, manifest, manifest.script_id)
            manifest.status = "failed"
            save_run_manifest(manifest)
            if job_id:
                update_job(job_id, status="failed", error=str(exc), current_step="Test Lab run failed")
        raise


def _update_manifest_cost(engine, manifest: TestLabRunManifest, script_id: str) -> None:
    try:
        with Session(engine) as session:
            cost = build_cost_breakdown(session, script_id)
    except Exception:
        logger.exception("Failed to update Test Lab cost for run %s", manifest.run_id)
        return
    manifest.cost_breakdown = cost
    manifest.total_cost = cost["total_cost"]


def manifest_path(run_id: str) -> Path:
    safe_run_id = validate_run_id(run_id)
    path = runs_dir() / f"{safe_run_id}.json"
    if not _path_under(path, runs_dir()):
        raise ValueError("run_id resolved outside Test Lab runs directory")
    return path


def save_run_manifest(manifest: TestLabRunManifest) -> TestLabRunManifest:
    manifest.updated_at = utc_now_iso()
    path = manifest_path(manifest.run_id)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(manifest.model_dump(mode="json"), indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    prune_run_history()
    return manifest


def load_run_manifest(run_id: str) -> TestLabRunManifest:
    path = manifest_path(run_id)
    return TestLabRunManifest.model_validate_json(path.read_text(encoding="utf-8"))


def list_run_history() -> list[TestLabRunManifest]:
    directory = runs_dir()
    if not directory.is_dir():
        return []

    manifests: list[TestLabRunManifest] = []
    for path in directory.glob("*.json"):
        try:
            manifests.append(TestLabRunManifest.model_validate_json(path.read_text(encoding="utf-8")))
        except ValueError:
            continue
    manifests.sort(key=lambda manifest: (manifest.created_at, manifest.run_id), reverse=True)
    return manifests[:MAX_HISTORY]


def clear_test_lab_history() -> None:
    root = test_lab_root()
    if root.is_dir() and _path_under(root, DATA_DIR):
        shutil.rmtree(root)
    runs_dir().mkdir(parents=True, exist_ok=True)


def prune_run_history() -> None:
    directory = runs_dir()
    if not directory.is_dir():
        return

    manifests: list[tuple[TestLabRunManifest, Path]] = []
    for path in directory.glob("*.json"):
        try:
            manifests.append((TestLabRunManifest.model_validate_json(path.read_text(encoding="utf-8")), path))
        except ValueError:
            continue

    manifests.sort(key=lambda item: (item[0].created_at, item[0].run_id), reverse=True)
    for manifest, path in manifests[MAX_HISTORY:]:
        if _path_under(path, runs_dir()):
            path.unlink(missing_ok=True)
        artifact_dir = runs_dir() / manifest.run_id
        if _path_under(artifact_dir, runs_dir()):
            if artifact_dir.is_dir():
                shutil.rmtree(artifact_dir)


def _test_lab_query(session: Session):
    """Keep Test Lab imports exercised for future API helpers without side effects."""
    _ = session
    _usage_task_label("test_lab", "test_lab", "{}")
    return select(Script, ProjectConfig).where(Script.id == ProjectConfig.script_id)
