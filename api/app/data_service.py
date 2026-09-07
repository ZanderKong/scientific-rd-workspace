from __future__ import annotations

import copy
import math
import uuid
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.models import (
    DataImport,
    DataPoint,
    DataRecord,
    DataRepresentation,
    DataScalar,
    DataSubjectAssignment,
    DataTableRow,
    DocumentOccurrence,
    ObjectRelation,
    ObjectRevision,
    ProcessExecution,
    ProcessExecutionDataBinding,
    ProcessExecutionObjectBinding,
    ProcessExecutionRelation,
    ResearchObject,
)
from app.relation_semantics import (
    SemanticConflict,
    lock_project_graph,
    validate_derived_cycle,
    validate_relation_scope,
)
from app.schemas import DataRecordCreate, DataRecordPut, DataRepresentationCreate, ObjectCreate
from app.scientific_record_service import lock_record_owner
from app.services import (
    _create_object_in_session,
    _create_revision_in_session,
    _update_object_in_session,
    get_object,
    object_out,
    sha256_json,
)


def acquisition_subject_ids(occurrences: list[Any]) -> list[uuid.UUID]:
    """Extract subject intent from the submitted acquisition document."""
    return [
        occurrence.target_id
        for occurrence in occurrences
        if occurrence.kind == "object"
        and occurrence.binding is not None
        and occurrence.binding.role == "subject"
    ]


def _data_object(db: Session, data_id: uuid.UUID, *, lock: bool = False) -> ResearchObject:
    data = lock_record_owner(db, data_id, expected_kind="data") if lock else get_object(db, data_id)
    if data is None or data.kind != "data":
        raise LookupError("data object not found")
    return data


def _representation_query(data_id: uuid.UUID | None = None) -> Any:
    query = select(DataRepresentation).options(
        selectinload(DataRepresentation.points),
        selectinload(DataRepresentation.scalar),
        selectinload(DataRepresentation.table_rows),
        selectinload(DataRepresentation.asset),
    )
    if data_id is not None:
        query = query.where(DataRepresentation.data_object_id == data_id)
    return query.order_by(DataRepresentation.created_at, DataRepresentation.id)


def representation_out(item: DataRepresentation) -> dict[str, Any]:
    return {
        "id": item.id,
        "data_object_id": item.data_object_id,
        "kind": item.kind,
        "name": item.name,
        "format": item.format,
        "schema_jsonb": item.schema_jsonb or {},
        "metadata_jsonb": item.metadata_jsonb or {},
        "summary_jsonb": item.summary_jsonb or {},
        "inline_payload_jsonb": item.inline_payload_jsonb,
        "asset_id": item.asset_id,
        "source_representation_id": item.source_representation_id,
        "provenance_jsonb": item.provenance_jsonb or {},
        "representation_sha256": item.representation_sha256,
        "points_count": len(item.points or []),
        "table_rows_count": len(item.table_rows or []),
        "table_rows": [
            {
                "representation_id": row.representation_id,
                "ordinal": row.ordinal,
                "source_row_number": row.source_row_number,
                "values": row.values_jsonb or {},
            }
            for row in item.table_rows or []
        ],
        "scalar": {
            "representation_id": item.scalar.representation_id,
            "value": item.scalar.value,
            "unit": item.scalar.unit,
        }
        if item.scalar
        else None,
        "created_at": item.created_at,
    }


def _relation_objects(db: Session, data_id: uuid.UUID, relation_type: str) -> list[ResearchObject]:
    rows = db.scalars(
        select(ObjectRelation)
        .where(
            ObjectRelation.source_object_id == data_id,
            ObjectRelation.relation_type == relation_type,
        )
        .order_by(ObjectRelation.created_at)
    ).all()
    result: list[ResearchObject] = []
    for row in rows:
        target = get_object(db, row.target_object_id)
        if target:
            result.append(target)
    return result


