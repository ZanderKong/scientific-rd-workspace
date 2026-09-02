from __future__ import annotations

import uuid

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Query, status
from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.core.config import get_settings
from app.db import get_db
from app.evaluation_service import (
    case_out,
    create_evaluation_case,
    create_evaluation_run,
    result_out,
    run_evaluation_background,
    run_out,
)
from app.models import EvaluationCase, EvaluationResult, EvaluationRun
from app.schemas import (
    EvaluationCaseCreate,
    EvaluationCaseOut,
    EvaluationResultOut,
    EvaluationRunCreate,
    EvaluationRunOut,
)

router = APIRouter(tags=["evaluation"])


@router.post(
    "/findings/{finding_id}/evaluation-cases", response_model=EvaluationCaseOut, status_code=201
)
def create_bad_case(
    finding_id: uuid.UUID,
    payload: EvaluationCaseCreate,
    db: Session = Depends(get_db),
) -> EvaluationCaseOut:
    try:
        return case_out(create_evaluation_case(db, finding_id, payload, "bad_case", get_settings()))
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc


@router.post(
    "/findings/{finding_id}/evaluation-cases/reference",
    response_model=EvaluationCaseOut,
    status_code=201,
)
def create_reference_case(
    finding_id: uuid.UUID,
    payload: EvaluationCaseCreate,
    db: Session = Depends(get_db),
) -> EvaluationCaseOut:
    try:
        return case_out(
            create_evaluation_case(db, finding_id, payload, "reference_case", get_settings())
        )
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc


@router.get("/projects/{project_id}/evaluation-cases", response_model=list[EvaluationCaseOut])
def list_cases(
    project_id: uuid.UUID,
    case_type: str | None = Query(default=None),
    db: Session = Depends(get_db),
) -> list[EvaluationCaseOut]:
    query = select(EvaluationCase).where(EvaluationCase.project_id == project_id)
    if case_type:
        if case_type not in {"bad_case", "reference_case"}:
            raise HTTPException(status_code=422, detail="invalid case_type")
        query = query.where(EvaluationCase.case_type == case_type)
    return [
        case_out(item) for item in db.scalars(query.order_by(EvaluationCase.created_at.asc())).all()
    ]


@router.get("/evaluation-cases/{case_id}", response_model=EvaluationCaseOut)
def get_case(case_id: uuid.UUID, db: Session = Depends(get_db)) -> EvaluationCaseOut:
    case = db.get(EvaluationCase, case_id)
    if case is None:
        raise HTTPException(status_code=404, detail="evaluation case not found")
    return case_out(case)


@router.post(
    "/projects/{project_id}/evaluation-runs",
    response_model=EvaluationRunOut,
    status_code=status.HTTP_202_ACCEPTED,
)
def create_run(
    project_id: uuid.UUID,
    payload: EvaluationRunCreate,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
) -> EvaluationRunOut:
    try:
        run = create_evaluation_run(db, project_id, payload, get_settings())
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    background_tasks.add_task(run_evaluation_background, run.id)
    return run_out(run)


@router.get("/projects/{project_id}/evaluation-runs", response_model=list[EvaluationRunOut])
def list_runs(project_id: uuid.UUID, db: Session = Depends(get_db)) -> list[EvaluationRunOut]:
    rows = db.scalars(
        select(EvaluationRun)
        .where(EvaluationRun.project_id == project_id)
        .options(selectinload(EvaluationRun.results).selectinload(EvaluationResult.evaluation_case))
        .order_by(EvaluationRun.created_at.desc())
    ).all()
    return [run_out(item) for item in rows]


@router.get("/evaluation-runs/{run_id}", response_model=EvaluationRunOut)
def get_run(run_id: uuid.UUID, db: Session = Depends(get_db)) -> EvaluationRunOut:
    run = db.scalar(
        select(EvaluationRun)
        .where(EvaluationRun.id == run_id)
        .options(selectinload(EvaluationRun.results).selectinload(EvaluationResult.evaluation_case))
    )
    if run is None:
        raise HTTPException(status_code=404, detail="evaluation run not found")
    return run_out(run)


@router.get("/evaluation-runs/{run_id}/results", response_model=list[EvaluationResultOut])
def get_results(run_id: uuid.UUID, db: Session = Depends(get_db)) -> list[EvaluationResultOut]:
    if db.get(EvaluationRun, run_id) is None:
        raise HTTPException(status_code=404, detail="evaluation run not found")
    rows = db.scalars(
        select(EvaluationResult)
        .where(EvaluationResult.evaluation_run_id == run_id)
        .options(selectinload(EvaluationResult.evaluation_case))
        .order_by(EvaluationResult.ordinal.asc())
    ).all()
    return [result_out(item) for item in rows]


@router.get("/evaluation-results/{result_id}", response_model=EvaluationResultOut)
def get_result(result_id: uuid.UUID, db: Session = Depends(get_db)) -> EvaluationResultOut:
    result = db.scalar(
        select(EvaluationResult)
        .where(EvaluationResult.id == result_id)
        .options(selectinload(EvaluationResult.evaluation_case))
    )
    if result is None:
        raise HTTPException(status_code=404, detail="evaluation result not found")
    return result_out(result)


@router.post("/evaluation-runs/{run_id}/cancel", response_model=EvaluationRunOut)
def cancel_run(run_id: uuid.UUID, db: Session = Depends(get_db)) -> EvaluationRunOut:
    run = db.scalar(
        select(EvaluationRun)
        .where(EvaluationRun.id == run_id)
        .options(selectinload(EvaluationRun.results).selectinload(EvaluationResult.evaluation_case))
    )
    if run is None:
        raise HTTPException(status_code=404, detail="evaluation run not found")
    if run.status in {"queued", "running"}:
        run.status = "cancel_requested"
        db.commit()
    return run_out(run)
