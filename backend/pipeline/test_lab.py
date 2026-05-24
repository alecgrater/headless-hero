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
from models.script import MainCharacter, Scene, Script, ScriptContent, Segment, VisualCanvas, VisualLayer
from pipeline.script_helpers import _usage_task_label

logger = logging.getLogger(__name__)

MAX_HISTORY = 20
TEST_LAB_DIRNAME = "test-lab"
__test__ = False
SAFE_RUN_ID_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_-]{0,127}$")


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
    media_source: Literal["ai", "ai_video"] = "ai"
    duration_estimate_seconds: float = 7.0
    main_character: MainCharacter | None = None


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
    def validate_run_id(cls, value: str) -> str:
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
        media_source="ai_video",
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
        media_source="ai_video",
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


def _sync_ai_video_enabled(content: ScriptContent) -> ScriptContent:
    content.ai_video_enabled = any(
        scene.media_source == "ai_video"
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
    if "visual_treatment" in settings and "visual_treatment" not in advanced_scene:
        scene.visual_treatment = settings["visual_treatment"]
    if (
        "visual_layers" in settings
        and "visual_layers" not in advanced_scene
        and isinstance(settings["visual_layers"], list)
    ):
        scene.visual_layers = [VisualLayer.model_validate(layer) for layer in settings["visual_layers"]]


def build_content_from_preset(preset_id: str, settings: dict) -> ScriptContent:
    preset = get_preset(preset_id)
    media_source = _setting(settings, "media_source", preset.media_source)
    scene = Scene(
        id=f"{preset.id}-scene-1",
        narration=_setting(settings, "narration", preset.narration),
        visual_prompt=_setting(settings, "visual_prompt", preset.visual_prompt),
        duration_estimate_seconds=float(
            _setting(settings, "duration_estimate_seconds", preset.duration_estimate_seconds)
        ),
        media_source=media_source,
        contains_person=bool(_setting(settings, "contains_person", preset.main_character is not None)),
        visual_treatment=_setting(settings, "visual_treatment", "full_frame"),
        visual_layers=settings.get("visual_layers") if isinstance(settings.get("visual_layers"), list) else [],
    )
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
        segment_timer_enabled=bool(_setting(settings, "segment_timer_enabled", True)),
        subtitle_highlight_enabled=bool(_setting(settings, "subtitle_highlight_enabled", True)),
        ai_video_enabled=media_source == "ai_video",
        format_id=_setting(settings, "format_id", preset.format_id),
    )
    advanced_script = settings.get("advanced_script")
    if isinstance(advanced_script, dict):
        content = ScriptContent.model_validate(_deep_merge(content.model_dump(), advanced_script))
        _reapply_top_level_scene_settings(content, settings)
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
    brand_id = settings.get("brand_id") or get_default_brand_id(session)
    eli_enabled = _bool_setting(settings, "eli_enabled", True)
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


def _voice_id_for_run(session: Session, ctx: TestLabRunContext) -> str:
    if ctx.settings.get("voice_id"):
        return str(ctx.settings["voice_id"])

    from database import get_default_brand_id
    from models.brand import BrandProfile

    brand_id = get_default_brand_id(session)
    brand = session.get(BrandProfile, brand_id)
    if not brand or not brand.voice_id:
        raise RuntimeError("No voice configured - set a voice in Settings first")
    return brand.voice_id


