"""Popup crop lab helpers for contact-sheet prompt iteration."""

from __future__ import annotations

import re
import shutil
import uuid
from pathlib import Path

from PIL import Image
from pydantic import BaseModel, Field

from config import DATA_DIR, IMAGE_HEIGHT, IMAGE_WIDTH
from integrations.image_client import generate_image

PROJECT_ID = "test-lab-popup-crops"


class PopupCropResultCrop(BaseModel):
    role: str
    label: str
    url: str
    raw_url: str
    box: list[int]
    trim_box: list[int]


class PopupCropPreviewResult(BaseModel):
    run_id: str
    anchor_prompt_used: str
    item_prompt_used: str
    anchor_source_url: str
    sheet_url: str
    crops: list[PopupCropResultCrop] = Field(default_factory=list)


def generate_popup_crop_preview(
    *,
    anchor_prompt: str,
    item_prompt: str,
    items: list[str],
    run_id: str | None = None,
) -> PopupCropPreviewResult:
    """Generate separate anchor and item-sheet images, then crop clean cutouts."""

    cleaned_items = [_clean_label(item) for item in items if _clean_label(item)]
    safe_run_id = _safe_run_id(run_id or uuid.uuid4().hex)
    output_dir = DATA_DIR / "projects" / PROJECT_ID / safe_run_id
    output_dir.mkdir(parents=True, exist_ok=True)

    composed_anchor_prompt = _compose_anchor_prompt(anchor_prompt)
    generated_anchor_path = Path(
        generate_image(composed_anchor_prompt, width=IMAGE_WIDTH, height=IMAGE_HEIGHT, script_id=PROJECT_ID)
    )
    anchor_source_path = output_dir / "anchor_source.png"
    if generated_anchor_path.resolve() != anchor_source_path.resolve():
        shutil.copyfile(generated_anchor_path, anchor_source_path)

    composed_item_prompt = _compose_item_sheet_prompt(item_prompt, cleaned_items)
    generated_sheet_path = Path(
        generate_image(composed_item_prompt, width=IMAGE_WIDTH, height=IMAGE_HEIGHT, script_id=PROJECT_ID)
    )

    sheet_path = output_dir / "item_sheet.png"
    if generated_sheet_path.resolve() != sheet_path.resolve():
        shutil.copyfile(generated_sheet_path, sheet_path)

    crops = [
        _process_anchor_source(anchor_source_path, output_dir),
        *_crop_item_sheet(sheet_path, output_dir, cleaned_items),
    ]
    return PopupCropPreviewResult(
        run_id=safe_run_id,
        anchor_prompt_used=composed_anchor_prompt,
        item_prompt_used=composed_item_prompt,
        anchor_source_url=_web_url(safe_run_id, "anchor_source.png"),
        sheet_url=_web_url(safe_run_id, "item_sheet.png"),
        crops=crops,
    )


def _compose_anchor_prompt(prompt: str) -> str:
    return "\n".join(
        [
            "Create one large isolated cutout of the same recurring character used by this scene.",
            "The character should be detailed, expressive, centered, and visually dominant.",
            "Use a flat chroma background color that does not appear anywhere in the character, preferably bright green unless the character contains green.",
            "No props unless requested, no text, no labels, no frames, no full background scene.",
            "Leave a little empty margin around the full character so automatic trimming does not clip the pose.",
            "",
            "Character direction:",
            prompt.strip(),
        ]
    ).strip()


def _compose_item_sheet_prompt(prompt: str, items: list[str]) -> str:
    item_lines = [f"{index}. {item}" for index, item in enumerate(items, start=1)]
    return "\n".join(
        [
            "Create a clean Headless Hero cartoon item contact sheet for automatic cropping.",
            f"Create exactly {len(items)} isolated popup item cutout(s), arranged left to right in this exact order:",
            *item_lines,
            "Each item must sit alone in its own equal-width vertical slot.",
            "Do not include the main character.",
            "Do not draw frames, labels, captions, speech bubbles, text, arrows, colored cards, rounded rectangles, or full background scenes.",
            "Use one flat chroma background color across the entire image that does not appear anywhere in any item, preferably bright green unless an item contains green.",
            "Leave generous empty margin around each item so fixed vertical crops do not clip it.",
            "",
            "Item style direction:",
            prompt.strip(),
        ]
    ).strip()


