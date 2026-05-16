"""Short-form export endpoints — intros + per-segment renders."""

import json
import logging

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlmodel import Session

from database import get_session
from models.brand import BrandProfile
from models.script import Script, ScriptContent
from pipeline.render_jobs import (
    create_job,
    get_job,
    run_in_background,
    update_job,
)
from pipeline.short_form_intros import (
    build_display_text,
    generate_short_intro,
    generate_short_intros,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/short-form", tags=["short-form"])

# --- Request / Response schemas ---


class GenerateShortIntrosRequest(BaseModel):
    script_id: str
    force: bool = False  # if true, regenerates even non-stale intros


class GenerateShortIntroRequest(BaseModel):
    script_id: str
    segment_idx: int


class JobResponse(BaseModel):
    job_id: str


class JobStatusResponse(BaseModel):
    job_id: str
    status: str
    progress: float
    current_step: str
    output_urls: list[str]
    error: str | None = None
    estimated_seconds: float | None = None
    elapsed_seconds: float | None = None


# --- Helpers ---


def _load_content(session: Session, script_id: str) -> ScriptContent:
    record = session.get(Script, script_id)
    if not record:
        raise HTTPException(status_code=404, detail="Script not found")
    return ScriptContent.model_validate(json.loads(record.script_json))


def _resolve_voice_id(session: Session, script_id: str) -> str:
    record = session.get(Script, script_id)
    if not record:
        raise HTTPException(status_code=404, detail="Script not found")
    brand = session.get(BrandProfile, record.brand_id)
    if not brand or not brand.voice_id:
        raise HTTPException(
            status_code=400,
            detail="No voice configured — set a voice in Settings first",
        )
    return brand.voice_id


def _persist_intros(script_id: str, intros: list) -> None:
    """Write a list of ShortIntros into the script's short_intros field."""
    from database import engine

    with Session(engine) as session:
        record = session.get(Script, script_id)
        if not record:
            return
        content = ScriptContent.model_validate(json.loads(record.script_json))

        existing_map = {intro.segment_idx: intro for intro in (content.short_intros or [])}
        for intro in intros:
            existing_map[intro.segment_idx] = intro
        content.short_intros = [existing_map[k] for k in sorted(existing_map.keys())]

        record.script_json = content.model_dump_json()
        session.add(record)
        session.commit()


# --- Endpoints: intros ---


@router.post("/intros/generate-all", response_model=JobResponse)
def start_generate_all_intros(
    body: GenerateShortIntrosRequest, session: Session = Depends(get_session)
):
    """Generate intros for every segment in the background."""
    content = _load_content(session, body.script_id)
    voice_id = _resolve_voice_id(session, body.script_id)
    total = len(content.segments)

    job = create_job(scene_count=total)
    logger.info(
        "Starting short-form intro generation for script %s (%d segments, force=%s)",
        body.script_id, total, body.force,
    )

    def do_generate():
        def on_progress(idx, n, display_text):
            update_job(
                job.id,
                progress=idx / max(1, n),
                current_step=f"Generating intro {idx + 1}/{n}...",
            )

        intros = generate_short_intros(
            script_id=body.script_id,
            content=content,
            voice_id=voice_id,
            force=body.force,
            on_progress=on_progress,
        )
        _persist_intros(body.script_id, intros)
        update_job(job.id, progress=1.0, current_step="Complete")
        return ""

    run_in_background(job.id, do_generate)
    return JobResponse(job_id=job.id)


@router.post("/intros/generate-one", response_model=JobResponse)
def start_generate_one_intro(
    body: GenerateShortIntroRequest, session: Session = Depends(get_session)
):
    """Regenerate a single segment's intro in the background."""
    content = _load_content(session, body.script_id)
    if body.segment_idx < 0 or body.segment_idx >= len(content.segments):
        raise HTTPException(status_code=400, detail="segment_idx out of range")
    voice_id = _resolve_voice_id(session, body.script_id)
    seg = content.segments[body.segment_idx]
    display_text = build_display_text(content.title, seg.name)

    job = create_job(scene_count=1)
    logger.info(
        "Starting short-form intro regen for script %s segment %d",
        body.script_id, body.segment_idx,
    )

    def do_generate():
        update_job(job.id, progress=0.1, current_step=f"Generating intro for {seg.name}...")
        intro = generate_short_intro(
            script_id=body.script_id,
            segment_idx=body.segment_idx,
            display_text=display_text,
            voice_id=voice_id,
        )
        _persist_intros(body.script_id, [intro])
        update_job(job.id, progress=1.0, current_step="Complete")
        return ""

    run_in_background(job.id, do_generate)
    return JobResponse(job_id=job.id)


@router.get("/jobs/{job_id}", response_model=JobStatusResponse)
def job_status(job_id: str):
    """Poll a short-form job (intro or render)."""
    job = get_job(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    return JobStatusResponse(**job.to_dict())


# --- Render endpoints ---


class RenderShortAllRequest(BaseModel):
    script_id: str


class RenderShortOneRequest(BaseModel):
    script_id: str
    segment_idx: int


def _validate_intros_present(content: ScriptContent) -> None:
    intros = content.short_intros or []
    intro_segments = {intro.segment_idx for intro in intros}
    missing = [i for i in range(len(content.segments)) if i not in intro_segments]
    if missing:
        raise HTTPException(
            status_code=400,
            detail=f"Missing intros for segments: {missing}. Generate intros first.",
        )


@router.post("/render/all", response_model=JobResponse)
def start_render_all_shorts(
    body: RenderShortAllRequest, session: Session = Depends(get_session)
):
    """Render all per-segment shorts in the background."""
    from pipeline.short_form_render import render_all_shorts

    content = _load_content(session, body.script_id)
    _validate_intros_present(content)

    record = session.get(Script, body.script_id)
    project_title = record.topic_title or "Untitled"
    total = len(content.segments)

    job = create_job(scene_count=total)
    logger.info("Starting render-all-shorts for script %s (%d segments)", body.script_id, total)

    def do_render():
        def on_progress(p: float, msg: str):
            update_job(job.id, progress=p, current_step=msg)

        urls = render_all_shorts(
            script_id=body.script_id,
            content=content,
            project_title=project_title,
            on_progress=on_progress,
        )
        for url in urls:
            job.output_urls.append(url)
        update_job(job.id, progress=1.0, current_step="All shorts rendered")
        return ""

    run_in_background(job.id, do_render)
    return JobResponse(job_id=job.id)


@router.post("/render/one", response_model=JobResponse)
def start_render_one_short(
    body: RenderShortOneRequest, session: Session = Depends(get_session)
):
    """Render a single segment's short in the background."""
    from pipeline.short_form_render import render_short_segment

    content = _load_content(session, body.script_id)
    if body.segment_idx < 0 or body.segment_idx >= len(content.segments):
        raise HTTPException(status_code=400, detail="segment_idx out of range")
    _validate_intros_present(content)

    record = session.get(Script, body.script_id)
    project_title = record.topic_title or "Untitled"

    job = create_job(scene_count=1)
    logger.info(
        "Starting render-one-short for script %s segment %d",
        body.script_id, body.segment_idx,
    )

    def do_render():
        def on_progress(p: float, msg: str):
            update_job(job.id, progress=p, current_step=msg)

        url = render_short_segment(
            script_id=body.script_id,
            segment_idx=body.segment_idx,
            content=content,
            project_title=project_title,
            on_progress=on_progress,
        )
        job.output_urls.append(url)
        update_job(job.id, progress=1.0, current_step="Short rendered")
        return url

    run_in_background(job.id, do_render)
    return JobResponse(job_id=job.id)
