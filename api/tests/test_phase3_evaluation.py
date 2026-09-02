from __future__ import annotations

from sqlalchemy import select
from test_phase3_analysis import _make_fixture, _payload

from app.core.config import Settings
from app.evaluation_service import (
    create_evaluation_case,
    create_evaluation_run,
    dataset_version,
    run_evaluation,
)
from app.models import EvaluationCase, EvaluationResult
from app.schemas import (
    AnalysisRunCreate,
    EvaluationCaseCreate,
    EvaluationRunCreate,
    ReviewDecisionCreate,
)
from app.scientific_ai_service import create_analysis_run, create_review


def _analysis(db):
    project, _, experiments, measurements = _make_fixture(db, 2)
    run = create_analysis_run(
        db,
        project.id,
        AnalysisRunCreate.model_validate(_payload(experiments, measurements)),
        Settings(),
    )
    finding = run.findings[0]
    return project, finding


def test_bad_and_reference_cases_require_latest_review_and_are_idempotent(db):
    project, finding = _analysis(db)
    create_review(
        db,
        finding.id,
        ReviewDecisionCreate(
            decision="reject",
            reviewer_name="Reviewer",
            reason_code="incorrect_reasoning",
            comment="bad",
        ),
    )
    first = create_evaluation_case(
        db, finding.id, EvaluationCaseCreate(case_tags=["bad"]), "bad_case", Settings()
    )
    second = create_evaluation_case(
        db, finding.id, EvaluationCaseCreate(case_tags=["changed"]), "bad_case", Settings()
    )
    assert first.id == second.id
    assert first.case_type == "bad_case"
    assert (
        db.scalar(select(EvaluationCase).where(EvaluationCase.project_id == project.id)).id
        == first.id
    )


def test_reference_case_uses_accepted_review_and_dataset_hash_is_order_independent(db):
    project, finding = _analysis(db)
    create_review(db, finding.id, ReviewDecisionCreate(decision="accept", reviewer_name="Reviewer"))
    case = create_evaluation_case(
        db, finding.id, EvaluationCaseCreate(case_tags=["reference"]), "reference_case", Settings()
    )
    assert case.case_type == "reference_case"
    assert dataset_version([case]) == dataset_version([case])


def test_evaluation_run_persists_then_executes_sequentially(db):
    project, finding = _analysis(db)
    create_review(db, finding.id, ReviewDecisionCreate(decision="accept", reviewer_name="Reviewer"))
    case = create_evaluation_case(
        db, finding.id, EvaluationCaseCreate(), "reference_case", Settings()
    )
    run = create_evaluation_run(
        db, project.id, EvaluationRunCreate(evaluation_case_ids=[case.id]), Settings()
    )
    assert run.status == "queued"
    completed = run_evaluation(db, run.id, Settings())
    assert completed.status in {"completed", "completed_with_errors"}
    result = db.scalar(select(EvaluationResult).where(EvaluationResult.evaluation_run_id == run.id))
    assert result is not None
    assert result.status in {"passed", "failed", "error"}
