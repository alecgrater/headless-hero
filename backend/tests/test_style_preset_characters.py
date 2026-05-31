"""Tests for style-preset-scoped main characters."""

from datetime import datetime, timezone
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient
from PIL import Image, ImageDraw
from sqlalchemy.pool import StaticPool
from sqlmodel import SQLModel, Session, create_engine


@pytest.fixture
def style_character_engine():
    from models.project_config import ProjectConfig  # noqa: F401
    from models.script import Script  # noqa: F401
    from models.settings import AppSetting  # noqa: F401
    from models.style_preset import StylePreset  # noqa: F401
    from models.style_preset_character import StylePresetCharacter  # noqa: F401

    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    SQLModel.metadata.create_all(engine)
    return engine


@pytest.fixture
def client(style_character_engine):
    from api import app
    from api import style as style_api

    def override_get_session():
        with Session(style_character_engine) as session:
            yield session

    app.dependency_overrides[style_api.get_session] = override_get_session
    try:
        yield TestClient(app)
    finally:
        app.dependency_overrides.pop(style_api.get_session, None)


def _insert_preset(engine, tmp_path, preset_id: str, name: str):
    from models.style_preset import StylePreset

    preset_dir = tmp_path / "style" / "presets"
    preset_dir.mkdir(parents=True, exist_ok=True)
    (preset_dir / f"{preset_id}.png").write_bytes(f"preset:{preset_id}".encode())
    with Session(engine) as session:
        session.add(
            StylePreset(
                id=preset_id,
                name=name,
                prompt=f"{name} prompt",
                created_at=datetime.now(timezone.utc),
            )
        )
        session.commit()


def _write_chroma_character(path):
    path.parent.mkdir(parents=True, exist_ok=True)
    image = Image.new("RGB", (160, 120), (0, 255, 0))
    draw = ImageDraw.Draw(image)
    draw.rectangle((62, 30, 98, 92), fill=(255, 0, 0))
    image.save(path)


def _write_character_with_enclosed_background_detail(path):
    path.parent.mkdir(parents=True, exist_ok=True)
    background = (238, 236, 232)
    image = Image.new("RGB", (160, 160), background)
    pixels = image.load()
    for y in range(40, 121):
        for x in range(40, 121):
            pixels[x, y] = (12, 12, 12) if x in (40, 120) or y in (40, 120) else (245, 181, 132)
    pixels[80, 80] = background
    image.save(path)


def _write_corrupted_cutout_with_transparent_detail(path):
    path.parent.mkdir(parents=True, exist_ok=True)
    image = Image.new("RGBA", (120, 120), (245, 181, 132, 255))
    image.putpixel((60, 60), (238, 236, 232, 0))
    image.save(path)


def test_create_character_scopes_it_to_the_requested_preset(
    client,
    style_character_engine,
    tmp_path,
    monkeypatch,
):
    from api import style as style_api
    from pipeline import main_character

    monkeypatch.setattr(style_api, "DATA_DIR", tmp_path)
    monkeypatch.setattr(main_character, "DATA_DIR", tmp_path)
    _insert_preset(style_character_engine, tmp_path, "preset-a", "Preset A")
    _insert_preset(style_character_engine, tmp_path, "preset-b", "Preset B")

    calls: list[dict[str, object]] = []

    def fake_generate(prompt, script_id, style_reference_path):
        from PIL import Image, ImageDraw

        fake_tmp = tmp_path / "generated-character.png"
        image = Image.new("RGB", (200, 200), (0, 255, 0))
        draw = ImageDraw.Draw(image)
        draw.rectangle((70, 50, 130, 160), fill=(255, 0, 0))
        image.save(fake_tmp)
        calls.append(
            {
                "prompt": prompt,
                "script_id": script_id,
                "style_reference_path": style_reference_path,
            }
        )
        return str(fake_tmp)

    with patch.object(
        main_character,
        "_call_style_character_image_generator",
        side_effect=fake_generate,
    ):
        response = client.post(
            "/api/style/presets/preset-a/characters",
            json={
                "name": "Mara",
                "appearance": "short black hair, teal jacket",
                "vibe": "calm and sharp",
            },
        )

    assert response.status_code == 200
    created = response.json()
    assert created["style_preset_id"] == "preset-a"
    assert created["name"] == "Mara"
    assert created["active"] is True
    assert created["reference_image_url"].endswith(f"/characters/{created['id']}.png")
    assert created["cutout_image_url"].endswith(f"/characters/{created['id']}.cutout.png")
    assert calls[0]["style_reference_path"] == str(
        tmp_path / "style" / "presets" / "preset-a.png"
    )
    assert (tmp_path / "style" / "presets" / "preset-a" / "characters" / f"{created['id']}.png").exists()
    assert (tmp_path / "style" / "presets" / "preset-a" / "characters" / f"{created['id']}.cutout.png").exists()
    assert not (tmp_path / "generated-character.png").exists()

    preset_a = client.get("/api/style/presets/preset-a/characters")
    preset_b = client.get("/api/style/presets/preset-b/characters")

    assert [item["id"] for item in preset_a.json()] == [created["id"]]
    assert preset_b.json() == []


