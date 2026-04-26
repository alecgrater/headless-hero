"""Media upload endpoint for user-provided images and videos."""

import logging
from pathlib import Path

from fastapi import APIRouter, File, Form, HTTPException, UploadFile
from pydantic import BaseModel

from config import DATA_DIR

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/media", tags=["media"])

ALLOWED_IMAGE_TYPES = {".png", ".jpg", ".jpeg", ".webp"}
ALLOWED_VIDEO_TYPES = {".mp4", ".mov", ".webm"}
ALLOWED_TYPES = ALLOWED_IMAGE_TYPES | ALLOWED_VIDEO_TYPES


class UploadResponse(BaseModel):
    url: str
    media_type: str


@router.post("/upload", response_model=UploadResponse)
async def upload_scene_media(
    script_id: str = Form(...),
    scene_id: str = Form(...),
    file: UploadFile = File(...),
):
    """Upload an image or video file for a scene."""
    if not file.filename:
        raise HTTPException(status_code=400, detail="No filename provided")

    ext = Path(file.filename).suffix.lower()
    if ext not in ALLOWED_TYPES:
        raise HTTPException(
            status_code=400,
            detail=f"Unsupported file type: {ext}. Allowed: {', '.join(sorted(ALLOWED_TYPES))}",
        )

    uploads_dir = DATA_DIR / "projects" / script_id / "uploads"
    uploads_dir.mkdir(parents=True, exist_ok=True)
    dest = uploads_dir / f"{scene_id}{ext}"

    content = await file.read()
    dest.write_bytes(content)

    media_type = "video" if ext in ALLOWED_VIDEO_TYPES else "image"
    url = f"/static/projects/{script_id}/uploads/{scene_id}{ext}"

    logger.info("Uploaded %s for scene %s: %s (%d bytes)", media_type, scene_id, dest, len(content))
    return UploadResponse(url=url, media_type=media_type)
