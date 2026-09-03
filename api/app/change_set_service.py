from __future__ import annotations

import uuid
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import desc, select
from sqlalchemy.orm import Session

from app.data_service import create_data_record
from app.execution_service import get_execution, update_execution
from app.experiment_record_service import (
    create_experiment_record,
    get_experiment_record,
    update_experiment_record,
)
from app.models import ChangeSet, ObjectRevision
from app.sample_record_service import create_sample_record, get_sample_record, update_sample_record
from app.schemas import (
    ChangeSetProposal,
    ChangeSetReview,
    DataRecordCreate,
    ExperimentRecordCreate,
    ExperimentRecordPut,
    SampleExecutionUpdate,
    SampleRecordCreate,
    SampleRecordPut,
)


def _record_for_operation(db: Session, proposal: ChangeSetProposal) -> dict[str, Any] | None:
    if proposal.target_id is None:
        return None
    if proposal.operation_kind in {"update_sample_record", "create_sample_record"}:
        return get_sample_record(db, proposal.target_id)
    if proposal.operation_kind in {"update_experiment_record", "create_experiment_record"}:
        return get_experiment_record(db, proposal.target_id)
    if proposal.operation_kind == "update_execution":
        return get_execution(db, proposal.target_id)
    return None


def _validate_payload(db: Session, proposal: ChangeSetProposal) -> dict[str, Any]:
    body = proposal.request_payload_jsonb
    operation = proposal.operation_kind
    if operation == "create_sample_record":
        parsed = SampleRecordCreate.model_validate(body)
        if parsed.project_scope_id != proposal.project_scope_id:
            raise ValueError("ChangeSet project scope does not match Sample Record")
    elif operation == "update_sample_record":
        if proposal.target_id is None or proposal.base_record_sha256 is None:
            raise ValueError("Sample update proposals require target_id and base_record_sha256")
        parsed = SampleRecordPut.model_validate(body)
    elif operation == "create_experiment_record":
        parsed = ExperimentRecordCreate.model_validate(body)
        if parsed.project_scope_id != proposal.project_scope_id:
            raise ValueError("ChangeSet project scope does not match Experiment Record")
    elif operation == "update_experiment_record":
        if proposal.target_id is None or proposal.base_record_sha256 is None:
            raise ValueError("Experiment update proposals require target_id and base_record_sha256")
        parsed = ExperimentRecordPut.model_validate(body)
    elif operation == "create_data_record":
        parsed = DataRecordCreate.model_validate(body)
        if parsed.project_scope_id != proposal.project_scope_id:
            raise ValueError("ChangeSet project scope does not match Data Record")
    elif operation == "update_execution":
        if proposal.target_id is None or proposal.base_record_sha256 is None:
            raise ValueError("Execution update proposals require target_id and base_record_sha256")
        parsed = SampleExecutionUpdate.model_validate(body)
    else:
        raise ValueError("unsupported ChangeSet operation")
    return parsed.model_dump(mode="json")


def _diff(current: dict[str, Any] | None, requested: dict[str, Any]) -> list[dict[str, Any]]:
    if current is None:
        return [{"key": "create", "label": "Create record", "before": None, "after": requested}]
    changes: list[dict[str, Any]] = []

    def add(key: str, label: str, before: Any, after: Any) -> None:
        if before != after:
            changes.append({"key": key, "label": label, "before": before, "after": after})

    if isinstance(requested.get("sample"), dict) and isinstance(current.get("sample"), dict):
        sample_before = current["sample"]
        sample_after = requested["sample"]
        for field in ("title", "status", "properties_jsonb", "content_document"):
            if field in sample_after:
                add(
                    f"sample.{field}",
                    f"Sample {field.replace('_', ' ')}",
                    sample_before.get(field),
                    sample_after[field],
                )
    if isinstance(requested.get("experiment"), dict) and isinstance(
        current.get("experiment"), dict
    ):
        experiment_before = current["experiment"]
        experiment_after = requested["experiment"]
        for field in ("title", "status", "properties_jsonb", "content_document"):
            if field in experiment_after:
                add(
                    f"experiment.{field}",
                    f"Experiment {field.replace('_', ' ')}",
                    experiment_before.get(field),
                    experiment_after[field],
                )
    if "members" in requested:
        before_members = current.get("members", [])
        after_members = requested.get("members", [])
        add(
            "experiment.members",
            "Experiment Sample members",
            len(before_members),
            len(after_members),
        )
        add(
            "experiment.member_order",
            "Experiment member order",
            [str(item.get("sample", {}).get("id")) for item in before_members],
            [str(item.get("sample_id")) for item in after_members],
        )
    if "steps" in requested:
        before_steps = current.get("steps", [])
        after_steps = requested.get("steps", [])
        add("sample.steps", "Process step count", len(before_steps), len(after_steps))
        for index, step in enumerate(after_steps):
            before = before_steps[index] if index < len(before_steps) else {}
            process_before = before.get("process", {})
            for field in ("title", "status", "properties_jsonb"):
                if field in step:
                    add(
                        f"sample.step.{index}.{field}",
                        f"Process step {index + 1} {field.replace('_', ' ')}",
                        process_before.get(field),
                        step[field],
                    )
            before_resources = {
                str(item.get("object", {}).get("id")): item for item in before.get("resources", [])
            }
            for resource in step.get("resources", []):
                resource_id = str(resource.get("target_object_id"))
                before_resource = before_resources.get(resource_id, {})
                add(
                    f"sample.step.{index}.resource.{resource_id}.usage",
                    f"Process step {index + 1} resource usage",
                    before_resource.get("usage_values", {}),
                    resource.get("usage_values", {}),
                )
    if "observations" in requested:
        add(
            "execution.observations",
            "Execution observations",
            len(current.get("observations", [])),
            len(requested["observations"]),
        )
    if "deviation_notes" in requested:
        add(
            "execution.deviation_notes",
            "Execution deviation notes",
            len(current.get("deviation_notes", [])),
            len(requested["deviation_notes"]),
        )
    return changes


