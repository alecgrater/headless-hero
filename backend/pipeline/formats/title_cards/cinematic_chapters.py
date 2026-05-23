"""cinematic-chapters title-card strategy — single AI thumbnail + per-level chapter cards."""

from __future__ import annotations

import logging
import shutil
from dataclasses import dataclass
from pathlib import Path

from config import DATA_DIR
from models.script import Scene, ScriptContent
from pipeline.image_gen import generate_scene_image

logger = logging.getLogger(__name__)


def _with_main_character_subject(prompt: str, content: ScriptContent) -> str:
    """Strengthen life-as-a chapter prompts when a project character is active."""
    character = content.main_character
    if character is None or not character.name.strip():
        return prompt
    name = character.name.strip()
    return (
        f"{name} is the visually dominant main subject and protagonist in this image. "
        f"Depict {name} as the role named by the video; any other people are secondary and visually distinct from {name}. "
        f"{prompt}"
    )


def _chapter_image_path(script_id: str, level_number: int) -> Path:
    return DATA_DIR / "projects" / script_id / "images" / f"chapter_{level_number}.png"


def _thumbnail_paths(script_id: str) -> tuple[Path, Path, Path]:
    """Returns (clean_path, final_path, sidecar_path) for the cinematic thumbnail.

    - clean_path: AI-generated iconic image. Also reused as chapter_1.png.
    - final_path: split-progression enhanced thumbnail (frontend reads this).
    - sidecar_path: persisted label JSON for re-render consistency.
    """
    base = DATA_DIR / "projects" / script_id / "images"
    return (
        base / "cinematic_thumbnail_clean.png",
        base / "cinematic_thumbnail.png",
        base / "cinematic_thumbnail.levels.json",
    )


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
        del job_id, accent_color  # accent_color was used by the old Pillow title overlay.

        from pipeline.thumbnail import (
            _pick_life_as_a_thumbnail_labels,
            _read_life_as_a_thumbnail_label_sidecar,
            _write_life_as_a_thumbnail_label_sidecar,
            enhance_split_progression,
        )

        clean_path, final_path, sidecar_path = _thumbnail_paths(script_id)
        clean_path.parent.mkdir(parents=True, exist_ok=True)

        thumb_prompt = content.cinematic_thumbnail_prompt or content.title
        if not thumb_prompt:
            raise RuntimeError(
                "cinematic-chapters: cinematic_thumbnail_prompt missing on ScriptContent"
            )

        # 1. Generate the iconic image (Gemini call)
        generate_scene_image(
            scene_id="cinematic_thumbnail_clean",
            visual_prompt=_with_main_character_subject(thumb_prompt, content),
            script_id=script_id,
            force=force,
            contains_person=True,
        )

        # 2. Reuse it as chapter_1.png — copy if missing or older than the source.
        chapter_1_path = _chapter_image_path(script_id, 1)
        if (
            force
            or not chapter_1_path.exists()
            or chapter_1_path.stat().st_mtime < clean_path.stat().st_mtime
        ):
            chapter_1_path.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(str(clean_path), str(chapter_1_path))
            logger.info(
                "cinematic-chapters: copied cinematic image -> chapter_1 for script %s",
                script_id,
            )

        # 3. Generate chapter images for levels 2..N from levels[i].image_prompt.
        if not content.levels:
            logger.warning(
                "cinematic-chapters: content.levels is empty; falling back to clean image as final thumbnail"
            )
            shutil.copy2(str(clean_path), str(final_path))
            return

        for level in content.levels[1:]:
            if not level.image_prompt:
                logger.warning(
                    "cinematic-chapters: level %d missing image_prompt — skipping",
                    level.number,
                )
                continue
            generate_scene_image(
                scene_id=f"chapter_{level.number}",
                visual_prompt=_with_main_character_subject(level.image_prompt, content),
                script_id=script_id,
                force=force,
                contains_person=True,
            )

        # 4. Decide time labels (cached in sidecar for re-render consistency).
        n_levels = len(content.levels)
        if n_levels < 2:
            logger.warning(
                "cinematic-chapters: only %d level(s) — skipping split-progression "
                "enhancement, using clean image as final thumbnail",
                n_levels,
            )
            shutil.copy2(str(clean_path), str(final_path))
            return

        cached_labels = (
            None if force else _read_life_as_a_thumbnail_label_sidecar(sidecar_path)
        )
        if cached_labels is None:
            left_label, right_label = _pick_life_as_a_thumbnail_labels()
            _write_life_as_a_thumbnail_label_sidecar(sidecar_path, left_label, right_label)
            force_enhancement = True
        else:
            left_label, right_label = cached_labels
            force_enhancement = force

        # 5. Split-progression enhancement (Gemini call).
        enhance_split_progression(
            clean_image_path=clean_path,
            output_path=final_path,
            left_label=left_label,
            right_label=right_label,
            script_id=script_id,
            force=force_enhancement,
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
