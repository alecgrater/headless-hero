"""Tests for the /api/thumbnail/regenerate-split-progression endpoint."""

import json

import pytest
from fastapi.testclient import TestClient
from PIL import Image
from sqlmodel import Session, SQLModel, create_engine

import api.thumbnail as thumbnail_api
import pipeline.formats.title_cards.cinematic_chapters as cinematic_module
import pipeline.thumbnail as thumbnail_pipeline
from api import app
from database import get_session
from models.script import LevelMeta, Scene, Script, ScriptContent, Segment


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_life_as_a_content(n_levels: int = 3) -> ScriptContent:
    levels = [
        LevelMeta(number=i + 1, descriptor=f"stage{i + 1}", image_prompt="" if i == 0 else f"prompt {i + 1}")
        for i in range(n_levels)
    ]
    segments = [
        Segment(
            name=f"Level {i + 1}",
            scenes=[
                Scene(id=f"ch_{i+1}", narration="x", visual_prompt="[ESTABLISHING] x",
                      duration_estimate_seconds=4.0, is_title_card=True, visual_beat="static"),
            ],
        )
        for i in range(n_levels)
    ]
    return ScriptContent(
        title="Your Life As A Chef",
        format_id="life-as-a",
        cinematic_thumbnail_prompt="chef at work",
        levels=levels,
        segments=segments,
    )


def _make_listicle_content() -> ScriptContent:
    return ScriptContent(
        title="Top 5 Things",
        format_id="youtube-listicle",
        segments=[
            Segment(
                name="Segment 1",
                scenes=[Scene(id="s1", narration="x", visual_prompt="x", visual_beat="static")],
            )
        ],
    )


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def db_engine(tmp_path):
    engine = create_engine(f"sqlite:///{tmp_path / 'test.db'}")
    SQLModel.metadata.create_all(engine)
    return engine


@pytest.fixture
def client(db_engine):
    """TestClient with in-memory DB session override."""

    def override_get_session():
        with Session(db_engine) as session:
            yield session

    app.dependency_overrides[get_session] = override_get_session
    with TestClient(app) as c:
        yield c
    app.dependency_overrides.clear()


@pytest.fixture
def patched_data_dirs(tmp_path, monkeypatch):
    """Redirect DATA_DIR in all relevant modules to tmp_path."""
    monkeypatch.setattr(thumbnail_api, "DATA_DIR", tmp_path)
    monkeypatch.setattr(thumbnail_pipeline, "DATA_DIR", tmp_path)
    monkeypatch.setattr(cinematic_module, "DATA_DIR", tmp_path)
    return tmp_path


@pytest.fixture
def fake_gemini_transform(tmp_path, monkeypatch):
    """Stub transform_with_references: writes a marker PNG and tracks calls."""
    calls: list[dict] = []

    def fake_transform(prompt: str, image_paths: list[str], script_id: str | None = None) -> str:
        calls.append({"prompt": prompt, "image_paths": image_paths})
        out = tmp_path / f"gemini_out_{len(calls)}.png"
        Image.new("RGB", (32, 32), (200, 100, len(calls) * 50)).save(out)
        return str(out)

    monkeypatch.setattr("integrations.google_image_client.transform_with_references", fake_transform)
    return calls


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

