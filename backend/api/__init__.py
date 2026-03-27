from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from api.brands import router as brands_router
from api.database import init_db
from api.ideas import router as ideas_router
from models.brand import BrandProfile as _BrandProfile  # noqa: F401 — register table


@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()
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


@app.get("/api/health")
async def health():
    return {"status": "ok", "version": "0.1.0"}
