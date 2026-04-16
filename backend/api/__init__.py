import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from sqlmodel import Session

from api.brands import router as brands_router
from database import init_db, ensure_default_brand
from database import engine as _db_engine
from api.fx import router as fx_router
from api.ideas import router as ideas_router
from api.publish import router as publish_router
from api.render import router as render_router
from api.scripts import router as scripts_router
from api.generation import router as generation_router
from api.seo import router as seo_router
from api.character import router as character_router
from api.settings import router as settings_router
from api.thumbnail_references import router as thumbnail_references_router
from api.thumbnail import router as thumbnail_router
from api.trending import router as trending_router
from api.visuals import router as visuals_router
from api.voiceover import router as voiceover_router
from dev.log_handler import DevLog as _DevLog  # noqa: F401 — register table
from dev.log_handler import SQLiteLogHandler, prune_old_logs
from models.brand import BrandProfile as _BrandProfile  # noqa: F401 — register table
from models.credential import PlatformCredential as _PlatformCredential  # noqa: F401 — register table
from models.publish import PublishRecord as _PublishRecord  # noqa: F401 — register table
from models.script import Script as _Script  # noqa: F401 — register table
from models.generation_duration import GenerationDuration as _GenerationDuration  # noqa: F401 — register table
from models.settings import AppSetting as _AppSetting  # noqa: F401 — register table
from models.api_usage import ApiUsage as _ApiUsage  # noqa: F401 — register table
from models.trending import TrendingTopic as _TrendingTopic  # noqa: F401 — register table
from models.content_profile import ContentProfile as _ContentProfile  # noqa: F401 — register table

from config import DATA_DIR

@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()
    ensure_default_brand()
    # Install dev dashboard log handler
    prune_old_logs(_db_engine)
    log_handler = SQLiteLogHandler(_db_engine)
    log_handler.setLevel(logging.DEBUG)
    root_logger = logging.getLogger()
    root_logger.addHandler(log_handler)
    if root_logger.level > logging.DEBUG:
        root_logger.setLevel(logging.DEBUG)
    # Load saved API keys into environment
    from api.settings import load_keys_into_env
    with Session(_db_engine) as session:
        load_keys_into_env(session)
    # Ensure projects directory exists for static file serving
    projects_dir = DATA_DIR / "projects"
    projects_dir.mkdir(parents=True, exist_ok=True)
    # Ensure character frames directory exists
    character_dir = DATA_DIR / "character" / "frames"
    character_dir.mkdir(parents=True, exist_ok=True)
    thumb_ref_dir = DATA_DIR / "character" / "thumbnail_references"
    thumb_ref_dir.mkdir(parents=True, exist_ok=True)
    yield

app = FastAPI(title="Headless Hero", version="0.1.0", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Dev dashboard
from dev.routes import router as _dev_router
app.include_router(_dev_router)

# Core routers
app.include_router(brands_router)
app.include_router(fx_router)
app.include_router(ideas_router)
app.include_router(scripts_router)
app.include_router(visuals_router)
app.include_router(voiceover_router)
app.include_router(render_router)
app.include_router(publish_router)
app.include_router(thumbnail_router)
app.include_router(generation_router)
app.include_router(seo_router)
app.include_router(settings_router)
app.include_router(character_router)
app.include_router(thumbnail_references_router)
app.include_router(trending_router)

# Import modifiers package (no dynamic routers remaining)
import pipeline.modifiers  # noqa: F401

# Serve generated images as static files
_projects_dir = DATA_DIR / "projects"
_projects_dir.mkdir(parents=True, exist_ok=True)
app.mount("/static/projects", StaticFiles(directory=str(_projects_dir)), name="project-assets")

_character_dir = DATA_DIR / "character"
_character_dir.mkdir(parents=True, exist_ok=True)
app.mount("/static/character", StaticFiles(directory=str(_character_dir)), name="character-assets")

@app.get("/api/health")
async def health():
    return {"status": "ok", "version": "0.1.0"}
