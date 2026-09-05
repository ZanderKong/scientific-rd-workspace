from __future__ import annotations

import copy
import uuid
from datetime import UTC, datetime
from typing import Any

from fastapi.encoders import jsonable_encoder
from sqlalchemy import desc, select
from sqlalchemy.orm import Session, selectinload

from app.data_service import set_system_relations
from app.models import (
    ProcessDefinitionVersion,
    ProcessExecution,
    ProcessExecutionDataBinding,
    ProcessExecutionObjectBinding,
    ProcessExecutionRelation,
    ProcessExecutionRevision,
    ResearchObject,
)
from app.process_definition_service import get_current_version
from app.relation_semantics import SemanticConflict, validate_relation_scope
from app.schemas import ProcessExecutionCreate, ProcessExecutionPut
from app.services import get_object, object_out, sha256_json


def _execution(db: Session, execution_id: uuid.UUID) -> ProcessExecution:
    item = db.scalar(
        select(ProcessExecution)
        .where(ProcessExecution.id == execution_id)
        .options(
            selectinload(ProcessExecution.definition_version),
            selectinload(ProcessExecution.object_bindings)
            .selectinload(ProcessExecutionObjectBinding.research_object)
            .selectinload(ResearchObject.type_version),
            selectinload(ProcessExecution.data_bindings).selectinload(
                ProcessExecutionDataBinding.data
            ),
        )
    )
    if item is None:
        raise LookupError("process execution not found")
    return item


def _definition(db: Session, definition_id: uuid.UUID) -> ResearchObject:
    definition = get_object(db, definition_id)
    if definition is None or definition.kind != "process_definition":
        raise LookupError("process definition not found")
    return definition


def _binding_object_out(item: ProcessExecutionObjectBinding) -> dict[str, Any]:
    return {
        "id": item.id,
        "research_object_id": item.research_object_id,
        "direction": item.direction,
        "role": item.role,
        "field_definition_snapshot": item.field_definition_snapshot_jsonb or {},
        "values": item.values_jsonb or {},
        "order_index": item.order_index,
        "object": object_out(item.research_object),
    }


def _binding_data_out(item: ProcessExecutionDataBinding) -> dict[str, Any]:
    return {
        "id": item.id,
        "data_id": item.data_id,
        "direction": item.direction,
        "role": item.role,
        "values": item.values_jsonb or {},
        "order_index": item.order_index,
        "data": object_out(item.data),
    }


def execution_out(db: Session, item: ProcessExecution) -> dict[str, Any]:
    precedes = db.scalars(
        select(ProcessExecutionRelation.target_execution_id).where(
            ProcessExecutionRelation.source_execution_id == item.id,
            ProcessExecutionRelation.relation_type == "precedes",
        )
    ).all()
    body = {
        "id": item.id,
        "project_scope_id": item.project_scope_id,
        "process_definition_id": item.process_definition_id,
        "process_definition_version_id": item.process_definition_version_id,
        "title_snapshot": item.title_snapshot,
        "status": item.status,
        "execution_field_definitions": item.execution_field_definition_snapshot_jsonb or {},
        "values": item.values_jsonb or {},
        "note": item.note,
        "occurred_at": item.occurred_at,
        "started_at": item.started_at,
        "completed_at": item.completed_at,
        "created_at": item.created_at,
        "updated_at": item.updated_at,
        "object_bindings": [_binding_object_out(binding) for binding in item.object_bindings],
        "data_bindings": [_binding_data_out(binding) for binding in item.data_bindings],
        "precedes_execution_ids": precedes,
    }
    return {"record_sha256": sha256_json(body), **body}


def _revision(
    db: Session, item: ProcessExecution, change_note: str | None
) -> ProcessExecutionRevision:
    latest = (
        db.scalar(
            select(ProcessExecutionRevision.revision_number)
            .where(ProcessExecutionRevision.execution_id == item.id)
            .order_by(desc(ProcessExecutionRevision.revision_number))
            .limit(1)
        )
        or 0
    )
    snapshot = jsonable_encoder(execution_out(db, item))
    revision = ProcessExecutionRevision(
        execution_id=item.id,
        revision_number=latest + 1,
        snapshot_jsonb=copy.deepcopy(snapshot),
        snapshot_sha256=sha256_json(snapshot),
        change_note=change_note,
    )
    db.add(revision)
    db.flush()
    return revision


def _check_precedes_cycle(db: Session, source_id: uuid.UUID, targets: list[uuid.UUID]) -> None:
    adjacency: dict[uuid.UUID, set[uuid.UUID]] = {}
    rows = db.execute(
        select(
            ProcessExecutionRelation.source_execution_id,
            ProcessExecutionRelation.target_execution_id,
        )
    ).all()
    for source, target in rows:
        adjacency.setdefault(source, set()).add(target)
    adjacency.setdefault(source_id, set()).update(targets)
    visiting: set[uuid.UUID] = set()
    visited: set[uuid.UUID] = set()

    def visit(node: uuid.UUID) -> bool:
        if node in visiting:
            return True
        if node in visited:
            return False
        visiting.add(node)
        if any(visit(child) for child in adjacency.get(node, ())):
            return True
        visiting.remove(node)
        visited.add(node)
        return False

    if visit(source_id):
        raise SemanticConflict("ProcessExecution precedes cycle is not allowed")


