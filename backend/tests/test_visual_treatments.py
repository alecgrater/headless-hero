import json
import os
import tempfile

from PIL import Image, ImageDraw
import pytest
from sqlmodel import Session, SQLModel, create_engine
from sqlmodel.pool import StaticPool

from models.settings import AppSetting
from models.script import Script
from models.script import ScriptContent, Scene, Segment, VisualCanvas, VisualLayer
from pipeline.image_gen import generate_visual_layer_panels, visual_layer_image_filename
from pipeline.render_jobs import RenderJob
from pipeline.render_jobs import UserFacingJobError
from pipeline.visual_treatments import (
    VisualTreatmentAssignment,
    analyze_visual_treatments,
    apply_visual_treatment_assignments,
    flipflop_background_prompt,
    flipflop_cutout_prompt,
    require_visual_treatment_voiceover,
)


def _build_test_engine():
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    SQLModel.metadata.create_all(engine)
    return engine


def scene_with_words(scene_id: str, narration: str) -> Scene:
    words = []
    cursor = 0
    for word in narration.replace(",", "").replace(".", "").split():
        words.append({"word": word, "start_ms": cursor, "end_ms": cursor + 300})
        cursor += 350
    return Scene(
        id=scene_id,
        narration=narration,
        visual_prompt=f"Panel for {scene_id}",
        audio_duration_seconds=max(cursor / 1000, 1.0),
        word_timestamps=words,
    )


def content_with_scenes(*scenes: Scene) -> ScriptContent:
    return ScriptContent(title="Treatment Test", segments=[{"name": "Segment", "scenes": list(scenes)}])


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


def test_scene_visual_layers_default_is_not_shared():
    first_scene = Scene(id="s1", narration="Hello.", visual_prompt="A simple scene")
    second_scene = Scene(id="s2", narration="Hi.", visual_prompt="Another simple scene")

    first_scene.visual_layers.append(VisualLayer(id="panel_1"))

    assert len(first_scene.visual_layers) == 1
    assert second_scene.visual_layers == []


def test_unknown_visual_treatment_normalizes_to_full_frame():
    scene = Scene(
        id="s1",
        narration="Hello.",
        visual_prompt="A simple scene",
        visual_treatment="unknown",
    )
    assert scene.visual_treatment == "full_frame"


def test_visual_layer_defaults_to_panel_image():
    layer = VisualLayer(id="panel_1")
    assert layer.type == "image"
    assert layer.asset_kind == "panel"
    assert layer.image_url == ""
    assert layer.prompt == ""
    assert layer.placement == "center"
    assert layer.enter_at_seconds == 0.0
    assert layer.exit_at_seconds is None
    assert layer.animation == "none"


def test_visual_layer_invalid_values_normalize_to_defaults():
    layer = VisualLayer(
        id="panel_1",
        type="video",
        asset_kind="thumbnail",
        animation="slide",
    )
    assert layer.type == "image"
    assert layer.asset_kind == "panel"
    assert layer.animation == "none"


def test_visual_treatment_assignment_sets_canonical_visual_mode():
    content = content_with_scenes(
        Scene(id="scene_001", narration="First this, second that.", visual_prompt="A list")
    )

    apply_visual_treatment_assignments(
        content,
        [
            VisualTreatmentAssignment(
                scene_id="scene_001",
                visual_treatment="popup_sequence",
                visual_layers=[VisualLayer(id="panel_1")],
            )
        ],
    )

    scene = content.all_scenes()[0]
    assert scene.visual_mode == "popup_sequence"
    assert scene.media_source == "ai"
    assert scene.visual_treatment == "popup_sequence"


def test_update_visual_treatment_request_normalizes_legacy_treatment():
    from api.visual_treatments import UpdateVisualTreatmentRequest

    request = UpdateVisualTreatmentRequest.model_validate({
        "scene_id": "scene_001",
        "visual_treatment": "flipflop",
    })

    assert request.visual_mode == "flipflop"


def test_visual_treatment_assignment_preserves_video_visual_mode():
    content = content_with_scenes(
        scene_with_words("scene_001", "Video line with motion.")
    )
    content.all_scenes()[0].set_visual_mode("video")

    assignments = analyze_visual_treatments(content, script_id="script-1")
    apply_visual_treatment_assignments(content, assignments)

    scene = content.all_scenes()[0]
    assert scene.visual_mode == "video"
    assert scene.media_source == "ai_video"
    assert scene.visual_treatment == "full_frame"
    assert scene.visual_layers == []


def test_analyze_visual_treatments_preserves_explicit_captions_scene():
    scene = Scene(
        id="scene_001",
        narration="This is the real cost.",
        visual_prompt="",
        visual_mode="captions",
        caption_text="The real cost",
        caption_emphasis="real",
        audio_duration_seconds=2.0,
        word_timestamps=[
            {"word": "This", "start_ms": 0, "end_ms": 100},
            {"word": "is", "start_ms": 120, "end_ms": 180},
            {"word": "the", "start_ms": 200, "end_ms": 260},
            {"word": "real", "start_ms": 300, "end_ms": 450},
            {"word": "cost", "start_ms": 470, "end_ms": 640},
        ],
    )
    content = ScriptContent(title="Test", segments=[Segment(name="Segment", scenes=[scene])])

    assignment = analyze_visual_treatments(content, script_id="script")[0]

    assert assignment.visual_mode == "captions"
    assert assignment.visual_treatment == "full_frame"
    assert assignment.visual_layers == []


def test_analyze_visual_treatments_preserves_explicit_captions_scene_with_stale_video_url():
    scene = Scene(
        id="scene_001",
        narration="This is the real cost.",
        visual_prompt="",
        visual_mode="captions",
        caption_text="The real cost",
        audio_duration_seconds=2.0,
        word_timestamps=[
            {"word": "This", "start_ms": 0, "end_ms": 100},
            {"word": "is", "start_ms": 120, "end_ms": 180},
            {"word": "the", "start_ms": 200, "end_ms": 260},
            {"word": "real", "start_ms": 300, "end_ms": 450},
            {"word": "cost", "start_ms": 470, "end_ms": 640},
        ],
        video_url="/static/projects/script/video/scene_001.mp4",
    )
    content = ScriptContent(title="Test", segments=[Segment(name="Segment", scenes=[scene])])

    assignment = analyze_visual_treatments(content, script_id="script")[0]

    assert assignment.visual_mode == "captions"
    assert assignment.visual_treatment == "full_frame"
    assert assignment.visual_layers == []


def test_visual_treatment_assignment_can_change_video_scene_to_full_frame():
    content = content_with_scenes(
        Scene(id="scene_001", narration="Video line.", visual_prompt="A walking character.", visual_mode="video")
    )

    apply_visual_treatment_assignments(
        content,
        [
            VisualTreatmentAssignment(
                scene_id="scene_001",
                visual_mode="full_frame",
                visual_treatment="full_frame",
                visual_layers=[],
            )
        ],
    )

    scene = content.all_scenes()[0]
    assert scene.visual_mode == "full_frame"
    assert scene.media_source == "ai"
    assert scene.visual_treatment == "full_frame"


def test_visual_layer_image_filename_is_stable_and_png():
    assert visual_layer_image_filename("scene_001", "scene_001_panel_1") == "scene_001_layer_scene_001_panel_1.png"


def test_visual_layer_image_filename_sanitizes_scene_and_layer_ids():
    filename = visual_layer_image_filename("../bad", "panel/../../evil")

    assert "/" not in filename
    assert ".." not in filename
    assert filename == "___bad_layer_panel_______evil.png"


def _stub_panel_image_context(monkeypatch, tmp_path):
    from pipeline import image_gen as image_gen_mod

    char_ref = tmp_path / "character-ref.png"
    char_ref.write_text("char", encoding="utf-8")
    style_ref = tmp_path / "style-ref.png"
    style_ref.write_text("style", encoding="utf-8")

    monkeypatch.setattr(image_gen_mod, "DATA_DIR", tmp_path)
    monkeypatch.setattr(image_gen_mod, "_VISUAL_STYLE", "HOUSE STYLE")
    monkeypatch.setattr(image_gen_mod, "_STYLE_GUIDE", "COMPOSITION GUIDE")
    monkeypatch.setattr(image_gen_mod, "_load_project_character_context", lambda script_id: (True, None, None))
    monkeypatch.setattr(image_gen_mod, "_ensure_project_character_reference_ready", lambda **kwargs: None)
    monkeypatch.setattr(image_gen_mod, "_load_project_style_enabled", lambda script_id: True)
    monkeypatch.setattr(
        image_gen_mod,
        "_resolve_character_reference",
        lambda **kwargs: (str(char_ref), "CHARACTER PROMPT") if kwargs["contains_person"] else (None, ""),
    )
    monkeypatch.setattr(image_gen_mod, "_resolve_style_preset", lambda **kwargs: str(style_ref))
    return image_gen_mod, str(char_ref), str(style_ref)


def _stub_generate_image_file(monkeypatch, image_gen_mod, captured):
    def fake_generate_image(prompt, *, width, height, reference_image_path=None, original_prompt=None, script_id=None, **kwargs):
        fd, tmp = tempfile.mkstemp(suffix=".png")
        os.close(fd)
        with open(tmp, "wb") as handle:
            handle.write(b"panel")
        captured.append(
            {
                "prompt": prompt,
                "width": width,
                "height": height,
                "reference_image_path": reference_image_path,
                "original_prompt": original_prompt,
                "script_id": script_id,
                "style_reference_path": kwargs.get("style_reference_path"),
            }
        )
        return tmp

    monkeypatch.setattr(image_gen_mod, "generate_image", fake_generate_image)


def test_generate_visual_layer_panels_uses_composed_prompt_and_references(tmp_path, monkeypatch):
    image_gen_mod, char_ref, style_ref = _stub_panel_image_context(monkeypatch, tmp_path)
    captured = []
    _stub_generate_image_file(monkeypatch, image_gen_mod, captured)

    layers = generate_visual_layer_panels(
        "scene_001",
        [{"id": "panel_1", "type": "image", "asset_kind": "panel", "prompt": "Raw panel", "contains_person": True}],
        "script-1",
        width=320,
        height=180,
    )

    assert len(captured) == 1
    prompt = captured[0]["prompt"]
    assert "HOUSE STYLE" in prompt
    assert "COMPOSITION GUIDE" in prompt
    assert "CHARACTER PROMPT" in prompt
    assert "Raw panel" in prompt
    assert "[char_ref:" in prompt
    assert "[style_ref:" in prompt
    assert captured[0]["reference_image_path"] == char_ref
    assert captured[0]["style_reference_path"] == style_ref
    assert captured[0]["original_prompt"] == "Raw panel"
    assert layers[0]["image_url"] == "/static/projects/script-1/images/scene_001_layer_panel_1.png"
    prompt_marker = tmp_path / "projects" / "script-1" / "images" / "scene_001_layer_panel_1.png.prompt"
    assert prompt_marker.read_text(encoding="utf-8") == prompt


def test_generate_visual_layer_panels_uses_scene_person_fallback(tmp_path, monkeypatch):
    image_gen_mod, char_ref, _ = _stub_panel_image_context(monkeypatch, tmp_path)
    captured = []
    _stub_generate_image_file(monkeypatch, image_gen_mod, captured)

    generate_visual_layer_panels(
        "scene_001",
        [{"id": "panel_1", "type": "image", "asset_kind": "panel", "prompt": "Raw panel"}],
        "script-1",
        contains_person=True,
    )

    assert len(captured) == 1
    assert "CHARACTER PROMPT" in captured[0]["prompt"]
    assert captured[0]["reference_image_path"] == char_ref


def test_generate_visual_layer_panels_expands_flipflop_micro_animation_prompts(tmp_path, monkeypatch):
    image_gen_mod, char_ref, _ = _stub_panel_image_context(monkeypatch, tmp_path)
    captured = []
    _stub_generate_image_file(monkeypatch, image_gen_mod, captured)

    layers = generate_visual_layer_panels(
        "scene_001",
        [
            {
                "id": "scene_001_state_a",
                "type": "image",
                "asset_kind": "panel",
                "prompt": "Flat 2D cartoon person standing at a podium holding a book.",
                "contains_person": True,
            },
            {
                "id": "scene_001_state_b",
                "type": "image",
                "asset_kind": "panel",
                "prompt": "Flat 2D cartoon person standing at a podium holding a book.",
                "contains_person": True,
            },
        ],
        "script-1",
        visual_treatment="flipflop",
    )

    assert len(captured) == 2
    assert "State A" in captured[0]["prompt"]
    assert "initial pose" in captured[0]["prompt"]
    assert "full-bleed 16:9 illustration" in captured[0]["prompt"]
    assert "No decorative border" in captured[0]["prompt"]
    assert "small framed" not in captured[0]["prompt"].lower()
    assert "framed panel" not in captured[0]["prompt"].lower()
    assert "State B" in captured[1]["prompt"]
    assert "same exact composition" in captured[1]["prompt"]
    assert "small pose/expression progression" in captured[1]["prompt"]
    assert "full-bleed 16:9 illustration" in captured[1]["prompt"]
    assert "No decorative border" in captured[1]["prompt"]
    assert "small framed" not in captured[1]["prompt"].lower()
    assert "framed panel" not in captured[1]["prompt"].lower()
    assert captured[0]["reference_image_path"] == char_ref
    assert captured[1]["reference_image_path"].endswith("scene_001_layer_scene_001_state_a.png")
    assert "State A" in captured[0]["original_prompt"]
    assert "State B" in captured[1]["original_prompt"]
    assert layers[0]["image_url"] == "/static/projects/script-1/images/scene_001_layer_scene_001_state_a.png"
    assert layers[1]["image_url"] == "/static/projects/script-1/images/scene_001_layer_scene_001_state_b.png"


def test_generate_visual_layer_panels_sanitizes_stale_flipflop_frame_prompts(tmp_path, monkeypatch):
    image_gen_mod, _char_ref, _ = _stub_panel_image_context(monkeypatch, tmp_path)
    captured = []
    _stub_generate_image_file(monkeypatch, image_gen_mod, captured)

    generate_visual_layer_panels(
        "scene_001",
        [
            {
                "id": "scene_001_state_a",
                "type": "image",
                "asset_kind": "panel",
                "prompt": (
                    "small framed Headless Hero cartoon panel for state A: "
                    "Flat 2D cartoon person standing at a podium holding a book. "
                    "The panel sits on a flat static color background, not a full video background. "
                    "No text in image."
                ),
            },
        ],
        "script-1",
        visual_treatment="flipflop",
    )

    prompt = captured[0]["prompt"].lower()
    assert "flat 2d cartoon person standing at a podium holding a book" in prompt
    assert "small framed" not in prompt
    assert "headless hero cartoon panel" not in prompt
    assert "the panel sits" not in prompt
    assert "full video background" not in prompt


