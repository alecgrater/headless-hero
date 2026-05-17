import logging

from sqlmodel import Session, SQLModel, create_engine, select

from config import BALANCED_CLAUDE_MODEL, DATA_DIR, DEFAULT_CLAUDE_MODEL, FAST_CLAUDE_MODEL

logger = logging.getLogger(__name__)

# Store the DB in a `data/` directory next to the backend package
DATA_DIR.mkdir(parents=True, exist_ok=True)
_db_path = DATA_DIR / "db.sqlite"

engine = create_engine(f"sqlite:///{_db_path}", echo=False)

def init_db() -> None:
    """Create all tables. Safe to call repeatedly."""
    logger.info("Initializing database")
    SQLModel.metadata.create_all(engine)
    _migrate_add_eli_position()
    _migrate_script_model_default()
    _migrate_llm_task_route_defaults()
    _migrate_add_script_id_to_api_usage()
    _migrate_add_scene_count_to_generation_durations()
    _migrate_add_export_folder_to_publish_records()
    _migrate_add_short_upload_fields_to_publish_records()
    _migrate_postits_add_status_source()
    _migrate_postits_to_ideas()
    logger.info("Database ready")

def ensure_default_brand() -> None:
    """Ensure exactly one default brand exists. Create if missing."""
    from models.brand import BrandProfile

    with Session(engine) as session:
        existing = session.exec(select(BrandProfile)).first()
        if not existing:
            brand = BrandProfile(name="Headless Hero")
            session.add(brand)
            session.commit()
            logger.info("Created default brand: %s", brand.id)
        else:
            logger.info("Default brand exists: %s", existing.id)

def get_default_brand_id(session: Session) -> str:
    """Return the single default brand's ID."""
    from models.brand import BrandProfile

    brand = session.exec(select(BrandProfile)).first()
    if not brand:
        raise RuntimeError("No default brand found — ensure_default_brand() must run first")
    return brand.id

def get_session():
    """FastAPI dependency that yields a DB session."""
    with Session(engine) as session:
        yield session


def _migrate_add_eli_position() -> None:
    """Add eli_position_json column to brand_profiles if missing."""
    import sqlite3

    conn = sqlite3.connect(str(_db_path))
    try:
        cursor = conn.execute("PRAGMA table_info(brand_profiles)")
        columns = {row[1] for row in cursor.fetchall()}
        if "eli_position_json" not in columns:
            conn.execute("ALTER TABLE brand_profiles ADD COLUMN eli_position_json TEXT DEFAULT ''")
            conn.commit()
            logger.info("Migrated: added eli_position_json to brand_profiles")
    finally:
        conn.close()


def _migrate_add_script_id_to_api_usage() -> None:
    """Add script_id column to api_usage if missing."""
    import sqlite3

    conn = sqlite3.connect(str(_db_path))
    try:
        cursor = conn.execute("PRAGMA table_info(api_usage)")
        columns = {row[1] for row in cursor.fetchall()}
        if "script_id" not in columns:
            conn.execute("ALTER TABLE api_usage ADD COLUMN script_id TEXT DEFAULT NULL")
            conn.execute("CREATE INDEX IF NOT EXISTS ix_api_usage_script_id ON api_usage(script_id)")
            conn.commit()
            logger.info("Migrated: added script_id to api_usage")
    finally:
        conn.close()


def _migrate_script_model_default() -> None:
    """Clear stale script LLM defaults so the current Claude route takes effect."""
    from models.settings import AppSetting

    stale_script_models = {
        *_stale_anthropic_model_upgrades().keys(),
        "gpt-5.5",
    }

    with Session(engine) as session:
        changed: list[str] = []

        provider_setting = session.get(AppSetting, "SCRIPT_LLM_PROVIDER")
        model_setting = session.get(AppSetting, "SCRIPT_MODEL")

        model_value = model_setting.value if model_setting else ""
        has_stale_script_model = model_value in stale_script_models

        if provider_setting and provider_setting.value == "":
            provider_setting.value = "anthropic"
            session.add(provider_setting)
            changed.append("SCRIPT_LLM_PROVIDER")
        elif provider_setting and provider_setting.value == "openai" and has_stale_script_model:
            provider_setting.value = "anthropic"
            session.add(provider_setting)
            changed.append("SCRIPT_LLM_PROVIDER")

        if model_setting and has_stale_script_model:
            model_setting.value = DEFAULT_CLAUDE_MODEL
            session.add(model_setting)
            changed.append("SCRIPT_MODEL")

        if changed:
            session.commit()
            logger.info("Migrated: refreshed stale script LLM defaults: %s", ", ".join(changed))


