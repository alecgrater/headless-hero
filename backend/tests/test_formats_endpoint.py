"""Tests for the /api/formats payload (reference-page fields)."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))


def test_formats_endpoint_includes_reference_fields():
    from api.formats import list_formats_endpoint

    summaries = {s.id: s for s in list_formats_endpoint()}

    listicle = summaries["youtube-listicle"]
    life = summaries["life-as-a"]

    assert "captions" in listicle.supported_visual_modes
    assert "captions" not in life.supported_visual_modes
    assert "stat_card" not in life.supported_visual_modes

    assert set(listicle.allowed_visual_beats) == {"static", "continuous", "multi_frame"}
    assert listicle.max_consecutive_same_beat == 3
    assert life.max_consecutive_same_beat == 2

    assert life.target_distribution["static"] == [0.45, 0.60]
    assert listicle.target_distribution == {}

    assert life.reference_notes
    assert all(set(n.keys()) == {"category", "text"} for n in life.reference_notes)
