from __future__ import annotations

import copy
import uuid
from datetime import UTC, datetime
from typing import Any

from fastapi.encoders import jsonable_encoder
from sqlalchemy import desc, select
from sqlalchemy.orm import Session, selectinload

from app.data_service import sync_data_subject_assignments, sync_system_relations_for_data
from app.models import (
    ObjectRevision,
    ProcessDefinitionVersion,
    ProcessExecution,
    ProcessExecutionDataBinding,
    ProcessExecutionObjectBinding,
    ProcessExecutionRelation,
    ProcessExecutionRevision,
    ResearchObject,
    RevisionReference,
    ViewRevision,
)
from app.process_definition_service import get_current_version
from app.relation_semantics import SemanticConflict, lock_project_graph
from app.schemas import ProcessExecutionCreate, ProcessExecutionPut
from app.services import _create_revision_in_session, get_object, object_out, sha256_json


def _execution(db: Session, execution_id: uuid.UUID, *, lock: bool = False) -> ProcessExecution:
    statement = (
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
    if lock:
        statement = statement.with_for_update()
    item = db.scalar(statement)
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
        "authoring_occurrence_id": item.authoring_occurrence_id,
        "research_object_id": item.research_object_id,
        "research_object_revision_id": item.research_object_revision_id,
        "direction": item.direction,
        "role": item.role,
        "is_active": item.is_active,
        "field_definition_snapshot": item.field_definition_snapshot_jsonb or {},
        "values": item.values_jsonb or {},
        "order_index": item.order_index,
        "object": object_out(item.research_object),
    }


def _binding_data_out(item: ProcessExecutionDataBinding) -> dict[str, Any]:
    return {
        "id": item.id,
        "data_id": item.data_id,
        "data_revision_id": item.data_revision_id,
        "direction": item.direction,
        "role": item.role,
        "values": item.values_jsonb or {},
        "order_index": item.order_index,
        "data": object_out(item.data),
    }


def execution_out(
    db: Session,
    item: ProcessExecution,
    *,
    precedes_ids: list[uuid.UUID] | None = None,
) -> dict[str, Any]:
    precedes = (
        precedes_ids
        if precedes_ids is not None
        else db.scalars(
            select(ProcessExecutionRelation.target_execution_id).where(
                ProcessExecutionRelation.source_execution_id == item.id,
                ProcessExecutionRelation.relation_type == "precedes",
            )
        ).all()
    )
    body = {
        "id": item.id,
        "authoring_record_id": item.authoring_record_id,
        "authoring_occurrence_id": item.authoring_occurrence_id,
        "project_scope_id": item.project_scope_id,
        "process_definition_id": item.process_definition_id,
        "process_definition_version_id": item.process_definition_version_id,
        "source_view_id": item.source_view_id,
        "source_view_revision_id": item.source_view_revision_id,
        "title_snapshot": item.title_snapshot,
        "status": item.status,
        "record_validity": item.record_validity,
        "execution_field_definitions": item.execution_field_definition_snapshot_jsonb or {},
        "values": item.values_jsonb or {},
        "note": item.note,
        "occurred_at": item.occurred_at,
        "started_at": item.started_at,
        "completed_at": item.completed_at,
        "created_at": item.created_at,
        "updated_at": item.updated_at,
        "object_bindings": [
            _binding_object_out(binding) for binding in item.object_bindings if binding.is_active
        ],
        "data_bindings": [_binding_data_out(binding) for binding in item.data_bindings],
        "precedes_execution_ids": precedes,
    }
    # The current execution token is its own immutable revision identity.  Do
    # not hash enriched object/Data summaries here: renaming a referenced
    # target must not turn an otherwise unchanged execution into a stale write.
    own_revision_sha = db.scalar(
        select(ProcessExecutionRevision.snapshot_sha256)
        .where(ProcessExecutionRevision.execution_id == item.id)
        .order_by(ProcessExecutionRevision.revision_number.desc())
        .limit(1)
    )
    stable_token = {
        key: value for key, value in body.items() if key not in {"object_bindings", "data_bindings"}
    }
    stable_token["object_bindings"] = [
        {key: value for key, value in binding.items() if key not in {"object"}}
        for binding in body["object_bindings"]
    ]
    stable_token["data_bindings"] = [
        {key: value for key, value in binding.items() if key not in {"data"}}
        for binding in body["data_bindings"]
    ]
    return {"record_sha256": own_revision_sha or sha256_json(stable_token), **body}


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
    references: list[RevisionReference] = []
    if item.source_view_revision_id is not None:
        source_view_revision = db.get(ViewRevision, item.source_view_revision_id)
        if source_view_revision is not None:
            references.append(
                RevisionReference(
                    source_execution_revision_id=revision.id,
                    target_view_revision_id=source_view_revision.id,
                )
            )
    for binding in item.object_bindings:
        if not binding.is_active:
            continue
        if binding.research_object_revision_id is not None:
            references.append(
                RevisionReference(
                    source_execution_revision_id=revision.id,
                    target_object_revision_id=binding.research_object_revision_id,
                )
            )
    for binding in item.data_bindings:
        if binding.data_revision_id is not None:
            references.append(
                RevisionReference(
                    source_execution_revision_id=revision.id,
                    target_object_revision_id=binding.data_revision_id,
                )
            )
    db.add_all(references)
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
        raise SemanticConflict(
            "ProcessExecution precedes cycle is not allowed", code="cycle_detected"
        )


