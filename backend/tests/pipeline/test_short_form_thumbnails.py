"""Tests for short-form thumbnail helpers."""

from pathlib import Path

from PIL import Image, ImageDraw

from models.script import Scene, ScriptContent, Segment
from pipeline import short_form_thumbnails as thumbs
from pipeline.short_form_parts import short_form_part_indicator


def _content() -> ScriptContent:
    return ScriptContent(
        title="Example",
        segments=[
            Segment(
                name="The Bizarre Case of the Missing Lighthouse Keepers",
                short_name="Missing Keepers",
                scenes=[Scene(id="s1", narration="", visual_prompt="")],
            ),
            Segment(
                name="The Vanishing Train",
                short_name="",
                scenes=[Scene(id="s2", narration="", visual_prompt="")],
            ),
        ],
    )


def test_short_thumbnail_title_prefers_short_name():
    assert thumbs.short_thumbnail_title(_content(), 0) == "Missing Keepers"


def test_short_thumbnail_title_falls_back_to_segment_name():
    assert thumbs.short_thumbnail_title(_content(), 1) == "The Vanishing Train"


def test_short_thumbnail_filename_sanitizes_segment_name():
    result = thumbs.short_thumbnail_filename('Bad/Name: "Test"', 3, 8)
    assert result == "[Shortform 3∕8] [Thumbnail] - BadName Test.png"
    assert "/" not in result


def test_short_form_part_indicator_only_for_life_as_a():
    content = _content()
    assert short_form_part_indicator(content, 0) == ""

    content.format_id = "life-as-a"
    assert short_form_part_indicator(content, 1) == "Part 2/2"


def test_fit_text_shrinks_instead_of_splitting_single_word():
    canvas = Image.new("RGB", (1080, 1920), (0, 0, 0))
    draw = ImageDraw.Draw(canvas)

    _font, lines, _gap, bboxes = thumbs._fit_text(draw, "RECIPROCITY", 960, 390)

    assert lines == ["RECIPROCITY"]
    assert bboxes[0][2] - bboxes[0][0] <= 960


def test_generate_short_thumbnail_dimensions_and_dpi(tmp_path, monkeypatch):
    monkeypatch.setattr(thumbs, "DATA_DIR", tmp_path)
    script_id = "abc"
    source_dir = tmp_path / "projects" / script_id / "images"
    source_dir.mkdir(parents=True)
    Image.new("RGB", (768, 768), (80, 120, 200)).save(source_dir / "title_card_0.png")

    url = thumbs.generate_short_thumbnail(script_id, 0, _content())

    output = tmp_path / "projects" / script_id / "renders" / "short_thumbnails" / "0.png"
    assert url == f"/static/projects/{script_id}/renders/short_thumbnails/0.png"
    assert output.is_file()
    with Image.open(output) as img:
        assert img.size == (1080, 1920)
        assert img.info.get("dpi") == (72.009, 72.009)
    assert output.stat().st_size <= thumbs.MAX_PNG_BYTES


def test_generate_short_thumbnail_missing_source_raises(tmp_path, monkeypatch):
    monkeypatch.setattr(thumbs, "DATA_DIR", tmp_path)
    try:
        thumbs.generate_short_thumbnail("abc", 0, _content())
    except RuntimeError as exc:
        assert "Title-card image missing" in str(exc)
    else:
        raise AssertionError("Expected RuntimeError")


def test_generate_all_preserves_requested_order(tmp_path, monkeypatch):
    monkeypatch.setattr(thumbs, "DATA_DIR", tmp_path)
    script_id = "abc"
    source_dir = tmp_path / "projects" / script_id / "images"
    source_dir.mkdir(parents=True)
    for idx, color in [(0, (80, 120, 200)), (1, (180, 80, 120))]:
        Image.new("RGB", (768, 768), color).save(source_dir / f"title_card_{idx}.png")

    urls = thumbs.generate_all_short_thumbnails(script_id, _content(), [1, 0])

    assert urls == [
        f"/static/projects/{script_id}/renders/short_thumbnails/1.png",
        f"/static/projects/{script_id}/renders/short_thumbnails/0.png",
    ]


def test_export_generates_missing_and_copies_files(tmp_path, monkeypatch):
    monkeypatch.setattr(thumbs, "DATA_DIR", tmp_path)
    monkeypatch.setenv("DOWNLOADS_DIR", str(tmp_path / "Downloads"))
    script_id = "abc"
    source_dir = tmp_path / "projects" / script_id / "images"
    source_dir.mkdir(parents=True)
    for idx, color in [(0, (80, 120, 200)), (1, (180, 80, 120))]:
        Image.new("RGB", (768, 768), color).save(source_dir / f"title_card_{idx}.png")

    folder, files, paths = thumbs.export_short_thumbnails(script_id, _content(), "Project/Name")

    assert folder == str(Path(tmp_path / "Downloads" / "[project] ProjectName"))
    assert files == [
        "[Shortform 1∕2] [Thumbnail] - The Bizarre Case of the Missing Lighthouse Keepers.png",
        "[Shortform 2∕2] [Thumbnail] - The Vanishing Train.png",
    ]
    assert Path(paths[0]).is_file()
    assert Path(paths[1]).is_file()