def _import_out(record: DataImport) -> dict[str, Any]:
    metadata = record.metadata_jsonb or {}
    return {
        "id": record.id,
        "data_object_id": record.data_object_id,
        "source_asset_id": record.source_asset_id,
        "representation_id": record.representation_id,
        "status": record.status,
        "source_format": record.source_format,
        "parser_key": record.parser_key,
        "parser_version": record.parser_version,
        "sheet_name": record.sheet_name,
        "source_sha256": record.source_sha256,
        "headers": record.header_json or [],
        "mapping_json": record.mapping_json,
        "warnings": record.warnings_json or [],
        "errors": record.errors_json or [],
        "row_count": record.row_count,
        "created_at": record.created_at,
        "completed_at": record.completed_at,
        "available_sheets": metadata.get("available_sheets", []),
        "preview_rows": metadata.get("preview_rows", []),
        "column_count": metadata.get("column_count", len(record.header_json or [])),
    }


def _data_occurrences(db: Session, data: ResearchObject) -> list[dict[str, Any]]:
    # Import locally to avoid the process_execution_service ↔ data_service
    # dependency cycle. The read path is shared with Sample's enriched DTO,
    # while retaining Data's own document as the canonical source.
    from app.process_execution_service import execution_out

    rows = list(
        db.scalars(
            select(DocumentOccurrence)
            .where(DocumentOccurrence.owner_id == data.id)
            .order_by(DocumentOccurrence.ordinal, DocumentOccurrence.id)
        ).all()
    )
    result: list[dict[str, Any]] = []
    targets = {
        item.id: item
        for item in db.scalars(
            select(ResearchObject).where(ResearchObject.id.in_({row.target_id for row in rows}))
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
    precedes_by_source: dict[uuid.UUID, list[uuid.UUID]] = {}
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
            precedes_by_source.setdefault(source_id, []).append(target_id)
    for row in rows:
        target = targets.get(row.target_id)
        execution = executions.get(row.execution_id) if row.execution_id else None
        values = copy.deepcopy(row.values_jsonb or {})
        binding = None
        if row.binding_id:
            bound = bindings.get(row.binding_id)
            if bound is not None:
                values = copy.deepcopy(bound.values_jsonb or {})
                process_row = process_rows.get(bound.execution_id)
                if process_row is not None:
                    binding = {
                        "process_occurrence_id": process_row.occurrence_id,
                        "binding_id": bound.id,
                        "direction": bound.direction,
                        "role": bound.role,
                    }
        result.append(
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
    return result


def get_data_record(db: Session, data_id: uuid.UUID) -> dict[str, Any]:
    data = _data_object(db, data_id)
    record = db.get(DataRecord, data.id)
    representations = db.scalars(_representation_query(data.id)).all()
    imports = db.scalars(
        select(DataImport)
        .where(DataImport.data_object_id == data.id)
        .order_by(DataImport.created_at)
    ).all()
    occurrences = _data_occurrences(db, data)
    subject_assignments = db.scalars(
        select(DataSubjectAssignment)
        .where(DataSubjectAssignment.data_id == data.id)
        .order_by(DataSubjectAssignment.created_at, DataSubjectAssignment.id)
    ).all()
    body = {
        "data": object_out(data),
        "document": {
            "schema_version": data.document_format_version,
            "blocks": data.content_document,
        },
        "occurrences": occurrences,
        "editable": True,
        "edit_blockers": [],
        "scientific_type": record.scientific_type if record else None,
        "description": record.description if record else None,
        "origin_representation_id": record.origin_representation_id if record else None,
        "representations": [representation_out(item) for item in representations],
        "subjects": [object_out(item) for item in _relation_objects(db, data.id, "subject")],
        "subject_assignments": [
            {
                "id": item.id,
                "subject_id": item.subject_id,
                "subject_revision_id": item.subject_revision_id,
                "source_kind": item.source_kind,
                "source_ref_id": item.source_ref_id,
            }
            for item in subject_assignments
        ],
        "derived_from": [
            object_out(item) for item in _relation_objects(db, data.id, "derived_from")
        ],
        "imports": [_import_out(item) for item in imports],
    }
    own_revision_sha = db.scalar(
        select(ObjectRevision.snapshot_sha256)
        .where(ObjectRevision.object_id == data.id)
        .order_by(ObjectRevision.revision_number.desc())
        .limit(1)
    )
    token_body = {
        "data": {
            key: value
            for key, value in body["data"].items()
            if key not in {"created_at", "updated_at"}
        },
        "scientific_type": body["scientific_type"],
        "description": body["description"],
        "document": body["document"],
        "occurrences": [
            {
                key: value
                for key, value in occurrence.items()
                if key not in {"execution", "object", "label_snapshot"}
            }
            for occurrence in body["occurrences"]
        ],
        "origin_representation_id": body["origin_representation_id"],
        "representations": [item["id"] for item in body["representations"]],
        "subject_assignments": body["subject_assignments"],
        "derived_from": [item["id"] for item in body["derived_from"]],
        "revision": own_revision_sha,
    }
    return {"record_sha256": sha256_json(token_body), **body}


def get_data_record_revision(
    db: Session, data_id: uuid.UUID, revision_number: int
) -> ObjectRevision:
    """Read an immutable Data snapshot without hydrating current relations."""
    data = _data_object(db, data_id)
    revision = db.scalar(
        select(ObjectRevision).where(
            ObjectRevision.object_id == data.id,
            ObjectRevision.revision_number == revision_number,
        )
    )
    if revision is None:
        raise LookupError("data record revision not found")
    return revision


def create_data_record(
    db: Session, payload: DataRecordCreate, *, commit: bool = True
) -> dict[str, Any]:
    try:
        data = _create_object_in_session(
            db,
            ObjectCreate(
                kind="data",
                code=payload.data.code,
                title=payload.data.title,
                status=payload.data.status,
                project_scope_id=payload.project_scope_id,
                tags=payload.data.tags,
                properties_jsonb=payload.data.properties_jsonb,
                content_document=payload.data.content_document,
            ),
        )
        data.authoring_kind = "data"
        db.flush()
        db.add(
            DataRecord(
                data_object_id=data.id,
                scientific_type=payload.scientific_type,
                description=payload.description,
            )
        )
        sync_data_subject_assignments(
            db,
            data.id,
            subject_ids=payload.subject_ids,
            source_kind="manual",
            source_ref_id=None,
        )
        _create_revision_in_session(db, data.id, payload.change_note)
        if commit:
            db.commit()
        else:
            db.flush()
        return get_data_record(db, data.id)
    except Exception:
        db.rollback()
        raise


def update_data_record(
    db: Session,
    data_id: uuid.UUID,
    payload: DataRecordPut,
    *,
    expected_record_sha256: str | None = None,
    commit: bool = True,
) -> dict[str, Any]:
    try:
        data = _data_object(db, data_id)
        lock_project_graph(db, data.project_scope_id)
        data = _data_object(db, data_id, lock=True)
        current = get_data_record(db, data.id)
        expected = expected_record_sha256 or payload.base_record_sha256
        if not expected:
            raise ValueError("revision_required")
        if expected.strip('"') != current["record_sha256"]:
            raise SemanticConflict(
                "The Data record changed after it was loaded", code="stale_record"
            )
        changes = {
            key: value
            for key, value in payload.model_dump(exclude_unset=True).items()
            if key in {"title", "status", "tags", "properties_jsonb"}
        }
        if changes:
            _update_object_in_session(db, data, changes, managed_write=True)
        record = db.get(DataRecord, data.id)
        if record is None:
            record = DataRecord(data_object_id=data.id)
            db.add(record)
        for key in ("scientific_type", "description"):
            if key in payload.model_fields_set:
                setattr(record, key, getattr(payload, key))
        if payload.document is not None or payload.occurrences is not None:
            if payload.document is None or payload.occurrences is None:
                raise ValueError("document and occurrences must be updated together")
            from app.sample_record_service import _sync_record

            _sync_record(
                db,
                data,
                payload.document,
                payload.occurrences,
                payload.change_note or "update Data scientific record",
            )
            sync_data_subject_assignments(
                db,
                data.id,
                subject_ids=acquisition_subject_ids(payload.occurrences),
                source_kind="acquisition_document",
                source_ref_id=data.id,
            )
        if payload.subject_ids is not None:
            sync_data_subject_assignments(
                db,
                data.id,
                subject_ids=payload.subject_ids,
                source_kind="manual",
                source_ref_id=None,
            )
        _create_revision_in_session(db, data.id, payload.change_note)
        if commit:
            db.commit()
        else:
            db.flush()
        return get_data_record(db, data.id)
    except Exception:
        db.rollback()
        raise


def _validate_inline(kind: str, value: dict[str, Any] | None) -> dict[str, Any] | None:
    if value is None:
        return None
    if kind == "structured" and "value" in value:
        number = value["value"]
        if (
            isinstance(number, bool)
            or not isinstance(number, (int, float))
            or not math.isfinite(float(number))
        ):
            raise ValueError("structured value must be finite")
    return copy.deepcopy(value)


def _create_representation_in_session(
    db: Session, data: ResearchObject, payload: DataRepresentationCreate
) -> DataRepresentation:
    if payload.asset_id is not None:
        from app.models import Asset

        if db.get(Asset, payload.asset_id) is None:
            raise LookupError("asset not found")
    if payload.source_representation_id is not None:
        source = db.get(DataRepresentation, payload.source_representation_id)
        if source is None or source.data_object_id != data.id:
            raise SemanticConflict(
                "source representation must belong to the same Data", code="validation_failed"
            )
        seen: set[uuid.UUID] = set()
        current = source
        while current is not None:
            if current.id in seen:
                raise SemanticConflict(
                    "representation lineage cycle is not allowed", code="cycle_detected"
                )
            seen.add(current.id)
            current = (
                db.get(DataRepresentation, current.source_representation_id)
                if current.source_representation_id is not None
                else None
            )
    inline = _validate_inline(payload.kind, payload.inline_payload_jsonb)
    item = DataRepresentation(
        data_object_id=data.id,
        kind=payload.kind,
        name=payload.name.strip(),
        format=payload.format,
        schema_jsonb=copy.deepcopy(payload.schema_jsonb),
        metadata_jsonb=copy.deepcopy(payload.metadata_jsonb),
        summary_jsonb=copy.deepcopy(payload.summary_jsonb),
        inline_payload_jsonb=inline,
        asset_id=payload.asset_id,
        source_representation_id=payload.source_representation_id,
        provenance_jsonb=copy.deepcopy(payload.provenance_jsonb),
        representation_sha256=sha256_json(
            {
                "kind": payload.kind,
                "name": payload.name,
                "format": payload.format,
                "schema": payload.schema_jsonb,
                "metadata": payload.metadata_jsonb,
                "summary": payload.summary_jsonb,
                "inline": inline,
                "asset_id": str(payload.asset_id) if payload.asset_id else None,
                "source": str(payload.source_representation_id)
                if payload.source_representation_id
                else None,
                "provenance": payload.provenance_jsonb,
            }
        ),
    )
    db.add(item)
    db.flush()
    _materialize_inline_children(db, item)
    return item


def _materialize_inline_children(db: Session, item: DataRepresentation) -> None:
    payload = item.inline_payload_jsonb or {}
    if item.kind == "structured" and "value" in payload:
        db.add(
            DataScalar(
                representation_id=item.id, value=float(payload["value"]), unit=payload.get("unit")
            )
        )
    rows = payload.get("rows") if isinstance(payload.get("rows"), list) else None
    if item.kind == "table" and rows is not None:
        db.add_all(
            DataTableRow(
                representation_id=item.id,
                ordinal=index,
                source_row_number=index + 1,
                values_jsonb=row if isinstance(row, dict) else {},
            )
            for index, row in enumerate(rows)
        )
    points = payload.get("points") if isinstance(payload.get("points"), list) else None
    if item.kind == "table" and points is not None:
        db.add_all(
            DataPoint(
                representation_id=item.id,
                ordinal=index,
                source_row_number=int(point.get("source_row_number", index + 1)),
                x_value=float(point["x"]),
                y_value=float(point["y"]),
            )
            for index, point in enumerate(points)
        )


def create_representation(
    db: Session, data_id: uuid.UUID, payload: DataRepresentationCreate
) -> dict[str, Any]:
    try:
        data = _data_object(db, data_id)
        lock_project_graph(db, data.project_scope_id)
        data = _data_object(db, data_id, lock=True)
        item = _create_representation_in_session(db, data, payload)
        record = db.get(DataRecord, data.id)
        if record is None:
            record = DataRecord(data_object_id=data.id)
            db.add(record)
        if record.origin_representation_id is None:
            record.origin_representation_id = item.id
        _create_revision_in_session(db, data.id, f"add representation {item.kind}: {item.name}")
        db.commit()
        result = db.scalar(_representation_query(data.id).where(DataRepresentation.id == item.id))
        if result is None:
            raise LookupError("created representation not found")
        return representation_out(result)
    except Exception:
        db.rollback()
        raise


def sync_system_relations_for_data(
    db: Session,
    data_id: uuid.UUID,
    *,
    subject_ids: list[uuid.UUID] | None = None,
    derived_from_ids: list[uuid.UUID] | None = None,
) -> None:
    data = _data_object(db, data_id)
    lock_project_graph(db, data.project_scope_id)
    data = _data_object(db, data_id, lock=True)
    validated: dict[str, list[ResearchObject]] = {}
    for relation_type, ids in (("subject", subject_ids), ("derived_from", derived_from_ids)):
        if ids is None:
            continue
        seen: set[uuid.UUID] = set()
        targets: list[ResearchObject] = []
        for target_id in ids:
            if target_id in seen:
                continue
            target = get_object(db, target_id)
            if target is None:
                raise LookupError("relation target object not found")
            from app.relation_semantics import validate_relation_kinds

            validate_relation_kinds(data, target, relation_type)
            validate_relation_scope(data, target)
            if relation_type == "derived_from":
                validate_derived_cycle(db, data, target)
            targets.append(target)
            seen.add(target_id)
        validated[relation_type] = targets
    for relation_type, targets in validated.items():
        db.query(ObjectRelation).filter(
            ObjectRelation.source_object_id == data.id,
            ObjectRelation.relation_type == relation_type,
        ).delete(synchronize_session=False)
        db.add_all(
            ObjectRelation(
                source_object_id=data.id,
                target_object_id=target.id,
                relation_type=relation_type,
                role=None,
                properties_jsonb={"system_managed": True},
            )
            for target in targets
        )


def sync_data_subject_assignments(
    db: Session,
    data_id: uuid.UUID,
    *,
    subject_ids: list[uuid.UUID],
    source_kind: str,
    source_ref_id: uuid.UUID | None,
) -> None:
    if source_kind not in {"manual", "acquisition_document", "producer"}:
        raise ValueError("invalid Data subject source kind")
    data = _data_object(db, data_id)
    lock_project_graph(db, data.project_scope_id)
    data = _data_object(db, data_id, lock=True)
    from app.relation_semantics import validate_relation_kinds

    subjects: list[ResearchObject] = []
    seen: set[uuid.UUID] = set()
    for subject_id in subject_ids:
        if subject_id in seen:
            continue
        subject = get_object(db, subject_id)
        if subject is None:
            raise LookupError("Data subject not found")
        validate_relation_kinds(data, subject, "subject")
        validate_relation_scope(data, subject)
        subjects.append(subject)
        seen.add(subject_id)

    source_filter = [
        DataSubjectAssignment.data_id == data.id,
        DataSubjectAssignment.source_kind == source_kind,
    ]
    if source_ref_id is None:
        source_filter.append(DataSubjectAssignment.source_ref_id.is_(None))
    else:
        source_filter.append(DataSubjectAssignment.source_ref_id == source_ref_id)
    db.query(DataSubjectAssignment).filter(*source_filter).delete(synchronize_session=False)
    for subject in subjects:
        revision_id = db.scalar(
            select(ObjectRevision.id)
            .where(ObjectRevision.object_id == subject.id)
            .order_by(ObjectRevision.revision_number.desc())
            .limit(1)
        )
        db.add(
            DataSubjectAssignment(
                data_id=data.id,
                subject_id=subject.id,
                subject_revision_id=revision_id,
                source_kind=source_kind,
                source_ref_id=source_ref_id,
            )
        )
    db.flush()

    all_subject_ids = list(
        db.scalars(
            select(DataSubjectAssignment.subject_id)
            .where(DataSubjectAssignment.data_id == data.id)
            .distinct()
        ).all()
    )
    sync_system_relations_for_data(db, data.id, subject_ids=all_subject_ids)
    db.flush()
