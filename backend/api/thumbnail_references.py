"""Thumbnail reference image management — upload, list, delete."""

import logging
from pathlib import Path

from fastapi import APIRouter, HTTPException, UploadFile

from config import DATA_DIR

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/character/thumbnail-references", tags=["character"])

REFERENCES_DIR = DATA_DIR / "character" / "thumbnail_references"


def _ensure_dir() -> Path:
    REFERENCES_DIR.mkdir(parents=True, exist_ok=True)
    return REFERENCES_DIR


@router.get("")
async def list_references():
    """List all uploaded thumbnail reference images."""
    ref_dir = _ensure_dir()
    files = sorted(
        [f.name for f in ref_dir.iterdir() if f.suffix.lower() in (".png", ".jpg", ".jpeg", ".webp")],
    )
    return {
        "references": [
            {"filename": f, "url": f"/static/character/thumbnail_references/{f}"}
            for f in files
        ],
    }


@router.post("")
async def upload_reference(file: UploadFile):
    """Upload a new thumbnail reference image."""
    if not file.content_type or not file.content_type.startswith("image/"):
        raise HTTPException(status_code=422, detail="File must be an image")

    ref_dir = _ensure_dir()
    # Sanitize filename — keep original name but ensure no path traversal
    safe_name = Path(file.filename).name if file.filename else "reference.png"
    dest = ref_dir / safe_name

    # Avoid overwrites by appending a counter
    counter = 1
    stem = dest.stem
    suffix = dest.suffix
    while dest.exists():
        dest = ref_dir / f"{stem}_{counter}{suffix}"
        counter += 1

    content = await file.read()
    dest.write_bytes(content)
    logger.info("Uploaded thumbnail reference: %s", dest.name)

    return {"filename": dest.name, "url": f"/static/character/thumbnail_references/{dest.name}"}


@router.delete("/{filename}")
async def delete_reference(filename: str):
    """Delete a thumbnail reference image."""
    ref_dir = _ensure_dir()
    # Prevent path traversal
    safe_name = Path(filename).name
    target = ref_dir / safe_name
    if not target.exists():
        raise HTTPException(status_code=404, detail="Reference not found")
    target.unlink()
    logger.info("Deleted thumbnail reference: %s", safe_name)
    return {"deleted": safe_name}
