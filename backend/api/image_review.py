"""Project image review APIs for non-destructive render-source edits."""

from __future__ import annotations

import base64
import binascii
import io
import json
import logging
import re
from pathlib import Path
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException
from PIL import Image
from pydantic import BaseModel, Field
from sqlmodel import Session

from config import DATA_DIR
from database import get_session
from models.script import Script, ScriptContent, Scene, VisualLayer
from pipeline.render_cache import mark_render_inputs_changed

router = APIRouter(prefix="/api/image-review", tags=["image-review"])
logger = logging.getLogger(__name__)

IMAGE_REVIEW_METADATA_KEY = "image_review"


class ImageReviewAsset(BaseModel):
    asset_id: str
    scene_id: str
    segment_index: int
    segment_name: str
    scene_index: int
    scene_label: str
    asset_kind: Literal["scene", "frame", "layer"]
    current_url: str
    original_url: str
    reviewed: bool = False
    width: int | None = None
    height: int | None = None
    layer_id: str | None = None
    frame_index: int | None = None


class ImageReviewListResponse(BaseModel):
    script_id: str
    assets: list[ImageReviewAsset]


class ImageReviewAssetDataResponse(BaseModel):
    script_id: str
    asset_id: str
    content_type: str
    byte_count: int
    data_url: str


class ImageReviewEditRequest(BaseModel):
    data_url: str = Field(min_length=1)


class ImageReviewUpdateResponse(BaseModel):
    script_id: str
    asset: ImageReviewAsset
    assets: list[ImageReviewAsset]
    script: ScriptContent


class AssetRef(BaseModel):
    asset_id: str
    scene: Scene
    segment_index: int
    segment_name: str
    scene_index: int
    asset_kind: Literal["scene", "frame", "layer"]
    current_url: str
    frame_index: int | None = None
    layer_index: int | None = None


def _scene_label(scene: Scene) -> str:
    text = (scene.narration or scene.visual_prompt or scene.id).strip()
    return text[:90] + ("..." if len(text) > 90 else "")


def _safe_asset_folder(asset_id: str) -> str:
    return re.sub(r"[^A-Za-z0-9_.-]+", "_", asset_id).strip("_") or "asset"


def _metadata_assets(metadata: dict | None) -> dict:
    if not isinstance(metadata, dict):
        return {}
    review = metadata.get(IMAGE_REVIEW_METADATA_KEY)
    if not isinstance(review, dict):
        return {}
    assets = review.get("assets")
    return assets if isinstance(assets, dict) else {}


def _asset_metadata(metadata: dict | None, asset_id: str) -> dict:
    assets = _metadata_assets(metadata)
    value = assets.get(asset_id)
    return value if isinstance(value, dict) else {}


def _set_asset_metadata(
    metadata: dict | None,
    asset_id: str,
    *,
    original_url: str,
    current_url: str,
    reviewed: bool,
) -> dict:
    next_metadata = dict(metadata or {})
    review = dict(next_metadata.get(IMAGE_REVIEW_METADATA_KEY) or {})
    assets = dict(review.get("assets") or {})
    assets[asset_id] = {
        "original_url": original_url,
        "current_url": current_url,
        "reviewed": reviewed,
    }
    review["assets"] = assets
    next_metadata[IMAGE_REVIEW_METADATA_KEY] = review
    return next_metadata


def _static_project_path(url: str) -> Path | None:
    prefix = "/static/projects/"
    if not url.startswith(prefix):
        return None
    relative = url.removeprefix(prefix).lstrip("/")
    path = (DATA_DIR / "projects" / relative).resolve()
    projects_root = (DATA_DIR / "projects").resolve()
    if path != projects_root and projects_root not in path.parents:
        return None
    return path


def _image_dimensions(url: str) -> tuple[int | None, int | None]:
    path = _static_project_path(url)
    if path is None or not path.exists():
        return None, None
    try:
        with Image.open(path) as image:
            return image.size
    except Exception:
        return None, None


def _asset_from_ref(ref: AssetRef) -> ImageReviewAsset:
    if ref.asset_kind == "layer" and ref.layer_index is not None:
        metadata = ref.scene.visual_layers[ref.layer_index].visual_source_metadata
    else:
        metadata = ref.scene.visual_source_metadata
    review = _asset_metadata(metadata, ref.asset_id)
    original_url = str(review.get("original_url") or ref.current_url)
    reviewed = bool(review.get("reviewed")) and ref.current_url != original_url
    width, height = _image_dimensions(ref.current_url)
    layer_id = None
    if ref.asset_kind == "layer" and ref.layer_index is not None:
        layer_id = ref.scene.visual_layers[ref.layer_index].id or str(ref.layer_index)
    return ImageReviewAsset(
        asset_id=ref.asset_id,
        scene_id=ref.scene.id,
        segment_index=ref.segment_index,
        segment_name=ref.segment_name,
        scene_index=ref.scene_index,
        scene_label=_scene_label(ref.scene),
        asset_kind=ref.asset_kind,
        current_url=ref.current_url,
        original_url=original_url,
        reviewed=reviewed,
        width=width,
        height=height,
        layer_id=layer_id,
        frame_index=ref.frame_index,
    )


