"""API routes for the hidden Test Lab runner."""

from __future__ import annotations

import uuid
from typing import Any

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlmodel import Session

from config import DEFAULT_TTS_MODEL
from database import get_session
from integrations.elevenlabs_client import list_voices
from models.settings import AppSetting
from pipeline.render_jobs import create_job, get_job, run_in_background
from pipeline.test_lab import (
    TEST_LAB_PRESETS,
    VISUAL_TREATMENT_TEXT_DEFAULTS,
    clear_test_lab_history,
    list_run_history,
    load_run_manifest,
    run_test_lab,
    validate_run_id,
)
from pipeline.test_lab_popup_crop import (
    chroma_popup_crop_anchor,
    chroma_popup_crop_item_sheet,
    generate_popup_crop_preview,
    generate_popup_crop_anchor,
    generate_popup_crop_item_sheet,
)
from pipeline.full_frame_blink import (
    BURGER_KING_BLINK_AUDIT_SCRIPT_ID,
    list_blink_audit_reports,
    load_blink_audit_report,
    run_full_frame_blink_audit,
)
from pipeline.renderer_context import RendererContext, normalize_renderer_context
from pipeline.test_lab_smoke import (
    SmokeTestOptions,
    export_smoke_report,
    list_smoke_reports,
    load_smoke_report,
    run_and_save_smoke_test,
)

router = APIRouter(prefix="/api/test-lab", tags=["test-lab"])


_VOICE_DEFAULTS = {
    "ELEVENLABS_TTS_MODEL": DEFAULT_TTS_MODEL,
    "ELEVENLABS_STABILITY": "0.5",
    "ELEVENLABS_STYLE": "0.0",
    "ELEVENLABS_SPEED": "1.0",
}

_DELIVERY_PRESETS = {
    "Steady": {
        "ELEVENLABS_TTS_MODEL": "eleven_multilingual_v2",
        "ELEVENLABS_STABILITY": "0.5",
        "ELEVENLABS_STYLE": "0.0",
        "ELEVENLABS_SPEED": "1.0",
    },
    "More Human": {
        "ELEVENLABS_TTS_MODEL": "eleven_multilingual_v2",
        "ELEVENLABS_STABILITY": "0.45",
        "ELEVENLABS_STYLE": "0.15",
        "ELEVENLABS_SPEED": "0.97",
    },
    "Dramatic": {
        "ELEVENLABS_TTS_MODEL": "eleven_multilingual_v2",
        "ELEVENLABS_STABILITY": "0.35",
        "ELEVENLABS_STYLE": "0.25",
        "ELEVENLABS_SPEED": "0.95",
    },
}

_SUBTITLE_STYLE_LABELS = {
    "clean": "Clean",
    "kinetic": "Kinetic Cards",
    "burst": "Burst",
}

_SUBTITLE_STYLE_KEYS = {
    "clean": "SUBTITLE_STYLE_CLEAN_ENABLED",
    "kinetic": "SUBTITLE_STYLE_KINETIC_ENABLED",
    "burst": "SUBTITLE_STYLE_BURST_ENABLED",
}


class StartTestLabRunRequest(BaseModel):
    preset_id: str
    settings: dict[str, Any] = Field(default_factory=dict)


class PopupCropPreviewRequest(BaseModel):
    anchor_prompt: str = Field(min_length=1)
    item_prompt: str = Field(min_length=1)
    items: list[str] = Field(default_factory=list, max_length=5)


class PopupCropAnchorRequest(BaseModel):
    anchor_prompt: str = Field(min_length=1)
    run_id: str | None = None


class PopupCropAnchorChromaRequest(BaseModel):
    run_id: str = Field(min_length=1)


class PopupCropItemSheetRequest(BaseModel):
    item_prompt: str = Field(min_length=1)
    items: list[str] = Field(default_factory=list, max_length=5)
    run_id: str | None = None


class PopupCropItemSheetChromaRequest(BaseModel):
    run_id: str = Field(min_length=1)
    items: list[str] = Field(default_factory=list, max_length=5)


class BlinkAuditRequest(BaseModel):
    script_id: str = ""


class SmokeTestRequest(BaseModel):
    render_heavy: bool = True
    external_api: bool = False


def _default_main_character(session: Session) -> dict[str, str] | None:
    from pipeline.main_character import get_active_style_preset_character, read_active_style_preset_id

    preset_id = read_active_style_preset_id(session)
    if not preset_id:
        return None
    character = get_active_style_preset_character(session, preset_id)
    if character is None:
        return None
    return {
        "name": character.name,
        "appearance": character.appearance,
        "vibe": character.vibe,
        "reference_image_url": character.reference_image_url,
    }


def _setting_value(session: Session, key: str) -> str:
    row = session.get(AppSetting, key)
    if row and row.value:
        return row.value
    return _VOICE_DEFAULTS.get(key, "")


