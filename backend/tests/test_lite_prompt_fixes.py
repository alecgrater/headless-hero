"""Prompt fixes measured on Nano Banana 2 Lite (2026-09-30).

Each test pins one wording or ordering decision that a side-by-side image test
showed matters. They are text checks, so they say nothing about image quality on
their own — the measurements behind them are in CLAUDE.md under Local/Cloud image
models. Change a pinned phrase only after re-measuring.
"""

from types import SimpleNamespace

import pytest
from PIL import Image

from models.script import MainCharacter
from pipeline import image_gen

def test_batch_request_labels_each_attached_image(tmp_path):
    """Unlabelled, the busy style preset was copied as content when the scene prompt was thin."""
    from integrations import google_image_client as gic

    ref, style = tmp_path / "ref.png", tmp_path / "style.png"
    for path in (ref, style):
        Image.new("RGB", (4, 4)).save(path)
    request = gic.GoogleBatchImageRequest(key="k", prompt="Draw it.", aspect_ratio="16:9",
                                          reference_image_path=str(ref), style_reference_path=str(style))
    parts = gic._batch_request_payload(request)["contents"][0]["parts"]
    assert parts[0] == {"text": gic.REFERENCE_IMAGE_LABEL}
    assert "inline_data" in parts[1] or "inlineData" in parts[1]
    assert parts[2] == {"text": gic.STYLE_IMAGE_LABEL}
    assert parts[-1] == {"text": "Draw it."}
    assert "Never copy its people" in gic.STYLE_IMAGE_LABEL


RAY = MainCharacter(name="Fred", appearance="Large round white head, round black glasses, navy top.", vibe="Chatty.")


class TestMainCharacterInstructions:
    def test_reference_defines_identity_not_clothing(self):
        text = image_gen._serialize_main_character(RAY)
        assert "does NOT define clothing" in text
        # "match exactly ... clothing cues" made Lite copy the reference tank top onto a prison guard.
        assert "clothing cues" not in text

    def test_any_name_or_role_in_the_scene_means_this_character(self):
        """Scene text written before a character swap can use a different name."""
        text = image_gen._serialize_main_character(RAY)
        assert '"Fred", another name, a role' in text

    def test_style_lock_closes_the_instructions(self):
        text = image_gen._serialize_main_character(RAY)
        assert text.endswith(image_gen._PROTAGONIST_STYLE_LOCK)


class TestCharacterBlockComesLast:
    """Placed before the scene text, it lost to "square jaw, heavy brows" (6/12 vs 12/12 last)."""

    def test_scene_image_prompt(self, monkeypatch):
        monkeypatch.setattr(image_gen, "_load_project_character_context", lambda _sid: (False, None, RAY))
        monkeypatch.setattr(image_gen, "_ensure_project_character_reference_ready", lambda **_kw: None)
        monkeypatch.setattr(image_gen, "_load_project_style_enabled", lambda _sid: False)
        monkeypatch.setattr(image_gen, "_resolve_style_preset", lambda **_kw: None)
        monkeypatch.setattr(image_gen, "_project_character_reference_path", lambda _sid: None)
        monkeypatch.setattr(image_gen, "_resolve_character_reference",
                            lambda **_kw: (None, image_gen._serialize_main_character(RAY)))
        prompt, _, _ = image_gen._compose_image_prompt_context(
            visual_prompt="Ray, square jaw and heavy brows, at the tier window.", script_id="p", contains_person=True)
        assert prompt.index("square jaw") < prompt.index("STYLE LOCK")
        assert prompt.rstrip().endswith(image_gen._PROTAGONIST_STYLE_LOCK)

    def test_popup_anchor_prompt(self):
        prompt = image_gen._compose_popup_anchor_prompt(
            "Ray, square jaw, at his locker.", contains_person=True,
            character_context=image_gen._serialize_main_character(RAY))
        assert prompt.index("square jaw") < prompt.index("STYLE LOCK")
        # "detailed" pulled the anchor away from a minimal reference style.
        assert "should be detailed" not in prompt


