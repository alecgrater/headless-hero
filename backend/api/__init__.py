from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from api.brands import router as brands_router
from api.database import init_db
from api.ideas import router as ideas_router
from api.publish import router as publish_router
from api.render import router as render_router
from api.scripts import router as scripts_router
from api.seo import router as seo_router
from api.thumbnail import router as thumbnail_router
from api.visuals import router as visuals_router
from api.voiceover import router as voiceover_router
from models.brand import BrandProfile as _BrandProfile  # noqa: F401 — register table
from models.credential import PlatformCredential as _PlatformCredential  # noqa: F401 — register table
from models.publish import PublishRecord as _PublishRecord  # noqa: F401 — register table
from models.script import Script as _Script  # noqa: F401 — register table

import os
_data_dir = Path(os.environ.get("YAM_DATA_DIR", Path(__file__).resolve().parents[2] / "data"))

@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()
    # Ensure projects directory exists for static file serving
    projects_dir = _data_dir / "projects"
    projects_dir.mkdir(parents=True, exist_ok=True)
    yield

app = FastAPI(title="YouTube AI Machine", version="0.1.0", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(brands_router)
app.include_router(ideas_router)
app.include_router(scripts_router)
app.include_router(visuals_router)
app.include_router(voiceover_router)
app.include_router(render_router)
app.include_router(publish_router)
app.include_router(thumbnail_router)
app.include_router(seo_router)

# Serve generated images as static files
_projects_dir = _data_dir / "projects"
_projects_dir.mkdir(parents=True, exist_ok=True)
app.mount("/static/projects", StaticFiles(directory=str(_projects_dir)), name="project-assets")

@app.get("/api/health")
async def health():
    return {"status": "ok", "version": "0.1.0"}
