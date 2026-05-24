"""API routes for the hidden Test Lab runner."""

from __future__ import annotations

import uuid
from typing import Any

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlmodel import Session

from database import get_session
from pipeline.render_jobs import create_job, get_job, run_in_background
from pipeline.test_lab import (
    TEST_LAB_PRESETS,
    clear_test_lab_history,
    list_run_history,
    load_run_manifest,
    run_test_lab,
    validate_run_id,
)
from pipeline.test_lab_popup_crop import generate_popup_crop_preview

router = APIRouter(prefix="/api/test-lab", tags=["test-lab"])


class StartTestLabRunRequest(BaseModel):
    preset_id: str
    settings: dict[str, Any] = Field(default_factory=dict)


class PopupCropPreviewRequest(BaseModel):
    anchor_prompt: str = Field(min_length=1)
    item_prompt: str = Field(min_length=1)
    items: list[str] = Field(default_factory=list, max_length=5)


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
        "default_main_character": _default_main_character(session),
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