def test_generate_visual_layer_panels_sanitizes_stale_frame_prompts_for_any_treatment(tmp_path, monkeypatch):
    image_gen_mod, _char_ref, _ = _stub_panel_image_context(monkeypatch, tmp_path)
    captured = []
    _stub_generate_image_file(monkeypatch, image_gen_mod, captured)

    generate_visual_layer_panels(
        "scene_001",
        [
            {
                "id": "panel_1",
                "type": "image",
                "asset_kind": "panel",
                "prompt": (
                    "small framed Headless Hero cartoon panel: "
                    "Flat 2D cartoon person opening a bright classroom door. "
                    "The panel sits on a flat static color background, not a full video background. "
                    "No text in image."
                ),
            },
        ],
        "script-1",
        visual_treatment="popup_sequence",
    )

    prompt = captured[0]["prompt"].lower()
    assert "flat 2d cartoon person opening a bright classroom door" in prompt
    assert "small framed" not in prompt
    assert "headless hero cartoon panel" not in prompt
    assert "the panel sits" not in prompt
    assert "full video background" not in prompt


def test_generate_visual_layer_panels_cache_hit_uses_composed_prompt(tmp_path, monkeypatch):
    image_gen_mod, _, _ = _stub_panel_image_context(monkeypatch, tmp_path)
    captured = []
    _stub_generate_image_file(monkeypatch, image_gen_mod, captured)
    layer = {"id": "panel_1", "type": "image", "asset_kind": "panel", "prompt": "Raw panel", "contains_person": True}
    generate_visual_layer_panels("scene_001", [layer], "script-1")
    captured.clear()

    layers = generate_visual_layer_panels("scene_001", [layer], "script-1")

    assert captured == []
    assert layers[0]["image_url"] == "/static/projects/script-1/images/scene_001_layer_panel_1.png"


def test_generate_visual_layer_panels_force_regenerates_cached_panel(tmp_path, monkeypatch):
    image_gen_mod, _, _ = _stub_panel_image_context(monkeypatch, tmp_path)
    captured = []
    _stub_generate_image_file(monkeypatch, image_gen_mod, captured)
    layer = {"id": "panel_1", "type": "image", "asset_kind": "panel", "prompt": "Raw panel"}
    generate_visual_layer_panels("scene_001", [layer], "script-1")

    generate_visual_layer_panels("scene_001", [layer], "script-1", force=True)

    assert len(captured) == 2


def test_generate_visual_layer_panels_preserves_non_panel_layers(tmp_path, monkeypatch):
    image_gen_mod, _, _ = _stub_panel_image_context(monkeypatch, tmp_path)
    captured = []
    _stub_generate_image_file(monkeypatch, image_gen_mod, captured)
    non_panel = {"id": "cutout_1", "type": "image", "asset_kind": "cutout", "prompt": "Do not generate"}

    layers = generate_visual_layer_panels(
        "scene_001",
        [
            {"id": "panel_1", "type": "image", "asset_kind": "panel", "prompt": "Generate panel"},
            non_panel,
        ],
        "script-1",
    )

    assert len(captured) == 1
    assert layers[1] == non_panel


def test_phase_persist_writes_generated_visual_layer_urls(monkeypatch):
    import database
    from pipeline.render_phases import ExportContext, _phase_persist

    engine = _build_test_engine()
    content = content_with_scenes(
        Scene(
            id="scene_001",
            narration="Panel scene.",
            visual_prompt="Panel",
            visual_treatment="popup_sequence",
            visual_layers=[VisualLayer(id="panel_1", prompt="Panel prompt")],
        )
    )
    with Session(engine) as session:
        session.add(
            Script(
                id="script-1",
                brand_id="brand",
                topic_title="Treatment Test",
                script_json=content.model_dump_json(),
            )
        )
        session.commit()

    monkeypatch.setattr(database, "engine", engine)
    ctx = ExportContext(
        script_id="script-1",
        job=RenderJob("job-1"),
        scenes=[
            {
                "scene_id": "scene_001",
                "_visual_layers": [
                    {
                        "id": "panel_1",
                        "type": "image",
                        "asset_kind": "panel",
                        "prompt": "Panel prompt",
                        "image_url": "/static/projects/script-1/images/scene_001_layer_panel_1.png",
                    }
                ],
            }
        ],
        seg_name="Segment",
        total_scenes=1,
        voice_id="voice",
        brand_dict={},
        project_title="Treatment Test",
        title="Segment",
        total_segments=1,
        regen_images=True,
        regen_audio=False,
        regen_fx=False,
        regen_eli=False,
        phase_ranges={"persist": (0.0, 1.0)},
    )

    _phase_persist(ctx)

    with Session(engine) as session:
        stored = session.get(Script, "script-1")
        assert stored is not None
        stored_content = ScriptContent.model_validate_json(stored.script_json)
        assert stored_content.segments[0].scenes[0].visual_layers[0].image_url == (
            "/static/projects/script-1/images/scene_001_layer_panel_1.png"
        )


def test_phase_persist_clears_popup_sequence_scene_image(monkeypatch):
    import database
    from pipeline.render_phases import ExportContext, _phase_persist

    engine = _build_test_engine()
    content = content_with_scenes(
        Scene(
            id="scene_001",
            narration="Panel scene.",
            visual_prompt="Panel",
            image_url="/static/projects/script-1/images/stale_scene.png",
            frame_urls=["/static/projects/script-1/images/stale_frame.png"],
            visual_treatment="popup_sequence",
            visual_layers=[VisualLayer(id="panel_1", prompt="Panel prompt")],
        )
    )
    with Session(engine) as session:
        session.add(
            Script(
                id="script-1",
                brand_id="brand",
                topic_title="Treatment Test",
                script_json=content.model_dump_json(),
            )
        )
        session.commit()

    monkeypatch.setattr(database, "engine", engine)
    ctx = ExportContext(
        script_id="script-1",
        job=RenderJob("job-1"),
        scenes=[
            {
                "scene_id": "scene_001",
                "_image_url": "",
                "_frame_urls": [],
            }
        ],
        seg_name="Segment",
        total_scenes=1,
        voice_id="voice",
        brand_dict={},
        project_title="Treatment Test",
        title="Segment",
        total_segments=1,
        regen_images=True,
        regen_audio=False,
        regen_fx=False,
        regen_eli=False,
        phase_ranges={"persist": (0.0, 1.0)},
    )

    _phase_persist(ctx)

    with Session(engine) as session:
        stored = session.get(Script, "script-1")
        assert stored is not None
        stored_content = ScriptContent.model_validate_json(stored.script_json)
        scene = stored_content.segments[0].scenes[0]
        assert scene.image_url == ""
        assert scene.frame_urls == []


def test_phase_images_forces_flipflop_cutout_regeneration(monkeypatch):
    from pipeline import image_gen as image_gen_mod
    from pipeline import render_phases as render_phases_mod
    from pipeline.render_phases import ExportContext, _phase_images

    content = content_with_scenes(
        Scene(
            id="scene_001",
            narration="Panel scene.",
            visual_prompt="Panel",
            visual_treatment="flipflop",
            contains_person=True,
            visual_layers=[
                VisualLayer(id="state_a", asset_kind="panel", prompt="State A prompt"),
                VisualLayer(id="state_b", asset_kind="panel", prompt="State B prompt"),
            ],
        )
    )
    captured = {}
    monkeypatch.setattr(render_phases_mod, "_reload_content", lambda script_id: content)
    def fail_scene_image(*_args, **_kwargs):
        raise AssertionError("layered animation treatments should not generate a full scene image")

    monkeypatch.setattr(image_gen_mod, "generate_scene_image", fail_scene_image)

    def fail_popup_sequence_cutouts(**_kwargs):
        raise AssertionError("flipflop should not use popup sequence cutouts")

    def fail_visual_layer_panels(*_args, **_kwargs):
        raise AssertionError("flipflop should generate chroma cutouts, not visual layer panels")

    def fake_generate_flipflop_cutouts(**kwargs):
        captured.update(kwargs)
        return [
            {**kwargs["layers"][0], "asset_kind": "cutout", "image_url": "/static/projects/script-1/flipflop_cutouts/scene_001/state_a.png"},
            {**kwargs["layers"][1], "asset_kind": "cutout", "image_url": "/static/projects/script-1/flipflop_cutouts/scene_001/state_b.png"},
        ]

    monkeypatch.setattr(image_gen_mod, "generate_popup_sequence_cutouts", fail_popup_sequence_cutouts)
    monkeypatch.setattr(image_gen_mod, "generate_visual_layer_panels", fail_visual_layer_panels)
    monkeypatch.setattr(image_gen_mod, "generate_flipflop_cutouts", fake_generate_flipflop_cutouts)
    ctx = ExportContext(
        script_id="script-1",
        job=RenderJob("job-1"),
        scenes=[
            {
                "scene_id": "scene_001",
                "visual_prompt": "Panel",
                "is_title_card": False,
                "contains_person": True,
            }
        ],
        seg_name="Segment",
        total_scenes=1,
        voice_id="voice",
        brand_dict={},
        project_title="Treatment Test",
        title="Segment",
        total_segments=1,
        regen_images=True,
        regen_audio=False,
        regen_fx=False,
        regen_eli=False,
        phase_ranges={"images": (0.0, 1.0)},
    )

    _phase_images(ctx)

    assert captured["scene_id"] == "scene_001"
    assert captured["script_id"] == "script-1"
    assert captured["force"] is True
    assert captured["scene_prompt"] == "Panel"
    assert captured["contains_person"] is True
    assert ctx.scenes[0]["_image_url"] == ""
    assert ctx.scenes[0]["_frame_urls"] == []
    assert [layer["asset_kind"] for layer in ctx.scenes[0]["_visual_layers"]] == ["cutout", "cutout"]
    assert [layer["image_url"] for layer in ctx.scenes[0]["_visual_layers"]] == [
        "/static/projects/script-1/flipflop_cutouts/scene_001/state_a.png",
        "/static/projects/script-1/flipflop_cutouts/scene_001/state_b.png",
    ]


def test_phase_images_regenerates_frame_sequence_for_multi_frame_mode(monkeypatch):
    from pipeline import image_gen as image_gen_mod
    from pipeline import render_phases as render_phases_mod
    from pipeline.render_phases import ExportContext, _phase_images

    scene = Scene(
        id="scene_001",
        narration="First this, then that.",
        visual_prompt="A two-part comparison.",
        visual_mode="multi_frame",
        frame_directives=[
            {"prompt": "First frame", "source": "ai_generated"},
            {"prompt": "Second frame", "source": "ai_generated"},
        ],
    )
    content = content_with_scenes(scene)
    captured = {}
    monkeypatch.setattr(render_phases_mod, "_reload_content", lambda script_id: content)

    def fail_scene_image(*_args, **_kwargs):
        raise AssertionError("multi_frame should regenerate frame URLs, not a single scene image")

    def fake_generate_scene_frames_v2(**kwargs):
        captured.update(kwargs)
        return [
            ("/static/projects/script-1/frames/scene_001_01.png", "First prompt", {"source_type": "ai_generated"}),
            ("/static/projects/script-1/frames/scene_001_02.png", "Second prompt", {"source_type": "ai_generated"}),
        ]

    monkeypatch.setattr(image_gen_mod, "generate_scene_image", fail_scene_image)
    monkeypatch.setattr(image_gen_mod, "generate_scene_frames_v2", fake_generate_scene_frames_v2)

    ctx = ExportContext(
        script_id="script-1",
        job=RenderJob("job-1"),
        scenes=[
            {
                "scene_id": "scene_001",
                "visual_prompt": "A two-part comparison.",
                "is_title_card": False,
                "visual_mode": "multi_frame",
            }
        ],
        seg_name="Segment",
        total_scenes=1,
        voice_id="voice",
        brand_dict={},
        project_title="Treatment Test",
        title="Segment",
        total_segments=1,
        regen_images=True,
        regen_audio=False,
        regen_fx=False,
        regen_eli=False,
        phase_ranges={"images": (0.0, 1.0)},
    )

    _phase_images(ctx)

    assert captured["scene_id"] == "scene_001"
    assert captured["frame_directives"] == [directive.model_dump() for directive in scene.frame_directives]
    assert ctx.scenes[0]["_image_url"] == "/static/projects/script-1/frames/scene_001_01.png"
    assert ctx.scenes[0]["_frame_urls"] == [
        "/static/projects/script-1/frames/scene_001_01.png",
        "/static/projects/script-1/frames/scene_001_02.png",
    ]


def test_phase_images_skips_scene_image_for_video_mode(monkeypatch):
    from pipeline import image_gen as image_gen_mod
    from pipeline import render_phases as render_phases_mod
    from pipeline.render_phases import ExportContext, _phase_images

    content = content_with_scenes(
        Scene(
            id="scene_001",
            narration="A video-backed scene.",
            visual_prompt="Video anchor",
            visual_mode="video",
            video_url="/static/projects/script-1/video/scene_001.mp4",
        )
    )
    monkeypatch.setattr(render_phases_mod, "_reload_content", lambda script_id: content)

    def fail_scene_image(*_args, **_kwargs):
        raise AssertionError("video scenes should not regenerate a normal scene image")

    def fail_scene_frames(**_kwargs):
        raise AssertionError("video scenes should not regenerate frame sequences")

    monkeypatch.setattr(image_gen_mod, "generate_scene_image", fail_scene_image)
    monkeypatch.setattr(image_gen_mod, "generate_scene_frames_v2", fail_scene_frames)

    ctx = ExportContext(
        script_id="script-1",
        job=RenderJob("job-1"),
        scenes=[
            {
                "scene_id": "scene_001",
                "visual_prompt": "Video anchor",
                "is_title_card": False,
                "visual_mode": "video",
                "video_url": "/static/projects/script-1/video/scene_001.mp4",
            }
        ],
        seg_name="Segment",
        total_scenes=1,
        voice_id="voice",
        brand_dict={},
        project_title="Treatment Test",
        title="Segment",
        total_segments=1,
        regen_images=True,
        regen_audio=False,
        regen_fx=False,
        regen_eli=False,
        phase_ranges={"images": (0.0, 1.0)},
    )

    _phase_images(ctx)

    assert ctx.scenes[0]["_image_url"] == ""
    assert ctx.scenes[0]["_frame_urls"] == []


def test_phase_images_skips_scene_image_for_text_only_captions(monkeypatch):
    from pipeline import image_gen as image_gen_mod
    from pipeline import render_phases as render_phases_mod
    from pipeline.render_phases import ExportContext, _phase_images

    content = content_with_scenes(
        Scene(
            id="scene_001",
            narration="A caption-only scene.",
            visual_prompt="",
            visual_mode="captions",
            caption_text="The real cost",
            caption_emphasis="cost",
        )
    )
    monkeypatch.setattr(render_phases_mod, "_reload_content", lambda script_id: content)

    def fail_scene_image(*_args, **_kwargs):
        raise AssertionError("text-only captions should not regenerate a normal scene image")

    monkeypatch.setattr(image_gen_mod, "generate_scene_image", fail_scene_image)

    ctx = ExportContext(
        script_id="script-1",
        job=RenderJob("job-1"),
        scenes=[
            {
                "scene_id": "scene_001",
                "visual_prompt": "",
                "is_title_card": False,
                "visual_mode": "captions",
                "caption_text": "The real cost",
                "caption_emphasis": "cost",
            }
        ],
        seg_name="Segment",
        total_scenes=1,
        voice_id="voice",
        brand_dict={},
        project_title="Treatment Test",
        title="Segment",
        total_segments=1,
        regen_images=True,
        regen_audio=False,
        regen_fx=False,
        regen_eli=False,
        phase_ranges={"images": (0.0, 1.0)},
    )

    _phase_images(ctx)

    assert ctx.scenes[0]["_image_url"] == ""
    assert ctx.scenes[0]["_frame_urls"] == []


