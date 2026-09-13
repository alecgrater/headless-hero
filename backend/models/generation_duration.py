"""Model for tracking AI generation durations."""

import logging
import uuid
from datetime import datetime, timezone

from pydantic import BaseModel
from sqlalchemy import event
from sqlmodel import Field, SQLModel

logger = logging.getLogger(__name__)

# Which engine decides how long an operation takes: (modality, llm_task).
# The task matters as much as the modality — each LLM task has its own provider
# and model keys with different defaults, and under Local Mode the cheap
# structured tasks read LOCAL_TEXT_FAST_MODEL while narrative ones read
# LOCAL_TEXT_MODEL. Stamping every text timing with the `script` engine would
# discard SEO history whenever SCRIPT_MODEL changed, and pool it when SEO_MODEL
# did. `llm_task` is None for the non-text modalities.
OPERATION_ENGINE_SCOPE: dict[str, tuple[str, str | None]] = {
    "script_generation_youtube": ("text", "script"),
    "cold_open_generation": ("text", "script"),
    "scene_refinement": ("text", "script"),
    "idea_generation": ("text", "idea"),
    "seo_generation": ("text", "seo"),
    "short_form_seo_generation": ("text", "short_form_seo"),
    "fx_generation": ("text", "fx"),
    "script_rating": ("text", "script_rating"),
    "hook_score": ("text", "hook"),
    "single_audio_generation": ("voice", None),
    "voice_cloning": ("voice", None),
    "single_image_generation": ("image", None),
    "title_card_generation": ("image", None),
    "thumbnail_generation": ("image", None),
}

# Recorded operations whose duration does not depend on any model engine, so
# their timings pool across every configuration. Listed rather than left to
# fall through, so a new operation cannot inherit "pooled" by omission —
# tests/test_generation_estimate_engine.py enforces that every recorded
# operation_type appears in one of these two tables.
ENGINE_INDEPENDENT_OPERATIONS: frozenset[str] = frozenset({
    "video_render",
    "export_bundle",
    # Cloud-only by design: Local Mode never serves AI video (see CLAUDE.md).
    "single_video_generation",
})

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
    "single_image_generation": 35.0,
    "title_card_generation": 35.0,
    "thumbnail_generation": 60.0,
    "fx_generation": 120.0,
    "script_rating": 180.0,
    "hook_score": 180.0,
    "scene_refinement": 120.0,
}


def engine_for_operation(operation_type: str) -> str:
    """Identity of the engine that would run this operation right now.

    Durations are pooled per engine, because a script that takes two minutes on
    Claude takes ninety-five on a local 27B — averaged together they produce an
    ETA that is wrong for both and converges on neither.

    Engine-independent operations return "", which pools them as before.
    """
    scope = OPERATION_ENGINE_SCOPE.get(operation_type)
    if scope is None:
        return ""
    modality, llm_task = scope
    try:
        if modality == "text":
            from integrations.llm_client import text_fingerprint

            return text_fingerprint(llm_task)
        if modality == "image":
            # image_client is the only module allowed to name an image
            # provider; asking it removes the chance of drifting from it.
            from integrations.image_client import provider_fingerprint

            return provider_fingerprint()
        from integrations.local_models import active_model, modality_source

        if modality_source(modality) != "local":
            return "cloud"
        return f"local:{active_model(modality).id}"
    except Exception as exc:  # noqa: BLE001 — a timing label is never worth failing a run
        # Warn, not debug: the sample is still written, but with no engine it
        # will never match a scoped query again.
        logger.warning("Could not resolve the engine for %s (%s); sample is unscoped", operation_type, exc)
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