def _collect_refs(content: ScriptContent) -> list[AssetRef]:
    refs: list[AssetRef] = []
    for segment_index, segment in enumerate(content.segments):
        for scene_index, scene in enumerate(segment.scenes):
            if scene.image_url and not scene.frame_urls:
                refs.append(
                    AssetRef(
                        asset_id=f"scene:{scene.id}:image",
                        scene=scene,
                        segment_index=segment_index,
                        segment_name=segment.name,
                        scene_index=scene_index,
                        asset_kind="scene",
                        current_url=scene.image_url,
                    )
                )
            for frame_index, frame_url in enumerate(scene.frame_urls or []):
                if not frame_url:
                    continue
                refs.append(
                    AssetRef(
                        asset_id=f"scene:{scene.id}:frame:{frame_index}",
                        scene=scene,
                        segment_index=segment_index,
                        segment_name=segment.name,
                        scene_index=scene_index,
                        asset_kind="frame",
                        current_url=frame_url,
                        frame_index=frame_index,
                    )
                )
            for layer_index, layer in enumerate(scene.visual_layers or []):
                if not layer.image_url:
                    continue
                layer_key = layer.id or str(layer_index)
                refs.append(
                    AssetRef(
                        asset_id=f"scene:{scene.id}:layer:{layer_key}",
                        scene=scene,
                        segment_index=segment_index,
                        segment_name=segment.name,
                        scene_index=scene_index,
                        asset_kind="layer",
                        current_url=layer.image_url,
                        layer_index=layer_index,
                    )
                )
    return refs


def _find_ref(content: ScriptContent, asset_id: str) -> AssetRef | None:
    return next((ref for ref in _collect_refs(content) if ref.asset_id == asset_id), None)


def _load_script(session: Session, script_id: str) -> tuple[Script, ScriptContent]:
    record = session.get(Script, script_id)
    if record is None:
        raise HTTPException(status_code=404, detail="Script not found")
    return record, ScriptContent.model_validate(json.loads(record.script_json))


def _decode_png_data_url(data_url: str) -> bytes:
    prefix = "data:image/png;base64,"
    if not data_url.startswith(prefix):
        raise HTTPException(status_code=422, detail="Img Review edits must be PNG data URLs.")
    try:
        raw = base64.b64decode(data_url.removeprefix(prefix), validate=True)
    except (binascii.Error, ValueError) as exc:
        raise HTTPException(status_code=422, detail="Img Review edit data is not valid base64.") from exc
    try:
        with Image.open(io.BytesIO(raw)) as image:
            if image.format != "PNG":
                raise HTTPException(status_code=422, detail="Img Review edits must be PNG images.")
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=422, detail="Img Review edit data is not a readable PNG.") from exc
    return raw


def _image_content_type(path: Path) -> str:
    suffix = path.suffix.lower()
    if suffix in {".jpg", ".jpeg"}:
        return "image/jpeg"
    if suffix == ".webp":
        return "image/webp"
    if suffix == ".gif":
        return "image/gif"
    return "image/png"


def _read_asset_data_url(script_id: str, asset_id: str, url: str) -> ImageReviewAssetDataResponse:
    path = _static_project_path(url)
    if path is None:
        logger.warning(
            "Img Review asset %s for script %s uses unsupported image URL: %s",
            asset_id,
            script_id,
            url,
        )
        raise HTTPException(status_code=422, detail="Image Review asset URL is not a local project image")
    if not path.exists() or not path.is_file():
        logger.warning(
            "Img Review asset %s for script %s is missing at %s for URL %s",
            asset_id,
            script_id,
            path,
            url,
        )
        raise HTTPException(status_code=404, detail="Image Review asset file not found")

    try:
        raw = path.read_bytes()
        with Image.open(io.BytesIO(raw)) as image:
            image.verify()
    except HTTPException:
        raise
    except Exception as exc:
        logger.exception(
            "Img Review asset %s for script %s could not be read or decoded from %s",
            asset_id,
            script_id,
            path,
        )
        raise HTTPException(status_code=422, detail="Image Review asset file is not a readable image") from exc

    content_type = _image_content_type(path)
    return ImageReviewAssetDataResponse(
        script_id=script_id,
        asset_id=asset_id,
        content_type=content_type,
        byte_count=len(raw),
        data_url=f"data:{content_type};base64,{base64.b64encode(raw).decode('ascii')}",
    )


def _next_edit_path(script_id: str, asset_id: str) -> tuple[Path, str]:
    folder = DATA_DIR / "projects" / script_id / "image_review" / _safe_asset_folder(asset_id)
    folder.mkdir(parents=True, exist_ok=True)
    existing = sorted(folder.glob("edit_*.png"))
    version = len(existing) + 1
    path = folder / f"edit_{version}.png"
    while path.exists():
        version += 1
        path = folder / f"edit_{version}.png"
    url = f"/static/projects/{script_id}/image_review/{folder.name}/{path.name}"
    return path, url


