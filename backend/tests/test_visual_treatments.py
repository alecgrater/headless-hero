import json

import pytest
from sqlmodel import Session, SQLModel, create_engine
from sqlmodel.pool import StaticPool

from models.settings import AppSetting
from models.script import ScriptContent, Scene, VisualCanvas, VisualLayer
from pipeline.image_gen import visual_layer_image_filename
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
