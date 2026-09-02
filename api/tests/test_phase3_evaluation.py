from __future__ import annotations

import json
import uuid
from types import SimpleNamespace

import pytest
from sqlalchemy import select
from test_phase3_analysis import _make_fixture, _payload

import app.evaluation_service as evaluation_service
from app.ai_provider import AIResult, FixtureProvider, ProviderFailure
from app.core.config import Settings
from app.evaluation_service import (
    create_evaluation_case,
    create_evaluation_run,
    dataset_version,
    run_evaluation,
)
from app.models import EvaluationCase, EvaluationResult, EvaluationRun, Finding
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
        db,
        finding.id,
        EvaluationCaseCreate(
            expected_behavior={"must_avoid_unsupported_causal_conclusion": True},
            case_tags=["bad"],
        ),
        "bad_case",
        Settings(),
    )
    second = create_evaluation_case(
        db,
        finding.id,
        EvaluationCaseCreate(
            expected_behavior={"must_avoid_unsupported_causal_conclusion": False},
            case_tags=["changed"],
        ),
        "bad_case",
        Settings(),
    )
    assert first.id == second.id
    assert first.case_type == "bad_case"
    assert (
        db.scalar(select(EvaluationCase).where(EvaluationCase.project_id == project.id)).id
        == first.id
    )
    assert first.finding_snapshot_json["observed_behavior"]["claim"] == finding.claim
    assert "required_claim_types" not in first.expected_behavior_json
    assert "required_evidence_ids" not in first.expected_behavior_json


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


def test_replay_targets_nonzero_source_finding_ordinal(db):
    project, _, experiments, measurements = _make_fixture(db, 3)
    run = create_analysis_run(
        db,
        project.id,
        AnalysisRunCreate.model_validate(_payload(experiments, measurements)),
        Settings(),
    )
    assert len(run.findings) == 2
    source = run.findings[1]
    create_review(
        db,
        source.id,
        ReviewDecisionCreate(
            decision="reject",
            reviewer_name="Reviewer",
            reason_code="unsupported_causal_claim",
            comment="Causal claim is not supported.",
        ),
    )
    case = create_evaluation_case(
        db,
        source.id,
        EvaluationCaseCreate(),
        "bad_case",
        Settings(),
    )
    evaluation_run = create_evaluation_run(
        db,
        project.id,
        EvaluationRunCreate(evaluation_case_ids=[case.id]),
        Settings(),
    )
    completed = run_evaluation(db, evaluation_run.id, Settings())
    result = db.scalar(
        select(EvaluationResult).where(EvaluationResult.evaluation_run_id == completed.id)
    )
    assert result is not None
    assert result.replay_analysis_run_id is not None
    replay_findings = db.scalars(
        select(Finding)
        .where(Finding.analysis_run_id == result.replay_analysis_run_id)
        .order_by(Finding.ordinal.asc())
    ).all()
    assert len(replay_findings) == 2
    assert replay_findings[0].claim_type == "comparative_finding"
    assert replay_findings[1].claim_type == "causal_claim"
    assert result.deterministic_scores_json["causal_gate_not_upgraded_by_direct_support"] is True


def test_ambiguous_bad_case_requires_expected_behavior(db):
    project, finding = _analysis(db)
    create_review(
        db,
        finding.id,
        ReviewDecisionCreate(
            decision="reject",
            reviewer_name="Reviewer",
            reason_code="incorrect_reasoning",
            comment="Reasoning is not reliable.",
        ),
    )
    with pytest.raises(ValueError, match="ambiguous Bad Case"):
        create_evaluation_case(db, finding.id, EvaluationCaseCreate(), "bad_case", Settings())


def test_reference_case_derives_expected_behavior_from_accepted_finding(db):
    project, finding = _analysis(db)
    create_review(db, finding.id, ReviewDecisionCreate(decision="accept", reviewer_name="Reviewer"))
    case = create_evaluation_case(
        db, finding.id, EvaluationCaseCreate(), "reference_case", Settings()
    )
    assert case.expected_behavior_json["required_claim_types"] == [finding.claim_type]
    assert case.expected_behavior_json["expected_gate_status"] == finding.evidence_gate_status


