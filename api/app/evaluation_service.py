from __future__ import annotations

import copy
import json
import uuid
from datetime import UTC, datetime
from typing import Any

from pydantic import ValidationError
from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.ai_provider import AIRequest, LangfuseAdapter, ProviderFailure
from app.core.config import Settings
from app.db import SessionLocal
from app.models import (
    AnalysisContextSnapshot,
    EvaluationCase,
    EvaluationResult,
    EvaluationRun,
    Finding,
    ReviewDecision,
    ScientificAnalysisRun,
)
from app.schemas import (
    EvaluationCaseCreate,
    EvaluationCaseOut,
    EvaluationResultOut,
    EvaluationRunCreate,
    EvaluationRunOut,
    ScientificAnalysisResponseV1,
)
from app.scientific_ai_service import (
    _make_finding,
    _prompt_registry,
    _provider,
    resolve_profile,
)


def _now() -> datetime:
    return datetime.now(UTC)


def _canonical_hash(value: Any) -> str:
    import hashlib

    return hashlib.sha256(
        json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False).encode()
    ).hexdigest()


def _latest_review(db: Session, finding_id: uuid.UUID) -> ReviewDecision | None:
    return db.scalar(
        select(ReviewDecision)
        .where(ReviewDecision.finding_id == finding_id)
        .order_by(ReviewDecision.sequence_number.desc())
    )


class GlobalEvaluationFailure(RuntimeError):
    """A provider/configuration failure that makes the rest of a run unsafe to execute."""

    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code


class ReplayTargetFailure(ValueError):
    """The frozen source Finding target cannot be matched by a replay."""

    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code


GLOBAL_PROVIDER_FAILURE_CODES = {
    "model_profile_not_found",
    "provider_auth",
    "provider_unavailable",
    "unsupported_structured_output",
    "provider_configuration",
}


def _is_global_provider_failure(exc: ProviderFailure) -> bool:
    return exc.code in GLOBAL_PROVIDER_FAILURE_CODES


def _suggestion_change_paths(suggestion: Any) -> list[str]:
    """Read paths from the normalized suggestion without assuming one storage wrapper."""
    if not isinstance(suggestion, dict):
        return []
    containers = [suggestion]
    prefill = suggestion.get("prefill")
    if isinstance(prefill, dict):
        containers.insert(0, prefill)
    for container in containers:
        operations = container.get("change_operations")
        if isinstance(operations, list):
            return sorted(
                {
                    str(item.get("path"))
                    for item in operations
                    if isinstance(item, dict) and item.get("path")
                }
            )
    return []


def _reference_expected_behavior(finding: Finding, payload: EvaluationCaseCreate) -> dict[str, Any]:
    expected = dict(payload.expected_behavior)
    expected.setdefault("expected_gate_status", finding.evidence_gate_status)
    expected.setdefault("required_claim_types", [finding.claim_type])
    expected.setdefault(
        "required_direct_support_kinds",
        sorted({item.get("kind") for item in finding.structured_support_json if item.get("kind")}),
    )
    expected.setdefault(
        "required_evidence_ids", [str(item.evidence_record_id) for item in finding.evidence_links]
    )
    expected.setdefault(
        "required_limitation_codes",
        sorted({item.get("code") for item in finding.limitations_json if item.get("code")}),
    )
    expected.setdefault(
        "required_missing_evidence_codes",
        sorted({item.get("code") for item in finding.missing_evidence_json if item.get("code")}),
    )
    expected.setdefault(
        "required_suggestion_change_paths",
        _suggestion_change_paths(finding.suggested_next_experiment_json),
    )
    expected.setdefault("must_have_valid_citations", True)
    expected.setdefault(
        "must_avoid_unsupported_causal_conclusion", finding.claim_type == "causal_claim"
    )
    expected.setdefault(
        "must_distinguish_comparison_from_causality", finding.claim_type == "causal_claim"
    )
    expected.setdefault("reviewer_notes", "")
    return expected


