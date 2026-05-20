"""cinematic-chapters title-card strategy — single AI thumbnail + per-level chapter cards."""

from __future__ import annotations

import logging
from dataclasses import dataclass
from pathlib import Path

from config import DATA_DIR
from models.script import Scene, ScriptContent
from pipeline.image_gen import generate_scene_image

logger = logging.getLogger(__name__)


def _chapter_image_path(script_id: str, level_number: int) -> Path:
    return DATA_DIR / "projects" / script_id / "images" / f"chapter_{level_number}.png"


def _thumbnail_paths(script_id: str) -> tuple[Path, Path]:
    base = DATA_DIR / "projects" / script_id / "images"
    return base / "cinematic_thumbnail.png", base / "cinematic_thumbnail_clean.png"


@dataclass(frozen=True)
class CinematicChaptersStrategy:
    """Strategy for life-as-a: one cinematic thumbnail + one chapter card per level."""

    kind: str = "cinematic-chapters"

    def prepare_thumbnail(
        self,
        script_id: str,
        content: ScriptContent,
        accent_color: str,
        force: bool = False,
        job_id: str | None = None,
    ) -> None:
        # ``job_id`` is part of the strategy protocol contract for cancellation /
        # progress tracking. The cinematic-chapters pipeline does not yet wire
        # job_id into its sub-steps; accepted here as a no-op for future use.
        del job_id

        # 1. Single cinematic thumbnail (clean — no overlay)
        clean_path, with_title_path = _thumbnail_paths(script_id)
        clean_path.parent.mkdir(parents=True, exist_ok=True)

        thumb_prompt = content.cinematic_thumbnail_prompt or content.title
        if not thumb_prompt:
            raise RuntimeError(
                "cinematic-chapters: cinematic_thumbnail_prompt missing on ScriptContent"
            )

        generate_scene_image(
            scene_id="cinematic_thumbnail_clean",
            visual_prompt=thumb_prompt,
            script_id=script_id,
            force=force,
        )

        # 2. The "with title" variant is composited by an existing helper
        #    (text-overlay composite — same util used for legacy thumbnails). Defer
        #    to thumbnail.py's existing _composite_title_overlay() once available.
        from pipeline.thumbnail import composite_title_overlay
        composite_title_overlay(
            source_image=clean_path,
            output_image=with_title_path,
            title=content.title,
            accent_color=accent_color,
        )

        # 3. Per-level chapter card images (one per segment with is_title_card scene)
        if not content.levels:
            logger.warning(
                "cinematic-chapters: content.levels is empty; no chapter images generated"
            )
            return

        for level in content.levels:
            generate_scene_image(
                scene_id=f"chapter_{level.number}",
                visual_prompt=level.image_prompt,
                script_id=script_id,
                force=force,
            )

    def prepare_title_card_scene(
        self,
        scene: Scene,
        script_id: str,
        content: ScriptContent,
        brand: dict,
    ) -> Scene:
        if not scene.is_title_card:
            return scene

        # The chapter-card scene id is "chapter_NN" by enforce_life_as_a_constraints.
        # Map back to a level number via order in segments.
        all_scenes = content.all_scenes()
        title_card_index = sum(
            1 for s in all_scenes[: all_scenes.index(scene)] if s.is_title_card
        )
        level_number = title_card_index + 1

        img_path = _chapter_image_path(script_id, level_number)
        if img_path.exists():
            scene.image_url = f"/static/projects/{script_id}/images/chapter_{level_number}.png"
        else:
            logger.warning(
                "cinematic-chapters: chapter image missing for level %d at %s",
                level_number, img_path,
            )

        # Stash overlay text onto the scene for Remotion to render.
        # The Remotion-side TitleCardScene reads scene.chapter_overlay (added in Task 8).
        descriptor = ""
        if content.levels and level_number - 1 < len(content.levels):
            descriptor = content.levels[level_number - 1].descriptor

        # Use visual_source_metadata to carry overlay info — it's a dict | None
        # field that Remotion already serializes.
        existing = dict(scene.visual_source_metadata or {})
        existing["chapter_overlay"] = {
            "level_number": level_number,
            "descriptor": descriptor,
        }
        scene.visual_source_metadata = existing

        return scene


CINEMATIC_CHAPTERS = CinematicChaptersStrategy()
