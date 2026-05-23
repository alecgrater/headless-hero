import json
import os
import tempfile

import pytest
from sqlmodel import Session, SQLModel, create_engine
from sqlmodel.pool import StaticPool

from models.settings import AppSetting
from models.script import Script
from models.script import ScriptContent, Scene, VisualCanvas, VisualLayer
from pipeline.image_gen import generate_visual_layer_panels, visual_layer_image_filename
from pipeline.render_jobs import RenderJob
from pipeline.render_jobs import UserFacingJobError
from pipeline.visual_treatments import (
    VisualTreatmentAssignment,
    analyze_visual_treatments,
    apply_visual_treatment_assignments,
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


def test_phase_images_forces_visual_layer_panel_regeneration(monkeypatch):
    from pipeline import image_gen as image_gen_mod
    from pipeline import render_phases as render_phases_mod
    from pipeline.render_phases import ExportContext, _phase_images

    content = content_with_scenes(
        Scene(
            id="scene_001",
            narration="Panel scene.",
            visual_prompt="Panel",
            visual_treatment="popup_sequence",
            visual_layers=[VisualLayer(id="panel_1", prompt="Panel prompt")],
        )
    )
    captured = {}
    monkeypatch.setattr(render_phases_mod, "_reload_content", lambda script_id: content)
    monkeypatch.setattr(
        image_gen_mod,
        "generate_scene_image",
        lambda scene_id, visual_prompt, script_id, force: ("/static/projects/script-1/images/scene_001.png", "", None),
    )

    def fake_generate_visual_layer_panels(scene_id, layers, script_id, force=False, **kwargs):
        captured["force"] = force
        return layers

    monkeypatch.setattr(image_gen_mod, "generate_visual_layer_panels", fake_generate_visual_layer_panels)
    ctx = ExportContext(
        script_id="script-1",
        job=RenderJob("job-1"),
        scenes=[
            {
                "scene_id": "scene_001",
                "visual_prompt": "Panel",
                "is_title_card": False,
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

    assert captured["force"] is True


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
        lambda **kwargs: ("/static/projects/regular-visual-panels/images/scene_001.png", "prompt", None),
    )

    def fake_generate_visual_layer_panels(scene_id, layers, script_id, **kwargs):
        captured["scene_id"] = scene_id
        captured["layers"] = layers
        captured["contains_person"] = kwargs.get("contains_person")
        return [
            {
                **layers[0],
                "image_url": "/static/projects/regular-visual-panels/images/scene_001_layer_panel_1.png",
            }
        ]

    monkeypatch.setattr(visuals_api, "generate_visual_layer_panels", fake_generate_visual_layer_panels, raising=False)

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
    assert response.visual_layers[0]["image_url"] == "/static/projects/regular-visual-panels/images/scene_001_layer_panel_1.png"
    assert stored_content.segments[0].scenes[0].visual_layers[0].image_url == (
        "/static/projects/regular-visual-panels/images/scene_001_layer_panel_1.png"
    )


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

    with pytest.raises(UserFacingJobError, match="Generate voiceover first"):
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
    assert all("small framed Headless Hero cartoon panel" in layer.prompt for layer in assignment.visual_layers)


def test_analyze_visual_treatments_assigns_flipflop_for_two_state_narration():
    scene = scene_with_words("s1", "At first the room is calm, but then everything becomes chaos.")
    content = content_with_scenes(scene)

    assignments = analyze_visual_treatments(content, script_id="script-flip")

    assignment = assignments[0]
    assert assignment.scene_id == "s1"
    assert assignment.visual_treatment == "flipflop"
    assert len(assignment.visual_layers) == 2
    assert [layer.id for layer in assignment.visual_layers] == ["s1_state_a", "s1_state_b"]
    assert [layer.enter_at_seconds for layer in assignment.visual_layers] == [0.0, 2.1]


def test_analyze_visual_treatments_assigns_flipflop_for_repetition():
    scene = scene_with_words("s1", "The meter rises, rises, and rises again.")
    content = content_with_scenes(scene)

    assignments = analyze_visual_treatments(content, script_id="script-repeat")

    assert assignments[0].visual_treatment == "flipflop"
    assert len(assignments[0].visual_layers) == 2


def test_analyze_visual_treatments_does_not_treat_cardinal_words_as_list_markers():
    scene = scene_with_words("s1", "No one knew two guards were hiding.")
    content = content_with_scenes(scene)

    assignments = analyze_visual_treatments(content, script_id="script-cardinal")

    assert assignments[0].visual_treatment == "full_frame"
    assert assignments[0].visual_layers == []


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
