"""Short-form export endpoints — per-segment renders only.

Intros (per-segment voiceover generation) were removed in favor of reusing
each segment's existing first-scene narration audio (which already names the
segment). See docs/superpowers/specs/2026-05-15-short-form-export-design.md.
"""

import json
import logging
import os
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlmodel import Session

from config import DATA_DIR, sanitize_filename
from database import get_session
from models.script import Script, ScriptContent
from pipeline.render_jobs import (
    create_job,
    get_job,
    run_in_background,
    update_job,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/short-form", tags=["short-form"])


# --- Request / Response schemas ---


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


class RenderedShortsResponse(BaseModel):
    rendered_indices: list[int]
    paths: dict[int, str]


class RenderShortAllRequest(BaseModel):
    script_id: str


class RenderShortOneRequest(BaseModel):
    script_id: str
    segment_idx: int


class RenderShortBatchRequest(BaseModel):
    script_id: str
    segment_indices: list[int]


# --- Helpers ---


def _load_content(session: Session, script_id: str) -> ScriptContent:
    record = session.get(Script, script_id)
    if not record:
        raise HTTPException(status_code=404, detail="Script not found")
    return ScriptContent.model_validate(json.loads(record.script_json))


def _short_download_paths(project_title: str, total: int) -> dict[int, str]:
    from pipeline.short_form_render import _short_filename

    base = os.environ.get("DOWNLOADS_DIR", "") or str(Path.home() / "Downloads")
    folder = Path(base) / sanitize_filename(project_title)
    return {
        idx: str(folder / _short_filename(project_title, idx + 1, total))
        for idx in range(total)
    }


# --- Endpoints ---


@router.get("/jobs/{job_id}", response_model=JobStatusResponse)
def job_status(job_id: str):
    """Poll a short-form render job."""
    job = get_job(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    return JobStatusResponse(**job.to_dict())


@router.get("/rendered", response_model=RenderedShortsResponse)
def rendered_shorts(script_id: str, session: Session = Depends(get_session)):
    """Return shorts that exist in Downloads or the project render folder."""
    content = _load_content(session, script_id)
    record = session.get(Script, script_id)
    project_title = record.topic_title or "Untitled"
    expected_paths = _short_download_paths(project_title, len(content.segments))
    project_dir = DATA_DIR / "projects" / script_id / "renders" / "shorts"
    paths: dict[int, str] = {}
    for idx, path in expected_paths.items():
        if Path(path).is_file():
            paths[idx] = path
            continue
        project_path = project_dir / f"{idx}.mp4"
        if project_path.is_file():
            paths[idx] = str(project_path)
    return RenderedShortsResponse(
        rendered_indices=sorted(paths.keys()),
        paths=paths,
    )


@router.post("/render/all", response_model=JobResponse)
def start_render_all_shorts(
    body: RenderShortAllRequest, session: Session = Depends(get_session)
):
    """Render all per-segment shorts in the background."""
    from pipeline.short_form_render import render_all_shorts

    content = _load_content(session, body.script_id)

    record = session.get(Script, body.script_id)
    project_title = record.topic_title or "Untitled"
    total = len(content.segments)

    job = create_job(scene_count=total)
    logger.info("Starting render-all-shorts for script %s (%d segments)", body.script_id, total)

    def do_render():
        def on_progress(p: float, msg: str):
            update_job(job.id, progress=p, current_step=msg)

        results = render_all_shorts(
            script_id=body.script_id,
            content=content,
            project_title=project_title,
            on_progress=on_progress,
        )
        update_job(job.id, progress=1.0, current_step="All shorts rendered")
        return [downloads_path for _web_url, downloads_path in results]

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

        _web_url, downloads_path = render_short_segment(
            script_id=body.script_id,
            segment_idx=body.segment_idx,
            content=content,
            project_title=project_title,
            on_progress=on_progress,
        )
        update_job(job.id, progress=1.0, current_step="Short rendered")
        return downloads_path

    run_in_background(job.id, do_render)
    return JobResponse(job_id=job.id)


@router.post("/render/batch", response_model=JobResponse)
def start_render_short_batch(
    body: RenderShortBatchRequest, session: Session = Depends(get_session)
):
    """Render selected segment shorts in one background job."""
    from pipeline.short_form_render import render_short_segment

    content = _load_content(session, body.script_id)
    total_segments = len(content.segments)
    segment_indices = list(dict.fromkeys(body.segment_indices))
    invalid_indices = [
        idx for idx in segment_indices if idx < 0 or idx >= total_segments
    ]
    if invalid_indices:
        raise HTTPException(status_code=400, detail="segment_indices out of range")
    if not segment_indices:
        raise HTTPException(status_code=400, detail="segment_indices cannot be empty")

    record = session.get(Script, body.script_id)
    project_title = record.topic_title or "Untitled"

    job = create_job(scene_count=len(segment_indices))
    logger.info(
        "Starting render-short-batch for script %s segments %s",
        body.script_id,
        segment_indices,
    )

    def do_render():
        results: list[str] = []
        batch_total = len(segment_indices)
        for batch_idx, segment_idx in enumerate(segment_indices):
            batch_n = batch_idx + 1
            segment_n = segment_idx + 1

            def on_progress(
                p: float,
                msg: str,
                _batch_idx: int = batch_idx,
                _batch_n: int = batch_n,
                _segment_n: int = segment_n,
            ) -> None:
                global_p = (_batch_idx + p) / batch_total
                update_job(
                    job.id,
                    progress=global_p,
                    current_step=f"Short {_batch_n}/{batch_total} (segment {_segment_n}): {msg}",
                )

            _web_url, downloads_path = render_short_segment(
                script_id=body.script_id,
                segment_idx=segment_idx,
                content=content,
                project_title=project_title,
                on_progress=on_progress,
            )
            results.append(downloads_path)

        update_job(job.id, progress=1.0, current_step="Selected shorts rendered")
        return results

    run_in_background(job.id, do_render)
    return JobResponse(job_id=job.id)
