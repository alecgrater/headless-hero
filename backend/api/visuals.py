"""Endpoints for AI image generation via Google Gemini."""

import json
import logging
import time

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlmodel import Session

from config import DEFAULT_ACCENT_COLOR, IMAGE_HEIGHT, IMAGE_WIDTH
from database import get_session
from api._helpers import update_scene
from models.generation_duration import GenerationDuration
from models.script import Script, ScriptContent
from pipeline.image_gen import generate_batch, generate_scene_frames_v2, generate_scene_image
from pipeline.render_jobs import create_job, get_job, run_in_background
from pipeline.formats import resolve_format

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/visuals", tags=["visuals"])

METADATA_CLEAR = {"source_type": "none", "provider": "", "fallback": False}

# --- Request / Response schemas ---

class GenerateVisualRequest(BaseModel):
    script_id: str
    scene_id: str
    visual_prompt: str
    width: int = IMAGE_WIDTH
    height: int = IMAGE_HEIGHT
    frame_directives: list[dict] = []
    contains_person: bool = False
    media_source: str = "ai"
    gameplay_game_name: str = ""
    gameplay_game_override: str = ""
    audio_duration_seconds: float = 0.0

class GenerateVisualResponse(BaseModel):
    image_url: str
    prompt_used: str
    frame_urls: list[str] = []
    video_url: str | None = None
    visual_source_metadata: dict | None = None

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
    visual_source_metadata: dict | None = None
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
    """Generate a visual for a single scene, dispatching by media_source."""
    t0 = time.monotonic()
    record = session.get(Script, body.script_id)
    if not record:
        raise HTTPException(status_code=404, detail="Script not found")

    logger.info("Generating visual for scene %s in script %s (media_source=%s)", body.scene_id, body.script_id, body.media_source)

    # --- Stock photo dispatch ---
    if body.media_source == "stock_photo":
        logger.info("[PEXELS] scene %s — query: %s", body.scene_id, body.visual_prompt[:80])
        from pipeline.stock_photo import generate_stock_photo
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
            frame_urls = [url for url, _, _ in frame_results]
            source_metadata = next((metadata for url, _, metadata in frame_results if url and metadata), None)
            first_image = next((u for u in frame_urls if u), "")
            if frame_urls:
                _update_scene_with_frames(
                    session,
                    body.script_id,
                    body.scene_id,
                    video_url="",
                    frame_urls=frame_urls,
                    visual_source_metadata=source_metadata or METADATA_CLEAR,
                )
            session.add(GenerationDuration(operation_type="single_image_generation", duration_seconds=time.monotonic() - t0))
            session.commit()
            return GenerateVisualResponse(
                image_url=first_image,
                prompt_used=body.visual_prompt,
                frame_urls=frame_urls,
                video_url="",
                visual_source_metadata=source_metadata or METADATA_CLEAR,
            )
        image_url = generate_stock_photo(body.script_id, body.scene_id, body.visual_prompt)
        update_scene(
            session,
            body.script_id,
            body.scene_id,
            image_url=image_url,
            frame_urls=[],
            video_url="",
            visual_source_metadata=METADATA_CLEAR,
        )
        session.add(GenerationDuration(operation_type="single_image_generation", duration_seconds=time.monotonic() - t0))
        session.commit()
        return GenerateVisualResponse(image_url=image_url, prompt_used=body.visual_prompt, frame_urls=[], video_url="", visual_source_metadata=METADATA_CLEAR)

    # --- Gameplay video dispatch ---
    if body.media_source == "gameplay_video":
        from pipeline.gameplay import generate_gameplay_clip
        game_name = body.gameplay_game_name or body.gameplay_game_override
        if not game_name:
            raise HTTPException(status_code=400, detail="Gameplay scene missing game name")
        logger.info("[TWITCH] scene %s — game: %s, duration: %.1fs", body.scene_id, game_name, body.audio_duration_seconds or 8.0)
        duration = body.audio_duration_seconds or 8.0
        video_url = generate_gameplay_clip(body.script_id, body.scene_id, game_name, duration)
        update_scene(
            session,
            body.script_id,
            body.scene_id,
            image_url="",
            frame_urls=[],
            video_url=video_url,
            visual_source_metadata=METADATA_CLEAR,
        )
        session.add(GenerationDuration(operation_type="single_image_generation", duration_seconds=time.monotonic() - t0))
        session.commit()
        return GenerateVisualResponse(image_url="", prompt_used=f"gameplay:{game_name}", frame_urls=[], video_url=video_url, visual_source_metadata=METADATA_CLEAR)

    # --- AI video dispatch ---
    if body.media_source == "ai_video":
        from pipeline.video_gen import generate_scene_video

        duration = body.audio_duration_seconds or 5.0
        logger.info("[RUNWAY] scene %s — prompt: %s", body.scene_id, body.visual_prompt[:80])
        video_url, prompt_used, source_metadata = generate_scene_video(
            scene_id=body.scene_id,
            visual_prompt=body.visual_prompt,
            script_id=body.script_id,
            width=body.width,
            height=body.height,
            scene_duration_seconds=duration,
            contains_person=body.contains_person,
        )
        update_scene(
            session,
            body.script_id,
            body.scene_id,
            image_url="",
            frame_urls=[],
            video_url=video_url,
            visual_source_metadata=source_metadata,
        )
        session.add(GenerationDuration(operation_type="single_video_generation", duration_seconds=time.monotonic() - t0))
        session.commit()
        return GenerateVisualResponse(image_url="", prompt_used=prompt_used, frame_urls=[], video_url=video_url, visual_source_metadata=source_metadata)

    # --- AI-generated (default) ---
    logger.info("[GEMINI] scene %s — prompt: %s", body.scene_id, body.visual_prompt[:80])

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
        frame_urls = [url for url, _, _ in frame_results]
        source_metadata = next((metadata for url, _, metadata in frame_results if url and metadata), None)
        first_image = next((u for u in frame_urls if u), "")
        if frame_urls:
            _update_scene_with_frames(
                session,
                body.script_id,
                body.scene_id,
                video_url="",
                frame_urls=frame_urls,
                visual_source_metadata=source_metadata,
            )
        session.add(GenerationDuration(operation_type="single_image_generation", duration_seconds=time.monotonic() - t0))
        session.commit()
        return GenerateVisualResponse(
            image_url=first_image,
            prompt_used=frame_results[0][1] if frame_results else "",
            frame_urls=frame_urls,
            video_url="",
            visual_source_metadata=source_metadata,
        )

    # Single-image path
    image_url, prompt_used, source_metadata = generate_scene_image(
        scene_id=body.scene_id,
        visual_prompt=body.visual_prompt,
        script_id=body.script_id,
        width=body.width,
        height=body.height,
        contains_person=body.contains_person,
    )

    update_scene(
        session,
        body.script_id,
        body.scene_id,
        image_url=image_url,
        frame_urls=[],
        video_url="",
        visual_source_metadata=source_metadata,
    )

    session.add(GenerationDuration(operation_type="single_image_generation", duration_seconds=time.monotonic() - t0))
    session.commit()

    return GenerateVisualResponse(image_url=image_url, prompt_used=prompt_used, frame_urls=[], video_url="", visual_source_metadata=source_metadata)

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
            sc.image_url = ""
            sc.frame_urls = []
        elif frame_urls:
            sc.frame_urls = frame_urls
            sc.video_url = ""
            first_image = next((u for u in frame_urls if u), "")
            if first_image:
                sc.image_url = first_image
        elif r.get("image_url"):
            sc.image_url = r["image_url"]
            sc.frame_urls = []
            sc.video_url = ""
        sc.visual_source_metadata = r.get("visual_source_metadata") or METADATA_CLEAR
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

        fmt = resolve_format(content.format_id)
        fmt.title_card_strategy.prepare_thumbnail(
            script_id=script_id,
            content=content,
            accent_color=DEFAULT_ACCENT_COLOR,
            force=force,
            job_id=job.id,
        )

        # Persist updated image_urls back to script_json
        with SyncSession(engine) as bg_session:
            rec = bg_session.get(Script, script_id)
            if rec:
                # Re-serialize the mutated content (strategy.prepare_thumbnail mutates it)
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
