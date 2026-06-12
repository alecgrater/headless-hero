"""Tests for the Test Lab hidden project and run APIs."""

from datetime import datetime, timezone

from fastapi.testclient import TestClient
from PIL import Image, ImageDraw
from sqlmodel import Session, SQLModel, create_engine
from sqlmodel.pool import StaticPool


def _build_inmemory_engine():
    import models.api_usage  # noqa: F401
    import models.brand  # noqa: F401
    import models.content_profile  # noqa: F401
    import models.credential  # noqa: F401
    import models.generation_duration  # noqa: F401
    import models.idea  # noqa: F401
    import models.project_config  # noqa: F401
    import models.publish  # noqa: F401
    import models.script  # noqa: F401
    import models.settings  # noqa: F401
    import models.style_preset  # noqa: F401
    import models.style_preset_character  # noqa: F401
    import models.trending  # noqa: F401

    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    SQLModel.metadata.create_all(engine)
    return engine


def _setup_app(monkeypatch, tmp_path):
    engine = _build_inmemory_engine()

    from models.brand import BrandProfile

    with Session(engine) as session:
        session.add(BrandProfile(id="default", name="Headless Hero", description="", is_default=True))
        session.commit()

    import api.scripts as scripts_module
    import database

    try:
        import pipeline.test_lab as test_lab_module
    except ModuleNotFoundError:
        test_lab_module = None

    monkeypatch.setattr(database, "engine", engine)
    monkeypatch.setattr(scripts_module, "engine", engine)
    if test_lab_module is not None:
        monkeypatch.setattr(test_lab_module, "DATA_DIR", tmp_path)

    from api import app
    from database import get_session

    def _override_get_session():
        with Session(engine) as session:
            yield session

    app.dependency_overrides[get_session] = _override_get_session
    return engine, app


def _seed_script(engine, script_id: str, *, is_test_lab: bool, title: str | None = None):
    from models.script import Scene, Script, ScriptContent, Segment

    content = ScriptContent(
        title=f"Script {script_id}",
        segments=[
            Segment(
                name="Segment",
                scenes=[
                    Scene(
                        id=f"{script_id}-scene",
                        narration="A single line of narration.",
                        visual_prompt="A clean flat cartoon scene.",
                        duration_estimate_seconds=6,
                    )
                ],
            )
        ],
    )
    with Session(engine) as session:
        session.add(
            Script(
                id=script_id,
                brand_id="default",
                format_id="youtube-listicle",
                topic_title=title or f"Script {script_id}",
                topic_description="",
                script_json=content.model_dump_json(),
                is_test_lab=is_test_lab,
                created_at=datetime.now(timezone.utc),
            )
        )
        session.commit()


def _write_chroma_character(path):
    image = Image.new("RGB", (180, 140), (0, 255, 0))
    draw = ImageDraw.Draw(image)
    draw.rectangle((70, 34, 110, 112), fill=(255, 0, 0))
    image.save(path)


def test_list_scripts_excludes_test_lab_scripts(monkeypatch, tmp_path):
    engine, app = _setup_app(monkeypatch, tmp_path)
    _seed_script(engine, "normal-1", is_test_lab=False)
    _seed_script(engine, "test-lab-1", is_test_lab=True)

    client = TestClient(app)

    from database import get_session

    try:
        response = client.get("/api/scripts")

        assert response.status_code == 200
        ids = [item["id"] for item in response.json()]
        assert ids == ["normal-1"]
    finally:
        app.dependency_overrides.pop(get_session, None)


def test_generate_dedup_ignores_recent_test_lab_scripts(monkeypatch, tmp_path):
    engine, app = _setup_app(monkeypatch, tmp_path)
    _seed_script(engine, "test-lab-same-topic", is_test_lab=True, title="Same Topic")

    import api.scripts as scripts_api
    from pipeline.render_jobs import get_job

    monkeypatch.setattr(scripts_api, "run_in_background", lambda _job_id, _fn: None)
    client = TestClient(app)

    try:
        response = client.post(
            "/api/scripts/generate",
            json={
                "topic": "Same Topic",
                "description": "",
                "format_id": "youtube-listicle",
            },
        )

        assert response.status_code == 200
        job = get_job(response.json()["job_id"])
        assert job is not None
        assert job.status == "pending"
        assert job.output_urls == []
    finally:
        from database import get_session

        app.dependency_overrides.pop(get_session, None)


def test_test_lab_presets_validate_as_script_content():
    from models.script import ScriptContent
    from pipeline.test_lab import TEST_LAB_PRESETS, build_content_from_preset

    assert len(TEST_LAB_PRESETS) == 14
    for preset in TEST_LAB_PRESETS:
        content = build_content_from_preset(preset.id, {})
        validated = ScriptContent.model_validate(content.model_dump())
        assert validated.segments
        assert validated.segments[0].scenes
        if preset.id != "blank":
            assert validated.segments[0].scenes[0].narration
        if preset.id != "blank" and (preset.visual_mode != "stat_card" or preset.visual_prompt):
            assert validated.segments[0].scenes[0].visual_prompt


def test_test_lab_blank_preset_is_first_and_has_empty_scene_fields():
    from pipeline.test_lab import TEST_LAB_PRESETS, build_content_from_preset

    preset = TEST_LAB_PRESETS[0]

    assert preset.id == "blank"
    assert preset.title == "Blank"
    assert preset.description == "Write your own test script"
    assert preset.narration == ""
    assert preset.visual_prompt == ""

    content = build_content_from_preset("blank", {})
    scene = content.segments[0].scenes[0]
    assert scene.narration == ""
    assert scene.visual_prompt == ""


def test_test_lab_preset_accepts_multi_frame_visual_mode():
    from pipeline.test_lab import TestLabPreset

    preset = TestLabPreset(
        id="multi",
        title="Multi",
        description="Multi frame",
        segment_name="Segment",
        narration="First this, then that.",
        visual_prompt="Several examples.",
        visual_mode="multi_frame",
    )

    assert preset.visual_mode == "multi_frame"


def test_test_lab_preset_accepts_continuous_visual_mode():
    from pipeline.test_lab import TestLabPreset

    preset = TestLabPreset(
        id="continuous",
        title="Continuous",
        description="Continuous",
        segment_name="Segment",
        narration="The object grows.",
        visual_prompt="A sprout growing.",
        visual_mode="continuous",
    )

    assert preset.visual_mode == "continuous"


def test_test_lab_accepts_captions_visual_mode_without_treatment_assets():
    from pipeline.test_lab import TestLabPreset

    preset = TestLabPreset(
        id="caption-punch",
        title="Caption Punch",
        description="Caption test",
        segment_name="The point",
        narration="This was the real cost.",
        visual_prompt="",
        visual_mode="captions",
        caption_text="The real cost",
        caption_emphasis="real",
        duration_estimate_seconds=3.0,
    )

    assert preset.visual_mode == "captions"
    assert preset.media_source == "ai"
    assert preset.caption_text == "The real cost"
    assert preset.caption_emphasis == "real"


def test_test_lab_captions_allow_empty_text_overrides():
    from pipeline.test_lab import build_content_from_preset

    content = build_content_from_preset(
        "caption-punch",
        {
            "caption_text": "",
            "caption_emphasis": "",
        },
    )

    scene = content.segments[0].scenes[0]
    assert scene.caption_text == ""
    assert scene.caption_emphasis == ""


def test_test_lab_captions_derive_caption_when_narration_is_custom():
    from pipeline.test_lab import CAPTIONS_TEXT_DEFAULTS, build_content_from_preset

    custom_narration = "The tiny crack spreads across the wall until the whole room feels like it is holding its breath."
    content = build_content_from_preset(
        "coffee-brain",
        {
            "visual_mode": "captions",
            "narration": custom_narration,
            "visual_prompt": "[CLOSE-UP] A cracked cartoon wall.",
            "caption_text": CAPTIONS_TEXT_DEFAULTS["caption_text"],
            "caption_emphasis": CAPTIONS_TEXT_DEFAULTS["caption_emphasis"],
        },
    )

    scene = content.segments[0].scenes[0]
    assert scene.visual_mode == "captions"
    assert scene.narration == custom_narration
    assert scene.caption_text == "The tiny crack spreads across the wall until the whole room feels like it is holding its breath"
    assert scene.caption_emphasis == "breath"


def test_test_lab_captions_default_to_custom_narration_excerpt():
    from pipeline.test_lab import build_content_from_preset

    custom_narration = "The tiny crack spreads across the wall until the whole room feels like it is holding its breath."
    content = build_content_from_preset(
        "caption-punch",
        {
            "visual_mode": "captions",
            "narration": custom_narration,
            "visual_prompt": "[CLOSE-UP] A cracked cartoon wall.",
        },
    )

    scene = content.segments[0].scenes[0]
    assert scene.visual_mode == "captions"
    assert scene.narration == custom_narration
    assert scene.caption_text == "The tiny crack spreads across the wall until the whole room feels like it is holding its breath"
    assert scene.caption_emphasis == "breath"


def test_test_lab_captions_rederive_stale_caption_after_narration_change():
    from pipeline.test_lab import build_content_from_preset

    content = build_content_from_preset(
        "caption-punch",
        {
            "visual_mode": "captions",
            "narration": "The real problem is friction.",
            "caption_text": "The old problem was attention",
            "caption_emphasis": "attention",
        },
    )

    scene = content.segments[0].scenes[0]
    assert scene.caption_text == "The real problem is friction"
    assert scene.caption_emphasis == "friction"


def test_test_lab_settings_preserve_subtitle_style():
    from pipeline.test_lab import build_content_from_preset

    content = build_content_from_preset("coffee-brain", {"subtitle_style": "burst"})

    scene = content.segments[0].scenes[0]
    assert scene.subtitle_style == "burst"


def test_test_lab_flipflop_settings_preserve_action():
    from pipeline.test_lab import build_content_from_preset

    content = build_content_from_preset(
        "coffee-brain",
        {"visual_mode": "flipflop", "flipflop_action": "blink"},
    )

    scene = content.segments[0].scenes[0]
    assert scene.visual_mode == "flipflop"
    assert scene.flipflop_action == "blink"


def test_run_test_lab_manifest_defaults_flipflop_action(monkeypatch, tmp_path):
    engine, _app = _setup_app(monkeypatch, tmp_path)

    import pipeline.test_lab as test_lab

    monkeypatch.setattr(test_lab, "_stage_treatment_assets", lambda _ctx: None)

    test_lab.run_test_lab(
        engine=engine,
        run_id="run-flipflop-action-default",
        preset_id="coffee-brain",
        settings={
            "visual_mode": "flipflop",
            "stages": {
                "audio": False,
                "visual": False,
                "treatment_assets": False,
                "fx": False,
                "render": False,
            },
        },
        job_id=None,
    )

    manifest = test_lab.load_run_manifest("run-flipflop-action-default")
    assert manifest.settings["visual_mode"] == "flipflop"
    assert manifest.settings["flipflop_action"] == "blink"


def test_run_test_lab_manifest_clears_flipflop_action_for_non_flipflop(monkeypatch, tmp_path):
    engine, _app = _setup_app(monkeypatch, tmp_path)

    import pipeline.test_lab as test_lab

    test_lab.run_test_lab(
        engine=engine,
        run_id="run-full-frame-action-clear",
        preset_id="coffee-brain",
        settings={
            "visual_mode": "full_frame",
            "flipflop_action": "head_nod",
            "stages": {
                "audio": False,
                "visual": False,
                "treatment_assets": False,
                "fx": False,
                "render": False,
            },
        },
        job_id=None,
    )

    manifest = test_lab.load_run_manifest("run-full-frame-action-clear")
    assert manifest.settings["visual_mode"] == "full_frame"
    assert manifest.settings["flipflop_action"] == ""


def test_test_lab_scenes_endpoint_returns_presets(monkeypatch, tmp_path):
    _engine, app = _setup_app(monkeypatch, tmp_path)
    client = TestClient(app)

    try:
        response = client.get("/api/test-lab/scenes")

        assert response.status_code == 200
        data = response.json()
        assert len(data["presets"]) == 14
        assert data["presets"][0]["id"] == "blank"
        assert data["presets"][0]["description"] == "Write your own test script"
    finally:
        from database import get_session

        app.dependency_overrides.pop(get_session, None)


def test_test_lab_scenes_endpoint_returns_popup_sequence_text_defaults(monkeypatch, tmp_path):
    _engine, app = _setup_app(monkeypatch, tmp_path)
    client = TestClient(app)

    try:
        response = client.get("/api/test-lab/scenes")

        assert response.status_code == 200
        data = response.json()
        popup_defaults = data["visual_treatment_defaults"]["popup_sequence"]
        assert popup_defaults["narration"] == (
            "Your brain treats every notification like a tiny mystery box: one might be a message, "
            "one might be a reward, and one might be nothing at all."
        )
        assert popup_defaults["visual_prompt"].startswith("[REACTION] Flat 2D cartoon person sitting at a desk")
        assert popup_defaults["visual_prompt"].endswith("no words or letters.")
    finally:
        from database import get_session

        app.dependency_overrides.pop(get_session, None)


def test_test_lab_scenes_endpoint_returns_flipflop_text_defaults(monkeypatch, tmp_path):
    _engine, app = _setup_app(monkeypatch, tmp_path)
    client = TestClient(app)

    try:
        response = client.get("/api/test-lab/scenes")

        assert response.status_code == 200
        data = response.json()
        flipflop_defaults = data["visual_treatment_defaults"]["flipflop"]
        assert flipflop_defaults["narration"] == (
            "He tried to explain the rule calmly, but the longer he talked, the harder it became "
            "to hide how tired he was"
        )
        assert flipflop_defaults["visual_prompt"] == (
            "Flat 2D cartoon person standing behind a small podium in a plain community room, holding an "
            "open book in one hand and gesturing with the other while speaking to people off-camera. The "
            "character looks tired but focused, with simple overhead lighting, a few chairs in the background, "
            "strong clear silhouette, bold outlines, expressive face, clean 2D cartoon aesthetic, no readable "
            "text or letters."
        )
    finally:
        from database import get_session

        app.dependency_overrides.pop(get_session, None)


