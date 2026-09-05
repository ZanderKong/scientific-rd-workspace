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
    ResearchObject,
)
from app.process_execution_service import (
    create_process_execution,
    execution_out,
    update_process_execution,
)
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
    return list(
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
            .order_by(ProcessExecution.created_at)
        ).all()
    )


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


def _step_payload(step: Any, sample_id: uuid.UUID, final: bool) -> ProcessExecutionCreate:
    bindings = list(step.object_bindings)
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
        status=step.status,
        title_snapshot=step.title_snapshot,
        values=step.values,
        object_bindings=bindings,
        data_bindings=step.data_bindings,
    )


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
            result = create_process_execution(
                db, _step_payload(step, sample.id, index == len(payload.steps) - 1)
            )
            execution = db.get(ProcessExecution, result["id"])
            if execution is None:
                raise LookupError("created execution not found")
            created.append(execution)
        # The execution service commits each operation for direct API calls;
        # the projection still makes the full scientific path visible.
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
        for index, step in enumerate(payload.steps):
            if index < len(existing):
                update_process_execution(
                    db,
                    existing[index].id,
                    ProcessExecutionPut(
                        process_definition_id=step.process_definition_id,
                        process_definition_version_id=step.process_definition_version_id,
                        status=step.status,
                        title_snapshot=step.title_snapshot,
                        values=step.values,
                        object_bindings=list(step.object_bindings)
                        + [
                            ProcessExecutionObjectBindingCreate(
                                research_object_id=sample.id,
                                direction="context",
                                role="sample_record",
                                values={},
                            )
                        ]
                        + (
                            [
                                ProcessExecutionObjectBindingCreate(
                                    research_object_id=sample.id,
                                    direction="output",
                                    role="product",
                                    values={},
                                )
                            ]
                            if index == len(payload.steps) - 1
                            else []
                        ),
                        data_bindings=step.data_bindings,
                    ),
                )
            else:
                create_process_execution(
                    db, _step_payload(step, sample.id, index == len(payload.steps) - 1)
                )
        _create_revision_in_session(db, sample.id, payload.change_note)
        db.commit()
        return get_sample_record(db, sample.id)
    except Exception:
        db.rollback()
        raise