def test_apply_visual_treatment_assignments_does_not_promote_normal_scene_to_video():
    content = content_with_scenes(
        scene_with_words("scene_001", "A normal illustrated scene.")
    )

    apply_visual_treatment_assignments(
        content,
        [
            VisualTreatmentAssignment(
                scene_id="scene_001",
                visual_mode="video",
                reasoning="Manual layered-mode review should not create video scenes.",
            )
        ],
    )

    scene = content.all_scenes()[0]
    assert scene.visual_mode == "full_frame"
    assert scene.media_source == "ai"


def test_generate_batch_popup_sequence_skips_scene_image(monkeypatch):
    from pipeline import image_gen as image_gen_mod

    def fail_scene_image(*_args, **_kwargs):
        raise AssertionError("popup_sequence should not generate a full scene image")

    def fake_generate_popup_sequence_cutouts(**kwargs):
        return [
            {
                "id": "scene_001_anchor",
                "type": "image",
                "asset_kind": "cutout",
                "image_url": "/static/projects/script-1/popup_crops/scene_001/anchor_cutout.png",
            },
            {
                **kwargs["layers"][0],
                "asset_kind": "cutout",
                "image_url": "/static/projects/script-1/popup_crops/scene_001/crop_02_message.png",
            },
        ]

    monkeypatch.setattr(image_gen_mod, "generate_scene_image", fail_scene_image)
    monkeypatch.setattr(image_gen_mod, "generate_popup_sequence_cutouts", fake_generate_popup_sequence_cutouts)

    results = image_gen_mod.generate_batch(
        [
            {
                "scene_id": "scene_001",
                "visual_prompt": "A character with popup bubbles.",
                "visual_treatment": "popup_sequence",
                "visual_layers": [
                    {
                        "id": "message",
                        "type": "image",
                        "asset_kind": "panel",
                        "prompt": "message bubble",
                    }
                ],
            }
        ],
        script_id="script-1",
    )

    assert results[0]["image_url"] is None
    assert results[0]["frame_urls"] == []
    assert results[0]["visual_layers"][0]["id"] == "scene_001_anchor"

    no_layer_results = image_gen_mod.generate_batch(
        [
            {
                "scene_id": "scene_002",
                "visual_prompt": "A character with popup bubbles.",
                "visual_treatment": "popup_sequence",
                "visual_layers": [],
            }
        ],
        script_id="script-1",
    )

    assert no_layer_results[0]["image_url"] is None
    assert no_layer_results[0]["frame_urls"] == []
    assert no_layer_results[0].get("visual_layers", []) == []


def test_generate_batch_captions_without_prompt_skips_scene_image(monkeypatch):
    from pipeline import image_gen as image_gen_mod

    def fail_generate_scene_image(**_kwargs):
        raise AssertionError("text-only captions should not generate a scene image")

    monkeypatch.setattr(image_gen_mod, "generate_scene_image", fail_generate_scene_image)

    result = image_gen_mod.generate_scene_visual(
        {
            "scene_id": "scene_001",
            "visual_mode": "captions",
            "visual_prompt": "",
            "caption_text": "The real cost",
            "caption_emphasis": "real",
            "media_source": "ai",
            "visual_treatment": "full_frame",
            "frame_directives": [],
            "contains_person": False,
        },
        script_id="script",
    )

    assert result["scene_id"] == "scene_001"
    assert result["image_url"] is None
    assert result["frame_urls"] == []
    assert result["prompt_used"] is None
    assert result["error"] is None


def test_generate_batch_captions_with_prompt_uses_single_scene_image(monkeypatch):
    from pipeline import image_gen as image_gen_mod

    calls = []

    def fake_generate_scene_image(**kwargs):
        calls.append(kwargs)
        return "/static/projects/script/images/scene_001.png", kwargs["visual_prompt"], {"source_type": "ai_generated"}

    monkeypatch.setattr(image_gen_mod, "generate_scene_image", fake_generate_scene_image)

    result = image_gen_mod.generate_scene_visual(
        {
            "scene_id": "scene_001",
            "visual_mode": "captions",
            "visual_prompt": "[REACTION] A worried shopper holding a receipt.",
            "caption_text": "Falling behind",
            "caption_emphasis": "behind",
            "media_source": "ai",
            "visual_treatment": "full_frame",
            "frame_directives": [],
            "contains_person": True,
        },
        script_id="script",
    )

    assert len(calls) == 1
    assert result["image_url"] == "/static/projects/script/images/scene_001.png"
    assert result["video_url"] == ""


def test_generate_batch_flipflop_routes_to_cutout_assets(monkeypatch):
    from pipeline import image_gen as image_gen_mod

    def fail_scene_image(*_args, **_kwargs):
        raise AssertionError("flipflop should not generate a full scene image")

    def fail_panel_generation(*_args, **_kwargs):
        raise AssertionError("flipflop cutout layers should not use panel generation")

    def fake_generate_flipflop_cutouts(**kwargs):
        assert kwargs["scene_id"] == "scene_001"
        assert kwargs["script_id"] == "script-1"
        return [
            {**kwargs["layers"][0], "asset_kind": "cutout", "image_url": "/static/projects/script-1/flipflop_cutouts/scene_001/state_a.png"},
            {**kwargs["layers"][1], "asset_kind": "cutout", "image_url": "/static/projects/script-1/flipflop_cutouts/scene_001/state_b.png"},
        ]

    monkeypatch.setattr(image_gen_mod, "generate_scene_image", fail_scene_image)
    monkeypatch.setattr(image_gen_mod, "generate_visual_layer_panels", fail_panel_generation)
    monkeypatch.setattr(image_gen_mod, "generate_flipflop_cutouts", fake_generate_flipflop_cutouts)

    results = image_gen_mod.generate_batch(
        [
            {
                "scene_id": "scene_001",
                "visual_prompt": "A character changes expression.",
                "visual_treatment": "flipflop",
                "visual_layers": [
                    {
                        "id": "state_a",
                        "type": "image",
                        "asset_kind": "cutout",
                        "prompt": "state A",
                    },
                    {
                        "id": "state_b",
                        "type": "image",
                        "asset_kind": "cutout",
                        "prompt": "state B",
                    },
                ],
            }
        ],
        script_id="script-1",
    )

    assert results[0]["image_url"] is None
    assert results[0]["frame_urls"] == []
    assert [layer["id"] for layer in results[0]["visual_layers"]] == ["state_a", "state_b"]
    assert [layer["asset_kind"] for layer in results[0]["visual_layers"]] == ["cutout", "cutout"]


def test_generate_batch_flipflop_with_empty_layers_synthesizes_assets(monkeypatch):
    from pipeline import image_gen as image_gen_mod

    def fake_generate_flipflop_cutouts(**kwargs):
        assert kwargs["layers"] == []
        assert kwargs["scene_narration"] == "The cashier blinks in front of the fryer."
        return [
            {"id": "scene_001_background", "type": "image", "asset_kind": "full_frame", "image_url": "/static/bg.png"},
            {"id": "scene_001_state_a", "type": "image", "asset_kind": "cutout", "image_url": "/static/a.png"},
            {"id": "scene_001_state_b", "type": "image", "asset_kind": "cutout", "image_url": "/static/b.png"},
        ]

    monkeypatch.setattr(image_gen_mod, "generate_flipflop_cutouts", fake_generate_flipflop_cutouts)

    results = image_gen_mod.generate_batch(
        [
            {
                "scene_id": "scene_001",
                "narration": "The cashier blinks in front of the fryer.",
                "visual_prompt": "Cartoon cashier character, no props, no background elements.",
                "visual_treatment": "flipflop",
                "visual_layers": [],
            }
        ],
        script_id="script-1",
    )

    assert results[0]["image_url"] is None
    assert [layer["asset_kind"] for layer in results[0]["visual_layers"]] == ["full_frame", "cutout", "cutout"]


def test_generate_batch_persists_request_visual_treatment(monkeypatch):
    from api import visuals as visuals_api
    from api.visuals import BatchScene, GenerateBatchRequest

    engine = _build_test_engine()
    script_id = "batch-request-treatment"
    content = content_with_scenes(
        Scene(
            id="scene_001",
            narration="Before and after.",
            visual_prompt="Person changes expression.",
            visual_treatment="full_frame",
            image_url="/static/projects/batch-request-treatment/images/stale.png",
        )
    )

    monkeypatch.setattr(visuals_api, "_require_character_reference_ready", lambda session, script_id: None)
    monkeypatch.setattr(
        visuals_api,
        "generate_batch",
        lambda scenes, script_id, **_kwargs: [
            {
                "scene_id": scenes[0]["scene_id"],
                "image_url": None,
                "frame_urls": [],
                "video_url": None,
                "prompt_used": None,
                "visual_source_metadata": None,
                "visual_layers": [
                    {**scenes[0]["visual_layers"][0], "image_url": f"/static/projects/{script_id}/images/state_a.png"},
                    {**scenes[0]["visual_layers"][1], "image_url": f"/static/projects/{script_id}/images/state_b.png"},
                ],
                "error": None,
            }
        ],
    )

    with Session(engine) as session:
        session.add(
            Script(
                id=script_id,
                brand_id="brand",
                topic_title="Treatment Test",
                script_json=content.model_dump_json(),
            )
        )
        session.commit()

        visuals_api.generate_visual_batch(
            GenerateBatchRequest(
                script_id=script_id,
                scenes=[
                    BatchScene(
                        scene_id="scene_001",
                        visual_prompt="Person changes expression.",
                        visual_treatment="flipflop",
                        visual_layers=[
                            {"id": "state_a", "type": "image", "asset_kind": "panel", "prompt": "state A"},
                            {"id": "state_b", "type": "image", "asset_kind": "panel", "prompt": "state B"},
                        ],
                    )
                ],
            ),
            session,
        )

        stored = session.get(Script, script_id)
        assert stored is not None
        stored_scene = ScriptContent.model_validate_json(stored.script_json).segments[0].scenes[0]

    assert stored_scene.visual_treatment == "flipflop"
    assert stored_scene.image_url == ""
    assert stored_scene.frame_urls == []
    assert [layer.id for layer in stored_scene.visual_layers] == ["state_a", "state_b"]


def test_generate_batch_persists_request_visual_mode_without_legacy_treatment(monkeypatch):
    from api import visuals as visuals_api
    from api.visuals import BatchScene, GenerateBatchRequest

    engine = _build_test_engine()
    script_id = "batch-request-mode"
    content = content_with_scenes(
        Scene(
            id="scene_001",
            narration="First this, then that.",
            visual_prompt="Person gestures at a list.",
            visual_treatment="full_frame",
            image_url="/static/projects/batch-request-mode/images/stale.png",
        )
    )

    monkeypatch.setattr(visuals_api, "_require_character_reference_ready", lambda session, script_id: None)
    monkeypatch.setattr(
        visuals_api,
        "generate_batch",
        lambda scenes, script_id, **_kwargs: [
            {
                "scene_id": scenes[0]["scene_id"],
                "image_url": None,
                "frame_urls": [],
                "video_url": None,
                "prompt_used": None,
                "visual_source_metadata": None,
                "visual_layers": [
                    {**scenes[0]["visual_layers"][0], "image_url": f"/static/projects/{script_id}/images/item_1.png"},
                    {**scenes[0]["visual_layers"][1], "image_url": f"/static/projects/{script_id}/images/item_2.png"},
                ],
                "error": None,
            }
        ],
    )

    with Session(engine) as session:
        session.add(
            Script(
                id=script_id,
                brand_id="brand",
                topic_title="Mode Test",
                script_json=content.model_dump_json(),
            )
        )
        session.commit()

        visuals_api.generate_visual_batch(
            GenerateBatchRequest(
                script_id=script_id,
                scenes=[
                    BatchScene(
                        scene_id="scene_001",
                        visual_prompt="Person gestures at a list.",
                        visual_mode="popup_sequence",
                        visual_layers=[
                            {"id": "item_1", "type": "image", "asset_kind": "cutout", "prompt": "item 1"},
                            {"id": "item_2", "type": "image", "asset_kind": "cutout", "prompt": "item 2"},
                        ],
                    )
                ],
            ),
            session,
        )

        stored = session.get(Script, script_id)
        assert stored is not None
        stored_scene = ScriptContent.model_validate_json(stored.script_json).segments[0].scenes[0]

    assert stored_scene.visual_mode == "popup_sequence"
    assert stored_scene.visual_treatment == "popup_sequence"
    assert stored_scene.media_source == "ai"
    assert stored_scene.image_url == ""
    assert stored_scene.frame_urls == []
    assert [layer.id for layer in stored_scene.visual_layers] == ["item_1", "item_2"]


def test_generate_batch_visual_mode_wins_over_conflicting_legacy_treatment(monkeypatch):
    from api import visuals as visuals_api
    from api.visuals import BatchScene, GenerateBatchRequest

    engine = _build_test_engine()
    script_id = "batch-conflicting-mode"
    content = content_with_scenes(
        Scene(
            id="scene_001",
            narration="First this, then that.",
            visual_prompt="Person gestures at a list.",
            visual_treatment="full_frame",
            image_url="/static/projects/batch-conflicting-mode/images/stale.png",
        )
    )
    captured_scenes = []

    def fake_generate_batch(scenes, script_id, **_kwargs):
        captured_scenes.extend(scenes)
        return [
            {
                "scene_id": scenes[0]["scene_id"],
                "image_url": None,
                "frame_urls": [],
                "video_url": None,
                "prompt_used": None,
                "visual_source_metadata": None,
                "visual_layers": [
                    {**scenes[0]["visual_layers"][0], "image_url": f"/static/projects/{script_id}/images/item_1.png"},
                    {**scenes[0]["visual_layers"][1], "image_url": f"/static/projects/{script_id}/images/item_2.png"},
                ],
                "error": None,
            }
        ]

    monkeypatch.setattr(visuals_api, "_require_character_reference_ready", lambda session, script_id: None)
    monkeypatch.setattr(visuals_api, "generate_batch", fake_generate_batch)

    with Session(engine) as session:
        session.add(
            Script(
                id=script_id,
                brand_id="brand",
                topic_title="Mode Test",
                script_json=content.model_dump_json(),
            )
        )
        session.commit()

        visuals_api.generate_visual_batch(
            GenerateBatchRequest(
                script_id=script_id,
                scenes=[
                    BatchScene(
                        scene_id="scene_001",
                        visual_prompt="Person gestures at a list.",
                        visual_mode="popup_sequence",
                        visual_treatment="full_frame",
                        visual_layers=[
                            {"id": "item_1", "type": "image", "asset_kind": "cutout", "prompt": "item 1"},
                            {"id": "item_2", "type": "image", "asset_kind": "cutout", "prompt": "item 2"},
                        ],
                    )
                ],
            ),
            session,
        )

        stored = session.get(Script, script_id)
        assert stored is not None
        stored_scene = ScriptContent.model_validate_json(stored.script_json).segments[0].scenes[0]

    assert captured_scenes[0]["visual_mode"] == "popup_sequence"
    assert stored_scene.visual_mode == "popup_sequence"
    assert stored_scene.visual_treatment == "popup_sequence"
    assert stored_scene.image_url == ""
    assert [layer.id for layer in stored_scene.visual_layers] == ["item_1", "item_2"]


