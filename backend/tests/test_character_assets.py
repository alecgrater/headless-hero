from pathlib import Path

import pytest
from PIL import Image


def _save_chroma_character(path: Path, color: tuple[int, int, int] = (220, 40, 40)) -> None:
    image = Image.new("RGB", (200, 200), (0, 255, 0))
    image.paste(color, (70, 50, 130, 160))
    image.save(path)


def _opaque_colors(path: Path) -> set[tuple[int, int, int]]:
    with Image.open(path) as image:
        data = image.convert("RGBA").tobytes()
    return {
        (data[index], data[index + 1], data[index + 2])
        for index in range(0, len(data), 4)
        if data[index + 3] > 0
    }


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


def test_process_character_asset_bundle_preserves_enclosed_character_details_near_background_color(tmp_path):
    from pipeline.character_assets import process_character_asset_bundle

    background = (238, 236, 232)
    source = tmp_path / "source.png"
    image = Image.new("RGB", (160, 160), background)
    pixels = image.load()

    for y in range(40, 121):
        for x in range(40, 121):
            if x in (40, 120) or y in (40, 120):
                pixels[x, y] = (12, 12, 12)
            else:
                pixels[x, y] = (245, 181, 132)

    pixels[80, 80] = background
    image.save(source)

    result = process_character_asset_bundle(
        source_path=source,
        output_dir=tmp_path / "bundle",
        reference_filename="reference.png",
        cutout_filename="cutout.png",
    )

    interior_x = 80 - result.trim_box[0]
    interior_y = 80 - result.trim_box[1]
    with Image.open(result.cutout_path) as cutout:
        assert cutout.getpixel((interior_x, interior_y))[3] == 255


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
    assert metadata["version"] == 2
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


def test_select_character_reference_variant_replaces_current_project_cutout(
    tmp_path,
    monkeypatch,
):
    from pipeline import main_character
    from pipeline.character_assets import process_character_asset_bundle

    monkeypatch.setattr(main_character, "DATA_DIR", tmp_path)
    script_id = "script-a"
    variants_dir = tmp_path / "projects" / script_id / "character" / "references"
    variants_dir.mkdir(parents=True)

    first_color = (220, 40, 40)
    second_color = (40, 80, 220)
    first_variant = variants_dir / "1.png"
    second_variant = variants_dir / "2.png"
    _save_chroma_character(first_variant, first_color)
    _save_chroma_character(second_variant, second_color)

    for idx in (1, 2):
        process_character_asset_bundle(
            source_path=variants_dir / f"{idx}.png",
            output_dir=variants_dir,
            reference_filename=f"{idx}.png",
            cutout_filename=f"{idx}.cutout.png",
            metadata_filename=f"{idx}.metadata.json",
        )

    main_character.select_character_reference_variant(script_id=script_id, idx=1)
    assert first_color in _opaque_colors(tmp_path / "projects" / script_id / "character" / "cutout.png")

    main_character.select_character_reference_variant(script_id=script_id, idx=2)

    active_colors = _opaque_colors(tmp_path / "projects" / script_id / "character" / "cutout.png")
    assert second_color in active_colors
    assert first_color not in active_colors


def test_select_global_character_reference_variant_replaces_current_cutout(
    tmp_path,
    monkeypatch,
):
    from pipeline import main_character
    from pipeline.character_assets import process_character_asset_bundle

    monkeypatch.setattr(main_character, "DATA_DIR", tmp_path)
    variants_dir = tmp_path / "character" / "main" / "references"
    variants_dir.mkdir(parents=True)

    first_color = (220, 40, 40)
    second_color = (40, 80, 220)
    _save_chroma_character(variants_dir / "1.png", first_color)
    _save_chroma_character(variants_dir / "2.png", second_color)

    for idx in (1, 2):
        process_character_asset_bundle(
            source_path=variants_dir / f"{idx}.png",
            output_dir=variants_dir,
            reference_filename=f"{idx}.png",
            cutout_filename=f"{idx}.cutout.png",
            metadata_filename=f"{idx}.metadata.json",
        )

    main_character.select_global_character_reference_variant(idx=1)
    assert first_color in _opaque_colors(tmp_path / "character" / "main" / "cutout.png")

    main_character.select_global_character_reference_variant(idx=2)

    active_colors = _opaque_colors(tmp_path / "character" / "main" / "cutout.png")
    assert second_color in active_colors
    assert first_color not in active_colors