def test_test_lab_scenes_endpoint_returns_multi_frame_text_defaults(monkeypatch, tmp_path):
    _engine, app = _setup_app(monkeypatch, tmp_path)
    client = TestClient(app)

    try:
        response = client.get("/api/test-lab/scenes")

        assert response.status_code == 200
        data = response.json()
        multi_frame_defaults = data["visual_treatment_defaults"]["multi_frame"]
        assert multi_frame_defaults["narration"] == (
            "First the warning signs were tiny, then they were everywhere, and by the end nobody could pretend "
            "they had not seen them."
        )
        assert multi_frame_defaults["visual_prompt"].startswith(
            "[CONTRAST] Flat 2D cartoon sequence of escalating warning signs in a city"
        )
        assert multi_frame_defaults["visual_prompt"].endswith("no readable words or letters.")
        continuous_defaults = data["visual_treatment_defaults"]["continuous"]
        assert continuous_defaults["narration"] == (
            "The tiny crack spreads across the wall until the whole room feels like it is holding its breath."
        )
        assert continuous_defaults["visual_prompt"].startswith("[CLOSE-UP] Flat 2D cartoon wall")
        assert continuous_defaults["visual_prompt"].endswith("no readable words or letters.")
    finally:
        from database import get_session

        app.dependency_overrides.pop(get_session, None)


def test_test_lab_scenes_endpoint_returns_active_default_character(monkeypatch, tmp_path):
    engine, app = _setup_app(monkeypatch, tmp_path)

    import pipeline.main_character as main_character

    monkeypatch.setattr(main_character, "DATA_DIR", tmp_path)

    from models.settings import AppSetting
    from models.style_preset import StylePreset
    from models.style_preset_character import StylePresetCharacter

    preset_id = "preset-a"
    character_id = "character-a"
    (tmp_path / "style" / "presets").mkdir(parents=True)
    (tmp_path / "style" / "presets" / f"{preset_id}.png").write_bytes(b"fakepng")
    (tmp_path / "style" / "presets" / preset_id / "characters").mkdir(parents=True)
    _write_chroma_character(tmp_path / "style" / "presets" / preset_id / "characters" / f"{character_id}.png")

    with Session(engine) as session:
        session.add(StylePreset(id=preset_id, name="House style", prompt="flat 2d"))
        session.add(
            StylePresetCharacter(
                id=character_id,
                style_preset_id=preset_id,
                name="Mara",
                appearance="A cheerful explorer in a yellow jacket.",
                vibe="Bright and curious.",
                reference_image_url=f"/static/style/presets/{preset_id}/characters/{character_id}.png",
            )
        )
        session.add(AppSetting(key="ACTIVE_STYLE_PRESET_ID", value=preset_id))
        session.add(AppSetting(key=main_character.active_style_preset_character_key(preset_id), value=character_id))
        session.commit()

    client = TestClient(app)

    try:
        response = client.get("/api/test-lab/scenes")

        assert response.status_code == 200
        data = response.json()
        assert data["default_main_character"]["name"] == "Mara"
        assert (
            data["default_main_character"]["reference_image_url"]
            == f"/static/style/presets/{preset_id}/characters/{character_id}.png"
        )
    finally:
        from database import get_session

        app.dependency_overrides.pop(get_session, None)


def test_test_lab_scenes_endpoint_returns_voice_summary(monkeypatch, tmp_path):
    engine, app = _setup_app(monkeypatch, tmp_path)

    from models.brand import BrandProfile
    from models.settings import AppSetting

    import api.test_lab as test_lab_api

    monkeypatch.setattr(
        test_lab_api,
        "list_voices",
        lambda: [{"voice_id": "voice-default", "name": "Headless Hero Narrator", "category": "cloned"}],
    )

    with Session(engine) as session:
        brand = session.get(BrandProfile, "default")
        assert brand is not None
        brand.voice_id = "voice-default"
        session.add(brand)
        session.add(AppSetting(key="ELEVENLABS_TTS_MODEL", value="eleven_multilingual_v2"))
        session.add(AppSetting(key="ELEVENLABS_STABILITY", value="0.45"))
        session.add(AppSetting(key="ELEVENLABS_STYLE", value="0.15"))
        session.add(AppSetting(key="ELEVENLABS_SPEED", value="0.97"))
        session.commit()

    client = TestClient(app)

    try:
        response = client.get("/api/test-lab/scenes")

        assert response.status_code == 200
        summary = response.json()["voice_summary"]
        assert summary["voice_id"] == "voice-default"
        assert summary["voice_name"] == "Headless Hero Narrator"
        assert summary["model_id"] == "eleven_multilingual_v2"
        assert summary["model_label"] == "Eleven v2"
        assert summary["delivery_preset"] == "More Human"
        assert summary["visible_settings"] == [{"label": "Delivery preset", "value": "More Human"}]
    finally:
        from database import get_session

        app.dependency_overrides.pop(get_session, None)


def test_test_lab_scenes_endpoint_returns_subtitle_summary(monkeypatch, tmp_path):
    engine, app = _setup_app(monkeypatch, tmp_path)

    from models.settings import AppSetting

    with Session(engine) as session:
        session.add(AppSetting(key="SUBTITLE_COVERAGE_MODE", value="punchy"))
        session.add(AppSetting(key="SUBTITLE_STYLE_CLEAN_ENABLED", value="true"))
        session.add(AppSetting(key="SUBTITLE_STYLE_KINETIC_ENABLED", value="false"))
        session.add(AppSetting(key="SUBTITLE_STYLE_BURST_ENABLED", value="true"))
        session.add(AppSetting(key="SUBTITLE_HIGHLIGHT_ENABLED", value="false"))
        session.commit()

    client = TestClient(app)

    try:
        response = client.get("/api/test-lab/scenes")

        assert response.status_code == 200
        summary = response.json()["subtitle_summary"]
        assert summary["coverage_label"] == "Punchy scenes"
        assert summary["enabled_style_labels"] == ["Clean", "Burst"]
        assert "highlight_label" not in summary
    finally:
        from database import get_session

        app.dependency_overrides.pop(get_session, None)


def test_popup_crop_preview_generates_sheet_and_crops_fixed_grid(monkeypatch, tmp_path):
    from PIL import Image

    import pipeline.asset_vault as asset_vault
    import pipeline.test_lab_popup_crop as popup_crop

    monkeypatch.setattr(popup_crop, "DATA_DIR", tmp_path)
    monkeypatch.setattr(asset_vault, "DATA_DIR", tmp_path)

    anchor_path = tmp_path / "anchor.png"
    anchor = Image.new("RGB", (200, 200), (0, 255, 0))
    anchor.paste("red", (70, 50, 130, 160))
    anchor.save(anchor_path)

    sheet_path = tmp_path / "item-sheet.png"
    sheet = Image.new("RGB", (600, 200), (0, 255, 0))
    sheet.paste("blue", (55, 60, 145, 150))
    sheet.paste("yellow", (255, 60, 345, 150))
    sheet.paste("purple", (455, 60, 545, 150))
    sheet.save(sheet_path)

    generated_prompts = []

    def fake_generate_image(prompt, *_args, **_kwargs):
        generated_prompts.append(prompt)
        return str(anchor_path if len(generated_prompts) == 1 else sheet_path)

    monkeypatch.setattr(popup_crop, "generate_image", fake_generate_image)

    result = popup_crop.generate_popup_crop_preview(
        anchor_prompt="Generate a detailed recurring character.",
        item_prompt="Generate clean icon cutouts.",
        items=["clock", "barred window", "warning sign"],
        run_id="crop-test",
    )

    assert result.anchor_source_url == "/static/projects/test-lab-popup-crops/crop-test/anchor_source.png"
    assert result.sheet_url == "/static/projects/test-lab-popup-crops/crop-test/item_sheet.png"
    assert [crop.label for crop in result.crops] == ["Anchor character", "clock", "barred window", "warning sign"]
    assert [crop.box for crop in result.crops[1:]] == [
        [0, 0, 200, 200],
        [200, 0, 400, 200],
        [400, 0, 600, 200],
    ]
    assert "same recurring character" in generated_prompts[0]
    assert "left to right in this exact order" in generated_prompts[1]
    assert "Items fill no more than 70% of their slot width" in generated_prompts[1]
    assert "Use bright green (#00FF00) unless any item contains green" in generated_prompts[1]
    assert "Single row only" in generated_prompts[1]
    assert "No drop shadows, glows, or effects" in generated_prompts[1]
    assert "Headless Hero" not in generated_prompts[1]
    assert (tmp_path / "projects" / "test-lab-popup-crops" / "crop-test" / "anchor_source.png").exists()
    assert (tmp_path / "projects" / "test-lab-popup-crops" / "crop-test" / "anchor_cutout.png").exists()
    assert (tmp_path / "projects" / "test-lab-popup-crops" / "crop-test" / "anchor_metadata.json").exists()
    assert (tmp_path / "projects" / "test-lab-popup-crops" / "crop-test" / "item_sheet.png").exists()

    with Image.open(tmp_path / "projects" / "test-lab-popup-crops" / "crop-test" / "anchor_cutout.png") as crop:
        assert crop.mode == "RGBA"
        assert crop.size[0] < 120
        assert crop.size[1] < 160
        assert crop.getpixel((0, 0))[3] == 0

    character_vault = sorted((tmp_path / "projects" / "asset-vault" / "characters").glob("*.png"))
    item_vault = sorted((tmp_path / "projects" / "asset-vault" / "items").glob("*.png"))
    assert len(character_vault) == 1
    assert len(item_vault) == 3
    assert character_vault[0].name.startswith("character_anchor_character_")
    barred_window = next(path for path in item_vault if path.name.startswith("item_barred_window_"))
    with Image.open(barred_window) as vault_crop:
        assert vault_crop.mode == "RGBA"
        assert vault_crop.getpixel((0, 0))[3] == 0


def test_popup_crop_anchor_generate_saves_vault_and_chroma_does_not_duplicate(monkeypatch, tmp_path):
    import pipeline.asset_vault as asset_vault
    import pipeline.test_lab_popup_crop as popup_crop

    monkeypatch.setattr(popup_crop, "DATA_DIR", tmp_path)
    monkeypatch.setattr(asset_vault, "DATA_DIR", tmp_path)

    anchor_path = tmp_path / "anchor.png"
    anchor = Image.new("RGB", (200, 200), (0, 255, 0))
    anchor.paste("red", (70, 50, 130, 160))
    anchor.save(anchor_path)

    monkeypatch.setattr(popup_crop, "generate_image", lambda *_args, **_kwargs: str(anchor_path))

    result = popup_crop.generate_popup_crop_anchor(anchor_prompt="Generate a detailed recurring character.", run_id="anchor-vault")

    assert result.anchor_cutout_url == "/static/projects/test-lab-popup-crops/anchor-vault/anchor_cutout.png"
    character_vault = sorted((tmp_path / "projects" / "asset-vault" / "characters").glob("*.png"))
    assert len(character_vault) == 1
    assert character_vault[0].name.startswith("character_anchor_character_")

    chroma = popup_crop.chroma_popup_crop_anchor(run_id="anchor-vault")

    assert chroma.crops[0].url == "/static/projects/test-lab-popup-crops/anchor-vault/anchor_cutout.png"
    assert sorted((tmp_path / "projects" / "asset-vault" / "characters").glob("*.png")) == character_vault


def test_asset_vault_api_lists_filename_only_cutouts(monkeypatch, tmp_path):
    _engine, app = _setup_app(monkeypatch, tmp_path)

    import pipeline.asset_vault as asset_vault

    monkeypatch.setattr(asset_vault, "DATA_DIR", tmp_path)

    from PIL import Image

    source_path = tmp_path / "source.png"
    Image.new("RGBA", (32, 24), (255, 0, 0, 255)).save(source_path)
    asset_vault.save_vault_image(kind="item", label="Barred window", source_path=source_path)
    asset_vault.save_vault_image(kind="character", label="Anchor character", source_path=source_path)

    client = TestClient(app)

    try:
        response = client.get("/api/assets/vault")
        assert response.status_code == 200
        assets = response.json()["assets"]
        assert {asset["kind"] for asset in assets} == {"character", "item"}
        assert assets[0]["created_at"]
        item = next(asset for asset in assets if asset["kind"] == "item")
        assert item["name"] == "barred window"
        assert item["filename"].startswith("item_barred_window_")
        assert item["url"].startswith("/static/projects/asset-vault/items/item_barred_window_")

        filtered = client.get("/api/assets/vault?kind=character")
        assert filtered.status_code == 200
        assert [asset["kind"] for asset in filtered.json()["assets"]] == ["character"]
    finally:
        from database import get_session

        app.dependency_overrides.pop(get_session, None)