def test_dataset_hash_changes_for_type_or_content_but_not_order():
    first = SimpleNamespace(id=uuid.uuid4(), case_type="bad_case", case_hash="a" * 64)
    second = SimpleNamespace(id=uuid.uuid4(), case_type="reference_case", case_hash="b" * 64)
    assert dataset_version([first, second]) == dataset_version([second, first])
    changed_type = SimpleNamespace(id=second.id, case_type="bad_case", case_hash=second.case_hash)
    changed_content = SimpleNamespace(id=second.id, case_type=second.case_type, case_hash="c" * 64)
    assert dataset_version([first, changed_type]) != dataset_version([first, second])
    assert dataset_version([first, changed_content]) != dataset_version([first, second])


def test_suggestion_paths_are_required_and_read_from_normalized_prefill():
    case = SimpleNamespace(
        expected_behavior_json={"required_suggestion_change_paths": ["/additives/@starch"]},
        context_snapshot_json={"evidence": []},
    )
    common = dict(
        evidence_links=[],
        structured_support_json=[],
        claim_type="scientific_observation",
        evidence_gate_status="supported",
        limitations_json=[],
        missing_evidence_json=[],
    )
    passing = SimpleNamespace(
        **common,
        suggested_next_experiment_json={
            "validation_status": "valid",
            "prefill": {
                "structured_data": {},
                "change_operations": [{"path": "/additives/@starch"}],
            },
        },
    )
    failing = SimpleNamespace(
        **common,
        suggested_next_experiment_json={
            "validation_status": "valid",
            "prefill": {"structured_data": {}, "change_operations": []},
        },
    )
    assert evaluation_service.deterministic_metrics(case, passing, True)["overall_pass"] is True
    assert (
        evaluation_service.deterministic_metrics(case, failing, True)[
            "required_suggestion_paths_present"
        ]
        is False
    )


def test_per_case_failure_does_not_stop_later_cases(db, monkeypatch):
    project, _, experiments, measurements = _make_fixture(db, 3)
    run = create_analysis_run(
        db,
        project.id,
        AnalysisRunCreate.model_validate(_payload(experiments, measurements)),
        Settings(),
    )
    first, second = run.findings
    create_review(db, first.id, ReviewDecisionCreate(decision="accept", reviewer_name="Reviewer"))
    create_review(
        db,
        second.id,
        ReviewDecisionCreate(
            decision="reject",
            reviewer_name="Reviewer",
            reason_code="unsupported_causal_claim",
            comment="Not causal proof.",
        ),
    )
    cases = [
        create_evaluation_case(db, first.id, EvaluationCaseCreate(), "reference_case", Settings()),
        create_evaluation_case(
            db,
            second.id,
            EvaluationCaseCreate(),
            "bad_case",
            Settings(),
        ),
    ]
    evaluation_run = create_evaluation_run(
        db,
        project.id,
        EvaluationRunCreate(evaluation_case_ids=[item.id for item in cases]),
        Settings(),
    )
    original = evaluation_service._build_replay

    def fail_first(session, case, run, settings):
        if case.id == cases[0].id:
            raise ValueError("invalid_provider_json")
        return original(session, case, run, settings)

    monkeypatch.setattr(evaluation_service, "_build_replay", fail_first)
    completed = run_evaluation(db, evaluation_run.id, Settings())
    results = db.scalars(
        select(EvaluationResult)
        .where(EvaluationResult.evaluation_run_id == completed.id)
        .order_by(EvaluationResult.ordinal.asc())
    ).all()
    result_by_case = {item.evaluation_case_id: item for item in results}
    assert result_by_case[cases[0].id].status == "error"
    assert result_by_case[cases[1].id].status in {"passed", "failed"}
    assert completed.status == "completed_with_errors"


def test_global_provider_auth_failure_stops_remaining_cases(db, monkeypatch):
    project, _, experiments, measurements = _make_fixture(db, 3)
    run = create_analysis_run(
        db,
        project.id,
        AnalysisRunCreate.model_validate(_payload(experiments, measurements)),
        Settings(),
    )
    first, second = run.findings
    create_review(db, first.id, ReviewDecisionCreate(decision="accept", reviewer_name="Reviewer"))
    create_review(
        db,
        second.id,
        ReviewDecisionCreate(
            decision="reject",
            reviewer_name="Reviewer",
            reason_code="unsupported_causal_claim",
            comment="Not causal proof.",
        ),
    )
    cases = [
        create_evaluation_case(db, first.id, EvaluationCaseCreate(), "reference_case", Settings()),
        create_evaluation_case(db, second.id, EvaluationCaseCreate(), "bad_case", Settings()),
    ]
    evaluation_run = create_evaluation_run(
        db,
        project.id,
        EvaluationRunCreate(evaluation_case_ids=[item.id for item in cases]),
        Settings(),
    )

    class AuthFailureProvider:
        def generate_structured(self, request, response_model):
            raise ProviderFailure("provider_auth", "invalid credentials")

    monkeypatch.setattr(evaluation_service, "_provider", lambda profile: AuthFailureProvider())
    failed = run_evaluation(db, evaluation_run.id, Settings())
    results = db.scalars(
        select(EvaluationResult)
        .where(EvaluationResult.evaluation_run_id == failed.id)
        .order_by(EvaluationResult.ordinal.asc())
    ).all()
    assert failed.status == "failed"
    assert failed.error_code == "provider_auth"
    assert all(item.status == "error" for item in results)
    assert failed.completed_cases == 2
    assert failed.error_cases == 2