def test_regenerate_split_progression_200_and_archives_previous_thumbnail(
    client, db_engine, patched_data_dirs, fake_gemini_transform
):
    """Happy path: 200, returns thumbnail_url, archives previous active thumbnail + sidecar."""
    tmp_path = patched_data_dirs
    script_id = "script-regen-test"
    content = _make_life_as_a_content(n_levels=3)

    # Seed a pre-existing clean image
    images_dir = tmp_path / "projects" / script_id / "images"
    images_dir.mkdir(parents=True, exist_ok=True)
    clean_path = images_dir / "cinematic_thumbnail_clean.png"
    Image.new("RGB", (64, 64), (10, 20, 30)).save(clean_path)

    # Pre-existing final thumbnail + sidecar from a previous run
    final_path = images_dir / "cinematic_thumbnail.png"
    Image.new("RGB", (64, 64), (99, 99, 99)).save(final_path)
    thumbs_dir = tmp_path / "projects" / script_id / "renders" / "thumbnails"
    thumbs_dir.mkdir(parents=True, exist_ok=True)
    active_path = thumbs_dir / "0.png"
    Image.new("RGB", (64, 64), (11, 22, 33)).save(active_path)
    sidecar_path = images_dir / "cinematic_thumbnail.levels.json"
    sidecar_path.write_text(json.dumps({"left_label": "3 months in", "right_label": "8 years in"}))
    original_final_bytes = final_path.read_bytes()
    original_active_bytes = active_path.read_bytes()

    # Insert a Script record into the DB
    with Session(db_engine) as session:
        session.add(
            Script(
                id=script_id,
                brand_id="brand-1",
                topic_title="Your Life As A Chef",
                topic_description="",
                script_json=content.model_dump_json(),
            )
        )
        session.commit()

    # POST to the new endpoint
    resp = client.post(
        "/api/thumbnail/regenerate-split-progression",
        json={"script_id": script_id},
    )

    assert resp.status_code == 200, resp.text
    data = resp.json()
    assert "concepts" in data
    assert len(data["concepts"]) == 2
    concept = data["concepts"][0]
    assert "thumbnail_url" in concept or "image_url" in concept
    url_key = "image_url" if "image_url" in concept else "thumbnail_url"
    assert concept[url_key] is not None
    assert "thumbnails/0.png" in concept[url_key] or "cinematic_thumbnail" in concept[url_key]

    # Final thumbnail was overwritten (content different from pre-existing)
    assert final_path.exists()
    assert final_path.read_bytes() != original_final_bytes
    assert active_path.exists()
    assert active_path.read_bytes() == final_path.read_bytes()
    archived_path = thumbs_dir / "1.png"
    assert archived_path.exists()
    assert archived_path.read_bytes() == original_active_bytes

    # Sidecar was rewritten (new pair)
    assert sidecar_path.exists()
    sidecar_data = json.loads(sidecar_path.read_text())
    assert "left_label" in sidecar_data
    assert "right_label" in sidecar_data

    # Exactly one Gemini call was made (enhance_split_progression only)
    assert len(fake_gemini_transform) == 1


def test_regenerate_split_progression_re_rolls_time_labels(
    client, db_engine, patched_data_dirs, fake_gemini_transform, monkeypatch
):
    """Endpoint always re-rolls the time labels (ignores existing sidecar).

    Verified by:
    - Monkeypatching _pick_life_as_a_thumbnail_labels to a deterministic stub
      and counting how many times it is called.
    - Pre-seeding the sidecar with different labels.
    - Hitting the endpoint twice.
    - Asserting _pick_life_as_a_thumbnail_labels was called exactly twice (once per request).
    - Asserting the sidecar now contains the stub labels, proving it was overwritten each time.
    """
    tmp_path = patched_data_dirs
    script_id = "script-reroll-test"
    content = _make_life_as_a_content(n_levels=4)

    images_dir = tmp_path / "projects" / script_id / "images"
    images_dir.mkdir(parents=True, exist_ok=True)
    Image.new("RGB", (32, 32), (1, 2, 3)).save(images_dir / "cinematic_thumbnail_clean.png")

    # Pre-seed sidecar with different labels — stub labels prove overwrite.
    sidecar_path = images_dir / "cinematic_thumbnail.levels.json"
    sidecar_path.write_text(json.dumps({"left_label": "4 months in", "right_label": "9 years in"}))

    with Session(db_engine) as session:
        session.add(Script(
            id=script_id,
            brand_id="brand-1",
            topic_title="Test",
            topic_description="",
            script_json=content.model_dump_json(),
        ))
        session.commit()

    # Monkeypatch _pick_life_as_a_thumbnail_labels in the source module so the endpoint picks it up.
    # The endpoint imports it inside the function body as:
    #   from pipeline.thumbnail import _pick_life_as_a_thumbnail_labels
    # so patching pipeline.thumbnail._pick_life_as_a_thumbnail_labels is the correct target.
    pick_call_count = {"n": 0}

    def stub_pick_life_as_a_thumbnail_labels(
        style="time_periods", n_levels=None,
    ) -> tuple[str, str]:
        pick_call_count["n"] += 1
        return ("3 months in", "8 years in")

    monkeypatch.setattr(
        thumbnail_pipeline,
        "_pick_life_as_a_thumbnail_labels",
        stub_pick_life_as_a_thumbnail_labels,
    )

    # First call
    resp1 = client.post(
        "/api/thumbnail/regenerate-split-progression",
        json={"script_id": script_id},
    )
    assert resp1.status_code == 200, resp1.text

    # Second call
    resp2 = client.post(
        "/api/thumbnail/regenerate-split-progression",
        json={"script_id": script_id},
    )
    assert resp2.status_code == 200, resp2.text

    # _pick_life_as_a_thumbnail_labels must have been called exactly once per request
    assert pick_call_count["n"] == 2, (
        f"Expected _pick_life_as_a_thumbnail_labels to be called 2 times, got {pick_call_count['n']}"
    )

    # Sidecar must now contain the stub's deterministic labels,
    # proving the endpoint overwrote the seeded labels on each call.
    sidecar_data = json.loads(sidecar_path.read_text())
    assert sidecar_data["left_label"] == "3 months in"
    assert sidecar_data["right_label"] == "8 years in"

    # Two Gemini enhancement calls (one per request)
    assert len(fake_gemini_transform) == 2


