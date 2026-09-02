from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.db import get_db
from app.models import Experiment, ExperimentProvenanceLink, Project
from app.schemas import (
    CloneRequest,
    ExperimentCreate,
    ExperimentOut,
    ExperimentProvenanceOut,
    ExperimentUpdate,
)
from app.services import clone_experiment, create_experiment, update_experiment

router = APIRouter(tags=["experiments"])


def _get_experiment(db: Session, experiment_id: uuid.UUID) -> Experiment | None:
    return db.scalar(
        select(Experiment)
        .where(Experiment.id == experiment_id)
        .options(selectinload(Experiment.template))
    )


@router.get("/experiments", response_model=list[ExperimentOut])
def list_all_experiments(db: Session = Depends(get_db)) -> list[Experiment]:
    return list(db.scalars(select(Experiment).order_by(Experiment.updated_at.desc())))


@router.get("/projects/{project_id}/experiments", response_model=list[ExperimentOut])
def list_experiments(project_id: uuid.UUID, db: Session = Depends(get_db)) -> list[Experiment]:
    if db.get(Project, project_id) is None:
        raise HTTPException(status_code=404, detail="project not found")
    return list(
        db.scalars(
            select(Experiment)
            .where(Experiment.project_id == project_id)
            .order_by(Experiment.updated_at.desc())
        )
    )


@router.post("/projects/{project_id}/experiments", response_model=ExperimentOut, status_code=201)
def create_experiment_route(
    project_id: uuid.UUID, payload: ExperimentCreate, db: Session = Depends(get_db)
) -> Experiment:
    project = db.get(Project, project_id)
    if project is None:
        raise HTTPException(status_code=404, detail="project not found")
    try:
        return create_experiment(db, project, payload)
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ValueError as exc:
        status_code = (
            409
            if str(exc)
            in {
                "suggestion_review_changed",
                "suggestion_hash_mismatch",
                "suggestion_base_experiment_changed",
                "suggestion_template_changed",
                "suggestion_project_or_template_changed",
            }
            else 422
        )
        raise HTTPException(status_code=status_code, detail=str(exc)) from exc


@router.get("/experiments/{experiment_id}", response_model=ExperimentOut)
def get_experiment(experiment_id: uuid.UUID, db: Session = Depends(get_db)) -> Experiment:
    experiment = _get_experiment(db, experiment_id)
    if experiment is None:
        raise HTTPException(status_code=404, detail="experiment not found")
    return experiment


@router.get("/experiments/{experiment_id}/provenance", response_model=ExperimentProvenanceOut)
def get_experiment_provenance(
    experiment_id: uuid.UUID, db: Session = Depends(get_db)
) -> ExperimentProvenanceLink:
    if db.get(Experiment, experiment_id) is None:
        raise HTTPException(status_code=404, detail="experiment not found")
    link = db.scalar(
        select(ExperimentProvenanceLink).where(
            ExperimentProvenanceLink.experiment_id == experiment_id
        )
    )
    if link is None:
        raise HTTPException(status_code=404, detail="experiment provenance not found")
    return link


@router.patch("/experiments/{experiment_id}", response_model=ExperimentOut)
def patch_experiment(
    experiment_id: uuid.UUID, payload: ExperimentUpdate, db: Session = Depends(get_db)
) -> Experiment:
    experiment = _get_experiment(db, experiment_id)
    if experiment is None:
        raise HTTPException(status_code=404, detail="experiment not found")
    try:
        return update_experiment(db, experiment, payload)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


@router.post("/experiments/{experiment_id}/clone", response_model=ExperimentOut, status_code=201)
def clone_experiment_route(
    experiment_id: uuid.UUID, payload: CloneRequest, db: Session = Depends(get_db)
) -> Experiment:
    experiment = _get_experiment(db, experiment_id)
    if experiment is None:
        raise HTTPException(status_code=404, detail="experiment not found")
    return clone_experiment(db, experiment, payload)