def test_popup_crop_endpoint_returns_preview(monkeypatch, tmp_path):
    _engine, app = _setup_app(monkeypatch, tmp_path)

    import api.test_lab as test_lab_api

    class FakeResult:
        def model_dump(self, mode="python"):
            return {
                "run_id": "fake-run",
                "anchor_prompt_used": "anchor prompt",
                "item_prompt_used": "item prompt",
                "anchor_source_url": "/static/projects/test-lab-popup-crops/fake-run/anchor_source.png",
                "sheet_url": "/static/projects/test-lab-popup-crops/fake-run/item_sheet.png",
                "crops": [
                    {
                        "role": "anchor",
                        "label": "Anchor character",
                        "url": "/static/projects/test-lab-popup-crops/fake-run/anchor_cutout.png",
                        "raw_url": "/static/projects/test-lab-popup-crops/fake-run/anchor_source.png",
                        "box": [0, 0, 200, 200],
                        "trim_box": [20, 20, 120, 160],
                        "warnings": [],
                    }
                ],
            }

    monkeypatch.setattr(
        test_lab_api,
        "generate_popup_crop_preview",
        lambda anchor_prompt, item_prompt, items, run_id=None: FakeResult(),
    )

    client = TestClient(app)

    try:
        response = client.post(
            "/api/test-lab/popup-crop",
            json={"anchor_prompt": "A character", "item_prompt": "A contact sheet", "items": ["clock"]},
        )

        assert response.status_code == 200
        body = response.json()
        assert body["run_id"] == "fake-run"
        assert body["crops"][0]["label"] == "Anchor character"
    finally:
        from database import get_session

        app.dependency_overrides.pop(get_session, None)


def test_popup_crop_split_endpoints_generate_and_chroma_separately(monkeypatch, tmp_path):
    _engine, app = _setup_app(monkeypatch, tmp_path)

    import api.test_lab as test_lab_api

    class FakeAnchor:
        def model_dump(self, mode="python"):
            return {
                "run_id": "split-run",
                "anchor_prompt_used": "anchor prompt",
                "anchor_source_url": "/static/projects/test-lab-popup-crops/split-run/anchor_source.png",
                "anchor_cutout_url": "/static/projects/test-lab-popup-crops/split-run/anchor_cutout.png",
                "warnings": [],
            }

    class FakeSheet:
        def model_dump(self, mode="python"):
            return {
                "run_id": "split-run",
                "item_prompt_used": "item prompt",
                "sheet_url": "/static/projects/test-lab-popup-crops/split-run/item_sheet.png",
            }

    class FakeAnchorChroma:
        def model_dump(self, mode="python"):
            return {
                "run_id": "split-run",
                "crops": [
                    {
                        "role": "anchor",
                        "label": "Anchor character",
                        "url": "/static/projects/test-lab-popup-crops/split-run/anchor_cutout.png",
                        "raw_url": "/static/projects/test-lab-popup-crops/split-run/anchor_source.png",
                        "box": [0, 0, 200, 200],
                        "trim_box": [20, 20, 120, 160],
                        "warnings": [],
                    }
                ],
            }

    class FakeItemChroma:
        def model_dump(self, mode="python"):
            return {
                "run_id": "split-run",
                "crops": [
                    {
                        "role": "item",
                        "label": "clock",
                        "url": "/static/projects/test-lab-popup-crops/split-run/crop_02_clock.png",
                        "raw_url": "/static/projects/test-lab-popup-crops/split-run/raw_crop_02_clock.png",
                        "box": [0, 0, 200, 200],
                        "trim_box": [20, 20, 120, 160],
                        "warnings": [],
                    }
                ],
            }

    monkeypatch.setattr(test_lab_api, "generate_popup_crop_anchor", lambda anchor_prompt, run_id=None: FakeAnchor())
    monkeypatch.setattr(test_lab_api, "chroma_popup_crop_anchor", lambda run_id: FakeAnchorChroma())
    monkeypatch.setattr(test_lab_api, "generate_popup_crop_item_sheet", lambda item_prompt, items, run_id=None: FakeSheet())
    monkeypatch.setattr(test_lab_api, "chroma_popup_crop_item_sheet", lambda run_id, items: FakeItemChroma())

    client = TestClient(app)

    try:
        anchor = client.post("/api/test-lab/popup-crop/anchor", json={"anchor_prompt": "A character"})
        anchor_chroma = client.post("/api/test-lab/popup-crop/anchor/chroma", json={"run_id": "split-run"})
        sheet = client.post(
            "/api/test-lab/popup-crop/items",
            json={"run_id": "split-run", "item_prompt": "Icons", "items": ["clock"]},
        )
        sheet_chroma = client.post(
            "/api/test-lab/popup-crop/items/chroma",
            json={"run_id": "split-run", "items": ["clock"]},
        )

        assert anchor.status_code == 200
        assert anchor.json()["anchor_source_url"].endswith("/anchor_source.png")
        assert anchor_chroma.status_code == 200
        assert anchor_chroma.json()["crops"][0]["role"] == "anchor"
        assert anchor_chroma.json()["crops"][0]["url"].endswith("/anchor_cutout.png")
        assert sheet.status_code == 200
        assert sheet.json()["sheet_url"].endswith("/item_sheet.png")
        assert sheet_chroma.status_code == 200
        assert sheet_chroma.json()["crops"][0]["url"].endswith("/crop_02_clock.png")
    finally:
        from database import get_session

        app.dependency_overrides.pop(get_session, None)


def test_start_test_lab_run_returns_run_and_job(monkeypatch, tmp_path):
    engine, app = _setup_app(monkeypatch, tmp_path)

    import api.test_lab as test_lab_api

    def fake_background(job_id, fn):
        fn()

    monkeypatch.setattr(test_lab_api, "run_in_background", fake_background)

    client = TestClient(app)
    try:
        response = client.post(
            "/api/test-lab/runs",
            json={
                "preset_id": "coffee-brain",
                "settings": {
                    "stages": {"audio": False, "visual": False, "render": False, "eli": False, "fx": False, "treatment_assets": False},
                },
            },
        )

        assert response.status_code == 200
        body = response.json()
        assert body["run_id"]
        assert body["job_id"]

        history = client.get("/api/test-lab/runs")
        assert history.status_code == 200
        assert history.json()["runs"][0]["preset_id"] == "coffee-brain"
    finally:
        from database import get_session

        app.dependency_overrides.pop(get_session, None)


def test_test_lab_status_includes_run_id_without_output_urls(monkeypatch, tmp_path):
    engine, app = _setup_app(monkeypatch, tmp_path)

    import api.test_lab as test_lab_api

    def fake_background(job_id, fn):
        fn()

    monkeypatch.setattr(test_lab_api, "run_in_background", fake_background)

    client = TestClient(app)
    try:
        response = client.post(
            "/api/test-lab/runs",
            json={
                "preset_id": "coffee-brain",
                "settings": {
                    "stages": {
                        "audio": False,
                        "visual": False,
                        "render": False,
                        "eli": False,
                        "fx": False,
                        "treatment_assets": False,
                    },
                },
            },
        )

        assert response.status_code == 200
        body = response.json()

        status = client.get(f"/api/test-lab/runs/status/{body['job_id']}")
        assert status.status_code == 200
        status_body = status.json()
        assert status_body["output_urls"] == []
        assert status_body["run_id"] == body["run_id"]
    finally:
        from database import get_session

        app.dependency_overrides.pop(get_session, None)


def test_test_lab_advanced_script_recomputes_ai_video_enabled():
    from pipeline.test_lab import build_content_from_preset

    content = build_content_from_preset(
        "coffee-brain",
        {
            "advanced_script": {
                "segments": [
                    {
                        "name": "The caffeine switch",
                        "scenes": [
                            {
                                "id": "coffee-brain-scene-1",
                                "narration": "Caffeine blocks the sleepy signal.",
                                "visual_prompt": "Flat 2D cartoon coffee mug powering up a brain.",
                                "media_source": "ai_video",
                            }
                        ],
                    }
                ],
            }
        },
    )

    assert content.segments[0].scenes[0].media_source == "ai_video"
    assert content.ai_video_enabled is True


def test_test_lab_preset_uses_visual_canvas_background_setting():
    from pipeline.test_lab import build_content_from_preset

    content = build_content_from_preset(
        "coffee-brain",
        {"visual_canvas": {"background_color": "#123456"}},
    )

    assert content.visual_canvas.background_color == "#123456"


def test_test_lab_preset_uses_visual_treatment_setting():
    from pipeline.test_lab import build_content_from_preset

    content = build_content_from_preset("coffee-brain", {"visual_treatment": "flipflop"})

    assert content.segments[0].scenes[0].visual_treatment == "flipflop"


def test_test_lab_preset_keeps_scene_text_when_multi_frame_mode_selected():
    from pipeline.test_lab import get_preset, build_content_from_preset

    content = build_content_from_preset("coffee-brain", {"visual_mode": "multi_frame"})
    scene = content.segments[0].scenes[0]
    preset = get_preset("coffee-brain")

    assert scene.visual_mode == "multi_frame"
    assert scene.narration == preset.narration
    assert scene.visual_prompt == preset.visual_prompt


def test_test_lab_preset_keeps_scene_text_when_continuous_mode_selected():
    from pipeline.test_lab import get_preset, build_content_from_preset

    content = build_content_from_preset("coffee-brain", {"visual_mode": "continuous"})
    scene = content.segments[0].scenes[0]
    preset = get_preset("coffee-brain")

    assert scene.visual_mode == "continuous"
    assert scene.narration == preset.narration
    assert scene.visual_prompt == preset.visual_prompt


def test_test_lab_preset_uses_top_level_frame_directives():
    from pipeline.test_lab import build_content_from_preset

    content = build_content_from_preset(
        "coffee-brain",
        {
            "visual_mode": "multi_frame",
            "frame_directives": [
                {
                    "prompt": "Custom frame one.",
                    "source": "ai_generated",
                    "transition": "cut",
                    "reference_previous": False,
                    "search_query": "",
                }
            ],
        },
    )
    scene = content.segments[0].scenes[0]

    assert scene.visual_mode == "multi_frame"
    assert len(scene.frame_directives) == 1
    assert scene.frame_directives[0].prompt == "Custom frame one."


def test_stage_defaults_remove_character_and_direct_eli_stage():
    from pipeline.test_lab import _stage_defaults

    defaults = _stage_defaults(
        {
            "eli_enabled": True,
            "stages": {
                "character": True,
                "eli": False,
                "audio": False,
                "visual": False,
                "render": False,
            },
        }
    )

    assert "character" not in defaults
    assert "eli" not in defaults
    assert defaults["eli_derived"] is True


def test_stage_defaults_derive_treatment_assets_from_visual_mode():
    from pipeline.test_lab import _stage_defaults

    layered_defaults = _stage_defaults(
        {
            "visual_mode": "flipflop",
            "stages": {
                "treatment_assets": False,
            },
        }
    )
    stat_card_defaults = _stage_defaults(
        {
            "visual_mode": "stat_card",
            "stages": {
                "treatment_assets": False,
            },
        }
    )
    normal_defaults = _stage_defaults(
        {
            "visual_mode": "full_frame",
            "stages": {
                "treatment_assets": True,
            },
        }
    )

    assert layered_defaults["treatment_assets"] is True
    assert stat_card_defaults["treatment_assets"] is True
    assert normal_defaults["treatment_assets"] is False


def test_test_lab_advanced_script_keeps_top_level_visual_treatment_when_scene_omits_it():
    from pipeline.test_lab import build_content_from_preset

    content = build_content_from_preset(
        "coffee-brain",
        {
            "visual_treatment": "flipflop",
            "advanced_script": {
                "segments": [
                    {
                        "name": "x",
                        "scenes": [
                            {
                                "id": "adv",
                                "narration": "n",
                                "visual_prompt": "p",
                                "duration_estimate_seconds": 5,
                                "is_title_card": False,
                            }
                        ],
                    }
                ],
            },
        },
    )

    assert content.segments[0].scenes[0].visual_treatment == "flipflop"


def test_test_lab_preset_main_character_is_not_mutated_by_content():
    from pipeline.test_lab import TEST_LAB_PRESETS, build_content_from_preset

    preset = next(item for item in TEST_LAB_PRESETS if item.id == "life-scribe")
    assert preset.main_character is not None
    original_name = preset.main_character.name

    content = build_content_from_preset("life-scribe", {"main_character": preset.main_character.model_dump()})
    assert content.main_character is not None
    content.main_character.name = "Mutated Rowan"

    assert preset.main_character.name == original_name


def test_test_lab_preset_does_not_fall_back_to_dummy_character():
    from pipeline.test_lab import build_content_from_preset

    content = build_content_from_preset("life-scribe", {})

    assert content.main_character is None


def test_test_lab_rejects_unsafe_run_ids(monkeypatch, tmp_path):
    import pytest
    from pydantic import ValidationError

    import pipeline.test_lab as test_lab

    monkeypatch.setattr(test_lab, "DATA_DIR", tmp_path)

    for run_id in ("", "../oops"):
        with pytest.raises(ValidationError):
            test_lab.TestLabRunManifest(
                run_id=run_id,
                script_id="script-1",
                preset_id="life-scribe",
            )
        with pytest.raises(ValueError):
            test_lab.manifest_path(run_id)

    assert not (tmp_path / "test-lab" / "oops.json").exists()
    assert not (tmp_path / "oops.json").exists()


def test_test_lab_history_is_capped_to_20(monkeypatch, tmp_path):
    import pipeline.test_lab as test_lab

    monkeypatch.setattr(test_lab, "DATA_DIR", tmp_path)

    for i in range(25):
        manifest = test_lab.TestLabRunManifest(
            run_id=f"run-{i:02d}",
            script_id=f"script-{i:02d}",
            preset_id="life-scribe",
            status="completed",
            settings={},
        )
        test_lab.save_run_manifest(manifest)

    history = test_lab.list_run_history()

    assert len(history) == 20
    assert history[0].run_id == "run-24"
    assert history[-1].run_id == "run-05"
    assert not (tmp_path / "test-lab" / "runs" / "run-00.json").exists()


