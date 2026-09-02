from __future__ import annotations

import copy
import json
import uuid
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from pydantic import ValidationError
from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.ai_provider import (
    AIRequest,
    AIResult,
    FixtureProvider,
    LangfuseAdapter,
    LiteLLMProvider,
    ModelProfile,
    PromptRegistry,
    ProviderFailure,
    load_model_profiles,
)
from app.context_builder import (
    ContextValidationError,
    _pointer_get,
    build_scientific_context,
    sha256_json,
)
from app.core.config import Settings
from app.models import (
    AnalysisContextSnapshot,
    Finding,
    FindingEvidenceLink,
    ReviewDecision,
    ScientificAnalysisRun,
)
from app.schemas import (
    AnalysisRunCreate,
    AnalysisRunOut,
    EvidenceLinkOut,
    FindingCandidateV1,
    FindingOut,
    ReviewDecisionCreate,
    ReviewDecisionOut,
    ScientificAnalysisResponseV1,
)
from app.validation import validate_template_data


class AnalysisFailure(RuntimeError):
    def __init__(self, code: str, message: str, run_id: uuid.UUID) -> None:
        super().__init__(message)
        self.code = code
        self.run_id = run_id


TRANSIENT_PROVIDER_CODES = {
    "provider_timeout",
    "provider_rate_limit",
    "provider_unavailable",
    "provider_server_error",
}


def _generate_with_retry(
    provider: Any, request: AIRequest, response_model: type[ScientificAnalysisResponseV1]
) -> tuple[AIResult, int]:
    attempts = 0
    while True:
        attempts += 1
        try:
            return provider.generate_structured(request, response_model), attempts
        except ProviderFailure as exc:
            if attempts == 1 and exc.retryable and exc.code in TRANSIENT_PROVIDER_CODES:
                continue
            raise


def resolve_profile(settings: Settings, key: str) -> ModelProfile:
    profiles = load_model_profiles(settings)
    profile = profiles.get(key)
    if profile is None:
        raise ProviderFailure("model_profile_not_found", f"model profile {key} not found")
    if profile.provider == "fixture":
        return profile
    available, reason = LiteLLMProvider.capability(profile)
    if not available:
        raise ProviderFailure("unsupported_structured_output", reason or "profile unavailable")
    return profile


def list_profiles(settings: Settings) -> list[ModelProfile]:
    result: list[ModelProfile] = []
    for profile in load_model_profiles(settings).values():
        if profile.provider == "fixture":
            result.append(profile)
            continue
        available, reason = LiteLLMProvider.capability(profile)
        result.append(
            ModelProfile(
                key=profile.key,
                model=profile.model,
                label=profile.label,
                provider=profile.provider,
                structured_output_mode=profile.structured_output_mode,
                available=available,
                capability_reason=reason,
            )
        )
    return result


def _provider(profile: ModelProfile) -> FixtureProvider | LiteLLMProvider:
    return FixtureProvider() if profile.provider == "fixture" else LiteLLMProvider(profile)


def _prompt_registry(settings: Settings) -> PromptRegistry:
    root = settings.ai_prompt_root
    if not root.is_absolute() and not root.exists():
        root = (Path(__file__).parent / "prompts").resolve()
    return PromptRegistry(root)


def _now() -> datetime:
    return datetime.now(UTC)


def _pointer_set(document: Any, pointer: str, value: Any) -> None:
    if pointer in {"", "/"}:
        raise ValueError("root replacement is not supported")
    segments = [
        segment.replace("~1", "/").replace("~0", "~") for segment in pointer.lstrip("/").split("/")
    ]
    current = document
    for segment in segments[:-1]:
        if segment.startswith("@") and isinstance(current, list):
            name = segment[1:]
            match = next(
                (item for item in current if isinstance(item, dict) and item.get("name") == name),
                None,
            )
            if match is None:
                match = {"name": name}
                current.append(match)
            current = match
        elif isinstance(current, dict):
            current = current.setdefault(segment, {})
        elif isinstance(current, list) and segment.isdigit():
            current = current[int(segment)]
        else:
            raise ValueError(f"invalid JSON pointer path {pointer}")
    final = segments[-1]
    if final.startswith("@") and isinstance(current, list):
        name = final[1:]
        for index, item in enumerate(current):
            if isinstance(item, dict) and item.get("name") == name:
                current[index] = copy.deepcopy(value)
                return
        current.append(copy.deepcopy(value))
    elif isinstance(current, dict):
        current[final] = copy.deepcopy(value)
    elif isinstance(current, list) and final.isdigit():
        current[int(final)] = copy.deepcopy(value)
    else:
        raise ValueError(f"invalid JSON pointer path {pointer}")