def test_create_character_cleans_up_assets_when_cutout_processing_fails(
    style_character_engine,
    tmp_path,
    monkeypatch,
):
    from models.script import MainCharacter
    from pipeline import main_character

    monkeypatch.setattr(main_character, "DATA_DIR", tmp_path)
    monkeypatch.setattr(main_character.uuid, "uuid4", lambda: type("FixedUuid", (), {"hex": "char-fail"})())
    _insert_preset(style_character_engine, tmp_path, "preset-a", "Preset A")

    source_path = tmp_path / "generated-character.png"
    source_path.write_bytes(b"generated")
    final_path = tmp_path / "style" / "presets" / "preset-a" / "characters" / "char-fail.png"
    final_cutout_path = tmp_path / "style" / "presets" / "preset-a" / "characters" / "char-fail.cutout.png"
    metadata_path = tmp_path / "style" / "presets" / "preset-a" / "characters" / "char-fail.metadata.json"

    def fake_process_character_asset_bundle(**kwargs):
        final_path.parent.mkdir(parents=True, exist_ok=True)
        final_path.write_bytes(b"partial-reference")
        final_cutout_path.write_bytes(b"partial-cutout")
        metadata_path.write_text("{}", encoding="utf-8")
        raise RuntimeError("cutout failed")

    monkeypatch.setattr(
        main_character,
        "_call_style_character_image_generator",
        lambda prompt, script_id, style_reference_path: str(source_path),
    )
    monkeypatch.setattr(
        main_character,
        "process_character_asset_bundle",
        fake_process_character_asset_bundle,
    )

    with Session(style_character_engine) as session:
        with pytest.raises(RuntimeError, match="cutout failed"):
            main_character.create_style_preset_character(
                session,
                preset_id="preset-a",
                character=MainCharacter(name="Mara", appearance="teal jacket", vibe="calm"),
            )

    assert not source_path.exists()
    assert not final_path.exists()
    assert not final_cutout_path.exists()
    assert not metadata_path.exists()


def test_selecting_character_under_wrong_preset_fails(
    client,
    style_character_engine,
    tmp_path,
    monkeypatch,
):
    from api import style as style_api
    from models.style_preset_character import StylePresetCharacter
    from pipeline import main_character

    monkeypatch.setattr(style_api, "DATA_DIR", tmp_path)
    monkeypatch.setattr(main_character, "DATA_DIR", tmp_path)
    _insert_preset(style_character_engine, tmp_path, "preset-a", "Preset A")
    _insert_preset(style_character_engine, tmp_path, "preset-b", "Preset B")

    character_id = "char-a"
    character_path = tmp_path / "style" / "presets" / "preset-a" / "characters" / f"{character_id}.png"
    character_path.parent.mkdir(parents=True, exist_ok=True)
    character_path.write_bytes(b"char")
    with Session(style_character_engine) as session:
        session.add(
            StylePresetCharacter(
                id=character_id,
                style_preset_id="preset-a",
                name="Mara",
                appearance="short black hair",
                vibe="calm",
                reference_image_url=f"/static/style/presets/preset-a/characters/{character_id}.png",
                created_at=datetime.now(timezone.utc),
            )
        )
        session.commit()

    response = client.post(
        f"/api/style/presets/preset-b/characters/{character_id}/select"
    )

    assert response.status_code == 404