def _validate_execution_scope(db: Session, scope_id: uuid.UUID | None) -> None:
    if scope_id is None:
        return
    scope = get_object(db, scope_id)
    if scope is None or scope.kind != "project":
        raise SemanticConflict(
            "project_scope_id must point to a Project object", code="scope_conflict"
        )


def _validate_definition_scope(
    definition: ResearchObject, execution_scope_id: uuid.UUID | None
) -> None:
    if (
        definition.project_scope_id is not None
        and definition.project_scope_id != execution_scope_id
    ):
        raise SemanticConflict(
            "ProcessDefinition is outside the execution project scope", code="scope_conflict"
        )


def _validate_view_source(
    db: Session,
    execution_scope_id: uuid.UUID | None,
    source_view_id: uuid.UUID | None,
    source_view_revision_id: uuid.UUID | None,
) -> None:
    if source_view_id is None and source_view_revision_id is None:
        return
    if source_view_id is None or source_view_revision_id is None:
        raise SemanticConflict(
            "source_view_id and source_view_revision_id must be provided together",
            code="validation_failed",
        )
    view = get_object(db, source_view_id)
    if view is None or view.kind != "view":
        raise SemanticConflict("source_view_id must point to a View", code="invalid_binding_target")
    if view.project_scope_id not in {None, execution_scope_id}:
        raise SemanticConflict("source View crosses project scope", code="scope_conflict")
    from app.models import ViewRevision

    revision = db.get(ViewRevision, source_view_revision_id)
    if revision is None or revision.view_id != view.id:
        raise SemanticConflict(
            "source_view_revision_id must belong to source_view_id", code="validation_failed"
        )


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
    existing_sample_members = set(
        db.scalars(
            select(ProcessExecutionObjectBinding.research_object_id).where(
                ProcessExecutionObjectBinding.execution_id == item.id,
                ProcessExecutionObjectBinding.direction == "context",
                ProcessExecutionObjectBinding.role == "sample_record",
                ProcessExecutionObjectBinding.is_active.is_(True),
            )
        ).all()
    )
    requested_sample_members = {
        binding.research_object_id
        for binding in payload.object_bindings
        if binding.direction == "context" and binding.role == "sample_record"
    }
    if len(existing_sample_members | requested_sample_members) > 1:
        raise SemanticConflict(
            "a ProcessExecution may belong to only one Sample Record",
            code="semantic_conflict",
        )
    existing_objects = {binding.id: binding for binding in item.object_bindings}
    existing_data = {binding.id: binding for binding in item.data_bindings}
    used_object_ids: set[uuid.UUID] = set()
    used_data_ids: set[uuid.UUID] = set()
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
        if target.kind != "research_object":
            raise SemanticConflict(
                "ProcessExecution object bindings must target Research Objects",
                code="invalid_binding_target",
            )
        if target.project_scope_id not in {None, item.project_scope_id}:
            raise SemanticConflict(
                "Research Object is outside the execution project scope", code="scope_conflict"
            )
        snapshot = copy.deepcopy(
            binding.field_definition_snapshot or target.process_field_definitions_jsonb or {}
        )
        if binding.research_object_revision_id is not None:
            target_revision = db.get(ObjectRevision, binding.research_object_revision_id)
            if target_revision is None or target_revision.object_id != target.id:
                raise SemanticConflict(
                    "research_object_revision_id must belong to the bound object",
                    code="validation_failed",
                )
        explicit_current = existing_objects.get(binding.binding_id) if binding.binding_id else None
        current = explicit_current
        if current is not None and current.research_object_id != target.id:
            # A binding identity represents the occurrence usage. Replace keeps
            # that identity while changing the referenced object and its pinned
            # revision/value snapshot atomically.
            current.research_object_id = target.id
        if current is None:
            current = next(
                (
                    candidate
                    for candidate in existing_objects.values()
                    if candidate.id not in used_object_ids
                    and binding.authoring_occurrence_id is not None
                    and candidate.authoring_occurrence_id == binding.authoring_occurrence_id
                ),
                None,
            )
        if current is not None and current.research_object_id != target.id:
            current.research_object_id = target.id
        if current is None:
            current = next(
                (
                    candidate
                    for candidate in existing_objects.values()
                    if candidate.id not in used_object_ids
                    and candidate.research_object_id == target.id
                    and candidate.direction == binding.direction
                    and candidate.role == (binding.role.strip() if binding.role else None)
                ),
                None,
            )
        if current is None:
            current = ProcessExecutionObjectBinding(
                execution_id=item.id, research_object_id=target.id
            )
            db.add(current)
        if (
            current.authoring_occurrence_id is not None
            and binding.authoring_occurrence_id is not None
            and current.authoring_occurrence_id != binding.authoring_occurrence_id
        ):
            raise SemanticConflict(
                "binding occurrence identity cannot change", code="validation_failed"
            )
        current.authoring_occurrence_id = binding.authoring_occurrence_id
        current.is_active = True
        current.research_object_revision_id = binding.research_object_revision_id
        current.direction = binding.direction
        current.role = binding.role.strip() if binding.role else None
        current.field_definition_snapshot_jsonb = snapshot
        current.values_jsonb = _resolve_values(binding.values)
        current.order_index = binding.order_index if binding.order_index is not None else index
        db.flush()
        used_object_ids.add(current.id)
        if binding.direction == "input" and binding.role == "subject":
            subject_ids.append(target.id)
    for index, binding in enumerate(payload.data_bindings):
        target = get_object(db, binding.data_id)
        if target is None or target.kind != "data":
            raise SemanticConflict(
                "data binding must target a Data object", code="invalid_binding_target"
            )
        if target.project_scope_id not in {None, item.project_scope_id}:
            raise SemanticConflict(
                "Data is outside the execution project scope", code="scope_conflict"
            )
        if binding.direction == "output":
            existing = db.scalar(
                select(ProcessExecutionDataBinding.id).where(
                    ProcessExecutionDataBinding.data_id == target.id,
                    ProcessExecutionDataBinding.direction == "output",
                    ProcessExecutionDataBinding.execution_id != item.id,
                )
            )
            if existing is not None:
                raise SemanticConflict(
                    "Data already has a canonical output producer",
                    code="data_already_has_producer",
                )
        current_data = existing_data.get(binding.binding_id) if binding.binding_id else None
        if current_data is not None and current_data.data_id != target.id:
            raise SemanticConflict("binding_id target cannot change", code="validation_failed")
        if current_data is None:
            current_data = next(
                (
                    candidate
                    for candidate in existing_data.values()
                    if candidate.id not in used_data_ids
                    and candidate.data_id == target.id
                    and candidate.direction == binding.direction
                    and candidate.role == binding.role
                ),
                None,
            )
        if current_data is None:
            current_data = ProcessExecutionDataBinding(execution_id=item.id, data_id=target.id)
            db.add(current_data)
        if binding.data_revision_id is not None:
            data_revision = db.get(ObjectRevision, binding.data_revision_id)
            if data_revision is None or data_revision.object_id != target.id:
                raise SemanticConflict(
                    "data_revision_id must belong to the bound Data object",
                    code="validation_failed",
                )
        current_data.data_revision_id = binding.data_revision_id
        current_data.direction = binding.direction
        current_data.role = binding.role
        current_data.values_jsonb = copy.deepcopy(binding.values)
        current_data.order_index = binding.order_index if binding.order_index is not None else index
        db.flush()
        used_data_ids.add(current_data.id)
        if binding.direction == "input":
            input_data_ids.append(target.id)
        else:
            output_data_ids.append(target.id)
    for binding_id, binding in existing_objects.items():
        if binding_id not in used_object_ids:
            # Keep the row and its identity so an occurrence can be restored
            # without allocating a different binding or violating the
            # DocumentOccurrence foreign key.  It is excluded from current
            # execution output while inactive.
            binding.is_active = False
    for binding_id, binding in existing_data.items():
        if binding_id not in used_data_ids:
            db.delete(binding)
    db.flush()
    return subject_ids, input_data_ids + output_data_ids