def change_set_out(change_set: ChangeSet) -> dict[str, Any]:
    return {
        "id": change_set.id,
        "project_scope_id": change_set.project_scope_id,
        "status": change_set.status,
        "operation_kind": change_set.operation_kind,
        "target_kind": change_set.target_kind,
        "target_id": change_set.target_id,
        "base_record_sha256": change_set.base_record_sha256,
        "request_payload_jsonb": change_set.request_payload_jsonb or {},
        "preview_jsonb": change_set.preview_jsonb or {},
        "diff_jsonb": change_set.diff_jsonb or [],
        "source_client_name": change_set.source_client_name,
        "source_client_version": change_set.source_client_version,
        "source_transport": change_set.source_transport,
        "idempotency_key": change_set.idempotency_key,
        "created_at": change_set.created_at,
        "reviewed_at": change_set.reviewed_at,
        "applied_at": change_set.applied_at,
        "failure_jsonb": change_set.failure_jsonb,
    }


def propose_change_set(
    db: Session,
    proposal: ChangeSetProposal,
    *,
    idempotency_key: str | None = None,
) -> dict[str, Any]:
    parsed_payload = _validate_payload(db, proposal)
    current = _record_for_operation(db, proposal)
    if proposal.base_record_sha256 is not None and current is not None:
        if current.get("record_sha256") != proposal.base_record_sha256:
            raise ValueError("stale_record")
    target_kind = {
        "create_sample_record": "sample",
        "update_sample_record": "sample",
        "create_experiment_record": "experiment",
        "update_experiment_record": "experiment",
        "create_data_record": "data",
        "update_execution": "sample",
    }[proposal.operation_kind]
    change_set = ChangeSet(
        id=uuid.uuid4(),
        project_scope_id=proposal.project_scope_id,
        status="proposed",
        operation_kind=proposal.operation_kind,
        target_kind=target_kind,
        target_id=proposal.target_id,
        base_record_sha256=proposal.base_record_sha256,
        request_payload_jsonb=parsed_payload,
        preview_jsonb={"current": current, "requested": parsed_payload},
        diff_jsonb=_diff(current, parsed_payload),
        source_client_name=proposal.source_client_name,
        source_client_version=proposal.source_client_version,
        source_transport=proposal.source_transport,
        idempotency_key=idempotency_key,
    )
    db.add(change_set)
    db.commit()
    db.refresh(change_set)
    return change_set_out(change_set)


def _check_concurrency(db: Session, change_set: ChangeSet) -> None:
    if change_set.base_record_sha256 is None or change_set.target_id is None:
        return
    proposal = ChangeSetProposal(
        operation_kind=change_set.operation_kind,
        project_scope_id=change_set.project_scope_id,
        target_id=change_set.target_id,
        base_record_sha256=change_set.base_record_sha256,
        request_payload_jsonb=change_set.request_payload_jsonb,
        source_client_name=change_set.source_client_name,
        source_client_version=change_set.source_client_version,
        source_transport=change_set.source_transport,
    )
    current = _record_for_operation(db, proposal)
    if current is None or current.get("record_sha256") != change_set.base_record_sha256:
        change_set.status = "stale"
        change_set.failure_jsonb = {"code": "change_set_stale"}
        change_set.reviewed_at = datetime.now(UTC)
        db.commit()
        raise ValueError("change_set_stale")