def test_create_character_rejects_missing_preset_image(
    client,
    style_character_engine,
    tmp_path,
    monkeypatch,
):
    from api import style as style_api
    from models.style_preset import StylePreset
    from pipeline import main_character

    monkeypatch.setattr(style_api, "DATA_DIR", tmp_path)
    monkeypatch.setattr(main_character, "DATA_DIR", tmp_path)
    with Session(style_character_engine) as session:
        session.add(
            StylePreset(
                id="fileless",
                name="Fileless",
                prompt="missing image",
                created_at=datetime.now(timezone.utc),
            )
        )
        session.commit()

    response = client.post(
        "/api/style/presets/fileless/characters",
        json={
            "name": "Mara",
            "appearance": "short black hair",
            "vibe": "calm",
        },
    )

    assert response.status_code == 404


def test_sync_active_preset_character_to_project(
    style_character_engine,
    tmp_path,
    monkeypatch,
):
    from models.project_config import ProjectConfig
    from models.script import Script, ScriptContent
    from models.settings import AppSetting
    from models.style_preset_character import StylePresetCharacter
    from pipeline import main_character

    monkeypatch.setattr(main_character, "DATA_DIR", tmp_path)
    _insert_preset(style_character_engine, tmp_path, "preset-a", "Preset A")

    character_id = "char-a"
    source_ref = tmp_path / "style" / "presets" / "preset-a" / "characters" / f"{character_id}.png"
    source_cutout = tmp_path / "style" / "presets" / "preset-a" / "characters" / f"{character_id}.cutout.png"
    _write_chroma_character(source_ref)

    with Session(style_character_engine) as session:
        session.add(
            StylePresetCharacter(
                id=character_id,
                style_preset_id="preset-a",
                name="Mara",
                appearance="short black hair",
                vibe="calm",
                reference_image_url=f"/static/style/presets/preset-a/characters/{character_id}.png",
                cutout_image_url=f"/static/style/presets/preset-a/characters/{character_id}.cutout.png",
                created_at=datetime.now(timezone.utc),
            )
        )
        session.add(AppSetting(key="ACTIVE_STYLE_PRESET_ID", value="preset-a"))
        session.add(
            AppSetting(
                key=main_character.active_style_preset_character_key("preset-a"),
                value=character_id,
            )
        )
        session.add(
            Script(
                id="script-a",
                brand_id="default",
                topic_title="Test",
                topic_description="",
                script_json=ScriptContent(title="Test", segments=[]).model_dump_json(),
            )
        )
        session.add(ProjectConfig(script_id="script-a", eli_enabled=False))
        session.commit()

    with Session(style_character_engine) as session:
        changed = main_character.sync_global_main_character_to_project(session, "script-a")
        session.commit()

        assert changed is True
        cfg = session.get(ProjectConfig, "script-a")
        script = session.get(Script, "script-a")

    project_ref = tmp_path / "projects" / "script-a" / "character" / "reference.png"
    project_cutout = tmp_path / "projects" / "script-a" / "character" / "cutout.png"
    assert project_ref.read_bytes() == source_ref.read_bytes()
    assert source_cutout.exists()
    assert project_cutout.exists()
    assert cfg.main_character_reference_url == "/static/projects/script-a/character/reference.png"
    content = ScriptContent.model_validate_json(script.script_json)
    assert content.main_character is not None
    assert content.main_character.name == "Mara"


