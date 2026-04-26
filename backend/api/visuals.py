"""Endpoints for AI image generation via Google Gemini."""

import json
import logging
import time

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlmodel import Session

from config import IMAGE_HEIGHT, IMAGE_WIDTH
from database import get_session
from api._helpers import update_scene
from models.generation_duration import GenerationDuration
from models.script import Script, ScriptContent
from pipeline.image_gen import generate_batch, generate_scene_frames_v2, generate_scene_image
from pipeline.render_jobs import create_job, get_job, run_in_background
from pipeline.title_card import ensure_title_card_images

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/visuals", tags=["visuals"])

# --- Request / Response schemas ---

class GenerateVisualRequest(BaseModel):
    script_id: str
    scene_id: str
    visual_prompt: str
    width: int = IMAGE_WIDTH
    height: int = IMAGE_HEIGHT
    frame_directives: list[dict] = []
    contains_person: bool = False

class GenerateVisualResponse(BaseModel):
    image_url: str
    prompt_used: str
    frame_urls: list[str] = []

class BatchScene(BaseModel):
    scene_id: str
    visual_prompt: str
    frame_directives: list[dict] = []
    contains_person: bool = False
    media_source: str = "ai"
    gameplay_game_name: str = ""
    gameplay_game_override: str = ""
    audio_duration_seconds: float = 0.0
    upload_url: str = ""

class GenerateBatchRequest(BaseModel):
    script_id: str
    scenes: list[BatchScene]
    width: int = IMAGE_WIDTH
    height: int = IMAGE_HEIGHT

class BatchResultItem(BaseModel):
    scene_id: str
    image_url: str | None = None
    frame_urls: list[str] = []
    video_url: str | None = None
    prompt_used: str | None = None
    error: str | None = None

class GenerateBatchResponse(BaseModel):
    results: list[BatchResultItem]

# --- Helpers ---

def _update_scene_with_frames(
    session: Session, script_id: str, scene_id: str, **fields: object
) -> None:
    """Update scene fields, and when setting frame_urls, also set image_url to first non-empty frame."""
    # When setting frame_urls, also derive image_url
    if "frame_urls" in fields and fields["frame_urls"]:
        first_image = next((u for u in fields["frame_urls"] if u), "")
        if first_image:
            fields["image_url"] = first_image
    update_scene(session, script_id, scene_id, **fields)

# --- Endpoints ---

@router.post("/generate", response_model=GenerateVisualResponse)
def generate_visual(body: GenerateVisualRequest, session: Session = Depends(get_session)):
    """Generate an image for a single scene."""
    t0 = time.monotonic()
    record = session.get(Script, body.script_id)
    if not record:
        raise HTTPException(status_code=404, detail="Script not found")

    logger.info("Generating visual for scene %s in script %s", body.scene_id, body.script_id)

    # Visual Beat System v2 path: per-frame directives
    if body.frame_directives:
        frame_results = generate_scene_frames_v2(
            scene_id=body.scene_id,
            frame_directives=body.frame_directives,
            script_id=body.script_id,
            visual_prompt=body.visual_prompt,
            width=body.width,
            height=body.height,
            contains_person=body.contains_person,
        )
        frame_urls = [url for url, _ in frame_results]
        # Guard: only set image_url from first non-empty frame URL
        first_image = next((u for u in frame_urls if u), "")
        if frame_urls:
            _update_scene_with_frames(session, body.script_id, body.scene_id, frame_urls=frame_urls)
        session.add(GenerationDuration(operation_type="single_image_generation", duration_seconds=time.monotonic() - t0))
        session.commit()
        return GenerateVisualResponse(
            image_url=first_image,
            prompt_used=frame_results[0][1] if frame_results else "",
            frame_urls=frame_urls,
        )

    # Single-image path
    image_url, prompt_used = generate_scene_image(
        scene_id=body.scene_id,
        visual_prompt=body.visual_prompt,
        script_id=body.script_id,
        width=body.width,
        height=body.height,
        contains_person=body.contains_person,
    )

    update_scene(session, body.script_id, body.scene_id, image_url=image_url)

    session.add(GenerationDuration(operation_type="single_image_generation", duration_seconds=time.monotonic() - t0))
    session.commit()

    return GenerateVisualResponse(image_url=image_url, prompt_used=prompt_used)

