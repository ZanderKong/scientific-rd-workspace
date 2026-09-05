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
    DataTableRow,
    ObjectRelation,
    ResearchObject,
)
from app.relation_semantics import SemanticConflict, validate_derived_cycle, validate_relation_scope
from app.schemas import DataRecordCreate, DataRecordPut, DataRepresentationCreate, ObjectCreate
from app.services import (
    _create_object_in_session,
    _create_revision_in_session,
    _update_object_in_session,
    get_object,
    object_out,
    sha256_json,
)


def _data_object(db: Session, data_id: uuid.UUID) -> ResearchObject:
    data = get_object(db, data_id)
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


def get_data_record(db: Session, data_id: uuid.UUID) -> dict[str, Any]:
    data = _data_object(db, data_id)
    record = db.get(DataRecord, data.id)
    representations = db.scalars(_representation_query(data.id)).all()
    imports = db.scalars(
        select(DataImport)
        .where(DataImport.data_object_id == data.id)
        .order_by(DataImport.created_at)
    ).all()
    body = {
        "data": object_out(data),
        "scientific_type": record.scientific_type if record else None,
        "description": record.description if record else None,
        "origin_representation_id": record.origin_representation_id if record else None,
        "representations": [representation_out(item) for item in representations],
        "subjects": [object_out(item) for item in _relation_objects(db, data.id, "subject")],
        "derived_from": [
            object_out(item) for item in _relation_objects(db, data.id, "derived_from")
        ],
        "imports": [_import_out(item) for item in imports],
    }
    return {"record_sha256": sha256_json(body), **body}


def create_data_record(db: Session, payload: DataRecordCreate) -> dict[str, Any]:
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
        db.add(
            DataRecord(
                data_object_id=data.id,
                scientific_type=payload.scientific_type,
                description=payload.description,
            )
        )
        _create_revision_in_session(db, data.id, payload.change_note)
        db.commit()
        return get_data_record(db, data.id)
    except Exception:
        db.rollback()
        raise


def update_data_record(db: Session, data_id: uuid.UUID, payload: DataRecordPut) -> dict[str, Any]:
    try:
        data = _data_object(db, data_id)
        changes = {
            key: value
            for key, value in payload.model_dump(exclude_unset=True).items()
            if key in {"title", "status", "tags", "properties_jsonb"}
        }
        if changes:
            _update_object_in_session(db, data, changes)
        record = db.get(DataRecord, data.id)
        if record is None:
            record = DataRecord(data_object_id=data.id)
            db.add(record)
        for key in ("scientific_type", "description"):
            if key in payload.model_fields_set:
                setattr(record, key, getattr(payload, key))
        _create_revision_in_session(db, data.id, payload.change_note)
        db.commit()
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
