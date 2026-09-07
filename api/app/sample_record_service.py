from __future__ import annotations

import copy
import math
import uuid
from collections import defaultdict
from typing import Any

from sqlalchemy import desc, select
from sqlalchemy.orm import Session, selectinload

from app.models import (
    DocumentOccurrence,
    ObjectRelation,
    ObjectRevision,
    OccurrenceFieldValue,
    ProcessExecution,
    ProcessExecutionDataBinding,
    ProcessExecutionObjectBinding,
    ProcessExecutionRelation,
    ProcessExecutionRevision,
    ResearchObject,
)
from app.process_execution_service import (
    _check_precedes_cycle,
    _create_process_execution_in_session,
    _revision,
    _update_process_execution_in_session,
    execution_out,
)
from app.relation_semantics import SemanticConflict, lock_project_graph
from app.schemas import (
    ObjectCreate,
    ProcessExecutionCreate,
    ProcessExecutionObjectBindingCreate,
    ProcessExecutionPut,
    SampleBatchCreate,
    SampleRecordCreate,
    SampleRecordPut,
    ScientificDocumentV1,
    ScientificOccurrenceDraft,
)
from app.scientific_record_service import lock_record_owner
from app.services import (
    _create_object_in_session,
    _create_revision_in_session,
    _update_object_in_session,
    get_object,
    object_out,
    sha256_json,
)


def _sample(db: Session, sample_id: uuid.UUID, *, lock: bool = False) -> ResearchObject:
    item = (
        lock_record_owner(db, sample_id, expected_kind="research_object")
        if lock
        else db.scalar(select(ResearchObject).where(ResearchObject.id == sample_id))
    )
    if item is None or item.kind != "research_object":
        raise LookupError("Research Object not found")
    tags = item.tags_jsonb or []
    if item.authoring_kind != "sample" and "样品" not in tags and "sample" not in tags:
        raise LookupError("sample record not found")
    return item


def _document_occurrence_ids(value: Any) -> list[uuid.UUID]:
    found: list[uuid.UUID] = []

    def visit(current: Any) -> None:
        if isinstance(current, dict):
            props = current.get("props")
            if current.get("type") in {"processRef", "objectRef"} and isinstance(props, dict):
                raw_id = props.get("occurrenceId")
                if raw_id:
                    try:
                        found.append(uuid.UUID(str(raw_id)))
                    except ValueError as exc:
                        raise ValueError("document contains an invalid occurrence ID") from exc
            for child in current.values():
                visit(child)
        elif isinstance(current, list):
            for child in current:
                visit(child)

    visit(value)
    return found


def _validate_document(
    document: ScientificDocumentV1, occurrences: list[ScientificOccurrenceDraft]
) -> None:
    ids = [item.occurrence_id for item in occurrences]
    if len(ids) != len(set(ids)):
        raise ValueError("occurrence IDs must be unique within a document")
    if _document_occurrence_ids(document.blocks) != ids:
        raise ValueError("document Ref order must match occurrences")


def _field_definitions(value: dict[str, Any]) -> dict[str, dict[str, Any]]:
    nested = value.get("fields")
    if isinstance(nested, list):
        return {
            str(item["key"]): item for item in nested if isinstance(item, dict) and item.get("key")
        }
    return {key: item for key, item in value.items() if isinstance(item, dict)}