def test_generate_batch_full_frame_mode_wins_over_conflicting_legacy_treatment(monkeypatch):
    from api import visuals as visuals_api
    from api.visuals import BatchScene, GenerateBatchRequest

    engine = _build_test_engine()
    script_id = "batch-full-frame-conflict"
    content = content_with_scenes(
        Scene(
            id="scene_001",
            narration="One strong image.",
            visual_prompt="Person in a clean full-frame composition.",
            visual_treatment="popup_sequence",
            visual_layers=[VisualLayer(id="stale_layer", prompt="stale")],
        )
    )
    captured_scenes = []

    def fake_generate_batch(scenes, script_id, **_kwargs):
        captured_scenes.extend(scenes)
        return [
            {
                "scene_id": scenes[0]["scene_id"],
                "image_url": f"/static/projects/{script_id}/images/scene_001.png",
                "frame_urls": [],
                "video_url": None,
                "prompt_used": "prompt",
                "visual_source_metadata": None,
                "visual_layers": [],
                "error": None,
            }
        ]

    monkeypatch.setattr(visuals_api, "_require_character_reference_ready", lambda session, script_id: None)
    monkeypatch.setattr(visuals_api, "generate_batch", fake_generate_batch)

    with Session(engine) as session:
        session.add(
            Script(
                id=script_id,
                brand_id="brand",
                topic_title="Mode Test",
                script_json=content.model_dump_json(),
            )
        )
        session.commit()

        visuals_api.generate_visual_batch(
            GenerateBatchRequest(
                script_id=script_id,
                scenes=[
                    BatchScene(
                        scene_id="scene_001",
                        visual_prompt="Person in a clean full-frame composition.",
                        visual_mode="full_frame",
                        visual_treatment="popup_sequence",
                        visual_layers=[],
                    )
                ],
            ),
            session,
        )

        stored = session.get(Script, script_id)
        assert stored is not None
        stored_scene = ScriptContent.model_validate_json(stored.script_json).segments[0].scenes[0]

    assert captured_scenes[0]["visual_mode"] == "full_frame"
    assert stored_scene.visual_mode == "full_frame"
    assert stored_scene.visual_treatment == "full_frame"
    assert stored_scene.image_url == f"/static/projects/{script_id}/images/scene_001.png"
    assert stored_scene.visual_layers == []


def test_generate_visual_persists_generated_visual_layers(monkeypatch):
    from api import visuals as visuals_api
    from api.visuals import GenerateVisualRequest

    engine = _build_test_engine()
    script_id = "regular-visual-panels"
    content = content_with_scenes(
        Scene(
            id="scene_001",
            narration="Panel scene.",
            visual_prompt="Panel",
            contains_person=True,
            visual_treatment="popup_sequence",
            visual_layers=[VisualLayer(id="panel_1", prompt="Panel prompt")],
        )
    )

    captured = {}
    monkeypatch.setattr(visuals_api, "_require_character_reference_ready", lambda session, script_id: None)
    monkeypatch.setattr(
        visuals_api,
        "generate_scene_image",
        lambda **_kwargs: (_ for _ in ()).throw(AssertionError("layered animation treatments should not generate scene images")),
    )

    def fake_generate_popup_sequence_cutouts(*, scene_id, layers, script_id, scene_prompt, **kwargs):
        captured["scene_id"] = scene_id
        captured["layers"] = layers
        captured["scene_prompt"] = scene_prompt
        captured["contains_person"] = kwargs.get("contains_person")
        return [
            {
                **layers[0],
                "asset_kind": "cutout",
                "image_url": "/static/projects/regular-visual-panels/popup_crops/scene_001/crop_02_panel_prompt.png",
            }
        ]

    monkeypatch.setattr(visuals_api, "generate_popup_sequence_cutouts", fake_generate_popup_sequence_cutouts)

    with Session(engine) as session:
        session.add(
            Script(
                id=script_id,
                brand_id="brand",
                topic_title="Treatment Test",
                script_json=content.model_dump_json(),
            )
        )
        session.commit()

        response = visuals_api.generate_visual(
            GenerateVisualRequest(
                script_id=script_id,
                scene_id="scene_001",
                visual_prompt="Panel",
                contains_person=False,
            ),
            session,
        )

        stored = session.get(Script, script_id)
        assert stored is not None
        stored_content = ScriptContent.model_validate_json(stored.script_json)

    assert captured["scene_id"] == "scene_001"
    assert captured["contains_person"] is True
    assert captured["layers"][0]["prompt"] == "Panel prompt"
    assert captured["scene_prompt"] == "Panel"
    assert response.visual_layers[0]["image_url"] == "/static/projects/regular-visual-panels/popup_crops/scene_001/crop_02_panel_prompt.png"
    assert response.image_url == ""
    stored_scene = stored_content.segments[0].scenes[0]
    assert stored_scene.image_url == ""
    assert stored_scene.frame_urls == []
    assert stored_content.segments[0].scenes[0].visual_layers[0].image_url == (
        "/static/projects/regular-visual-panels/popup_crops/scene_001/crop_02_panel_prompt.png"
    )


def test_generate_visual_persists_request_visual_treatment(monkeypatch):
    from api import visuals as visuals_api
    from api.visuals import GenerateVisualRequest

    engine = _build_test_engine()
    script_id = "request-treatment-panels"
    content = content_with_scenes(
        Scene(
            id="scene_001",
            narration="Before and after.",
            visual_prompt="Person changes expression.",
            visual_treatment="full_frame",
            image_url="/static/projects/request-treatment-panels/images/stale.png",
        )
    )

    monkeypatch.setattr(visuals_api, "_require_character_reference_ready", lambda session, script_id: None)
    monkeypatch.setattr(
        visuals_api,
        "generate_scene_image",
        lambda **_kwargs: (_ for _ in ()).throw(AssertionError("flipflop should not generate scene images")),
    )
    monkeypatch.setattr(
        visuals_api,
        "generate_flipflop_cutouts",
        lambda scene_id, layers, script_id, **_kwargs: [
            {**layers[0], "asset_kind": "cutout", "image_url": f"/static/projects/{script_id}/flipflop_cutouts/{scene_id}/state_a.png"},
            {**layers[1], "asset_kind": "cutout", "image_url": f"/static/projects/{script_id}/flipflop_cutouts/{scene_id}/state_b.png"},
        ],
    )

    with Session(engine) as session:
        session.add(
            Script(
                id=script_id,
                brand_id="brand",
                topic_title="Treatment Test",
                script_json=content.model_dump_json(),
            )
        )
        session.commit()

        visuals_api.generate_visual(
            GenerateVisualRequest(
                script_id=script_id,
                scene_id="scene_001",
                visual_prompt="Person changes expression.",
                visual_treatment="flipflop",
                visual_layers=[
                    {"id": "state_a", "type": "image", "asset_kind": "panel", "prompt": "state A"},
                    {"id": "state_b", "type": "image", "asset_kind": "panel", "prompt": "state B"},
                ],
            ),
            session,
        )

        stored = session.get(Script, script_id)
        assert stored is not None
        stored_scene = ScriptContent.model_validate_json(stored.script_json).segments[0].scenes[0]

    assert stored_scene.visual_treatment == "flipflop"
    assert stored_scene.image_url == ""
    assert stored_scene.frame_urls == []
    assert [layer.id for layer in stored_scene.visual_layers] == ["state_a", "state_b"]
    assert [layer.asset_kind for layer in stored_scene.visual_layers] == ["cutout", "cutout"]
    assert [layer.image_url for layer in stored_scene.visual_layers] == [
        "/static/projects/request-treatment-panels/flipflop_cutouts/scene_001/state_a.png",
        "/static/projects/request-treatment-panels/flipflop_cutouts/scene_001/state_b.png",
    ]


def test_generate_visual_preserves_explicit_stat_card_and_generates_icon_layer(monkeypatch):
    from api import visuals as visuals_api
    from api.visuals import GenerateVisualRequest

    engine = _build_test_engine()
    script_id = "request-stat-card"
    content = content_with_scenes(
        Scene(
            id="scene_001",
            narration="The number jumps to eighty percent.",
            visual_prompt="Warning icon over a bold statistic.",
            visual_treatment="full_frame",
            image_url="/static/projects/request-stat-card/images/stale.png",
        )
    )

    captured = {}
    monkeypatch.setattr(visuals_api, "_require_character_reference_ready", lambda session, script_id: None)
    monkeypatch.setattr(
        visuals_api,
        "generate_scene_image",
        lambda **_kwargs: (_ for _ in ()).throw(AssertionError("stat_card should not generate scene images")),
    )

    def fake_generate_stat_card_cutout(**kwargs):
        captured.update(kwargs)
        return [
            {
                **kwargs["layers"][0],
                "asset_kind": "cutout",
                "image_url": "/static/projects/request-stat-card/stat_cards/scene_001/icon_cutout.png",
            }
        ]

    monkeypatch.setattr(visuals_api, "generate_stat_card_cutout", fake_generate_stat_card_cutout)

    with Session(engine) as session:
        session.add(
            Script(
                id=script_id,
                brand_id="brand",
                topic_title="Treatment Test",
                script_json=content.model_dump_json(),
            )
        )
        session.commit()

        response = visuals_api.generate_visual(
            GenerateVisualRequest(
                script_id=script_id,
                scene_id="scene_001",
                visual_prompt="Warning icon over a bold statistic.",
                visual_mode="stat_card",
                visual_layers=[
                    {"id": "scene_001_stat_icon", "type": "image", "asset_kind": "cutout", "prompt": "warning icon"},
                ],
            ),
            session,
        )

        stored = session.get(Script, script_id)
        assert stored is not None
        stored_scene = ScriptContent.model_validate_json(stored.script_json).segments[0].scenes[0]

    assert captured["scene_id"] == "scene_001"
    assert captured["script_id"] == script_id
    assert captured["scene_prompt"] == "Warning icon over a bold statistic."
    assert [layer["id"] for layer in captured["layers"]] == ["scene_001_stat_icon"]
    assert response.image_url == ""
    assert response.frame_urls == []
    assert response.visual_layers[0]["image_url"] == "/static/projects/request-stat-card/stat_cards/scene_001/icon_cutout.png"
    assert stored_scene.visual_treatment == "stat_card"
    assert stored_scene.image_url == ""
    assert stored_scene.frame_urls == []
    assert stored_scene.video_url == ""
    assert [layer.id for layer in stored_scene.visual_layers] == ["scene_001_stat_icon"]
    assert stored_scene.visual_layers[0].image_url == "/static/projects/request-stat-card/stat_cards/scene_001/icon_cutout.png"


def test_generate_visual_stat_card_mode_change_does_not_reuse_flipflop_layers(monkeypatch):
    from api import visuals as visuals_api
    from api.visuals import GenerateVisualRequest

    engine = _build_test_engine()
    script_id = "request-stat-card-mode-change"
    content = content_with_scenes(
        Scene(
            id="scene_001",
            narration="The number jumps to eighty percent.",
            visual_prompt="Warning icon over a bold statistic.",
            visual_treatment="flipflop",
            image_url="",
            visual_layers=[
                VisualLayer(id="state_a", asset_kind="cutout", prompt="state A", image_url="/static/projects/old/state_a.png"),
                VisualLayer(id="state_b", asset_kind="cutout", prompt="state B", image_url="/static/projects/old/state_b.png"),
            ],
        )
    )

    monkeypatch.setattr(visuals_api, "_require_character_reference_ready", lambda session, script_id: None)
    monkeypatch.setattr(
        visuals_api,
        "generate_scene_image",
        lambda **_kwargs: (_ for _ in ()).throw(AssertionError("stat_card should not generate scene images")),
    )
    monkeypatch.setattr(
        visuals_api,
        "generate_stat_card_cutout",
        lambda **_kwargs: (_ for _ in ()).throw(AssertionError("stat_card mode change should not reuse flipflop layers")),
    )

    with Session(engine) as session:
        session.add(
            Script(
                id=script_id,
                brand_id="brand",
                topic_title="Treatment Test",
                script_json=content.model_dump_json(),
            )
        )
        session.commit()

        response = visuals_api.generate_visual(
            GenerateVisualRequest(
                script_id=script_id,
                scene_id="scene_001",
                visual_prompt="Warning icon over a bold statistic.",
                visual_mode="stat_card",
            ),
            session,
        )

        stored = session.get(Script, script_id)
        assert stored is not None
        stored_scene = ScriptContent.model_validate_json(stored.script_json).segments[0].scenes[0]

    assert response.image_url == ""
    assert response.frame_urls == []
    assert response.visual_layers == []
    assert stored_scene.visual_treatment == "stat_card"
    assert stored_scene.image_url == ""
    assert stored_scene.frame_urls == []
    assert stored_scene.visual_layers == []


def test_generate_visual_preserves_multi_frame_mode_for_frame_directives(monkeypatch):
    from api import visuals as visuals_api
    from api.visuals import GenerateVisualRequest

    engine = _build_test_engine()
    script_id = "multi-frame-visual"
    content = content_with_scenes(
        Scene(
            id="scene_001",
            narration="First this, then that.",
            visual_prompt="Several examples.",
            visual_mode="multi_frame",
        )
    )

    monkeypatch.setattr(visuals_api, "_require_character_reference_ready", lambda session, script_id: None)
    monkeypatch.setattr(
        visuals_api,
        "generate_scene_frames_v2",
        lambda **_kwargs: [
            (
                f"/static/projects/{script_id}/images/scene_001_0.png",
                "Frame prompt",
                {"provider": "fake"},
            )
        ],
    )

    with Session(engine) as session:
        session.add(
            Script(
                id=script_id,
                brand_id="brand",
                topic_title="Multi Frame Test",
                script_json=content.model_dump_json(),
            )
        )
        session.commit()

        visuals_api.generate_visual(
            GenerateVisualRequest(
                script_id=script_id,
                scene_id="scene_001",
                visual_prompt="Several examples.",
                visual_mode="multi_frame",
                frame_directives=[
                    {
                        "prompt": "Frame prompt",
                        "source": "ai_generated",
                        "transition": "cut",
                        "reference_previous": False,
                    }
                ],
            ),
            session,
        )

        stored = session.get(Script, script_id)
        assert stored is not None
        stored_scene = ScriptContent.model_validate_json(stored.script_json).segments[0].scenes[0]

    assert stored_scene.visual_mode == "multi_frame"
    assert stored_scene.media_source == "ai"
    assert stored_scene.visual_treatment == "full_frame"
    assert stored_scene.frame_urls == [f"/static/projects/{script_id}/images/scene_001_0.png"]