def test_sync_active_preset_character_repairs_missing_project_cutout(
    style_character_engine,
    tmp_path,
    monkeypatch,
):
    from models.project_config import ProjectConfig
    from models.script import Script, ScriptContent
    from models.settings import AppSetting
    from models.style_preset_character import StylePresetCharacter
    from pipeline import main_character

    monkeypatch.setattr(main_character, "DATA_DIR", tmp_path)
    _insert_preset(style_character_engine, tmp_path, "preset-a", "Preset A")

    character_id = "char-a"
    source_ref = tmp_path / "style" / "presets" / "preset-a" / "characters" / f"{character_id}.png"
    _write_chroma_character(source_ref)

    with Session(style_character_engine) as session:
        session.add(
            StylePresetCharacter(
                id=character_id,
                style_preset_id="preset-a",
                name="Mara",
                appearance="short black hair",
                vibe="calm",
                reference_image_url=f"/static/style/presets/preset-a/characters/{character_id}.png",
                cutout_image_url="",
                created_at=datetime.now(timezone.utc),
            )
        )
        session.add(AppSetting(key="ACTIVE_STYLE_PRESET_ID", value="preset-a"))
        session.add(
            AppSetting(
                key=main_character.active_style_preset_character_key("preset-a"),
                value=character_id,
            )
        )
        session.add(
            Script(
                id="script-a",
                brand_id="default",
                topic_title="Test",
                topic_description="",
                script_json=ScriptContent(title="Test", segments=[]).model_dump_json(),
            )
        )
        session.add(ProjectConfig(script_id="script-a", eli_enabled=False))
        session.commit()

    with Session(style_character_engine) as session:
        changed = main_character.sync_global_main_character_to_project(session, "script-a")
        session.commit()

    project_cutout = tmp_path / "projects" / "script-a" / "character" / "cutout.png"
    assert changed is True
    assert project_cutout.exists()
    with Image.open(project_cutout) as image:
        assert image.mode == "RGBA"
        assert image.width < 120


def test_sync_active_preset_character_reprocesses_stale_cutouts(
    style_character_engine,
    tmp_path,
    monkeypatch,
):
    import json

    from models.project_config import ProjectConfig
    from models.script import Script, ScriptContent
    from models.settings import AppSetting
    from models.style_preset_character import StylePresetCharacter
    from pipeline import main_character
    from pipeline.character_assets import PROCESSOR_VERSION

    monkeypatch.setattr(main_character, "DATA_DIR", tmp_path)
    _insert_preset(style_character_engine, tmp_path, "preset-a", "Preset A")

    character_id = "char-a"
    source_ref = tmp_path / "style" / "presets" / "preset-a" / "characters" / f"{character_id}.png"
    source_cutout = tmp_path / "style" / "presets" / "preset-a" / "characters" / f"{character_id}.cutout.png"
    source_metadata = tmp_path / "style" / "presets" / "preset-a" / "characters" / f"{character_id}.metadata.json"
    _write_character_with_enclosed_background_detail(source_ref)
    _write_corrupted_cutout_with_transparent_detail(source_cutout)
    source_metadata.write_text(json.dumps({"version": 1}), encoding="utf-8")

    with Session(style_character_engine) as session:
        session.add(
            StylePresetCharacter(
                id=character_id,
                style_preset_id="preset-a",
                name="Mara",
                appearance="short black hair",
                vibe="calm",
                reference_image_url=f"/static/style/presets/preset-a/characters/{character_id}.png",
                cutout_image_url=f"/static/style/presets/preset-a/characters/{character_id}.cutout.png",
                created_at=datetime.now(timezone.utc),
            )
        )
        session.add(AppSetting(key="ACTIVE_STYLE_PRESET_ID", value="preset-a"))
        session.add(
            AppSetting(
                key=main_character.active_style_preset_character_key("preset-a"),
                value=character_id,
            )
        )
        session.add(
            Script(
                id="script-a",
                brand_id="default",
                topic_title="Test",
                topic_description="",
                script_json=ScriptContent(title="Test", segments=[]).model_dump_json(),
            )
        )
        session.add(ProjectConfig(script_id="script-a", eli_enabled=False))
        session.commit()

    with Session(style_character_engine) as session:
        changed = main_character.sync_global_main_character_to_project(session, "script-a")
        session.commit()

    project_cutout = tmp_path / "projects" / "script-a" / "character" / "cutout.png"
    project_metadata = tmp_path / "projects" / "script-a" / "character" / "metadata.json"
    assert changed is True
    assert json.loads(source_metadata.read_text(encoding="utf-8"))["version"] == PROCESSOR_VERSION
    assert json.loads(project_metadata.read_text(encoding="utf-8"))["version"] == PROCESSOR_VERSION
    with Image.open(source_cutout) as image:
        assert image.getpixel((80 - 16, 80 - 16))[3] == 255
    with Image.open(project_cutout) as image:
        assert image.getpixel((80 - 16, 80 - 16))[3] == 255


