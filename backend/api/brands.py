"""CRUD endpoints for brand profiles."""

import logging
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException
from sqlmodel import Session, select

from database import get_session
from models.brand import (
    BrandProfile,
    BrandProfileCreate,
    BrandProfileRead,
    BrandProfileUpdate,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/brands", tags=["brands"])


@router.get("/modifiers")
def list_modifiers():
    """Return metadata for all available content modifiers."""
    import pipeline.modifiers  # noqa: F401 — ensure modifiers are registered
    from pipeline.modifiers.registry import all_metadata
    return all_metadata()

@router.post("", response_model=BrandProfileRead, status_code=201)
def create_brand(body: BrandProfileCreate, session: Session = Depends(get_session)):
    logger.info("Creating brand: %s", body.name)
    brand = BrandProfile.model_validate(body)
    session.add(brand)
    session.commit()
    session.refresh(brand)
    logger.info("Brand created: %s (id=%s)", brand.name, brand.id)
    return brand

@router.get("", response_model=list[BrandProfileRead])
def list_brands(session: Session = Depends(get_session)):
    return session.exec(select(BrandProfile).order_by(BrandProfile.name)).all()

@router.get("/{brand_id}", response_model=BrandProfileRead)
def get_brand(brand_id: str, session: Session = Depends(get_session)):
    brand = session.get(BrandProfile, brand_id)
    if not brand:
        raise HTTPException(status_code=404, detail="Brand not found")
    return brand

@router.put("/{brand_id}", response_model=BrandProfileRead)
def update_brand(
    brand_id: str, body: BrandProfileUpdate, session: Session = Depends(get_session)
):
    brand = session.get(BrandProfile, brand_id)
    if not brand:
        raise HTTPException(status_code=404, detail="Brand not found")
    updates = body.model_dump(exclude_unset=True)
    logger.info("Updating brand %s: fields=%s", brand_id, list(updates.keys()))
    for key, value in updates.items():
        setattr(brand, key, value)
    brand.updated_at = datetime.now(timezone.utc)
    session.add(brand)
    session.commit()
    session.refresh(brand)
    logger.info("Brand updated: %s (id=%s)", brand.name, brand_id)
    return brand

@router.delete("/{brand_id}", status_code=204)
def delete_brand(brand_id: str, session: Session = Depends(get_session)):
    brand = session.get(BrandProfile, brand_id)
    if not brand:
        raise HTTPException(status_code=404, detail="Brand not found")
    session.delete(brand)
    session.commit()
    logger.info("Brand deleted: %s", brand_id)