def _pointer_remove(document: Any, pointer: str) -> None:
    if pointer in {"", "/"}:
        raise ValueError("root removal is not supported")
    segments = [
        segment.replace("~1", "/").replace("~0", "~") for segment in pointer.lstrip("/").split("/")
    ]
    current = document
    for segment in segments[:-1]:
        if segment.startswith("@") and isinstance(current, list):
            current = next(
                item
                for item in current
                if isinstance(item, dict) and item.get("name") == segment[1:]
            )
        elif isinstance(current, dict):
            current = current[segment]
        elif isinstance(current, list) and segment.isdigit():
            current = current[int(segment)]
        else:
            raise KeyError(pointer)
    final = segments[-1]
    if final.startswith("@") and isinstance(current, list):
        current[:] = [
            item
            for item in current
            if not (isinstance(item, dict) and item.get("name") == final[1:])
        ]
    elif isinstance(current, dict):
        current.pop(final, None)
    elif isinstance(current, list) and final.isdigit():
        current.pop(int(final))
    else:
        raise KeyError(pointer)


def _normalize_suggestion(
    candidate: FindingCandidateV1, context: dict[str, Any]
) -> dict[str, Any] | None:
    suggestion = candidate.suggested_next_experiment
    if suggestion is None:
        return None
    base = next(
        (
            item
            for item in context["experiments"]
            if item["experiment_id"] == str(suggestion.base_experiment_id)
        ),
        None,
    )
    if base is None:
        return {"validation_status": "invalid", "error": "base experiment is not in frozen context"}
    structured = copy.deepcopy(base["experiment_snapshot"]["structured_data"])
    try:
        for operation in suggestion.change_operations:
            if operation.op == "set":
                _pointer_set(structured, operation.path, operation.value)
            else:
                _pointer_remove(structured, operation.path)
        validate_template_data(base.get("template_schema", {}), structured)
    except (KeyError, ValueError, StopIteration) as exc:
        # Template schema is stored separately in the frozen context.
        return {"validation_status": "invalid", "error": str(exc)}
    prefill = {
        "title": suggestion.title,
        "objective": suggestion.objective,
        "template_id": base["experiment_snapshot"].get("template_id"),
        "template_version": base["experiment_snapshot"].get("template_version"),
        "parent_experiment_id": suggestion.base_experiment_id,
        "structured_data": structured,
        "control_strategy": suggestion.control_strategy,
        "addresses_missing_evidence_codes": suggestion.addresses_missing_evidence_codes,
        "change_operations": [
            item.model_dump(mode="json") for item in suggestion.change_operations
        ],
    }
    return {
        "validation_status": "valid",
        "template_id": base["experiment_snapshot"].get("template_id"),
        "template_version": base["experiment_snapshot"].get("template_version"),
        "prefill": prefill,
        "suggestion_hash": sha256_json(prefill),
    }


def _experiment_data(
    context: dict[str, Any], experiment_id: uuid.UUID, revision_number: int
) -> dict[str, Any]:
    for item in context["experiments"]:
        if (
            item["experiment_id"] == str(experiment_id)
            and item["revision_number"] == revision_number
        ):
            return item["experiment_snapshot"]["structured_data"]
    raise ValueError("experiment revision is not in frozen context")


