"""File-backed reusable image vault helpers."""

from __future__ import annotations

import re
import shutil
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Literal

from pydantic import BaseModel

from config import DATA_DIR

VaultKind = Literal["character", "item"]

_VAULT_PROJECT_ID = "asset-vault"
_KIND_DIRS: dict[VaultKind, str] = {
    "character": "characters",
    "item": "items",
}


class VaultImage(BaseModel):
    kind: VaultKind
    name: str
    filename: str
    url: str
    created_at: str


def save_vault_image(*, kind: VaultKind, label: str, source_path: Path) -> VaultImage:
    """Copy a cleaned reusable PNG cutout into the vault with metadata in its filename."""

    safe_label = _slug(label)
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    suffix = uuid.uuid4().hex[:6]
    filename = f"{kind}_{safe_label}_{timestamp}_{suffix}.png"
    output_dir = _vault_dir(kind)
    output_dir.mkdir(parents=True, exist_ok=True)
    output_path = output_dir / filename
    shutil.copyfile(source_path, output_path)
    return _vault_image_from_path(kind, output_path)


def list_vault_images(*, kind: VaultKind | None = None) -> list[VaultImage]:
    kinds: list[VaultKind] = [kind] if kind else ["character", "item"]
    images: list[VaultImage] = []
    for image_kind in kinds:
        for path in _vault_dir(image_kind).glob("*.png"):
            images.append(_vault_image_from_path(image_kind, path))
    return sorted(images, key=lambda image: image.created_at, reverse=True)


def _vault_dir(kind: VaultKind) -> Path:
    return DATA_DIR / "projects" / _VAULT_PROJECT_ID / _KIND_DIRS[kind]


def _vault_image_from_path(kind: VaultKind, path: Path) -> VaultImage:
    created_at = datetime.fromtimestamp(path.stat().st_mtime, tz=timezone.utc).isoformat()
    return VaultImage(
        kind=kind,
        name=_display_name(kind, path.stem),
        filename=path.name,
        url=f"/static/projects/{_VAULT_PROJECT_ID}/{_KIND_DIRS[kind]}/{path.name}",
        created_at=created_at,
    )


def _display_name(kind: VaultKind, stem: str) -> str:
    prefix = f"{kind}_"
    without_prefix = stem[len(prefix):] if stem.startswith(prefix) else stem
    without_suffix = re.sub(r"_\d{8}_\d{6}_[a-f0-9]{6}$", "", without_prefix)
    return without_suffix.replace("_", " ") or kind


def _slug(value: str) -> str:
    slug = re.sub(r"[^a-zA-Z0-9]+", "_", value.lower()).strip("_")
    return slug[:80] if slug else "asset"