def _project_field_values(
    row: DocumentOccurrence, occurrence: ScientificOccurrenceDraft, ordinal: int
) -> list[OccurrenceFieldValue]:
    definitions = _field_definitions(occurrence.field_definitions)
    result: list[OccurrenceFieldValue] = []
    field_keys = list(dict.fromkeys([*definitions.keys(), *occurrence.values.keys()]))
    for field_key in field_keys:
        stored = occurrence.values.get(field_key)
        definition = definitions.get(field_key)
        if definition is None:
            raise ValueError(f"unknown field key: {field_key}")
        raw = stored.get("value") if isinstance(stored, dict) else stored
        unit = stored.get("unit") if isinstance(stored, dict) else definition.get("default_unit")
        value_type = str(definition.get("value_type") or "text")
        if value_type not in {"number", "text", "boolean", "select"}:
            raise ValueError(f"unsupported field value type: {value_type}")
        text_value: str | None = None
        number_value: float | None = None
        boolean_value: bool | None = None
        if raw is None or raw == "":
            # Keep an occurrence-level projection even when its slot is empty.
            # The table query uses this row to expose field definitions and to
            # preserve the position of an unfilled repeated occurrence.
            result.append(
                OccurrenceFieldValue(
                    occurrence_row_id=row.id,
                    owner_id=row.owner_id,
                    occurrence_id=row.occurrence_id,
                    target_id=row.target_id,
                    field_key=field_key,
                    value_type=value_type,
                    unit=str(unit) if unit else None,
                    ordinal=ordinal,
                )
            )
            continue
        if value_type == "number":
            if isinstance(raw, bool):
                raise ValueError(f"field {field_key} must be a number")
            try:
                number_value = float(raw)
            except (TypeError, ValueError) as exc:
                raise ValueError(f"field {field_key} must be a complete number") from exc
            if not math.isfinite(number_value):
                raise ValueError(f"field {field_key} must be a finite number")
            text_value = str(raw)
        elif value_type == "boolean":
            if isinstance(raw, bool):
                boolean_value = raw
            elif isinstance(raw, str) and raw.lower() in {"true", "false"}:
                boolean_value = raw.lower() == "true"
            else:
                raise ValueError(f"field {field_key} must be a boolean")
            text_value = "true" if boolean_value else "false"
        else:
            text_value = str(raw)
        result.append(
            OccurrenceFieldValue(
                occurrence_row_id=row.id,
                owner_id=row.owner_id,
                occurrence_id=row.occurrence_id,
                target_id=row.target_id,
                field_key=field_key,
                value_type=value_type,
                text_value=text_value,
                number_value=number_value,
                boolean_value=boolean_value,
                unit=str(unit) if unit else None,
                ordinal=ordinal,
            )
        )
    return result


