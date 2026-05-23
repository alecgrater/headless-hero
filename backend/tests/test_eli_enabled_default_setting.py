from api.settings import ALLOWED_KEYS, _DEFAULTS, _PLAINTEXT_KEYS


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