def test_list_characters_repairs_stale_cutout_preview(
    client,
    style_character_engine,
    tmp_path,
    monkeypatch,
):
    import json

    from api import style as style_api
    from models.style_preset_character import StylePresetCharacter
    from pipeline import main_character
    from pipeline.character_assets import PROCESSOR_VERSION

    monkeypatch.setattr(style_api, "DATA_DIR", tmp_path)
    monkeypatch.setattr(main_character, "DATA_DIR", tmp_path)
    _insert_preset(style_character_engine, tmp_path, "preset-a", "Preset A")

    character_id = "char-a"
    source_ref = tmp_path / "style" / "presets" / "preset-a" / "characters" / f"{character_id}.png"
    source_cutout = tmp_path / "style" / "presets" / "preset-a" / "characters" / f"{character_id}.cutout.png"
    source_metadata = tmp_path / "style" / "presets" / "preset-a" / "characters" / f"{character_id}.metadata.json"
    _write_character_with_enclosed_background_detail(source_ref)
    _write_corrupted_cutout_with_transparent_detail(source_cutout)
    source_metadata.write_text(json.dumps({"version": 1}), encoding="utf-8")

    with Session(style_character_engine) as session:
        session.add(
            StylePresetCharacter(
                id=character_id,
                style_preset_id="preset-a",
                name="Mara",
                appearance="short black hair",
                vibe="calm",
                reference_image_url=f"/static/style/presets/preset-a/characters/{character_id}.png",
                cutout_image_url=f"/static/style/presets/preset-a/characters/{character_id}.cutout.png",
                created_at=datetime.now(timezone.utc),
            )
        )
        session.commit()

    response = client.get("/api/style/presets/preset-a/characters")

    assert response.status_code == 200
    assert response.json()[0]["cutout_image_url"].endswith(f"/characters/{character_id}.cutout.png")
    assert json.loads(source_metadata.read_text(encoding="utf-8"))["version"] == PROCESSOR_VERSION
    with Image.open(source_cutout) as image:
        assert image.getpixel((80 - 16, 80 - 16))[3] == 255


def test_sync_active_preset_character_change_clears_project_variants(
    style_character_engine,
    tmp_path,
    monkeypatch,
):
    from models.project_config import ProjectConfig
    from models.script import MainCharacter, Script, ScriptContent
    from models.settings import AppSetting
    from models.style_preset_character import StylePresetCharacter
    from pipeline import main_character

    monkeypatch.setattr(main_character, "DATA_DIR", tmp_path)
    _insert_preset(style_character_engine, tmp_path, "preset-a", "Preset A")

    character_id = "char-new"
    source_ref = tmp_path / "style" / "presets" / "preset-a" / "characters" / f"{character_id}.png"
    source_cutout = tmp_path / "style" / "presets" / "preset-a" / "characters" / f"{character_id}.cutout.png"
    _write_chroma_character(source_ref)

    project_character_dir = tmp_path / "projects" / "script-a" / "character"
    project_variants_dir = project_character_dir / "references"
    project_variants_dir.mkdir(parents=True, exist_ok=True)
    (project_variants_dir / "1.png").write_bytes(b"old-project-variant")
    (project_variants_dir / "1.cutout.png").write_bytes(b"old-project-variant-cutout")
    (project_variants_dir / "1.metadata.json").write_text("{}", encoding="utf-8")
    (project_character_dir / "active_reference.txt").write_text("1", encoding="utf-8")
    (project_character_dir / "metadata.json").write_text("{}", encoding="utf-8")

    old_character = MainCharacter(name="Old", appearance="old look", vibe="old vibe")
    with Session(style_character_engine) as session:
        session.add(
            StylePresetCharacter(
                id=character_id,
                style_preset_id="preset-a",
                name="Mara",
                appearance="short black hair",
                vibe="calm",
                reference_image_url=f"/static/style/presets/preset-a/characters/{character_id}.png",
                cutout_image_url=f"/static/style/presets/preset-a/characters/{character_id}.cutout.png",
                created_at=datetime.now(timezone.utc),
            )
        )
        session.add(AppSetting(key="ACTIVE_STYLE_PRESET_ID", value="preset-a"))
        session.add(
            AppSetting(
                key=main_character.active_style_preset_character_key("preset-a"),
                value=character_id,
            )
        )
        session.add(
            Script(
                id="script-a",
                brand_id="default",
                topic_title="Test",
                topic_description="",
                script_json=ScriptContent(
                    title="Test",
                    segments=[],
                    main_character=old_character,
                ).model_dump_json(),
            )
        )
        session.add(
            ProjectConfig(
                script_id="script-a",
                eli_enabled=False,
                main_character_reference_url="/static/projects/script-a/character/reference.png",
            )
        )
        session.commit()

    with Session(style_character_engine) as session:
        changed = main_character.sync_global_main_character_to_project(session, "script-a")
        session.commit()

    project_ref = project_character_dir / "reference.png"
    project_cutout = project_character_dir / "cutout.png"
    assert changed is True
    assert project_ref.read_bytes() == source_ref.read_bytes()
    assert project_cutout.exists()
    assert not project_variants_dir.exists()
    assert not (project_character_dir / "active_reference.txt").exists()
    assert (project_character_dir / "metadata.json").exists()
    assert source_ref.exists()
    assert source_cutout.exists()