def _record_body(db: Session, sample: ResearchObject) -> dict[str, Any]:
    rows = list(
        db.scalars(
            select(DocumentOccurrence)
            .where(DocumentOccurrence.owner_id == sample.id)
            .order_by(DocumentOccurrence.ordinal, DocumentOccurrence.id)
        ).all()
    )
    occurrences: list[dict[str, Any]] = []
    target_ids = {row.target_id for row in rows}
    targets = {
        item.id: item
        for item in db.scalars(
            select(ResearchObject).where(ResearchObject.id.in_(target_ids))
        ).all()
    }
    execution_ids = {row.execution_id for row in rows if row.execution_id is not None}
    executions = {
        item.id: item
        for item in db.scalars(
            select(ProcessExecution)
            .where(ProcessExecution.id.in_(execution_ids))
            .options(
                selectinload(ProcessExecution.object_bindings).selectinload(
                    ProcessExecutionObjectBinding.research_object
                ),
                selectinload(ProcessExecution.data_bindings).selectinload(
                    ProcessExecutionDataBinding.data
                ),
            )
        ).all()
    }
    binding_ids = {row.binding_id for row in rows if row.binding_id is not None}
    bindings = {
        item.id: item
        for item in db.scalars(
            select(ProcessExecutionObjectBinding).where(
                ProcessExecutionObjectBinding.id.in_(binding_ids),
                ProcessExecutionObjectBinding.is_active.is_(True),
            )
        ).all()
    }
    process_rows = {
        row.execution_id: row
        for row in rows
        if row.execution_id is not None and row.kind == "process"
    }
    precedes_by_source: dict[uuid.UUID, list[uuid.UUID]] = defaultdict(list)
    if execution_ids:
        for source_id, target_id in db.execute(
            select(
                ProcessExecutionRelation.source_execution_id,
                ProcessExecutionRelation.target_execution_id,
            ).where(
                ProcessExecutionRelation.source_execution_id.in_(execution_ids),
                ProcessExecutionRelation.relation_type == "precedes",
            )
        ).all():
            precedes_by_source[source_id].append(target_id)
    for row in rows:
        target = targets.get(row.target_id)
        execution = executions.get(row.execution_id) if row.execution_id else None
        values = row.values_jsonb or {}
        binding = None
        if row.binding_id:
            bound = bindings.get(row.binding_id)
            if bound is not None:
                values = bound.values_jsonb or {}
                process_row = process_rows.get(bound.execution_id)
                if process_row is not None:
                    binding = {
                        "process_occurrence_id": process_row.occurrence_id,
                        "binding_id": bound.id,
                        "direction": bound.direction,
                        "role": bound.role,
                    }
        occurrences.append(
            {
                "occurrence_id": row.occurrence_id,
                "kind": row.kind,
                "target_id": row.target_id,
                "target_revision_id": row.target_revision_id,
                "execution_id": row.execution_id,
                "process_definition_version_id": (
                    execution.process_definition_version_id if execution else None
                ),
                "label_snapshot": (
                    execution.title_snapshot if execution else (target.title if target else None)
                ),
                "field_definitions": (
                    execution.execution_field_definition_snapshot_jsonb
                    if execution
                    else row.field_definition_snapshot_jsonb or {}
                ),
                "values": values,
                "status": execution.status if execution else "recorded",
                "binding": binding,
                "execution": (
                    execution_out(
                        db,
                        execution,
                        precedes_ids=precedes_by_source.get(execution.id, []),
                    )
                    if execution
                    else None
                ),
                "object": object_out(target) if target else None,
            }
        )
    data_ids = db.scalars(
        select(ObjectRelation.source_object_id).where(
            ObjectRelation.target_object_id == sample.id,
            ObjectRelation.relation_type == "subject",
        )
    ).all()
    data = (
        list(db.scalars(select(ResearchObject).where(ResearchObject.id.in_(data_ids))).all())
        if data_ids
        else []
    )
    body = {
        "sample": object_out(sample),
        "document": {
            "schema_version": sample.document_format_version,
            "blocks": sample.content_document,
        },
        "occurrences": occurrences,
        "data": [object_out(item) for item in data],
        "editable": True,
        "edit_blockers": [],
    }
    # The current token is the immutable revision identity of this record. It
    # must not be recomputed from enriched target titles or reverse relations,
    # because those can change without changing the record itself.
    current_revision_sha = db.scalar(
        select(ObjectRevision.snapshot_sha256)
        .where(ObjectRevision.object_id == sample.id)
        .order_by(desc(ObjectRevision.revision_number))
        .limit(1)
    )
    if current_revision_sha is None:
        record_version = {
            "sample": body["sample"],
            "document": body["document"],
            "occurrences": occurrences,
        }
        current_revision_sha = sha256_json(record_version)
    return {"record_sha256": current_revision_sha, **body}


def get_sample_record(db: Session, sample_id: uuid.UUID) -> dict[str, Any]:
    return _record_body(db, _sample(db, sample_id))


