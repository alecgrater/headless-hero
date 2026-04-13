"""Endpoints for the single default brand profile."""

import json
import logging
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException
from sqlmodel import Session, select

from database import get_session
from models.brand import (
    BrandProfile,
    BrandProfileRead,
    BrandProfileUpdate,
    EliPosition,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api", tags=["brand"])


def _get_default_brand(session: Session) -> BrandProfile:
    """Return the single default brand or 404."""
    brand = session.exec(select(BrandProfile)).first()
    if not brand:
        raise HTTPException(status_code=404, detail="Default brand not found")
    return brand


def _parse_eli_position(raw: str) -> EliPosition | None:
    """Parse eli_position_json string into EliPosition, or None if empty."""
    if not raw:
        return None
    try:
        return EliPosition(**json.loads(raw))
    except (json.JSONDecodeError, TypeError):
        return None


def _brand_to_read(brand: BrandProfile) -> BrandProfileRead:
    """Convert DB model to response, deserializing eli_position."""
    return BrandProfileRead(
        id=brand.id,
        name=brand.name,
        voice_id=brand.voice_id,
        youtube_channel_id=brand.youtube_channel_id,
        eli_position=_parse_eli_position(brand.eli_position_json),
        created_at=brand.created_at,
        updated_at=brand.updated_at,
    )


@router.get("/brand", response_model=BrandProfileRead)
def get_brand(session: Session = Depends(get_session)):
    """Return the single default brand profile."""
    return _brand_to_read(_get_default_brand(session))


@router.put("/brand", response_model=BrandProfileRead)
def update_brand(body: BrandProfileUpdate, session: Session = Depends(get_session)):
    """Update the single default brand profile."""
    brand = _get_default_brand(session)
    updates = body.model_dump(exclude_unset=True)
    logger.info("Updating default brand: fields=%s", list(updates.keys()))

    # Handle eli_position → eli_position_json serialization
    if "eli_position" in updates:
        pos = updates.pop("eli_position")
        brand.eli_position_json = json.dumps(pos) if pos else ""

    for key, value in updates.items():
        setattr(brand, key, value)
    brand.updated_at = datetime.now(timezone.utc)
    session.add(brand)
    session.commit()
    session.refresh(brand)
    logger.info("Brand updated: %s (id=%s)", brand.name, brand.id)
    return _brand_to_read(brand)
