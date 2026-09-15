"""Every chroma-keyed cutout generator must ask for the cutout provider.

The escalation logic itself is covered in test_image_client_provider_routing.py.
This pins the other half — that the call sites actually pass `purpose`. Without
it the kwarg can be deleted from any one generator and the whole suite still
passes, while Local Mode exports quietly regress to opaque rectangles. That is
not hypothetical: 38 of 40 cutouts in a shipped video were rectangles, and the
only way anyone noticed was by measuring alpha after the fact.
"""

import os
import tempfile
from types import SimpleNamespace

import pytest
from PIL import Image

from integrations.image_client import CUTOUT_SHEET


@pytest.fixture
def image_gen(monkeypatch, tmp_path):
    """image_gen pointed at a temp data dir, with generation and keying stubbed."""
    monkeypatch.setenv("HH_DATA_DIR", str(tmp_path))
    import config
    import pipeline.image_gen as module

    monkeypatch.setattr(config, "DATA_DIR", tmp_path)
    monkeypatch.setattr(module, "DATA_DIR", tmp_path)
    monkeypatch.setattr(module, "save_vault_image", lambda **_kwargs: None)
    monkeypatch.setattr(
        module, "_save_keyed_trimmed_cutout", lambda image, path, **_k: path.write_bytes(b"") or [0, 0, 8, 8]
    )
    return module


@pytest.fixture
def purposes(monkeypatch, image_gen):
    """Records the `purpose` of every generate_image call, in order."""
    recorded: list[str | None] = []

    def fake_generate_image(prompt, **kwargs):
        recorded.append(kwargs.get("purpose"))
        handle, path = tempfile.mkstemp(suffix=".png")
        os.close(handle)
        Image.new("RGB", (24, 8), color=(0, 255, 0)).save(path)
        return path

    monkeypatch.setattr(image_gen, "generate_image", fake_generate_image)
    return recorded


def image_layer(layer_id: str, prompt: str) -> dict:
    return {"id": layer_id, "prompt": prompt, "type": "image"}


class TestCutoutCallSitesRequestTheCutoutProvider:
    def test_popup_item_sheet(self, image_gen, purposes, monkeypatch):
        monkeypatch.setattr(
            image_gen,
            "_generate_popup_anchor_cutout",
            lambda **_kwargs: None,  # anchor has its own provider rule, covered below
        )
        image_gen.generate_popup_sequence_cutouts(
            scene_id="s1",
            layers=[image_layer("a", "Popup item cutout prompt for wrench."),
                    image_layer("b", "Popup item cutout prompt for hammer.")],
            script_id="proj",
            scene_prompt="A workbench.",
            force=True,
        )
        assert purposes == [CUTOUT_SHEET]

    def test_comparison_subject_sheet(self, image_gen, purposes):
        image_gen.generate_comparison_board_cutouts(
            scene_id="s2",
            layers=[image_layer("a", "Comparison board transparent cutout for before: x."),
                    image_layer("b", "Comparison board transparent cutout for after: y.")],
            script_id="proj",
            scene_prompt="Before and after.",
            force=True,
        )
        assert purposes == [CUTOUT_SHEET]

    def test_stat_card_icon(self, image_gen, purposes):
        image_gen.generate_stat_card_cutout(
            scene_id="s3",
            layers=[image_layer("a", "A single clock icon.")],
            script_id="proj",
            scene_prompt="Eighty percent.",
            force=True,
        )
        assert purposes == [CUTOUT_SHEET]


class TestAnchorFollowsTheSceneProvider:
    def test_popup_anchor_does_not_escalate(self, image_gen, purposes, monkeypatch):
        """A single subject on flat chroma keys fine locally (measured 53-79%);
        only the multi-item sheet defeats the keyer. See CLAUDE.md."""
        def fake_bundle(source_path, output_dir, **kwargs):
            cutout = output_dir / kwargs["cutout_filename"]
            cutout.write_bytes(b"")
            return SimpleNamespace(cutout_path=cutout)

        monkeypatch.setattr(image_gen, "process_character_asset_bundle", fake_bundle)
        monkeypatch.setattr(image_gen, "_generate_popup_item_cutouts", lambda **_kwargs: None)
        monkeypatch.setattr(image_gen, "_resolve_popup_anchor_generation_context",
                            lambda **_kwargs: (None, None, "", ""))
        image_gen.generate_popup_sequence_cutouts(
            scene_id="s4",
            layers=[image_layer("a", "Popup item cutout prompt for wrench."),
                    image_layer("b", "Popup item cutout prompt for hammer.")],
            script_id="proj",
            scene_prompt="A workbench.",
            force=True,
        )
        assert purposes == [None]