def test_regenerate_split_progression_404_on_missing_script(
    client, patched_data_dirs, fake_gemini_transform
):
    resp = client.post(
        "/api/thumbnail/regenerate-split-progression",
        json={"script_id": "nonexistent"},
    )
    assert resp.status_code == 404
    assert len(fake_gemini_transform) == 0


def test_regenerate_split_progression_400_on_wrong_format(
    client, db_engine, patched_data_dirs, fake_gemini_transform
):
    """Returns 400 if the script is not a cinematic-chapters format."""
    script_id = "script-listicle"
    content = _make_listicle_content()

    with Session(db_engine) as session:
        session.add(Script(
            id=script_id,
            brand_id="brand-1",
            topic_title="Top 5",
            topic_description="",
            script_json=content.model_dump_json(),
        ))
        session.commit()

    resp = client.post(
        "/api/thumbnail/regenerate-split-progression",
        json={"script_id": script_id},
    )
    assert resp.status_code == 400
    assert "cinematic-chapters" in resp.json()["detail"]
    assert len(fake_gemini_transform) == 0


def test_regenerate_split_progression_400_when_clean_image_missing(
    client, db_engine, patched_data_dirs, fake_gemini_transform
):
    """Returns 400 if cinematic_thumbnail_clean.png doesn't exist yet."""
    script_id = "script-no-clean"
    content = _make_life_as_a_content(n_levels=3)

    # Do NOT create the clean image

    with Session(db_engine) as session:
        session.add(Script(
            id=script_id,
            brand_id="brand-1",
            topic_title="Test",
            topic_description="",
            script_json=content.model_dump_json(),
        ))
        session.commit()

    resp = client.post(
        "/api/thumbnail/regenerate-split-progression",
        json={"script_id": script_id},
    )
    assert resp.status_code == 400
    assert "clean" in resp.json()["detail"].lower() or "missing" in resp.json()["detail"].lower()
    assert len(fake_gemini_transform) == 0


def test_regenerate_split_progression_400_when_too_few_levels(
    client, db_engine, patched_data_dirs, fake_gemini_transform
):
    """Returns 400 if script has fewer than 2 levels."""
    script_id = "script-one-level"
    content = _make_life_as_a_content(n_levels=1)

    images_dir = patched_data_dirs / "projects" / script_id / "images"
    images_dir.mkdir(parents=True, exist_ok=True)
    Image.new("RGB", (32, 32), (1, 2, 3)).save(images_dir / "cinematic_thumbnail_clean.png")

    with Session(db_engine) as session:
        session.add(Script(
            id=script_id,
            brand_id="brand-1",
            topic_title="Test",
            topic_description="",
            script_json=content.model_dump_json(),
        ))
        session.commit()

    resp = client.post(
        "/api/thumbnail/regenerate-split-progression",
        json={"script_id": script_id},
    )
    assert resp.status_code == 400
    assert len(fake_gemini_transform) == 0


def test_regenerate_split_progression_style_levels(
    client, db_engine, patched_data_dirs, fake_gemini_transform
):
    """Explicit style='levels' produces LEVEL X / LEVEL Y labels and persists style in sidecar."""
    tmp_path = patched_data_dirs
    script_id = "script-style-levels"
    content = _make_life_as_a_content(n_levels=4)

    images_dir = tmp_path / "projects" / script_id / "images"
    images_dir.mkdir(parents=True, exist_ok=True)
    Image.new("RGB", (32, 32), (1, 2, 3)).save(images_dir / "cinematic_thumbnail_clean.png")

    with Session(db_engine) as session:
        session.add(Script(
            id=script_id,
            brand_id="brand-1",
            topic_title="Test",
            topic_description="",
            script_json=content.model_dump_json(),
        ))
        session.commit()

    resp = client.post(
        "/api/thumbnail/regenerate-split-progression",
        json={"script_id": script_id, "style": "levels"},
    )
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["label_style"] == "levels"

    sidecar_path = images_dir / "cinematic_thumbnail.levels.json"
    sidecar_data = json.loads(sidecar_path.read_text())
    assert sidecar_data["style"] == "levels"
    assert sidecar_data["left_label"].startswith("LEVEL ")
    assert sidecar_data["right_label"].startswith("LEVEL ")