def test_generate_visual_preserves_continuous_mode_for_single_image_path(monkeypatch):
    from api import visuals as visuals_api
    from api.visuals import GenerateVisualRequest

    engine = _build_test_engine()
    script_id = "continuous-visual"
    content = content_with_scenes(
        Scene(
            id="scene_001",
            narration="The crack slowly spreads.",
            visual_prompt="A spreading crack.",
            visual_mode="continuous",
        )
    )

    monkeypatch.setattr(visuals_api, "_require_character_reference_ready", lambda session, script_id: None)
    monkeypatch.setattr(
        visuals_api,
        "generate_scene_image",
        lambda **_kwargs: (
            f"/static/projects/{script_id}/images/scene_001.png",
            "Image prompt",
            {"provider": "fake"},
        ),
    )

    with Session(engine) as session:
        session.add(
            Script(
                id=script_id,
                brand_id="brand",
                topic_title="Continuous Test",
                script_json=content.model_dump_json(),
            )
        )
        session.commit()

        visuals_api.generate_visual(
            GenerateVisualRequest(
                script_id=script_id,
                scene_id="scene_001",
                visual_prompt="A spreading crack.",
                visual_mode="continuous",
            ),
            session,
        )

        stored = session.get(Script, script_id)
        assert stored is not None
        stored_scene = ScriptContent.model_validate_json(stored.script_json).segments[0].scenes[0]

    assert stored_scene.visual_mode == "continuous"
    assert stored_scene.media_source == "ai"
    assert stored_scene.visual_treatment == "full_frame"
    assert stored_scene.image_url == f"/static/projects/{script_id}/images/scene_001.png"


def test_generate_visual_explicit_full_frame_overrides_stored_multi_frame(monkeypatch):
    from api import visuals as visuals_api
    from api.visuals import GenerateVisualRequest

    engine = _build_test_engine()
    script_id = "full-frame-over-multi"
    content = content_with_scenes(
        Scene(
            id="scene_001",
            narration="Several examples.",
            visual_prompt="Several examples.",
            visual_mode="multi_frame",
        )
    )

    monkeypatch.setattr(visuals_api, "_require_character_reference_ready", lambda session, script_id: None)
    monkeypatch.setattr(
        visuals_api,
        "generate_scene_image",
        lambda **_kwargs: (
            f"/static/projects/{script_id}/images/scene_001.png",
            "Image prompt",
            {"provider": "fake"},
        ),
    )

    with Session(engine) as session:
        session.add(
            Script(
                id=script_id,
                brand_id="brand",
                topic_title="Full Frame Test",
                script_json=content.model_dump_json(),
            )
        )
        session.commit()

        visuals_api.generate_visual(
            GenerateVisualRequest(
                script_id=script_id,
                scene_id="scene_001",
                visual_prompt="Single image.",
                visual_mode="full_frame",
            ),
            session,
        )

        stored = session.get(Script, script_id)
        assert stored is not None
        stored_scene = ScriptContent.model_validate_json(stored.script_json).segments[0].scenes[0]

    assert stored_scene.visual_mode == "full_frame"
    assert stored_scene.visual_treatment == "full_frame"
    assert stored_scene.image_url == f"/static/projects/{script_id}/images/scene_001.png"


def test_generate_visual_explicit_full_frame_overrides_stored_continuous(monkeypatch):
    from api import visuals as visuals_api
    from api.visuals import GenerateVisualRequest

    engine = _build_test_engine()
    script_id = "full-frame-over-continuous"
    content = content_with_scenes(
        Scene(
            id="scene_001",
            narration="The crack spreads.",
            visual_prompt="A spreading crack.",
            visual_mode="continuous",
        )
    )

    monkeypatch.setattr(visuals_api, "_require_character_reference_ready", lambda session, script_id: None)
    monkeypatch.setattr(
        visuals_api,
        "generate_scene_image",
        lambda **_kwargs: (
            f"/static/projects/{script_id}/images/scene_001.png",
            "Image prompt",
            {"provider": "fake"},
        ),
    )

    with Session(engine) as session:
        session.add(
            Script(
                id=script_id,
                brand_id="brand",
                topic_title="Full Frame Test",
                script_json=content.model_dump_json(),
            )
        )
        session.commit()

        visuals_api.generate_visual(
            GenerateVisualRequest(
                script_id=script_id,
                scene_id="scene_001",
                visual_prompt="Single image.",
                visual_mode="full_frame",
            ),
            session,
        )

        stored = session.get(Script, script_id)
        assert stored is not None
        stored_scene = ScriptContent.model_validate_json(stored.script_json).segments[0].scenes[0]

    assert stored_scene.visual_mode == "full_frame"
    assert stored_scene.visual_treatment == "full_frame"
    assert stored_scene.image_url == f"/static/projects/{script_id}/images/scene_001.png"


def test_generate_visual_explicit_full_frame_overrides_stored_layered_mode(monkeypatch):
    from api import visuals as visuals_api
    from api.visuals import GenerateVisualRequest

    engine = _build_test_engine()
    script_id = "full-frame-over-layered"
    content = content_with_scenes(
        Scene(
            id="scene_001",
            narration="A layered scene.",
            visual_prompt="Layered scene.",
            visual_mode="popup_sequence",
            visual_layers=[VisualLayer(id="panel_1", prompt="Panel")],
        )
    )

    monkeypatch.setattr(visuals_api, "_require_character_reference_ready", lambda session, script_id: None)
    monkeypatch.setattr(
        visuals_api,
        "generate_popup_sequence_cutouts",
        lambda **_kwargs: (_ for _ in ()).throw(AssertionError("explicit full_frame should not generate layered assets")),
    )
    monkeypatch.setattr(
        visuals_api,
        "generate_scene_image",
        lambda **_kwargs: (
            f"/static/projects/{script_id}/images/scene_001.png",
            "Image prompt",
            {"provider": "fake"},
        ),
    )

    with Session(engine) as session:
        session.add(
            Script(
                id=script_id,
                brand_id="brand",
                topic_title="Full Frame Test",
                script_json=content.model_dump_json(),
            )
        )
        session.commit()

        visuals_api.generate_visual(
            GenerateVisualRequest(
                script_id=script_id,
                scene_id="scene_001",
                visual_prompt="Single image.",
                visual_mode="full_frame",
            ),
            session,
        )

        stored = session.get(Script, script_id)
        assert stored is not None
        stored_scene = ScriptContent.model_validate_json(stored.script_json).segments[0].scenes[0]

    assert stored_scene.visual_mode == "full_frame"
    assert stored_scene.visual_treatment == "full_frame"
    assert stored_scene.image_url == f"/static/projects/{script_id}/images/scene_001.png"
    assert stored_scene.visual_layers == []


def test_generate_visual_routes_popup_sequence_to_cutout_assets(monkeypatch):
    from api import visuals as visuals_api

    content = content_with_scenes(
        Scene(
            id="scene_001",
            narration="One might be a message, one might be a reward, and one might be nothing.",
            visual_prompt="Person holding phone with three notification bubbles.",
            contains_person=True,
            visual_treatment="popup_sequence",
            visual_layers=[
                VisualLayer(id="bubble_1", prompt="chat bubble", placement="left", enter_at_seconds=0.5),
                VisualLayer(id="bubble_2", prompt="gift icon", placement="center", enter_at_seconds=1.0),
                VisualLayer(id="bubble_3", prompt="empty bubble", placement="right", enter_at_seconds=1.5),
            ],
        )
    )

    captured = {}

    def fail_panel_generation(*_args, **_kwargs):
        raise AssertionError("popup_sequence should not use panel generation")

    def fake_generate_popup_sequence_cutouts(**kwargs):
        captured.update(kwargs)
        return [
            {
                "id": "scene_001_anchor",
                "type": "image",
                "asset_kind": "cutout",
                "image_url": "/static/projects/script-1/popup_crops/scene_001/anchor_cutout.png",
                "placement": "center",
                "enter_at_seconds": 0.0,
                "animation": "none",
            },
            {
                **kwargs["layers"][0],
                "asset_kind": "cutout",
                "image_url": "/static/projects/script-1/popup_crops/scene_001/crop_02_chat_bubble.png",
            },
        ]

    monkeypatch.setattr(visuals_api, "generate_visual_layer_panels", fail_panel_generation)
    monkeypatch.setattr(visuals_api, "generate_popup_sequence_cutouts", fake_generate_popup_sequence_cutouts)

    layers = visuals_api._generate_scene_visual_layers(
        content=content,
        scene_id="scene_001",
        script_id="script-1",
        width=1920,
        height=1080,
    )

    assert captured["scene_prompt"] == "Person holding phone with three notification bubbles."
    assert captured["contains_person"] is True
    assert [layer["asset_kind"] for layer in layers] == ["cutout", "cutout"]
    assert layers[0]["id"] == "scene_001_anchor"


def test_generate_visual_routes_flipflop_to_cutout_assets(monkeypatch):
    from api import visuals as visuals_api

    content = content_with_scenes(
        Scene(
            id="scene_001",
            narration="Before and after.",
            visual_prompt="Person changes expression.",
            visual_treatment="flipflop",
            visual_layers=[
                VisualLayer(id="state_a", asset_kind="cutout", prompt="state A"),
                VisualLayer(id="state_b", asset_kind="cutout", prompt="state B"),
            ],
        )
    )

    captured = {}

    def fail_panel_generation(*_args, **_kwargs):
        raise AssertionError("flipflop cutout layers should not use panel generation")

    def fake_generate_flipflop_cutouts(**kwargs):
        captured.update(kwargs)
        return [
            {**kwargs["layers"][0], "asset_kind": "cutout", "image_url": "/static/projects/script-1/flipflop_cutouts/scene_001/state_a.png"},
            {**kwargs["layers"][1], "asset_kind": "cutout", "image_url": "/static/projects/script-1/flipflop_cutouts/scene_001/state_b.png"},
        ]

    monkeypatch.setattr(visuals_api, "generate_visual_layer_panels", fail_panel_generation)
    monkeypatch.setattr(visuals_api, "generate_flipflop_cutouts", fake_generate_flipflop_cutouts)

    layers = visuals_api._generate_scene_visual_layers(
        content=content,
        scene_id="scene_001",
        script_id="script-1",
        width=1920,
        height=1080,
    )

    assert captured["scene_id"] == "scene_001"
    assert captured["scene_prompt"] == "Person changes expression."
    assert [layer["id"] for layer in captured["layers"]] == ["state_a", "state_b"]
    assert [layer["image_url"] for layer in layers] == [
        "/static/projects/script-1/flipflop_cutouts/scene_001/state_a.png",
        "/static/projects/script-1/flipflop_cutouts/scene_001/state_b.png",
    ]


def test_generate_visual_routes_empty_flipflop_layers_to_synthesized_assets(monkeypatch):
    from api import visuals as visuals_api

    content = content_with_scenes(
        Scene(
            id="scene_001",
            narration="The cashier blinks while the fryer screams behind him.",
            visual_prompt="Cartoon cashier character, no props, no background elements.",
            visual_treatment="flipflop",
            visual_layers=[],
        )
    )

    captured = {}

    def fake_generate_flipflop_cutouts(**kwargs):
        captured.update(kwargs)
        return [
            {"id": "scene_001_background", "type": "image", "asset_kind": "full_frame", "image_url": "/static/bg.png"},
            {"id": "scene_001_state_a", "type": "image", "asset_kind": "cutout", "image_url": "/static/a.png"},
            {"id": "scene_001_state_b", "type": "image", "asset_kind": "cutout", "image_url": "/static/b.png"},
        ]

    monkeypatch.setattr(visuals_api, "generate_flipflop_cutouts", fake_generate_flipflop_cutouts)

    layers = visuals_api._generate_scene_visual_layers(
        content=content,
        scene_id="scene_001",
        script_id="script-1",
        width=1920,
        height=1080,
    )

    assert captured["layers"] == []
    assert captured["scene_narration"] == "The cashier blinks while the fryer screams behind him."
    assert [layer["asset_kind"] for layer in layers] == ["full_frame", "cutout", "cutout"]


def test_generate_flipflop_cutouts_keys_cutout_layers_and_preserves_non_images(tmp_path, monkeypatch):
    image_gen, char_ref, style_ref = _stub_panel_image_context(monkeypatch, tmp_path)

    monkeypatch.setattr(image_gen, "save_vault_image", lambda **_kwargs: None)
    captured = []

    def fake_generate_image(
        prompt,
        *,
        width,
        height,
        reference_image_path=None,
        style_reference_path=None,
        script_id=None,
        **_kwargs,
    ):
        captured.append(
            {
                "prompt": prompt,
                "width": width,
                "height": height,
                "reference_image_path": reference_image_path,
                "style_reference_path": style_reference_path,
                "script_id": script_id,
            }
        )
        source = tmp_path / f"source-{len(captured)}.png"
        image = Image.new("RGBA", (120, 80), (0, 255, 0, 255))
        draw = ImageDraw.Draw(image)
        draw.rectangle((40, 20, 80, 60), fill=(255, 0, 0, 255))
        image.save(source)
        return str(source)

    monkeypatch.setattr(image_gen, "generate_image", fake_generate_image)

    layers = image_gen.generate_flipflop_cutouts(
        scene_id="scene_001",
        layers=[
            {"id": "state_a", "type": "image", "asset_kind": "panel", "prompt": "State A prompt", "contains_person": True},
            {"id": "label_1", "type": "text", "asset_kind": "text", "text": "overlay"},
            {"id": "state_b", "asset_kind": "panel", "prompt": "State B prompt", "contains_person": True},
        ],
        script_id="script-1",
        scene_prompt="Person changes expression.",
        width=320,
        height=180,
        contains_person=True,
    )

    assert len(captured) == 2
    assert captured[0]["reference_image_path"] is None
    assert captured[1]["reference_image_path"] == char_ref
    assert captured[0]["style_reference_path"] == style_ref
    assert captured[0]["style_reference_path"] == style_ref
    assert captured[1]["style_reference_path"] == style_ref
    assert "[char_ref:" not in captured[0]["prompt"]
    assert "[style_ref:" in captured[0]["prompt"]
    assert "[char_ref:" in captured[1]["prompt"]
    assert "two-cell contact sheet" in captured[1]["prompt"]
    assert "LEFT CELL" in captured[1]["prompt"]
    assert "RIGHT CELL" in captured[1]["prompt"]
    assert "equal-width vertical cells" in captured[1]["prompt"]
    assert "Environment-only static background" in captured[0]["prompt"]
    prompt = captured[1]["prompt"].lower()
    assert "full-bleed" not in prompt
    assert "fill the entire canvas" not in prompt
    assert "edge to edge" not in prompt
    assert "flip-flop animation state cutouts" in prompt
    assert "chroma key background" in prompt
    assert "identical pixel footprint" in prompt
    assert "no zoom" in prompt
    assert "no full background scene" in prompt
    assert {"id": "label_1", "type": "text", "asset_kind": "text", "text": "overlay"} in layers
    image_layers = [layer for layer in layers if layer.get("type", "image") == "image"]
    assert [layer["image_url"] for layer in image_layers] == [
        "/static/projects/script-1/flipflop_cutouts/scene_001/state_01_scene_001_background.png",
        "/static/projects/script-1/flipflop_cutouts/scene_001/state_02_state_a.png",
        "/static/projects/script-1/flipflop_cutouts/scene_001/state_03_state_b.png",
    ]
    assert [layer["asset_kind"] for layer in image_layers] == ["full_frame", "cutout", "cutout"]
    assert image_layers[0]["visual_source_metadata"]["source_type"] == "flipflop_background"
    assert all(layer["visual_source_metadata"]["source_type"] == "flipflop_cutout" for layer in image_layers[1:])
    with Image.open(tmp_path / "projects" / "script-1" / "flipflop_cutouts" / "scene_001" / "state_02_state_a.png") as cutout:
        assert cutout.mode == "RGBA"
        assert cutout.getpixel((0, 0))[3] == 0
        assert cutout.getbbox() is not None