def _bad_expected_behavior(
    finding: Finding, review: ReviewDecision, payload: EvaluationCaseCreate
) -> dict[str, Any]:
    """Build only safe, rejection-taxonomy defaults; disputed Finding fields stay observed."""
    user_expected = dict(payload.expected_behavior)
    expected = dict(user_expected)
    reason = review.reason_code or ""
    expected["source_rejection_reason"] = reason
    if reason == "unsupported_causal_claim":
        expected.setdefault("must_avoid_unsupported_causal_conclusion", True)
    elif reason == "incorrect_citation":
        expected.setdefault("must_have_valid_citations", True)
    elif reason == "missed_limitation":
        if not expected.get("required_limitation_codes"):
            raise ValueError(
                "missed_limitation Bad Case requires expected_behavior.required_limitation_codes"
            )
    elif reason == "insufficient_evidence":
        if "expected_gate_status" not in expected:
            raise ValueError(
                "insufficient_evidence Bad Case requires explicit expected_gate_status"
            )
    elif reason == "incorrect_experiment_comparison":
        expected.setdefault("direct_structured_support_required", True)
        expected.setdefault("comparison_assertions_correct", True)
    elif not any(key != "source_rejection_reason" for key in user_expected):
        raise ValueError(
            "ambiguous Bad Case rejection requires reviewer-provided expected_behavior"
        )
    if not expected:
        raise ValueError("Bad Case requires expected_behavior")
    return expected


def _case_payload(
    finding: Finding,
    review: ReviewDecision,
    run: ScientificAnalysisRun,
    payload: EvaluationCaseCreate,
    case_type: str,
) -> dict[str, Any]:
    context = run.context_snapshot.snapshot_json if run.context_snapshot else {}
    observed_behavior = {
        "id": str(finding.id),
        "project_id": str(finding.project_id),
        "analysis_run_id": str(finding.analysis_run_id),
        "ordinal": finding.ordinal,
        "claim": finding.claim,
        "claim_type": finding.claim_type,
        "confidence_label": finding.confidence_label,
        "confidence_rationale": finding.confidence_rationale,
        "applicability_scope": finding.applicability_scope,
        "limitations_json": copy.deepcopy(finding.limitations_json),
        "risks_json": copy.deepcopy(finding.risks_json),
        "missing_evidence_json": copy.deepcopy(finding.missing_evidence_json),
        "comparison_assertions_json": copy.deepcopy(finding.comparison_assertions_json),
        "structured_support_json": copy.deepcopy(finding.structured_support_json),
        "causal_target_json": copy.deepcopy(finding.causal_target_json),
        "suggested_next_experiment_json": copy.deepcopy(finding.suggested_next_experiment_json),
        "evidence_gate_status": finding.evidence_gate_status,
        "review_status": finding.review_status,
    }
    finding_snapshot = copy.deepcopy(observed_behavior)
    finding_snapshot["observed_behavior"] = copy.deepcopy(observed_behavior)
    finding_snapshot["replay_target"] = {
        "source_ordinal": finding.ordinal,
        "allowed_claim_types": [finding.claim_type],
        "causal_target": copy.deepcopy(finding.causal_target_json),
    }
    gate_snapshot = {
        "status": finding.evidence_gate_status,
        "rationale": copy.deepcopy(finding.evidence_gate_rationale_json),
        "policy_version": finding.gate_policy_version,
    }
    review_snapshot = {
        "id": str(review.id),
        "finding_id": str(review.finding_id),
        "sequence_number": review.sequence_number,
        "decision": review.decision,
        "reviewer_name": review.reviewer_name,
        "reason_code": review.reason_code,
        "comment": review.comment,
    }
    source_model = {
        "provider_key": run.provider_key,
        "model_profile_key": run.model_profile_key,
        "requested_model": run.requested_model,
        "resolved_model": run.resolved_model,
        "structured_output_mode": run.structured_output_mode,
        "output_schema_version": run.output_schema_version,
        "workflow_version": run.workflow_version,
    }
    expected = (
        _reference_expected_behavior(finding, payload)
        if case_type == "reference_case"
        else _bad_expected_behavior(finding, review, payload)
    )
    body = {
        "project_id": str(finding.project_id),
        "case_type": case_type,
        "source_finding_id": str(finding.id),
        "source_review_decision_id": str(review.id),
        "context_schema_version": run.context_snapshot.schema_version
        if run.context_snapshot
        else 1,
        "context_snapshot_json": copy.deepcopy(context),
        "model_output_snapshot_json": copy.deepcopy(run.validated_output_json or {}),
        "finding_snapshot_json": finding_snapshot,
        "gate_snapshot_json": gate_snapshot,
        "review_snapshot_json": review_snapshot,
        "expected_behavior_json": expected,
        "case_tags_json": list(payload.case_tags),
        "source_model_config_json": source_model,
        "source_prompt_snapshot_json": copy.deepcopy(run.prompt_snapshot_json),
    }
    return body


