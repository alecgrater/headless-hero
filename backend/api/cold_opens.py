"""Endpoints for cold open A/B variant generation."""

import json
import logging

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlmodel import Session

from database import get_default_brand_id, get_session
from models.brand import BrandProfile
from models.cold_open import GenerateColdOpensRequest
from pipeline.cold_open import generate_cold_opens
from pipeline.render_jobs import create_job, get_job, run_in_background, update_job
from prompts import CHARACTER_SPEC_MD, IMAGE_VISUAL_STYLE

_VISUAL_STYLE = IMAGE_VISUAL_STYLE.template
_CHARACTER = CHARACTER_SPEC_MD.template

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/scripts", tags=["cold-opens"])


class ColdOpenJobResponse(BaseModel):
    job_id: str


@router.post("/cold-opens", response_model=ColdOpenJobResponse)
def generate_cold_opens_endpoint(
    body: GenerateColdOpensRequest,
    session: Session = Depends(get_session),
):
    brand_id = body.brand_id or get_default_brand_id(session)
    brand = session.get(BrandProfile, brand_id)
    if not brand:
        raise HTTPException(status_code=404, detail="Brand not found")

    logger.info("Cold open generation requested: topic=%r, brand_id=%s", body.topic, brand_id)

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
        result = generate_cold_opens(
            topic=topic,
            description=description,
            brand_context=brand_context,
            model=model,
        )
        update_job(job_id, output_data=result.model_dump_json())
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