def _validate_direct_support(
    candidate: FindingCandidateV1, context: dict[str, Any]
) -> list[dict[str, Any]]:
    assertions = list(candidate.structured_support_assertions)
    assertions.extend(
        {
            "kind": "measurement_comparison",
            **item.model_dump(mode="json"),
        }
        for item in candidate.comparison_assertions
    )
    measurements = {item["id"]: item for item in context["measurements"]}
    artifacts: list[dict[str, Any]] = []
    for assertion in assertions:
        data = assertion.model_dump(mode="json") if hasattr(assertion, "model_dump") else assertion
        kind = data["kind"]
        if kind == "measurement_comparison":
            left = measurements.get(str(data["left_measurement_id"]))
            right = measurements.get(str(data["right_measurement_id"]))
            if left is None or right is None:
                raise ValueError("invalid measurement comparison reference")
            left_value = left["summary_json"].get(data["metric"])
            right_value = right["summary_json"].get(data["metric"])
            relation = data["relation"]
            valid = (
                right_value > left_value
                if relation == "greater_than"
                else right_value < left_value
                if relation == "less_than"
                else abs(right_value - left_value) <= max(1e-9, abs(left_value) * 1e-6)
            )
            if not valid:
                raise ValueError("invalid_comparison_assertion")
            artifacts.append(
                {
                    "kind": kind,
                    "left_measurement_id": str(data["left_measurement_id"]),
                    "right_measurement_id": str(data["right_measurement_id"]),
                    "metric": data["metric"],
                    "relation": relation,
                    "left_value": left_value,
                    "right_value": right_value,
                    "support_scope": "comparative",
                    "verified": True,
                }
            )
        elif kind == "experiment_difference":
            left = _experiment_data(
                context, data["left_experiment_id"], data["left_revision_number"]
            )
            right = _experiment_data(
                context, data["right_experiment_id"], data["right_revision_number"]
            )
            left_exists, left_value = _pointer_get(left, data["path"])
            right_exists, right_value = _pointer_get(right, data["path"])
            actual = (
                "added"
                if not left_exists and right_exists
                else "removed"
                if left_exists and not right_exists
                else "equal"
                if left_value == right_value
                else "changed"
            )
            if actual != data["relation"]:
                raise ValueError("invalid_experiment_difference_assertion")
            artifacts.append(
                {
                    **data,
                    "left_value": left_value if left_exists else None,
                    "right_value": right_value if right_exists else None,
                    "support_scope": "comparative",
                    "verified": True,
                }
            )
        elif kind == "revision_observation":
            value = _experiment_data(context, data["experiment_id"], data["revision_number"])
            exists, observed = _pointer_get(value, data["path"])
            operator = data["operator"]
            valid = (
                (operator == "present" and exists)
                or (operator == "absent" and not exists)
                or (operator == "equals" and exists and observed == data.get("expected_value"))
            )
            if not valid:
                raise ValueError("invalid_revision_observation_assertion")
            artifacts.append(
                {
                    **data,
                    "observed_value": observed if exists else None,
                    "support_scope": "descriptive",
                    "verified": True,
                }
            )
        else:
            raise ValueError("unsupported structured support kind")
    return artifacts


def _validate_evidence_links(
    candidate: FindingCandidateV1, context: dict[str, Any]
) -> list[dict[str, Any]]:
    allowed = {item["id"]: item for item in context["evidence"]}
    links: list[dict[str, Any]] = []
    seen: set[str] = set()
    for raw in candidate.evidence_links:
        evidence_id = str(raw.get("evidence_id", ""))
        role = raw.get("role")
        if evidence_id not in allowed:
            raise ValueError("invalid_evidence_reference")
        if evidence_id in seen or role not in {"supporting", "contradicting", "contextual"}:
            raise ValueError("invalid_evidence_role")
        stance = allowed[evidence_id]["stance"]
        if role == "supporting" and stance != "supports":
            raise ValueError("supporting EvidenceRecord stance mismatch")
        if role == "contradicting" and stance != "contradicts":
            raise ValueError("contradicting EvidenceRecord stance mismatch")
        seen.add(evidence_id)
        links.append(
            {
                "evidence_record_id": evidence_id,
                "role": role,
                "rationale": str(raw.get("rationale", ""))[:2000],
                "evidence_snapshot_json": copy.deepcopy(allowed[evidence_id]),
            }
        )
    return links


def _causal_changed_paths(context: dict[str, Any], candidate: FindingCandidateV1) -> list[str]:
    target = candidate.causal_target
    if target is None:
        return []
    baseline = str(target.baseline_experiment_id)
    outcome = str(target.outcome_experiment_id)
    paths: set[str] = set()
    for item in context.get("factor_differences", []):
        pair = {item.get("left_experiment_id"), item.get("right_experiment_id")}
        if pair == {baseline, outcome} and item.get("differs"):
            path = item["path"]
            if "/@" in path:
                path = path[: path.index("/@") + 1] + path[path.index("/@") + 1 :].split("/", 1)[0]
            paths.add(path)
    return sorted(paths)


