"""Endpoints for fetching real media (gameplay clips, hardware images) via yt-dlp."""

import logging

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlmodel import Session

from api.database import get_session
from models.script import Script, ScriptContent
from pipeline.media_fetcher import fetch_batch, fetch_scene_media

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/media", tags=["media"])

# --- Request / Response schemas ---


class FetchMediaRequest(BaseModel):
    script_id: str
    scene_id: str
    media_type: str  # "gameplay_clip" | "hardware_image"
    search_query: str
    duration: float = 10.0
    force: bool = False


class FetchMediaResponse(BaseModel):
    scene_id: str
    video_clip_url: str | None = None
    image_url: str | None = None


class BatchFetchScene(BaseModel):
    scene_id: str
    media_type: str
    search_query: str
    duration: float = 10.0


class BatchFetchRequest(BaseModel):
    script_id: str
    scenes: list[BatchFetchScene]


class BatchFetchResultItem(BaseModel):
    scene_id: str
    video_clip_url: str | None = None
    image_url: str | None = None
    error: str | None = None


class BatchFetchResponse(BaseModel):
    results: list[BatchFetchResultItem]


# --- Endpoints ---


@router.post("/fetch", response_model=FetchMediaResponse)
def fetch_media(req: FetchMediaRequest, session: Session = Depends(get_session)):
    """Fetch real media for a single scene and update the script_json."""
    logger.info("Fetching %s for scene %s (script %s)", req.media_type, req.scene_id, req.script_id)
    db_script = session.get(Script, req.script_id)
    if not db_script:
        raise HTTPException(404, "Script not found")

    try:
        result = fetch_scene_media(
            script_id=req.script_id,
            scene_id=req.scene_id,
            media_type=req.media_type,
            search_query=req.search_query,
            duration=req.duration,
            force=req.force,
        )
    except Exception as e:
        raise HTTPException(500, str(e))

    # Update the scene in script_json
    content = ScriptContent.model_validate_json(db_script.script_json)
    for seg in content.segments:
        for sc in seg.scenes:
            if sc.id == req.scene_id:
                if "video_clip_url" in result:
                    sc.video_clip_url = result["video_clip_url"]
                if "image_url" in result:
                    sc.image_url = result["image_url"]
                break
    db_script.script_json = content.model_dump_json()
    session.add(db_script)
    session.commit()

    logger.info("Media fetch complete for scene %s", req.scene_id)
    return FetchMediaResponse(
        scene_id=req.scene_id,
        video_clip_url=result.get("video_clip_url"),
        image_url=result.get("image_url"),
    )


@router.post("/fetch-batch", response_model=BatchFetchResponse)
def fetch_media_batch(req: BatchFetchRequest, session: Session = Depends(get_session)):
    """Fetch real media for multiple scenes."""
    logger.info("Batch fetching media for %d scenes (script %s)", len(req.scenes), req.script_id)
    db_script = session.get(Script, req.script_id)
    if not db_script:
        raise HTTPException(404, "Script not found")

    scenes_data = [s.model_dump() for s in req.scenes]
    results = fetch_batch(scenes_data, req.script_id)

    # Update script_json for successful fetches
    content = ScriptContent.model_validate_json(db_script.script_json)
    result_map = {r["scene_id"]: r for r in results if "error" not in r}
    for seg in content.segments:
        for sc in seg.scenes:
            if sc.id in result_map:
                r = result_map[sc.id]
                if "video_clip_url" in r:
                    sc.video_clip_url = r["video_clip_url"]
                if "image_url" in r:
                    sc.image_url = r["image_url"]
    db_script.script_json = content.model_dump_json()
    session.add(db_script)
    session.commit()

    success_count = sum(1 for r in results if "error" not in r or r.get("error") is None)
    logger.info("Batch media fetch complete: %d/%d scenes succeeded", success_count, len(req.scenes))
    return BatchFetchResponse(
        results=[
            BatchFetchResultItem(
                scene_id=r["scene_id"],
                video_clip_url=r.get("video_clip_url"),
                image_url=r.get("image_url"),
                error=r.get("error"),
            )
            for r in results
        ]
    )
