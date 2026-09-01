from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.db import get_db
from app.models import Experiment, ExperimentRevision
from app.schemas import RevisionCreate, RevisionOut
from app.services import create_revision

router = APIRouter(tags=["revisions"])


@router.post("/experiments/{experiment_id}/revisions", response_model=RevisionOut, status_code=201)
def create_revision_route(
    experiment_id: uuid.UUID, payload: RevisionCreate, db: Session = Depends(get_db)
) -> ExperimentRevision:
    try:
        return create_revision(db, experiment_id, payload.change_note)
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.get("/experiments/{experiment_id}/revisions", response_model=list[RevisionOut])
def list_revisions(experiment_id: uuid.UUID, db: Session = Depends(get_db)) -> list[ExperimentRevision]:
    if db.get(Experiment, experiment_id) is None:
        raise HTTPException(status_code=404, detail="experiment not found")
    return list(
        db.scalars(
            select(ExperimentRevision)
            .where(ExperimentRevision.experiment_id == experiment_id)
            .order_by(ExperimentRevision.revision_number.desc())
        )
    )


@router.get(
    "/experiments/{experiment_id}/revisions/{revision_number}", response_model=RevisionOut
)
def get_revision(
    experiment_id: uuid.UUID, revision_number: int, db: Session = Depends(get_db)
) -> ExperimentRevision:
    revision = db.scalar(
        select(ExperimentRevision)
        .where(
            ExperimentRevision.experiment_id == experiment_id,
            ExperimentRevision.revision_number == revision_number,
        )
        .options(selectinload(ExperimentRevision.experiment))
    )
    if revision is None:
        raise HTTPException(status_code=404, detail="revision not found")
    return revision
