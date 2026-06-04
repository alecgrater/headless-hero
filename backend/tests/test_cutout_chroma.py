from pathlib import Path

from PIL import Image, ImageDraw

from pipeline.cutout_chroma import save_keyed_trimmed_cutout


def test_save_keyed_trimmed_cutout_removes_corner_sampled_background(tmp_path: Path):
    source = Image.new("RGBA", (120, 90), (0, 255, 0, 255))
    draw = ImageDraw.Draw(source)
    draw.rectangle((40, 25, 75, 65), fill=(200, 20, 20, 255))

    output_path = tmp_path / "cutout.png"

    trim_box = save_keyed_trimmed_cutout(source, output_path, padding=4)

    assert trim_box == [36, 21, 80, 70]
    with Image.open(output_path) as result:
        assert result.mode == "RGBA"
        assert result.size == (44, 49)
        assert result.getbbox() is not None
        assert result.getpixel((0, 0))[3] == 0


def test_save_keyed_trimmed_cutout_handles_empty_cutout(tmp_path: Path):
    source = Image.new("RGBA", (40, 40), (0, 255, 0, 255))
    output_path = tmp_path / "empty.png"

    trim_box = save_keyed_trimmed_cutout(source, output_path)

    assert trim_box == [0, 0, 40, 40]
    with Image.open(output_path) as result:
        assert result.size == (40, 40)