def get_sample_record_revision(
    db: Session, sample_id: uuid.UUID, revision_number: int
) -> dict[str, Any]:
    _sample(db, sample_id)
    revision = db.scalar(
        select(ObjectRevision).where(
            ObjectRevision.object_id == sample_id,
            ObjectRevision.revision_number == revision_number,
        )
    )
    if revision is None:
        raise LookupError("sample record revision not found")
    snapshot = copy.deepcopy(revision.snapshot_jsonb)
    manifest = snapshot.get("scientific_manifest") or {}
    execution_revisions: dict[str, dict[str, Any]] = {}
    process_occurrence_by_execution: dict[str, str] = {}
    for entry in manifest.get("execution_manifest") or []:
        execution_id = entry.get("execution_id")
        occurrence_id = entry.get("occurrence_id")
        if execution_id and occurrence_id:
            process_occurrence_by_execution[execution_id] = occurrence_id
        revision_id = entry.get("execution_revision_id")
        execution_revision = db.get(ProcessExecutionRevision, revision_id) if revision_id else None
        if execution_id and execution_revision is not None:
            execution_revisions[execution_id] = copy.deepcopy(execution_revision.snapshot_jsonb)
    occurrences: list[dict[str, Any]] = []
    for entry in sorted(manifest.get("occurrences") or [], key=lambda item: item["ordinal"]):
        execution = execution_revisions.get(entry.get("execution_id"))
        values = copy.deepcopy(entry.get("values") or {})
        binding = None
        if entry.get("binding_id"):
            for execution_id, candidate in execution_revisions.items():
                binding_snapshot = next(
                    (
                        item
                        for item in candidate.get("object_bindings") or []
                        if item.get("id") == entry["binding_id"]
                    ),
                    None,
                )
                if binding_snapshot is None:
                    continue
                values = copy.deepcopy(binding_snapshot.get("values") or {})
                binding = {
                    "process_occurrence_id": process_occurrence_by_execution[execution_id],
                    "binding_id": entry["binding_id"],
                    "direction": binding_snapshot["direction"],
                    "role": binding_snapshot.get("role"),
                }
                break
        occurrences.append(
            {
                "occurrence_id": entry["occurrence_id"],
                "kind": entry["kind"],
                "target_id": entry["target_id"],
                "target_revision_id": entry.get("target_revision_id"),
                "execution_id": entry.get("execution_id"),
                "process_definition_version_id": (
                    execution.get("process_definition_version_id") if execution else None
                ),
                "label_snapshot": (
                    execution.get("title_snapshot") if execution else entry.get("label_snapshot")
                ),
                "field_definitions": (
                    execution.get("execution_field_definitions")
                    if execution
                    else entry.get("field_definition_snapshot") or {}
                ),
                "values": execution.get("values") if execution else values,
                "status": execution.get("status") if execution else "recorded",
                "binding": binding,
                "execution": execution,
                "object": None,
            }
        )
    object_snapshot = snapshot["object"]
    return {
        "record_sha256": revision.snapshot_sha256,
        "sample": object_snapshot,
        "document": {
            "schema_version": manifest.get("document_format_version", 1),
            "blocks": object_snapshot.get("content_document") or [],
        },
        "occurrences": occurrences,
        "data": [],
        "editable": False,
        "edit_blockers": ["historical_revision"],
    }


def _execution_payload(
    occurrence: ScientificOccurrenceDraft,
    project_scope_id: uuid.UUID | None,
    bindings: list[ProcessExecutionObjectBindingCreate],
) -> ProcessExecutionCreate:
    return ProcessExecutionCreate(
        process_definition_id=occurrence.target_id,
        process_definition_version_id=occurrence.process_definition_version_id,
        project_scope_id=project_scope_id,
        title_snapshot=occurrence.label_snapshot,
        status=occurrence.status,
        execution_field_definitions=occurrence.field_definitions,
        values=occurrence.values,
        object_bindings=bindings,
        data_bindings=[],
    )


