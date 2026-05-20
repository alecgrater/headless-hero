"""Tests for the format registry resolution + defensive fallback."""

import logging
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from pipeline.formats import (
    DEFAULT_FORMAT_ID,
    get_format,
    list_formats,
    resolve_format,
)


def test_default_format_resolves():
    fmt = resolve_format(None)
    assert fmt.id == DEFAULT_FORMAT_ID


def test_resolve_format_falls_back_for_unknown(caplog):
    with caplog.at_level(logging.WARNING):
        fmt = resolve_format("does-not-exist")
    assert fmt.id == DEFAULT_FORMAT_ID
    assert any("does-not-exist" in r.message for r in caplog.records)


def test_get_format_raises_for_unknown():
    with pytest.raises(KeyError):
        get_format("does-not-exist")


def test_list_formats_returns_registered_formats():
    formats = list_formats()
    ids = [f.id for f in formats]
    assert "youtube-listicle" in ids
    assert "life-as-a" in ids


def test_youtube_listicle_flags():
    fmt = get_format("youtube-listicle")
    assert fmt.supports_cold_open is True
    assert fmt.supports_hook_scoring is True
    assert fmt.title_card_strategy.kind == "composite-grid"
    assert fmt.level_label == "segment"


def test_life_as_a_flags():
    fmt = get_format("life-as-a")
    assert fmt.supports_cold_open is False
    assert fmt.supports_hook_scoring is False
    assert fmt.supports_segmented_generation is True
    assert fmt.title_card_strategy.kind == "cinematic-chapters"
    assert fmt.level_label == "level"