@router.post("/generate-batch", response_model=GenerateBatchResponse)
def generate_visual_batch(body: GenerateBatchRequest, session: Session = Depends(get_session)):
    """Generate images for multiple scenes sequentially."""
    record = session.get(Script, body.script_id)
    if not record:
        raise HTTPException(status_code=404, detail="Script not found")

    logger.info("Starting batch visual generation for script %s (%d scenes)", body.script_id, len(body.scenes))

    scenes = [
        {
            "scene_id": s.scene_id,
            "visual_prompt": s.visual_prompt,
            "frame_directives": s.frame_directives,
            "contains_person": s.contains_person,
            "media_source": s.media_source,
            "gameplay_game_name": s.gameplay_game_name,
            "gameplay_game_override": s.gameplay_game_override,
            "audio_duration_seconds": s.audio_duration_seconds,
            "upload_url": s.upload_url,
        }
        for s in body.scenes
    ]

    results = generate_batch(
        scenes=scenes,
        script_id=body.script_id,
        width=body.width,
        height=body.height,
    )

    # Persist all successful results in a single DB write
    content = ScriptContent.model_validate(json.loads(record.script_json))
    scene_map = {sc.id: sc for seg in content.segments for sc in seg.scenes}
    for r in results:
        sc = scene_map.get(r["scene_id"])
        if not sc:
            continue
        frame_urls = r.get("frame_urls", [])
        video_url = r.get("video_url")
        if video_url:
            sc.video_url = video_url
        elif frame_urls:
            sc.frame_urls = frame_urls
            first_image = next((u for u in frame_urls if u), "")
            if first_image:
                sc.image_url = first_image
        elif r.get("image_url"):
            sc.image_url = r["image_url"]
    record.script_json = content.model_dump_json()
    session.add(record)
    session.commit()

    errors = sum(1 for r in results if r.get("error"))
    logger.info("Batch visual generation complete for script %s: %d succeeded, %d failed", body.script_id, len(results) - errors, errors)
    return GenerateBatchResponse(results=[BatchResultItem(**r) for r in results])


# --- Title card generation (background job with per-segment progress) ---

class GenerateTitleCardsRequest(BaseModel):
    script_id: str
    force: bool = False

class GenerateTitleCardsResponse(BaseModel):
    job_id: str

@router.post("/generate-title-cards", response_model=GenerateTitleCardsResponse)
def generate_title_cards(body: GenerateTitleCardsRequest, session: Session = Depends(get_session)):
    """Start title card generation as a background job and return the job ID."""
    record = session.get(Script, body.script_id)
    if not record:
        raise HTTPException(status_code=404, detail="Script not found")

    content = ScriptContent.model_validate(json.loads(record.script_json))
    segment_count = len(content.segments)

    job = create_job(scene_count=segment_count)

    logger.info("Starting title card generation for script %s (%d segments)", body.script_id, segment_count)

    # Capture values needed by background thread (session not thread-safe)
    script_id = body.script_id
    force = body.force

    def _run() -> list[str]:
        from database import engine
        from sqlmodel import Session as SyncSession

        t0_bg = time.monotonic()

        ensure_title_card_images(
            script_id=script_id,
            content=content,
            force=force,
            job_id=job.id,
        )

        # Persist updated image_urls back to script_json
        with SyncSession(engine) as bg_session:
            rec = bg_session.get(Script, script_id)
            if rec:
                # Re-serialize the mutated content (ensure_title_card_images mutates it)
                rec.script_json = content.model_dump_json()
                bg_session.add(rec)
                bg_session.commit()

            bg_session.add(GenerationDuration(
                operation_type="title_card_generation",
                duration_seconds=time.monotonic() - t0_bg,
                scene_count=segment_count,
            ))
            bg_session.commit()

        return []

    run_in_background(job.id, _run)

    return GenerateTitleCardsResponse(job_id=job.id)


@router.get("/title-cards-status/{job_id}")
def title_cards_status(job_id: str):
    """Poll for title card generation progress."""
    job = get_job(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    return job.to_dict()
