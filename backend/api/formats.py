"""Format discovery endpoint — drives the frontend selector."""

from fastapi import APIRouter
from pydantic import BaseModel

from pipeline.formats import list_formats

router = APIRouter(prefix="/api/formats", tags=["formats"])


class FormatSummary(BaseModel):
    id: str
    display_name: str
    short_description: str
    level_count_min: int
    level_count_max: int
    level_label: str
    supports_cold_open: bool
    supports_hook_scoring: bool
    supports_segmented_generation: bool
    title_card_strategy_kind: str


def _summarize(fmt) -> FormatSummary:
    if isinstance(fmt.level_count, int):
        lo = hi = fmt.level_count
    else:
        lo, hi = fmt.level_count
    return FormatSummary(
        id=fmt.id,
        display_name=fmt.display_name,
        short_description=fmt.short_description,
        level_count_min=lo,
        level_count_max=hi,
        level_label=fmt.level_label,
        supports_cold_open=fmt.supports_cold_open,
        supports_hook_scoring=fmt.supports_hook_scoring,
        supports_segmented_generation=fmt.supports_segmented_generation,
        title_card_strategy_kind=fmt.title_card_strategy.kind,
    )


@router.get("", response_model=list[FormatSummary])
def list_formats_endpoint() -> list[FormatSummary]:
    return [_summarize(f) for f in list_formats()]
