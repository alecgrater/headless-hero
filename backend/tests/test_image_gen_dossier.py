"""Tests for the dossier visual-mode asset generation pipeline.

Mocks Gemini calls (`generate_image`) so we can assert anchor + contact-sheet calls
happen for the anchor layout, contact-sheet only for the network layout, and that
each cropped cutout is written to the asset vault.
"""

from __future__ import annotations

import importlib
from pathlib import Path
from unittest.mock import MagicMock, patch

from PIL import Image


def _reset_data_dir(monkeypatch, tmp_path):
    monkeypatch.setenv("HH_DATA_DIR", str(tmp_path))
    import config
    importlib.reload(config)
    import pipeline.asset_vault as vault_mod
    importlib.reload(vault_mod)
    import pipeline.image_gen as ig_mod
    importlib.reload(ig_mod)
    return ig_mod, vault_mod


def _write_chroma_image(path: Path, *, width: int = 600, height: int = 200, color=(0, 255, 0)) -> None:
    image = Image.new("RGB", (width, height), color)
    path.parent.mkdir(parents=True, exist_ok=True)
    image.save(path)


def _layer(layer_id: str, label: str, prompt: str = "thing", placement: str = "top-left") -> dict:
    return {
        "id": layer_id,
        "type": "image",
        "asset_kind": "cutout",
        "image_url": "",
        "prompt": prompt,
        "label": label,
        "placement": placement,
        "enter_at_seconds": 0.5,
        "animation": "pop_in",
    }


def test_generate_dossier_cutouts_anchor_layout_calls_anchor_and_sheet(tmp_path, monkeypatch):
    ig_mod, _vault_mod = _reset_data_dir(monkeypatch, tmp_path)

    anchor_call = tmp_path / "fake_anchor.png"
    sheet_call = tmp_path / "fake_sheet.png"
    _write_chroma_image(anchor_call, width=400, height=400)
    _write_chroma_image(sheet_call, width=900, height=300)

    generated_paths = iter([str(anchor_call), str(sheet_call)])
    generate_image_mock = MagicMock(side_effect=lambda *a, **k: next(generated_paths))
    save_vault_mock = MagicMock()

    layers = [
        _layer("scene1_anchor", "SUSPECT", "anchor character", "center"),
        _layer("scene1_evidence_1", "WEAPON", "knife", "top-left"),
        _layer("scene1_evidence_2", "NOTE", "torn note", "top-right"),
        _layer("scene1_evidence_3", "WITNESS", "witness photo", "bottom-center"),
    ]

    with patch.object(ig_mod, "generate_image", generate_image_mock), \
         patch.object(ig_mod, "save_vault_image", save_vault_mock), \
         patch.object(ig_mod, "process_character_asset_bundle") as bundle_mock:
        # process_character_asset_bundle is responsible for cutout + metadata; fake the result.
        def fake_bundle(source_path, output_dir, *, reference_filename, cutout_filename, metadata_filename):
            # Pretend to write a cutout file; satisfy save_vault_image arg type.
            cutout = Path(output_dir) / cutout_filename
            cutout.write_bytes(b"cutout")
            result = MagicMock()
            result.cutout_path = cutout
            return result
        bundle_mock.side_effect = fake_bundle

        processed = ig_mod.generate_dossier_cutouts(
            scene_id="scene1",
            layers=layers,
            script_id="proj1",
            scene_prompt="A grim case file",
            dossier_layout="anchor",
            contains_person=True,
        )

    # Two Gemini calls: anchor + evidence sheet.
    assert generate_image_mock.call_count == 2
    # Vault: 1 anchor + 3 evidence cutouts.
    assert save_vault_mock.call_count == 4
    kinds = {call.kwargs["kind"] for call in save_vault_mock.call_args_list}
    assert kinds == {"character", "item"}

    # Output URLs: anchor + 3 evidence (ordering preserved).
    assert len(processed) == 4
    assert processed[0]["image_url"].endswith("anchor_cutout.png")
    assert all(layer["asset_kind"] == "cutout" for layer in processed)


def test_generate_dossier_cutouts_network_layout_skips_anchor_call(tmp_path, monkeypatch):
    ig_mod, _vault_mod = _reset_data_dir(monkeypatch, tmp_path)

    sheet_call = tmp_path / "fake_sheet.png"
    _write_chroma_image(sheet_call, width=900, height=300)
    generated_paths = iter([str(sheet_call)])
    generate_image_mock = MagicMock(side_effect=lambda *a, **k: next(generated_paths))
    save_vault_mock = MagicMock()

    layers = [
        _layer("scene1_subj_1", "SUSPECT A", "ringleader", "top-left"),
        _layer("scene1_subj_2", "SUSPECT B", "associate", "top-right"),
        _layer("scene1_subj_3", "SUSPECT C", "informant", "bottom-center"),
    ]

    with patch.object(ig_mod, "generate_image", generate_image_mock), \
         patch.object(ig_mod, "save_vault_image", save_vault_mock):
        processed = ig_mod.generate_dossier_cutouts(
            scene_id="scene1",
            layers=layers,
            script_id="proj1",
            scene_prompt="A network of co-conspirators",
            dossier_layout="network",
        )

    # Network: only the contact sheet call (no anchor).
    assert generate_image_mock.call_count == 1
    # Three vault writes (one per evidence cutout).
    assert save_vault_mock.call_count == 3
    assert len(processed) == 3
    assert all(layer["asset_kind"] == "cutout" for layer in processed)


def test_generate_dossier_cutouts_returns_empty_layers_unchanged(tmp_path, monkeypatch):
    ig_mod, _vault_mod = _reset_data_dir(monkeypatch, tmp_path)
    result = ig_mod.generate_dossier_cutouts(
        scene_id="scene1",
        layers=[],
        script_id="proj1",
        scene_prompt="x",
        dossier_layout="anchor",
    )
    assert result == []
