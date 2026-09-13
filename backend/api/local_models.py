"""Read-only status for Local Mode: catalog, active selections, daemon health."""

from fastapi import APIRouter

from integrations.local_models import MODALITIES, active_model, modality_source, models_for
from pipeline.local_runtime import DAEMONS, daemon_health, daemon_url

router = APIRouter(prefix="/api/local-models", tags=["local-models"])


@router.get("")
async def get_local_models() -> dict:
    """Everything the Settings panel needs to render Local Mode in one call."""
    health = daemon_health()
    sources = {modality: modality_source(modality) for modality in MODALITIES}
    return {
        "enabled": any(source == "local" for source in sources.values()),
        "modalities": {
            modality: {
                "source": sources[modality],
                "active_model": active_model(modality).id,
            }
            for modality in MODALITIES
        },
        "catalog": {
            modality: [
                {
                    "id": model.id,
                    "label": model.label,
                    "description": model.description,
                    "backend": model.backend,
                    "license": model.license,
                    "approx_resident_gb": model.approx_resident_gb,
                    "requires_attribution": model.requires_attribution,
                    "attribution_text": model.attribution_text,
                }
                for model in models_for(modality)
            ]
            for modality in MODALITIES
        },
        "daemons": {
            backend: {"healthy": health[backend], "url": daemon_url(backend)}
            for backend in DAEMONS
        },
    }
