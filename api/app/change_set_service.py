from __future__ import annotations

import uuid
from datetime import UTC, datetime
from typing import Any

from fastapi.encoders import jsonable_encoder
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.claim_service import create_claim, get_claim, update_claim
from app.data_service import create_data_record, get_data_record, update_data_record
from app.experiment_record_service import (
    create_experiment_record,
    get_experiment_record,
    update_experiment_record,
)
from app.models import ChangeSet
from app.process_definition_service import create_process_definition
from app.process_execution_service import (
    create_process_execution,
    get_process_execution,
    update_process_execution,
)
from app.schemas import (
    ChangeSetProposal,
    ChangeSetReview,
    ClaimCreate,
    ClaimPut,
    DataRecordCreate,
    DataRecordPut,
    ExperimentRecordCreate,
    ExperimentRecordPut,
    ObjectCreate,
    ObjectPatch,
    ProcessDefinitionCreate,
    ProcessExecutionCreate,
    ProcessExecutionPut,
    ViewCreate,
    ViewPut,
)
from app.services import create_object, get_object, object_out, sha256_json, update_object
from app.view_service import create_view, get_view, update_view


def _record_for_operation(db: Session, proposal: ChangeSetProposal) -> dict[str, Any] | None:
    if proposal.target_id is None:
        return None
    operation = proposal.operation_kind
    if "research_object" in operation:
        item = get_object(db, proposal.target_id)
        return (
            {"object": object_out(item), "record_sha256": sha256_json(object_out(item))}
            if item
            else None
        )
    if "process_definition" in operation:
        from app.process_definition_service import get_process_definition

        return get_process_definition(db, proposal.target_id)
    if "process_execution" in operation:
        return get_process_execution(db, proposal.target_id)
    if "data_record" in operation:
        return get_data_record(db, proposal.target_id)
    if "experiment_record" in operation:
        return get_experiment_record(db, proposal.target_id)
    if "view" in operation:
        return get_view(db, proposal.target_id)
    if "claim" in operation:
        return get_claim(db, proposal.target_id)
    return None


def _validate_payload(db: Session, proposal: ChangeSetProposal) -> dict[str, Any]:
    operation = proposal.operation_kind
    body = proposal.request_payload_jsonb
    mapping: dict[str, type[Any]] = {
        "create_research_object": ObjectCreate,
        "update_research_object": ObjectPatch,
        "create_process_definition": ProcessDefinitionCreate,
        "create_process_execution": ProcessExecutionCreate,
        "update_process_execution": ProcessExecutionPut,
        "create_data_record": DataRecordCreate,
        "update_data_record": DataRecordPut,
        "create_experiment_record": ExperimentRecordCreate,
        "update_experiment_record": ExperimentRecordPut,
        "create_view": ViewCreate,
        "update_view": ViewPut,
        "create_claim": ClaimCreate,
        "update_claim": ClaimPut,
    }
    model = mapping.get(operation)
    if model is None:
        raise ValueError("unsupported ChangeSet operation")
    if operation.startswith("create_") and proposal.target_id is not None:
        raise ValueError("create proposals must not provide target_id")
    if operation.startswith("update_") and (
        proposal.target_id is None or proposal.base_record_sha256 is None
    ):
        raise ValueError("update proposals require target_id and base_record_sha256")
    parsed = model.model_validate(body)
    return parsed.model_dump(mode="json", exclude_none=True)


def change_set_out(item: ChangeSet) -> dict[str, Any]:
    return {
        "id": item.id,
        "project_scope_id": item.project_scope_id,
        "status": item.status,
        "operation_kind": item.operation_kind,
        "target_kind": item.target_kind,
        "target_id": item.target_id,
        "base_record_sha256": item.base_record_sha256,
        "request_payload_jsonb": item.request_payload_jsonb or {},
        "preview_jsonb": item.preview_jsonb or {},
        "diff_jsonb": item.diff_jsonb or [],
        "source_client_name": item.source_client_name,
        "source_client_version": item.source_client_version,
        "source_transport": item.source_transport,
        "idempotency_key": item.idempotency_key,
        "created_at": item.created_at,
        "reviewed_at": item.reviewed_at,
        "applied_at": item.applied_at,
        "failure_jsonb": item.failure_jsonb,
    }


def propose_change_set(
    db: Session, proposal: ChangeSetProposal, *, idempotency_key: str | None = None
) -> dict[str, Any]:
    parsed = _validate_payload(db, proposal)
    current = _record_for_operation(db, proposal)
    if (
        proposal.base_record_sha256
        and current
        and proposal.base_record_sha256 != current.get("record_sha256")
    ):
        raise ValueError("stale_record")
    target_kind = proposal.operation_kind.replace("create_", "").replace("update_", "")
    item = ChangeSet(
        project_scope_id=proposal.project_scope_id,
        status="proposed",
        operation_kind=proposal.operation_kind,
        target_kind=target_kind,
        target_id=proposal.target_id,
        base_record_sha256=proposal.base_record_sha256,
        request_payload_jsonb=parsed,
        preview_jsonb=jsonable_encoder({"current": current, "requested": parsed}),
        diff_jsonb=jsonable_encoder([{"key": "record", "before": current, "after": parsed}]),
        source_client_name=proposal.source_client_name,
        source_client_version=proposal.source_client_version,
        source_transport=proposal.source_transport,
        idempotency_key=idempotency_key,
    )
    db.add(item)
    db.commit()
    db.refresh(item)
    return change_set_out(item)


