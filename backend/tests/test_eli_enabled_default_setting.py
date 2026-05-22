from api.settings import ALLOWED_KEYS, _DEFAULTS, _PLAINTEXT_KEYS


def test_eli_enabled_default_is_allowed():
    assert "ELI_ENABLED_DEFAULT" in ALLOWED_KEYS


def test_eli_enabled_default_has_default_true():
    assert _DEFAULTS.get("ELI_ENABLED_DEFAULT") == "true"


def test_eli_enabled_default_is_plaintext():
    assert "ELI_ENABLED_DEFAULT" in _PLAINTEXT_KEYS
