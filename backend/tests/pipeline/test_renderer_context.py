from pipeline.renderer_context import (
    RENDERER_CONTEXTS,
    infer_renderer_context,
    normalize_renderer_context,
)


def test_renderer_context_values_are_stable():
    assert RENDERER_CONTEXTS == (
        "plain",
        "outdoor",
        "desk",
        "classroom",
        "office",
        "kitchen",
        "lab",
    )


def test_normalize_renderer_context_accepts_only_allowlist():
    assert normalize_renderer_context("kitchen") == "kitchen"
    assert normalize_renderer_context("Kitchen") == "plain"
    assert normalize_renderer_context("") == "plain"
    assert normalize_renderer_context(None) == "plain"
    assert normalize_renderer_context("street") == "plain"
    assert normalize_renderer_context("shop") == "plain"
    assert normalize_renderer_context("space_station") == "plain"


def test_infer_renderer_context_prefers_specific_setting():
    assert infer_renderer_context(
        narration="The fryer is screaming while a customer waits at the register.",
        visual_prompt="Fast food worker at a counter.",
    ) == "kitchen"
    assert infer_renderer_context(
        narration="He blinks under the blue sky while standing on the grass.",
        visual_prompt="Simple character outdoors.",
    ) == "outdoor"
    assert infer_renderer_context(
        narration="The teacher points at the whiteboard.",
        visual_prompt="Student in a classroom.",
    ) == "classroom"
    assert infer_renderer_context(
        narration="The spreadsheet has seven fonts.",
        visual_prompt="Office worker with laptop and paperwork.",
    ) == "office"
    assert infer_renderer_context(
        narration="He blinks once.",
        visual_prompt="Human character portrait, no setting.",
    ) == "plain"