def apply_change_set(db: Session, change_set_id: uuid.UUID) -> dict[str, Any]:
    change_set = db.scalar(select(ChangeSet).where(ChangeSet.id == change_set_id).with_for_update())
    if change_set is None:
        raise LookupError("ChangeSet not found")
    if change_set.status not in {"proposed", "approved"}:
        raise ValueError(f"ChangeSet cannot be applied from {change_set.status}")
    _check_concurrency(db, change_set)
    body = change_set.request_payload_jsonb
    try:
        if change_set.operation_kind == "create_sample_record":
            result = create_sample_record(db, SampleRecordCreate.model_validate(body))
            change_set.target_id = uuid.UUID(str(result["sample"]["id"]))
        elif change_set.operation_kind == "update_sample_record":
            result = update_sample_record(
                db, change_set.target_id, SampleRecordPut.model_validate(body)
            )
        elif change_set.operation_kind == "create_experiment_record":
            result = create_experiment_record(db, ExperimentRecordCreate.model_validate(body))
            change_set.target_id = uuid.UUID(str(result["experiment"]["id"]))
        elif change_set.operation_kind == "update_experiment_record":
            result = update_experiment_record(
                db, change_set.target_id, ExperimentRecordPut.model_validate(body)
            )
        elif change_set.operation_kind == "create_data_record":
            result = create_data_record(db, DataRecordCreate.model_validate(body))
            change_set.target_id = uuid.UUID(str(result["data"]["id"]))
        elif change_set.operation_kind == "update_execution":
            result = update_execution(
                db, change_set.target_id, SampleExecutionUpdate.model_validate(body)
            )
        else:
            raise ValueError("unsupported ChangeSet operation")
        change_set.status = "applied"
        change_set.applied_at = datetime.now(UTC)
        change_set.reviewed_at = change_set.reviewed_at or datetime.now(UTC)
        db.commit()
        _tag_latest_revisions(db, change_set, result)
        return result
    except Exception as exc:
        db.rollback()
        change_set = db.get(ChangeSet, change_set_id)
        if change_set is not None and change_set.status not in {"stale", "applied"}:
            change_set.status = "failed"
            change_set.failure_jsonb = {"code": "change_set_failed", "message": str(exc)}
            db.commit()
        raise


def _tag_latest_revisions(db: Session, change_set: ChangeSet, result: dict[str, Any]) -> None:
    ids: list[uuid.UUID] = []
    if change_set.target_id is not None:
        ids.append(change_set.target_id)
    if change_set.target_kind == "sample" and change_set.operation_kind == "create_sample_record":
        ids.extend(uuid.UUID(str(item["process"]["id"])) for item in result.get("steps", []))
    for object_id in ids:
        revision = db.scalar(
            select(ObjectRevision)
            .where(ObjectRevision.object_id == object_id)
            .order_by(desc(ObjectRevision.revision_number))
            .limit(1)
        )
        if revision is not None:
            revision.change_set_id = change_set.id
            revision.source_client_name = change_set.source_client_name
            revision.source_client_version = change_set.source_client_version
            revision.source_transport = change_set.source_transport
    db.commit()


def review_change_set(
    db: Session, change_set_id: uuid.UUID, review: ChangeSetReview
) -> dict[str, Any]:
    change_set = db.get(ChangeSet, change_set_id)
    if change_set is None:
        raise LookupError("ChangeSet not found")
    if change_set.status != "proposed":
        raise ValueError("ChangeSet is no longer reviewable")
    if review.decision == "reject":
        change_set.status = "rejected"
        change_set.reviewed_at = datetime.now(UTC)
        db.commit()
        return change_set_out(change_set)
    if review.edited_payload_jsonb is not None:
        proposal = ChangeSetProposal(
            operation_kind=change_set.operation_kind,
            project_scope_id=change_set.project_scope_id,
            target_id=change_set.target_id,
            base_record_sha256=change_set.base_record_sha256,
            request_payload_jsonb=review.edited_payload_jsonb,
            source_client_name=change_set.source_client_name,
            source_client_version=change_set.source_client_version,
            source_transport=change_set.source_transport,
        )
        change_set.request_payload_jsonb = _validate_payload(db, proposal)
        change_set.diff_jsonb = _diff(
            _record_for_operation(db, proposal), change_set.request_payload_jsonb
        )
    change_set.status = "approved"
    change_set.reviewed_at = datetime.now(UTC)
    db.commit()
    apply_change_set(db, change_set.id)
    return change_set_out(db.get(ChangeSet, change_set.id))


def list_change_sets(
    db: Session, project_scope_id: uuid.UUID | None = None
) -> list[dict[str, Any]]:
    statement = select(ChangeSet).order_by(ChangeSet.created_at.desc())
    if project_scope_id is not None:
        statement = statement.where(ChangeSet.project_scope_id == project_scope_id)
    return [change_set_out(item) for item in db.scalars(statement.limit(200)).all()]