def create_evaluation_case(
    db: Session,
    finding_id: uuid.UUID,
    payload: EvaluationCaseCreate,
    case_type: str,
    settings: Settings,
) -> EvaluationCase:
    finding = db.scalar(
        select(Finding)
        .where(Finding.id == finding_id)
        .options(
            selectinload(Finding.reviews),
            selectinload(Finding.evidence_links),
            selectinload(Finding.analysis_run).selectinload(ScientificAnalysisRun.context_snapshot),
        )
    )
    if finding is None:
        raise LookupError("finding not found")
    latest = _latest_review(db, finding_id)
    required_decision = "reject" if case_type == "bad_case" else "accept"
    if latest is None or latest.decision != required_decision:
        raise ValueError(f"latest review must be {required_decision} for {case_type}")
    existing = db.scalar(
        select(EvaluationCase).where(
            EvaluationCase.source_review_decision_id == latest.id,
            EvaluationCase.case_type == case_type,
        )
    )
    if existing is not None:
        return existing
    run = finding.analysis_run
    if run is None or run.context_snapshot is None:
        raise ValueError("finding has no frozen analysis context")
    body = _case_payload(finding, latest, run, payload, case_type)
    case_hash = _canonical_hash(body)
    case = EvaluationCase(
        project_id=finding.project_id,
        case_type=case_type,
        source_finding_id=finding.id,
        source_review_decision_id=latest.id,
        context_schema_version=body["context_schema_version"],
        context_snapshot_json=body["context_snapshot_json"],
        model_output_snapshot_json=body["model_output_snapshot_json"],
        finding_snapshot_json=body["finding_snapshot_json"],
        gate_snapshot_json=body["gate_snapshot_json"],
        review_snapshot_json=body["review_snapshot_json"],
        expected_behavior_json=body["expected_behavior_json"],
        case_tags_json=body["case_tags_json"],
        source_model_config_json=body["source_model_config_json"],
        source_prompt_snapshot_json=body["source_prompt_snapshot_json"],
        case_hash=case_hash,
        langfuse_sync_status="disabled" if not settings.langfuse_enabled else "pending",
    )
    db.add(case)
    db.commit()
    db.refresh(case)
    try:
        case.langfuse_dataset_item_id = LangfuseAdapter(settings).sync_evaluation_case(case)
        if case.langfuse_dataset_item_id:
            case.langfuse_sync_status = "synced"
            db.commit()
    except Exception:
        case.langfuse_sync_status = "failed"
        db.commit()
    return case


def dataset_version(cases: list[EvaluationCase]) -> str:
    entries = [
        {"case_type": item.case_type, "case_id": str(item.id), "case_hash": item.case_hash}
        for item in cases
    ]
    return _canonical_hash(
        sorted(entries, key=lambda item: (item["case_type"], item["case_id"], item["case_hash"]))
    )


def create_evaluation_run(
    db: Session,
    project_id: uuid.UUID,
    payload: EvaluationRunCreate,
    settings: Settings,
) -> EvaluationRun:
    cases = list(
        db.scalars(
            select(EvaluationCase)
            .where(
                EvaluationCase.project_id == project_id,
                EvaluationCase.id.in_(payload.evaluation_case_ids),
            )
            .order_by(EvaluationCase.case_type.asc(), EvaluationCase.id.asc())
        ).all()
    )
    if len(cases) != len(payload.evaluation_case_ids):
        raise ValueError("all evaluation cases must belong to the selected project")
    profile = resolve_profile(settings, payload.model_profile_key)
    prompt, prompt_hash = _prompt_registry(settings).get(
        "scientific_analysis", payload.prompt_version
    )
    baseline = None
    if payload.baseline_run_id is not None:
        baseline = db.get(EvaluationRun, payload.baseline_run_id)
        if baseline is None or baseline.project_id != project_id:
            raise ValueError("baseline run must belong to the selected project")
        if baseline.dataset_version != dataset_version(cases):
            raise ValueError("baseline dataset version does not match selected cases")
    judge_profile = None
    if payload.judge_enabled:
        judge_profile = resolve_profile(
            settings, payload.judge_model_profile_key or settings.ai_default_judge_profile
        )
    run = EvaluationRun(
        project_id=project_id,
        status="queued",
        dataset_version=dataset_version(cases),
        model_profile_key=profile.key,
        structured_output_mode=profile.structured_output_mode,
        requested_model=profile.model,
        prompt_key="scientific_analysis",
        prompt_version=payload.prompt_version,
        prompt_sha256=prompt_hash,
        prompt_snapshot_json={
            "key": "scientific_analysis",
            "version": payload.prompt_version,
            "content": prompt,
        },
        workflow_version=1,
        output_schema_version=1,
        generation_parameters_json={
            "temperature": 0.0,
            "timeout_seconds": settings.ai_timeout_seconds,
        },
        judge_enabled=payload.judge_enabled,
        judge_model_profile_key=judge_profile.key if judge_profile else None,
        judge_structured_output_mode=judge_profile.structured_output_mode
        if judge_profile
        else None,
        judge_prompt_version=1 if judge_profile else None,
        baseline_run_id=baseline.id if baseline else None,
        total_cases=len(cases),
        completed_cases=0,
        passed_cases=0,
        failed_cases=0,
        error_cases=0,
        aggregate_scores_json={},
        regression_summary_json={},
        langfuse_experiment_name="scientific-rd/evaluation/{uuid}",
        langfuse_sync_status="disabled" if not settings.langfuse_enabled else "pending",
    )
    db.add(run)
    db.flush()
    run.langfuse_experiment_name = f"scientific-rd/evaluation/{run.id}"
    for ordinal, case in enumerate(cases):
        db.add(
            EvaluationResult(
                evaluation_run_id=run.id,
                evaluation_case_id=case.id,
                ordinal=ordinal,
                status="pending",
                deterministic_scores_json={},
                failure_tags_json=[],
                langfuse_sync_status="disabled" if not settings.langfuse_enabled else "pending",
            )
        )
    db.commit()
    db.refresh(run)
    return run


