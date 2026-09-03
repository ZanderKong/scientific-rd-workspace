from __future__ import annotations

import copy
import math
import uuid
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.models import Attachment, DataImport, DataPayload, DataScalar, DataTableRow, ResearchObject
from app.schemas import (
    DataFileCreate,
    DataRecordCreate,
    DataScalarCreate,
    DataTableCreate,
    ObjectCreate,
)
from app.services import (
    _create_object_in_session,
    _create_revision_in_session,
    get_object,
    object_out,
    sha256_json,
)


def _data_object(db: Session, data_id: uuid.UUID) -> ResearchObject:
    data = get_object(db, data_id)
    if data is None or data.kind != "data":
        raise LookupError("data object not found")
    return data


def _payload_query(data_id: uuid.UUID) -> Any:
    return (
        select(DataPayload)
        .where(DataPayload.data_object_id == data_id)
        .options(
            selectinload(DataPayload.points),
            selectinload(DataPayload.scalar),
            selectinload(DataPayload.table_rows),
        )
        .order_by(DataPayload.created_at, DataPayload.id)
    )


def payload_out(payload: DataPayload) -> dict[str, Any]:
    metadata = payload.metadata_jsonb or {}
    return {
        "id": payload.id,
        "data_object_id": payload.data_object_id,
        "payload_kind": payload.payload_kind,
        "name": payload.name,
        "schema_key": payload.schema_key,
        "schema_version": payload.schema_version,
        "metadata_jsonb": metadata,
        "summary_jsonb": payload.summary_jsonb or {},
        "source_attachment_id": payload.source_attachment_id,
        "payload_sha256": payload.payload_sha256,
        "points_count": len(payload.points or []),
        "table_rows_count": len(payload.table_rows or []),
        "table_columns": metadata.get("columns", []),
        "table_rows": [
            {
                "payload_id": row.payload_id,
                "ordinal": row.ordinal,
                "source_row_number": row.source_row_number,
                "values": row.values_jsonb or {},
            }
            for row in payload.table_rows or []
        ],
        "scalar": (
            {
                "payload_id": payload.scalar.payload_id,
                "value": payload.scalar.value,
                "unit": payload.scalar.unit,
            }
            if payload.scalar is not None
            else None
        ),
        "created_at": payload.created_at,
    }


def _import_out(record: DataImport) -> dict[str, Any]:
    return {
        "id": record.id,
        "data_object_id": record.data_object_id,
        "source_attachment_id": record.source_attachment_id,
        "payload_id": record.payload_id,
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
    }


def get_data_record(db: Session, data_id: uuid.UUID) -> dict[str, Any]:
    data = _data_object(db, data_id)
    payloads = db.scalars(_payload_query(data.id)).all()
    imports = db.scalars(
        select(DataImport)
        .where(DataImport.data_object_id == data.id)
        .order_by(DataImport.created_at)
    ).all()
    projection = {
        "data": object_out(data),
        "payloads": [payload_out(payload) for payload in payloads],
        "imports": [_import_out(item) for item in imports],
    }
    return {"record_sha256": sha256_json(projection), **projection}


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
                type_version_id=payload.data.type_version_id,
                properties_jsonb=copy.deepcopy(payload.data.properties_jsonb),
                content_document=copy.deepcopy(payload.data.content_document),
            ),
        )
        _create_revision_in_session(db, data.id, payload.change_note)
        db.commit()
        return get_data_record(db, data.id)
    except Exception:
        db.rollback()
        raise


def _payload_base(
    data_id: uuid.UUID, item: DataScalarCreate | DataTableCreate | DataFileCreate
) -> dict[str, Any]:
    if isinstance(item, DataScalarCreate):
        return {
            "payload_kind": "scalar",
            "name": item.name,
            "schema_key": item.schema_key,
            "schema_version": 1,
            "metadata_jsonb": copy.deepcopy(item.metadata_jsonb),
        }
    if isinstance(item, DataTableCreate):
        columns = [column.model_dump(exclude_none=True) for column in item.columns]
        return {
            "payload_kind": "table",
            "name": item.name,
            "schema_key": item.schema_key,
            "schema_version": 1,
            "metadata_jsonb": {**copy.deepcopy(item.metadata_jsonb), "columns": columns},
        }
    return {
        "payload_kind": "file",
        "name": item.name,
        "schema_key": item.schema_key,
        "schema_version": 1,
        "metadata_jsonb": copy.deepcopy(item.metadata_jsonb),
    }