def _sync_provenance(
    db: Session,
    item: ProcessExecution,
    affected_data_ids: list[uuid.UUID],
) -> None:
    current_bindings = db.scalars(
        select(ProcessExecutionDataBinding).where(
            ProcessExecutionDataBinding.execution_id == item.id
        )
    ).all()
    current_output_data_ids = {
        binding.data_id for binding in current_bindings if binding.direction == "output"
    }
    for data_id in sorted(set(affected_data_ids) | current_output_data_ids, key=str):
        producer = db.scalar(
            select(ProcessExecutionDataBinding)
            .where(
                ProcessExecutionDataBinding.data_id == data_id,
                ProcessExecutionDataBinding.direction == "output",
            )
            .order_by(ProcessExecutionDataBinding.created_at)
        )
        if producer is None:
            sync_data_subject_assignments(
                db,
                data_id,
                subject_ids=[],
                source_kind="producer",
                source_ref_id=item.id,
            )
            sync_system_relations_for_data(db, data_id, derived_from_ids=[])
            _create_revision_in_session(db, data_id, "update producer and Data provenance")
            continue
        producer_execution = db.get(ProcessExecution, producer.execution_id)
        if producer_execution is None:
            continue
        producer_object_bindings = db.scalars(
            select(ProcessExecutionObjectBinding).where(
                ProcessExecutionObjectBinding.execution_id == producer_execution.id,
                ProcessExecutionObjectBinding.is_active.is_(True),
            )
        ).all()
        producer_data_bindings = db.scalars(
            select(ProcessExecutionDataBinding).where(
                ProcessExecutionDataBinding.execution_id == producer_execution.id
            )
        ).all()
        subjects = [
            binding.research_object_id
            for binding in producer_object_bindings
            if binding.direction == "input" and binding.role == "subject"
        ]
        inputs = [
            binding.data_id for binding in producer_data_bindings if binding.direction == "input"
        ]
        sync_data_subject_assignments(
            db,
            data_id,
            subject_ids=subjects,
            source_kind="producer",
            source_ref_id=producer_execution.id,
        )
        sync_system_relations_for_data(db, data_id, derived_from_ids=inputs)
        _create_revision_in_session(db, data_id, "update producer and Data provenance")