def _gate(
    candidate: FindingCandidateV1,
    direct: list[dict[str, Any]],
    links: list[dict[str, Any]],
    context: dict[str, Any],
) -> tuple[str, dict[str, Any]]:
    supporting = [item for item in links if item["role"] == "supporting"]
    contradicting = [item for item in links if item["role"] == "contradicting"]
    changed_paths = _causal_changed_paths(context, candidate)
    reasons: list[str] = []
    if candidate.claim_type == "causal_claim":
        if contradicting and not supporting:
            status = "contradicted"
            reasons.append("valid_direct_contradiction")
        elif len(changed_paths) > 1:
            status = "insufficient_evidence"
            reasons.extend(["confounded_variables", "missing_isolating_control"])
        elif any(item.code == "missing_isolating_control" for item in candidate.missing_evidence):
            status = "insufficient_evidence"
            reasons.append("missing_isolating_control")
        elif not supporting:
            status = "insufficient_evidence"
            reasons.append("direct_structured_support_is_not_causal_proof")
        else:
            status = "partially_supported"
            reasons.append("causal_claim_capped_without_formal_design")
    else:
        support_count = len(direct) + len(supporting)
        if contradicting and not support_count:
            status = "contradicted"
            reasons.append("curated_contradiction_without_support")
        elif contradicting and support_count:
            status = "partially_supported"
            reasons.append("support_and_contradiction_coexist")
        elif not support_count:
            status = "insufficient_evidence"
            reasons.append("no_verified_support")
        elif candidate.missing_evidence or candidate.limitations:
            status = "partially_supported"
            reasons.append("material_limitations_present")
        else:
            status = "supported"
            reasons.append("verified_direct_or_curated_support")
    return status, {
        "policy_version": 1,
        "valid_direct_structured_support": direct,
        "valid_curated_supporting_evidence_ids": [
            item["evidence_record_id"] for item in supporting
        ],
        "valid_curated_contradicting_evidence_ids": [
            item["evidence_record_id"] for item in contradicting
        ],
        "changed_factor_paths": changed_paths,
        "reason_codes": sorted(set(reasons)),
        "causal_support_excluded": candidate.claim_type == "causal_claim",
    }


def _make_finding(
    db: Session,
    project_id: uuid.UUID,
    run_id: uuid.UUID,
    ordinal: int,
    candidate: FindingCandidateV1,
    context: dict[str, Any],
) -> Finding:
    direct = _validate_direct_support(candidate, context)
    links = _validate_evidence_links(candidate, context)
    gate_status, gate_rationale = _gate(candidate, direct, links, context)
    suggestion = _normalize_suggestion(candidate, context)
    row = Finding(
        project_id=project_id,
        analysis_run_id=run_id,
        ordinal=ordinal,
        claim=candidate.claim,
        claim_type=candidate.claim_type,
        confidence_label=candidate.confidence_label,
        confidence_rationale=candidate.confidence_rationale,
        applicability_scope=candidate.applicability_scope,
        limitations_json=[item.model_dump(mode="json") for item in candidate.limitations],
        risks_json=[item.model_dump(mode="json") for item in candidate.risks],
        missing_evidence_json=[item.model_dump(mode="json") for item in candidate.missing_evidence],
        comparison_assertions_json=[
            item.model_dump(mode="json") for item in candidate.comparison_assertions
        ],
        structured_support_json=direct,
        causal_target_json=candidate.causal_target.model_dump(mode="json")
        if candidate.causal_target
        else None,
        suggested_next_experiment_json=suggestion,
        model_proposed_gate_status=candidate.proposed_gate.status,
        model_proposed_gate_rationale=candidate.proposed_gate.rationale,
        evidence_gate_status=gate_status,
        evidence_gate_rationale_json=gate_rationale,
        gate_policy_version=1,
        review_status="pending_review",
    )
    db.add(row)
    db.flush()
    for link in links:
        db.add(
            FindingEvidenceLink(
                finding_id=row.id,
                evidence_record_id=uuid.UUID(link["evidence_record_id"]),
                role=link["role"],
                rationale=link["rationale"],
                evidence_snapshot_json=link["evidence_snapshot_json"],
            )
        )
    return row


