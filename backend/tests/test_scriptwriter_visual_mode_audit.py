"""Regression tests for script visual-mode post-processing."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from models.script import FrameDirective, Scene, ScriptContent, Segment
from pipeline.scriptwriter import _audit_visual_mode_metadata


def test_audit_converts_caption_prompt_leak_to_text_only_captions_scene():
    scene = Scene(
        id="scene_089",
        narration="The temporary job became the whole life.",
        visual_mode="full_frame",
        visual_beat="static",
        visual_prompt=(
            "[METAPHOR] Bold flat caption text on a dark background -- no imagery, "
            "no ornamentation, just the words in clean sans-serif against near-black."
        ),
        image_url="/static/projects/test/images/scene_089_f0.png",
        frame_urls=["/static/projects/test/images/scene_089_f0.png"],
        frame_directives=[
            FrameDirective(
                prompt="[METAPHOR] Bold flat caption text on a dark background",
                source="ai_generated",
            )
        ],
    )
    content = ScriptContent(title="Test", segments=[Segment(name="Level 5", scenes=[scene])])

    counts = _audit_visual_mode_metadata(content)

    assert counts["captions"] == 1
    assert scene.visual_mode == "captions"
    assert scene.visual_beat == "captions"
    assert scene.caption_text == "The temporary job became the whole life"
    assert scene.caption_emphasis == "temporary"
    assert scene.visual_prompt == ""
    assert scene.frame_directives == []
    assert scene.image_url == ""
    assert scene.frame_urls == []


def test_audit_converts_continuous_caption_prompt_leak_to_text_only_captions_scene():
    scene = Scene(
        id="scene_091",
        narration="Because you kept not choosing anything else.",
        visual_mode="continuous",
        visual_beat="continuous",
        visual_prompt="[METAPHOR] Bold flat caption text on a dark background.",
        frame_directives=[
            FrameDirective(
                prompt="[METAPHOR] Bold flat caption text on a dark background",
                source="ai_generated",
            )
        ],
    )
    content = ScriptContent(title="Test", segments=[Segment(name="Level 5", scenes=[scene])])

    counts = _audit_visual_mode_metadata(content)

    assert counts["captions"] == 1
    assert scene.visual_mode == "captions"
    assert scene.caption_text == "Because you kept not choosing anything else"
    assert scene.caption_emphasis == "not"
    assert scene.visual_prompt == ""
    assert scene.frame_directives == []