def _replace_precedes(db: Session, item: ProcessExecution, target_ids: list[uuid.UUID]) -> None:
    lock_project_graph(db, item.project_scope_id)
    targets = []
    for target_id in target_ids:
        target = db.get(ProcessExecution, target_id)
        if target is None:
            raise LookupError("ProcessExecution target not found")
        if target.id == item.id:
            raise SemanticConflict("ProcessExecution cannot precede itself", code="cycle_detected")
        if target.project_scope_id != item.project_scope_id:
            raise SemanticConflict(
                "ProcessExecution precedes relation crosses project scopes", code="scope_conflict"
            )
        targets.append(target.id)
    _check_precedes_cycle(db, item.id, targets)
    db.query(ProcessExecutionRelation).filter(
        ProcessExecutionRelation.source_execution_id == item.id
    ).delete(synchronize_session=False)
    db.add_all(
        ProcessExecutionRelation(
            source_execution_id=item.id,
            target_execution_id=target_id,
            relation_type="precedes",
        )
        for target_id in targets
    )
    db.flush()


def _create_process_execution_in_session(
    db: Session, payload: ProcessExecutionCreate, *, create_revision: bool = True
) -> ProcessExecution:
    definition = _definition(db, payload.process_definition_id)
    version = (
        db.get(ProcessDefinitionVersion, payload.process_definition_version_id)
        if payload.process_definition_version_id
        else get_current_version(db, definition.id)
    )
    if version is None or version.process_definition_id != definition.id:
        raise SemanticConflict(
            "definition version does not belong to ProcessDefinition", code="validation_failed"
        )
    scope_id = (
        payload.project_scope_id
        if payload.project_scope_id is not None
        else definition.project_scope_id
    )
    _validate_execution_scope(db, scope_id)
    _validate_definition_scope(definition, scope_id)
    lock_project_graph(db, scope_id)
    _validate_view_source(db, scope_id, payload.source_view_id, payload.source_view_revision_id)
    item = ProcessExecution(
        project_scope_id=scope_id,
        process_definition_id=definition.id,
        process_definition_version_id=version.id,
        source_view_id=payload.source_view_id,
        source_view_revision_id=payload.source_view_revision_id,
        title_snapshot=payload.title_snapshot or definition.title,
        status=payload.status,
        execution_field_definition_snapshot_jsonb=copy.deepcopy(
            payload.execution_field_definitions or version.execution_field_definitions_jsonb or {}
        ),
        values_jsonb=copy.deepcopy(payload.values),
        note=payload.note,
        occurred_at=payload.occurred_at,
        started_at=datetime.now(UTC) if payload.status in {"running", "completed"} else None,
        completed_at=datetime.now(UTC) if payload.status == "completed" else None,
    )
    db.add(item)
    db.flush()
    _replace_bindings(db, item, payload)
    _replace_precedes(db, item, payload.precedes_execution_ids)
    db.flush()
    _sync_provenance(db, item, [])
    if create_revision:
        db.expire(item, ["object_bindings", "data_bindings"])
        _revision(db, item, "create process execution")
    return item