def test_sync_active_preset_character_asset_change_clears_project_variants(
    style_character_engine,
    tmp_path,
    monkeypatch,
):
    from models.project_config import ProjectConfig
    from models.script import MainCharacter, Script, ScriptContent
    from models.settings import AppSetting
    from models.style_preset_character import StylePresetCharacter
    from pipeline import main_character

    monkeypatch.setattr(main_character, "DATA_DIR", tmp_path)
    _insert_preset(style_character_engine, tmp_path, "preset-a", "Preset A")

    character_details = {
        "name": "Mara",
        "appearance": "short black hair",
        "vibe": "calm",
    }
    old_character_id = "char-old"
    new_character_id = "char-new"
    old_ref = tmp_path / "style" / "presets" / "preset-a" / "characters" / f"{old_character_id}.png"
    old_cutout = tmp_path / "style" / "presets" / "preset-a" / "characters" / f"{old_character_id}.cutout.png"
    new_ref = tmp_path / "style" / "presets" / "preset-a" / "characters" / f"{new_character_id}.png"
    new_cutout = tmp_path / "style" / "presets" / "preset-a" / "characters" / f"{new_character_id}.cutout.png"
    _write_chroma_character(old_ref)
    _write_chroma_character(new_ref)

    project_character_dir = tmp_path / "projects" / "script-a" / "character"
    project_variants_dir = project_character_dir / "references"
    project_variants_dir.mkdir(parents=True, exist_ok=True)
    (project_character_dir / "reference.png").write_bytes(b"old-preset-reference")
    (project_character_dir / "cutout.png").write_bytes(b"old-preset-cutout")
    (project_variants_dir / "1.png").write_bytes(b"old-project-variant")
    (project_variants_dir / "1.cutout.png").write_bytes(b"old-project-variant-cutout")
    (project_character_dir / "active_reference.txt").write_text("1", encoding="utf-8")
    prompt_marker = tmp_path / "projects" / "script-a" / "images" / "foo.prompt"
    prompt_marker.parent.mkdir(parents=True, exist_ok=True)
    prompt_marker.write_text("old scene prompt", encoding="utf-8")

    with Session(style_character_engine) as session:
        session.add(
            StylePresetCharacter(
                id=old_character_id,
                style_preset_id="preset-a",
                reference_image_url=f"/static/style/presets/preset-a/characters/{old_character_id}.png",
                cutout_image_url=f"/static/style/presets/preset-a/characters/{old_character_id}.cutout.png",
                created_at=datetime.now(timezone.utc),
                **character_details,
            )
        )
        session.add(
            StylePresetCharacter(
                id=new_character_id,
                style_preset_id="preset-a",
                reference_image_url=f"/static/style/presets/preset-a/characters/{new_character_id}.png",
                cutout_image_url=f"/static/style/presets/preset-a/characters/{new_character_id}.cutout.png",
                created_at=datetime.now(timezone.utc),
                **character_details,
            )
        )
        session.add(AppSetting(key="ACTIVE_STYLE_PRESET_ID", value="preset-a"))
        session.add(
            AppSetting(
                key=main_character.active_style_preset_character_key("preset-a"),
                value=new_character_id,
            )
        )
        session.add(
            Script(
                id="script-a",
                brand_id="default",
                topic_title="Test",
                topic_description="",
                script_json=ScriptContent(
                    title="Test",
                    segments=[],
                    main_character=MainCharacter(**character_details),
                ).model_dump_json(),
            )
        )
        session.add(
            ProjectConfig(
                script_id="script-a",
                eli_enabled=False,
                main_character_reference_url="/static/projects/script-a/character/reference.png",
            )
        )
        session.commit()

    with Session(style_character_engine) as session:
        changed = main_character.sync_global_main_character_to_project(session, "script-a")
        session.commit()

    assert changed is True
    assert (project_character_dir / "reference.png").read_bytes() == new_ref.read_bytes()
    assert (project_character_dir / "cutout.png").exists()
    assert not project_variants_dir.exists()
    assert not (project_character_dir / "active_reference.txt").exists()
    assert not prompt_marker.exists()
    assert old_ref.exists()
    assert not old_cutout.exists()
    assert new_ref.exists()
    assert new_cutout.exists()