def test_create_hidden_test_script_creates_script_and_project_config(monkeypatch, tmp_path):
    engine, _app = _setup_app(monkeypatch, tmp_path)

    from models.project_config import ProjectConfig
    from models.script import Script, ScriptContent
    from pipeline.test_lab import create_hidden_test_script

    with Session(engine) as session:
        script_id = create_hidden_test_script(
            session,
            run_id="run-create",
            preset_id="life-scribe",
            settings={
                "eli_enabled": False,
                "style_preset_enabled": True,
                "main_character": {
                    "name": "Test",
                    "appearance": "cartoon explorer",
                    "vibe": "curious",
                },
            },
        )
        session.commit()

        script = session.get(Script, script_id)
        cfg = session.get(ProjectConfig, script_id)

    assert script is not None
    assert script.is_test_lab is True
    assert script.topic_title == "Your Life as a Medieval Scribe"
    assert cfg is not None
    assert cfg.eli_enabled is False
    content = ScriptContent.model_validate_json(script.script_json)
    assert content.main_character is not None
    assert content.main_character.name == "Test"


def test_create_hidden_test_script_uses_active_style_preset_character(monkeypatch, tmp_path):
    engine, _app = _setup_app(monkeypatch, tmp_path)

    import pipeline.main_character as main_character
    import pipeline.test_lab as test_lab
    from models.settings import AppSetting
    from models.script import Script, ScriptContent
    from models.style_preset import StylePreset
    from models.style_preset_character import StylePresetCharacter

    monkeypatch.setattr(main_character, "DATA_DIR", tmp_path)
    monkeypatch.setattr(test_lab, "DATA_DIR", tmp_path)

    preset_id = "preset-a"
    character_id = "character-a"
    (tmp_path / "style" / "presets").mkdir(parents=True)
    (tmp_path / "style" / "presets" / f"{preset_id}.png").write_bytes(b"fakepng")
    (tmp_path / "style" / "presets" / preset_id / "characters").mkdir(parents=True)
    _write_chroma_character(tmp_path / "style" / "presets" / preset_id / "characters" / f"{character_id}.png")

    with Session(engine) as session:
        session.add(StylePreset(id=preset_id, name="House style", prompt="flat 2d"))
        session.add(
            StylePresetCharacter(
                id=character_id,
                style_preset_id=preset_id,
                name="Mara",
                appearance="A cheerful explorer in a yellow jacket.",
                vibe="Bright and curious.",
                reference_image_url=f"/static/style/presets/{preset_id}/characters/{character_id}.png",
            )
        )
        session.add(AppSetting(key="ACTIVE_STYLE_PRESET_ID", value=preset_id))
        session.add(AppSetting(key=main_character.active_style_preset_character_key(preset_id), value=character_id))
        script_id = test_lab.create_hidden_test_script(
            session,
            run_id="run-active-character",
            preset_id="life-scribe",
            settings={"eli_enabled": False},
        )
        session.commit()

        script = session.get(Script, script_id)

    assert script is not None
    content = ScriptContent.model_validate_json(script.script_json)
    assert content.main_character is not None
    assert content.main_character.name == "Mara"


def test_create_hidden_test_script_skips_active_character_when_style_preset_disabled(monkeypatch, tmp_path):
    engine, _app = _setup_app(monkeypatch, tmp_path)

    import pipeline.main_character as main_character
    import pipeline.test_lab as test_lab
    from models.settings import AppSetting
    from models.script import Script, ScriptContent
    from models.style_preset import StylePreset
    from models.style_preset_character import StylePresetCharacter

    monkeypatch.setattr(main_character, "DATA_DIR", tmp_path)
    monkeypatch.setattr(test_lab, "DATA_DIR", tmp_path)

    preset_id = "preset-a"
    character_id = "character-a"
    (tmp_path / "style" / "presets").mkdir(parents=True)
    (tmp_path / "style" / "presets" / f"{preset_id}.png").write_bytes(b"fakepng")
    (tmp_path / "style" / "presets" / preset_id / "characters").mkdir(parents=True)
    (tmp_path / "style" / "presets" / preset_id / "characters" / f"{character_id}.png").write_bytes(b"fakepng")

    with Session(engine) as session:
        session.add(StylePreset(id=preset_id, name="House style", prompt="flat 2d"))
        session.add(
            StylePresetCharacter(
                id=character_id,
                style_preset_id=preset_id,
                name="Mara",
                appearance="A cheerful explorer in a yellow jacket.",
                vibe="Bright and curious.",
                reference_image_url=f"/static/style/presets/{preset_id}/characters/{character_id}.png",
            )
        )
        session.add(AppSetting(key="ACTIVE_STYLE_PRESET_ID", value=preset_id))
        session.add(AppSetting(key=main_character.active_style_preset_character_key(preset_id), value=character_id))
        script_id = test_lab.create_hidden_test_script(
            session,
            run_id="run-style-disabled",
            preset_id="life-scribe",
            settings={"eli_enabled": False, "style_preset_enabled": False},
        )
        session.commit()

        script = session.get(Script, script_id)

    assert script is not None
    content = ScriptContent.model_validate_json(script.script_json)
    assert content.main_character is None


def test_create_hidden_test_script_coerces_raw_boolean_settings(monkeypatch, tmp_path):
    engine, _app = _setup_app(monkeypatch, tmp_path)

    from models.project_config import ProjectConfig
    from pipeline.test_lab import create_hidden_test_script

    with Session(engine) as session:
        script_id = create_hidden_test_script(
            session,
            run_id="run-coerce",
            preset_id="life-scribe",
            settings={
                "eli_enabled": None,
                "style_preset_enabled": "false",
            },
        )
        session.commit()

        cfg = session.get(ProjectConfig, script_id)

    assert cfg is not None
    assert cfg.eli_enabled is False
    assert cfg.style_preset_enabled is False


def test_create_hidden_test_script_keeps_subtitle_highlight_enabled(monkeypatch, tmp_path):
    engine, _app = _setup_app(monkeypatch, tmp_path)

    from models.script import Script, ScriptContent
    from pipeline.test_lab import create_hidden_test_script

    with Session(engine) as session:
        script_id = create_hidden_test_script(
            session,
            run_id="run-highlight",
            preset_id="coffee-brain",
            settings={"subtitle_highlight_enabled": False},
        )
        session.commit()

        script = session.get(Script, script_id)

    assert script is not None
    content = ScriptContent.model_validate_json(script.script_json)
    assert content.subtitle_highlight_enabled is True


def test_create_hidden_test_script_ignores_saved_subtitle_highlight_setting(monkeypatch, tmp_path):
    engine, _app = _setup_app(monkeypatch, tmp_path)

    from models.script import Script, ScriptContent
    from models.settings import AppSetting
    from pipeline.test_lab import create_hidden_test_script

    with Session(engine) as session:
        session.add(AppSetting(key="SUBTITLE_HIGHLIGHT_ENABLED", value="false"))
        script_id = create_hidden_test_script(
            session,
            run_id="run-highlight-setting",
            preset_id="coffee-brain",
            settings={},
        )
        session.commit()

        script = session.get(Script, script_id)

    assert script is not None
    content = ScriptContent.model_validate_json(script.script_json)
    assert content.subtitle_highlight_enabled is True


def test_stage_character_reference_blocks_eli_disabled_without_selected_reference(monkeypatch, tmp_path):
    import pytest

    engine, _app = _setup_app(monkeypatch, tmp_path)

    import pipeline.test_lab as test_lab

    with Session(engine) as session:
        script_id = test_lab.create_hidden_test_script(
            session,
            run_id="run-character-blocked",
            preset_id="life-scribe",
            settings={"eli_enabled": False},
        )
        session.commit()

    manifest = test_lab.TestLabRunManifest(
        run_id="run-character-blocked",
        script_id=script_id,
        preset_id="life-scribe",
        status="running",
    )
    ctx = test_lab.TestLabRunContext(
        engine=engine,
        run_id="run-character-blocked",
        script_id=script_id,
        preset_id="life-scribe",
        settings={"eli_enabled": False},
        manifest=manifest,
        job_id=None,
    )

    with pytest.raises(RuntimeError, match="Active style preset is missing"):
        test_lab._stage_character_reference(ctx)


def test_stage_character_reference_uses_active_preset_character(monkeypatch, tmp_path):
    engine, _app = _setup_app(monkeypatch, tmp_path)

    import pipeline.main_character as main_character
    import pipeline.test_lab as test_lab
    from models.settings import AppSetting
    from models.style_preset import StylePreset
    from models.style_preset_character import StylePresetCharacter

    monkeypatch.setattr(main_character, "DATA_DIR", tmp_path)
    monkeypatch.setattr(test_lab, "DATA_DIR", tmp_path)

    with Session(engine) as session:
        preset_id = "preset-a"
        character_id = "character-a"
        preset_image = tmp_path / "style" / "presets" / f"{preset_id}.png"
        preset_image.parent.mkdir(parents=True, exist_ok=True)
        preset_image.write_bytes(b"preset")
        character_ref = tmp_path / "style" / "presets" / preset_id / "characters" / f"{character_id}.png"
        character_cutout = tmp_path / "style" / "presets" / preset_id / "characters" / f"{character_id}.cutout.png"
        character_ref.parent.mkdir(parents=True, exist_ok=True)
        _write_chroma_character(character_ref)
        character_cutout.write_bytes(b"preset-main-character-cutout")
        session.add(
            StylePreset(
                id=preset_id,
                name="Mara",
                prompt="bright illustrated style",
                created_at=datetime.now(timezone.utc),
            )
        )
        session.add(
            StylePresetCharacter(
                id=character_id,
                style_preset_id=preset_id,
                name="Mara",
                appearance="A cartographer in a green jacket.",
                vibe="Inventive and calm.",
                reference_image_url=f"/static/style/presets/{preset_id}/characters/{character_id}.png",
                cutout_image_url=f"/static/style/presets/{preset_id}/characters/{character_id}.cutout.png",
                created_at=datetime.now(timezone.utc),
            )
        )
        session.add(AppSetting(key="ACTIVE_STYLE_PRESET_ID", value=preset_id))
        session.add(
            AppSetting(
                key=main_character.active_style_preset_character_key(preset_id),
                value=character_id,
            )
        )
        script_id = test_lab.create_hidden_test_script(
            session,
            run_id="run-preset-character",
            preset_id="life-scribe",
            settings={"eli_enabled": False},
        )
        session.commit()

    manifest = test_lab.TestLabRunManifest(
        run_id="run-preset-character",
        script_id=script_id,
        preset_id="life-scribe",
        status="running",
    )
    ctx = test_lab.TestLabRunContext(
        engine=engine,
        run_id="run-preset-character",
        script_id=script_id,
        preset_id="life-scribe",
        settings={"eli_enabled": False},
        manifest=manifest,
        job_id=None,
    )

    test_lab._stage_character_reference(ctx)

    project_ref = tmp_path / "projects" / script_id / "character" / "reference.png"
    project_cutout = tmp_path / "projects" / script_id / "character" / "cutout.png"
    assert project_ref.read_bytes() == character_ref.read_bytes()
    assert project_cutout.exists()
    with Image.open(project_cutout) as cutout:
        assert cutout.mode == "RGBA"
    assert ctx.manifest.assets[-1].url == f"/static/projects/{script_id}/character/reference.png"


def test_stage_character_reference_skips_when_style_preset_disabled(monkeypatch, tmp_path):
    engine, _app = _setup_app(monkeypatch, tmp_path)

    import pipeline.main_character as main_character
    import pipeline.test_lab as test_lab
    from models.project_config import ProjectConfig
    from models.settings import AppSetting
    from models.style_preset import StylePreset
    from models.style_preset_character import StylePresetCharacter

    monkeypatch.setattr(main_character, "DATA_DIR", tmp_path)
    monkeypatch.setattr(test_lab, "DATA_DIR", tmp_path)

    with Session(engine) as session:
        preset_id = "preset-a"
        character_id = "character-a"
        preset_image = tmp_path / "style" / "presets" / f"{preset_id}.png"
        preset_image.parent.mkdir(parents=True, exist_ok=True)
        preset_image.write_bytes(b"preset")
        character_ref = tmp_path / "style" / "presets" / preset_id / "characters" / f"{character_id}.png"
        character_ref.parent.mkdir(parents=True, exist_ok=True)
        character_ref.write_bytes(b"preset-main-character")
        session.add(
            StylePreset(
                id=preset_id,
                name="Mara",
                prompt="bright illustrated style",
                created_at=datetime.now(timezone.utc),
            )
        )
        session.add(
            StylePresetCharacter(
                id=character_id,
                style_preset_id=preset_id,
                name="Mara",
                appearance="A cartographer in a green jacket.",
                vibe="Inventive and calm.",
                reference_image_url=f"/static/style/presets/{preset_id}/characters/{character_id}.png",
                created_at=datetime.now(timezone.utc),
            )
        )
        session.add(AppSetting(key="ACTIVE_STYLE_PRESET_ID", value=preset_id))
        session.add(
            AppSetting(
                key=main_character.active_style_preset_character_key(preset_id),
                value=character_id,
            )
        )
        script_id = test_lab.create_hidden_test_script(
            session,
            run_id="run-style-disabled-character-stage",
            preset_id="life-scribe",
            settings={"eli_enabled": False, "style_preset_enabled": False},
        )
        session.commit()

    manifest = test_lab.TestLabRunManifest(
        run_id="run-style-disabled-character-stage",
        script_id=script_id,
        preset_id="life-scribe",
        status="running",
    )
    ctx = test_lab.TestLabRunContext(
        engine=engine,
        run_id="run-style-disabled-character-stage",
        script_id=script_id,
        preset_id="life-scribe",
        settings={"eli_enabled": False, "style_preset_enabled": False},
        manifest=manifest,
        job_id=None,
    )

    test_lab._stage_character_reference(ctx)

    with Session(engine) as session:
        cfg = session.get(ProjectConfig, script_id)

    assert cfg is not None
    assert cfg.main_character_reference_url is None
    assert ctx.manifest.assets == []