def test_cancellation_marks_pending_results_terminal(db, monkeypatch):
    project, _, experiments, measurements = _make_fixture(db, 3)
    run = create_analysis_run(
        db,
        project.id,
        AnalysisRunCreate.model_validate(_payload(experiments, measurements)),
        Settings(),
    )
    first, second = run.findings
    create_review(db, first.id, ReviewDecisionCreate(decision="accept", reviewer_name="Reviewer"))
    create_review(
        db,
        second.id,
        ReviewDecisionCreate(
            decision="reject",
            reviewer_name="Reviewer",
            reason_code="unsupported_causal_claim",
            comment="Not causal proof.",
        ),
    )
    cases = [
        create_evaluation_case(db, first.id, EvaluationCaseCreate(), "reference_case", Settings()),
        create_evaluation_case(db, second.id, EvaluationCaseCreate(), "bad_case", Settings()),
    ]
    evaluation_run = create_evaluation_run(
        db,
        project.id,
        EvaluationRunCreate(evaluation_case_ids=[item.id for item in cases]),
        Settings(),
    )
    original = evaluation_service._run_case

    def cancel_after_first(session, run, result, case, settings):
        original(session, run, result, case, settings)
        run.status = "cancel_requested"
        session.commit()

    monkeypatch.setattr(evaluation_service, "_run_case", cancel_after_first)
    cancelled = run_evaluation(db, evaluation_run.id, Settings())
    results = db.scalars(
        select(EvaluationResult)
        .where(EvaluationResult.evaluation_run_id == cancelled.id)
        .order_by(EvaluationResult.ordinal.asc())
    ).all()
    assert cancelled.status == "cancelled"
    assert results[1].status == "cancelled"


def test_startup_interruption_marks_queued_and_running_runs(db):
    project, _, experiments, measurements = _make_fixture(db, 2)
    analysis_run = create_analysis_run(
        db,
        project.id,
        AnalysisRunCreate.model_validate(_payload(experiments, measurements)),
        Settings(),
    )
    create_review(
        db,
        analysis_run.findings[0].id,
        ReviewDecisionCreate(decision="accept", reviewer_name="Reviewer"),
    )
    case = create_evaluation_case(
        db, analysis_run.findings[0].id, EvaluationCaseCreate(), "reference_case", Settings()
    )
    evaluation_run = create_evaluation_run(
        db, project.id, EvaluationRunCreate(evaluation_case_ids=[case.id]), Settings()
    )
    evaluation_run.status = "running"
    db.commit()
    assert evaluation_service.mark_interrupted_runs(db) == 1
    assert db.get(EvaluationRun, evaluation_run.id).status == "interrupted"


