"""Per-project config endpoints (Eli on/off, main character)."""

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlmodel import Session

from database import get_session
from models.project_config import (
    ProjectConfig,
    get_project_config,
    update_project_config,
)
from models.script import MainCharacter, Script, ScriptContent

router = APIRouter(prefix="/api/projects", tags=["project_config"])


class ProjectConfigResponse(BaseModel):
    script_id: str
    eli_enabled: bool
    style_preset_enabled: bool
    main_character_reference_url: str | None
    main_character: MainCharacter | None
    main_character_reference_variants: list[dict[str, object]] = Field(default_factory=list)


class UpdateProjectConfigRequest(BaseModel):
    eli_enabled: bool | None = None
    style_preset_enabled: bool | None = None


@router.get("/{script_id}/config", response_model=ProjectConfigResponse)
def get_config(script_id: str, session: Session = Depends(get_session)) -> ProjectConfigResponse:
    script = session.get(Script, script_id)
    if script is None:
        raise HTTPException(status_code=404, detail="Script not found")

    cfg = get_project_config(session, script_id)
    main_character: MainCharacter | None = None
    try:
        content = ScriptContent.model_validate_json(script.script_json)
        main_character = content.main_character
    except Exception:  # noqa: BLE001
        main_character = None

    from pipeline.main_character import list_character_reference_variants

    return ProjectConfigResponse(
        script_id=script_id,
        eli_enabled=cfg.eli_enabled,
        style_preset_enabled=cfg.style_preset_enabled,
        main_character_reference_url=cfg.main_character_reference_url,
        main_character=main_character,
        main_character_reference_variants=list_character_reference_variants(script_id),
    )


@router.put("/{script_id}/config", response_model=ProjectConfigResponse)
def update_config(
    script_id: str,
    body: UpdateProjectConfigRequest,
    session: Session = Depends(get_session),
) -> ProjectConfigResponse:
    script = session.get(Script, script_id)
    if script is None:
        raise HTTPException(status_code=404, detail="Script not found")

    cfg = get_project_config(session, script_id)
    # If this is a synthetic default (no DB row), we need to persist it first
    if session.get(ProjectConfig, script_id) is None:
        session.add(cfg)

    if body.eli_enabled is not None:
        cfg.eli_enabled = body.eli_enabled
    if body.style_preset_enabled is not None:
        cfg.style_preset_enabled = body.style_preset_enabled
    session.add(cfg)
    session.commit()
    session.refresh(cfg)

    main_character: MainCharacter | None = None
    try:
        content = ScriptContent.model_validate_json(script.script_json)
        main_character = content.main_character
    except Exception:  # noqa: BLE001
        main_character = None

    from pipeline.main_character import list_character_reference_variants

    return ProjectConfigResponse(
        script_id=script_id,
        eli_enabled=cfg.eli_enabled,
        style_preset_enabled=cfg.style_preset_enabled,
        main_character_reference_url=cfg.main_character_reference_url,
        main_character=main_character,
        main_character_reference_variants=list_character_reference_variants(script_id),
    )


@router.put("/{script_id}/config/character", response_model=ProjectConfigResponse)
def update_character(
    script_id: str,
    body: MainCharacter,
    session: Session = Depends(get_session),
) -> ProjectConfigResponse:
    script = session.get(Script, script_id)
    if script is None:
        raise HTTPException(status_code=404, detail="Script not found")

    cfg = get_project_config(session, script_id)
    if cfg.eli_enabled:
        raise HTTPException(
            status_code=400, detail="Cannot edit main character when Eli is enabled"
        )

    content = ScriptContent.model_validate_json(script.script_json)
    previous = content.main_character
    content.main_character = body
    script.script_json = content.model_dump_json()
    session.add(script)

    # Invalidate cached scene images that depend on the character description.
    from pipeline.main_character import (
        character_reference_active_marker,
        character_reference_path,
        invalidate_dependent_scene_caches,
    )

    invalidate_dependent_scene_caches(script_id)
    if previous != body:
        cfg.main_character_reference_url = None
        marker = character_reference_active_marker(script_id)
        if marker.exists():
            marker.unlink()
        active_reference = character_reference_path(script_id)
        if active_reference.exists():
            active_reference.unlink()
        session.add(cfg)

    session.commit()
    session.refresh(script)

    from pipeline.main_character import list_character_reference_variants

    return ProjectConfigResponse(
        script_id=script_id,
        eli_enabled=cfg.eli_enabled,
        style_preset_enabled=cfg.style_preset_enabled,
        main_character_reference_url=cfg.main_character_reference_url,
        main_character=body,
        main_character_reference_variants=list_character_reference_variants(script_id),
    )


@router.post(
    "/{script_id}/config/character/regenerate", response_model=ProjectConfigResponse
)
def regenerate_character_reference(
    script_id: str, session: Session = Depends(get_session)
) -> ProjectConfigResponse:
    script = session.get(Script, script_id)
    if script is None:
        raise HTTPException(status_code=404, detail="Script not found")

    cfg = get_project_config(session, script_id)
    if cfg.eli_enabled:
        raise HTTPException(
            status_code=400, detail="Cannot regenerate main character when Eli is enabled"
        )

    content = ScriptContent.model_validate_json(script.script_json)
    if content.main_character is None:
        raise HTTPException(
            status_code=400, detail="Script has no main character to regenerate"
        )

    from pipeline.main_character import (
        generate_character_reference,
        invalidate_dependent_scene_caches,
    )

    web_path = generate_character_reference(
        script_id=script_id,
        character=content.main_character,
        force=True,
    )
    update_project_config(session, script_id, main_character_reference_url=web_path)
    invalidate_dependent_scene_caches(script_id)
    session.commit()

    from pipeline.main_character import list_character_reference_variants

    return ProjectConfigResponse(
        script_id=script_id,
        eli_enabled=cfg.eli_enabled,
        style_preset_enabled=cfg.style_preset_enabled,
        main_character_reference_url=web_path,
        main_character=content.main_character,
        main_character_reference_variants=list_character_reference_variants(script_id),
    )


@router.post(
    "/{script_id}/config/character/select/{idx}", response_model=ProjectConfigResponse
)
def select_character_reference(
    script_id: str, idx: int, session: Session = Depends(get_session)
) -> ProjectConfigResponse:
    script = session.get(Script, script_id)
    if script is None:
        raise HTTPException(status_code=404, detail="Script not found")

    cfg = get_project_config(session, script_id)
    if cfg.eli_enabled:
        raise HTTPException(
            status_code=400, detail="Cannot select main character when Eli is enabled"
        )

    from pipeline.main_character import (
        invalidate_dependent_scene_caches,
        list_character_reference_variants,
        select_character_reference_variant,
    )

    try:
        web_path = select_character_reference_variant(script_id=script_id, idx=idx)
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc

    update_project_config(session, script_id, main_character_reference_url=web_path)
    invalidate_dependent_scene_caches(script_id)
    session.commit()

    content = ScriptContent.model_validate_json(script.script_json)
    return ProjectConfigResponse(
        script_id=script_id,
        eli_enabled=cfg.eli_enabled,
        style_preset_enabled=cfg.style_preset_enabled,
        main_character_reference_url=web_path,
        main_character=content.main_character,
        main_character_reference_variants=list_character_reference_variants(script_id),
    )
