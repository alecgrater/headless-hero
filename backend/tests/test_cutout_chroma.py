from pathlib import Path

from PIL import Image, ImageDraw

from pipeline.cutout_chroma import key_out_background, sample_background_rgb, save_keyed_trimmed_cutout


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


def test_key_out_background_accepts_non_rgba_input():
    source = Image.new("RGB", (20, 20), (0, 255, 0))
    draw = ImageDraw.Draw(source)
    draw.rectangle((8, 8, 11, 11), fill=(200, 20, 20))

    keyed = key_out_background(source)

    assert keyed.mode == "RGBA"
    assert keyed.getpixel((0, 0))[3] == 0
    assert keyed.getpixel((9, 9))[3] == 255


def test_key_out_background_prefers_magenta_chroma_over_contact_sheet_margins():
    source = Image.new("RGBA", (80, 60), (212, 210, 204, 255))
    draw = ImageDraw.Draw(source)
    draw.rectangle((12, 0, 67, 59), fill=(229, 15, 175, 255))
    draw.rectangle((28, 18, 51, 42), fill=(230, 200, 170, 255))
    draw.rectangle((36, 26, 42, 32), fill=(5, 5, 5, 255))

    keyed = key_out_background(source)

    assert keyed.getpixel((0, 0))[3] == 0
    assert keyed.getpixel((20, 10))[3] == 0
    assert keyed.getpixel((35, 30)) == (230, 200, 170, 255)
    assert keyed.getpixel((39, 29)) == (5, 5, 5, 255)


def test_key_out_background_preserves_isolated_chroma_colored_subject_detail():
    source = Image.new("RGBA", (80, 60), (212, 210, 204, 255))
    draw = ImageDraw.Draw(source)
    draw.rectangle((12, 0, 67, 59), fill=(229, 15, 175, 255))
    draw.rectangle((24, 12, 55, 48), fill=(230, 200, 170, 255))
    draw.rectangle((34, 24, 45, 35), fill=(229, 15, 175, 255))

    keyed = key_out_background(source)

    assert keyed.getpixel((20, 10))[3] == 0
    assert keyed.getpixel((39, 29)) == (229, 15, 175, 255)


def test_key_out_background_removes_soft_green_chroma_and_dark_cell_divider():
    source = Image.new("RGBA", (80, 60), (145, 210, 100, 255))
    draw = ImageDraw.Draw(source)
    draw.rectangle((79, 0, 79, 59), fill=(8, 6, 4, 255))
    draw.rectangle((24, 12, 55, 48), fill=(230, 200, 170, 255))
    draw.rectangle((36, 26, 42, 32), fill=(5, 5, 5, 255))

    keyed = key_out_background(source)

    assert keyed.getpixel((10, 10))[3] == 0
    assert keyed.getpixel((79, 30))[3] == 0
    assert keyed.getpixel((35, 30)) == (230, 200, 170, 255)
    assert keyed.getpixel((39, 29)) == (5, 5, 5, 255)


def test_key_out_background_preserves_narrow_dark_subject_touching_edge():
    source = Image.new("RGBA", (80, 60), (145, 210, 100, 255))
    draw = ImageDraw.Draw(source)
    draw.rectangle((36, 10, 44, 59), fill=(10, 8, 6, 255))

    keyed = key_out_background(source)

    assert keyed.getpixel((10, 10))[3] == 0
    assert keyed.getpixel((40, 30)) == (10, 8, 6, 255)
    assert keyed.getpixel((40, 58)) == (10, 8, 6, 255)


def test_key_out_background_removes_small_edge_artifacts_but_keeps_edge_touching_subject():
    source = Image.new("RGBA", (80, 60), (145, 210, 100, 255))
    draw = ImageDraw.Draw(source)
    draw.rectangle((70, 0, 79, 59), fill=(242, 242, 242, 255))
    draw.rectangle((0, 0, 8, 4), fill=(182, 166, 186, 255))
    draw.rectangle((24, 12, 55, 59), fill=(230, 200, 170, 255))
    draw.rectangle((36, 26, 42, 32), fill=(5, 5, 5, 255))

    keyed = key_out_background(source)

    assert keyed.getpixel((2, 2))[3] == 0
    assert keyed.getpixel((35, 58)) == (230, 200, 170, 255)
    assert keyed.getpixel((39, 29)) == (5, 5, 5, 255)


def test_sample_background_rgb_uses_non_overlapping_corners_for_small_images():
    source = Image.new("RGBA", (19, 19), (0, 255, 0, 255))
    source.putpixel((9, 9), (200, 20, 20, 255))

    assert sample_background_rgb(source) == (0, 255, 0)