def test_generate_flipflop_cutouts_generates_background_as_full_frame_layer(tmp_path, monkeypatch):
    image_gen, _char_ref, style_ref = _stub_panel_image_context(monkeypatch, tmp_path)

    monkeypatch.setattr(image_gen, "save_vault_image", lambda **_kwargs: None)
    captured = []

    def fake_generate_image(
        prompt,
        *,
        width,
        height,
        reference_image_path=None,
        style_reference_path=None,
        script_id=None,
        **_kwargs,
    ):
        captured.append(
            {
                "prompt": prompt,
                "width": width,
                "height": height,
                "reference_image_path": reference_image_path,
                "style_reference_path": style_reference_path,
                "script_id": script_id,
            }
        )
        source = tmp_path / f"source-{len(captured)}.png"
        image = Image.new("RGBA", (120, 80), (20, 30, 40, 255))
        draw = ImageDraw.Draw(image)
        draw.rectangle((10, 20, 110, 60), fill=(80, 90, 100, 255))
        image.save(source)
        return str(source)

    monkeypatch.setattr(image_gen, "generate_image", fake_generate_image)

    layers = image_gen.generate_flipflop_cutouts(
        scene_id="scene_001",
        layers=[
            {
                "id": "background",
                "type": "image",
                "asset_kind": "full_frame",
                "prompt": "Environment-only static background: fast-food kitchen. No people, no readable text, no logos.",
            },
            {"id": "state_a", "type": "image", "asset_kind": "cutout", "prompt": "State A prompt", "contains_person": True},
            {"id": "state_b", "type": "image", "asset_kind": "cutout", "prompt": "State B prompt", "contains_person": True},
        ],
        script_id="script-1",
        scene_prompt="Person changes expression.",
        width=320,
        height=180,
        contains_person=True,
    )

    assert len(captured) == 2
    assert captured[0]["reference_image_path"] is None
    assert captured[0]["style_reference_path"] == style_ref
    assert "Environment-only static background" in captured[0]["prompt"]
    assert "No people" in captured[0]["prompt"]
    assert "[char_ref:" not in captured[0]["prompt"]
    assert captured[1]["reference_image_path"] is not None
    assert "two-cell contact sheet" in captured[1]["prompt"]
    image_layers = [layer for layer in layers if layer.get("type", "image") == "image"]
    assert image_layers[0]["asset_kind"] == "full_frame"
    assert image_layers[0]["image_url"] == "/static/projects/script-1/flipflop_cutouts/scene_001/state_01_background.png"
    assert image_layers[0]["visual_source_metadata"]["source_type"] == "flipflop_background"
    assert image_layers[1]["asset_kind"] == "cutout"
    assert image_layers[2]["asset_kind"] == "cutout"


def test_generate_flipflop_cutouts_repairs_legacy_two_state_layers_with_background(tmp_path, monkeypatch):
    image_gen, _char_ref, _style_ref = _stub_panel_image_context(monkeypatch, tmp_path)

    monkeypatch.setattr(image_gen, "save_vault_image", lambda **_kwargs: None)
    captured_prompts = []

    def fake_generate_image(prompt, **_kwargs):
        captured_prompts.append(prompt)
        source = tmp_path / f"legacy-source-{len(captured_prompts)}.png"
        image = Image.new("RGBA", (120, 80), (20, 30, 40, 255))
        draw = ImageDraw.Draw(image)
        draw.rectangle((20, 20, 100, 70), fill=(240, 210, 180, 255))
        image.save(source)
        return str(source)

    monkeypatch.setattr(image_gen, "generate_image", fake_generate_image)

    layers = image_gen.generate_flipflop_cutouts(
        scene_id="scene_001",
        layers=[
            {"id": "state_a", "type": "image", "asset_kind": "cutout", "prompt": "State A prompt", "contains_person": True},
            {"id": "state_b", "type": "image", "asset_kind": "cutout", "prompt": "State B prompt", "contains_person": True},
        ],
        script_id="script-1",
        scene_prompt=(
            "Young fast-food employee character framed chest-up, no props, no counter, "
            "no background elements."
        ),
        scene_narration=(
            "You're six hours in. The fryer is screaming, your visor is sliding, "
            "and the guy in line three asks about cheese."
        ),
        width=320,
        height=180,
        contains_person=True,
    )

    image_layers = [layer for layer in layers if layer.get("type", "image") == "image"]
    assert [layer["id"] for layer in image_layers] == ["scene_001_background", "state_a", "state_b"]
    assert [layer["asset_kind"] for layer in image_layers] == ["full_frame", "cutout", "cutout"]
    assert "Environment context from narration" in captured_prompts[0]
    assert "fryer is screaming" in captured_prompts[0]
    assert "Character/style context only; do not use this as environment direction" in captured_prompts[0]


def test_flipflop_background_source_prompt_treats_scene_prompt_as_character_context():
    from pipeline.image_gen import _compose_flipflop_background_source_prompt

    prompt = _compose_flipflop_background_source_prompt(
        layer_prompt=flipflop_background_prompt(
            visual_prompt=(
                "Young fast-food employee character framed chest-up, clean flat 2D illustration, "
                "no props, no counter, no background elements."
            ),
            narration=(
                "You're six hours in. The fryer is screaming, your visor is sliding, "
                "and the guy in line three is asking if the flame-grilled burger comes with cheese."
            ),
        ),
        scene_prompt=(
            "Young fast-food employee character framed chest-up, clean flat 2D illustration, "
            "no props, no counter, no background elements."
        ),
    )

    assert "Environment context from narration" in prompt
    assert "fryer is screaming" in prompt
    assert "Scene context for setting and style only" not in prompt
    assert "Character/style context only; do not use this as environment direction" in prompt


def test_generate_flipflop_cutouts_recrops_states_to_shared_bbox(tmp_path, monkeypatch):
    image_gen, _, _ = _stub_panel_image_context(monkeypatch, tmp_path)

    monkeypatch.setattr(image_gen, "save_vault_image", lambda **_kwargs: None)
    def fake_generate_image(
        _prompt,
        *,
        width,
        height,
        **_kwargs,
    ):
        call_number = len(list(tmp_path.glob("source-*.png"))) + 1
        source = tmp_path / f"source-{call_number}.png"
        image = Image.new("RGBA", (120, 100), (0, 255, 0, 255))
        draw = ImageDraw.Draw(image)
        if call_number == 1:
            draw.rectangle((0, 0, 119, 99), fill=(30, 40, 50, 255))
        else:
            draw.rectangle((20, 20, 50, 60), fill=(255, 0, 0, 255))
            draw.rectangle((65, 10, 110, 80), fill=(255, 0, 0, 255))
        image.save(source)
        return str(source)

    monkeypatch.setattr(image_gen, "generate_image", fake_generate_image)

    layers = image_gen.generate_flipflop_cutouts(
        scene_id="scene_001",
        layers=[
            {"id": "state_a", "type": "image", "prompt": "State A prompt", "contains_person": True},
            {"id": "state_b", "type": "image", "prompt": "State B prompt", "contains_person": True},
        ],
        script_id="script-1",
        scene_prompt="Person changes expression.",
        width=320,
        height=180,
        contains_person=True,
    )

    image_layers = [layer for layer in layers if layer.get("type", "image") == "image"]
    assert [layer["asset_kind"] for layer in image_layers] == ["full_frame", "cutout", "cutout"]
    assert [layer["visual_source_metadata"]["trim_box"] for layer in image_layers[1:]] == [
        [0, 0, 60, 85],
        [0, 0, 60, 85],
    ]
    assert [layer["visual_source_metadata"]["registration_box"] for layer in image_layers[1:]] == [
        [20, 20, 51, 61],
        [20, 20, 51, 61],
    ]
    output_dir = tmp_path / "projects" / "script-1" / "flipflop_cutouts" / "scene_001"
    with Image.open(output_dir / "state_02_state_a.png") as state_a:
        assert state_a.size == (60, 85)
        state_a_bbox = state_a.getbbox()
    with Image.open(output_dir / "state_03_state_b.png") as state_b:
        assert state_b.size == (60, 85)
        assert state_b.getbbox() == state_a_bbox


def test_generate_flipflop_cutouts_shared_sheet_cache_ignores_state_cutout_mtime(tmp_path, monkeypatch):
    image_gen, _, _ = _stub_panel_image_context(monkeypatch, tmp_path)

    monkeypatch.setattr(image_gen, "save_vault_image", lambda **_kwargs: None)
    generated_count = 0

    def fake_generate_image(
        _prompt,
        *,
        width,
        height,
        **_kwargs,
    ):
        nonlocal generated_count
        generated_count += 1
        source = tmp_path / f"source-{generated_count}.png"
        image = Image.new("RGBA", (120, 100), (0, 255, 0, 255))
        draw = ImageDraw.Draw(image)
        if generated_count == 1:
            draw.rectangle((0, 0, 119, 99), fill=(30, 40, 50, 255))
        else:
            draw.rectangle((40, 20, 70 + generated_count, 60), fill=(255, 0, 0, 255))
        image.save(source)
        return str(source)

    monkeypatch.setattr(image_gen, "generate_image", fake_generate_image)

    kwargs = {
        "scene_id": "scene_001",
        "layers": [
            {"id": "state_a", "type": "image", "prompt": "State A prompt", "contains_person": True},
            {"id": "state_b", "type": "image", "prompt": "State B prompt", "contains_person": True},
        ],
        "script_id": "script-1",
        "scene_prompt": "Person changes expression.",
        "width": 320,
        "height": 180,
        "contains_person": True,
    }

    image_gen.generate_flipflop_cutouts(**kwargs)
    output_dir = tmp_path / "projects" / "script-1" / "flipflop_cutouts" / "scene_001"
    state_a_path = output_dir / "state_02_state_a.png"
    future_mtime = state_a_path.stat().st_mtime + 5
    os.utime(state_a_path, (future_mtime, future_mtime))
    image_gen.generate_flipflop_cutouts(**kwargs)

    assert generated_count == 2


def test_popup_sequence_cutout_chroma_trims_item_sheet_crop(tmp_path):
    from pipeline import image_gen

    image = Image.new("RGBA", (120, 80), (0, 255, 0, 255))
    draw = ImageDraw.Draw(image)
    draw.rectangle((40, 20, 80, 60), fill=(255, 0, 0, 255))

    output_path = tmp_path / "cutout.png"
    trim_box = image_gen._save_keyed_trimmed_cutout(image, output_path, padding=4)

    assert trim_box == [36, 16, 85, 65]
    with Image.open(output_path) as cutout:
        assert cutout.mode == "RGBA"
        assert cutout.getpixel((0, 0))[3] == 0
        assert cutout.getbbox() is not None


def test_popup_sequence_anchor_prompt_requests_standing_character_without_popup_items():
    from pipeline.image_gen import _compose_popup_anchor_prompt

    prompt = _compose_popup_anchor_prompt(
        "[REACTION] Flat 2D cartoon person sitting at a desk while three floating notification bubbles hover around them.",
        contains_person=True,
    )

    assert "standing upright" in prompt
    assert "No popup items" in prompt
    assert "No sitting" in prompt
    assert "No desks" in prompt


def test_script_content_has_visual_canvas_default():
    content = ScriptContent(title="Test", segments=[])
    raw = json.loads(content.model_dump_json())
    assert raw["visual_canvas"]["background_color"] == "#F6C54A"


def test_palette_adds_recent_first_and_dedupes():
    from api.visual_treatments import (
        VISUAL_CANVAS_COLOR_PALETTE_KEY,
        add_palette_color,
    )

    engine = _build_test_engine()
    with Session(engine) as session:
        session.add(
            AppSetting(
                key=VISUAL_CANVAS_COLOR_PALETTE_KEY,
                value='["#111111", "#222222"]',
            )
        )
        session.commit()

        palette = add_palette_color(session, "#222222")

        assert palette == ["#222222", "#111111"]


def test_palette_add_mutates_without_committing():
    from api.visual_treatments import (
        VISUAL_CANVAS_COLOR_PALETTE_KEY,
        add_palette_color,
    )

    engine = _build_test_engine()
    with Session(engine) as session:
        session.add(
            AppSetting(
                key=VISUAL_CANVAS_COLOR_PALETTE_KEY,
                value='["#111111", "#222222"]',
            )
        )
        session.commit()

        add_palette_color(session, "#333333")
        session.rollback()

    with Session(engine) as session:
        row = session.get(AppSetting, VISUAL_CANVAS_COLOR_PALETTE_KEY)
        assert row is not None
        assert json.loads(row.value) == ["#111111", "#222222"]


def test_update_visual_canvas_persists_script_color_and_palette(tmp_path, monkeypatch):
    from models.script import Script
    from pipeline import render_cache
    from api.visual_treatments import (
        VISUAL_CANVAS_COLOR_PALETTE_KEY,
        UpdateVisualCanvasRequest,
        get_canvas_palette,
        update_visual_canvas,
    )

    monkeypatch.setattr(render_cache, "DATA_DIR", tmp_path)
    engine = _build_test_engine()
    script_id = "canvas-script-test"
    content = ScriptContent(title="Canvas Test", segments=[])

    with Session(engine) as session:
        session.add(
            Script(
                id=script_id,
                brand_id="brand",
                topic_title="Canvas Test",
                script_json=content.model_dump_json(),
            )
        )
        session.commit()

        response = update_visual_canvas(
            script_id,
            UpdateVisualCanvasRequest(background_color="abcdef"),
            session,
        )

        assert response.script.visual_canvas.background_color == "#ABCDEF"
        stored_script = session.get(Script, script_id)
        assert stored_script is not None
        stored_content = ScriptContent.model_validate_json(stored_script.script_json)
        assert stored_content.visual_canvas.background_color == "#ABCDEF"
        assert isinstance(response.palette, list)
        assert "#ABCDEF" in response.palette
        assert "#ABCDEF" in get_canvas_palette(session).colors
        assert (tmp_path / "projects" / script_id / ".render_inputs_mtime").is_file()


def test_update_visual_canvas_persists_canonical_topic_title(tmp_path, monkeypatch):
    from models.script import Script
    from pipeline import render_cache
    from api.visual_treatments import (
        UpdateVisualCanvasRequest,
        update_visual_canvas,
    )

    monkeypatch.setattr(render_cache, "DATA_DIR", tmp_path)
    engine = _build_test_engine()
    script_id = "canonical-title-canvas-test"
    stale_content = ScriptContent(title="Stale JSON Title", segments=[])

    with Session(engine) as session:
        session.add(
            Script(
                id=script_id,
                brand_id="brand",
                topic_title="Canonical Title",
                script_json=stale_content.model_dump_json(),
            )
        )
        session.commit()

        response = update_visual_canvas(
            script_id,
            UpdateVisualCanvasRequest(background_color="#abcdef"),
            session,
        )

        assert response.script.title == "Canonical Title"
        stored_script = session.get(Script, script_id)
        assert stored_script is not None
        stored_content = ScriptContent.model_validate_json(stored_script.script_json)
        assert stored_content.title == "Canonical Title"
        assert stored_content.visual_canvas.background_color == "#ABCDEF"