def create_scalar_payload(
    db: Session, data_id: uuid.UUID, item: DataScalarCreate
) -> dict[str, Any]:
    try:
        data = _data_object(db, data_id)
        if not math.isfinite(item.value):
            raise ValueError("scalar value must be finite")
        base = _payload_base(data.id, item)
        source = {**base, "value": item.value, "unit": item.unit}
        payload = DataPayload(
            data_object_id=data.id,
            **base,
            summary_jsonb={"value": item.value, "unit": item.unit},
            payload_sha256=sha256_json(source),
        )
        db.add(payload)
        db.flush()
        db.add(DataScalar(payload_id=payload.id, value=item.value, unit=item.unit))
        db.flush()
        db.commit()
        result = db.scalar(_payload_query(data.id).where(DataPayload.id == payload.id))
        if result is None:
            raise LookupError("created scalar payload not found")
        return payload_out(result)
    except Exception:
        db.rollback()
        raise


def _validate_table_rows(item: DataTableCreate) -> list[dict[str, Any]]:
    columns = {column.key: column for column in item.columns}
    if len(columns) != len(item.columns):
        raise ValueError("table column keys must be unique")
    rows: list[dict[str, Any]] = []
    for ordinal, row in enumerate(item.rows):
        unknown = set(row.values) - set(columns)
        if unknown:
            raise ValueError(f"table row {ordinal} contains unknown columns")
        values: dict[str, Any] = {}
        for key, column in columns.items():
            value = row.values.get(key)
            if value is None:
                values[key] = None
                continue
            if column.value_type == "number":
                if (
                    isinstance(value, bool)
                    or not isinstance(value, (int, float))
                    or not math.isfinite(value)
                ):
                    raise ValueError(f"table row {ordinal} column {key} must be a finite number")
            elif column.value_type == "text" and not isinstance(value, str):
                raise ValueError(f"table row {ordinal} column {key} must be text")
            elif column.value_type == "boolean" and not isinstance(value, bool):
                raise ValueError(f"table row {ordinal} column {key} must be boolean")
            values[key] = value
        rows.append(values)
    return rows


def create_table_payload(db: Session, data_id: uuid.UUID, item: DataTableCreate) -> dict[str, Any]:
    try:
        data = _data_object(db, data_id)
        rows = _validate_table_rows(item)
        base = _payload_base(data.id, item)
        payload = DataPayload(
            data_object_id=data.id,
            **base,
            summary_jsonb={"rows_count": len(rows), "columns_count": len(item.columns)},
            payload_sha256=sha256_json({**base, "rows": rows}),
        )
        db.add(payload)
        db.flush()
        db.add_all(
            [
                DataTableRow(
                    payload_id=payload.id,
                    ordinal=ordinal,
                    source_row_number=ordinal + 1,
                    values_jsonb=values,
                )
                for ordinal, values in enumerate(rows)
            ]
        )
        db.flush()
        db.commit()
        result = db.scalar(_payload_query(data.id).where(DataPayload.id == payload.id))
        if result is None:
            raise LookupError("created table payload not found")
        return payload_out(result)
    except Exception:
        db.rollback()
        raise


def create_file_payload(db: Session, data_id: uuid.UUID, item: DataFileCreate) -> dict[str, Any]:
    try:
        data = _data_object(db, data_id)
        attachment = db.get(Attachment, item.source_attachment_id)
        if attachment is None:
            raise LookupError("source attachment not found")
        source = object_out(data)
        if attachment.object_id != data.id:
            attachment_object = get_object(db, attachment.object_id)
            if (
                attachment_object is None
                or attachment_object.project_scope_id != data.project_scope_id
            ):
                raise ValueError("source attachment is outside the Data project scope")
        base = _payload_base(data.id, item)
        payload = DataPayload(
            data_object_id=data.id,
            **base,
            source_attachment_id=attachment.id,
            summary_jsonb={"filename": attachment.original_filename, "sha256": attachment.sha256},
            payload_sha256=sha256_json(
                {**base, "attachment_sha256": attachment.sha256, "data": source}
            ),
        )
        db.add(payload)
        db.flush()
        db.commit()
        result = db.scalar(_payload_query(data.id).where(DataPayload.id == payload.id))
        if result is None:
            raise LookupError("created file payload not found")
        return payload_out(result)
    except Exception:
        db.rollback()
        raise
