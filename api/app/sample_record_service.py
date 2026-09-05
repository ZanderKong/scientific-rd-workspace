from __future__ import annotations

import uuid
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.models import (
    ObjectRelation,
    ProcessExecution,
    ProcessExecutionDataBinding,
    ProcessExecutionObjectBinding,
    ProcessExecutionRelation,
    ResearchObject,
)
from app.process_execution_service import (
    _create_process_execution_in_session,
    _revision,
    _update_process_execution_in_session,
    execution_out,
)
from app.relation_semantics import SemanticConflict
from app.schemas import (
    ObjectCreate,
    ProcessExecutionCreate,
    ProcessExecutionObjectBindingCreate,
    ProcessExecutionPut,
    SampleRecordCreate,
    SampleRecordPut,
)
from app.services import (
    _create_object_in_session,
    _create_revision_in_session,
    _update_object_in_session,
    get_object,
    object_out,
    sha256_json,
)


def _sample(db: Session, sample_id: uuid.UUID) -> ResearchObject:
    item = get_object(db, sample_id)
    if item is None or item.kind != "research_object":
        raise LookupError("Research Object not found")
    if "样品" not in (item.tags_jsonb or []) and "sample" not in (item.tags_jsonb or []):
        # Output bindings are also a valid Sample projection even if the user
        # did not keep the recommended tag.
        exists = db.scalar(
            select(ProcessExecutionObjectBinding.id).where(
                ProcessExecutionObjectBinding.research_object_id == item.id,
                ProcessExecutionObjectBinding.direction == "output",
            )
        )
        if exists is None:
            raise LookupError("sample projection not found")
    return item


def _sample_executions(db: Session, sample_id: uuid.UUID) -> list[ProcessExecution]:
    items = list(
        db.scalars(
            select(ProcessExecution)
            .join(ProcessExecutionObjectBinding)
            .where(
                ProcessExecutionObjectBinding.research_object_id == sample_id,
                (ProcessExecutionObjectBinding.direction == "output")
                | (ProcessExecutionObjectBinding.role == "sample_record"),
            )
            .options(
                selectinload(ProcessExecution.object_bindings).selectinload(
                    ProcessExecutionObjectBinding.research_object
                ),
                selectinload(ProcessExecution.data_bindings).selectinload(
                    ProcessExecutionDataBinding.data
                ),
                selectinload(ProcessExecution.definition_version),
            )
            .distinct()
        ).all()
    )
    by_id = {item.id: item for item in items}
    relations = db.execute(
        select(
            ProcessExecutionRelation.source_execution_id,
            ProcessExecutionRelation.target_execution_id,
        ).where(
            ProcessExecutionRelation.source_execution_id.in_(list(by_id)),
            ProcessExecutionRelation.target_execution_id.in_(list(by_id)),
        )
    ).all()
    outgoing: dict[uuid.UUID, set[uuid.UUID]] = {item.id: set() for item in items}
    indegree: dict[uuid.UUID, int] = {item.id: 0 for item in items}
    for source_id, target_id in relations:
        if target_id not in outgoing[source_id]:
            outgoing[source_id].add(target_id)
            indegree[target_id] += 1

    def sort_key(execution_id: uuid.UUID) -> tuple[Any, str]:
        item = by_id[execution_id]
        return (item.created_at, str(item.id))

    ready = sorted((item.id for item in items if indegree[item.id] == 0), key=sort_key)
    ordered: list[ProcessExecution] = []
    while ready:
        execution_id = ready.pop(0)
        ordered.append(by_id[execution_id])
        for target_id in sorted(outgoing[execution_id], key=sort_key):
            indegree[target_id] -= 1
            if indegree[target_id] == 0:
                ready.append(target_id)
                ready.sort(key=sort_key)
    if len(ordered) != len(items):
        return sorted(items, key=sort_key)
    return ordered


def get_sample_record(db: Session, sample_id: uuid.UUID) -> dict[str, Any]:
    sample = _sample(db, sample_id)
    executions = _sample_executions(db, sample.id)
    # Subject is Data -> Object, so use the inverse relation directly.
    data_ids = db.scalars(
        select(ObjectRelation.source_object_id).where(
            ObjectRelation.target_object_id == sample.id, ObjectRelation.relation_type == "subject"
        )
    ).all()
    data = [item for item in (get_object(db, item_id) for item_id in data_ids) if item is not None]
    body = {
        "sample": object_out(sample),
        "steps": [
            {"execution": execution_out(db, item), "ordinal": index}
            for index, item in enumerate(executions)
        ],
        "data": [object_out(item) for item in data],
        "editable": True,
        "edit_blockers": [],
    }
    return {"record_sha256": sha256_json(body), **body}


def _step_payload(
    step: Any,
    sample_id: uuid.UUID,
    project_scope_id: uuid.UUID | None,
    final: bool,
) -> ProcessExecutionCreate:
    bindings = [
        binding
        for binding in step.object_bindings
        if not (
            binding.research_object_id == sample_id and binding.role in {"sample_record", "product"}
        )
    ]
    bindings.append(
        ProcessExecutionObjectBindingCreate(
            research_object_id=sample_id,
            direction="context",
            role="sample_record",
            values={},
        )
    )
    if final:
        bindings.append(
            ProcessExecutionObjectBindingCreate(
                research_object_id=sample_id, direction="output", role="product", values={}
            )
        )
    return ProcessExecutionCreate(
        process_definition_id=step.process_definition_id,
        process_definition_version_id=step.process_definition_version_id,
        project_scope_id=project_scope_id,
        status=step.status,
        title_snapshot=step.title_snapshot,
        values=step.values,
        object_bindings=bindings,
        data_bindings=step.data_bindings,
        source_view_id=getattr(step, "source_view_id", None),
        source_view_revision_id=getattr(step, "source_view_revision_id", None),
    )