def test_analyze_visual_treatments_status_does_not_expose_output_urls(monkeypatch):
    import database
    from api import visual_treatments as visual_treatments_api
    from models.script import Script
    from pipeline.render_jobs import update_job

    engine = _build_test_engine()
    script_id = "visual-treatment-analysis-job"
    content = content_with_scenes(
        scene_with_words("s1", "They learned to keep your head down, hide feelings, and never be different.")
    )

    def run_sync(job_id, target):
        update_job(job_id, status="running")
        result = target()
        if isinstance(result, str):
            output_urls = [result]
        elif isinstance(result, list):
            output_urls = result
        else:
            output_urls = []
        update_job(job_id, status="completed", progress=1.0, current_step="Complete", output_urls=output_urls)

    monkeypatch.setattr(database, "engine", engine)
    monkeypatch.setattr(visual_treatments_api, "run_in_background", run_sync)

    with Session(engine) as session:
        session.add(
            Script(
                id=script_id,
                brand_id="brand",
                topic_title="Treatment Test",
                script_json=content.model_dump_json(),
            )
        )
        session.commit()

        response = visual_treatments_api.analyze_visual_treatment_job(script_id, session)
        status = visual_treatments_api.visual_treatment_analyze_status(response.job_id)

    assert status["status"] == "completed"
    assert status["output_urls"] == []
    assert len(status["assignments"]) == 1


def test_require_visual_treatment_voiceover_raises_for_missing_non_title_audio():
    title = Scene(id="title", narration="", visual_prompt="", is_title_card=True)
    scene = Scene(id="s1", narration="Missing audio.", visual_prompt="Panel")
    content = content_with_scenes(title, scene)

    with pytest.raises(UserFacingJobError, match="animation types can sync to words"):
        require_visual_treatment_voiceover(content)


def test_require_visual_treatment_voiceover_raises_for_missing_non_title_word_timing():
    scene = Scene(
        id="s1",
        narration="Missing word timings.",
        visual_prompt="Panel",
        audio_duration_seconds=2.0,
        word_timestamps=[],
    )
    content = content_with_scenes(scene)

    with pytest.raises(UserFacingJobError, match="sync to words"):
        require_visual_treatment_voiceover(content)


@pytest.mark.parametrize(
    ("narration", "expected_layers"),
    [
        (
            "They learned to keep your head down, hide feelings, and never be different.",
            3,
        ),
        (
            "They learned to keep your head down; hide feelings; never be different.",
            3,
        ),
        (
            "They learned to keep your head down and hide feelings and never be different.",
            3,
        ),
        (
            "They could keep your head down or hide feelings or never be different.",
            3,
        ),
    ],
)
def test_analyze_visual_treatments_assigns_popup_sequence_for_list_narration(
    narration: str,
    expected_layers: int,
):
    scene = scene_with_words(
        "s1",
        narration,
    )
    content = content_with_scenes(scene)

    assignments = analyze_visual_treatments(content, script_id="script-popup")

    assignment = assignments[0]
    assert assignment.scene_id == "s1"
    assert assignment.visual_treatment == "popup_sequence"
    assert 2 <= len(assignment.visual_layers) <= 4
    assert len(assignment.visual_layers) == expected_layers
    enter_times = [layer.enter_at_seconds for layer in assignment.visual_layers]
    assert enter_times == sorted(enter_times)
    for layer in assignment.visual_layers:
        prompt = layer.prompt.lower()
        assert "popup item cutout prompt" in prompt
        assert "no decorative border" in prompt
        assert "small framed" not in prompt
        assert "picture frame" in prompt


def test_analyze_visual_treatments_prefers_natural_list_over_repeated_words():
    scene = scene_with_words(
        "s1",
        "You know the problem: missing keys, spoiled lunch, and an angry prisoner, and you know it cannot end well.",
    )
    content = content_with_scenes(scene)

    assignments = analyze_visual_treatments(content, script_id="script-repeated-list")

    assignment = assignments[0]
    assert assignment.visual_treatment == "popup_sequence"
    assert len(assignment.visual_layers) == 3
    assert [layer.placement for layer in assignment.visual_layers] == ["left", "center", "right"]
    assert [layer.enter_at_seconds for layer in assignment.visual_layers] == [1.4, 2.1, 3.5]


def test_analyze_visual_treatments_times_list_item_after_lead_in():
    scene = scene_with_words(
        "s1",
        "They learned to keep your head down, hide feelings, and never be different.",
    )
    content = content_with_scenes(scene)

    assignments = analyze_visual_treatments(content, script_id="script-list-lead-in")

    assignment = assignments[0]
    assert assignment.visual_treatment == "popup_sequence"
    assert [layer.enter_at_seconds for layer in assignment.visual_layers] == [1.05, 2.45, 3.5]


def test_analyze_visual_treatments_does_not_assign_flipflop_for_generic_contrast():
    scene = scene_with_words("s1", "At first the room is calm, but then everything becomes chaos.")
    content = content_with_scenes(scene)

    assignments = analyze_visual_treatments(content, script_id="script-contrast")

    assignment = assignments[0]
    assert assignment.scene_id == "s1"
    assert assignment.visual_mode == "comparison_board"
    assert assignment.visual_treatment == "comparison_board"
    assert [layer.placement for layer in assignment.visual_layers] == ["left", "right"]
    assert [layer.label for layer in assignment.visual_layers] == ["", ""]
    assert all(layer.asset_kind == "cutout" for layer in assignment.visual_layers)
    assert all("No text in image" in layer.prompt for layer in assignment.visual_layers)


def test_analyze_visual_treatments_assigns_three_column_comparison_board():
    scene = scene_with_words("s1", "The myth says talent, the reality is practice, and the outcome is patience.")
    content = content_with_scenes(scene)

    assignments = analyze_visual_treatments(content, script_id="script-three-way")

    assignment = assignments[0]
    assert assignment.visual_mode == "comparison_board"
    assert assignment.visual_treatment == "comparison_board"
    assert [layer.placement for layer in assignment.visual_layers] == ["left", "center", "right"]
    assert [layer.label for layer in assignment.visual_layers] == ["myth", "reality", "outcome"]


def test_analyze_visual_treatments_assigns_flipflop_for_same_subject_micro_action():
    scene = scene_with_words("s1", "His hands open and close around the microphone while he talks.")
    scene.visual_prompt = "[REACTION] Cartoon man holding a microphone while talking."
    content = content_with_scenes(scene)

    assignments = analyze_visual_treatments(content, script_id="script-micro-action")

    assignment = assignments[0]
    assert assignment.scene_id == "s1"
    assert assignment.visual_mode == "flipflop"
    assert assignment.visual_treatment == "flipflop"
    assert len(assignment.visual_layers) == 3
    assert [layer.id for layer in assignment.visual_layers] == ["s1_background", "s1_state_a", "s1_state_b"]
    assert assignment.visual_layers[0].asset_kind == "full_frame"
    assert "Environment-only static background" in assignment.visual_layers[0].prompt
    assert "no people" in assignment.visual_layers[0].prompt.lower()
    assert "no readable text" in assignment.visual_layers[0].prompt.lower()
    assert "no logos" in assignment.visual_layers[0].prompt.lower()
    assert all(layer.asset_kind == "cutout" for layer in assignment.visual_layers[1:])
    assert scene.flipflop_action == "speaking_mouth"
    assert "mouth closed or lightly resting" in assignment.visual_layers[1].prompt
    assert "mouth slightly open as if speaking one syllable" in assignment.visual_layers[2].prompt
    for layer in assignment.visual_layers[1:]:
        prompt = layer.prompt.lower()
        assert "solid chroma" in prompt
        assert "no full background scene" in prompt
        assert "full-bleed" not in prompt
        assert "framed panel" not in prompt


def test_explicit_flipflop_layers_include_environment_background():
    scene = scene_with_words("s1", "He blinks while the kitchen noise keeps going.")
    scene.visual_prompt = "Young fast-food employee in a red polo, fast-food kitchen context."
    scene.set_visual_mode("flipflop")
    scene.flipflop_action = "blink"
    content = content_with_scenes(scene)

    assignments = analyze_visual_treatments(content, script_id="script-flipflop-background")

    layers = assignments[0].visual_layers
    assert [layer.id for layer in layers] == ["s1_background", "s1_state_a", "s1_state_b"]
    assert layers[0].asset_kind == "full_frame"
    assert "Environment-only static background" in layers[0].prompt
    assert "no people" in layers[0].prompt.lower()
    assert "no readable text" in layers[0].prompt.lower()
    assert "no logos" in layers[0].prompt.lower()
    assert [layer.asset_kind for layer in layers[1:]] == ["cutout", "cutout"]


def test_flipflop_background_prompt_uses_narration_for_environment_context():
    prompt = flipflop_background_prompt(
        visual_prompt=(
            "Young fast-food employee character framed chest-up, plain red polo and red visor, "
            "clean flat 2D illustration, no props, no counter, no background elements, no logos, no text."
        ),
        narration=(
            "You're six hours in. The fryer is screaming, your visor is sliding, "
            "and the guy in line three is asking if the flame-grilled burger comes with cheese."
        ),
    )

    assert "Environment context from narration" in prompt
    assert "fryer is screaming" in prompt
    assert "line three" in prompt
    assert "Character/style context only" in prompt
    assert "no background elements" in prompt
    assert prompt.index("fryer is screaming") < prompt.index("no background elements")


def test_explicit_flipflop_replaces_legacy_panel_layers_with_cutouts():
    scene = scene_with_words("s1", "His hands open and close while he talks.")
    scene.visual_prompt = "[REACTION] Cartoon man speaking with expressive hands."
    scene.set_visual_mode("flipflop")
    scene.flipflop_action = "speaking_mouth"
    scene.visual_layers = [
        VisualLayer(id="old_a", asset_kind="panel", prompt="Old full frame A"),
        VisualLayer(id="old_b", asset_kind="panel", prompt="Old full frame B"),
    ]
    content = content_with_scenes(scene)

    assignments = analyze_visual_treatments(content, script_id="script-legacy-flipflop")

    assignment = assignments[0]
    assert assignment.visual_mode == "flipflop"
    assert [layer.id for layer in assignment.visual_layers] == ["s1_background", "s1_state_a", "s1_state_b"]
    assert assignment.visual_layers[0].asset_kind == "full_frame"
    assert all(layer.asset_kind == "cutout" for layer in assignment.visual_layers[1:])


def test_explicit_flipflop_missing_action_downgrades_to_full_frame():
    scene = scene_with_words("s1", "He blinks before answering.")
    scene.set_visual_mode("flipflop")
    content = content_with_scenes(scene)

    assignments = analyze_visual_treatments(content, script_id="script-missing-action")

    assert assignments[0].visual_mode == "full_frame"
    assert assignments[0].visual_layers == []


def test_explicit_flipflop_non_human_downgrades_to_full_frame():
    scene = scene_with_words("s1", "The clock ticks once on the wall.")
    scene.set_visual_mode("flipflop")
    scene.flipflop_action = "blink"
    content = content_with_scenes(scene)

    assignments = analyze_visual_treatments(content, script_id="script-non-human")

    assert assignments[0].visual_mode == "full_frame"
    assert assignments[0].visual_layers == []


def test_explicit_flipflop_valid_action_uses_action_specific_prompts():
    scene = scene_with_words("s1", "He blinks before answering.")
    scene.visual_prompt = "[CLOSE-UP] Cartoon man at a desk before answering."
    scene.set_visual_mode("flipflop")
    scene.flipflop_action = "blink"
    content = content_with_scenes(scene)

    assignments = analyze_visual_treatments(content, script_id="script-blink")

    assignment = assignments[0]
    assert assignment.visual_mode == "flipflop"
    assert [layer.id for layer in assignment.visual_layers] == ["s1_background", "s1_state_a", "s1_state_b"]
    assert assignment.visual_layers[0].asset_kind == "full_frame"
    assert "Environment-only static background" in assignment.visual_layers[0].prompt
    assert "eyes open, neutral natural face" in assignment.visual_layers[1].prompt
    assert "eyes closed in a quick blink" in assignment.visual_layers[2].prompt
    assert all(layer.asset_kind == "cutout" for layer in assignment.visual_layers[1:])


def test_explicit_flipflop_valid_action_replaces_existing_generic_cutout_prompts():
    scene = scene_with_words("s1", "He blinks before answering.")
    scene.visual_prompt = "A human narrator blinks before answering."
    scene.set_visual_mode("flipflop")
    scene.flipflop_action = "blink"
    scene.visual_layers = [
        VisualLayer(id="old_a", asset_kind="cutout", prompt="Generic A"),
        VisualLayer(id="old_b", asset_kind="cutout", prompt="Generic B"),
    ]
    content = content_with_scenes(scene)

    assignments = analyze_visual_treatments(content, script_id="script-existing-blink")

    assignment = assignments[0]
    assert assignment.visual_mode == "flipflop"
    assert [layer.id for layer in assignment.visual_layers] == ["s1_background", "s1_state_a", "s1_state_b"]
    assert assignment.visual_layers[0].asset_kind == "full_frame"
    assert "eyes open, neutral natural face" in assignment.visual_layers[1].prompt
    assert "eyes closed in a quick blink" in assignment.visual_layers[2].prompt


def test_inferred_flipflop_sets_action():
    scene = scene_with_words("s1", "He blinks while explaining.")
    scene.visual_prompt = "[CLOSE-UP] Cartoon man explaining at a desk."
    content = content_with_scenes(scene)

    assignments = analyze_visual_treatments(content, script_id="script-inferred-blink")

    assignment = assignments[0]
    assert assignment.visual_mode == "flipflop"
    assert assignment.visual_layers[0].prompt
    assert scene.flipflop_action == "blink"


def test_analyze_visual_treatments_preserves_explicit_popup_sequence_with_progression_words():
    existing_layer = VisualLayer(id="existing_panel", prompt="Existing popup panel")
    scene = scene_with_words("s1", "The crack slowly spreads across the glass.")
    scene.set_visual_mode("popup_sequence")
    scene.visual_layers = [existing_layer]
    content = content_with_scenes(scene)

    assignments = analyze_visual_treatments(content, script_id="script-popup-progress")

    assignment = assignments[0]
    assert assignment.visual_mode == "popup_sequence"
    assert assignment.visual_treatment == "popup_sequence"
    assert assignment.visual_layers == [existing_layer]