def test_sync_active_preset_character_to_project_skips_when_style_preset_disabled(
    style_character_engine,
    tmp_path,
    monkeypatch,
):
    from models.project_config import ProjectConfig
    from models.script import Script, ScriptContent
    from models.settings import AppSetting
    from models.style_preset_character import StylePresetCharacter
    from pipeline import main_character

    monkeypatch.setattr(main_character, "DATA_DIR", tmp_path)
    _insert_preset(style_character_engine, tmp_path, "preset-a", "Preset A")

    character_id = "char-a"
    source_ref = tmp_path / "style" / "presets" / "preset-a" / "characters" / f"{character_id}.png"
    source_ref.parent.mkdir(parents=True, exist_ok=True)
    source_ref.write_bytes(b"preset-character")

    with Session(style_character_engine) as session:
        session.add(
            StylePresetCharacter(
                id=character_id,
                style_preset_id="preset-a",
                name="Mara",
                appearance="short black hair",
                vibe="calm",
                reference_image_url=f"/static/style/presets/preset-a/characters/{character_id}.png",
                created_at=datetime.now(timezone.utc),
            )
        )
        session.add(AppSetting(key="ACTIVE_STYLE_PRESET_ID", value="preset-a"))
        session.add(
            AppSetting(
                key=main_character.active_style_preset_character_key("preset-a"),
                value=character_id,
            )
        )
        session.add(
            Script(
                id="script-disabled",
                brand_id="default",
                topic_title="Test",
                topic_description="",
                script_json=ScriptContent(title="Test", segments=[]).model_dump_json(),
            )
        )
        session.add(ProjectConfig(script_id="script-disabled", eli_enabled=False, style_preset_enabled=False))
        session.commit()

    with Session(style_character_engine) as session:
        changed = main_character.sync_global_main_character_to_project(session, "script-disabled")
        session.commit()

        cfg = session.get(ProjectConfig, "script-disabled")
        script = session.get(Script, "script-disabled")
        reason = main_character.missing_character_reference_reason(session, "script-disabled")

    project_ref = tmp_path / "projects" / "script-disabled" / "character" / "reference.png"
    content = ScriptContent.model_validate_json(script.script_json)
    assert changed is False
    assert not project_ref.exists()
    assert cfg.main_character_reference_url is None
    assert content.main_character is None
    assert reason == "Style preset is disabled. Enable the style preset before generating Eli-disabled scene images."