def test_stage_audio_uses_settings_voice_and_ignores_run_overrides(monkeypatch, tmp_path):
    engine, _app = _setup_app(monkeypatch, tmp_path)

    import pipeline.test_lab as test_lab
    import pipeline.voiceover as voiceover
    from models.brand import BrandProfile
    from models.script import ScriptContent

    monkeypatch.setenv("ELEVENLABS_TTS_MODEL", "eleven_multilingual_v2")
    monkeypatch.setenv("ELEVENLABS_STABILITY", "0.45")
    monkeypatch.setenv("ELEVENLABS_STYLE", "0.15")
    monkeypatch.setenv("ELEVENLABS_SPEED", "0.97")

    with Session(engine) as session:
        brand = session.get(BrandProfile, "default")
        assert brand is not None
        brand.voice_id = "voice-default"
        session.add(brand)
        script_id = test_lab.create_hidden_test_script(
            session,
            run_id="run-audio-settings",
            preset_id="coffee-brain",
            settings={},
        )
        session.commit()

    captured = {}

    def fake_generate_scene_audio(scene_id, narration, voice_id, script_id_arg, *, model_id, voice_settings):
        captured.update(
            {
                "scene_id": scene_id,
                "narration": narration,
                "voice_id": voice_id,
                "script_id": script_id_arg,
                "model_id": model_id,
                "voice_settings": voice_settings,
            }
        )
        return (
            "/static/projects/test/audio/scene.mp3",
            4.2,
            [{"word": "Caffeine", "start_ms": 0, "end_ms": 500}],
            [{"text": "Caffeine", "start_ms": 0, "end_ms": 500}],
        )

    monkeypatch.setattr(voiceover, "generate_scene_audio", fake_generate_scene_audio)

    manifest = test_lab.TestLabRunManifest(
        run_id="run-audio-settings",
        script_id=script_id,
        preset_id="coffee-brain",
        status="running",
    )
    ctx = test_lab.TestLabRunContext(
        engine=engine,
        run_id="run-audio-settings",
        script_id=script_id,
        preset_id="coffee-brain",
        settings={
            "voice_id": "voice-override",
            "voice_model_id": "eleven_turbo_v2_5",
            "voice_settings": {"stability": 0.33, "similarity_boost": 0.75},
        },
        manifest=manifest,
        job_id=None,
    )

    test_lab._stage_audio(ctx)

    assert captured["voice_id"] == "voice-default"
    assert captured["model_id"] == "eleven_multilingual_v2"
    assert captured["voice_settings"]["stability"] == 0.45
    assert captured["voice_settings"]["style"] == 0.15
    assert captured["voice_settings"]["speed"] == 0.97
    with Session(engine) as session:
        record, content = test_lab._load_content_for_script(session, script_id)
        _ = record
        saved = ScriptContent.model_validate(content)
    assert saved.segments[0].scenes[0].audio_url == "/static/projects/test/audio/scene.mp3"


def test_cost_breakdown_scopes_to_script_id(monkeypatch, tmp_path):
    engine, _app = _setup_app(monkeypatch, tmp_path)

    from models.api_usage import ApiUsage
    from pipeline.test_lab import build_cost_breakdown

    with Session(engine) as session:
        session.add(
            ApiUsage(
                script_id="test-script",
                service="elevenlabs",
                operation="tts",
                model="eleven_multilingual_v2",
                characters=100,
                cost_estimate=0.01,
            )
        )
        session.add(
            ApiUsage(
                script_id="other-script",
                service="google_ai",
                operation="image_gen",
                model="gemini",
                images=1,
                cost_estimate=0.03,
            )
        )
        session.add(
            ApiUsage(
                script_id="test-script",
                service="google_ai",
                operation="image_gen",
                model="gemini",
                images=1,
                cost_estimate=0.02,
            )
        )
        session.commit()

        cost = build_cost_breakdown(session, "test-script")

    assert cost["total_cost"] == 0.03
    assert {item["service"] for item in cost["breakdown"]} == {"elevenlabs", "google_ai"}


def test_cost_breakdown_total_uses_raw_usage_sum(monkeypatch, tmp_path):
    engine, _app = _setup_app(monkeypatch, tmp_path)

    from models.api_usage import ApiUsage
    from pipeline.test_lab import build_cost_breakdown

    with Session(engine) as session:
        session.add(
            ApiUsage(
                script_id="test-script",
                service="elevenlabs",
                operation="tts",
                model="eleven_multilingual_v2",
                cost_estimate=0.00004,
            )
        )
        session.add(
            ApiUsage(
                script_id="test-script",
                service="google_ai",
                operation="image_gen",
                model="gemini",
                cost_estimate=0.00004,
            )
        )
        session.commit()

        cost = build_cost_breakdown(session, "test-script")

    assert cost["total_cost"] == 0.0001
    assert sum(item["total_cost"] for item in cost["breakdown"]) == 0.0


def test_run_test_lab_phases_uses_selected_order_and_classifies_assets(monkeypatch, tmp_path):
    engine, _app = _setup_app(monkeypatch, tmp_path)

    import pipeline.test_lab as test_lab

    calls = []

    def fake_audio(ctx):
        calls.append("audio")
        ctx.manifest.assets.append(test_lab.TestLabAsset(kind="audio", label="Voiceover", url="/static/projects/test/audio/scene.mp3"))

    def fake_visual(ctx):
        calls.append("visual")
        ctx.manifest.assets.append(test_lab.TestLabAsset(kind="video", label="AI video", url="/static/projects/test/videos/scene.mp4"))
        ctx.manifest.assets.append(test_lab.TestLabAsset(kind="image", label="Anchor image", url="/static/projects/test/images/scene.png"))

    def fake_render(ctx):
        calls.append("render")
        ctx.manifest.render_url = "/static/projects/test/renders/full_youtube.mp4"
        ctx.manifest.assets.append(test_lab.TestLabAsset(kind="render", label="Remotion render", url=ctx.manifest.render_url))

    monkeypatch.setattr(test_lab, "_stage_audio", fake_audio)
    monkeypatch.setattr(test_lab, "_stage_visual", fake_visual)
    monkeypatch.setattr(test_lab, "_stage_treatment_assets", lambda ctx: calls.append("treatment"))
    monkeypatch.setattr(test_lab, "_stage_fx", lambda ctx: calls.append("fx"))
    monkeypatch.setattr(test_lab, "_stage_eli", lambda ctx: calls.append("eli"))
    monkeypatch.setattr(test_lab, "_stage_render", fake_render)

    output_urls = test_lab.run_test_lab(
        engine=engine,
        run_id="run-phases",
        preset_id="coffee-brain",
        settings={
            "eli_enabled": True,
            "media_source": "ai_video",
            "stages": {
                "audio": True,
                "visual": True,
                "treatment_assets": True,
                "fx": True,
                "eli": True,
                "render": True,
            },
        },
        job_id=None,
    )

    manifest = test_lab.load_run_manifest("run-phases")

    assert calls == ["audio", "visual", "fx", "eli", "render"]
    assert output_urls == ["/static/projects/test/renders/full_youtube.mp4"]
    assert manifest.status == "completed"
    assert [asset.kind for asset in manifest.assets] == ["audio", "video", "image", "render"]


def test_run_test_lab_defaults_enable_stat_card_treatment_assets(monkeypatch, tmp_path):
    engine, _app = _setup_app(monkeypatch, tmp_path)

    import pipeline.test_lab as test_lab

    calls = []

    monkeypatch.setattr(test_lab, "_stage_audio", lambda ctx: calls.append("audio"))
    monkeypatch.setattr(test_lab, "_stage_visual", lambda ctx: calls.append("visual"))
    monkeypatch.setattr(test_lab, "_stage_treatment_assets", lambda ctx: calls.append("treatment"))
    monkeypatch.setattr(test_lab, "_stage_fx", lambda ctx: calls.append("fx"))
    monkeypatch.setattr(test_lab, "_stage_eli", lambda ctx: calls.append("eli"))
    monkeypatch.setattr(test_lab, "_stage_render", lambda ctx: calls.append("render"))

    test_lab.run_test_lab(
        engine=engine,
        run_id="run-stat-card-default-stages",
        preset_id="stat-card-with-icon",
        settings={},
        job_id=None,
    )

    assert calls == ["audio", "visual", "treatment", "render"]


def test_stage_treatment_assets_respects_explicit_treatment(monkeypatch, tmp_path):
    engine, _app = _setup_app(monkeypatch, tmp_path)

    import pipeline.image_gen as image_gen
    import pipeline.test_lab as test_lab
    import pipeline.visual_treatments as visual_treatments
    from models.script import ScriptContent

    with Session(engine) as session:
        script_id = test_lab.create_hidden_test_script(
            session,
            run_id="run-explicit-treatment",
            preset_id="coffee-brain",
            settings={
                "visual_treatment": "flipflop",
                "advanced_script": {
                    "segments": [
                        {
                            "name": "The caffeine switch",
                            "scenes": [
                                {
                                    "id": "coffee-brain-scene-1",
                                    "narration": "Caffeine blocks the sleepy signal.",
                                    "visual_prompt": "Flat 2D cartoon coffee mug powering up a brain.",
                                    "visual_treatment": "flipflop",
                                    "visual_layers": [
                                        {
                                            "id": "panel-a",
                                            "type": "image",
                                            "asset_kind": "panel",
                                            "prompt": "A simple panel.",
                                        }
                                    ],
                                }
                            ],
                        }
                    ],
                },
            },
        )
        session.commit()

    monkeypatch.setattr(
        visual_treatments,
        "analyze_visual_treatments",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(AssertionError("should not analyze explicit treatment")),
    )

    def fail_panel_generation(*_args, **_kwargs):
        raise AssertionError("flipflop should use cutout generation")

    def fake_generate_flipflop_cutouts(**kwargs):
        assert kwargs["scene_id"] == "coffee-brain-scene-1"
        assert kwargs["script_id"] == script_id
        assert kwargs["layers"][0]["id"] == "panel-a"
        return [{**kwargs["layers"][0], "asset_kind": "cutout", "image_url": "/static/projects/test/layers/panel-a.png"}]

    monkeypatch.setattr(image_gen, "generate_visual_layer_panels", fail_panel_generation)
    monkeypatch.setattr(image_gen, "generate_flipflop_cutouts", fake_generate_flipflop_cutouts)

    manifest = test_lab.TestLabRunManifest(
        run_id="run-explicit-treatment",
        script_id=script_id,
        preset_id="coffee-brain",
        status="running",
    )
    ctx = test_lab.TestLabRunContext(
        engine=engine,
        run_id="run-explicit-treatment",
        script_id=script_id,
        preset_id="coffee-brain",
        settings={},
        manifest=manifest,
        job_id=None,
    )

    test_lab._stage_treatment_assets(ctx)

    with Session(engine) as session:
        record, content = test_lab._load_content_for_script(session, script_id)
        _ = record
        saved = ScriptContent.model_validate(content)

    scene = saved.segments[0].scenes[0]
    assert scene.visual_treatment == "flipflop"
    assert scene.visual_layers
    assert scene.visual_layers[0].image_url == "/static/projects/test/layers/panel-a.png"
    assert [asset.kind for asset in manifest.assets] == ["treatment_asset"]


def test_stage_treatment_assets_generates_fallback_flipflop_cutout_urls(monkeypatch, tmp_path):
    engine, _app = _setup_app(monkeypatch, tmp_path)

    import pipeline.image_gen as image_gen
    import pipeline.test_lab as test_lab
    import pipeline.visual_treatments as visual_treatments
    from models.script import ScriptContent

    with Session(engine) as session:
        script_id = test_lab.create_hidden_test_script(
            session,
            run_id="run-flipflop-fallback",
            preset_id="coffee-brain",
            settings={
                "visual_treatment": "flipflop",
                "visual_layers": [],
                "contains_person": True,
            },
        )
        session.commit()

    monkeypatch.setattr(
        visual_treatments,
        "analyze_visual_treatments",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(AssertionError("should use fallback without timing")),
    )

    def fail_panel_generation(*_args, **_kwargs):
        raise AssertionError("fallback flipflop cutouts should not use panel generation")

    def fake_generate_flipflop_cutouts(**kwargs):
        assert kwargs["scene_id"] == "coffee-brain-scene-1"
        assert kwargs["script_id"] == script_id
        assert [layer["id"] for layer in kwargs["layers"]] == [
            "coffee-brain-scene-1_state_a",
            "coffee-brain-scene-1_state_b",
        ]
        assert [layer["asset_kind"] for layer in kwargs["layers"]] == ["cutout", "cutout"]
        assert [layer["enter_at_seconds"] for layer in kwargs["layers"]] == [0.0, 0.0]
        assert kwargs["contains_person"] is True
        return [
            {**kwargs["layers"][0], "asset_kind": "cutout", "image_url": "/static/projects/test/layers/state-a.png"},
            {**kwargs["layers"][1], "asset_kind": "cutout", "image_url": "/static/projects/test/layers/state-b.png"},
        ]

    monkeypatch.setattr(image_gen, "generate_visual_layer_panels", fail_panel_generation)
    monkeypatch.setattr(image_gen, "generate_flipflop_cutouts", fake_generate_flipflop_cutouts)

    manifest = test_lab.TestLabRunManifest(
        run_id="run-flipflop-fallback",
        script_id=script_id,
        preset_id="coffee-brain",
        status="running",
    )
    ctx = test_lab.TestLabRunContext(
        engine=engine,
        run_id="run-flipflop-fallback",
        script_id=script_id,
        preset_id="coffee-brain",
        settings={"visual_treatment": "flipflop", "visual_layers": [], "contains_person": True},
        manifest=manifest,
        job_id=None,
    )

    test_lab._stage_treatment_assets(ctx)

    with Session(engine) as session:
        record, content = test_lab._load_content_for_script(session, script_id)
        _ = record
        saved = ScriptContent.model_validate(content)

    scene = saved.segments[0].scenes[0]
    assert scene.visual_treatment == "flipflop"
    assert [layer.image_url for layer in scene.visual_layers] == [
        "/static/projects/test/layers/state-a.png",
        "/static/projects/test/layers/state-b.png",
    ]
    assert [asset.url for asset in manifest.assets] == [
        "/static/projects/test/layers/state-a.png",
        "/static/projects/test/layers/state-b.png",
    ]


