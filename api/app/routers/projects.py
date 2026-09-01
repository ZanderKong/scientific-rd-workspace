from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.db import get_db
from app.models import Experiment, Project
from app.schemas import ProjectCreate, ProjectOut, ProjectUpdate
from app.services import create_project, update_project

router = APIRouter(prefix="/projects", tags=["projects"])


def _project_out(project: Project, count: int) -> ProjectOut:
    return ProjectOut.model_validate({**project.__dict__, "experiment_count": count})


@router.get("", response_model=list[ProjectOut])
def list_projects(db: Session = Depends(get_db)) -> list[ProjectOut]:
    rows = db.execute(
        select(Project, func.count(Experiment.id))
        .outerjoin(Experiment, Experiment.project_id == Project.id)
        .group_by(Project.id)
        .order_by(Project.updated_at.desc())
    ).all()
    return [_project_out(project, count) for project, count in rows]


@router.post("", response_model=ProjectOut, status_code=status.HTTP_201_CREATED)
def create_project_route(payload: ProjectCreate, db: Session = Depends(get_db)) -> ProjectOut:
    project = create_project(db, payload)
    return _project_out(project, 0)


@router.get("/{project_id}", response_model=ProjectOut)
def get_project(project_id: uuid.UUID, db: Session = Depends(get_db)) -> ProjectOut:
    project = db.get(Project, project_id)
    if project is None:
        raise HTTPException(status_code=404, detail="project not found")
    count = db.scalar(select(func.count(Experiment.id)).where(Experiment.project_id == project.id)) or 0
    return _project_out(project, count)


@router.patch("/{project_id}", response_model=ProjectOut)
def patch_project(
    project_id: uuid.UUID, payload: ProjectUpdate, db: Session = Depends(get_db)
) -> ProjectOut:
    project = db.get(Project, project_id)
    if project is None:
        raise HTTPException(status_code=404, detail="project not found")
    return _project_out(update_project(db, project, payload), len(project.experiments))