def test_analyze_visual_treatments_fills_explicit_popup_sequence_without_layers():
    scene = scene_with_words("s1", "She points to missing keys, spoiled lunch, and an angry prisoner.")
    scene.set_visual_mode("popup_sequence")
    content = content_with_scenes(scene)

    assignments = analyze_visual_treatments(content, script_id="script-explicit-popup")

    assignment = assignments[0]
    assert assignment.visual_mode == "popup_sequence"
    assert assignment.visual_treatment == "popup_sequence"
    assert [layer.placement for layer in assignment.visual_layers] == ["left", "center", "right"]
    assert [layer.enter_at_seconds for layer in assignment.visual_layers] == [0.0, 1.75, 3.15]


def test_analyze_visual_treatments_downgrades_explicit_flipflop_with_missing_action():
    scene = scene_with_words("s1", "The crack slowly spreads across the glass.")
    scene.set_visual_mode("flipflop")
    content = content_with_scenes(scene)

    assignments = analyze_visual_treatments(content, script_id="script-flip-progress")

    assignment = assignments[0]
    assert assignment.visual_mode == "full_frame"
    assert assignment.visual_treatment == "full_frame"
    assert assignment.visual_layers == []


def test_flipflop_cutout_prompt_detects_state_b_without_matching_state_letter():
    state_a = flipflop_cutout_prompt("Person changes expression.", "Before and after.", "state A")
    state_b = flipflop_cutout_prompt("Person changes expression.", "Before and after.", "state B")

    assert "Initial pose or expression" in state_a
    assert "Next compatible pose or expression" in state_b
    assert "Initial pose or expression" not in state_b


def test_analyze_visual_treatments_fills_explicit_comparison_board_without_layers():
    scene = scene_with_words("s1", "Rich families kept warm while poor families counted every coin.")
    scene.set_visual_mode("comparison_board")
    content = content_with_scenes(scene)

    assignments = analyze_visual_treatments(content, script_id="script-explicit-comparison")

    assignment = assignments[0]
    assert assignment.visual_mode == "comparison_board"
    assert assignment.visual_treatment == "comparison_board"
    assert [layer.placement for layer in assignment.visual_layers] == ["left", "right"]
    assert [layer.label for layer in assignment.visual_layers] == ["rich", "poor"]


def test_analyze_visual_treatments_keeps_list_mode_with_progression_words():
    scene = scene_with_words("s1", "First the crack appears, second the warning light spreads.")
    content = content_with_scenes(scene)

    assignments = analyze_visual_treatments(content, script_id="script-list-progress")

    assignment = assignments[0]
    assert assignment.visual_mode == "popup_sequence"
    assert assignment.visual_treatment == "popup_sequence"
    assert len(assignment.visual_layers) == 2


def test_analyze_visual_treatments_downgrades_explicit_flipflop_with_non_human_subject():
    scene = scene_with_words("s1", "The crack starts small, but the damage spreads across the panel.")
    scene.set_visual_mode("flipflop")
    scene.flipflop_action = "speaking_mouth"
    content = content_with_scenes(scene)

    assignments = analyze_visual_treatments(content, script_id="script-contrast-progress")

    assignment = assignments[0]
    assert assignment.visual_mode == "full_frame"
    assert assignment.visual_treatment == "full_frame"
    assert assignment.visual_layers == []


def test_analyze_visual_treatments_does_not_treat_cardinal_words_as_list_markers():
    scene = scene_with_words("s1", "No one knew two guards were hiding.")
    content = content_with_scenes(scene)

    assignments = analyze_visual_treatments(content, script_id="script-cardinal")

    assert assignments[0].visual_treatment == "full_frame"
    assert assignments[0].visual_layers == []


def test_analyze_visual_treatments_preserves_explicit_multi_frame_mode():
    scene = scene_with_words("s1", "The wall shows three separate warning signs.")
    scene.set_visual_mode("multi_frame")
    content = content_with_scenes(scene)

    assignments = analyze_visual_treatments(content, script_id="script-multi-frame")

    assignment = assignments[0]
    assert assignment.visual_mode == "multi_frame"
    assert assignment.visual_treatment == "full_frame"
    assert assignment.visual_layers == []


def test_analyze_visual_treatments_detects_continuous_progression():
    scene = scene_with_words("s1", "The crack slowly spreads across the glass.")
    content = content_with_scenes(scene)

    assignments = analyze_visual_treatments(content, script_id="script-continuous")

    assignment = assignments[0]
    assert assignment.visual_mode == "continuous"
    assert assignment.visual_treatment == "full_frame"
    assert assignment.visual_layers == []


def test_apply_visual_treatment_assignments_updates_matching_scenes():
    first = scene_with_words("s1", "First panel.")
    second = scene_with_words("s2", "Second panel.")
    content = content_with_scenes(first, second)
    layer = VisualLayer(id="s1_panel", prompt="Panel prompt")

    apply_visual_treatment_assignments(
        content,
        [
            VisualTreatmentAssignment(
                scene_id="s1",
                visual_treatment="popup_sequence",
                visual_layers=[layer],
            ),
            VisualTreatmentAssignment(
                scene_id="missing",
                visual_treatment="flipflop",
                visual_layers=[VisualLayer(id="missing_panel")],
            ),
            VisualTreatmentAssignment(
                scene_id="s2",
                visual_treatment="unknown",
                visual_layers=[VisualLayer(id="ignored")],
            ),
        ],
    )

    assert first.visual_treatment == "popup_sequence"
    assert first.visual_layers == [layer]
    assert second.visual_treatment == "full_frame"
    assert second.visual_layers == []


def test_apply_visual_treatment_assignment_accepts_multi_frame_mode():
    scene = scene_with_words("s1", "Three separate images appear.")
    content = content_with_scenes(scene)

    apply_visual_treatment_assignments(
        content,
        [
            VisualTreatmentAssignment(
                scene_id="s1",
                visual_mode="multi_frame",
                visual_treatment="full_frame",
                visual_layers=[VisualLayer(id="bogus")],
            )
        ],
    )

    assert scene.visual_mode == "multi_frame"
    assert scene.media_source == "ai"
    assert scene.visual_treatment == "full_frame"
    assert scene.visual_layers == []


def test_apply_visual_treatment_assignment_accepts_continuous_mode():
    scene = scene_with_words("s1", "The crack slowly spreads across the glass.")
    content = content_with_scenes(scene)

    apply_visual_treatment_assignments(
        content,
        [
            VisualTreatmentAssignment(
                scene_id="s1",
                visual_mode="continuous",
                visual_treatment="full_frame",
                visual_layers=[VisualLayer(id="bogus")],
            )
        ],
    )

    assert scene.visual_mode == "continuous"
    assert scene.media_source == "ai"
    assert scene.visual_treatment == "full_frame"
    assert scene.visual_layers == []


def test_apply_visual_treatment_assignment_accepts_comparison_board_mode():
    scene = scene_with_words("s1", "Human strength versus Neanderthal strength.")
    content = content_with_scenes(scene)
    layers = [
        VisualLayer(id="s1_compare_1", asset_kind="cutout", prompt="Human"),
        VisualLayer(id="s1_compare_2", asset_kind="cutout", prompt="Neanderthal"),
    ]

    apply_visual_treatment_assignments(
        content,
        [
            VisualTreatmentAssignment(
                scene_id="s1",
                visual_mode="comparison_board",
                visual_layers=layers,
            )
        ],
    )

    assert scene.visual_mode == "comparison_board"
    assert scene.visual_treatment == "comparison_board"
    assert scene.visual_layers == layers


def test_analyze_visual_treatments_preserves_explicit_stat_card_mode():
    scene = scene_with_words("s1", "Eighty-five percent churn before week one.")
    scene.set_visual_mode("stat_card")
    scene.stat_value = "85%"
    scene.stat_label = "churn before week 1"
    scene.visual_layers = [
        VisualLayer(id="s1_stat_icon", asset_kind="cutout", prompt="Warning icon"),
    ]
    content = content_with_scenes(scene)

    assignments = analyze_visual_treatments(content, script_id="stat-script")

    assert len(assignments) == 1
    assignment = assignments[0]
    assert assignment.visual_mode == "stat_card"
    assert assignment.visual_layers == scene.visual_layers


def test_apply_visual_treatment_assignment_accepts_stat_card_mode_with_icon_layer():
    scene = scene_with_words("s1", "Eighty-five percent churn before week one.")
    content = content_with_scenes(scene)
    layers = [
        VisualLayer(id="s1_stat_icon", asset_kind="cutout", prompt="Warning icon"),
    ]

    apply_visual_treatment_assignments(
        content,
        [
            VisualTreatmentAssignment(
                scene_id="s1",
                visual_mode="stat_card",
                visual_layers=layers,
            )
        ],
    )

    assert scene.visual_mode == "stat_card"
    assert scene.visual_treatment == "stat_card"
    assert scene.visual_layers == layers


def test_analyze_visual_treatments_treats_removed_dossier_mode_as_full_frame():
    scene = scene_with_words("s1", "The case file is sealed shut.")
    scene.set_visual_mode("dossier")
    scene.visual_layers = [
        VisualLayer(id="s1_anchor", asset_kind="cutout", label="SUSPECT", prompt="Anchor"),
        VisualLayer(id="s1_evidence_1", asset_kind="cutout", label="WEAPON", prompt="Knife"),
    ]
    content = content_with_scenes(scene)

    assignments = analyze_visual_treatments(content, script_id="dossier-script")
    assert len(assignments) == 1
    assignment = assignments[0]
    assert assignment.visual_mode == "full_frame"
    assert assignment.visual_layers == []


def test_apply_visual_treatment_assignment_rejects_removed_dossier_mode():
    scene = scene_with_words("s1", "The investigators built the case slowly.")
    content = content_with_scenes(scene)
    layers = [
        VisualLayer(id="s1_anchor", asset_kind="cutout", label="SUSPECT", prompt="Anchor"),
        VisualLayer(id="s1_evidence_1", asset_kind="cutout", label="WEAPON", prompt="Weapon"),
        VisualLayer(id="s1_evidence_2", asset_kind="cutout", label="WITNESS", prompt="Witness"),
    ]

    apply_visual_treatment_assignments(
        content,
        [
            VisualTreatmentAssignment(
                scene_id="s1",
                visual_mode="dossier",
                visual_layers=layers,
            )
        ],
    )

    assert scene.visual_mode == "full_frame"
    assert scene.visual_treatment == "full_frame"
    assert scene.visual_layers == []


def test_visual_treatment_assignment_legacy_property_keeps_layered_modes():
    assert VisualTreatmentAssignment(scene_id="s1", visual_mode="stat_card").visual_treatment == "stat_card"
    assert VisualTreatmentAssignment(scene_id="s2", visual_mode="dossier").visual_treatment == "full_frame"


def test_analyze_visual_treatments_prevents_adjacent_non_full_frame_modes():
    first = scene_with_words("s1", "First the badge, second the receipt, third the timer.")
    second = scene_with_words("s2", "Before the lunch rush, after the dinner rush.")
    third = scene_with_words("s3", "His hands open and close around the register drawer while he talks.")
    third.visual_prompt = "[REACTION] Cartoon cashier talking beside a register drawer."
    content = content_with_scenes(first, second, third)

    assignments = analyze_visual_treatments(content, script_id="spacing-script")

    assert [assignment.visual_mode for assignment in assignments] == [
        "popup_sequence",
        "full_frame",
        "flipflop",
    ]
    assert "Separated from adjacent" in assignments[1].reasoning


def test_analyze_visual_treatments_routes_investigation_lists_without_dossier():
    caption = scene_with_words("s1", "That is the real cost.")
    stat = scene_with_words("s2", "By year three, 85% of your patience is gone.")
    investigation = scene_with_words("s3", "The case file has clues, witnesses, and a sealed report.")
    content = content_with_scenes(caption, stat, investigation)

    assignments = analyze_visual_treatments(content, script_id="clear-improvement-script")

    assert assignments[0].visual_mode == "captions"
    assert assignments[0].caption_text == "That is the real cost"
    assert assignments[0].caption_emphasis == "cost"

    assert assignments[1].visual_mode == "full_frame"
    assert "Separated from adjacent" in assignments[1].reasoning

    assert assignments[2].visual_mode == "popup_sequence"
    assert len(assignments[2].visual_layers) == 3


def test_apply_visual_treatment_assignment_sets_caption_and_stat_fields():
    caption = scene_with_words("s1", "That is the real cost.")
    buffer = scene_with_words("s2", "The parking lot is empty after midnight.")
    stat = scene_with_words("s3", "By year three, 85% of your patience is gone.")
    content = content_with_scenes(caption, buffer, stat)

    apply_visual_treatment_assignments(
        content,
        [
            VisualTreatmentAssignment(
                scene_id="s1",
                visual_mode="captions",
                caption_text="The real cost",
                caption_emphasis="cost",
            ),
            VisualTreatmentAssignment(
                scene_id="s2",
                visual_mode="full_frame",
            ),
            VisualTreatmentAssignment(
                scene_id="s3",
                visual_mode="stat_card",
                stat_value="85%",
                stat_label="of your patience is gone",
            ),
        ],
    )

    assert caption.visual_mode == "captions"
    assert caption.caption_text == "The real cost"
    assert caption.caption_emphasis == "cost"
    assert stat.visual_mode == "stat_card"
    assert stat.stat_value == "85%"
    assert stat.stat_label == "of your patience is gone"


def test_apply_visual_treatment_assignment_rejects_caption_text_outside_narration():
    caption = scene_with_words("s1", "The real problem is friction.")
    content = content_with_scenes(caption)

    apply_visual_treatment_assignments(
        content,
        [
            VisualTreatmentAssignment(
                scene_id="s1",
                visual_mode="captions",
                caption_text="It is not willpower",
                caption_emphasis="willpower",
            ),
        ],
    )

    assert caption.visual_mode == "captions"
    assert caption.caption_text == "The real problem is friction"
    assert caption.caption_emphasis == "real"


def test_apply_visual_treatment_assignment_derives_manual_caption_fields():
    caption = scene_with_words("s1", "That is the real cost.")
    content = content_with_scenes(caption)

    apply_visual_treatment_assignments(
        content,
        [
            VisualTreatmentAssignment(
                scene_id="s1",
                visual_mode="captions",
            ),
        ],
    )

    assert caption.visual_mode == "captions"
    assert caption.caption_text == "That is the real cost"
    assert caption.caption_emphasis == "cost"


def test_apply_visual_treatment_assignments_enforces_non_full_frame_spacing():
    first = scene_with_words("s1", "First the badge, second the receipt.")
    second = scene_with_words("s2", "Before the lunch rush, after the dinner rush.")
    third = scene_with_words("s3", "His hands open and close around the drawer while he talks.")
    content = content_with_scenes(first, second, third)

    apply_visual_treatment_assignments(
        content,
        [
            VisualTreatmentAssignment(scene_id="s1", visual_mode="popup_sequence", visual_layers=[VisualLayer(id="p1")]),
            VisualTreatmentAssignment(scene_id="s2", visual_mode="comparison_board", visual_layers=[VisualLayer(id="c1")]),
            VisualTreatmentAssignment(scene_id="s3", visual_mode="flipflop", visual_layers=[VisualLayer(id="f1")]),
        ],
    )

    assert [scene.visual_mode for scene in content.all_scenes()] == [
        "popup_sequence",
        "full_frame",
        "flipflop",
    ]
    assert second.visual_layers == []