def _build_replay(
    db: Session, case: EvaluationCase, run: EvaluationRun, settings: Settings
) -> tuple[ScientificAnalysisRun, Finding]:
    profile = resolve_profile(settings, run.model_profile_key)
    prompt = run.prompt_snapshot_json.get("content", "")
    replay = ScientificAnalysisRun(
        project_id=case.project_id,
        purpose="evaluation_replay",
        status="running",
        provider_key="fixture" if profile.provider == "fixture" else "litellm",
        model_profile_key=profile.key,
        structured_output_mode=profile.structured_output_mode,
        requested_model=profile.model,
        prompt_key=run.prompt_key,
        prompt_version=run.prompt_version,
        prompt_sha256=run.prompt_sha256,
        prompt_snapshot_json=copy.deepcopy(run.prompt_snapshot_json),
        output_schema_version=run.output_schema_version,
        workflow_version=run.workflow_version,
        generation_parameters_json=copy.deepcopy(run.generation_parameters_json),
        model_metadata_json={"evaluation_run_id": str(run.id), "evaluation_case_id": str(case.id)},
        langfuse_sync_status="disabled" if not settings.langfuse_enabled else "pending",
        started_at=_now(),
    )
    db.add(replay)
    db.flush()
    db.add(
        AnalysisContextSnapshot(
            analysis_run_id=replay.id,
            schema_version=case.context_schema_version,
            snapshot_json=copy.deepcopy(case.context_snapshot_json),
            snapshot_sha256=_canonical_hash(case.context_snapshot_json),
            size_bytes=len(json.dumps(case.context_snapshot_json, sort_keys=True).encode()),
        )
    )
    db.commit()
    request = AIRequest(
        model=profile.model,
        structured_output_mode=profile.structured_output_mode,
        messages=[
            {"role": "system", "content": prompt},
            {"role": "user", "content": json.dumps(case.context_snapshot_json, sort_keys=True)},
        ],
        response_schema=ScientificAnalysisResponseV1.model_json_schema(),
        timeout=settings.ai_timeout_seconds,
        max_output_tokens=settings.ai_max_output_tokens,
        temperature=0.0,
        metadata={
            "context": case.context_snapshot_json,
            "evaluation_case_id": str(case.id),
            "evaluation_run_id": str(run.id),
        },
    )
    provider = _provider(profile)
    try:
        result = provider.generate_structured(request, ScientificAnalysisResponseV1)
        parsed = ScientificAnalysisResponseV1.model_validate(result.parsed)
        replay.raw_output_text = result.raw_output
        replay.validated_output_json = parsed.model_dump(mode="json")
        replay.resolved_model = result.resolved_model
        replay.provider_response_id = result.response_id
        replay.provider_model_version = result.provider_model_version
        replay.model_metadata_json = {"usage": result.usage, "latency_ms": result.latency_ms}
        context = case.context_snapshot_json
        for ordinal, candidate in enumerate(parsed.findings):
            _make_finding(db, case.project_id, replay.id, ordinal, candidate, context)
        replay.status = "completed"
        replay.completed_at = _now()
        db.commit()
    except (ProviderFailure, ValidationError, ValueError) as exc:
        db.rollback()
        replay = db.get(ScientificAnalysisRun, replay.id)
        replay.status = "failed"
        replay.error_code = getattr(exc, "code", "invalid_provider_response")
        replay.error_message = str(exc)[:2000]
        replay.completed_at = _now()
        db.commit()
        raise
    target = case.finding_snapshot_json.get("replay_target", {})
    expected_ordinal = target.get("source_ordinal", case.finding_snapshot_json.get("ordinal"))
    if not isinstance(expected_ordinal, int) or expected_ordinal < 0:
        raise ReplayTargetFailure(
            "replay_target_missing_ordinal", "replay target ordinal is missing"
        )
    replay_findings = list(
        db.scalars(
            select(Finding)
            .where(
                Finding.analysis_run_id == replay.id,
                Finding.ordinal == expected_ordinal,
            )
            .options(selectinload(Finding.evidence_links))
        ).all()
    )
    finding = replay_findings[0] if replay_findings else None
    if finding is None:
        raise ReplayTargetFailure(
            "replay_target_missing", f"replay produced no Finding at ordinal {expected_ordinal}"
        )
    allowed_claim_types = target.get("allowed_claim_types") or [
        case.finding_snapshot_json.get("claim_type")
    ]
    if finding.claim_type not in allowed_claim_types:
        raise ReplayTargetFailure(
            "replay_target_incompatible_claim_type",
            f"expected {allowed_claim_types}, got {finding.claim_type}",
        )
    expected_causal_target = target.get("causal_target")
    if expected_causal_target is not None:
        actual_causal_target = finding.causal_target_json
        if actual_causal_target is None:
            raise ReplayTargetFailure(
                "replay_target_incompatible_causal_target", "replay target is missing"
            )
        for key in ("baseline_experiment_id", "outcome_experiment_id"):
            if str(actual_causal_target.get(key)) != str(expected_causal_target.get(key)):
                raise ReplayTargetFailure(
                    "replay_target_incompatible_causal_target",
                    f"replay target differs at {key}",
                )
        if sorted(actual_causal_target.get("factor_paths", [])) != sorted(
            expected_causal_target.get("factor_paths", [])
        ):
            raise ReplayTargetFailure(
                "replay_target_incompatible_causal_target", "replay target differs at factor_paths"
            )
        if sorted(map(str, actual_causal_target.get("outcome_measurement_ids", []))) != sorted(
            map(str, expected_causal_target.get("outcome_measurement_ids", []))
        ):
            raise ReplayTargetFailure(
                "replay_target_incompatible_causal_target",
                "replay target differs at outcome_measurement_ids",
            )
    elif finding.causal_target_json is not None:
        raise ReplayTargetFailure(
            "replay_target_incompatible_causal_target", "replay returned an unexpected target"
        )
    return replay, finding


