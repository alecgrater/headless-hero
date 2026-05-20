"""composite-grid title-card strategy — wraps existing N-circle composite behavior."""

from __future__ import annotations

import logging
from dataclasses import dataclass

from models.script import Scene, ScriptContent
from pipeline.modifiers.title_cards import prepare_title_card_scene as _legacy_prepare
from pipeline.title_card import ensure_title_card_images

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class CompositeGridStrategy:
    """Strategy wrapping the existing composite-grid pipeline.

    Behavior is unchanged from pre-refactor — this class is the seam through
    which the format registry routes title-card work for `youtube-listicle`.
    """

    kind: str = "composite-grid"

    def prepare_thumbnail(
        self,
        script_id: str,
        content: ScriptContent,
        accent_color: str,
        force: bool = False,
        job_id: str | None = None,
    ) -> None:
        ensure_title_card_images(
            script_id=script_id,
            content=content,
            accent_color=accent_color,
            force=force,
            job_id=job_id,
        )

    def prepare_title_card_scene(
        self,
        scene: Scene,
        script_id: str,
        content: ScriptContent,
        brand: dict,
    ) -> Scene:
        return _legacy_prepare(scene, script_id, brand)


COMPOSITE_GRID = CompositeGridStrategy()
