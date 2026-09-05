from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.core.config import get_settings
from app.db import SessionLocal
from app.routers.objects import router as object_graph_router
from app.seed import ensure_default_object_types

settings = get_settings()


@asynccontextmanager
async def lifespan(_app: FastAPI):
    # The type catalog is application metadata, not synthetic research seed data.
    # Keeping it outside Alembic lets a migrations-only database support first run.
    with SessionLocal() as db:
        ensure_default_object_types(db)
    yield


app = FastAPI(title=settings.app_name, version="0.3.0", lifespan=lifespan)
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/api/v1/health", tags=["health"])
def health() -> dict[str, str]:
    return {"status": "healthy", "version": "0.3.0"}


app.include_router(object_graph_router, prefix="/api/v1")
