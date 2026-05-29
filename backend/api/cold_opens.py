"""Endpoints for cold open A/B variant generation."""

import json
import logging
import os
import time

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlmodel import Session

from database import get_default_brand_id, get_session
from models.brand import BrandProfile
from models.generation_duration import GenerationDuration
from models.cold_open import GenerateColdOpensRequest
from models.script import HookScore
from pipeline.cold_open import generate_cold_opens
from pipeline.formats import resolve_format
from pipeline.hook_refiner import RefinedHook, refine_hook
from pipeline.hook_scorer import score_hook
from pipeline.render_jobs import create_job, get_job, run_in_background, update_job
from prompts import CHARACTER_SPEC_MD, IMAGE_VISUAL_STYLE


def _hook_refinement_enabled() -> bool:
    return os.environ.get("HOOK_REFINEMENT_ENABLED", "true").strip().lower() not in {"0", "false", "no", "off"}

_VISUAL_STYLE = IMAGE_VISUAL_STYLE.template
_CHARACTER = CHARACTER_SPEC_MD.template

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/scripts", tags=["cold-opens"])


class ColdOpenJobResponse(BaseModel):
    job_id: str


class RefineHookRequest(BaseModel):
    topic: str = Field(..., min_length=1)
    description: str = ""
    cold_open_index: int = Field(..., ge=0, le=2)
    cold_open_job_id: str = Field(..., min_length=1)
    format_id: str = "youtube-listicle"


class RefineHookResultData(BaseModel):
    hook_score: dict
    refined_hook: dict
    original_hook: dict


@router.post("/cold-opens", response_model=ColdOpenJobResponse)
def generate_cold_opens_endpoint(
    body: GenerateColdOpensRequest,
    session: Session = Depends(get_session),
):
    brand_id = body.brand_id or get_default_brand_id(session)
    brand = session.get(BrandProfile, brand_id)
    if not brand:
        raise HTTPException(status_code=404, detail="Brand not found")

    fmt = resolve_format(body.format_id)
    if not fmt.supports_cold_open:
        raise HTTPException(
            status_code=400,
            detail=f"Format {fmt.id!r} does not support cold opens",
        )

    logger.info(
        "Cold open generation requested: topic=%r, brand_id=%s, format_id=%s",
        body.topic, brand_id, fmt.id,
    )

    # Build brand context (same pattern as api/scripts.py)
    parts = [brand.name]
    if _VISUAL_STYLE:
        parts.append(f"Visual Style:\n{_VISUAL_STYLE}")
    if _CHARACTER:
        parts.append(f"Character:\n{_CHARACTER}")
    brand_context = "\n\n".join(parts)

    topic = body.topic
    description = body.description
    model = body.model

    job = create_job()
    job_id = job.id

    def _run() -> list[str]:
        t0_bg = time.monotonic()
        result = generate_cold_opens(
            topic=topic,
            description=description,
            brand_context=brand_context,
            model=model,
            format_id=fmt.id,
        )
        update_job(job_id, output_data=result.model_dump_json())

        from database import engine
        from sqlmodel import Session as BgSession
        with BgSession(engine) as s:
            s.add(GenerationDuration(operation_type="cold_open_generation", duration_seconds=time.monotonic() - t0_bg))
            s.commit()

        return []

    run_in_background(job_id, _run)
    return ColdOpenJobResponse(job_id=job_id)


@router.get("/cold-opens-status/{job_id}")
def cold_opens_status(job_id: str):
    job = get_job(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    result = job.to_dict()
    # If completed, parse the ColdOpenResult from output_data
    if job.status == "completed" and job.output_data:
        result["cold_open_result"] = json.loads(job.output_data)
    return result


@router.post("/refine-hook")
def refine_hook_endpoint(body: RefineHookRequest):
    cold_open_job = get_job(body.cold_open_job_id)
    if not cold_open_job or cold_open_job.status != "completed" or not cold_open_job.output_data:
        raise HTTPException(status_code=404, detail="Cold open job not found or not completed")

    cold_open_result = json.loads(cold_open_job.output_data)
    variants = cold_open_result.get("variants", [])
    if body.cold_open_index >= len(variants):
        raise HTTPException(status_code=422, detail="Invalid cold open index")

    variant = variants[body.cold_open_index]
    intro_hook = variant["intro_hook"]
    opening_narration = variant["opening_narration"]
    video_title = body.topic
    fmt = resolve_format(body.format_id)

    job = create_job()
    job_id = job.id

    def _run() -> list[str]:
        if fmt.id == "life-as-a":
            logger.info("Life-as-a opening selected — skipping listicle hook refinement")
            result = RefineHookResultData(
                hook_score={
                    "promise": {"score": 0, "reasoning": "Life-as-a openings use variant-level scoring."},
                    "tension": {"score": 0, "reasoning": "Life-as-a openings use variant-level scoring."},
                    "payoff_hint": {"score": 0, "reasoning": "Life-as-a openings use variant-level scoring."},
                    "overall": 0,
                    "suggestions": [],
                },
                refined_hook={"intro_hook": intro_hook, "opening_narration": opening_narration},
                original_hook={"intro_hook": intro_hook, "opening_narration": opening_narration},
            )
            update_job(job_id, output_data=result.model_dump_json())
            return []

        if not _hook_refinement_enabled():
            logger.info("Hook refinement disabled — passing through original hook")
            result = RefineHookResultData(
                hook_score={
                    "promise": 0,
                    "tension": 0,
                    "payoff_hint": 0,
                    "overall": 0,
                    "rationale": "Hook refinement disabled in settings.",
                },
                refined_hook={"intro_hook": intro_hook, "opening_narration": opening_narration},
                original_hook={"intro_hook": intro_hook, "opening_narration": opening_narration},
            )
            update_job(job_id, output_data=result.model_dump_json())
            return []

        update_job(job_id, current_step="Scoring hook...")
        hook_score = score_hook(
            intro_hook=intro_hook,
            hook_scenes=[],
            video_title=video_title,
            narration_text=opening_narration,
        )

        update_job(job_id, current_step="Refining hook...", progress=0.5)
        refined = refine_hook(
            intro_hook=intro_hook,
            opening_narration=opening_narration,
            hook_score=hook_score,
            video_title=video_title,
        )

        result = RefineHookResultData(
            hook_score=hook_score.model_dump(),
            refined_hook=refined.model_dump(),
            original_hook={"intro_hook": intro_hook, "opening_narration": opening_narration},
        )
        update_job(job_id, output_data=result.model_dump_json())
        return []

    run_in_background(job_id, _run)
    return {"job_id": job_id}


@router.get("/refine-hook-status/{job_id}")
def refine_hook_status(job_id: str):
    job = get_job(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    result = job.to_dict()
    if job.status == "completed" and job.output_data:
        result["refine_result"] = json.loads(job.output_data)
    return result
