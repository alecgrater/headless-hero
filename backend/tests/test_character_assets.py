from pathlib import Path

import pytest
from PIL import Image


def _save_chroma_character(path: Path) -> None:
    image = Image.new("RGB", (200, 200), (0, 255, 0))
    image.paste((220, 40, 40), (70, 50, 130, 160))
    image.save(path)


def test_process_character_asset_bundle_preserves_reference_and_writes_cutout(tmp_path):
    from pipeline.character_assets import process_character_asset_bundle

    source = tmp_path / "source.png"
    bundle_dir = tmp_path / "bundle"
    _save_chroma_character(source)

    result = process_character_asset_bundle(
        source_path=source,
        output_dir=bundle_dir,
        reference_filename="reference.png",
        cutout_filename="cutout.png",
        prompt_fingerprint="prompt-a",
    )

    assert result.reference_path == bundle_dir / "reference.png"
    assert result.cutout_path == bundle_dir / "cutout.png"
    assert result.metadata_path == bundle_dir / "metadata.json"
    assert result.reference_path.exists()
    assert result.cutout_path.exists()
    assert result.trim_box[0] < 70
    assert result.trim_box[1] < 50
    assert result.trim_box[2] > 130
    assert result.trim_box[3] > 160
    assert result.warnings == []

    with Image.open(result.cutout_path) as cutout:
        assert cutout.mode == "RGBA"
        assert cutout.size[0] < 120
        assert cutout.size[1] < 160
        assert cutout.getpixel((0, 0))[3] == 0


def test_process_character_asset_bundle_records_metadata(tmp_path):
    import json

    from pipeline.character_assets import process_character_asset_bundle

    source = tmp_path / "source.png"
    _save_chroma_character(source)

    result = process_character_asset_bundle(
        source_path=source,
        output_dir=tmp_path / "bundle",
        reference_filename="reference.png",
        cutout_filename="cutout.png",
        prompt_fingerprint="prompt-a",
    )

    metadata = json.loads(result.metadata_path.read_text(encoding="utf-8"))
    assert metadata["version"] == 1
    assert metadata["source_path"] == "reference.png"
    assert metadata["cutout_path"] == "cutout.png"
    assert metadata["prompt_fingerprint"] == "prompt-a"
    assert metadata["background_removal_method"] == "chroma_corner_sample"
    assert metadata["trim_box"] == result.trim_box
    assert len(metadata["source_sha256"]) == 64
    assert len(metadata["cutout_sha256"]) == 64
    assert metadata["warnings"] == []


def test_process_character_asset_bundle_warns_when_alpha_stays_full_frame(tmp_path):
    from pipeline.character_assets import process_character_asset_bundle

    source = tmp_path / "solid.png"
    Image.new("RGB", (160, 120), (255, 0, 0)).save(source)

    result = process_character_asset_bundle(
        source_path=source,
        output_dir=tmp_path / "bundle",
        reference_filename="reference.png",
        cutout_filename="cutout.png",
    )

    assert "cutout_bounds_touch_image_edge" in result.warnings
    assert "cutout_visible_area_large" in result.warnings


def test_process_character_asset_bundle_rejects_missing_source(tmp_path):
    from pipeline.character_assets import process_character_asset_bundle

    with pytest.raises(FileNotFoundError, match="character source image not found"):
        process_character_asset_bundle(
            source_path=tmp_path / "missing.png",
            output_dir=tmp_path / "bundle",
            reference_filename="reference.png",
            cutout_filename="cutout.png",
        )


def test_process_character_asset_bundle_rejects_output_path_collisions(tmp_path):
    from pipeline.character_assets import process_character_asset_bundle

    source = tmp_path / "source.png"
    _save_chroma_character(source)

    with pytest.raises(ValueError, match="character asset output paths must be distinct"):
        process_character_asset_bundle(
            source_path=source,
            output_dir=tmp_path / "bundle",
            reference_filename="character.png",
            cutout_filename="character.png",
        )