def _contains_codes(items: list[dict[str, Any]], codes: list[str]) -> bool:
    actual = {str(item.get("code")) for item in items}
    return set(codes).issubset(actual)


def deterministic_metrics(
    case: EvaluationCase, finding: Finding | None, replay_ok: bool
) -> dict[str, Any]:
    expected = case.expected_behavior_json or {}
    if not replay_ok or finding is None:
        return {"structured_output_valid": False, "overall_pass": False}
    context_evidence_ids = {
        str(item.get("id")) for item in case.context_snapshot_json.get("evidence", [])
    }
    evidence_ids = {str(item.evidence_record_id) for item in finding.evidence_links}
    required_kinds = set(expected.get("required_direct_support_kinds", []))
    actual_kinds = {str(item.get("kind")) for item in finding.structured_support_json}
    expected_gate = expected.get("expected_gate_status")
    scores: dict[str, Any] = {
        "structured_output_valid": True,
        "all_evidence_ids_allowed": evidence_ids.issubset(context_evidence_ids),
        "citation_roles_valid": all(
            item.role in {"supporting", "contradicting", "contextual"}
            for item in finding.evidence_links
        ),
        "direct_structured_support_valid": all(
            item.get("verified") is True for item in finding.structured_support_json
        ),
        "direct_support_scope_correct": all(
            item.get("support_scope") in {"comparative", "descriptive"}
            for item in finding.structured_support_json
        ),
        "comparison_assertions_correct": all(
            item.get("verified") is True
            for item in finding.structured_support_json
            if item.get("kind") in {"measurement_comparison", "experiment_difference"}
        ),
        "unsupported_claims_absent": finding.evidence_gate_status != "supported"
        or finding.claim_type != "causal_claim",
        "causal_overclaim_guard_correct": finding.claim_type != "causal_claim"
        or finding.evidence_gate_status != "supported",
        "causal_gate_not_upgraded_by_direct_support": finding.claim_type != "causal_claim"
        or finding.evidence_gate_status != "supported",
        "evidence_gate_matches_expected": expected_gate is None
        or finding.evidence_gate_status == expected_gate,
        "comparative_gate_matches_direct_data": finding.claim_type != "comparative_finding"
        or not finding.structured_support_json
        or finding.evidence_gate_status in {"supported", "partially_supported"},
        "required_limitations_present": _contains_codes(
            finding.limitations_json, list(expected.get("required_limitation_codes", []))
        ),
        "required_missing_evidence_present": _contains_codes(
            finding.missing_evidence_json, list(expected.get("required_missing_evidence_codes", []))
        ),
        "required_suggestion_paths_present": True,
        "suggestion_template_valid": (finding.suggested_next_experiment_json or {}).get(
            "validation_status", "valid"
        )
        != "invalid",
    }
    scores["direct_structured_support_valid"] = scores[
        "direct_structured_support_valid"
    ] and required_kinds.issubset(actual_kinds)
    required_claims = set(expected.get("required_claim_types", []))
    scores["unsupported_claims_absent"] = scores["unsupported_claims_absent"] and (
        not required_claims or finding.claim_type in required_claims
    )
    required_evidence = set(expected.get("required_evidence_ids", []))
    scores["all_evidence_ids_allowed"] = scores[
        "all_evidence_ids_allowed"
    ] and required_evidence.issubset(evidence_ids)
    required_paths = set(expected.get("required_suggestion_change_paths", []))
    actual_paths = set(_suggestion_change_paths(finding.suggested_next_experiment_json))
    scores["required_suggestion_paths_present"] = required_paths.issubset(actual_paths)
    if expected.get("direct_structured_support_required"):
        scores["direct_structured_support_required"] = (
            bool(finding.structured_support_json) and scores["direct_structured_support_valid"]
        )
    boolean_values = [value for value in scores.values() if isinstance(value, bool)]
    scores["overall_pass"] = all(boolean_values)
    return scores


