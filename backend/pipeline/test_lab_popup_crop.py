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
from pipeline.asset_vault import save_vault_image
from pipeline.character_assets import process_character_asset_bundle

PROJECT_ID = "test-lab-popup-crops"


class PopupCropResultCrop(BaseModel):
    role: str
    label: str
    url: str
    raw_url: str
    box: list[int]
    trim_box: list[int]
    warnings: list[str] = Field(default_factory=list)


class PopupCropPreviewResult(BaseModel):
    run_id: str
    anchor_prompt_used: str
    item_prompt_used: str
    anchor_source_url: str
    sheet_url: str
    crops: list[PopupCropResultCrop] = Field(default_factory=list)


class PopupCropAnchorResult(BaseModel):
    run_id: str
    anchor_prompt_used: str
    anchor_source_url: str
    anchor_cutout_url: str | None = None
    warnings: list[str] = Field(default_factory=list)


class PopupCropSheetResult(BaseModel):
    run_id: str
    item_prompt_used: str
    sheet_url: str


class PopupCropChromaResult(BaseModel):
    run_id: str
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
    anchor = generate_popup_crop_anchor(anchor_prompt=anchor_prompt, run_id=safe_run_id)
    sheet = generate_popup_crop_item_sheet(item_prompt=item_prompt, items=cleaned_items, run_id=safe_run_id)
    crops = [
        *chroma_popup_crop_anchor(run_id=safe_run_id).crops,
        *chroma_popup_crop_item_sheet(run_id=safe_run_id, items=cleaned_items).crops,
    ]
    return PopupCropPreviewResult(
        run_id=safe_run_id,
        anchor_prompt_used=anchor.anchor_prompt_used,
        item_prompt_used=sheet.item_prompt_used,
        anchor_source_url=anchor.anchor_source_url,
        sheet_url=sheet.sheet_url,
        crops=crops,
    )


def generate_popup_crop_anchor(
    *,
    anchor_prompt: str,
    run_id: str | None = None,
) -> PopupCropAnchorResult:
    safe_run_id = _safe_run_id(run_id or uuid.uuid4().hex)
    output_dir = _output_dir(safe_run_id)

    composed_anchor_prompt = _compose_anchor_prompt(anchor_prompt)
    generated_anchor_path = Path(
        generate_image(composed_anchor_prompt, width=IMAGE_WIDTH, height=IMAGE_HEIGHT, script_id=PROJECT_ID)
    )
    anchor_source_path = output_dir / "anchor_source.png"
    if generated_anchor_path.resolve() != anchor_source_path.resolve():
        shutil.copyfile(generated_anchor_path, anchor_source_path)
    crop = _process_anchor_source(anchor_source_path, output_dir, save_to_vault=False)

    return PopupCropAnchorResult(
        run_id=safe_run_id,
        anchor_prompt_used=composed_anchor_prompt,
        anchor_source_url=_web_url(safe_run_id, "anchor_source.png"),
        anchor_cutout_url=crop.url,
        warnings=crop.warnings,
    )


def chroma_popup_crop_anchor(*, run_id: str) -> PopupCropChromaResult:
    safe_run_id = _safe_run_id(run_id)
    output_dir = _output_dir(safe_run_id, create=False)
    crop = _process_anchor_source(output_dir / "anchor_source.png", output_dir)
    return PopupCropChromaResult(run_id=safe_run_id, crops=[crop])


def generate_popup_crop_item_sheet(
    *,
    item_prompt: str,
    items: list[str],
    run_id: str | None = None,
) -> PopupCropSheetResult:
    cleaned_items = [_clean_label(item) for item in items if _clean_label(item)]
    safe_run_id = _safe_run_id(run_id or uuid.uuid4().hex)
    output_dir = _output_dir(safe_run_id)

    composed_item_prompt = _compose_item_sheet_prompt(item_prompt, cleaned_items)
    generated_sheet_path = Path(
        generate_image(composed_item_prompt, width=IMAGE_WIDTH, height=IMAGE_HEIGHT, script_id=PROJECT_ID)
    )

    sheet_path = output_dir / "item_sheet.png"
    if generated_sheet_path.resolve() != sheet_path.resolve():
        shutil.copyfile(generated_sheet_path, sheet_path)

    return PopupCropSheetResult(
        run_id=safe_run_id,
        item_prompt_used=composed_item_prompt,
        sheet_url=_web_url(safe_run_id, "item_sheet.png"),
    )


def chroma_popup_crop_item_sheet(*, run_id: str, items: list[str]) -> PopupCropChromaResult:
    cleaned_items = [_clean_label(item) for item in items if _clean_label(item)]
    safe_run_id = _safe_run_id(run_id)
    output_dir = _output_dir(safe_run_id, create=False)
    return PopupCropChromaResult(
        run_id=safe_run_id,
        crops=_crop_item_sheet(output_dir / "item_sheet.png", output_dir, cleaned_items),
    )


def _output_dir(run_id: str, *, create: bool = True) -> Path:
    output_dir = DATA_DIR / "projects" / PROJECT_ID / run_id
    if create:
        output_dir.mkdir(parents=True, exist_ok=True)
    return output_dir


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
            "You are generating a contact sheet for automatic programmatic cropping.",
            "",
            f"Generate exactly {len(items)} cartoon item(s) arranged in a single row,",
            "evenly spaced, left to right in this exact order:",
            *item_lines,
            "",
            "Layout rules:",
            "- Each item occupies an equal-width vertical slot",
            "- Items are horizontally centered within their slot",
            "- Items fill no more than 70% of their slot width, leaving clear margins on both sides",
            "- All items are the same visual scale relative to their slot",
            "- Single row only; do not stack or wrap items",
            "",
            "Background:",
            "- Solid flat chroma key background across the entire image",
            "- Use bright green (#00FF00) unless any item contains green, in which case use bright magenta (#FF00FF)",
            "- The chroma color must not appear anywhere within any item",
            "",
            "Item rendering:",
            "- Each item is fully self-contained with no overlap into adjacent slots",
            "- Crisp closed silhouettes with no soft glow, feathering, or semi-transparent color bleed into the chroma background",
            "- No drop shadows, glows, or effects that extend outside the item boundary",
            "- No frames, borders, labels, captions, speech bubbles, arrows, or text",
            "- No background scenes, environments, or context behind items",
            "- No main character or human figures",
            "",
            "Style:",
            prompt.strip(),
        ]
    ).strip()


def _process_anchor_source(
    anchor_path: Path,
    output_dir: Path,
    *,
    save_to_vault: bool = True,
) -> PopupCropResultCrop:
    result = process_character_asset_bundle(
        anchor_path,
        output_dir,
        reference_filename="anchor_source.png",
        cutout_filename="anchor_cutout.png",
        metadata_filename="anchor_metadata.json",
    )
    if save_to_vault:
        save_vault_image(kind="character", label="Anchor character", source_path=result.cutout_path)

    with Image.open(result.reference_path) as image:
        width, height = image.size

    return PopupCropResultCrop(
        role="anchor",
        label="Anchor character",
        url=_web_url(output_dir.name, "anchor_cutout.png"),
        raw_url=_web_url(output_dir.name, "anchor_source.png"),
        box=[0, 0, width, height],
        trim_box=result.trim_box,
        warnings=result.warnings,
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
            output_path = output_dir / filename
            trim_box = _save_keyed_trimmed_cutout(crop, output_path)
            save_vault_image(kind="item", label=label, source_path=output_path)
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