def test_optional_judge_failure_or_disagreement_does_not_change_deterministic_result(
    db, monkeypatch
):
    project, _, experiments, measurements = _make_fixture(db, 2)
    analysis_run = create_analysis_run(
        db,
        project.id,
        AnalysisRunCreate.model_validate(_payload(experiments, measurements)),
        Settings(),
    )
    create_review(
        db,
        analysis_run.findings[0].id,
        ReviewDecisionCreate(decision="accept", reviewer_name="Reviewer"),
    )
    case = create_evaluation_case(
        db, analysis_run.findings[0].id, EvaluationCaseCreate(), "reference_case", Settings()
    )

    class JudgeProvider:
        def __init__(self, mode):
            self.mode = mode

        def generate_structured(self, request, response_model):
            if request.model == "fixture://judge" and self.mode == "error":
                raise ProviderFailure("judge_unavailable", "judge offline")
            if request.model == "fixture://judge":
                payload = {"overall": "poor", "rationale": "Disagree", "dimensions": {}}
                response_model.model_validate(payload)
                return AIResult(
                    parsed=payload,
                    raw_output=json.dumps(payload),
                    requested_model=request.model,
                    resolved_model=request.model,
                    response_id="judge",
                    provider_model_version="fixture-judge",
                    usage={},
                    finish_reason="stop",
                    latency_ms=0,
                )
            return FixtureProvider().generate_structured(request, response_model)

    monkeypatch.setattr(evaluation_service, "_provider", lambda profile: JudgeProvider("error"))
    first_run = create_evaluation_run(
        db,
        project.id,
        EvaluationRunCreate(evaluation_case_ids=[case.id], judge_enabled=True),
        Settings(),
    )
    first_completed = run_evaluation(db, first_run.id, Settings())
    first_result = db.scalar(
        select(EvaluationResult).where(EvaluationResult.evaluation_run_id == first_completed.id)
    )
    assert first_result.status in {"passed", "failed"}
    assert first_result.deterministic_scores_json["overall_pass"] is True
    assert first_result.judge_scores_json is None

    monkeypatch.setattr(evaluation_service, "_provider", lambda profile: JudgeProvider("disagree"))
    second_run = create_evaluation_run(
        db,
        project.id,
        EvaluationRunCreate(evaluation_case_ids=[case.id], judge_enabled=True),
        Settings(),
    )
    second_completed = run_evaluation(db, second_run.id, Settings())
    second_result = db.scalar(
        select(EvaluationResult).where(EvaluationResult.evaluation_run_id == second_completed.id)
    )
    assert second_result.status == first_result.status
    assert second_result.deterministic_scores_json["overall_pass"] is True
    assert second_result.judge_scores_json["overall"] == "poor"


def test_baseline_matching_and_mismatched_dataset_validation(db):
    project, _, experiments, measurements = _make_fixture(db, 2)
    analysis_run = create_analysis_run(
        db,
        project.id,
        AnalysisRunCreate.model_validate(_payload(experiments, measurements)),
        Settings(),
    )
    create_review(
        db,
        analysis_run.findings[0].id,
        ReviewDecisionCreate(decision="accept", reviewer_name="Reviewer"),
    )
    case = create_evaluation_case(
        db, analysis_run.findings[0].id, EvaluationCaseCreate(), "reference_case", Settings()
    )
    baseline = create_evaluation_run(
        db, project.id, EvaluationRunCreate(evaluation_case_ids=[case.id]), Settings()
    )
    run_evaluation(db, baseline.id, Settings())
    matching = create_evaluation_run(
        db,
        project.id,
        EvaluationRunCreate(evaluation_case_ids=[case.id], baseline_run_id=baseline.id),
        Settings(),
    )
    completed = run_evaluation(db, matching.id, Settings())
    assert completed.regression_summary_json["unchanged_cases"] == 1
    other_analysis = create_analysis_run(
        db,
        project.id,
        AnalysisRunCreate.model_validate(_payload(experiments, measurements)),
        Settings(),
    )
    create_review(
        db,
        other_analysis.findings[0].id,
        ReviewDecisionCreate(decision="accept", reviewer_name="Reviewer"),
    )
    other_case = create_evaluation_case(
        db, other_analysis.findings[0].id, EvaluationCaseCreate(), "reference_case", Settings()
    )
    with pytest.raises(ValueError, match="dataset version"):
        create_evaluation_run(
            db,
            project.id,
            EvaluationRunCreate(evaluation_case_ids=[other_case.id], baseline_run_id=baseline.id),
            Settings(),
        )


def test_evaluation_case_and_completed_result_are_immutable(db):
    project, finding = _analysis(db)
    create_review(db, finding.id, ReviewDecisionCreate(decision="accept", reviewer_name="Reviewer"))
    case = create_evaluation_case(
        db, finding.id, EvaluationCaseCreate(), "reference_case", Settings()
    )
    case.expected_behavior_json = {"tampered": True}
    with pytest.raises(ValueError, match="immutable"):
        db.commit()
    db.rollback()
    run = create_evaluation_run(
        db, project.id, EvaluationRunCreate(evaluation_case_ids=[case.id]), Settings()
    )
    completed = run_evaluation(db, run.id, Settings())
    result = db.scalar(
        select(EvaluationResult).where(EvaluationResult.evaluation_run_id == completed.id)
    )
    assert result is not None
    result.deterministic_scores_json = {"tampered": True}
    with pytest.raises(ValueError, match="completed EvaluationResult is immutable"):
        db.commit()
    db.rollback()
