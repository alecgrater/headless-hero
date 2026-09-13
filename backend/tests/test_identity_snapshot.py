"""Tests for the portable visual identity snapshot.

Covers the two properties that matter: no credential can reach the committed
snapshot, and a fresh clone's database ends up matching it.
"""

from datetime import datetime, timezone

import pytest
from sqlalchemy.pool import StaticPool
from sqlmodel import Session, SQLModel, create_engine, select

from models.brand import BrandProfile
from models.settings import AppSetting
from models.style_preset import StylePreset
from models.style_preset_character import StylePresetCharacter
from pipeline import identity

# Every credential currently living in app_settings. None may be exported.
CREDENTIAL_KEYS = [
    "ANTHROPIC_API_KEY",
    "OPENAI_API_KEY",
    "GOOGLE_AI_KEY",
    "ELEVENLABS_API_KEY",
    "FAL_API_KEY",
    "REPLICATE_API_TOKEN",
    "GOOGLE_CLIENT_ID",
    "GOOGLE_CLIENT_SECRET",
    "TWITCH_CLIENT_ID",
    "TWITCH_CLIENT_SECRET",
    "NEWS_API_KEY",
    "PEXELS_API_KEY",
    "YOUTUBE_API_KEY",
    "GITHUB_CONTENTS_TOKEN",
]

# Machine-specific paths and Local Mode settings, which depend on weights and
# daemons installed on this machine only.
MACHINE_SPECIFIC_KEYS = [
    "DOWNLOADS_DIR",
    "EXPORT_FOLDER",
    "LOCAL_MODELS_ENABLED",
    "LOCAL_TEXT_MODE",
    "LOCAL_TEXT_MODEL",
    "LOCAL_TEXT_FAST_MODEL",
    "LOCAL_IMAGE_MODE",
    "LOCAL_IMAGE_MODEL",
    "LOCAL_VOICE_MODE",
    "LOCAL_VOICE_MODEL",
    "LOCAL_VOICE_ID",
    "LOCAL_COMFYUI_URL",
    "LOCAL_TTS_URL",
]

EXPORTABLE_KEYS = [
    "ACTIVE_STYLE_PRESET_ID",
    "ACTIVE_STYLE_PRESET_CHARACTER_ID_abc-123",
    "SUBTITLE_COVERAGE_MODE",
    "SUBTITLE_STYLE_KINETIC_ENABLED",
    "ELEVENLABS_STABILITY",
    "ELEVENLABS_TTS_MODEL",
    "SCRIPT_MODEL",
    "SCRIPT_LLM_PROVIDER",
    "OPENAI_REASONING_EFFORT_SCRIPT",
    "VISUAL_CANVAS_COLOR_PALETTE",
    "AI_VIDEO_SCENES_PER_SEGMENT",
    "LIFE_AS_A_TARGET_SCENE_SECONDS",
]


@pytest.fixture
def identity_engine(tmp_path, monkeypatch):
    """Isolated engine plus an isolated identity.json, never the dev database."""
    monkeypatch.setattr(identity, "identity_path", lambda: tmp_path / "identity.json")
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    SQLModel.metadata.create_all(engine)
    return engine


def _seed_rows(session: Session) -> None:
    session.add(
        StylePreset(
            id="preset-1",
            name="House Style",
            prompt="flat vector, warm palette",
            created_at=datetime(2026, 1, 2, 3, 4, 5, tzinfo=timezone.utc),
        )
    )
    session.add(
        StylePresetCharacter(
            id="char-1",
            style_preset_id="preset-1",
            name="Mara",
            appearance="short dark hair, green jacket",
            vibe="calm",
            reference_image_url="/static/x.png",
            cutout_image_url="/static/x.cutout.png",
            created_at=datetime(2026, 1, 2, 3, 4, 6, tzinfo=timezone.utc),
        )
    )
    session.add(BrandProfile(name="Headless Hero", voice_id="voice-abc"))
    for key in CREDENTIAL_KEYS + MACHINE_SPECIFIC_KEYS:
        session.add(AppSetting(key=key, value="super-secret-value"))
    session.add(AppSetting(key="ACTIVE_STYLE_PRESET_ID", value="preset-1"))
    session.add(AppSetting(key="SCRIPT_MODEL", value="claude-sonnet-4-6"))
    session.add(AppSetting(key="_yt_channel_id:Vsauce", value="UC6nSF"))
    session.commit()


