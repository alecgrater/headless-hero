import json

from models.script import ScriptContent, Scene, VisualCanvas, VisualLayer


def test_visual_canvas_normalizes_hex_color():
    canvas = VisualCanvas(background_color="f6c54a")
    assert canvas.background_color == "#F6C54A"


def test_visual_canvas_invalid_color_falls_back_to_default():
    canvas = VisualCanvas(background_color="yellow")
    assert canvas.background_color == "#F6C54A"


def test_scene_defaults_to_full_frame_visual_treatment():
    scene = Scene(id="s1", narration="Hello.", visual_prompt="A simple scene")
    assert scene.visual_treatment == "full_frame"
    assert scene.visual_layers == []


def test_unknown_visual_treatment_normalizes_to_full_frame():
    scene = Scene(
        id="s1",
        narration="Hello.",
        visual_prompt="A simple scene",
        visual_treatment="unknown",
    )
    assert scene.visual_treatment == "full_frame"


def test_visual_layer_defaults_to_panel_image():
    layer = VisualLayer(id="panel_1", prompt="A small panel")
    assert layer.type == "image"
    assert layer.asset_kind == "panel"
    assert layer.placement == "center"
    assert layer.animation == "none"


def test_script_content_has_visual_canvas_default():
    content = ScriptContent(title="Test", segments=[])
    raw = json.loads(content.model_dump_json())
    assert raw["visual_canvas"]["background_color"] == "#F6C54A"
