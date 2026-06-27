"""Render-time safety net: image-backed scenes must never reach Remotion blank.

A scene can arrive at render in an image-backed visual_mode (full_frame /
multi_frame / continuous) with no generated image — e.g. a captions/stat_card/
comparison_board scene promoted to full_frame without regenerating assets.
`ensure_renderable_scene_images` backfills the prompt, generates the image, and
persists it so the renderer never draws the gray "No image" placeholder.
"""

import sys
from pathlib import Path
from unittest.mock import patch

import pytest
from sqlmodel import Session, SQLModel, create_engine

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from pipeline import remotion_render
from models.script import Script, ScriptContent, Scene, Segment


def _content() -> ScriptContent:
    return ScriptContent(
        title="Conversation",
        segments=[
            Segment(
                name="Segment",
                scenes=[
                    # Healthy full_frame scene — already has an image, untouched.
                    Scene(
                        id="scene_001",
                        narration="A normal scene.",
                        visual_prompt="A normal scene image",
                        visual_mode="full_frame",
                        image_url="/static/projects/s/images/scene_001.png",
                    ),
                    # Broken: full_frame, no image, empty prompt, carries caption text.
                    Scene(
                        id="scene_002",
                        narration="It is about the filter.",
                        visual_prompt="",
                        visual_mode="full_frame",
                        caption_text="It is about the filter.",
                    ),
                    # Captions scene with no image is legitimate — must be skipped.
                    Scene(
                        id="scene_003",
                        narration="Pure caption beat.",
                        visual_prompt="",
                        visual_mode="captions",
                        caption_text="Pure caption beat.",
                    ),
                ],
            )
        ],
    )


@pytest.fixture
def engine(tmp_path, monkeypatch):
    eng = create_engine(f"sqlite:///{tmp_path / 'test.db'}")
    SQLModel.metadata.create_all(eng)
    monkeypatch.setattr("database.engine", eng, raising=False)
    return eng


def test_ensure_renderable_scene_images_repairs_blank_full_frame(engine):
    content = _content()
    with Session(engine) as session:
        session.add(Script(id="s", brand_id="b", script_json=content.model_dump_json()))
        session.commit()

    calls: list[str] = []

    def _fake_generate(*, scene_id, visual_prompt, script_id, **kwargs):
        calls.append(scene_id)
        return (f"/static/projects/{script_id}/images/{scene_id}.png", visual_prompt, None)

    with patch("pipeline.image_gen.generate_scene_image", side_effect=_fake_generate):
        repaired = remotion_render.ensure_renderable_scene_images("s", content)

    # Only the broken full_frame scene is regenerated.
    assert repaired == 1
    assert calls == ["scene_002"]

    scene_002 = content.all_scenes()[1]
    assert scene_002.visual_prompt.strip() == "It is about the filter."  # backfilled
    assert scene_002.image_url.endswith("scene_002.png")

    # Healthy + captions scenes untouched.
    assert content.all_scenes()[0].image_url.endswith("scene_001.png")
    assert content.all_scenes()[2].image_url == ""

    # Repair is persisted to the DB.
    with Session(engine) as session:
        stored = ScriptContent.model_validate_json(session.get(Script, "s").script_json)
    assert stored.all_scenes()[1].image_url.endswith("scene_002.png")
    assert stored.all_scenes()[1].visual_prompt.strip() == "It is about the filter."


def test_ensure_renderable_scene_images_noop_when_all_present(engine):
    content = ScriptContent(
        title="All good",
        segments=[
            Segment(
                name="Segment",
                scenes=[
                    Scene(
                        id="scene_001",
                        narration="A normal scene.",
                        visual_prompt="A normal scene image",
                        visual_mode="full_frame",
                        image_url="/static/projects/s/images/scene_001.png",
                    ),
                ],
            )
        ],
    )
    with Session(engine) as session:
        session.add(Script(id="s2", brand_id="b", script_json=content.model_dump_json()))
        session.commit()

    with patch("pipeline.image_gen.generate_scene_image") as mock_gen:
        repaired = remotion_render.ensure_renderable_scene_images("s2", content)

    assert repaired == 0
    mock_gen.assert_not_called()