# --- Allowlist ---

@pytest.mark.parametrize("key", CREDENTIAL_KEYS)
def test_credentials_are_never_exportable(key: str) -> None:
    assert not identity.is_exportable_setting(key)


@pytest.mark.parametrize("key", MACHINE_SPECIFIC_KEYS)
def test_machine_specific_paths_are_not_exportable(key: str) -> None:
    assert not identity.is_exportable_setting(key)


@pytest.mark.parametrize("key", EXPORTABLE_KEYS)
def test_identity_settings_are_exportable(key: str) -> None:
    assert identity.is_exportable_setting(key)


@pytest.mark.parametrize(
    "key",
    ["SOME_NEW_API_KEY", "VENDOR_SECRET", "SERVICE_TOKEN", "DB_PASSWORD", "X_CREDENTIAL"],
)
def test_secret_shaped_keys_are_rejected(key: str) -> None:
    """Safety net for a credential wrongly added to the allowlist later."""
    assert not identity.is_exportable_setting(key)


def test_unknown_keys_are_excluded_by_default() -> None:
    assert not identity.is_exportable_setting("SOME_FUTURE_SETTING")
    assert not identity.is_exportable_setting("_yt_channel_id:Vsauce")


# --- Snapshot ---

def test_snapshot_excludes_secrets(identity_engine) -> None:
    with Session(identity_engine) as session:
        _seed_rows(session)
        snapshot = identity.build_snapshot(session)

    exported = snapshot["settings"]
    for key in CREDENTIAL_KEYS + MACHINE_SPECIFIC_KEYS:
        assert key not in exported
    assert "super-secret-value" not in str(snapshot)
    assert exported["ACTIVE_STYLE_PRESET_ID"] == "preset-1"
    assert exported["SCRIPT_MODEL"] == "claude-sonnet-4-6"


def test_snapshot_round_trips_into_an_empty_database(identity_engine, tmp_path) -> None:
    with Session(identity_engine) as session:
        _seed_rows(session)
        identity.write_snapshot(session)

    assert (tmp_path / "identity.json").exists()

    fresh = create_engine(
        "sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool
    )
    SQLModel.metadata.create_all(fresh)
    with Session(fresh) as session:
        session.add(BrandProfile(name="placeholder"))
        session.commit()
        identity.seed_from_snapshot(session)

        preset = session.get(StylePreset, "preset-1")
        assert preset is not None
        assert preset.name == "House Style"
        # SQLite columns are naive; the snapshot carries an explicit UTC offset,
        # so what must survive is the instant, not the tzinfo object.
        assert preset.created_at.replace(tzinfo=timezone.utc) == datetime(
            2026, 1, 2, 3, 4, 5, tzinfo=timezone.utc
        )

        character = session.get(StylePresetCharacter, "char-1")
        assert character is not None
        assert character.appearance == "short dark hair, green jacket"

        assert session.get(AppSetting, "ACTIVE_STYLE_PRESET_ID").value == "preset-1"
        assert session.get(AppSetting, "ANTHROPIC_API_KEY") is None

        brand = session.exec(select(BrandProfile)).first()
        assert brand.name == "Headless Hero"
        assert brand.voice_id == "voice-abc"


def test_seeding_is_idempotent(identity_engine) -> None:
    with Session(identity_engine) as session:
        _seed_rows(session)
        identity.write_snapshot(session)
        identity.seed_from_snapshot(session)
        identity.seed_from_snapshot(session)

        assert len(session.exec(select(StylePreset)).all()) == 1
        assert len(session.exec(select(StylePresetCharacter)).all()) == 1