def create_process_execution(
    db: Session, payload: ProcessExecutionCreate, *, commit: bool = True
) -> dict[str, Any]:
    try:
        item = _create_process_execution_in_session(db, payload)
        if commit:
            db.commit()
        else:
            db.flush()
        db.expire(item)
        return execution_out(db, _execution(db, item.id))
    except Exception:
        db.rollback()
        raise


def get_process_execution(db: Session, execution_id: uuid.UUID) -> dict[str, Any]:
    return execution_out(db, _execution(db, execution_id))


def get_process_execution_revision(
    db: Session, execution_id: uuid.UUID, revision_number: int
) -> ProcessExecutionRevision:
    _execution(db, execution_id)
    revision = db.scalar(
        select(ProcessExecutionRevision).where(
            ProcessExecutionRevision.execution_id == execution_id,
            ProcessExecutionRevision.revision_number == revision_number,
        )
    )
    if revision is None:
        raise LookupError("process execution revision not found")
    return revision


def _update_process_execution_in_session(
    db: Session,
    execution_id: uuid.UUID,
    payload: ProcessExecutionPut,
    *,
    create_revision: bool = True,
) -> ProcessExecution:
    item = _execution(db, execution_id)
    lock_project_graph(db, item.project_scope_id)
    item = _execution(db, execution_id, lock=True)
    old_output_ids = {
        binding.data_id for binding in item.data_bindings if binding.direction == "output"
    }
    definition_id = payload.process_definition_id or item.process_definition_id
    definition = _definition(db, definition_id)
    version_id = payload.process_definition_version_id or item.process_definition_version_id
    version = db.get(ProcessDefinitionVersion, version_id)
    if version is None or version.process_definition_id != definition.id:
        raise SemanticConflict(
            "definition version does not belong to ProcessDefinition", code="validation_failed"
        )
    if payload.base_record_sha256:
        current = execution_out(db, item)["record_sha256"]
        if payload.base_record_sha256 != current:
            raise SemanticConflict("stale_record", code="stale_record")
    next_scope = (
        payload.project_scope_id if payload.project_scope_id is not None else item.project_scope_id
    )
    _validate_execution_scope(db, next_scope)
    _validate_definition_scope(definition, next_scope)
    source_view_id = (
        payload.source_view_id if payload.source_view_id is not None else item.source_view_id
    )
    source_view_revision_id = (
        payload.source_view_revision_id
        if payload.source_view_revision_id is not None
        else item.source_view_revision_id
    )
    _validate_view_source(db, next_scope, source_view_id, source_view_revision_id)
    item.process_definition_id = definition.id
    item.process_definition_version_id = version.id
    item.project_scope_id = next_scope
    item.source_view_id = source_view_id
    item.source_view_revision_id = source_view_revision_id
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
    _replace_bindings(db, item, payload)
    _replace_precedes(db, item, payload.precedes_execution_ids)
    db.flush()
    _sync_provenance(db, item, list(old_output_ids))
    if create_revision:
        db.expire(item, ["object_bindings", "data_bindings"])
        _revision(db, item, payload.change_note)
    return item


def update_process_execution(
    db: Session,
    execution_id: uuid.UUID,
    payload: ProcessExecutionPut,
    *,
    commit: bool = True,
) -> dict[str, Any]:
    try:
        existing = _execution(db, execution_id)
        lock_project_graph(db, existing.project_scope_id)
        existing = _execution(db, execution_id, lock=True)
        if existing.authoring_record_id is not None:
            raise SemanticConflict(
                "Document-managed executions must be changed through their authoring record",
                code="managed_execution",
            )
        if not payload.base_record_sha256:
            raise ValueError("revision_required")
        item = _update_process_execution_in_session(db, execution_id, payload)
        if commit:
            db.commit()
        else:
            db.flush()
        db.expire(item)
        return execution_out(db, _execution(db, item.id))
    except Exception:
        db.rollback()
        raise


def list_process_executions_for_object(db: Session, object_id: uuid.UUID) -> list[ProcessExecution]:
    return list(
        db.scalars(
            select(ProcessExecution)
            .join(ProcessExecutionObjectBinding)
            .where(
                ProcessExecutionObjectBinding.research_object_id == object_id,
                ProcessExecutionObjectBinding.is_active.is_(True),
            )
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
