import json

from sqlmodel import Session, SQLModel, create_engine
from sqlmodel.pool import StaticPool

from models.settings import AppSetting
from models.script import ScriptContent, Scene, VisualCanvas, VisualLayer


def _build_test_engine():
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    SQLModel.metadata.create_all(engine)
    return engine


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