def _apply_ref_url(ref: AssetRef, new_url: str, *, original_url: str, reviewed: bool) -> None:
    if ref.asset_kind == "scene":
        ref.scene.image_url = new_url
        ref.scene.visual_source_metadata = _set_asset_metadata(
            ref.scene.visual_source_metadata,
            ref.asset_id,
            original_url=original_url,
            current_url=new_url,
            reviewed=reviewed,
        )
        return

    if ref.asset_kind == "frame":
        if ref.frame_index is None or ref.frame_index >= len(ref.scene.frame_urls):
            raise HTTPException(status_code=404, detail="Image Review asset not found")
        ref.scene.frame_urls[ref.frame_index] = new_url
        if ref.frame_index == 0 or ref.scene.image_url == ref.current_url:
            ref.scene.image_url = new_url
        ref.scene.visual_source_metadata = _set_asset_metadata(
            ref.scene.visual_source_metadata,
            ref.asset_id,
            original_url=original_url,
            current_url=new_url,
            reviewed=reviewed,
        )
        return

    if ref.layer_index is None or ref.layer_index >= len(ref.scene.visual_layers):
        raise HTTPException(status_code=404, detail="Image Review asset not found")
    layer = ref.scene.visual_layers[ref.layer_index]
    layer.image_url = new_url
    layer.visual_source_metadata = _set_asset_metadata(
        layer.visual_source_metadata,
        ref.asset_id,
        original_url=original_url,
        current_url=new_url,
        reviewed=reviewed,
    )


def _persist(session: Session, record: Script, content: ScriptContent) -> None:
    record.script_json = content.model_dump_json()
    session.add(record)
    session.commit()
    mark_render_inputs_changed(record.id)


@router.get("/{script_id}", response_model=ImageReviewListResponse)
def list_image_review_assets(script_id: str, session: Session = Depends(get_session)):
    _record, content = _load_script(session, script_id)
    return ImageReviewListResponse(
        script_id=script_id,
        assets=[_asset_from_ref(ref) for ref in _collect_refs(content)],
    )


@router.get("/{script_id}/assets/{asset_id}/data", response_model=ImageReviewAssetDataResponse)
def get_image_review_asset_data(
    script_id: str,
    asset_id: str,
    session: Session = Depends(get_session),
):
    _record, content = _load_script(session, script_id)
    ref = _find_ref(content, asset_id)
    if ref is None:
        raise HTTPException(status_code=404, detail="Image Review asset not found")
    return _read_asset_data_url(script_id, asset_id, ref.current_url)


@router.post("/{script_id}/assets/{asset_id}/edit", response_model=ImageReviewUpdateResponse)
def save_image_review_edit(
    script_id: str,
    asset_id: str,
    body: ImageReviewEditRequest,
    session: Session = Depends(get_session),
):
    png_bytes = _decode_png_data_url(body.data_url)
    record, content = _load_script(session, script_id)
    ref = _find_ref(content, asset_id)
    if ref is None:
        raise HTTPException(status_code=404, detail="Image Review asset not found")

    existing_asset = _asset_from_ref(ref)
    path, edited_url = _next_edit_path(script_id, asset_id)
    path.write_bytes(png_bytes)
    _apply_ref_url(ref, edited_url, original_url=existing_asset.original_url, reviewed=True)
    _persist(session, record, content)

    refreshed_ref = _find_ref(content, asset_id)
    if refreshed_ref is None:
        raise HTTPException(status_code=404, detail="Image Review asset not found after save")
    return ImageReviewUpdateResponse(
        script_id=script_id,
        asset=_asset_from_ref(refreshed_ref),
        assets=[_asset_from_ref(item) for item in _collect_refs(content)],
        script=content,
    )


@router.post("/{script_id}/assets/{asset_id}/reset", response_model=ImageReviewUpdateResponse)
def reset_image_review_asset(
    script_id: str,
    asset_id: str,
    session: Session = Depends(get_session),
):
    record, content = _load_script(session, script_id)
    ref = _find_ref(content, asset_id)
    if ref is None:
        raise HTTPException(status_code=404, detail="Image Review asset not found")

    existing_asset = _asset_from_ref(ref)
    _apply_ref_url(ref, existing_asset.original_url, original_url=existing_asset.original_url, reviewed=False)
    _persist(session, record, content)

    refreshed_ref = _find_ref(content, asset_id)
    if refreshed_ref is None:
        raise HTTPException(status_code=404, detail="Image Review asset not found after reset")
    return ImageReviewUpdateResponse(
        script_id=script_id,
        asset=_asset_from_ref(refreshed_ref),
        assets=[_asset_from_ref(item) for item in _collect_refs(content)],
        script=content,
    )