def _setting_enabled(value: str | None, fallback: bool = True) -> bool:
    if value is None:
        return fallback
    return value.strip().lower() not in {"", "0", "false", "no", "off"}


def _voice_summary(session: Session) -> dict[str, Any]:
    from database import get_default_brand_id
    from models.brand import BrandProfile

    brand = session.get(BrandProfile, get_default_brand_id(session))
    voice_id = brand.voice_id if brand and brand.voice_id else ""
    voice_name = _voice_name_for_id(voice_id)
    settings = {
        key: _setting_value(session, key)
        for key in (
            "ELEVENLABS_TTS_MODEL",
            "ELEVENLABS_STABILITY",
            "ELEVENLABS_STYLE",
            "ELEVENLABS_SPEED",
        )
    }
    model_id = settings["ELEVENLABS_TTS_MODEL"] or DEFAULT_TTS_MODEL
    model_label = "Eleven v3" if model_id == "eleven_v3" else "Eleven v2"
    delivery_preset = _delivery_preset_for_settings(settings) if model_id == "eleven_multilingual_v2" else None
    visible_settings = _visible_voice_summary_settings(model_id, settings, delivery_preset)
    return {
        "voice_id": voice_id,
        "voice_name": voice_name,
        "model_id": model_id,
        "model_label": model_label,
        "delivery_preset": delivery_preset,
        "visible_settings": visible_settings,
    }


def _voice_name_for_id(voice_id: str) -> str:
    if not voice_id:
        return "No voice selected"
    try:
        for voice in list_voices():
            if voice.get("voice_id") == voice_id:
                return voice.get("name") or voice_id
    except Exception:
        return voice_id
    return voice_id


def _delivery_preset_for_settings(settings: dict[str, str]) -> str:
    for label, preset_settings in _DELIVERY_PRESETS.items():
        if all(settings.get(key) == value for key, value in preset_settings.items()):
            return label
    return "Custom"


def _visible_voice_summary_settings(
    model_id: str,
    settings: dict[str, str],
    delivery_preset: str | None,
) -> list[dict[str, str]]:
    if model_id == "eleven_v3":
        return [{"label": "Stability", "value": settings["ELEVENLABS_STABILITY"]}]
    if delivery_preset and delivery_preset != "Custom":
        return [{"label": "Delivery preset", "value": delivery_preset}]
    return [
        {"label": "Stability", "value": settings["ELEVENLABS_STABILITY"]},
        {"label": "Style", "value": settings["ELEVENLABS_STYLE"]},
        {"label": "Speed", "value": settings["ELEVENLABS_SPEED"]},
    ]


def _subtitle_summary(session: Session) -> dict[str, Any]:
    coverage = session.get(AppSetting, "SUBTITLE_COVERAGE_MODE")
    coverage_value = (coverage.value if coverage and coverage.value else "all").strip().lower()
    enabled_style_labels = [
        _SUBTITLE_STYLE_LABELS[style]
        for style, key in _SUBTITLE_STYLE_KEYS.items()
        if _setting_enabled(session.get(AppSetting, key).value if session.get(AppSetting, key) else None, True)
    ]
    return {
        "coverage_label": "Punchy scenes" if coverage_value == "punchy" else "All scenes",
        "enabled_style_labels": enabled_style_labels,
    }


def _engine():
    import database

    return database.engine


def _run_id_from_job(job_data: dict[str, Any]) -> str:
    output_data = job_data.get("output_data")
    if isinstance(output_data, str) and output_data:
        try:
            from pipeline.test_lab import TestLabRunManifest

            return TestLabRunManifest.model_validate_json(output_data).run_id
        except ValueError:
            return ""
    return ""


@router.get("/scenes")
def get_test_lab_scenes(session: Session = Depends(get_session)):
    return {
        "presets": [preset.model_dump() for preset in TEST_LAB_PRESETS],
        "visual_treatment_defaults": VISUAL_TREATMENT_TEXT_DEFAULTS,
        "default_main_character": _default_main_character(session),
        "voice_summary": _voice_summary(session),
        "subtitle_summary": _subtitle_summary(session),
    }


@router.post("/runs")
def start_test_lab_run(request: StartTestLabRunRequest):
    run_id = uuid.uuid4().hex
    job = create_job(scene_count=1)

    def _run():
        return run_test_lab(
            engine=_engine(),
            run_id=run_id,
            preset_id=request.preset_id,
            settings=request.settings,
            job_id=job.id,
        )

    run_in_background(job.id, _run)
    return {"run_id": run_id, "job_id": job.id}


@router.post("/popup-crop")
def create_popup_crop_preview(request: PopupCropPreviewRequest):
    cleaned_items = [item.strip() for item in request.items if item.strip()]
    if not cleaned_items:
        raise HTTPException(status_code=422, detail="Add at least one item to crop.")
    result = generate_popup_crop_preview(
        anchor_prompt=request.anchor_prompt,
        item_prompt=request.item_prompt,
        items=cleaned_items,
    )
    return result.model_dump(mode="json")


