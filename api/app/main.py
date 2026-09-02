from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.core.config import get_settings
from app.routers import (
    analysis,
    attachments,
    compare,
    evaluation,
    experiments,
    literature,
    measurements,
    projects,
    revisions,
    templates,
)

settings = get_settings()
app = FastAPI(title=settings.app_name, version="0.1.0")
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/api/v1/health", tags=["health"])
def health() -> dict[str, str]:
    return {"status": "healthy"}


app.include_router(projects.router, prefix="/api/v1")
app.include_router(templates.router, prefix="/api/v1")
app.include_router(experiments.router, prefix="/api/v1")
app.include_router(attachments.router, prefix="/api/v1")
app.include_router(revisions.router, prefix="/api/v1")
app.include_router(measurements.router, prefix="/api/v1")
app.include_router(compare.router, prefix="/api/v1")
app.include_router(literature.router, prefix="/api/v1")
app.include_router(analysis.router, prefix="/api/v1")
app.include_router(evaluation.router, prefix="/api/v1")


@app.on_event("startup")
def interrupt_stale_evaluations() -> None:
    # v0.1 supports exactly one API process/worker. Never claim ownership across workers.
    from app.db import SessionLocal
    from app.evaluation_service import mark_interrupted_runs

    try:
        with SessionLocal() as db:
            mark_interrupted_runs(db)
    except Exception:
        # Test clients and local bootstraps may create the schema after app import. Runtime
        # readiness is still reported by /health; the next process with a reachable DB retries.
        return
