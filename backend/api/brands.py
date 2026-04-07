"""Endpoints for the single default brand profile."""

import logging
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException
from sqlmodel import Session, select

from database import get_session
from models.brand import (
    BrandProfile,
    BrandProfileRead,
    BrandProfileUpdate,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api", tags=["brand"])


def _get_default_brand(session: Session) -> BrandProfile:
    """Return the single default brand or 404."""
    brand = session.exec(select(BrandProfile)).first()
    if not brand:
        raise HTTPException(status_code=404, detail="Default brand not found")
    return brand


@router.get("/brand", response_model=BrandProfileRead)
def get_brand(session: Session = Depends(get_session)):
    """Return the single default brand profile."""
    return _get_default_brand(session)


@router.put("/brand", response_model=BrandProfileRead)
def update_brand(body: BrandProfileUpdate, session: Session = Depends(get_session)):
    """Update the single default brand profile."""
    brand = _get_default_brand(session)
    updates = body.model_dump(exclude_unset=True)
    logger.info("Updating default brand: fields=%s", list(updates.keys()))
    for key, value in updates.items():
        setattr(brand, key, value)
    brand.updated_at = datetime.now(timezone.utc)
    session.add(brand)
    session.commit()
    session.refresh(brand)
    logger.info("Brand updated: %s (id=%s)", brand.name, brand.id)
    return brand