def test_stage_treatment_assets_preserves_explicit_flipflop_action_without_analyzer(monkeypatch, tmp_path):
    engine, _app = _setup_app(monkeypatch, tmp_path)

    import pipeline.image_gen as image_gen
    import pipeline.test_lab as test_lab
    import pipeline.visual_treatments as visual_treatments
    from models.script import ScriptContent

    with Session(engine) as session:
        script_id = test_lab.create_hidden_test_script(
            session,
            run_id="run-flipflop-action-preserve",
            preset_id="blank",
            settings={
                "visual_mode": "flipflop",
                "visual_prompt": "Young employee in a plain red polo and visor, isolated chest-up character.",
                "narration": "He answers the impossible burger question.",
                "flipflop_action": "speaking_mouth",
                "visual_layers": [],
            },
        )
        record, content = test_lab._load_content_for_script(session, script_id)
        scene = content.segments[0].scenes[0]
        scene.audio_duration_seconds = 5.0
        scene.word_timestamps = [{"word": "He", "start_ms": 0, "end_ms": 200}]
        test_lab._save_content(session, record, content)
        session.commit()

    captured_layers = []

    def fake_generate_flipflop_cutouts(**kwargs):
        assert kwargs["contains_person"] is True
        captured_layers.extend(kwargs["layers"])
        return [
            {**kwargs["layers"][0], "asset_kind": "cutout", "image_url": "/static/projects/test/layers/state-a.png"},
            {**kwargs["layers"][1], "asset_kind": "cutout", "image_url": "/static/projects/test/layers/state-b.png"},
        ]

    monkeypatch.setattr(
        visual_treatments,
        "analyze_visual_treatments",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(AssertionError("explicit flipflop should not analyze")),
    )
    monkeypatch.setattr(image_gen, "generate_flipflop_cutouts", fake_generate_flipflop_cutouts)
    monkeypatch.setattr(
        image_gen,
        "generate_visual_layer_panels",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(AssertionError("flipflop should not use panel generation")),
    )

    manifest = test_lab.TestLabRunManifest(
        run_id="run-flipflop-action-preserve",
        script_id=script_id,
        preset_id="blank",
        status="running",
    )
    ctx = test_lab.TestLabRunContext(
        engine=engine,
        run_id="run-flipflop-action-preserve",
        script_id=script_id,
        preset_id="blank",
        settings={
            "visual_mode": "flipflop",
            "flipflop_action": "speaking_mouth",
            "visual_layers": [],
        },
        manifest=manifest,
        job_id=None,
    )

    test_lab._stage_treatment_assets(ctx)

    assert "mouth closed or lightly resting" in captured_layers[0]["prompt"]
    assert "mouth slightly open as if speaking one syllable" in captured_layers[1]["prompt"]

    with Session(engine) as session:
        _record, saved = test_lab._load_content_for_script(session, script_id)
        scene = ScriptContent.model_validate(saved).segments[0].scenes[0]

    assert scene.visual_mode == "flipflop"
    assert scene.flipflop_action == "speaking_mouth"


def test_stage_treatment_assets_generates_stat_card_icon_cutout(monkeypatch, tmp_path):
    engine, _app = _setup_app(monkeypatch, tmp_path)

    import pipeline.image_gen as image_gen
    import pipeline.test_lab as test_lab
    from models.script import ScriptContent

    with Session(engine) as session:
        script_id = test_lab.create_hidden_test_script(
            session,
            run_id="run-stat-card-icon",
            preset_id="stat-card-with-icon",
            settings={},
        )
        session.commit()

    def fail_panel_generation(*_args, **_kwargs):
        raise AssertionError("stat_card should use stat-card cutout generation")

    def fake_generate_stat_card_cutout(**kwargs):
        assert kwargs["scene_id"] == "stat-card-with-icon-scene-1"
        assert kwargs["script_id"] == script_id
        assert "padlock icon" in kwargs["scene_prompt"]
        assert [layer["id"] for layer in kwargs["layers"]] == ["stat-card-with-icon-stat-icon"]
        return [
            {
                **kwargs["layers"][0],
                "asset_kind": "cutout",
                "image_url": "/static/projects/test/stat_cards/stat-card-with-icon-scene-1/icon_cutout.png",
            }
        ]

    monkeypatch.setattr(image_gen, "generate_visual_layer_panels", fail_panel_generation)
    monkeypatch.setattr(image_gen, "generate_stat_card_cutout", fake_generate_stat_card_cutout)

    manifest = test_lab.TestLabRunManifest(
        run_id="run-stat-card-icon",
        script_id=script_id,
        preset_id="stat-card-with-icon",
        status="running",
    )
    ctx = test_lab.TestLabRunContext(
        engine=engine,
        run_id="run-stat-card-icon",
        script_id=script_id,
        preset_id="stat-card-with-icon",
        settings={},
        manifest=manifest,
        job_id=None,
    )

    test_lab._stage_treatment_assets(ctx)

    with Session(engine) as session:
        record, content = test_lab._load_content_for_script(session, script_id)
        _ = record
        saved = ScriptContent.model_validate(content)

    scene = saved.segments[0].scenes[0]
    assert scene.visual_treatment == "stat_card"
    assert [layer.image_url for layer in scene.visual_layers] == [
        "/static/projects/test/stat_cards/stat-card-with-icon-scene-1/icon_cutout.png"
    ]
    assert [asset.url for asset in manifest.assets] == [
        "/static/projects/test/stat_cards/stat-card-with-icon-scene-1/icon_cutout.png"
    ]


def test_stage_treatment_assets_stat_card_no_icon_keeps_layers_empty(monkeypatch, tmp_path):
    engine, _app = _setup_app(monkeypatch, tmp_path)

    import pipeline.image_gen as image_gen
    import pipeline.test_lab as test_lab
    from models.script import ScriptContent

    with Session(engine) as session:
        script_id = test_lab.create_hidden_test_script(
            session,
            run_id="run-stat-card-no-icon",
            preset_id="stat-card-no-icon",
            settings={},
        )
        session.commit()

    monkeypatch.setattr(
        image_gen,
        "generate_stat_card_cutout",
        lambda **_kwargs: (_ for _ in ()).throw(AssertionError("stat_card without icon should not generate cutouts")),
    )
    monkeypatch.setattr(
        image_gen,
        "generate_flipflop_cutouts",
        lambda **_kwargs: (_ for _ in ()).throw(AssertionError("stat_card should not synthesize flipflop layers")),
    )

    manifest = test_lab.TestLabRunManifest(
        run_id="run-stat-card-no-icon",
        script_id=script_id,
        preset_id="stat-card-no-icon",
        status="running",
    )
    ctx = test_lab.TestLabRunContext(
        engine=engine,
        run_id="run-stat-card-no-icon",
        script_id=script_id,
        preset_id="stat-card-no-icon",
        settings={},
        manifest=manifest,
        job_id=None,
    )

    test_lab._stage_treatment_assets(ctx)

    with Session(engine) as session:
        record, content = test_lab._load_content_for_script(session, script_id)
        _ = record
        saved = ScriptContent.model_validate(content)

    scene = saved.segments[0].scenes[0]
    assert scene.visual_treatment == "stat_card"
    assert scene.visual_layers == []
    assert manifest.assets == []


def test_stage_treatment_assets_skips_ai_video_scenes(monkeypatch, tmp_path):
    engine, _app = _setup_app(monkeypatch, tmp_path)

    import pipeline.image_gen as image_gen
    import pipeline.test_lab as test_lab
    import pipeline.visual_treatments as visual_treatments

    with Session(engine) as session:
        script_id = test_lab.create_hidden_test_script(
            session,
            run_id="run-ai-video-treatment",
            preset_id="coffee-brain",
            settings={
                "media_source": "ai_video",
                "visual_treatment": "flipflop",
                "advanced_script": {
                    "segments": [
                        {
                            "name": "The caffeine switch",
                            "scenes": [
                                {
                                    "id": "coffee-brain-scene-1",
                                    "media_source": "ai_video",
                                    "narration": "Caffeine blocks the sleepy signal.",
                                    "visual_prompt": "Flat 2D cartoon coffee mug powering up a brain.",
                                    "visual_treatment": "flipflop",
                                    "visual_layers": [
                                        {
                                            "id": "panel-a",
                                            "type": "image",
                                            "asset_kind": "panel",
                                            "prompt": "A simple panel.",
                                        }
                                    ],
                                }
                            ],
                        }
                    ],
                },
            },
        )
        session.commit()

    monkeypatch.setattr(
        visual_treatments,
        "analyze_visual_treatments",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(AssertionError("should not analyze ai video treatments")),
    )
    monkeypatch.setattr(
        image_gen,
        "generate_visual_layer_panels",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(AssertionError("should not generate ai video treatment assets")),
    )

    manifest = test_lab.TestLabRunManifest(
        run_id="run-ai-video-treatment",
        script_id=script_id,
        preset_id="coffee-brain",
        status="running",
    )
    ctx = test_lab.TestLabRunContext(
        engine=engine,
        run_id="run-ai-video-treatment",
        script_id=script_id,
        preset_id="coffee-brain",
        settings={"visual_treatment": "flipflop"},
        manifest=manifest,
        job_id=None,
    )

    test_lab._stage_treatment_assets(ctx)

    with Session(engine) as session:
        _record, content = test_lab._load_content_for_script(session, script_id)

    scene = content.segments[0].scenes[0]
    assert scene.visual_treatment == "full_frame"
    assert scene.visual_layers == []
    assert manifest.assets == []


def test_run_test_lab_normalizes_ai_video_treatment_when_stage_skipped(monkeypatch, tmp_path):
    engine, _app = _setup_app(monkeypatch, tmp_path)

    import pipeline.test_lab as test_lab

    calls = []

    monkeypatch.setattr(test_lab, "_stage_audio", lambda ctx: calls.append("audio"))
    monkeypatch.setattr(test_lab, "_stage_visual", lambda ctx: calls.append("visual"))
    monkeypatch.setattr(test_lab, "_stage_treatment_assets", lambda ctx: calls.append("treatment"))
    monkeypatch.setattr(test_lab, "_stage_fx", lambda ctx: calls.append("fx"))
    monkeypatch.setattr(test_lab, "_stage_eli", lambda ctx: calls.append("eli"))
    monkeypatch.setattr(test_lab, "_stage_render", lambda ctx: calls.append("render"))

    test_lab.run_test_lab(
        engine=engine,
        run_id="run-ai-video-skip-treatment",
        preset_id="coffee-brain",
        settings={
            "media_source": "ai_video",
            "visual_treatment": "flipflop",
            "visual_layers": [
                {
                    "id": "panel-a",
                    "type": "image",
                    "asset_kind": "panel",
                    "prompt": "A stale panel.",
                }
            ],
            "stages": {
                "audio": False,
                "visual": False,
                "treatment_assets": False,
                "fx": False,
                "eli": False,
                "render": False,
            },
        },
        job_id=None,
    )

    manifest = test_lab.load_run_manifest("run-ai-video-skip-treatment")
    assert calls == []
    assert manifest.status == "completed"

    with Session(engine) as session:
        _record, content = test_lab._load_content_for_script(session, manifest.script_id)

    scene = content.segments[0].scenes[0]
    assert scene.media_source == "ai_video"
    assert scene.visual_treatment == "full_frame"
    assert scene.visual_layers == []


def test_stage_treatment_assets_analyzes_empty_selected_layer_treatment(monkeypatch, tmp_path):
    engine, _app = _setup_app(monkeypatch, tmp_path)

    import pipeline.image_gen as image_gen
    import pipeline.test_lab as test_lab
    import pipeline.visual_treatments as visual_treatments
    from models.script import ScriptContent, VisualLayer
    from pipeline.visual_treatments import VisualTreatmentAssignment

    with Session(engine) as session:
        script_id = test_lab.create_hidden_test_script(
            session,
            run_id="run-empty-selected-treatment",
            preset_id="coffee-brain",
            settings={
                "visual_treatment": "popup_sequence",
                "visual_layers": [],
            },
        )
        record, content = test_lab._load_content_for_script(session, script_id)
        scene = content.segments[0].scenes[0]
        scene.audio_duration_seconds = 6.0
        scene.word_timestamps = [{"word": "Caffeine", "start_ms": 0, "end_ms": 500}]
        record.script_json = content.model_dump_json()
        session.add(record)
        session.commit()

    def fake_analyze(content, *, script_id):
        scene = content.segments[0].scenes[0]
        return [
            VisualTreatmentAssignment(
                scene_id=scene.id,
                visual_treatment="popup_sequence",
                visual_layers=[
                    VisualLayer(
                        id="generated-layer",
                        prompt="Generated layer prompt.",
                        placement="center",
                    )
                ],
            )
        ]

    def fake_generate_popup_sequence_cutouts(**kwargs):
        assert kwargs["scene_id"] == "coffee-brain-scene-1"
        assert kwargs["script_id"] == script_id
        assert kwargs["layers"][0]["id"] == "generated-layer"
        return [
            {"id": "coffee-brain-scene-1_anchor", "type": "image", "asset_kind": "cutout", "image_url": "/static/projects/test/layers/anchor.png"},
            {**kwargs["layers"][0], "asset_kind": "cutout", "image_url": "/static/projects/test/layers/generated-layer.png"},
        ]

    monkeypatch.setattr(visual_treatments, "analyze_visual_treatments", fake_analyze)
    monkeypatch.setattr(image_gen, "generate_popup_sequence_cutouts", fake_generate_popup_sequence_cutouts)

    manifest = test_lab.TestLabRunManifest(
        run_id="run-empty-selected-treatment",
        script_id=script_id,
        preset_id="coffee-brain",
        status="running",
    )
    ctx = test_lab.TestLabRunContext(
        engine=engine,
        run_id="run-empty-selected-treatment",
        script_id=script_id,
        preset_id="coffee-brain",
        settings={"visual_treatment": "popup_sequence", "visual_layers": []},
        manifest=manifest,
        job_id=None,
    )

    test_lab._stage_treatment_assets(ctx)

    with Session(engine) as session:
        record, content = test_lab._load_content_for_script(session, script_id)
        _ = record
        saved = ScriptContent.model_validate(content)

    scene = saved.segments[0].scenes[0]
    assert scene.visual_treatment == "popup_sequence"
    assert scene.visual_layers
    assert scene.visual_layers[1].image_url == "/static/projects/test/layers/generated-layer.png"
    assert [asset.kind for asset in manifest.assets] == ["treatment_asset", "treatment_asset"]