def test_snapshot_wins_over_local_values(identity_engine) -> None:
    with Session(identity_engine) as session:
        _seed_rows(session)
        identity.write_snapshot(session)

        session.get(StylePreset, "preset-1").name = "Locally Renamed"
        session.get(AppSetting, "SCRIPT_MODEL").value = "locally-changed"
        session.commit()

        identity.seed_from_snapshot(session)

        assert session.get(StylePreset, "preset-1").name == "House Style"
        assert session.get(AppSetting, "SCRIPT_MODEL").value == "claude-sonnet-4-6"


def test_seeding_does_not_delete_local_rows(identity_engine) -> None:
    with Session(identity_engine) as session:
        _seed_rows(session)
        identity.write_snapshot(session)

        session.add(StylePreset(id="local-only", name="Local", prompt="p"))
        session.commit()

        identity.seed_from_snapshot(session)
        assert session.get(StylePreset, "local-only") is not None


def test_snapshot_rejects_a_smuggled_secret(identity_engine, tmp_path) -> None:
    """A hand-edited snapshot cannot inject a credential into app_settings."""
    import json

    (tmp_path / "identity.json").write_text(
        json.dumps(
            {
                "version": identity.SNAPSHOT_VERSION,
                "style_presets": [],
                "style_preset_characters": [],
                "brand_profile": None,
                "settings": {"ANTHROPIC_API_KEY": "leaked"},
            }
        ),
        encoding="utf-8",
    )
    with Session(identity_engine) as session:
        identity.seed_from_snapshot(session)
        assert session.get(AppSetting, "ANTHROPIC_API_KEY") is None


def test_empty_brand_fields_do_not_blank_local_values(identity_engine, tmp_path) -> None:
    """A snapshot taken before a field was filled must not wipe it on a clone."""
    import json

    (tmp_path / "identity.json").write_text(
        json.dumps(
            {
                "version": identity.SNAPSHOT_VERSION,
                "style_presets": [],
                "style_preset_characters": [],
                "brand_profile": {"name": "", "voice_id": "voice-abc"},
                "settings": {},
            }
        ),
        encoding="utf-8",
    )
    with Session(identity_engine) as session:
        session.add(BrandProfile(name="Headless Hero"))
        session.commit()

        identity.seed_from_snapshot(session)

        brand = session.exec(select(BrandProfile)).first()
        assert brand.name == "Headless Hero"
        assert brand.voice_id == "voice-abc"


# --- The artifact that actually ships ---

def test_committed_snapshot_carries_no_unexportable_setting() -> None:
    """Guard the real data/identity.json, not just the function that writes it.

    Every other allowlist test exercises is_exportable_setting in isolation; a
    hand-edit or a future write_snapshot regression could still publish a
    credential to a public repo with all of them green.
    """
    import json
    from pathlib import Path

    committed = Path(__file__).resolve().parents[2] / "data" / "identity.json"
    if not committed.exists():
        pytest.skip("no committed identity snapshot in this checkout")

    payload = json.loads(committed.read_text(encoding="utf-8"))
    assert payload["version"] == identity.SNAPSHOT_VERSION

    leaked = [k for k in payload.get("settings", {}) if not identity.is_exportable_setting(k)]
    assert not leaked, f"committed snapshot exports keys it must not: {leaked}"


# --- Degraded input ---

def test_missing_snapshot_is_a_no_op(identity_engine) -> None:
    with Session(identity_engine) as session:
        identity.seed_from_snapshot(session)  # must not raise


def test_malformed_snapshot_is_a_no_op(identity_engine, tmp_path) -> None:
    (tmp_path / "identity.json").write_text("{not json", encoding="utf-8")
    with Session(identity_engine) as session:
        identity.seed_from_snapshot(session)  # must not raise


def test_unsupported_version_is_ignored(identity_engine, tmp_path) -> None:
    import json

    (tmp_path / "identity.json").write_text(
        json.dumps({"version": 99, "style_presets": [{"id": "x", "name": "x"}]}),
        encoding="utf-8",
    )
    with Session(identity_engine) as session:
        identity.seed_from_snapshot(session)
        assert session.get(StylePreset, "x") is None
