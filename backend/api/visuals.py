"""Endpoints for AI image generation via Google Gemini."""

import json
import logging

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlmodel import Session

from config import IMAGE_HEIGHT, IMAGE_WIDTH
from database import get_session
from models.script import Script, ScriptContent
from pipeline.image_gen import generate_batch, generate_scene_frames, generate_scene_frames_v2, generate_scene_image
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
    frame_prompts: list[str] = []
    frame_directives: list[dict] = []

class GenerateVisualResponse(BaseModel):
    image_url: str
    prompt_used: str
    frame_urls: list[str] = []

class BatchScene(BaseModel):
    scene_id: str
    visual_prompt: str
    frame_prompts: list[str] = []
    frame_directives: list[dict] = []

class GenerateBatchRequest(BaseModel):
    script_id: str
    scenes: list[BatchScene]
    width: int = IMAGE_WIDTH
    height: int = IMAGE_HEIGHT

class BatchResultItem(BaseModel):
    scene_id: str
    image_url: str | None = None
    frame_urls: list[str] = []
    prompt_used: str | None = None
    error: str | None = None

class GenerateBatchResponse(BaseModel):
    results: list[BatchResultItem]

# --- Helpers ---

def _update_scene(
    session: Session, script_id: str, scene_id: str, **fields: object
) -> None:
    """Persist one or more field updates into a scene inside script_json."""
    record = session.get(Script, script_id)
    if not record:
        return
    content = ScriptContent.model_validate(json.loads(record.script_json))
    for seg in content.segments:
        for scene in seg.scenes:
            if scene.id == scene_id:
                for key, value in fields.items():
                    setattr(scene, key, value)
                # When setting frame_urls, also set image_url to first non-empty frame
                if "frame_urls" in fields and fields["frame_urls"]:
                    first_image = next((u for u in fields["frame_urls"] if u), "")
                    if first_image:
                        scene.image_url = first_image
                break
    record.script_json = content.model_dump_json()
    session.add(record)
    session.commit()

# --- Endpoints ---

@router.post("/generate", response_model=GenerateVisualResponse)
def generate_visual(body: GenerateVisualRequest, session: Session = Depends(get_session)):
    """Generate an image for a single scene."""
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
        )
        frame_urls = [url for url, _ in frame_results]
        # Guard: only set image_url from first non-empty frame URL
        first_image = next((u for u in frame_urls if u), "")
        if frame_urls:
            _update_scene(session, body.script_id, body.scene_id, frame_urls=frame_urls)
        return GenerateVisualResponse(
            image_url=first_image,
            prompt_used=frame_results[0][1] if frame_results else "",
            frame_urls=frame_urls,
        )

    # Legacy multi-frame path
    if body.frame_prompts:
        frame_results = generate_scene_frames(
            scene_id=body.scene_id,
            frame_prompts=body.frame_prompts,
            script_id=body.script_id,
            visual_prompt=body.visual_prompt,
            width=body.width,
            height=body.height,
        )
        frame_urls = [url for url, _ in frame_results]
        _update_scene(session, body.script_id, body.scene_id, frame_urls=frame_urls)
        return GenerateVisualResponse(
            image_url=frame_urls[0] if frame_urls else "",
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
    )

    _update_scene(session, body.script_id, body.scene_id, image_url=image_url)

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
            "frame_prompts": s.frame_prompts,
            "frame_directives": s.frame_directives,
        }
        for s in body.scenes
    ]

    results = generate_batch(
        scenes=scenes,
        script_id=body.script_id,
        width=body.width,
        height=body.height,
    )

    # Persist successful image URLs
    for r in results:
        frame_urls = r.get("frame_urls", [])
        if frame_urls:
            _update_scene(session, body.script_id, r["scene_id"], frame_urls=frame_urls)
        elif r["image_url"]:
            _update_scene(session, body.script_id, r["scene_id"], image_url=r["image_url"])

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
