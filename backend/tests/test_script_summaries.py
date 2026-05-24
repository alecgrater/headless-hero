from api import scripts as scripts_api
from models.script import Scene, Script, ScriptContent, Segment


def _script_record(script_id: str) -> Script:
    content = ScriptContent(
        title="Your Life As A Test",
        format_id="life-as-a",
        cinematic_thumbnail_prompt="A dramatic split life thumbnail",
        segments=[
            Segment(
                name="First",
                scenes=[
                    Scene(
                        id="scene-1",
                        narration="Hello",
                        visual_prompt="A scene fallback",
                        image_url=f"/static/projects/{script_id}/images/scene_1.png",
                    ),
                ],
            ),
        ],
    )
    return Script(
        id=script_id,
        brand_id="brand-1",
        topic_title=content.title,
        topic_description="",
        script_json=content.model_dump_json(),
    )


def test_summary_prefers_active_longform_thumbnail(tmp_path, monkeypatch):
    monkeypatch.setattr(scripts_api, "DATA_DIR", tmp_path)
    script_id = "script-life-active"
    thumbs_dir = tmp_path / "projects" / script_id / "renders" / "thumbnails"
    images_dir = tmp_path / "projects" / script_id / "images"
    thumbs_dir.mkdir(parents=True)
    images_dir.mkdir(parents=True)
    (thumbs_dir / "0.png").write_bytes(b"active thumbnail")
    (images_dir / "cinematic_thumbnail.png").write_bytes(b"cinematic thumbnail")

    summary = scripts_api._build_summary(_script_record(script_id))

    assert summary.thumbnail_url == f"/static/projects/{script_id}/renders/thumbnails/0.png"


def test_summary_uses_life_as_a_cinematic_thumbnail(tmp_path, monkeypatch):
    monkeypatch.setattr(scripts_api, "DATA_DIR", tmp_path)
    script_id = "script-life-cinematic"
    images_dir = tmp_path / "projects" / script_id / "images"
    images_dir.mkdir(parents=True)
    (images_dir / "cinematic_thumbnail.png").write_bytes(b"cinematic thumbnail")

    summary = scripts_api._build_summary(_script_record(script_id))

    assert summary.thumbnail_url == f"/static/projects/{script_id}/images/cinematic_thumbnail.png"
    assert summary.format_id == "life-as-a"


def test_summary_falls_back_to_first_scene_image(tmp_path, monkeypatch):
    monkeypatch.setattr(scripts_api, "DATA_DIR", tmp_path)
    script_id = "script-life-fallback"

    summary = scripts_api._build_summary(_script_record(script_id))

    assert summary.thumbnail_url == f"/static/projects/{script_id}/images/scene_1.png"
