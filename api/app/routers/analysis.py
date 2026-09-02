from __future__ import annotations

import uuid
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.ai_provider import PromptRegistry, ProviderFailure
from app.context_builder import ContextValidationError
from app.core.config import get_settings
from app.db import get_db
from app.models import Finding, ReviewDecision, ScientificAnalysisRun
from app.schemas import (
    AnalysisRunCreate,
    AnalysisRunOut,
    EvidenceGateStatus,
    FindingClaimType,
    FindingOut,
    ModelProfileOut,
    PromptVersionOut,
    ReviewDecisionCreate,
    ReviewDecisionOut,
    ReviewStatus,
)
from app.scientific_ai_service import (
    AnalysisFailure,
    analysis_run_out,
    create_analysis_run,
    create_review,
    finding_out,
    list_profiles,
)

router = APIRouter(tags=["scientific-analysis"])


@router.get("/ai/model-profiles", response_model=list[ModelProfileOut])
def model_profiles() -> list[ModelProfileOut]:
    return [
        ModelProfileOut(
            key=item.key,
            provider=item.provider,
            model=item.model,
            label=item.label,
            structured_output_mode=item.structured_output_mode,
            available=item.available,
            capability_reason=item.capability_reason,
        )
        for item in list_profiles(get_settings())
    ]


@router.get("/ai/prompt-versions", response_model=list[PromptVersionOut])
def prompt_versions() -> list[PromptVersionOut]:
    settings = get_settings()
    root = settings.ai_prompt_root
    if not root.is_absolute() and not root.exists():
        root = Path(__file__).resolve().parents[1] / "prompts"
    registry = PromptRegistry(root)
    result: list[PromptVersionOut] = []
    for key, version in (("scientific_analysis", 1), ("evaluation_judge", 1)):
        try:
            _, digest = registry.get(key, version)
        except ProviderFailure:
            continue
        result.append(PromptVersionOut(key=key, version=version, sha256=digest))
    return result


@router.post("/projects/{project_id}/analysis-runs", response_model=AnalysisRunOut, status_code=201)
def post_analysis(
    project_id: uuid.UUID, payload: AnalysisRunCreate, db: Session = Depends(get_db)
) -> AnalysisRunOut:
    try:
        run = create_analysis_run(db, project_id, payload, get_settings())
        return analysis_run_out(run)
    except AnalysisFailure as exc:
        if exc.code in {
            "project_not_found",
            "revision_not_found",
            "measurement_not_found",
            "literature_selection_invalid",
            "evidence_selection_invalid",
        }:
            status_code = 404
        elif exc.code == "analysis_context_too_large":
            status_code = 413
        elif exc.code in {"provider_timeout"}:
            status_code = 504
        elif exc.code in {
            "provider_auth",
            "provider_rate_limit",
            "provider_server_error",
            "provider_unavailable",
            "provider_error",
            "invalid_provider_json",
            "invalid_provider_response",
            "unsupported_structured_output",
        }:
            status_code = 502
        else:
            status_code = 409
        raise HTTPException(
            status_code=status_code,
            detail={"code": exc.code, "message": str(exc), "analysis_run_id": str(exc.run_id)},
        ) from exc
    except (ContextValidationError, ProviderFailure) as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc


def _run_query():
    return select(ScientificAnalysisRun).options(
        selectinload(ScientificAnalysisRun.context_snapshot),
        selectinload(ScientificAnalysisRun.findings).selectinload(Finding.evidence_links),
        selectinload(ScientificAnalysisRun.findings).selectinload(Finding.reviews),
    )


@router.get("/projects/{project_id}/analysis-runs", response_model=list[AnalysisRunOut])
def list_analysis_runs(
    project_id: uuid.UUID,
    purpose: str | None = Query(default=None),
    status: str | None = Query(default=None),
    db: Session = Depends(get_db),
) -> list[AnalysisRunOut]:
    query = _run_query().where(ScientificAnalysisRun.project_id == project_id)
    if purpose:
        query = query.where(ScientificAnalysisRun.purpose == purpose)
    if status:
        query = query.where(ScientificAnalysisRun.status == status)
    return [
        analysis_run_out(item)
        for item in db.scalars(query.order_by(ScientificAnalysisRun.created_at.desc())).all()
    ]


@router.get("/analysis-runs/{analysis_run_id}", response_model=AnalysisRunOut)
def get_analysis_run(analysis_run_id: uuid.UUID, db: Session = Depends(get_db)) -> AnalysisRunOut:
    run = db.scalar(_run_query().where(ScientificAnalysisRun.id == analysis_run_id))
    if run is None:
        raise HTTPException(status_code=404, detail="analysis run not found")
    return analysis_run_out(run)


@router.get("/projects/{project_id}/findings", response_model=list[FindingOut])
def list_findings(
    project_id: uuid.UUID,
    review_status: ReviewStatus | None = Query(default=None),
    claim_type: FindingClaimType | None = Query(default=None),
    gate_status: EvidenceGateStatus | None = Query(default=None),
    db: Session = Depends(get_db),
) -> list[FindingOut]:
    query = (
        select(Finding)
        .where(Finding.project_id == project_id)
        .options(selectinload(Finding.evidence_links), selectinload(Finding.reviews))
    )
    if review_status:
        query = query.where(Finding.review_status == review_status)
    if claim_type:
        query = query.where(Finding.claim_type == claim_type)
    if gate_status:
        query = query.where(Finding.evidence_gate_status == gate_status)
    return [
        finding_out(item) for item in db.scalars(query.order_by(Finding.created_at.asc())).all()
    ]


@router.get("/findings/{finding_id}", response_model=FindingOut)
def get_finding(finding_id: uuid.UUID, db: Session = Depends(get_db)) -> FindingOut:
    finding = db.scalar(
        select(Finding)
        .where(Finding.id == finding_id)
        .options(selectinload(Finding.evidence_links), selectinload(Finding.reviews))
    )
    if finding is None:
        raise HTTPException(status_code=404, detail="finding not found")
    return finding_out(finding)


@router.get("/findings/{finding_id}/reviews", response_model=list[ReviewDecisionOut])
def list_reviews(finding_id: uuid.UUID, db: Session = Depends(get_db)) -> list[ReviewDecision]:
    if db.get(Finding, finding_id) is None:
        raise HTTPException(status_code=404, detail="finding not found")
    return list(
        db.scalars(
            select(ReviewDecision)
            .where(ReviewDecision.finding_id == finding_id)
            .order_by(ReviewDecision.sequence_number.asc())
        ).all()
    )


@router.post("/findings/{finding_id}/reviews", response_model=ReviewDecisionOut, status_code=201)
def post_review(
    finding_id: uuid.UUID, payload: ReviewDecisionCreate, db: Session = Depends(get_db)
) -> ReviewDecision:
    try:
        return create_review(db, finding_id, payload)
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
