"""Style preset endpoints.

GET    /api/style/presets               -> list all
POST   /api/style/presets               -> kick off background generation
GET    /api/style/presets/jobs/{job_id} -> poll job status
DELETE /api/style/presets/{id}          -> delete (also clears active if was active)
GET    /api/style/active                -> active preset or null
PUT    /api/style/active                -> set active preset by id (or null to clear)
"""

import logging

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlmodel import Session, select

from config import DATA_DIR
from database import get_session
from models.settings import AppSetting
from models.script import MainCharacter
from models.style_preset import (
    CreateStylePresetRequest,
    GeneratePresetJobResponse,
    SetActivePresetRequest,
    StylePreset,
    StylePresetResponse,
)
from pipeline.style_presets import get_job, submit_preset_job

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/style", tags=["style"])


_ACTIVE_KEY = "ACTIVE_STYLE_PRESET_ID"


class GlobalMainCharacterResponse(BaseModel):
    main_character: MainCharacter | None = None
    main_character_reference_url: str | None = None
    main_character_reference_variants: list[dict[str, object]] = Field(default_factory=list)


def _to_response(preset: StylePreset) -> StylePresetResponse:
    return StylePresetResponse(
        id=preset.id,
        name=preset.name,
        prompt=preset.prompt,
        image_url=f"/static/style/presets/{preset.id}.png",
        created_at=preset.created_at,
    )


def _preset_image_path(preset_id: str):
    return DATA_DIR / "style" / "presets" / f"{preset_id}.png"


def _read_active_id(session: Session) -> str:
    row = session.get(AppSetting, _ACTIVE_KEY)
    return (row.value if row else "").strip()


def _write_active_id(session: Session, preset_id: str | None) -> None:
    row = session.get(AppSetting, _ACTIVE_KEY)
    if row is None:
        row = AppSetting(key=_ACTIVE_KEY, value=preset_id or "")
    else:
        row.value = preset_id or ""
    session.add(row)
    session.commit()


@router.get("/presets", response_model=list[StylePresetResponse])
def list_presets(session: Session = Depends(get_session)):
    presets = session.exec(select(StylePreset).order_by(StylePreset.created_at.desc())).all()
    valid_presets: list[StylePreset] = []

    for preset in presets:
        if _preset_image_path(preset.id).exists():
            valid_presets.append(preset)
            continue
        logger.warning("Hiding style preset with missing image: %s", preset.id)

    return [_to_response(p) for p in valid_presets]


@router.post("/presets", response_model=GeneratePresetJobResponse)
def create_preset(req: CreateStylePresetRequest):
    if not req.prompt.strip():
        raise HTTPException(status_code=400, detail="prompt is required")
    job_id = submit_preset_job(prompt=req.prompt, name=req.name or "Untitled")
    return GeneratePresetJobResponse(job_id=job_id)


@router.get("/presets/jobs/{job_id}")
def get_preset_job(job_id: str, session: Session = Depends(get_session)):
    job = get_job(job_id)
    if job is None:
        raise HTTPException(status_code=404, detail="job not found")
    payload = {
        "job_id": job.job_id,
        "status": job.status,
        "error": job.error,
        "preset_id": job.preset_id,
    }
    if job.status == "completed" and job.preset_id:
        preset = session.get(StylePreset, job.preset_id)
        if preset:
            payload["preset"] = _to_response(preset).model_dump(mode="json")
    return payload


@router.delete("/presets/{preset_id}")
def delete_preset(preset_id: str, session: Session = Depends(get_session)):
    preset = session.get(StylePreset, preset_id)
    if preset is None:
        raise HTTPException(status_code=404, detail="preset not found")

    # Clear active id if it pointed at this preset (commits internally)
    active_id = _read_active_id(session)
    if active_id == preset_id:
        _write_active_id(session, None)

    # Delete row — _write_active_id may have already committed; this is a no-op
    # if so, or the sole commit when active_id didn't match
    session.delete(preset)
    session.commit()

    # Delete file last — DB is already consistent so a file-system error is
    # recoverable (orphaned file) rather than causing a phantom active preset
    image_path = _preset_image_path(preset_id)
    if image_path.exists():
        image_path.unlink()

    return {"ok": True}


@router.get("/active", response_model=StylePresetResponse | None)
def get_active(session: Session = Depends(get_session)):
    preset_id = _read_active_id(session)
    if not preset_id:
        return None
    preset = session.get(StylePreset, preset_id)
    if preset is None:
        return None
    if not _preset_image_path(preset.id).exists():
        logger.warning("Ignoring active style preset with missing image: %s", preset.id)
        return None
    return _to_response(preset)


@router.put("/active")
def set_active(req: SetActivePresetRequest, session: Session = Depends(get_session)):
    if req.preset_id is not None:
        preset = session.get(StylePreset, req.preset_id)
        if preset is None:
            raise HTTPException(status_code=404, detail="preset not found")
        if not _preset_image_path(preset.id).exists():
            raise HTTPException(status_code=404, detail="preset image not found")
    _write_active_id(session, req.preset_id)
    return {"ok": True, "active_id": req.preset_id}


def _global_character_response(session: Session) -> GlobalMainCharacterResponse:
    from pipeline.main_character import (
        global_character_reference_path,
        list_global_character_reference_variants,
        read_global_main_character,
        read_global_main_character_reference_url,
    )

    reference_url = read_global_main_character_reference_url(session)
    if reference_url and not global_character_reference_path().exists():
        reference_url = None
    return GlobalMainCharacterResponse(
        main_character=read_global_main_character(session),
        main_character_reference_url=reference_url,
        main_character_reference_variants=list_global_character_reference_variants(),
    )


@router.get("/main-character", response_model=GlobalMainCharacterResponse)
def get_main_character(session: Session = Depends(get_session)) -> GlobalMainCharacterResponse:
    return _global_character_response(session)


@router.put("/main-character", response_model=GlobalMainCharacterResponse)
def update_main_character(
    character: MainCharacter,
    session: Session = Depends(get_session),
) -> GlobalMainCharacterResponse:
    from pipeline.main_character import write_global_main_character

    write_global_main_character(session, character)
    session.commit()
    return _global_character_response(session)


@router.post("/main-character/regenerate", response_model=GlobalMainCharacterResponse)
def regenerate_main_character(session: Session = Depends(get_session)) -> GlobalMainCharacterResponse:
    from pipeline.main_character import (
        generate_global_character_reference,
        read_global_main_character,
        write_global_main_character_reference_url,
    )

    character = read_global_main_character(session)
    if character is None or not character.name.strip() or not character.appearance.strip():
        raise HTTPException(status_code=400, detail="Global main character details are required")

    web_path = generate_global_character_reference(character=character, force=True)
    write_global_main_character_reference_url(session, web_path)
    session.commit()
    return _global_character_response(session)


@router.post("/main-character/select/{idx}", response_model=GlobalMainCharacterResponse)
def select_main_character_reference(
    idx: int,
    session: Session = Depends(get_session),
) -> GlobalMainCharacterResponse:
    from pipeline.main_character import (
        select_global_character_reference_variant,
        write_global_main_character_reference_url,
    )

    try:
        web_path = select_global_character_reference_variant(idx=idx)
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    write_global_main_character_reference_url(session, web_path)
    session.commit()
    return _global_character_response(session)