@router.post("/popup-crop/anchor")
def create_popup_crop_anchor(request: PopupCropAnchorRequest):
    result = generate_popup_crop_anchor(anchor_prompt=request.anchor_prompt, run_id=request.run_id)
    return result.model_dump(mode="json")


@router.post("/popup-crop/anchor/chroma")
def create_popup_crop_anchor_chroma(request: PopupCropAnchorChromaRequest):
    try:
        result = chroma_popup_crop_anchor(run_id=request.run_id)
        return result.model_dump(mode="json")
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail="Generate the character source before running chroma.") from None


@router.post("/popup-crop/items")
def create_popup_crop_item_sheet(request: PopupCropItemSheetRequest):
    cleaned_items = [item.strip() for item in request.items if item.strip()]
    if not cleaned_items:
        raise HTTPException(status_code=422, detail="Add at least one item to crop.")
    result = generate_popup_crop_item_sheet(
        item_prompt=request.item_prompt,
        items=cleaned_items,
        run_id=request.run_id,
    )
    return result.model_dump(mode="json")


@router.post("/popup-crop/items/chroma")
def create_popup_crop_item_sheet_chroma(request: PopupCropItemSheetChromaRequest):
    cleaned_items = [item.strip() for item in request.items if item.strip()]
    if not cleaned_items:
        raise HTTPException(status_code=422, detail="Add at least one item to crop.")
    try:
        result = chroma_popup_crop_item_sheet(run_id=request.run_id, items=cleaned_items)
        return result.model_dump(mode="json")
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail="Generate the item sheet before running chroma.") from None


@router.post("/blink-audits")
def run_blink_audit(request: BlinkAuditRequest, session: Session = Depends(get_session)):
    try:
        script_id = request.script_id or BURGER_KING_BLINK_AUDIT_SCRIPT_ID
        return run_full_frame_blink_audit(session=session, script_id=script_id).model_dump(mode="json")
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail="Blink audit source script not found") from None


@router.get("/blink-audits")
def get_blink_audits():
    return {"reports": [report.model_dump(mode="json") for report in list_blink_audit_reports()]}


@router.get("/blink-audits/{report_id}")
def get_blink_audit(report_id: str):
    try:
        return load_blink_audit_report(report_id).model_dump(mode="json")
    except (FileNotFoundError, ValueError):
        raise HTTPException(status_code=404, detail="Blink Audit report not found") from None


@router.post("/smoke-test")
def run_test_lab_smoke_test(request: SmokeTestRequest):
    report = run_and_save_smoke_test(
        engine=_engine(),
        options=SmokeTestOptions(render_heavy=request.render_heavy, external_api=request.external_api),
    )
    return report.model_dump(mode="json")


@router.post("/smoke-tests")
def run_test_lab_smoke_test_history(request: SmokeTestRequest):
    report = run_and_save_smoke_test(
        engine=_engine(),
        options=SmokeTestOptions(render_heavy=request.render_heavy, external_api=request.external_api),
    )
    return report.model_dump(mode="json")


@router.get("/smoke-tests")
def get_test_lab_smoke_tests():
    return {"reports": [report.model_dump(mode="json") for report in list_smoke_reports()]}


@router.get("/smoke-tests/{report_id}/export")
def export_test_lab_smoke_test(report_id: str):
    try:
        return export_smoke_report(report_id).model_dump(mode="json")
    except (FileNotFoundError, ValueError):
        raise HTTPException(status_code=404, detail="Smoke Test report not found") from None


@router.get("/smoke-tests/{report_id}")
def get_test_lab_smoke_test(report_id: str):
    try:
        return load_smoke_report(report_id).model_dump(mode="json")
    except (FileNotFoundError, ValueError):
        raise HTTPException(status_code=404, detail="Smoke Test report not found") from None


@router.get("/runs")
def get_test_lab_runs():
    return {"runs": [manifest.model_dump(mode="json") for manifest in list_run_history()]}


@router.get("/runs/status/{job_id}")
def get_test_lab_run_status(job_id: str):
    job = get_job(job_id)
    if job is None:
        raise HTTPException(status_code=404, detail="Job not found")
    data = job.to_dict()
    run_id = _run_id_from_job(data)
    if run_id:
        data["run_id"] = run_id
    return data


@router.get("/runs/{run_id}")
def get_test_lab_run(run_id: str):
    try:
        validate_run_id(run_id)
        return load_run_manifest(run_id).model_dump(mode="json")
    except (FileNotFoundError, ValueError):
        raise HTTPException(status_code=404, detail="Run not found") from None


@router.delete("/runs")
def delete_test_lab_runs():
    clear_test_lab_history()
    return {"ok": True}