def _run_case(
    db: Session,
    run: EvaluationRun,
    result: EvaluationResult,
    case: EvaluationCase,
    settings: Settings,
) -> None:
    result.status = "running"
    db.commit()
    try:
        replay, finding = _build_replay(db, case, run, settings)
        result.replay_analysis_run_id = replay.id
        scores = deterministic_metrics(case, finding, True)
        result.deterministic_scores_json = scores
        result.status = "passed" if scores.get("overall_pass") else "failed"
        result.failure_tags_json = [key for key, value in scores.items() if value is False]
        result.completed_at = _now()
        try:
            LangfuseAdapter(settings).record_evaluation_scores(result, scores)
            if settings.langfuse_enabled:
                result.langfuse_sync_status = "synced"
        except Exception:
            result.langfuse_sync_status = "failed"
        if run.judge_enabled:
            _run_optional_judge(db, run, result, case, finding, settings)
    except ProviderFailure as exc:
        if _is_global_provider_failure(exc):
            db.rollback()
            persisted = db.get(EvaluationResult, result.id)
            if persisted is None:
                raise GlobalEvaluationFailure(exc.code, str(exc)) from exc
            persisted.status = "error"
            persisted.error_code = exc.code
            persisted.error_message = str(exc)[:2000]
            persisted.failure_tags_json = [exc.code]
            persisted.deterministic_scores_json = {
                "structured_output_valid": False,
                "overall_pass": False,
            }
            persisted.completed_at = _now()
            db.commit()
            raise GlobalEvaluationFailure(exc.code, str(exc)) from exc
        db.rollback()
        persisted = db.get(EvaluationResult, result.id)
        if persisted is None:
            raise
        persisted.status = "error"
        persisted.error_code = exc.code
        persisted.error_message = str(exc)[:2000]
        persisted.failure_tags_json = [exc.code]
        persisted.deterministic_scores_json = {
            "structured_output_valid": False,
            "overall_pass": False,
        }
        persisted.completed_at = _now()
    except Exception as exc:
        db.rollback()
        result = db.get(EvaluationResult, result.id)
        result.status = "error"
        result.error_code = getattr(exc, "code", "evaluation_case_error")
        result.error_message = str(exc)[:2000]
        result.failure_tags_json = [result.error_code]
        result.deterministic_scores_json = {"structured_output_valid": False, "overall_pass": False}
        result.completed_at = _now()
    db.commit()


