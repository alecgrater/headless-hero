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
