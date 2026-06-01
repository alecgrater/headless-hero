"""Smoke tests for the central prompt registry."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from prompts import PROMPTS, PromptDef, detect_conflicts


class TestPromptRegistry:
    def test_all_prompts_have_nonempty_template_or_builder(self):
        for name, p in PROMPTS.items():
            has_template = isinstance(p.template, str) and len(p.template) > 0
            has_builder = p.builder is not None
            assert has_template or has_builder, (
                f"PromptDef {name!r} has neither a non-empty template nor a builder"
            )

    def test_no_conflicts_detected(self):
        conflicts = detect_conflicts()
        assert conflicts == [], f"Unexpected prompt conflicts: {conflicts}"

    def test_registry_is_not_empty(self):
        assert len(PROMPTS) >= 20, (
            f"Expected at least 20 registered prompts, got {len(PROMPTS)}"
        )

    def test_all_prompts_have_domain(self):
        for name, p in PROMPTS.items():
            assert p.domain, f"PromptDef {name!r} has no domain"

    def test_build_raises_without_builder(self):
        p = PromptDef(name="test", domain="test", purpose="test", template="hello")
        try:
            p.build()
            assert False, "Expected TypeError"
        except TypeError:
            pass

    def test_build_calls_builder(self):
        p = PromptDef(
            name="test",
            domain="test",
            purpose="test",
            template="",
            builder=lambda x: f"built: {x}",
        )
        assert p.build("arg") == "built: arg"

    def test_title_card_prompts_forbid_subtitles(self):
        outline_prompt = PROMPTS["SCRIPT_OUTLINE_INSTRUCTIONS"].template
        title_card_prompt = PROMPTS["TITLE_CARD_INSTRUCTIONS"].build("8")

        assert '"card_subtitle": ""' in outline_prompt
        assert "Set card_subtitle to an empty string" in outline_prompt
        assert '"card_subtitle": MUST be an empty string' in title_card_prompt

    def test_script_prompt_allows_life_as_a_text_modes_by_best_fit(self):
        prompt_text = PROMPTS["LIFE_AS_A_SCRIPT_SYSTEM"].template

        assert "captions" in prompt_text
        assert "stat_card" in prompt_text
        assert "dossier" not in prompt_text
        assert "life-as-a" in prompt_text
        assert "captions remain disabled" not in prompt_text
        assert "DISABLED in life-as-a" not in prompt_text
        assert "60–75%" not in prompt_text