def _run_optional_judge(
    db: Session,
    run: EvaluationRun,
    result: EvaluationResult,
    case: EvaluationCase,
    finding: Finding,
    settings: Settings,
) -> None:
    """Run an isolated semantic judge. Any failure leaves deterministic scores untouched."""
    try:
        from pydantic import BaseModel, ConfigDict, Field

        class JudgeResponse(BaseModel):
            model_config = ConfigDict(extra="forbid")
            overall: str = Field(pattern="^(poor|mixed|good)$")
            rationale: str = Field(min_length=1, max_length=2000)
            dimensions: dict[str, str] = Field(default_factory=dict)

        profile = resolve_profile(
            settings, run.judge_model_profile_key or settings.ai_default_judge_profile
        )
        prompt, prompt_hash = _prompt_registry(settings).get(
            "evaluation_judge", run.judge_prompt_version or 1
        )
        request = AIRequest(
            model=profile.model,
            structured_output_mode=profile.structured_output_mode,
            messages=[
                {"role": "system", "content": prompt},
                {
                    "role": "user",
                    "content": json.dumps(
                        {
                            "expected_behavior": case.expected_behavior_json,
                            "finding": finding.claim,
                            "deterministic_scores": result.deterministic_scores_json,
                        },
                        sort_keys=True,
                    ),
                },
            ],
            response_schema=JudgeResponse.model_json_schema(),
            timeout=settings.ai_timeout_seconds,
            max_output_tokens=1000,
            temperature=0.0,
            metadata={"evaluation_case_id": str(case.id), "evaluation_run_id": str(run.id)},
        )
        judged = _provider(profile).generate_structured(request, JudgeResponse)
        parsed = JudgeResponse.model_validate(judged.parsed)
        result.judge_scores_json = parsed.model_dump(mode="json")
        result.judge_metadata_json = {
            "status": "completed",
            "model_profile_key": profile.key,
            "prompt_key": "evaluation_judge",
            "prompt_version": run.judge_prompt_version or 1,
            "prompt_sha256": prompt_hash,
        }
    except Exception as exc:
        result.judge_scores_json = None
        result.judge_metadata_json = {
            "status": "error",
            "error_code": getattr(exc, "code", "judge_unavailable"),
            "error_message": str(exc)[:500],
        }


def run_evaluation(
    db: Session, run_id: uuid.UUID, settings: Settings | None = None
) -> EvaluationRun:
    settings = settings or Settings()
    run = db.scalar(
        select(EvaluationRun)
        .where(EvaluationRun.id == run_id)
        .options(selectinload(EvaluationRun.results).selectinload(EvaluationResult.evaluation_case))
    )
    if run is None:
        raise LookupError("evaluation run not found")
    if run.status in {"completed", "completed_with_errors", "cancelled", "interrupted"}:
        return run
    run.status = "running"
    run.started_at = _now()
    db.commit()
    global_failure: GlobalEvaluationFailure | None = None
    for result in sorted(run.results, key=lambda item: item.ordinal):
        db.refresh(run)
        if run.status == "cancel_requested":
            result.status = "cancelled"
            result.completed_at = _now()
            db.commit()
            continue
        if result.status != "pending":
            continue
        try:
            _run_case(db, run, result, result.evaluation_case, settings)
        except GlobalEvaluationFailure as exc:
            global_failure = exc
            break
        run.completed_cases = sum(
            item.status in {"passed", "failed", "error", "cancelled"} for item in run.results
        )
        run.passed_cases = sum(item.status == "passed" for item in run.results)
        run.failed_cases = sum(item.status == "failed" for item in run.results)
        run.error_cases = sum(item.status == "error" for item in run.results)
        db.commit()
    if global_failure is not None:
        for pending in run.results:
            if pending.status == "pending":
                pending.status = "error"
                pending.error_code = f"run_aborted_{global_failure.code}"[:120]
                pending.error_message = (
                    "Evaluation stopped because a run-wide provider/configuration failure "
                    f"occurred: {str(global_failure)[:1800]}"
                )
                pending.failure_tags_json = [pending.error_code]
                pending.deterministic_scores_json = {
                    "structured_output_valid": False,
                    "overall_pass": False,
                }
                pending.completed_at = _now()
        run.error_code = global_failure.code
        run.error_message = str(global_failure)[:2000]
        run.status = "failed"
    elif run.status == "cancel_requested":
        run.status = "cancelled"
    elif run.error_cases:
        run.status = "completed_with_errors"
    elif run.failed_cases:
        run.status = "completed_with_errors"
    else:
        run.status = "completed"
    run.completed_cases = sum(
        item.status in {"passed", "failed", "error", "cancelled"} for item in run.results
    )
    run.passed_cases = sum(item.status == "passed" for item in run.results)
    run.failed_cases = sum(item.status == "failed" for item in run.results)
    run.error_cases = sum(item.status == "error" for item in run.results)
    run.aggregate_scores_json = {
        "total": run.total_cases,
        "passed": run.passed_cases,
        "failed": run.failed_cases,
        "errors": run.error_cases,
    }
    if run.baseline_run_id is not None:
        baseline_results = list(
            db.scalars(
                select(EvaluationResult).where(
                    EvaluationResult.evaluation_run_id == run.baseline_run_id
                )
            ).all()
        )
        current_by_case = {str(item.evaluation_case_id): item for item in run.results}
        baseline_by_case = {str(item.evaluation_case_id): item for item in baseline_results}
        improved = regressed = unchanged = 0
        for case_id, current in current_by_case.items():
            previous = baseline_by_case.get(case_id)
            if previous is None:
                continue
            current_pass = bool(current.deterministic_scores_json.get("overall_pass"))
            previous_pass = bool(previous.deterministic_scores_json.get("overall_pass"))
            if current_pass and not previous_pass:
                improved += 1
            elif previous_pass and not current_pass:
                regressed += 1
            else:
                unchanged += 1
        run.regression_summary_json = {
            "baseline_run_id": str(run.baseline_run_id),
            "dataset_version": run.dataset_version,
            "improved_cases": improved,
            "regressed_cases": regressed,
            "unchanged_cases": unchanged,
        }
    run.completed_at = _now()
    db.commit()
    return run


