from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import or_, select
from sqlalchemy.orm import Session, selectinload

from app.db import get_db
from app.literature_service import (
    create_evidence,
    create_link,
    create_literature,
    literature_out_values,
    update_link,
    update_literature,
    withdraw_evidence,
)
from app.models import (
    EvidenceRecord,
    Experiment,
    ExperimentLiteratureLink,
    LiteratureRecord,
    Project,
)
from app.schemas import (
    EvidenceCreate,
    EvidenceOut,
    EvidenceWithdrawRequest,
    LiteratureCreate,
    LiteratureLinkCreate,
    LiteratureLinkOut,
    LiteratureLinkUpdate,
    LiteratureOut,
    LiteratureUpdate,
)

router = APIRouter(tags=["literature", "evidence"])


def _literature(item: LiteratureRecord) -> LiteratureOut:
    return LiteratureOut.model_validate(literature_out_values(item))


def _link(item: ExperimentLiteratureLink) -> LiteratureLinkOut:
    return LiteratureLinkOut(
        id=item.id,
        experiment_id=item.experiment_id,
        literature_id=item.literature_id,
        relationship_type=item.relationship_type,
        notes=item.notes,
        created_at=item.created_at,
        literature=_literature(item.literature) if item.literature else None,
    )


def _evidence(item: EvidenceRecord) -> EvidenceOut:
    return EvidenceOut.model_validate(item, from_attributes=True)


@router.get("/projects/{project_id}/literature", response_model=list[LiteratureOut])
def list_literature(
    project_id: uuid.UUID,
    q: str | None = Query(default=None, max_length=200),
    publication_year: int | None = Query(default=None, ge=1000, le=3000),
    db: Session = Depends(get_db),
) -> list[LiteratureOut]:
    if db.get(Project, project_id) is None:
        raise HTTPException(status_code=404, detail="project not found")
    query = select(LiteratureRecord).where(LiteratureRecord.project_id == project_id)
    if q:
        term = f"%{q.strip()}%"
        query = query.where(
            or_(LiteratureRecord.title.ilike(term), LiteratureRecord.doi.ilike(term))
        )
    if publication_year is not None:
        query = query.where(LiteratureRecord.publication_year == publication_year)
    rows = db.scalars(query.order_by(LiteratureRecord.updated_at.desc())).all()
    return [_literature(item) for item in rows]


@router.post("/projects/{project_id}/literature", response_model=LiteratureOut, status_code=201)
def post_literature(
    project_id: uuid.UUID, payload: LiteratureCreate, db: Session = Depends(get_db)
) -> LiteratureOut:
    if db.get(Project, project_id) is None:
        raise HTTPException(status_code=404, detail="project not found")
    return _literature(create_literature(db, project_id, payload))


@router.get("/literature/{literature_id}", response_model=LiteratureOut)
def get_literature(literature_id: uuid.UUID, db: Session = Depends(get_db)) -> LiteratureOut:
    item = db.get(LiteratureRecord, literature_id)
    if item is None:
        raise HTTPException(status_code=404, detail="literature record not found")
    return _literature(item)


@router.patch("/literature/{literature_id}", response_model=LiteratureOut)
def patch_literature(
    literature_id: uuid.UUID, payload: LiteratureUpdate, db: Session = Depends(get_db)
) -> LiteratureOut:
    item = db.get(LiteratureRecord, literature_id)
    if item is None:
        raise HTTPException(status_code=404, detail="literature record not found")
    return _literature(update_literature(db, item, payload))


@router.get("/experiments/{experiment_id}/literature-links", response_model=list[LiteratureLinkOut])
def list_links(experiment_id: uuid.UUID, db: Session = Depends(get_db)) -> list[LiteratureLinkOut]:
    if db.get(Experiment, experiment_id) is None:
        raise HTTPException(status_code=404, detail="experiment not found")
    rows = db.scalars(
        select(ExperimentLiteratureLink)
        .where(ExperimentLiteratureLink.experiment_id == experiment_id)
        .options(selectinload(ExperimentLiteratureLink.literature))
    ).all()
    return [_link(item) for item in rows]


@router.post(
    "/experiments/{experiment_id}/literature-links",
    response_model=LiteratureLinkOut,
    status_code=201,
)
def post_link(
    experiment_id: uuid.UUID, payload: LiteratureLinkCreate, db: Session = Depends(get_db)
) -> LiteratureLinkOut:
    experiment = db.get(Experiment, experiment_id)
    if experiment is None:
        raise HTTPException(status_code=404, detail="experiment not found")
    try:
        return _link(create_link(db, experiment, payload))
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc


@router.patch("/experiment-literature-links/{link_id}", response_model=LiteratureLinkOut)
def patch_link(
    link_id: uuid.UUID, payload: LiteratureLinkUpdate, db: Session = Depends(get_db)
) -> LiteratureLinkOut:
    item = db.get(ExperimentLiteratureLink, link_id)
    if item is None:
        raise HTTPException(status_code=404, detail="literature link not found")
    return _link(update_link(db, item, payload))


@router.delete("/experiment-literature-links/{link_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_link(link_id: uuid.UUID, db: Session = Depends(get_db)) -> None:
    item = db.get(ExperimentLiteratureLink, link_id)
    if item is None:
        raise HTTPException(status_code=404, detail="literature link not found")
    db.delete(item)
    db.commit()


@router.get("/projects/{project_id}/evidence", response_model=list[EvidenceOut])
def list_evidence(
    project_id: uuid.UUID,
    context_experiment_id: uuid.UUID | None = None,
    source_type: str | None = None,
    evidence_status: str | None = Query(default=None, alias="status"),
    db: Session = Depends(get_db),
) -> list[EvidenceOut]:
    if db.get(Project, project_id) is None:
        raise HTTPException(status_code=404, detail="project not found")
    query = select(EvidenceRecord).where(EvidenceRecord.project_id == project_id)
    if context_experiment_id:
        query = query.where(EvidenceRecord.context_experiment_id == context_experiment_id)
    if source_type:
        query = query.where(EvidenceRecord.source_type == source_type)
    if evidence_status:
        query = query.where(EvidenceRecord.status == evidence_status)
    return [
        _evidence(item)
        for item in db.scalars(query.order_by(EvidenceRecord.created_at.desc())).all()
    ]


@router.post("/projects/{project_id}/evidence", response_model=EvidenceOut, status_code=201)
def post_evidence(
    project_id: uuid.UUID, payload: EvidenceCreate, db: Session = Depends(get_db)
) -> EvidenceOut:
    if db.get(Project, project_id) is None:
        raise HTTPException(status_code=404, detail="project not found")
    try:
        return _evidence(create_evidence(db, project_id, payload))
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc


@router.get("/evidence/{evidence_id}", response_model=EvidenceOut)
def get_evidence(evidence_id: uuid.UUID, db: Session = Depends(get_db)) -> EvidenceOut:
    item = db.get(EvidenceRecord, evidence_id)
    if item is None:
        raise HTTPException(status_code=404, detail="evidence not found")
    return _evidence(item)


@router.post("/evidence/{evidence_id}/withdraw", response_model=EvidenceOut)
def post_withdraw(
    evidence_id: uuid.UUID, payload: EvidenceWithdrawRequest, db: Session = Depends(get_db)
) -> EvidenceOut:
    item = db.get(EvidenceRecord, evidence_id)
    if item is None:
        raise HTTPException(status_code=404, detail="evidence not found")
    try:
        return _evidence(withdraw_evidence(db, item, payload.reason))
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