def _sync_record(
    db: Session,
    sample: ResearchObject,
    document: ScientificDocumentV1,
    occurrences: list[ScientificOccurrenceDraft],
    change_note: str | None,
) -> None:
    _validate_document(document, occurrences)
    lock_project_graph(db, sample.project_scope_id)
    resolved_occurrences: list[ScientificOccurrenceDraft] = []
    for occurrence in occurrences:
        target = get_object(db, occurrence.target_id)
        expected_kind = "process_definition" if occurrence.kind == "process" else "research_object"
        if target is None or target.kind != expected_kind:
            raise SemanticConflict(
                f"{occurrence.kind} occurrence target is invalid",
                code="invalid_binding_target",
            )
        if target.project_scope_id not in {None, sample.project_scope_id}:
            raise SemanticConflict(
                "occurrence target is outside the Sample project scope",
                code="scope_conflict",
            )
        revision_id = occurrence.target_revision_id
        if revision_id is None:
            revision_id = db.scalar(
                select(ObjectRevision.id)
                .where(ObjectRevision.object_id == target.id)
                .order_by(desc(ObjectRevision.revision_number))
                .limit(1)
            )
        else:
            revision = db.get(ObjectRevision, revision_id)
            if revision is None or revision.object_id != target.id:
                raise SemanticConflict(
                    "target revision does not belong to occurrence target",
                    code="validation_failed",
                )
        resolved_occurrences.append(
            occurrence.model_copy(update={"target_revision_id": revision_id})
        )
    occurrences = resolved_occurrences
    current_rows = {
        row.occurrence_id: row
        for row in db.scalars(
            select(DocumentOccurrence).where(DocumentOccurrence.owner_id == sample.id)
        ).all()
    }
    process_occurrences = [item for item in occurrences if item.kind == "process"]
    object_occurrences = [item for item in occurrences if item.kind == "object"]
    process_by_occurrence: dict[uuid.UUID, ProcessExecution] = {}
    bound_by_process: dict[uuid.UUID, list[ScientificOccurrenceDraft]] = defaultdict(list)
    for occurrence in object_occurrences:
        if occurrence.binding:
            bound_by_process[occurrence.binding.process_occurrence_id].append(occurrence)

    for occurrence in process_occurrences:
        binding_payloads = [
            ProcessExecutionObjectBindingCreate(
                binding_id=item.binding.binding_id if item.binding else None,
                authoring_occurrence_id=item.occurrence_id,
                research_object_id=item.target_id,
                research_object_revision_id=item.target_revision_id,
                direction=item.binding.direction if item.binding else "input",
                role=item.binding.role if item.binding else None,
                field_definition_snapshot=item.field_definitions,
                values=item.values,
                order_index=index,
            )
            for index, item in enumerate(bound_by_process.get(occurrence.occurrence_id, []))
        ]
        current = current_rows.get(occurrence.occurrence_id)
        execution = (
            db.get(ProcessExecution, current.execution_id)
            if current and current.execution_id
            else None
        )
        # A removed Process occurrence is retracted, not deleted. Restoring the
        # same occurrence must reuse that durable execution identity instead of
        # attempting a second row against the authoring uniqueness constraint.
        if execution is None:
            execution = db.scalar(
                select(ProcessExecution)
                .where(
                    ProcessExecution.authoring_record_id == sample.id,
                    ProcessExecution.authoring_occurrence_id == occurrence.occurrence_id,
                )
                .with_for_update()
            )
        if occurrence.execution_id and execution and occurrence.execution_id != execution.id:
            raise SemanticConflict(
                "occurrence execution identity cannot change", code="validation_failed"
            )
        if execution is None:
            execution = _create_process_execution_in_session(
                db,
                _execution_payload(occurrence, sample.project_scope_id, binding_payloads),
                create_revision=False,
            )
            execution.authoring_record_id = sample.id
            execution.authoring_occurrence_id = occurrence.occurrence_id
        else:
            _update_process_execution_in_session(
                db,
                execution.id,
                ProcessExecutionPut(
                    **_execution_payload(
                        occurrence, sample.project_scope_id, binding_payloads
                    ).model_dump(),
                    change_note=change_note,
                ),
                create_revision=False,
            )
            execution.record_validity = "active"
        db.flush()
        process_by_occurrence[occurrence.occurrence_id] = execution

    requested_process_ids = {item.id for item in process_by_occurrence.values()}
    omitted_query = select(ProcessExecution).where(
        ProcessExecution.authoring_record_id == sample.id,
        ProcessExecution.record_validity == "active",
    )
    if requested_process_ids:
        omitted_query = omitted_query.where(ProcessExecution.id.not_in(requested_process_ids))
    for execution in db.scalars(omitted_query).all():
        external_ref = db.scalar(
            select(ProcessExecutionRelation.id).where(
                (
                    (ProcessExecutionRelation.source_execution_id == execution.id)
                    | (ProcessExecutionRelation.target_execution_id == execution.id)
                ),
                ProcessExecutionRelation.source_kind == "explicit",
            )
        )
        if external_ref is not None:
            raise SemanticConflict(
                "Process occurrence has protected external dependencies",
                code="protected_dependency",
            )
        execution.record_validity = "retracted"
        _revision(db, execution, change_note or "retract from scientific record")

    db.query(ProcessExecutionRelation).filter(
        ProcessExecutionRelation.source_record_id == sample.id,
        ProcessExecutionRelation.source_kind == "record_sequence",
    ).delete(synchronize_session=False)
    db.flush()
    process_ids = [process_by_occurrence[item.occurrence_id].id for item in process_occurrences]
    for source_id, target_id in zip(process_ids, process_ids[1:], strict=False):
        _check_precedes_cycle(db, source_id, [target_id])
        db.add(
            ProcessExecutionRelation(
                source_execution_id=source_id,
                target_execution_id=target_id,
                relation_type="precedes",
                source_kind="record_sequence",
                source_record_id=sample.id,
            )
        )

    db.query(DocumentOccurrence).filter(DocumentOccurrence.owner_id == sample.id).delete(
        synchronize_session=False
    )
    db.flush()
    for ordinal, occurrence in enumerate(occurrences):
        target = get_object(db, occurrence.target_id)
        if target is None:
            raise LookupError("occurrence target not found")
        execution = process_by_occurrence.get(occurrence.occurrence_id)
        binding_id = None
        stored_values = copy.deepcopy(occurrence.values)
        if occurrence.binding:
            owner_execution = process_by_occurrence.get(occurrence.binding.process_occurrence_id)
            if owner_execution is None:
                raise ValueError("binding references an unknown Process occurrence")
            bound = db.scalar(
                select(ProcessExecutionObjectBinding).where(
                    ProcessExecutionObjectBinding.execution_id == owner_execution.id,
                    ProcessExecutionObjectBinding.authoring_occurrence_id
                    == occurrence.occurrence_id,
                )
            )
            if bound is None:
                raise ValueError("object binding was not materialized")
            binding_id = bound.id
        row = DocumentOccurrence(
            owner_id=sample.id,
            occurrence_id=occurrence.occurrence_id,
            kind=occurrence.kind,
            ordinal=ordinal,
            target_id=occurrence.target_id,
            target_revision_id=occurrence.target_revision_id,
            execution_id=execution.id if execution else None,
            binding_id=binding_id,
            field_definition_snapshot_jsonb=copy.deepcopy(occurrence.field_definitions),
            values_jsonb=stored_values,
        )
        db.add(row)
        db.flush()
        db.add_all(_project_field_values(row, occurrence, ordinal))
    for execution in process_by_occurrence.values():
        db.expire(execution, ["object_bindings", "data_bindings"])
        _revision(db, execution, change_note or "save scientific record")
    sample.content_document = copy.deepcopy(document.blocks)
    sample.document_format_version = document.schema_version
    db.flush()