def test_stage_treatment_assets_ignores_mismatched_assignment_for_selected_treatment(monkeypatch, tmp_path):
    engine, _app = _setup_app(monkeypatch, tmp_path)

    import pipeline.image_gen as image_gen
    import pipeline.test_lab as test_lab
    import pipeline.visual_treatments as visual_treatments
    from models.script import ScriptContent, VisualLayer
    from pipeline.visual_treatments import VisualTreatmentAssignment

    with Session(engine) as session:
        script_id = test_lab.create_hidden_test_script(
            session,
            run_id="run-selected-popup-mismatch",
            preset_id="coffee-brain",
            settings={
                "narration": "You know the problem: missing keys, spoiled lunch, and an angry prisoner, and you know it cannot end well.",
                "tts_narration": "You know the problem: missing keys, spoiled lunch, and an angry prisoner, and you know it cannot end well.",
                "visual_treatment": "popup_sequence",
                "visual_layers": [],
            },
        )
        record, content = test_lab._load_content_for_script(session, script_id)
        scene = content.segments[0].scenes[0]
        scene.audio_duration_seconds = 6.0
        scene.word_timestamps = [
            {"word": "You", "start_ms": 0, "end_ms": 200},
            {"word": "know", "start_ms": 250, "end_ms": 450},
            {"word": "missing", "start_ms": 1000, "end_ms": 1200},
            {"word": "keys", "start_ms": 1250, "end_ms": 1450},
            {"word": "spoiled", "start_ms": 1800, "end_ms": 2000},
            {"word": "lunch", "start_ms": 2050, "end_ms": 2250},
            {"word": "angry", "start_ms": 3000, "end_ms": 3200},
            {"word": "prisoner", "start_ms": 3250, "end_ms": 3450},
            {"word": "know", "start_ms": 4000, "end_ms": 4200},
        ]
        record.script_json = content.model_dump_json()
        session.add(record)
        session.commit()

    def fake_analyze(content, *, script_id):
        scene = content.segments[0].scenes[0]
        return [
            VisualTreatmentAssignment(
                scene_id=scene.id,
                visual_treatment="flipflop",
                visual_layers=[
                    VisualLayer(
                        id=f"{scene.id}_state_a",
                        prompt="State A prompt.",
                        placement="center",
                    ),
                    VisualLayer(
                        id=f"{scene.id}_state_b",
                        prompt="State B prompt.",
                        placement="center",
                        enter_at_seconds=3.0,
                    ),
                ],
            )
        ]

    def fake_generate_popup_sequence_cutouts(**kwargs):
        assert kwargs["scene_id"] == "coffee-brain-scene-1"
        assert kwargs["script_id"] == script_id
        assert [layer["id"] for layer in kwargs["layers"]] == [
            "coffee-brain-scene-1_popup_1",
            "coffee-brain-scene-1_popup_2",
            "coffee-brain-scene-1_popup_3",
        ]
        return [
            {"id": "coffee-brain-scene-1_anchor", "type": "image", "asset_kind": "cutout", "image_url": "/static/projects/test/layers/anchor.png"},
            {**kwargs["layers"][0], "asset_kind": "cutout", "image_url": "/static/projects/test/layers/popup-1.png"},
            {**kwargs["layers"][1], "asset_kind": "cutout", "image_url": "/static/projects/test/layers/popup-2.png"},
            {**kwargs["layers"][2], "asset_kind": "cutout", "image_url": "/static/projects/test/layers/popup-3.png"},
        ]

    monkeypatch.setattr(visual_treatments, "analyze_visual_treatments", fake_analyze)
    monkeypatch.setattr(image_gen, "generate_popup_sequence_cutouts", fake_generate_popup_sequence_cutouts)

    manifest = test_lab.TestLabRunManifest(
        run_id="run-selected-popup-mismatch",
        script_id=script_id,
        preset_id="coffee-brain",
        status="running",
    )
    ctx = test_lab.TestLabRunContext(
        engine=engine,
        run_id="run-selected-popup-mismatch",
        script_id=script_id,
        preset_id="coffee-brain",
        settings={"visual_treatment": "popup_sequence", "visual_layers": []},
        manifest=manifest,
        job_id=None,
    )

    test_lab._stage_treatment_assets(ctx)

    with Session(engine) as session:
        record, content = test_lab._load_content_for_script(session, script_id)
        _ = record
        saved = ScriptContent.model_validate(content)

    scene = saved.segments[0].scenes[0]
    assert scene.visual_treatment == "popup_sequence"
    assert [layer.id for layer in scene.visual_layers] == [
        "coffee-brain-scene-1_anchor",
        "coffee-brain-scene-1_popup_1",
        "coffee-brain-scene-1_popup_2",
        "coffee-brain-scene-1_popup_3",
    ]


def test_stage_treatment_assets_uses_fallback_for_explicit_layer_treatment_without_audio(monkeypatch, tmp_path):
    engine, _app = _setup_app(monkeypatch, tmp_path)

    import pipeline.image_gen as image_gen
    import pipeline.test_lab as test_lab
    import pipeline.visual_treatments as visual_treatments
    from models.script import ScriptContent

    with Session(engine) as session:
        script_id = test_lab.create_hidden_test_script(
            session,
            run_id="run-treatment-no-audio",
            preset_id="coffee-brain",
            settings={
                "visual_treatment": "popup_sequence",
                "visual_layers": [],
            },
        )
        session.commit()

    monkeypatch.setattr(
        visual_treatments,
        "analyze_visual_treatments",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(AssertionError("should use fallback without timing")),
    )

    def fake_generate_popup_sequence_cutouts(**kwargs):
        assert kwargs["scene_id"] == "coffee-brain-scene-1"
        assert kwargs["script_id"] == script_id
        assert [layer["id"] for layer in kwargs["layers"]] == [
            "coffee-brain-scene-1_popup_1",
            "coffee-brain-scene-1_popup_2",
            "coffee-brain-scene-1_popup_3",
        ]
        return [
            {"id": "coffee-brain-scene-1_anchor", "type": "image", "asset_kind": "cutout", "image_url": "/static/projects/test/layers/anchor.png"},
            {**kwargs["layers"][0], "asset_kind": "cutout", "image_url": "/static/projects/test/layers/popup-1.png"},
            {**kwargs["layers"][1], "asset_kind": "cutout", "image_url": "/static/projects/test/layers/popup-2.png"},
            {**kwargs["layers"][2], "asset_kind": "cutout", "image_url": "/static/projects/test/layers/popup-3.png"},
        ]

    monkeypatch.setattr(image_gen, "generate_popup_sequence_cutouts", fake_generate_popup_sequence_cutouts)

    manifest = test_lab.TestLabRunManifest(
        run_id="run-treatment-no-audio",
        script_id=script_id,
        preset_id="coffee-brain",
        status="running",
    )
    ctx = test_lab.TestLabRunContext(
        engine=engine,
        run_id="run-treatment-no-audio",
        script_id=script_id,
        preset_id="coffee-brain",
        settings={"visual_treatment": "popup_sequence", "visual_layers": []},
        manifest=manifest,
        job_id=None,
    )

    test_lab._stage_treatment_assets(ctx)

    with Session(engine) as session:
        record, content = test_lab._load_content_for_script(session, script_id)
        _ = record
        saved = ScriptContent.model_validate(content)

    scene = saved.segments[0].scenes[0]
    assert scene.visual_treatment == "popup_sequence"
    assert [layer.image_url for layer in scene.visual_layers] == [
        "/static/projects/test/layers/anchor.png",
        "/static/projects/test/layers/popup-1.png",
        "/static/projects/test/layers/popup-2.png",
        "/static/projects/test/layers/popup-3.png",
    ]
    assert [asset.kind for asset in manifest.assets] == [
        "treatment_asset",
        "treatment_asset",
        "treatment_asset",
        "treatment_asset",
    ]


def test_stage_render_wires_cancel_check_and_progress(monkeypatch, tmp_path):
    engine, _app = _setup_app(monkeypatch, tmp_path)

    import pipeline.remotion_render as remotion_render
    import pipeline.test_lab as test_lab
    from pipeline.render_jobs import create_job, get_job

    with Session(engine) as session:
        script_id = test_lab.create_hidden_test_script(
            session,
            run_id="run-render-hooks",
            preset_id="coffee-brain",
            settings={},
        )
        session.commit()

    job = create_job(scene_count=1)
    manifest = test_lab.TestLabRunManifest(
        run_id="run-render-hooks",
        script_id=script_id,
        preset_id="coffee-brain",
        status="running",
    )
    ctx = test_lab.TestLabRunContext(
        engine=engine,
        run_id="run-render-hooks",
        script_id=script_id,
        preset_id="coffee-brain",
        settings={},
        manifest=manifest,
        job_id=job.id,
        progress_start=0.5,
        progress_end=0.75,
    )
    observed = {}

    def fake_render_full_video(**kwargs):
        observed["cancel_check"] = kwargs["cancel_check"]
        observed["on_progress"] = kwargs["on_progress"]
        kwargs["cancel_check"]()
        kwargs["on_progress"](0.4, "Rendering video with Remotion...")
        return "/static/projects/test-lab-run/renders/full_youtube.mp4"

    monkeypatch.setattr(remotion_render, "render_full_video", fake_render_full_video)

    test_lab._stage_render(ctx)

    updated_job = get_job(job.id)
    assert callable(observed["cancel_check"])
    assert callable(observed["on_progress"])
    assert updated_job is not None
    assert updated_job.progress == 0.6
    assert updated_job.current_step == "Rendering video with Remotion..."
    assert manifest.render_url == "/static/projects/test-lab-run/renders/full_youtube.mp4"


def test_stage_visual_skips_scene_image_for_layered_animation_treatment(monkeypatch, tmp_path):
    engine, _app = _setup_app(monkeypatch, tmp_path)

    import pipeline.image_gen as image_gen
    import pipeline.test_lab as test_lab
    from models.script import ScriptContent

    with Session(engine) as session:
        script_id = test_lab.create_hidden_test_script(
            session,
            run_id="run-popup-no-scene-image",
            preset_id="coffee-brain",
            settings={
                "visual_treatment": "flipflop",
            },
        )
        session.commit()

    monkeypatch.setattr(
        image_gen,
        "generate_scene_image",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(AssertionError("layered animation treatment should not generate scene image")),
    )

    manifest = test_lab.TestLabRunManifest(
        run_id="run-popup-no-scene-image",
        script_id=script_id,
        preset_id="coffee-brain",
        status="running",
    )
    ctx = test_lab.TestLabRunContext(
        engine=engine,
        run_id="run-popup-no-scene-image",
        script_id=script_id,
        preset_id="coffee-brain",
        settings={"visual_treatment": "flipflop"},
        manifest=manifest,
        job_id=None,
    )

    test_lab._stage_visual(ctx)

    with Session(engine) as session:
        record, content = test_lab._load_content_for_script(session, script_id)
        _ = record
        saved = ScriptContent.model_validate(content)

    scene = saved.segments[0].scenes[0]
    assert scene.image_url == ""
    assert [asset.kind for asset in manifest.assets] == []


def test_stage_visual_generates_frame_urls_for_multi_frame_mode(monkeypatch, tmp_path):
    engine, _app = _setup_app(monkeypatch, tmp_path)

    import pipeline.image_gen as image_gen
    import pipeline.test_lab as test_lab
    from models.script import ScriptContent

    with Session(engine) as session:
        script_id = test_lab.create_hidden_test_script(
            session,
            run_id="run-multi-frame-visual",
            preset_id="coffee-brain",
            settings={
                "visual_mode": "multi_frame",
            },
        )
        session.commit()

    observed = {}

    monkeypatch.setattr(
        image_gen,
        "generate_scene_image",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(AssertionError("multi_frame should generate frames")),
    )

    def fake_generate_scene_frames_v2(**kwargs):
        observed["frame_directives"] = kwargs["frame_directives"]
        return [
            ("/static/projects/test/images/frame-0.png", "prompt 0", {"source_type": "ai_generated"}),
            ("/static/projects/test/images/frame-1.png", "prompt 1", {"source_type": "ai_generated"}),
            ("/static/projects/test/images/frame-2.png", "prompt 2", {"source_type": "ai_generated"}),
        ]

    monkeypatch.setattr(image_gen, "generate_scene_frames_v2", fake_generate_scene_frames_v2)

    manifest = test_lab.TestLabRunManifest(
        run_id="run-multi-frame-visual",
        script_id=script_id,
        preset_id="coffee-brain",
        status="running",
    )
    ctx = test_lab.TestLabRunContext(
        engine=engine,
        run_id="run-multi-frame-visual",
        script_id=script_id,
        preset_id="coffee-brain",
        settings={"visual_mode": "multi_frame"},
        manifest=manifest,
        job_id=None,
    )

    test_lab._stage_visual(ctx)

    with Session(engine) as session:
        record, content = test_lab._load_content_for_script(session, script_id)
        _ = record
        saved = ScriptContent.model_validate(content)

    scene = saved.segments[0].scenes[0]
    assert scene.image_url == "/static/projects/test/images/frame-0.png"
    assert scene.frame_urls == [
        "/static/projects/test/images/frame-0.png",
        "/static/projects/test/images/frame-1.png",
        "/static/projects/test/images/frame-2.png",
    ]
    assert [directive["reference_previous"] for directive in observed["frame_directives"]] == [False, False, False]
    assert [asset.kind for asset in manifest.assets] == ["image", "image", "image"]


