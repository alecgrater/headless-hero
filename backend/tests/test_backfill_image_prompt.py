"""Image-backed scenes must carry a prompt before the images stage runs.

A real life-as-a run moved four scenes into image-backed modes with no prompt
(a comparison board demoted at prep, two caption beats, a monotony-fix
multi_frame). Every image path skipped them, the render generated them late,
and all six shorts re-rendered because their sources were now newer.
"""

from models.script import Scene, ScriptContent, Segment
from pipeline.visual_mode_policy import backfill_image_prompt
from pipeline.visual_treatments import VisualTreatmentAssignment, apply_visual_treatment_assignments


def _scene(**kwargs) -> Scene:
    base = {"id": "scene_001", "narration": "Two crews finish their flights and never learn how near it came."}
    return Scene(**{**base, **kwargs})


def test_backfills_an_image_backed_scene_from_narration_before_caption():
    scene = _scene(visual_mode="full_frame", visual_prompt="", caption_text="Nothing happened.")
    assert backfill_image_prompt(scene) is True
    assert scene.visual_prompt == scene.narration


def test_falls_back_to_caption_text_without_narration():
    scene = _scene(narration="", visual_mode="multi_frame", visual_prompt="", caption_text="Nothing happened.")
    assert backfill_image_prompt(scene) is True
    assert scene.visual_prompt == "Nothing happened."


def test_leaves_prompted_text_only_and_title_scenes_alone():
    prompted = _scene(visual_mode="full_frame", visual_prompt="A radar room")
    captions = _scene(visual_mode="captions", visual_prompt="", caption_text="Nothing happened.")
    title = _scene(visual_mode="full_frame", visual_prompt="", is_title_card=True)
    assert [backfill_image_prompt(s) for s in (prompted, captions, title)] == [False, False, False]
    assert prompted.visual_prompt == "A radar room"
    assert captions.visual_prompt == ""


def test_prep_demotion_to_full_frame_backfills_the_prompt():
    scene = _scene(visual_mode="captions", visual_prompt="", caption_text="Nothing happened.")
    content = ScriptContent(title="T", segments=[Segment(name="S", scenes=[scene])])
    apply_visual_treatment_assignments(
        content,
        [VisualTreatmentAssignment(scene_id="scene_001", visual_mode="full_frame", reasoning="demoted")],
    )
    demoted = content.all_scenes()[0]
    assert demoted.visual_mode == "full_frame"
    assert demoted.visual_prompt == demoted.narration