def run_evaluation_background(run_id: uuid.UUID) -> None:
    with SessionLocal() as db:
        try:
            run_evaluation(db, run_id)
        except Exception:
            db.rollback()


def mark_interrupted_runs(db: Session) -> int:
    rows = list(
        db.scalars(
            select(EvaluationRun).where(
                EvaluationRun.status.in_(["queued", "running", "cancel_requested"])
            )
        ).all()
    )
    for row in rows:
        row.status = "interrupted"
        row.error_code = "process_restarted"
        row.error_message = "Evaluation was interrupted by API process restart."
        row.completed_at = _now()
    if rows:
        db.commit()
    return len(rows)


def case_out(case: EvaluationCase) -> EvaluationCaseOut:
    return EvaluationCaseOut.model_validate(case, from_attributes=True)


def result_out(result: EvaluationResult) -> EvaluationResultOut:
    return EvaluationResultOut(
        id=result.id,
        evaluation_run_id=result.evaluation_run_id,
        evaluation_case_id=result.evaluation_case_id,
        ordinal=result.ordinal,
        status=result.status,
        replay_analysis_run_id=result.replay_analysis_run_id,
        deterministic_scores_json=result.deterministic_scores_json,
        judge_scores_json=result.judge_scores_json,
        judge_metadata_json=result.judge_metadata_json,
        failure_tags_json=result.failure_tags_json,
        error_code=result.error_code,
        error_message=result.error_message,
        langfuse_trace_id=result.langfuse_trace_id,
        langfuse_sync_status=result.langfuse_sync_status,
        created_at=result.created_at,
        completed_at=result.completed_at,
        evaluation_case=case_out(result.evaluation_case) if result.evaluation_case else None,
    )


def run_out(run: EvaluationRun) -> EvaluationRunOut:
    return EvaluationRunOut(
        id=run.id,
        project_id=run.project_id,
        status=run.status,
        dataset_version=run.dataset_version,
        model_profile_key=run.model_profile_key,
        structured_output_mode=run.structured_output_mode,
        requested_model=run.requested_model,
        prompt_key=run.prompt_key,
        prompt_version=run.prompt_version,
        prompt_sha256=run.prompt_sha256,
        prompt_snapshot_json=run.prompt_snapshot_json,
        workflow_version=run.workflow_version,
        output_schema_version=run.output_schema_version,
        generation_parameters_json=run.generation_parameters_json,
        judge_enabled=run.judge_enabled,
        judge_model_profile_key=run.judge_model_profile_key,
        judge_structured_output_mode=run.judge_structured_output_mode,
        judge_prompt_version=run.judge_prompt_version,
        baseline_run_id=run.baseline_run_id,
        total_cases=run.total_cases,
        completed_cases=run.completed_cases,
        passed_cases=run.passed_cases,
        failed_cases=run.failed_cases,
        error_cases=run.error_cases,
        aggregate_scores_json=run.aggregate_scores_json,
        regression_summary_json=run.regression_summary_json,
        error_code=run.error_code,
        error_message=run.error_message,
        langfuse_experiment_name=run.langfuse_experiment_name,
        langfuse_sync_status=run.langfuse_sync_status,
        langfuse_error=run.langfuse_error,
        created_at=run.created_at,
        started_at=run.started_at,
        completed_at=run.completed_at,
        results=[result_out(item) for item in sorted(run.results, key=lambda item: item.ordinal)],
    )
