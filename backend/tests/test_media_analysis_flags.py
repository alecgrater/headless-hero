"""Tests for manual media analysis source fallback behavior."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from api.media import media_analysis_source_flags


def test_media_analysis_flags_default_old_scripts_to_manual_sources():
    assert media_analysis_source_flags({"segments": []}) == (True, True)


def test_media_analysis_flags_preserve_explicit_source_settings():
    assert media_analysis_source_flags({
        "segments": [],
        "gameplay_enabled": False,
        "stock_photo_enabled": True,
    }) == (False, True)