def _stage_audio(ctx: TestLabRunContext) -> None:
    from config import DEFAULT_TTS_MODEL
    from pipeline.voiceover import frame_title_card_for_tts, generate_scene_audio

    _check_cancelled(ctx)
    with Session(ctx.engine) as session:
        voice_id = _voice_id_for_run(session, ctx)
        record, content = _load_content_for_script(session, ctx.script_id)
        scene = _first_scene(content)
        narration = scene.tts_narration.strip() or scene.narration
        if scene.is_title_card:
            narration = frame_title_card_for_tts(narration, 1)
        audio_url, duration, word_timestamps, phrase_timestamps = generate_scene_audio(
            scene.id,
            narration,
            voice_id,
            ctx.script_id,
            model_id=str(ctx.settings.get("voice_model_id") or DEFAULT_TTS_MODEL),
            voice_settings=ctx.settings.get("voice_settings") if isinstance(ctx.settings.get("voice_settings"), dict) else None,
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
        if scene.media_source == "ai_video":
            from pipeline.video_gen import generate_scene_video

            video_url, _prompt_used, source_metadata = generate_scene_video(
                scene_id=scene.id,
                visual_prompt=scene.visual_prompt,
                script_id=ctx.script_id,
                scene_duration_seconds=scene.audio_duration_seconds or scene.duration_estimate_seconds,
                contains_person=scene.contains_person,
                force=True,
            )
            image_url = f"/static/projects/{ctx.script_id}/images/{scene.id}.png"
            scene.video_url = video_url
            scene.image_url = ""
            scene.frame_urls = []
            scene.visual_source_metadata = source_metadata
            ctx.manifest.assets.append(TestLabAsset(kind="video", label="AI video", url=video_url))
            ctx.manifest.assets.append(TestLabAsset(kind="image", label="Anchor image", url=image_url))
        else:
            from pipeline.image_gen import generate_scene_image

            image_url, _prompt_used, source_metadata = generate_scene_image(
                scene.id,
                scene.visual_prompt,
                ctx.script_id,
                force=True,
                contains_person=scene.contains_person,
            )
            scene.image_url = image_url
            scene.video_url = ""
            scene.frame_urls = []
            scene.visual_source_metadata = source_metadata
            ctx.manifest.assets.append(TestLabAsset(kind="image", label="Scene image", url=image_url))
        _save_content(session, record, content)


def _stage_treatment_assets(ctx: TestLabRunContext) -> None:
    from pipeline.image_gen import generate_visual_layer_panels
    from pipeline.visual_treatments import analyze_visual_treatments, apply_visual_treatment_assignments

    _check_cancelled(ctx)
    with Session(ctx.engine) as session:
        record, content = _load_content_for_script(session, ctx.script_id)
        scene = _first_scene(content)
        if scene.media_source == "ai_video":
            scene.visual_treatment = "full_frame"
            scene.visual_layers = []
            _save_content(session, record, content)
            return
        requested_treatment = ctx.settings.get("visual_treatment")
        if isinstance(requested_treatment, str):
            scene.visual_treatment = requested_treatment
        layer_based_treatment = scene.visual_treatment in {"popup_sequence", "flipflop"}
        explicit_treatment = "visual_treatment" in ctx.settings or scene.visual_treatment != "full_frame"
        if not explicit_treatment:
            assignments = analyze_visual_treatments(content, script_id=ctx.script_id)
            apply_visual_treatment_assignments(content, assignments)
            scene = _first_scene(content)
            layer_based_treatment = scene.visual_treatment in {"popup_sequence", "flipflop"}
        if scene.visual_treatment == "full_frame":
            scene.visual_layers = []
            _save_content(session, record, content)
            return
        if not layer_based_treatment:
            _save_content(session, record, content)
            return
        if not scene.visual_layers:
            assignment = None
            if scene.audio_duration_seconds > 0 and scene.word_timestamps:
                assignments = analyze_visual_treatments(content, script_id=ctx.script_id)
                assignment = _assignment_for_scene(assignments, scene.id)
            scene.visual_layers = (
                list(assignment.visual_layers)
                if assignment and assignment.visual_layers
                else _fallback_visual_layers_for_treatment(scene)
            )
            if isinstance(requested_treatment, str):
                scene.visual_treatment = requested_treatment
        if scene.visual_layers:
            layer_dicts = [layer.model_dump() for layer in scene.visual_layers]
            generated_layers = generate_visual_layer_panels(
                scene.id,
                layer_dicts,
                ctx.script_id,
                force=True,
                contains_person=scene.contains_person,
            )
            scene.visual_layers = [VisualLayer.model_validate(layer) for layer in generated_layers]
            for layer in scene.visual_layers:
                if layer.image_url:
                    ctx.manifest.assets.append(
                        TestLabAsset(kind="treatment_asset", label=f"Treatment asset {layer.id}", url=layer.image_url)
                    )
        _save_content(session, record, content)


def _assignment_for_scene(assignments: list["VisualTreatmentAssignment"], scene_id: str):
    return next((assignment for assignment in assignments if assignment.scene_id == scene_id), None)


def _fallback_visual_layers_for_treatment(scene: Scene) -> list[VisualLayer]:
    base_prompt = scene.visual_prompt.strip() or scene.narration.strip()
    if scene.visual_treatment == "popup_sequence":
        return [
            VisualLayer(
                id=f"{scene.id}_popup_1",
                prompt=f"small framed Headless Hero cartoon panel: {base_prompt}. No text in image.",
                placement="left",
                enter_at_seconds=0.0,
                animation="pop_in",
            ),
            VisualLayer(
                id=f"{scene.id}_popup_2",
                prompt=f"small framed Headless Hero cartoon panel, second beat: {base_prompt}. No text in image.",
                placement="right",
                enter_at_seconds=max((scene.audio_duration_seconds or scene.duration_estimate_seconds) / 2, 0.5),
                animation="pop_in",
            ),
        ]
    return [
        VisualLayer(
            id=f"{scene.id}_state_a",
            prompt=f"small framed Headless Hero cartoon panel for state A: {base_prompt}. No text in image.",
            placement="center",
            enter_at_seconds=0.0,
            animation="pop_in",
        ),
        VisualLayer(
            id=f"{scene.id}_state_b",
            prompt=f"small framed Headless Hero cartoon panel for state B: {base_prompt}. No text in image.",
            placement="center",
            enter_at_seconds=max((scene.audio_duration_seconds or scene.duration_estimate_seconds) / 2, 0.5),
            animation="pop_in",
        ),
    ]


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
    eli_default = _bool_setting(settings, "eli_enabled", True)
    treatment_assets_enabled = (
        False if settings.get("media_source") == "ai_video" else _enabled(settings, "treatment_assets", True)
    )
    return {
        "character": _enabled(settings, "character", False),
        "audio": _enabled(settings, "audio", True),
        "visual": _enabled(settings, "visual", True),
        "treatment_assets": treatment_assets_enabled,
        "fx": _enabled(settings, "fx", False),
        "eli": _enabled(settings, "eli", eli_default),
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
            ("character", _stage_character_reference),
            ("audio", _stage_audio),
            ("visual", _stage_visual),
            ("treatment_assets", _stage_treatment_assets),
            ("fx", _stage_fx),
            ("eli", _stage_eli),
            ("render", _stage_render),
        ]
        enabled = _stage_defaults(settings)
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

        with Session(engine) as session:
            cost = build_cost_breakdown(session, script_id)
        manifest.cost_breakdown = cost
        manifest.total_cost = cost["total_cost"]
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
            manifest.status = "cancelled"
            save_run_manifest(manifest)
            if job_id:
                update_job(job_id, status="cancelled", error=str(exc), current_step="Test Lab run cancelled")
        else:
            log_stage(manifest, "run", "failed", str(exc))
            manifest.status = "failed"
            save_run_manifest(manifest)
            if job_id:
                update_job(job_id, status="failed", error=str(exc), current_step="Test Lab run failed")
        raise


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
