"""Popup crop lab helpers for contact-sheet prompt iteration."""

from __future__ import annotations

import math
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
    box: list[int]


class PopupCropPreviewResult(BaseModel):
    run_id: str
    prompt_used: str
    sheet_url: str
    crops: list[PopupCropResultCrop] = Field(default_factory=list)


def generate_popup_crop_preview(
    *,
    prompt: str,
    items: list[str],
    run_id: str | None = None,
) -> PopupCropPreviewResult:
    """Generate one contact sheet and crop row-major slots into preview assets."""

    cleaned_items = [_clean_label(item) for item in items if _clean_label(item)]
    safe_run_id = _safe_run_id(run_id or uuid.uuid4().hex)
    output_dir = DATA_DIR / "projects" / PROJECT_ID / safe_run_id
    output_dir.mkdir(parents=True, exist_ok=True)

    labels = ["Anchor character", *cleaned_items]
    composed_prompt = _compose_contact_sheet_prompt(prompt, cleaned_items)
    generated_path = Path(generate_image(composed_prompt, width=IMAGE_WIDTH, height=IMAGE_HEIGHT, script_id=PROJECT_ID))

    sheet_path = output_dir / "contact_sheet.png"
    if generated_path.resolve() != sheet_path.resolve():
        shutil.copyfile(generated_path, sheet_path)

    crops = _crop_contact_sheet(sheet_path, output_dir, labels)
    return PopupCropPreviewResult(
        run_id=safe_run_id,
        prompt_used=composed_prompt,
        sheet_url=_web_url(safe_run_id, "contact_sheet.png"),
        crops=crops,
    )


def _compose_contact_sheet_prompt(prompt: str, items: list[str]) -> str:
    total_slots = 1 + len(items)
    rows = math.ceil(total_slots / 2)
    slot_lines = ["slot 1: the single anchored main character or center-focus subject"]
    for index, item in enumerate(items, start=2):
        slot_lines.append(f"slot {index}: isolated cutout of {item}")

    return "\n".join(
        [
            "Create a clean Headless Hero cartoon contact sheet for automatic cropping.",
            f"Use exactly 2 columns and {rows} row(s), with thick empty gutters between every slot.",
            "Each slot must contain one isolated subject only, centered inside its own crop-safe area.",
            "Do not draw frames, labels, captions, speech bubbles, text, arrows, or full background scenes.",
            "Use a plain flat background that contrasts with the subjects.",
            "Leave generous empty margin around each subject so fixed rectangular crops do not clip it.",
            *slot_lines,
            "",
            "Scene direction:",
            prompt.strip(),
        ]
    ).strip()


def _crop_contact_sheet(sheet_path: Path, output_dir: Path, labels: list[str]) -> list[PopupCropResultCrop]:
    with Image.open(sheet_path) as image:
        source = image.convert("RGBA")
        total = len(labels)
        cols = 2 if total > 1 else 1
        rows = math.ceil(total / cols)
        cell_width = source.width // cols
        cell_height = source.height // rows
        run_id = output_dir.name
        crops: list[PopupCropResultCrop] = []
        for index, label in enumerate(labels):
            row = index // cols
            col = index % cols
            left = col * cell_width
            top = row * cell_height
            right = source.width if col == cols - 1 else (col + 1) * cell_width
            bottom = source.height if row == rows - 1 else (row + 1) * cell_height
            crop = source.crop((left, top, right, bottom))
            filename = f"crop_{index + 1:02d}_{_slug(label)}.png"
            crop.save(output_dir / filename)
            crops.append(
                PopupCropResultCrop(
                    role="anchor" if index == 0 else "item",
                    label=label,
                    url=_web_url(run_id, filename),
                    box=[left, top, right, bottom],
                )
            )
    return crops


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