def _process_anchor_source(anchor_path: Path, output_dir: Path) -> PopupCropResultCrop:
    with Image.open(anchor_path) as image:
        source = image.convert("RGBA")
        raw_filename = "raw_crop_01_anchor_character.png"
        source.save(output_dir / raw_filename)
        filename = "crop_01_anchor_character.png"
        trim_box = _save_keyed_trimmed_cutout(source, output_dir / filename)
        return PopupCropResultCrop(
            role="anchor",
            label="Anchor character",
            url=_web_url(output_dir.name, filename),
            raw_url=_web_url(output_dir.name, raw_filename),
            box=[0, 0, source.width, source.height],
            trim_box=trim_box,
        )


def _crop_item_sheet(sheet_path: Path, output_dir: Path, labels: list[str]) -> list[PopupCropResultCrop]:
    with Image.open(sheet_path) as image:
        source = image.convert("RGBA")
        total = len(labels)
        cell_width = source.width // total
        run_id = output_dir.name
        crops: list[PopupCropResultCrop] = []
        for index, label in enumerate(labels):
            left = index * cell_width
            top = 0
            right = source.width if index == total - 1 else (index + 1) * cell_width
            bottom = source.height
            crop = source.crop((left, top, right, bottom))
            output_index = index + 2
            raw_filename = f"raw_crop_{output_index:02d}_{_slug(label)}.png"
            crop.save(output_dir / raw_filename)
            filename = f"crop_{output_index:02d}_{_slug(label)}.png"
            trim_box = _save_keyed_trimmed_cutout(crop, output_dir / filename)
            crops.append(
                PopupCropResultCrop(
                    role="item",
                    label=label,
                    url=_web_url(run_id, filename),
                    raw_url=_web_url(run_id, raw_filename),
                    box=[left, top, right, bottom],
                    trim_box=trim_box,
                )
            )
    return crops


def _save_keyed_trimmed_cutout(image: Image.Image, output_path: Path, *, padding: int = 24) -> list[int]:
    keyed = _key_out_background(image.convert("RGBA"))
    bbox = keyed.getbbox()
    if bbox is None:
        keyed.save(output_path)
        return [0, 0, keyed.width, keyed.height]

    left, top, right, bottom = bbox
    padded = [
        max(0, left - padding),
        max(0, top - padding),
        min(keyed.width, right + padding),
        min(keyed.height, bottom + padding),
    ]
    keyed.crop(tuple(padded)).save(output_path)
    return padded


def _key_out_background(image: Image.Image, *, tolerance: int = 70) -> Image.Image:
    bg = _sample_background_rgb(image)
    data = bytearray(image.tobytes())
    for index in range(0, len(data), 4):
        red, green, blue, alpha = data[index:index + 4]
        distance = ((red - bg[0]) ** 2 + (green - bg[1]) ** 2 + (blue - bg[2]) ** 2) ** 0.5
        if distance <= tolerance:
            data[index + 3] = 0
        else:
            data[index + 3] = alpha
    return Image.frombytes("RGBA", image.size, bytes(data))


def _sample_background_rgb(image: Image.Image) -> tuple[int, int, int]:
    corner_size = max(1, min(image.width, image.height, 24))
    corners = [
        image.crop((0, 0, corner_size, corner_size)),
        image.crop((image.width - corner_size, 0, image.width, corner_size)),
        image.crop((0, image.height - corner_size, corner_size, image.height)),
        image.crop((image.width - corner_size, image.height - corner_size, image.width, image.height)),
    ]
    samples = []
    for corner in corners:
        data = corner.convert("RGB").tobytes()
        samples.extend((data[index], data[index + 1], data[index + 2]) for index in range(0, len(data), 3))
    red = round(sum(pixel[0] for pixel in samples) / len(samples))
    green = round(sum(pixel[1] for pixel in samples) / len(samples))
    blue = round(sum(pixel[2] for pixel in samples) / len(samples))
    return red, green, blue


def _web_url(run_id: str, filename: str) -> str:
    return f"/static/projects/{PROJECT_ID}/{run_id}/{filename}"


def _safe_run_id(value: str) -> str:
    safe = re.sub(r"[^a-zA-Z0-9_-]+", "-", value).strip("-")
    return safe or uuid.uuid4().hex


def _clean_label(value: str) -> str:
    return re.sub(r"\s+", " ", value.strip())


def _slug(value: str) -> str:
    slug = re.sub(r"[^a-zA-Z0-9]+", "_", value.lower()).strip("_")
    return slug or "crop"