def create_analysis_run(
    db: Session,
    project_id: uuid.UUID,
    payload: AnalysisRunCreate,
    settings: Settings,
    *,
    fixture_response: dict[str, Any] | None = None,
) -> ScientificAnalysisRun:
    profile = resolve_profile(settings, payload.model_profile_key)
    registry = _prompt_registry(settings)
    prompt, prompt_hash = registry.get("scientific_analysis", payload.prompt_version)
    run = ScientificAnalysisRun(
        project_id=project_id,
        purpose="interactive",
        status="building_context",
        provider_key="fixture" if profile.provider == "fixture" else "litellm",
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
        output_schema_version=1,
        workflow_version=1,
        generation_parameters_json={
            "temperature": 0.0,
            "max_output_tokens": settings.ai_max_output_tokens,
            "timeout_seconds": settings.ai_timeout_seconds,
        },
        model_metadata_json={},
        langfuse_sync_status="disabled" if not settings.langfuse_enabled else "pending",
    )
    db.add(run)
    db.commit()
    db.refresh(run)
    attempts = 0
    try:
        context, context_hash, context_size = build_scientific_context(
            db, project_id, payload, settings
        )
        db.add(
            AnalysisContextSnapshot(
                analysis_run_id=run.id,
                schema_version=1,
                snapshot_json=context,
                snapshot_sha256=context_hash,
                size_bytes=context_size,
            )
        )
        run.status = "running"
        run.started_at = _now()
        db.commit()
        request = AIRequest(
            model=profile.model,
            structured_output_mode=profile.structured_output_mode,
            messages=[
                {"role": "system", "content": prompt},
                {
                    "role": "user",
                    "content": json.dumps(context, sort_keys=True, separators=(",", ":")),
                },
            ],
            response_schema=ScientificAnalysisResponseV1.model_json_schema(),
            timeout=settings.ai_timeout_seconds,
            max_output_tokens=settings.ai_max_output_tokens,
            temperature=0.0,
            metadata={
                "context": context,
                "analysis_run_id": str(run.id),
                "context_sha256": context_hash,
                "prompt_key": "scientific_analysis",
                "prompt_version": payload.prompt_version,
                "prompt_sha256": prompt_hash,
                "output_schema_version": 1,
                "workflow_version": 1,
                "model_profile_key": profile.key,
            },
        )
        provider: Any = (
            FixtureProvider(fixture_response)
            if fixture_response is not None
            else _provider(profile)
        )
        result, attempts = _generate_with_retry(provider, request, ScientificAnalysisResponseV1)
        parsed = ScientificAnalysisResponseV1.model_validate(result.parsed)
        run.raw_output_text = result.raw_output
        run.validated_output_json = parsed.model_dump(mode="json")
        run.resolved_model = result.resolved_model
        run.provider_response_id = result.response_id
        run.provider_model_version = result.provider_model_version
        run.model_metadata_json = {
            "usage": result.usage,
            "finish_reason": result.finish_reason,
            "latency_ms": result.latency_ms,
            "context_sha256": context_hash,
            "attempt_count": attempts,
            "retry_count": attempts - 1,
        }
        for ordinal, candidate in enumerate(parsed.findings):
            _make_finding(db, project_id, run.id, ordinal, candidate, context)
        run.status = "completed"
        run.completed_at = _now()
        db.commit()
        try:
            trace_id = LangfuseAdapter(settings).record_analysis(run.id, request, result)
            run.langfuse_trace_id = trace_id
            if settings.langfuse_enabled:
                run.langfuse_sync_status = "synced"
            db.commit()
        except ProviderFailure as exc:
            run.langfuse_sync_status = "failed"
            run.langfuse_error = str(exc)[:2000]
            db.commit()
        return run
    except (ContextValidationError, ProviderFailure, ValidationError, ValueError) as exc:
        db.rollback()
        failed = db.get(ScientificAnalysisRun, run.id)
        if failed is None:
            raise
        failed.status = "failed"
        failed.error_code = getattr(exc, "code", "invalid_provider_response")
        failed.error_message = str(exc)[:2000]
        failed.model_metadata_json = {
            **(failed.model_metadata_json or {}),
            "attempt_count": attempts,
            "retry_count": max(attempts - 1, 0),
        }
        failed.completed_at = _now()
        db.commit()
        raise AnalysisFailure(
            failed.error_code or "analysis_failed",
            failed.error_message or "analysis failed",
            failed.id,
        ) from exc


def _load_finding(db: Session, finding_id: uuid.UUID) -> Finding | None:
    return db.scalar(
        select(Finding)
        .where(Finding.id == finding_id)
        .options(selectinload(Finding.evidence_links), selectinload(Finding.reviews))
    )


