"""Reusable generated asset APIs."""

from __future__ import annotations

from typing import Literal

from fastapi import APIRouter, HTTPException, Query

from pipeline import asset_vault

router = APIRouter(prefix="/api/assets", tags=["assets"])


@router.get("/vault")
def get_asset_vault(kind: Literal["character", "item"] | None = Query(default=None)):
    try:
        assets = asset_vault.list_vault_images(kind=kind)
    except KeyError:
        raise HTTPException(status_code=422, detail="Vault kind must be character or item.") from None
    return {"assets": [asset.model_dump(mode="json") for asset in assets]}