def _resolve_values(values: dict[str, Any]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in values.items():
        if hasattr(value, "model_dump"):
            result[key] = value.model_dump(exclude_none=True)
        else:
            result[key] = copy.deepcopy(value)
    return result


def _replace_bindings(
    db: Session, item: ProcessExecution, payload: ProcessExecutionCreate | ProcessExecutionPut
) -> tuple[list[uuid.UUID], list[uuid.UUID]]:
    db.query(ProcessExecutionObjectBinding).filter(
        ProcessExecutionObjectBinding.execution_id == item.id
    ).delete(synchronize_session=False)
    db.query(ProcessExecutionDataBinding).filter(
        ProcessExecutionDataBinding.execution_id == item.id
    ).delete(synchronize_session=False)
    subject_ids: list[uuid.UUID] = []
    output_data_ids: list[uuid.UUID] = []
    input_data_ids: list[uuid.UUID] = []
    for index, binding in enumerate(payload.object_bindings):
        object_id = binding.research_object_id
        if object_id is None:
            raise ValueError("research_object_id is required")
        target = get_object(db, object_id)
        if target is None:
            raise LookupError("bound Research Object not found")
        if item.project_scope_id is not None:
            validate_relation_scope(_definition(db, item.process_definition_id), target)
        snapshot = copy.deepcopy(
            binding.field_definition_snapshot or target.process_field_definitions_jsonb or {}
        )
        db.add(
            ProcessExecutionObjectBinding(
                execution_id=item.id,
                research_object_id=target.id,
                direction=binding.direction,
                role=binding.role.strip() if binding.role else None,
                field_definition_snapshot_jsonb=snapshot,
                values_jsonb=_resolve_values(binding.values),
                order_index=binding.order_index if binding.order_index is not None else index,
            )
        )
        if binding.direction == "input" and binding.role == "subject":
            subject_ids.append(target.id)
    for index, binding in enumerate(payload.data_bindings):
        target = get_object(db, binding.data_id)
        if target is None or target.kind != "data":
            raise ValueError("data binding must target a Data object")
        db.add(
            ProcessExecutionDataBinding(
                execution_id=item.id,
                data_id=target.id,
                direction=binding.direction,
                role=binding.role,
                values_jsonb=copy.deepcopy(binding.values),
                order_index=binding.order_index if binding.order_index is not None else index,
            )
        )
        if binding.direction == "input":
            input_data_ids.append(target.id)
        else:
            output_data_ids.append(target.id)
    db.flush()
    return subject_ids, input_data_ids + output_data_ids


def _sync_provenance(
    db: Session,
    item: ProcessExecution,
    subject_ids: list[uuid.UUID],
    bound_data_ids: list[uuid.UUID],
) -> None:
    output_data_ids = [
        binding.data_id for binding in item.data_bindings if binding.direction == "output"
    ]
    input_data_ids = [
        binding.data_id for binding in item.data_bindings if binding.direction == "input"
    ]
    for data_id in output_data_ids:
        set_system_relations(db, data_id, subject_ids=subject_ids, derived_from_ids=input_data_ids)


def create_process_execution(db: Session, payload: ProcessExecutionCreate) -> dict[str, Any]:
    try:
        definition = _definition(db, payload.process_definition_id)
        version = (
            db.get(ProcessDefinitionVersion, payload.process_definition_version_id)
            if payload.process_definition_version_id
            else get_current_version(db, definition.id)
        )
        if version is None or version.process_definition_id != definition.id:
            raise ValueError("definition version does not belong to ProcessDefinition")
        scope_id = (
            payload.project_scope_id
            if payload.project_scope_id is not None
            else definition.project_scope_id
        )
        if scope_id is not None:
            scope = get_object(db, scope_id)
            if scope is None or scope.kind != "project":
                raise ValueError("project_scope_id must point to a Project object")
        item = ProcessExecution(
            project_scope_id=scope_id,
            process_definition_id=definition.id,
            process_definition_version_id=version.id,
            title_snapshot=payload.title_snapshot or definition.title,
            status=payload.status,
            execution_field_definition_snapshot_jsonb=copy.deepcopy(
                payload.execution_field_definitions
                or version.execution_field_definitions_jsonb
                or {}
            ),
            values_jsonb=copy.deepcopy(payload.values),
            note=payload.note,
            occurred_at=payload.occurred_at,
            started_at=datetime.now(UTC) if payload.status in {"running", "completed"} else None,
            completed_at=datetime.now(UTC) if payload.status == "completed" else None,
        )
        db.add(item)
        db.flush()
        subjects, bound_data_ids = _replace_bindings(db, item, payload)
        _check_precedes_cycle(db, item.id, payload.precedes_execution_ids)
        for target_id in payload.precedes_execution_ids:
            target = db.get(ProcessExecution, target_id)
            if target is None:
                raise LookupError("preceding ProcessExecution not found")
            db.add(
                ProcessExecutionRelation(
                    source_execution_id=item.id,
                    target_execution_id=target.id,
                    relation_type="precedes",
                )
            )
        db.flush()
        _sync_provenance(db, item, subjects, bound_data_ids)
        _revision(db, item, "create process execution")
        db.commit()
        return execution_out(db, _execution(db, item.id))
    except Exception:
        db.rollback()
        raise


def get_process_execution(db: Session, execution_id: uuid.UUID) -> dict[str, Any]:
    return execution_out(db, _execution(db, execution_id))


def update_process_execution(
    db: Session, execution_id: uuid.UUID, payload: ProcessExecutionPut
) -> dict[str, Any]:
    try:
        item = _execution(db, execution_id)
        definition_id = payload.process_definition_id or item.process_definition_id
        definition = _definition(db, definition_id)
        version_id = payload.process_definition_version_id or item.process_definition_version_id
        version = db.get(ProcessDefinitionVersion, version_id)
        if version is None or version.process_definition_id != definition.id:
            raise ValueError("definition version does not belong to ProcessDefinition")
        if payload.base_record_sha256:
            current = execution_out(db, item)["record_sha256"]
            if payload.base_record_sha256 != current:
                raise SemanticConflict("stale_record", code="stale_record")
        item.process_definition_id = definition.id
        item.process_definition_version_id = version.id
        item.project_scope_id = (
            payload.project_scope_id
            if payload.project_scope_id is not None
            else item.project_scope_id
        )
        item.title_snapshot = payload.title_snapshot or item.title_snapshot or definition.title
        item.status = payload.status
        item.execution_field_definition_snapshot_jsonb = copy.deepcopy(
            payload.execution_field_definitions
            or item.execution_field_definition_snapshot_jsonb
            or version.execution_field_definitions_jsonb
            or {}
        )
        item.values_jsonb = copy.deepcopy(payload.values)
        item.note = payload.note
        item.occurred_at = payload.occurred_at
        if item.status == "running" and item.started_at is None:
            item.started_at = datetime.now(UTC)
        item.completed_at = datetime.now(UTC) if item.status == "completed" else None
        db.query(ProcessExecutionRelation).filter(
            ProcessExecutionRelation.source_execution_id == item.id
        ).delete(synchronize_session=False)
        subjects, bound_data_ids = _replace_bindings(db, item, payload)
        _check_precedes_cycle(db, item.id, payload.precedes_execution_ids)
        for target_id in payload.precedes_execution_ids:
            if db.get(ProcessExecution, target_id) is None:
                raise LookupError("preceding ProcessExecution not found")
            db.add(
                ProcessExecutionRelation(
                    source_execution_id=item.id,
                    target_execution_id=target_id,
                    relation_type="precedes",
                )
            )
        db.flush()
        _sync_provenance(db, item, subjects, bound_data_ids)
        _revision(db, item, payload.change_note)
        db.commit()
        return execution_out(db, _execution(db, execution_id))
    except Exception:
        db.rollback()
        raise


def list_process_executions_for_object(db: Session, object_id: uuid.UUID) -> list[ProcessExecution]:
    return list(
        db.scalars(
            select(ProcessExecution)
            .join(ProcessExecutionObjectBinding)
            .where(ProcessExecutionObjectBinding.research_object_id == object_id)
            .options(
                selectinload(ProcessExecution.definition_version),
                selectinload(ProcessExecution.object_bindings).selectinload(
                    ProcessExecutionObjectBinding.research_object
                ),
                selectinload(ProcessExecution.data_bindings).selectinload(
                    ProcessExecutionDataBinding.data
                ),
            )
            .distinct()
            .order_by(ProcessExecution.created_at)
        )
    )


def list_process_executions_for_data(db: Session, data_id: uuid.UUID) -> list[ProcessExecution]:
    return list(
        db.scalars(
            select(ProcessExecution)
            .join(ProcessExecutionDataBinding)
            .where(ProcessExecutionDataBinding.data_id == data_id)
            .options(
                selectinload(ProcessExecution.definition_version),
                selectinload(ProcessExecution.object_bindings).selectinload(
                    ProcessExecutionObjectBinding.research_object
                ),
                selectinload(ProcessExecution.data_bindings).selectinload(
                    ProcessExecutionDataBinding.data
                ),
            )
            .distinct()
            .order_by(ProcessExecution.created_at)
        )
    )
