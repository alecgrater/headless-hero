import pytest
from fastapi import HTTPException

from api.settings import (
    ALLOWED_KEYS,
    RANGED_INTEGER_SETTINGS,
    _DEFAULTS,
    _PLAINTEXT_KEYS,
    _validate_ranged_integer_settings,
)


def test_eli_enabled_default_is_allowed():
    assert "ELI_ENABLED_DEFAULT" in ALLOWED_KEYS


def test_eli_enabled_default_has_default_true():
    assert _DEFAULTS.get("ELI_ENABLED_DEFAULT") == "true"


def test_eli_enabled_default_is_plaintext():
    assert "ELI_ENABLED_DEFAULT" in _PLAINTEXT_KEYS


def test_style_preset_enabled_default_is_allowed():
    from api.settings import ALLOWED_KEYS
    assert "STYLE_PRESET_ENABLED_DEFAULT" in ALLOWED_KEYS


def test_style_preset_enabled_default_has_default_true():
    from api.settings import _DEFAULTS
    assert _DEFAULTS.get("STYLE_PRESET_ENABLED_DEFAULT") == "true"


def test_active_style_preset_id_is_allowed():
    from api.settings import ALLOWED_KEYS
    assert "ACTIVE_STYLE_PRESET_ID" in ALLOWED_KEYS


def test_active_style_preset_id_default_empty():
    from api.settings import _DEFAULTS
    assert _DEFAULTS.get("ACTIVE_STYLE_PRESET_ID") == ""


def test_life_as_a_chunking_settings_are_allowed_plaintext_and_defaulted():
    expected_defaults = {
        "LIFE_AS_A_SCENE_CHUNKING_ENABLED": "true",
        "LIFE_AS_A_TARGET_SCENE_SECONDS": "8",
        "LIFE_AS_A_MAX_SCENE_SECONDS": "12",
        "LIFE_AS_A_SINGLE_VISUAL_MAX_SECONDS": "8",
    }

    for key, default in expected_defaults.items():
        assert key in ALLOWED_KEYS
        assert key in _PLAINTEXT_KEYS
        assert _DEFAULTS.get(key) == default


def test_life_as_a_chunking_range_validation_accepts_and_normalizes_values():
    keys = {
        "LIFE_AS_A_TARGET_SCENE_SECONDS": " 9 ",
        "LIFE_AS_A_MAX_SCENE_SECONDS": "14",
        "LIFE_AS_A_SINGLE_VISUAL_MAX_SECONDS": "7",
    }

    _validate_ranged_integer_settings(keys)

    assert keys == {
        "LIFE_AS_A_TARGET_SCENE_SECONDS": "9",
        "LIFE_AS_A_MAX_SCENE_SECONDS": "14",
        "LIFE_AS_A_SINGLE_VISUAL_MAX_SECONDS": "7",
    }


@pytest.mark.parametrize(
    ("key", "value"),
    [
        ("LIFE_AS_A_TARGET_SCENE_SECONDS", "4"),
        ("LIFE_AS_A_TARGET_SCENE_SECONDS", "13"),
        ("LIFE_AS_A_MAX_SCENE_SECONDS", "7"),
        ("LIFE_AS_A_MAX_SCENE_SECONDS", "19"),
        ("LIFE_AS_A_SINGLE_VISUAL_MAX_SECONDS", "4"),
        ("LIFE_AS_A_SINGLE_VISUAL_MAX_SECONDS", "13"),
        ("LIFE_AS_A_SINGLE_VISUAL_MAX_SECONDS", "soon"),
    ],
)
def test_life_as_a_chunking_range_validation_rejects_invalid_values(key, value):
    with pytest.raises(HTTPException) as exc_info:
        _validate_ranged_integer_settings({key: value})

    minimum, maximum = RANGED_INTEGER_SETTINGS[key]
    assert exc_info.value.status_code == 400
    assert f"integer from {minimum} to {maximum}" in exc_info.value.detail