def test_regenerate_split_progression_style_time_periods(
    client, db_engine, patched_data_dirs, fake_gemini_transform
):
    """Explicit style='time_periods' produces months/years labels and persists style."""
    tmp_path = patched_data_dirs
    script_id = "script-style-tp"
    content = _make_life_as_a_content(n_levels=4)

    images_dir = tmp_path / "projects" / script_id / "images"
    images_dir.mkdir(parents=True, exist_ok=True)
    Image.new("RGB", (32, 32), (1, 2, 3)).save(images_dir / "cinematic_thumbnail_clean.png")

    # Pre-seed with levels style — explicit body style should override.
    sidecar_path = images_dir / "cinematic_thumbnail.levels.json"
    sidecar_path.write_text(json.dumps({
        "style": "levels", "left_label": "LEVEL 1", "right_label": "LEVEL 4",
    }))

    with Session(db_engine) as session:
        session.add(Script(
            id=script_id,
            brand_id="brand-1",
            topic_title="Test",
            topic_description="",
            script_json=content.model_dump_json(),
        ))
        session.commit()

    resp = client.post(
        "/api/thumbnail/regenerate-split-progression",
        json={"script_id": script_id, "style": "time_periods"},
    )
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["label_style"] == "time_periods"

    sidecar_data = json.loads(sidecar_path.read_text())
    assert sidecar_data["style"] == "time_periods"
    assert sidecar_data["left_label"].endswith(" months in")
    assert sidecar_data["right_label"].endswith(" years in")


def test_regenerate_split_progression_omitted_style_reuses_sidecar(
    client, db_engine, patched_data_dirs, fake_gemini_transform
):
    """When style is omitted, the endpoint reuses the sidecar's existing style."""
    tmp_path = patched_data_dirs
    script_id = "script-reuse-style"
    content = _make_life_as_a_content(n_levels=4)

    images_dir = tmp_path / "projects" / script_id / "images"
    images_dir.mkdir(parents=True, exist_ok=True)
    Image.new("RGB", (32, 32), (1, 2, 3)).save(images_dir / "cinematic_thumbnail_clean.png")

    sidecar_path = images_dir / "cinematic_thumbnail.levels.json"
    sidecar_path.write_text(json.dumps({
        "style": "levels", "left_label": "LEVEL 1", "right_label": "LEVEL 4",
    }))

    with Session(db_engine) as session:
        session.add(Script(
            id=script_id,
            brand_id="brand-1",
            topic_title="Test",
            topic_description="",
            script_json=content.model_dump_json(),
        ))
        session.commit()

    resp = client.post(
        "/api/thumbnail/regenerate-split-progression",
        json={"script_id": script_id},
    )
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["label_style"] == "levels"

    sidecar_data = json.loads(sidecar_path.read_text())
    assert sidecar_data["style"] == "levels"


def test_regenerate_split_progression_omitted_style_no_sidecar_uses_default(
    client, db_engine, patched_data_dirs, fake_gemini_transform
):
    """When style omitted and no sidecar, falls back to default (time_periods)."""
    tmp_path = patched_data_dirs
    script_id = "script-default-style"
    content = _make_life_as_a_content(n_levels=4)

    images_dir = tmp_path / "projects" / script_id / "images"
    images_dir.mkdir(parents=True, exist_ok=True)
    Image.new("RGB", (32, 32), (1, 2, 3)).save(images_dir / "cinematic_thumbnail_clean.png")
    # No sidecar pre-seeded.

    with Session(db_engine) as session:
        session.add(Script(
            id=script_id,
            brand_id="brand-1",
            topic_title="Test",
            topic_description="",
            script_json=content.model_dump_json(),
        ))
        session.commit()

    resp = client.post(
        "/api/thumbnail/regenerate-split-progression",
        json={"script_id": script_id},
    )
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["label_style"] == "time_periods"
