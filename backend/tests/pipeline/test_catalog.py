"""Tests for catalog export parsing helpers."""

from pipeline.catalog import parse_seo_txt


def test_parse_seo_markdown(tmp_path):
    seo_path = tmp_path / "[Longform] [SEO] - Project.md"
    seo_path.write_text(
        "# Title\n\n"
        "A Useful Upload Title\n\n"
        "# Description\n\n"
        "First line.\n"
        "Second line.\n\n"
        "# Tags\n\n"
        "alpha, beta, gamma\n",
        encoding="utf-8",
    )

    title, description, tags = parse_seo_txt(seo_path)

    assert title == "A Useful Upload Title"
    assert description == "First line.\nSecond line."
    assert tags == ["alpha", "beta", "gamma"]


def test_build_youtube_description_appends_tags():
    from pipeline.publishing import _build_youtube_description

    result = _build_youtube_description("Great video about cats.", ["cats", "cute animals", "pets"])
    assert result == "Great video about cats.\n\nTags: cats, cute animals, pets"


def test_build_youtube_description_no_tags():
    from pipeline.publishing import _build_youtube_description

    result = _build_youtube_description("Just a description.", [])
    assert result == "Just a description."


def test_build_youtube_description_empty_description():
    from pipeline.publishing import _build_youtube_description

    result = _build_youtube_description("", ["one", "two"])
    assert result == "Tags: one, two"
