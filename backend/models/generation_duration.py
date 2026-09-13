"""Model for tracking AI generation durations."""

import logging
import uuid
from datetime import datetime, timezone

from pydantic import BaseModel
from sqlalchemy import event
from sqlmodel import Field, SQLModel

logger = logging.getLogger(__name__)

# Which modality's engine decides how long an operation takes. Anything absent
# is engine-independent (a Remotion render, a file copy), so its timings pool
# across every configuration.
OPERATION_MODALITY: dict[str, str] = {
    "script_generation_youtube": "text",
    "cold_open_generation": "text",
    "idea_generation": "text",
    "seo_generation": "text",
    "short_form_seo_generation": "text",
    "single_audio_generation": "voice",
    "voice_cloning": "voice",
    "thumbnail_generation": "image",
}

# What a first local run should be told before any local sample exists, from
# docs/local-models-run-report.md. Without these the UI either shows a
# cloud-calibrated ETA against a run that is 40x longer, or no ETA at all in
# front of an hour-and-a-half wait. Replaced by real measurements as soon as
# one local run of that operation completes.
LOCAL_BASELINE_SECONDS: dict[str, float] = {
    # Outline plus eight segment calls at ~11 min each, measured on an M4 Max.
    "script_generation_youtube": 5700.0,
    "cold_open_generation": 600.0,
    "idea_generation": 300.0,
    "seo_generation": 240.0,
    "short_form_seo_generation": 240.0,
    "single_audio_generation": 5.0,
    "thumbnail_generation": 60.0,
}


def engine_for_operation(operation_type: str) -> str:
    """Identity of the engine that would run this operation right now.

    Durations are pooled per engine, because a script that takes two minutes on
    Claude takes ninety-five on a local 27B — averaged together they produce an
    ETA that is wrong for both and converges on neither.

    Engine-independent operations return "", which pools them as before.
    """
    modality = OPERATION_MODALITY.get(operation_type)
    if modality is None:
        return ""
    try:
        if modality == "text":
            from integrations.llm_client import text_fingerprint

            return text_fingerprint("script")
        from integrations.local_models import active_model, modality_source

        if modality_source(modality) != "local":
            return "cloud"
        return f"local:{active_model(modality).id}"
    except Exception as exc:  # noqa: BLE001 — a timing label is never worth failing a run
        logger.debug("Could not resolve the engine for %s (%s)", operation_type, exc)
        return ""


class GenerationDuration(SQLModel, table=True):
    __tablename__ = "generation_durations"

    id: str = Field(default_factory=lambda: uuid.uuid4().hex, primary_key=True)
    operation_type: str = Field(index=True)
    duration_seconds: float
    scene_count: int | None = Field(default=None)
    # Stamped automatically on insert (see below), so the ten call sites that
    # record a duration do not each have to remember to.
    engine: str = Field(default="", index=True)
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


@event.listens_for(GenerationDuration, "before_insert")
def _stamp_engine(_mapper, _connection, target: GenerationDuration) -> None:
    """Record which engine produced a timing, unless the caller already said.

    A listener rather than a default_factory because the answer depends on
    `operation_type`, which a field default cannot see — and rather than ten
    edited call sites, because the eleventh would be the one that forgot.
    """
    if not target.engine:
        target.engine = engine_for_operation(target.operation_type)


class GenerationEstimateResponse(BaseModel):
    operation_type: str
    average_seconds: float | None
    sample_count: int
    # The engine the estimate describes, and whether it came from this machine's
    # own history or from the published baseline. The UI says "estimated" rather
    # than showing a measured-looking number it has not measured.
    engine: str = ""
    source: str = "measured"
