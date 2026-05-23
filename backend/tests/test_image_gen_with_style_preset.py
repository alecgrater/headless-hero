"""Tests for style_reference_path threading through generate_image()."""

from unittest.mock import MagicMock, patch

import pytest


@pytest.fixture
def fake_gemini_response():
    """A fake Gemini response with one inline_data Part containing tiny PNG bytes."""
    response = MagicMock()
    part = MagicMock()
    part.inline_data = MagicMock()
    # 1x1 PNG: minimal valid PNG header + IHDR + IDAT + IEND
    part.inline_data.data = (
        b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01\x00\x00\x00\x01"
        b"\x08\x06\x00\x00\x00\x1f\x15\xc4\x89\x00\x00\x00\rIDATx\x9cc\xfc\xcf"
        b"\xc0\x00\x00\x00\x05\x00\x01\xa6\xff\xa9\x9b\x00\x00\x00\x00IEND\xaeB`\x82"
    )
    response.parts = [part]
    return response


def test_generate_image_passes_style_reference_as_part(tmp_path, fake_gemini_response):
    """When style_reference_path is set, generate_image attaches it as a Part."""
    from integrations import google_image_client

    style_ref = tmp_path / "style.png"
    style_ref.write_bytes(b"fakepng")

    captured_contents = []

    def fake_call(client, contents, aspect, script_id=None, max_retries=3):
        captured_contents.append(contents)
        out = tmp_path / "out.png"
        out.write_bytes(fake_gemini_response.parts[0].inline_data.data)
        return str(out)

    with patch.object(google_image_client, "_call_gemini", side_effect=fake_call), \
         patch.object(google_image_client, "get_google_client", return_value=MagicMock()), \
         patch.object(google_image_client, "record_usage"):
        google_image_client.generate_image(
            prompt="a scene",
            style_reference_path=str(style_ref),
        )

    assert len(captured_contents) == 1
    contents = captured_contents[0]
    # Last item must be the prompt string
    assert contents[-1] == "a scene"
    # First items must be Parts (one for the style ref, since no character ref provided)
    assert len(contents) == 2  # 1 style ref + 1 prompt


def test_generate_image_without_style_reference_omits_part(tmp_path, fake_gemini_response):
    from integrations import google_image_client

    captured_contents = []

    def fake_call(client, contents, aspect, script_id=None, max_retries=3):
        captured_contents.append(contents)
        out = tmp_path / "out.png"
        out.write_bytes(fake_gemini_response.parts[0].inline_data.data)
        return str(out)

    with patch.object(google_image_client, "_call_gemini", side_effect=fake_call), \
         patch.object(google_image_client, "get_google_client", return_value=MagicMock()), \
         patch.object(google_image_client, "record_usage"):
        google_image_client.generate_image(prompt="a scene")

    contents = captured_contents[0]
    assert contents == ["a scene"]


def test_generate_image_with_both_char_and_style_refs(tmp_path, fake_gemini_response):
    """When both refs are present, char ref comes first, style ref second, prompt last."""
    from integrations import google_image_client

    char_ref = tmp_path / "char.png"
    char_ref.write_bytes(b"charpng")
    style_ref = tmp_path / "style.png"
    style_ref.write_bytes(b"stylepng")

    captured_contents = []

    def fake_call(client, contents, aspect, script_id=None, max_retries=3):
        captured_contents.append(contents)
        out = tmp_path / "out.png"
        out.write_bytes(fake_gemini_response.parts[0].inline_data.data)
        return str(out)

    with patch.object(google_image_client, "_call_gemini", side_effect=fake_call), \
         patch.object(google_image_client, "get_google_client", return_value=MagicMock()), \
         patch.object(google_image_client, "record_usage"):
        google_image_client.generate_image(
            prompt="a scene",
            reference_image_path=str(char_ref),
            style_reference_path=str(style_ref),
        )

    contents = captured_contents[0]
    # 2 parts (char + style) + prompt = 3 items
    assert len(contents) == 3
    assert contents[-1] == "a scene"