def create_review(
    db: Session, finding_id: uuid.UUID, payload: ReviewDecisionCreate
) -> ReviewDecision:
    finding = _load_finding(db, finding_id)
    if finding is None:
        raise LookupError("finding not found")
    latest = db.scalar(
        select(ReviewDecision)
        .where(ReviewDecision.finding_id == finding_id)
        .order_by(ReviewDecision.sequence_number.desc())
    )
    if latest is not None:
        if payload.supersedes_review_id != latest.id:
            raise ValueError("review must supersede the latest decision")
    elif payload.supersedes_review_id is not None:
        raise ValueError("no review exists to supersede")
    decision = ReviewDecision(
        finding_id=finding_id,
        sequence_number=(latest.sequence_number + 1) if latest else 1,
        decision=payload.decision,
        reviewer_name=payload.reviewer_name,
        reason_code=payload.reason_code,
        comment=payload.comment,
        supersedes_review_id=payload.supersedes_review_id,
    )
    db.add(decision)
    finding.review_status = {
        "accept": "accepted",
        "reject": "rejected",
        "needs_evidence": "needs_evidence",
    }[payload.decision]
    db.commit()
    db.refresh(decision)
    return decision


def finding_out(finding: Finding) -> FindingOut:
    return FindingOut(
        id=finding.id,
        project_id=finding.project_id,
        analysis_run_id=finding.analysis_run_id,
        ordinal=finding.ordinal,
        claim=finding.claim,
        claim_type=finding.claim_type,
        confidence_label=finding.confidence_label,
        confidence_rationale=finding.confidence_rationale,
        applicability_scope=finding.applicability_scope,
        limitations_json=finding.limitations_json,
        risks_json=finding.risks_json,
        missing_evidence_json=finding.missing_evidence_json,
        comparison_assertions_json=finding.comparison_assertions_json,
        structured_support_json=finding.structured_support_json,
        causal_target_json=finding.causal_target_json,
        suggested_next_experiment_json=finding.suggested_next_experiment_json,
        model_proposed_gate_status=finding.model_proposed_gate_status,
        model_proposed_gate_rationale=finding.model_proposed_gate_rationale,
        evidence_gate_status=finding.evidence_gate_status,
        evidence_gate_rationale_json=finding.evidence_gate_rationale_json,
        gate_policy_version=finding.gate_policy_version,
        review_status=finding.review_status,
        evidence_links=[EvidenceLinkOut.model_validate(item) for item in finding.evidence_links],
        reviews=[ReviewDecisionOut.model_validate(item) for item in finding.reviews],
        created_at=finding.created_at,
    )


def analysis_run_out(run: ScientificAnalysisRun) -> AnalysisRunOut:
    snapshot = run.context_snapshot
    return AnalysisRunOut(
        id=run.id,
        project_id=run.project_id,
        purpose=run.purpose,
        status=run.status,
        provider_key=run.provider_key,
        model_profile_key=run.model_profile_key,
        structured_output_mode=run.structured_output_mode,
        requested_model=run.requested_model,
        resolved_model=run.resolved_model,
        provider_response_id=run.provider_response_id,
        provider_model_version=run.provider_model_version,
        prompt_key=run.prompt_key,
        prompt_version=run.prompt_version,
        prompt_sha256=run.prompt_sha256,
        output_schema_version=run.output_schema_version,
        workflow_version=run.workflow_version,
        generation_parameters_json=run.generation_parameters_json,
        model_metadata_json=run.model_metadata_json,
        validated_output_json=run.validated_output_json,
        error_code=run.error_code,
        error_message=run.error_message,
        langfuse_trace_id=run.langfuse_trace_id,
        langfuse_sync_status=run.langfuse_sync_status,
        started_at=run.started_at,
        completed_at=run.completed_at,
        created_at=run.created_at,
        context_snapshot=(
            {
                "id": snapshot.id,
                "analysis_run_id": snapshot.analysis_run_id,
                "schema_version": snapshot.schema_version,
                "snapshot_json": snapshot.snapshot_json,
                "snapshot_sha256": snapshot.snapshot_sha256,
                "size_bytes": snapshot.size_bytes,
                "created_at": snapshot.created_at,
            }
            if snapshot
            else None
        ),
        findings=[finding_out(item) for item in run.findings],
    )