def _apply_operation(db: Session, item: ChangeSet) -> dict[str, Any]:
    body = item.request_payload_jsonb
    operation = item.operation_kind
    if operation == "create_research_object":
        created = create_object(db, ObjectCreate.model_validate(body))
        output = object_out(created)
        return {"object": output, "record_sha256": sha256_json(output)}
    if operation == "update_research_object":
        obj = get_object(db, item.target_id)
        if obj is None:
            raise LookupError("Research Object not found")
        updated = update_object(
            db, obj, ObjectPatch.model_validate(body).model_dump(exclude_unset=True)
        )
        output = object_out(updated)
        return {"object": output, "record_sha256": sha256_json(output)}
    if operation == "create_process_definition":
        return create_process_definition(db, ProcessDefinitionCreate.model_validate(body))
    if operation == "create_process_execution":
        return create_process_execution(db, ProcessExecutionCreate.model_validate(body))
    if operation == "update_process_execution":
        return update_process_execution(
            db, item.target_id, ProcessExecutionPut.model_validate(body)
        )
    if operation == "create_data_record":
        return create_data_record(db, DataRecordCreate.model_validate(body))
    if operation == "update_data_record":
        return update_data_record(db, item.target_id, DataRecordPut.model_validate(body))
    if operation == "create_experiment_record":
        return create_experiment_record(db, ExperimentRecordCreate.model_validate(body))
    if operation == "update_experiment_record":
        return update_experiment_record(
            db, item.target_id, ExperimentRecordPut.model_validate(body)
        )
    if operation == "create_view":
        return create_view(db, ViewCreate.model_validate(body))
    if operation == "update_view":
        return update_view(db, item.target_id, ViewPut.model_validate(body))
    if operation == "create_claim":
        return create_claim(db, ClaimCreate.model_validate(body))
    if operation == "update_claim":
        return update_claim(db, item.target_id, ClaimPut.model_validate(body))
    raise ValueError("unsupported ChangeSet operation")


def apply_change_set(db: Session, change_set_id: uuid.UUID) -> dict[str, Any]:
    item = db.scalar(select(ChangeSet).where(ChangeSet.id == change_set_id).with_for_update())
    if item is None:
        raise LookupError("ChangeSet not found")
    if item.status not in {"proposed", "approved"}:
        raise ValueError(f"ChangeSet cannot be applied from {item.status}")
    if item.base_record_sha256 and item.target_id:
        proposal = ChangeSetProposal(
            operation_kind=item.operation_kind,
            project_scope_id=item.project_scope_id,
            target_id=item.target_id,
            base_record_sha256=item.base_record_sha256,
            request_payload_jsonb=item.request_payload_jsonb,
        )
        current = _record_for_operation(db, proposal)
        if current is None or current.get("record_sha256") != item.base_record_sha256:
            item.status = "stale"
            item.failure_jsonb = {"code": "change_set_stale"}
            item.reviewed_at = datetime.now(UTC)
            db.commit()
            raise ValueError("change_set_stale")
    try:
        result = _apply_operation(db, item)
        if item.target_id is None and isinstance(result, dict):
            for key in ("object", "data", "experiment", "view", "claim", "process_definition"):
                value = result.get(key)
                if isinstance(value, dict) and value.get("id"):
                    item.target_id = uuid.UUID(str(value["id"]))
                    break
            if item.target_id is None and result.get("id"):
                item.target_id = uuid.UUID(str(result["id"]))
        item.status = "applied"
        item.applied_at = datetime.now(UTC)
        item.reviewed_at = item.reviewed_at or datetime.now(UTC)
        db.commit()
        return result
    except Exception as exc:
        db.rollback()
        item = db.get(ChangeSet, change_set_id)
        if item and item.status not in {"stale", "applied"}:
            item.status = "failed"
            item.failure_jsonb = {"code": "change_set_failed", "message": str(exc)}
            db.commit()
        raise


def review_change_set(
    db: Session, change_set_id: uuid.UUID, review: ChangeSetReview
) -> dict[str, Any]:
    item = db.get(ChangeSet, change_set_id)
    if item is None:
        raise LookupError("ChangeSet not found")
    if item.status != "proposed":
        raise ValueError("ChangeSet is no longer reviewable")
    if review.decision == "reject":
        item.status = "rejected"
    else:
        if review.edited_payload_jsonb is not None:
            proposal = ChangeSetProposal(
                operation_kind=item.operation_kind,
                project_scope_id=item.project_scope_id,
                target_id=item.target_id,
                base_record_sha256=item.base_record_sha256,
                request_payload_jsonb=review.edited_payload_jsonb,
            )
            item.request_payload_jsonb = _validate_payload(db, proposal)
        item.status = "approved"
    item.reviewed_at = datetime.now(UTC)
    db.commit()
    return change_set_out(item)


def list_change_sets(
    db: Session, project_scope_id: uuid.UUID | None = None
) -> list[dict[str, Any]]:
    statement = select(ChangeSet).order_by(ChangeSet.created_at.desc()).limit(200)
    if project_scope_id:
        statement = statement.where(ChangeSet.project_scope_id == project_scope_id)
    return [change_set_out(item) for item in db.scalars(statement)]