def _migrate_llm_task_route_defaults() -> None:
    """Seed missing per-task LLM routing defaults without overwriting user choices."""
    from integrations.llm_client import LLM_TASKS
    from models.settings import AppSetting

    stale_anthropic_models = _stale_anthropic_model_upgrades()

    with Session(engine) as session:
        seeded: list[str] = []
        refreshed: list[str] = []
        for task in LLM_TASKS.values():
            provider_key = task["provider_key"]
            model_key = task["model_key"]
            default_provider = task["default_provider"]
            default_model = "qwen3:14b" if default_provider == "ollama" else task[f"default_{default_provider}_model"]

            provider_setting = session.get(AppSetting, provider_key)
            model_setting = session.get(AppSetting, model_key)
            had_legacy_blank_provider = bool(provider_setting and provider_setting.value == "")

            if not provider_setting:
                session.add(AppSetting(key=provider_key, value=default_provider))
                seeded.append(provider_key)
            elif had_legacy_blank_provider:
                provider_setting.value = default_provider
                session.add(provider_setting)
                seeded.append(provider_key)

            if not model_setting:
                session.add(AppSetting(key=model_key, value=default_model))
                seeded.append(model_key)
            elif had_legacy_blank_provider:
                model_setting.value = default_model
                session.add(model_setting)
                seeded.append(model_key)
            elif model_setting.value in stale_anthropic_models:
                model_setting.value = stale_anthropic_models[model_setting.value]
                session.add(model_setting)
                refreshed.append(model_key)

        if seeded or refreshed:
            session.commit()
            details = []
            if seeded:
                details.append(f"seeded: {', '.join(seeded)}")
            if refreshed:
                details.append(f"refreshed stale Claude models: {', '.join(refreshed)}")
            logger.info("Migrated: LLM task route defaults: %s", "; ".join(details))


def _stale_anthropic_model_upgrades() -> dict[str, str]:
    """Map retired Claude IDs to the current tier-equivalent API model IDs."""
    return {
        "claude-opus-4-1-20250805": DEFAULT_CLAUDE_MODEL,
        "claude-opus-4-20250514": DEFAULT_CLAUDE_MODEL,
        "claude-sonnet-4-20250514": BALANCED_CLAUDE_MODEL,
        "claude-3-7-sonnet-20250219": BALANCED_CLAUDE_MODEL,
        "claude-3-5-haiku-20241022": FAST_CLAUDE_MODEL,
        "claude-haiku-4-5": FAST_CLAUDE_MODEL,
        "anthropic.claude-opus-4-6-v1": DEFAULT_CLAUDE_MODEL,
        "anthropic.claude-opus-4-1-20250805-v1:0": DEFAULT_CLAUDE_MODEL,
        "anthropic.claude-opus-4-20250514-v1:0": DEFAULT_CLAUDE_MODEL,
        "anthropic.claude-sonnet-4-6": BALANCED_CLAUDE_MODEL,
        "anthropic.claude-sonnet-4-5-20250929-v1:0": BALANCED_CLAUDE_MODEL,
        "anthropic.claude-sonnet-4-20250514-v1:0": BALANCED_CLAUDE_MODEL,
        "anthropic.claude-3-7-sonnet-20250219-v1:0": BALANCED_CLAUDE_MODEL,
        "anthropic.claude-haiku-4-5-20251001-v1:0": FAST_CLAUDE_MODEL,
        "anthropic.claude-3-5-haiku-20241022-v1:0": FAST_CLAUDE_MODEL,
    }


def _migrate_add_scene_count_to_generation_durations() -> None:
    """Add scene_count column to generation_durations if missing."""
    import sqlite3

    conn = sqlite3.connect(str(_db_path))
    try:
        cursor = conn.execute("PRAGMA table_info(generation_durations)")
        columns = {row[1] for row in cursor.fetchall()}
        if "scene_count" not in columns:
            conn.execute("ALTER TABLE generation_durations ADD COLUMN scene_count INTEGER DEFAULT NULL")
            conn.commit()
            logger.info("Migrated: added scene_count to generation_durations")
    finally:
        conn.close()


def _migrate_add_export_folder_to_publish_records() -> None:
    """Add export_folder column to publish_records if missing."""
    import sqlite3

    conn = sqlite3.connect(str(_db_path))
    try:
        cursor = conn.execute("PRAGMA table_info(publish_records)")
        columns = {row[1] for row in cursor.fetchall()}
        if "export_folder" not in columns:
            conn.execute("ALTER TABLE publish_records ADD COLUMN export_folder TEXT DEFAULT ''")
            conn.commit()
            logger.info("Migrated: added export_folder to publish_records")
    finally:
        conn.close()


