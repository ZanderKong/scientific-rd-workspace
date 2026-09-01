from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.core.config import get_settings
from app.routers import attachments, experiments, projects, revisions, templates

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
