"""Reusable character reference and cutout asset processing."""

from __future__ import annotations

import hashlib
import json
import logging
import shutil
from dataclasses import dataclass
from pathlib import Path

from PIL import Image

logger = logging.getLogger(__name__)

PROCESSOR_VERSION = 1
DEFAULT_PADDING = 24
DEFAULT_TOLERANCE = 70

_WARNING_EMPTY = "cutout_visible_area_empty"
_WARNING_SMALL = "cutout_visible_area_small"
_WARNING_LARGE = "cutout_visible_area_large"
_WARNING_TOUCH_EDGE = "cutout_bounds_touch_image_edge"
_WARNING_INCONSISTENT_CORNERS = "background_corner_samples_inconsistent"


@dataclass(frozen=True)
class CharacterAssetResult:
    reference_path: Path
    cutout_path: Path
    metadata_path: Path
    trim_box: list[int]
    warnings: list[str]


def process_character_asset_bundle(
    source_path: Path,
    output_dir: Path,
    reference_filename: str,
    cutout_filename: str,
    metadata_filename: str = "metadata.json",
    prompt_fingerprint: str = "",
    padding: int = DEFAULT_PADDING,
    tolerance: int = DEFAULT_TOLERANCE,
) -> CharacterAssetResult:
    """Copy a character source image and create a transparent trimmed cutout."""
    if not source_path.exists():
        raise FileNotFoundError(f"character source image not found: {source_path}")

    output_dir.mkdir(parents=True, exist_ok=True)
    reference_path = output_dir / reference_filename
    cutout_path = output_dir / cutout_filename
    metadata_path = output_dir / metadata_filename
    _validate_distinct_output_paths(
        reference_path=reference_path,
        cutout_path=cutout_path,
        metadata_path=metadata_path,
    )

    if source_path.resolve() != reference_path.resolve():
        shutil.copy2(source_path, reference_path)

    logger.info("Processing character cutout from %s", reference_path)
    with Image.open(reference_path) as image:
        rgba = image.convert("RGBA")
        keyed, background_warning = _key_out_chroma_background(
            rgba,
            tolerance=tolerance,
        )
        trim_box, warnings = _save_trimmed_cutout(
            keyed,
            cutout_path,
            fallback_image=rgba,
            padding=padding,
        )

    if background_warning:
        warnings.insert(0, background_warning)

    metadata = {
        "background_removal_method": "chroma_corner_sample",
        "cutout_path": cutout_path.name,
        "cutout_sha256": _sha256(cutout_path),
        "padding": padding,
        "prompt_fingerprint": prompt_fingerprint,
        "source_path": reference_path.name,
        "source_sha256": _sha256(reference_path),
        "trim_box": trim_box,
        "version": PROCESSOR_VERSION,
        "warnings": warnings,
    }
    metadata_path.write_text(
        json.dumps(metadata, indent=2, sort_keys=True),
        encoding="utf-8",
    )

    if warnings:
        logger.warning(
            "Character cutout warnings for %s: %s",
            cutout_path,
            ", ".join(warnings),
        )

    return CharacterAssetResult(
        reference_path=reference_path,
        cutout_path=cutout_path,
        metadata_path=metadata_path,
        trim_box=trim_box,
        warnings=warnings,
    )


def _validate_distinct_output_paths(
    *,
    reference_path: Path,
    cutout_path: Path,
    metadata_path: Path,
) -> None:
    resolved_paths = {
        reference_path.resolve(),
        cutout_path.resolve(),
        metadata_path.resolve(),
    }
    if len(resolved_paths) != 3:
        raise ValueError("character asset output paths must be distinct")


def _save_trimmed_cutout(
    image: Image.Image,
    output_path: Path,
    *,
    fallback_image: Image.Image,
    padding: int,
) -> tuple[list[int], list[str]]:
    bbox = image.getbbox()
    warnings: list[str] = []
    if bbox is None:
        fallback_bbox = fallback_image.getbbox()
        if fallback_bbox is None:
            image.save(output_path)
            return [0, 0, image.width, image.height], [_WARNING_EMPTY]
        bbox = fallback_bbox
        image = fallback_image

    left, top, right, bottom = bbox
    padded = [
        max(0, left - padding),
        max(0, top - padding),
        min(image.width, right + padding),
        min(image.height, bottom + padding),
    ]

    visible_area = (right - left) * (bottom - top)
    total_area = image.width * image.height
    visible_ratio = visible_area / total_area if total_area else 0
    if visible_ratio < 0.02:
        warnings.append(_WARNING_SMALL)
    if visible_ratio > 0.90:
        warnings.append(_WARNING_LARGE)
    if left <= 0 or top <= 0 or right >= image.width or bottom >= image.height:
        warnings.append(_WARNING_TOUCH_EDGE)

    image.crop(tuple(padded)).save(output_path)
    return padded, warnings


def _key_out_chroma_background(
    image: Image.Image,
    *,
    tolerance: int,
) -> tuple[Image.Image, str | None]:
    background, warning = _sample_background_rgb(image)
    data = bytearray(image.tobytes())
    for index in range(0, len(data), 4):
        red, green, blue, alpha = data[index : index + 4]
        if _rgb_distance((red, green, blue), background) <= tolerance:
            data[index + 3] = 0
        else:
            data[index + 3] = alpha
    return Image.frombytes("RGBA", image.size, bytes(data)), warning


def _sample_background_rgb(image: Image.Image) -> tuple[tuple[int, int, int], str | None]:
    corner_size = max(1, min(image.width, image.height, 24))
    corners = [
        image.crop((0, 0, corner_size, corner_size)),
        image.crop((image.width - corner_size, 0, image.width, corner_size)),
        image.crop((0, image.height - corner_size, corner_size, image.height)),
        image.crop(
            (
                image.width - corner_size,
                image.height - corner_size,
                image.width,
                image.height,
            )
        ),
    ]

    corner_colors: list[tuple[int, int, int]] = []
    all_samples: list[tuple[int, int, int]] = []
    for corner in corners:
        data = corner.convert("RGB").tobytes()
        samples = [
            (data[index], data[index + 1], data[index + 2])
            for index in range(0, len(data), 3)
        ]
        all_samples.extend(samples)
        corner_colors.append(_average_rgb(samples))

    background = _average_rgb(all_samples)
    max_distance = max(_rgb_distance(background, color) for color in corner_colors)
    warning = _WARNING_INCONSISTENT_CORNERS if max_distance > 45 else None
    return background, warning


def _average_rgb(samples: list[tuple[int, int, int]]) -> tuple[int, int, int]:
    return (
        round(sum(pixel[0] for pixel in samples) / len(samples)),
        round(sum(pixel[1] for pixel in samples) / len(samples)),
        round(sum(pixel[2] for pixel in samples) / len(samples)),
    )


def _rgb_distance(a: tuple[int, int, int], b: tuple[int, int, int]) -> float:
    return ((a[0] - b[0]) ** 2 + (a[1] - b[1]) ** 2 + (a[2] - b[2]) ** 2) ** 0.5


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()