def _rebuild_sample_sequence(
    db: Session, execution_ids: list[uuid.UUID], *, revision: bool = False
) -> None:
    if not execution_ids:
        return
    db.query(ProcessExecutionRelation).filter(
        ProcessExecutionRelation.source_execution_id.in_(execution_ids),
        ProcessExecutionRelation.target_execution_id.in_(execution_ids),
    ).delete(synchronize_session=False)
    db.add_all(
        ProcessExecutionRelation(
            source_execution_id=source_id,
            target_execution_id=target_id,
            relation_type="precedes",
        )
        for source_id, target_id in zip(execution_ids, execution_ids[1:], strict=False)
    )
    db.flush()
    if revision:
        for execution_id in execution_ids:
            item = db.get(ProcessExecution, execution_id)
            if item is not None:
                _revision(db, item, "update sample record sequence")


def create_sample_record(db: Session, payload: SampleRecordCreate) -> dict[str, Any]:
    try:
        sample = _create_object_in_session(
            db,
            ObjectCreate(
                kind="research_object",
                code=payload.sample.code,
                title=payload.sample.title,
                status=payload.sample.status,
                project_scope_id=payload.project_scope_id,
                tags=payload.sample.tags or ["样品"],
                properties_jsonb=payload.sample.properties_jsonb,
                process_field_definitions=payload.sample.process_field_definitions,
                content_document=payload.sample.content_document,
            ),
        )
        created: list[ProcessExecution] = []
        for index, step in enumerate(payload.steps):
            if step.execution_id is not None:
                raise ValueError("execution_id is only valid when updating a Sample Record")
            created.append(
                _create_process_execution_in_session(
                    db,
                    _step_payload(
                        step,
                        sample.id,
                        sample.project_scope_id,
                        index == len(payload.steps) - 1,
                    ),
                    create_revision=False,
                )
            )
        _rebuild_sample_sequence(db, [item.id for item in created], revision=True)
        _create_revision_in_session(db, sample.id, payload.change_note)
        db.commit()
        return get_sample_record(db, sample.id)
    except Exception:
        db.rollback()
        raise


def update_sample_record(
    db: Session, sample_id: uuid.UUID, payload: SampleRecordPut
) -> dict[str, Any]:
    try:
        sample = _sample(db, sample_id)
        changes = {
            key: value
            for key, value in payload.sample.items()
            if key
            in {
                "title",
                "status",
                "tags",
                "properties_jsonb",
                "process_field_definitions",
                "content_document",
            }
        }
        if changes:
            _update_object_in_session(db, sample, changes)
        existing = _sample_executions(db, sample.id)
        existing_ids = {item.id for item in existing}
        all_existing_ids = list(existing_ids)
        # Release old projection bindings first so a new final step can safely
        # claim the sample's unique output identity.
        if all_existing_ids:
            db.query(ProcessExecutionObjectBinding).filter(
                ProcessExecutionObjectBinding.execution_id.in_(all_existing_ids),
                ProcessExecutionObjectBinding.research_object_id == sample.id,
                ProcessExecutionObjectBinding.role.in_(["sample_record", "product"]),
            ).delete(synchronize_session=False)
            db.flush()
        desired_ids: list[uuid.UUID] = []
        touched: list[ProcessExecution] = []
        for index, step in enumerate(payload.steps):
            if step.execution_id is not None:
                if step.execution_id not in existing_ids:
                    raise SemanticConflict(
                        "step execution_id is not a member of this Sample Record",
                        code="validation_failed",
                    )
                execution = _update_process_execution_in_session(
                    db,
                    step.execution_id,
                    ProcessExecutionPut(
                        process_definition_id=step.process_definition_id,
                        process_definition_version_id=step.process_definition_version_id,
                        status=step.status,
                        title_snapshot=step.title_snapshot,
                        values=step.values,
                        object_bindings=_step_payload(
                            step,
                            sample.id,
                            sample.project_scope_id,
                            index == len(payload.steps) - 1,
                        ).object_bindings,
                        data_bindings=step.data_bindings,
                        execution_id=step.execution_id,
                        source_view_id=getattr(step, "source_view_id", None),
                        source_view_revision_id=getattr(step, "source_view_revision_id", None),
                        change_note=payload.change_note,
                        base_record_sha256=None,
                    ),
                    create_revision=False,
                )
            else:
                execution = _create_process_execution_in_session(
                    db,
                    _step_payload(step, sample.id, index == len(payload.steps) - 1),
                    create_revision=False,
                )
            desired_ids.append(execution.id)
            touched.append(execution)
        omitted_ids = existing_ids - set(desired_ids)
        if omitted_ids:
            db.query(ProcessExecutionRelation).filter(
                ProcessExecutionRelation.source_execution_id.in_(list(omitted_ids) + desired_ids),
                ProcessExecutionRelation.target_execution_id.in_(list(omitted_ids) + desired_ids),
            ).delete(synchronize_session=False)
        _rebuild_sample_sequence(db, desired_ids, revision=False)
        for execution in touched:
            _revision(db, execution, payload.change_note or "update sample record")
        _create_revision_in_session(db, sample.id, payload.change_note)
        db.commit()
        return get_sample_record(db, sample.id)
    except Exception:
        db.rollback()
        raise