class TestCutoutSheetPrompt:
    def test_avoids_wording_that_drew_panels_and_captions(self):
        prompt = image_gen._compose_popup_item_sheet_prompt("A locker room.", ["handcuffs", "a clipboard"])
        lowered = prompt.lower()
        assert "contact sheet" not in lowered
        assert "slot" not in lowered
        assert "1. handcuffs" not in prompt  # numbered labels were drawn as captions
        assert "Subject 1: handcuffs" in prompt
        assert "Never write them" in prompt

    def test_positions_are_in_words_not_numbers(self):
        """Percent positions ("17%, 50%, 83%") were drawn as captions under the subjects."""
        prompt = image_gen._compose_popup_item_sheet_prompt("Scene.", ["a", "b", "c"])
        layout = prompt[prompt.index("Layout:"):prompt.index("Background:")]
        assert "%" not in layout
        assert "evenly across the full width" in layout

    def test_popup_sheet_excludes_people_and_comparison_does_not(self):
        assert "No main character or human figures" in image_gen._compose_popup_item_sheet_prompt("S.", ["a", "b"])
        assert "human figures" not in image_gen._compose_comparison_subject_sheet_prompt("S.", ["a", "b"])


class TestComparisonSheetCarriesTheCharacter:
    @pytest.fixture
    def captured(self, monkeypatch, tmp_path):
        monkeypatch.setattr(image_gen, "DATA_DIR", tmp_path)
        monkeypatch.setattr(image_gen, "save_vault_image", lambda **_kw: None)
        monkeypatch.setattr(image_gen, "_save_keyed_trimmed_cutout", lambda image, path, **_kw: path.write_bytes(b""))
        calls = []

        def fake_generate_image(prompt, **kwargs):
            calls.append(SimpleNamespace(prompt=prompt, **kwargs))
            path = tmp_path / f"gen_{len(calls)}.png"
            Image.new("RGB", (24, 8), (0, 255, 0)).save(path)
            return str(path)

        monkeypatch.setattr(image_gen, "generate_image", fake_generate_image)
        monkeypatch.setattr(image_gen, "_load_project_character_context", lambda _sid: (False, None, RAY))
        monkeypatch.setattr(image_gen, "_resolve_character_reference",
                            lambda **_kw: ("/ref/ray.png", image_gen._serialize_main_character(RAY)))
        return calls

    def _generate(self, contains_person):
        image_gen.generate_comparison_board_cutouts(
            scene_id="s", script_id="p", scene_prompt="Year one vs year twelve.", force=True,
            contains_person=contains_person,
            layers=[{"id": "a", "type": "image", "prompt": "Comparison board transparent cutout for year one: x."},
                    {"id": "b", "type": "image", "prompt": "Comparison board transparent cutout for year twelve: y."}])

    def test_person_scene_sends_the_reference_and_identity_block(self, captured):
        self._generate(contains_person=True)
        assert captured[0].reference_image_path == "/ref/ray.png"
        assert "STYLE LOCK" in captured[0].prompt

    def test_object_scene_sends_neither(self, captured):
        self._generate(contains_person=False)
        assert captured[0].reference_image_path is None
        assert "STYLE LOCK" not in captured[0].prompt


def test_cache_markers_never_reach_the_model():
    """They are cache keys; left in, they were the last text after the style lock."""
    from integrations.image_client import strip_cache_markers

    prompt = "Scene.\n\nSTYLE LOCK — keep it.\n[char_ref:/a/ref.png:123]\n[style_ref:/a/s.png:456]"
    assert strip_cache_markers(prompt) == "Scene.\n\nSTYLE LOCK — keep it."
    assert strip_cache_markers("[reference_previous:/f.png:9] Draw.") == " Draw."


def test_every_frame_path_appends_the_character_block_last():
    """Pins the ordering in generate_scene_frames and the v2 frame planner, which are too heavy to call here."""
    import inspect

    legacy = inspect.getsource(image_gen.generate_scene_frames)
    planner = inspect.getsource(image_gen._plan_sequence_frame)
    legacy_tail = '            if character_text:\n                parts.append(character_text)\n            prompt = "\\n\\n".join(parts)'
    planner_tail = '        if character_text:\n            parts.append(character_text)\n        prompt = "\\n\\n".join(parts)'
    assert legacy.count(legacy_tail) == 2
    assert planner.count(planner_tail) == 2
    assert (legacy + planner).count("parts.append(character_text)") == 4


def test_comparison_sheet_lifts_the_single_protagonist_rule():
    prompt = image_gen._compose_comparison_subject_sheet_prompt("S.", ["a", "b"], character_block="BLOCK")
    assert "Several subjects may each be the main character" in prompt
    assert prompt.index("Several subjects") < prompt.index("BLOCK")