def create_sample_record(
    db: Session, payload: SampleRecordCreate, *, commit: bool = True
) -> dict[str, Any]:
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
                content_document=[],
            ),
        )
        sample.authoring_kind = "sample"
        db.flush()
        _sync_record(db, sample, payload.document, payload.occurrences, payload.change_note)
        _create_revision_in_session(
            db, sample.id, payload.change_note or "create scientific record"
        )
        if commit:
            db.commit()
        else:
            db.flush()
        return get_sample_record(db, sample.id)
    except Exception:
        db.rollback()
        raise


def create_sample_batch(
    db: Session, payload: SampleBatchCreate, *, commit: bool = True
) -> dict[str, Any]:
    client_row_ids = [row.client_row_id for row in payload.rows]
    if len(client_row_ids) != len(set(client_row_ids)):
        raise ValueError("Batch client_row_id values must be unique")
    try:
        rows = []
        for row in payload.rows:
            if row.record.project_scope_id != payload.project_scope_id:
                raise ValueError("Batch row project scope does not match the batch")
            rows.append(
                {
                    "client_row_id": row.client_row_id,
                    "record": create_sample_record(db, row.record, commit=False),
                }
            )
        if commit:
            db.commit()
        else:
            db.flush()
        return {"rows": rows}
    except Exception:
        db.rollback()
        raise


def update_sample_record(
    db: Session, sample_id: uuid.UUID, payload: SampleRecordPut, *, commit: bool = True
) -> dict[str, Any]:
    try:
        sample = _sample(db, sample_id, lock=True)
        current = _record_body(db, sample)
        if payload.base_record_sha256 != current["record_sha256"]:
            raise SemanticConflict("The record changed after it was loaded", code="stale_record")
        changes = {
            key: value
            for key, value in payload.sample.items()
            if key in {"title", "status", "tags", "properties_jsonb", "process_field_definitions"}
        }
        if changes:
            _update_object_in_session(db, sample, changes, managed_write=True)
        _sync_record(db, sample, payload.document, payload.occurrences, payload.change_note)
        _create_revision_in_session(
            db, sample.id, payload.change_note or "update scientific record"
        )
        if commit:
            db.commit()
            db.expire_all()
        else:
            db.flush()
        return get_sample_record(db, sample.id)
    except Exception:
        db.rollback()
        raise