def test_stage_visual_uses_shared_scene_visual_generator(monkeypatch, tmp_path):
    engine, _app = _setup_app(monkeypatch, tmp_path)

    import pipeline.image_gen as image_gen
    import pipeline.test_lab as test_lab
    from models.script import ScriptContent

    with Session(engine) as session:
        script_id = test_lab.create_hidden_test_script(
            session,
            run_id="run-shared-visual-wrapper",
            preset_id="coffee-brain",
            settings={"visual_mode": "full_frame"},
        )
        session.commit()

    observed = {}

    def fake_generate_scene_visual(scene, script_id, **_kwargs):
        observed["scene"] = scene
        observed["script_id"] = script_id
        return {
            "scene_id": scene["scene_id"],
            "image_url": "/static/projects/test/images/shared.png",
            "frame_urls": [],
            "video_url": "",
            "prompt_used": "prompt",
            "visual_source_metadata": {"source_type": "ai_generated"},
            "error": None,
        }

    monkeypatch.setattr(image_gen, "generate_scene_visual", fake_generate_scene_visual)

    manifest = test_lab.TestLabRunManifest(
        run_id="run-shared-visual-wrapper",
        script_id=script_id,
        preset_id="coffee-brain",
        status="running",
    )
    ctx = test_lab.TestLabRunContext(
        engine=engine,
        run_id="run-shared-visual-wrapper",
        script_id=script_id,
        preset_id="coffee-brain",
        settings={"visual_mode": "full_frame"},
        manifest=manifest,
        job_id=None,
    )

    test_lab._stage_visual(ctx)

    with Session(engine) as session:
        _record, content = test_lab._load_content_for_script(session, script_id)
        saved = ScriptContent.model_validate(content)

    scene = saved.segments[0].scenes[0]
    assert observed["script_id"] == script_id
    assert observed["scene"]["visual_mode"] == "full_frame"
    assert scene.image_url == "/static/projects/test/images/shared.png"
    assert scene.frame_urls == []
    assert scene.visual_source_metadata == {"source_type": "ai_generated"}
    assert [asset.url for asset in manifest.assets] == ["/static/projects/test/images/shared.png"]


def test_test_lab_multi_frame_fallback_prompts_avoid_decorative_frame_language():
    from models.script import Scene
    from pipeline.test_lab import _frame_directives_for_visual_mode

    scene = Scene(
        id="scene-1",
        narration="A sequence escalates.",
        visual_prompt="Flat 2D cartoon city street cracking apart.",
        visual_mode="multi_frame",
    )

    directives = _frame_directives_for_visual_mode(scene)

    assert len(directives) == 3
    for directive in directives:
        prompt = directive["prompt"].lower()
        assert "independent frame" not in prompt
        assert "decorative frame" not in prompt
        assert "picture frame" not in prompt


def test_test_lab_flipflop_fallback_prompts_avoid_decorative_frame_language():
    from models.script import Scene
    from pipeline.test_lab import _fallback_visual_layers_for_treatment

    scene = Scene(
        id="scene-1",
        narration="A face flips from calm to panic.",
        visual_prompt="Flat 2D cartoon person at a control panel.",
        visual_mode="flipflop",
    )

    layers = _fallback_visual_layers_for_treatment(scene)

    assert len(layers) == 2
    assert [layer.asset_kind for layer in layers] == ["cutout", "cutout"]
    assert [layer.enter_at_seconds for layer in layers] == [0.0, 0.0]
    assert scene.renderer_context == "plain"
    for layer in layers:
        prompt = layer.prompt.lower()
        assert layer.asset_kind == "cutout"
        assert layer.animation == "none"
        assert "flip-flop transparent cutout" in prompt
        assert "solid chroma" in prompt
        assert "no full background scene" in prompt
        assert "full-bleed" not in prompt
        assert "framed panel" not in prompt


def test_stage_visual_generates_referenced_frame_urls_for_continuous_mode(monkeypatch, tmp_path):
    engine, _app = _setup_app(monkeypatch, tmp_path)

    import pipeline.image_gen as image_gen
    import pipeline.test_lab as test_lab
    from models.script import ScriptContent

    with Session(engine) as session:
        script_id = test_lab.create_hidden_test_script(
            session,
            run_id="run-continuous-visual",
            preset_id="coffee-brain",
            settings={
                "visual_mode": "continuous",
            },
        )
        session.commit()

    observed = {}

    monkeypatch.setattr(
        image_gen,
        "generate_scene_image",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(AssertionError("continuous should generate frames")),
    )

    def fake_generate_scene_frames_v2(**kwargs):
        observed["frame_directives"] = kwargs["frame_directives"]
        return [
            ("/static/projects/test/images/continuous-0.png", "prompt 0", {"source_type": "ai_generated"}),
            ("/static/projects/test/images/continuous-1.png", "prompt 1", {"source_type": "ai_generated"}),
            ("/static/projects/test/images/continuous-2.png", "prompt 2", {"source_type": "ai_generated"}),
        ]

    monkeypatch.setattr(image_gen, "generate_scene_frames_v2", fake_generate_scene_frames_v2)

    manifest = test_lab.TestLabRunManifest(
        run_id="run-continuous-visual",
        script_id=script_id,
        preset_id="coffee-brain",
        status="running",
    )
    ctx = test_lab.TestLabRunContext(
        engine=engine,
        run_id="run-continuous-visual",
        script_id=script_id,
        preset_id="coffee-brain",
        settings={"visual_mode": "continuous"},
        manifest=manifest,
        job_id=None,
    )

    test_lab._stage_visual(ctx)

    with Session(engine) as session:
        record, content = test_lab._load_content_for_script(session, script_id)
        _ = record
        saved = ScriptContent.model_validate(content)

    scene = saved.segments[0].scenes[0]
    assert scene.image_url == "/static/projects/test/images/continuous-0.png"
    assert scene.frame_urls == [
        "/static/projects/test/images/continuous-0.png",
        "/static/projects/test/images/continuous-1.png",
        "/static/projects/test/images/continuous-2.png",
    ]
    assert [directive["reference_previous"] for directive in observed["frame_directives"]] == [False, True, True]
    assert [asset.kind for asset in manifest.assets] == ["image", "image", "image"]


def test_stage_visual_preserves_subtitle_frame_placeholders(monkeypatch, tmp_path):
    engine, _app = _setup_app(monkeypatch, tmp_path)

    import pipeline.image_gen as image_gen
    import pipeline.test_lab as test_lab
    from models.script import ScriptContent

    with Session(engine) as session:
        script_id = test_lab.create_hidden_test_script(
            session,
            run_id="run-subtitle-frame-placeholder",
            preset_id="coffee-brain",
            settings={
                "visual_mode": "multi_frame",
                "advanced_script": {
                    "segments": [
                        {
                            "name": "Segment",
                            "scenes": [
                                {
                                    "id": "coffee-brain-scene-1",
                                    "narration": "First this, then a label, then that.",
                                    "visual_prompt": "A simple progression.",
                                    "visual_mode": "multi_frame",
                                    "frame_directives": [
                                        {
                                            "prompt": "First image.",
                                            "source": "ai_generated",
                                            "transition": "cut",
                                            "reference_previous": False,
                                        },
                                        {
                                            "prompt": "ON SCREEN LABEL",
                                            "source": "subtitle",
                                            "transition": "cut",
                                            "reference_previous": False,
                                        },
                                        {
                                            "prompt": "Third image.",
                                            "source": "ai_generated",
                                            "transition": "cut",
                                            "reference_previous": False,
                                        },
                                    ],
                                }
                            ],
                        }
                    ]
                },
            },
        )
        session.commit()

    monkeypatch.setattr(
        image_gen,
        "generate_scene_image",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(AssertionError("multi_frame should generate frames")),
    )
    monkeypatch.setattr(
        image_gen,
        "generate_scene_frames_v2",
        lambda **_kwargs: [
            ("/static/projects/test/images/frame-0.png", "prompt 0", {"source_type": "ai_generated"}),
            ("", "ON SCREEN LABEL", None),
            ("/static/projects/test/images/frame-2.png", "prompt 2", {"source_type": "ai_generated"}),
        ],
    )

    manifest = test_lab.TestLabRunManifest(
        run_id="run-subtitle-frame-placeholder",
        script_id=script_id,
        preset_id="coffee-brain",
        status="running",
    )
    ctx = test_lab.TestLabRunContext(
        engine=engine,
        run_id="run-subtitle-frame-placeholder",
        script_id=script_id,
        preset_id="coffee-brain",
        settings={"visual_mode": "multi_frame"},
        manifest=manifest,
        job_id=None,
    )

    test_lab._stage_visual(ctx)

    with Session(engine) as session:
        record, content = test_lab._load_content_for_script(session, script_id)
        _ = record
        saved = ScriptContent.model_validate(content)

    scene = saved.segments[0].scenes[0]
    assert scene.image_url == "/static/projects/test/images/frame-0.png"
    assert scene.frame_urls == [
        "/static/projects/test/images/frame-0.png",
        "",
        "/static/projects/test/images/frame-2.png",
    ]
    assert [asset.url for asset in manifest.assets] == [
        "/static/projects/test/images/frame-0.png",
        "/static/projects/test/images/frame-2.png",
    ]


def test_run_test_lab_persists_failed_manifest_when_setup_fails(monkeypatch, tmp_path):
    import pytest

    engine, _app = _setup_app(monkeypatch, tmp_path)

    import pipeline.test_lab as test_lab

    with pytest.raises(ValueError):
        test_lab.run_test_lab(
            engine=engine,
            run_id="run-bad-preset",
            preset_id="missing-preset",
            settings={},
            job_id=None,
        )

    manifest = test_lab.load_run_manifest("run-bad-preset")
    assert manifest.status == "failed"
    assert manifest.logs[-1].level == "error"
    assert "Unknown Test Lab preset" in manifest.logs[-1].message


def test_run_test_lab_preserves_cancelled_job_status(monkeypatch, tmp_path):
    import pytest

    engine, _app = _setup_app(monkeypatch, tmp_path)

    import pipeline.test_lab as test_lab
    from pipeline.render_jobs import cancel_job, create_job, get_job

    job = create_job(scene_count=1)

    def fake_audio(ctx):
        cancel_job(ctx.job_id)
        test_lab._check_cancelled(ctx)

    monkeypatch.setattr(test_lab, "_stage_audio", fake_audio)

    with pytest.raises(RuntimeError, match="cancelled"):
        test_lab.run_test_lab(
            engine=engine,
            run_id="run-cancelled",
            preset_id="coffee-brain",
            settings={
                "stages": {
                    "audio": True,
                    "visual": False,
                    "treatment_assets": False,
                    "fx": False,
                    "eli": False,
                    "render": False,
                },
            },
            job_id=job.id,
        )

    updated_job = get_job(job.id)
    manifest = test_lab.load_run_manifest("run-cancelled")
    assert updated_job is not None
    assert updated_job.status == "cancelled"
    assert manifest.status == "cancelled"
    assert "cancelled" in manifest.logs[-1].message


def test_test_lab_preset_accepts_stat_card_visual_mode():
    from pipeline.test_lab import TestLabPreset

    preset = TestLabPreset(
        id="stat-card-test",
        title="Stat Card Test",
        description="Stat card test",
        segment_name="The number",
        narration="Eighty-five percent of new users churn in week one.",
        visual_prompt="",
        visual_mode="stat_card",
        stat_value="85%",
        stat_label="of new users churn in week 1",
        duration_estimate_seconds=4.0,
    )

    assert preset.visual_mode == "stat_card"
    assert preset.media_source == "ai"
    assert preset.stat_value == "85%"
    assert preset.stat_label == "of new users churn in week 1"


def test_test_lab_stat_card_no_icon_round_trip_through_builder():
    from pipeline.test_lab import build_content_from_preset

    content = build_content_from_preset("stat-card-no-icon", {})
    scene = content.segments[0].scenes[0]

    assert scene.visual_mode == "stat_card"
    assert scene.stat_value == "85%"
    assert scene.stat_label == "of new users churn in week 1"
    assert scene.visual_layers == []
    assert scene.image_url == ""
    assert scene.frame_urls == []


def test_test_lab_stat_card_with_icon_synthesizes_visual_layer():
    from pipeline.test_lab import build_content_from_preset

    content = build_content_from_preset("stat-card-with-icon", {})
    scene = content.segments[0].scenes[0]

    assert scene.visual_mode == "stat_card"
    assert scene.stat_value == "$2M"
    assert scene.stat_label == "lost to fraud every hour"
    assert len(scene.visual_layers) == 1
    layer = scene.visual_layers[0]
    assert layer.asset_kind == "cutout"
    assert layer.prompt