def _migrate_add_short_upload_fields_to_publish_records() -> None:
    """Add per-asset publish tracking columns to publish_records if missing."""
    import sqlite3

    conn = sqlite3.connect(str(_db_path))
    try:
        cursor = conn.execute("PRAGMA table_info(publish_records)")
        columns = {row[1] for row in cursor.fetchall()}
        added = False
        if "asset_kind" not in columns:
            conn.execute("ALTER TABLE publish_records ADD COLUMN asset_kind TEXT DEFAULT 'long_form'")
            conn.execute("CREATE INDEX IF NOT EXISTS ix_publish_records_asset_kind ON publish_records(asset_kind)")
            added = True
        if "short_index" not in columns:
            conn.execute("ALTER TABLE publish_records ADD COLUMN short_index INTEGER DEFAULT NULL")
            conn.execute("CREATE INDEX IF NOT EXISTS ix_publish_records_short_index ON publish_records(short_index)")
            added = True
        if "upload_batch_id" not in columns:
            conn.execute("ALTER TABLE publish_records ADD COLUMN upload_batch_id TEXT DEFAULT ''")
            conn.execute("CREATE INDEX IF NOT EXISTS ix_publish_records_upload_batch_id ON publish_records(upload_batch_id)")
            added = True
        if added:
            conn.commit()
            logger.info("Migrated: added short upload fields to publish_records")
    finally:
        conn.close()


def _migrate_postits_add_status_source() -> None:
    """Add status and source columns to postits if missing."""
    import sqlite3

    conn = sqlite3.connect(str(_db_path))
    try:
        tables = {row[0] for row in conn.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()}
        if "postits" not in tables:
            return
        cursor = conn.execute("PRAGMA table_info(postits)")
        columns = {row[1] for row in cursor.fetchall()}
        if "status" not in columns:
            conn.execute("ALTER TABLE postits ADD COLUMN status TEXT DEFAULT 'idea'")
            logger.info("Migrated: added status to postits")
        if "source" not in columns:
            conn.execute("ALTER TABLE postits ADD COLUMN source TEXT DEFAULT 'manual'")
            logger.info("Migrated: added source to postits")
        conn.commit()
    finally:
        conn.close()


def _migrate_postits_to_ideas() -> None:
    """Rename postits table to ideas and add hook-related columns."""
    import sqlite3

    conn = sqlite3.connect(str(_db_path))
    try:
        tables = {row[0] for row in conn.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()}

        if "ideas" in tables:
            # Already migrated — just ensure new columns exist
            cursor = conn.execute("PRAGMA table_info(ideas)")
            columns = {row[1] for row in cursor.fetchall()}
            new_cols = {
                "description": "TEXT DEFAULT ''",
                "category": "TEXT DEFAULT ''",
                "cold_open_status": "TEXT DEFAULT 'pending'",
                "cold_open_job_id": "TEXT DEFAULT ''",
                "cold_open_variants_json": "TEXT DEFAULT ''",
                "selected_hook_json": "TEXT DEFAULT ''",
                "hook_score": "INTEGER",
                "hook_score_json": "TEXT DEFAULT ''",
            }
            for col, typedef in new_cols.items():
                if col not in columns:
                    conn.execute(f"ALTER TABLE ideas ADD COLUMN {col} {typedef}")
                    logger.info("Migrated: added %s to ideas", col)
            conn.commit()
            return

        if "postits" not in tables:
            return

        conn.execute("ALTER TABLE postits RENAME TO ideas")
        logger.info("Migrated: renamed postits → ideas")

        cursor = conn.execute("PRAGMA table_info(ideas)")
        columns = {row[1] for row in cursor.fetchall()}
        new_cols = {
            "description": "TEXT DEFAULT ''",
            "category": "TEXT DEFAULT ''",
            "cold_open_status": "TEXT DEFAULT 'pending'",
            "cold_open_job_id": "TEXT DEFAULT ''",
            "cold_open_variants_json": "TEXT DEFAULT ''",
            "selected_hook_json": "TEXT DEFAULT ''",
            "hook_score": "INTEGER",
            "hook_score_json": "TEXT DEFAULT ''",
        }
        for col, typedef in new_cols.items():
            if col not in columns:
                conn.execute(f"ALTER TABLE ideas ADD COLUMN {col} {typedef}")
                logger.info("Migrated: added %s to ideas", col)
        conn.commit()
    finally:
        conn.close()
