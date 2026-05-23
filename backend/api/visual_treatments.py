"""Endpoints for static canvas visual treatment settings."""

from __future__ import annotations

import json
import logging
import re

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlmodel import Session

from api.settings import VISUAL_CANVAS_COLOR_PALETTE_KEY
from database import get_session
from models.script import Script, ScriptContent
from models.settings import AppSetting
from pipeline.render_cache import mark_render_inputs_changed

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/visual-treatments", tags=["visual-treatments"])

DEFAULT_CANVAS_COLOR = "#F6C54A"
MAX_PALETTE_COLORS = 24
_HEX_COLOR_RE = re.compile(r"^[0-9A-F]{6}$")


class CanvasPaletteResponse(BaseModel):
    colors: list[str]


class UpdateVisualCanvasRequest(BaseModel):
    background_color: str


class UpdateVisualCanvasResponse(BaseModel):
    script: ScriptContent
    palette: list[str]


def normalize_hex_color(value: str) -> str:
    """Normalize a 6-digit hex color to #RRGGBB."""
    text = value.strip().upper()
    if text.startswith("#"):
        text = text[1:]
    if not _HEX_COLOR_RE.fullmatch(text):
        raise HTTPException(
            status_code=400,
            detail="Enter a valid 6-digit hex color.",
        )
    return f"#{text}"


def _default_palette() -> list[str]:
    return [DEFAULT_CANVAS_COLOR]


def _normalize_palette_values(values: object) -> list[str]:
    if not isinstance(values, list):
        return _default_palette()

    colors: list[str] = []
    seen: set[str] = set()
    for value in values:
        if not isinstance(value, str):
            continue
        try:
            color = normalize_hex_color(value)
        except HTTPException:
            continue
        if color in seen:
            continue
        colors.append(color)
        seen.add(color)
        if len(colors) >= MAX_PALETTE_COLORS:
            break
    return colors or _default_palette()


def get_canvas_palette(session: Session) -> CanvasPaletteResponse:
    row = session.get(AppSetting, VISUAL_CANVAS_COLOR_PALETTE_KEY)
    raw_value = row.value if row and row.value else json.dumps(_default_palette())
    try:
        values = json.loads(raw_value)
    except json.JSONDecodeError:
        logger.warning("[VISUAL_CANVAS] invalid palette JSON; using default")
        return CanvasPaletteResponse(colors=_default_palette())

    return CanvasPaletteResponse(colors=_normalize_palette_values(values))


def add_palette_color(session: Session, color: str) -> list[str]:
    normalized_color = normalize_hex_color(color)
    existing_colors = get_canvas_palette(session).colors
    colors = [normalized_color, *(c for c in existing_colors if c != normalized_color)]
    colors = colors[:MAX_PALETTE_COLORS]

    row = session.get(AppSetting, VISUAL_CANVAS_COLOR_PALETTE_KEY)
    if row:
        row.value = json.dumps(colors)
    else:
        session.add(
            AppSetting(
                key=VISUAL_CANVAS_COLOR_PALETTE_KEY,
                value=json.dumps(colors),
            )
        )
    logger.info(
        "[VISUAL_CANVAS] palette updated; added=%s size=%d",
        normalized_color,
        len(colors),
    )
    return colors


@router.get("/palette", response_model=CanvasPaletteResponse)
def read_canvas_palette(session: Session = Depends(get_session)) -> CanvasPaletteResponse:
    return get_canvas_palette(session)


@router.put("/{script_id}/canvas", response_model=UpdateVisualCanvasResponse)
def update_visual_canvas(
    script_id: str,
    request: UpdateVisualCanvasRequest,
    session: Session = Depends(get_session),
) -> UpdateVisualCanvasResponse:
    record = session.get(Script, script_id)
    if not record:
        raise HTTPException(status_code=404, detail="Script not found")

    background_color = normalize_hex_color(request.background_color)
    content = ScriptContent.model_validate_json(record.script_json)
    content.title = record.topic_title or content.title
    old_color = content.visual_canvas.background_color
    content.visual_canvas.background_color = background_color
    record.script_json = content.model_dump_json()
    session.add(record)
    palette = add_palette_color(session, background_color)
    session.commit()
    mark_render_inputs_changed(script_id)
    logger.info(
        "[VISUAL_CANVAS] script=%s old=%s new=%s",
        script_id,
        old_color,
        background_color,
    )
    return UpdateVisualCanvasResponse(script=content, palette=palette)
