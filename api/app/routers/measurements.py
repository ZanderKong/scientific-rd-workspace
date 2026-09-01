from __future__ import annotations

import uuid
from typing import Any

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.core.config import get_settings
from app.db import get_db
from app.import_service import ImportValidationError, commit_import, create_preview
from app.models import Attachment, Experiment, Measurement, MeasurementImport, MeasurementPoint
from app.schemas import (
    ImportCommitMapping,
    ImportDiagnostic,
    ImportPreviewOut,
    ImportPreviewRequest,
    MeasurementImportOut,
    MeasurementOut,
    MeasurementPointOut,
)
from app.services import attachment_storage_key
from app.storage import LocalStorageAdapter, sanitise_filename

router = APIRouter(tags=["measurements"])


def _storage() -> LocalStorageAdapter:
    return LocalStorageAdapter(get_settings().storage_root)


def _measurement_out(measurement: Measurement) -> MeasurementOut:
    import_record = measurement.import_record
    return MeasurementOut(
        id=measurement.id,
        experiment_id=measurement.experiment_id,
        import_id=measurement.import_id,
        name=measurement.name,
        measurement_type=measurement.measurement_type,
        schema_key=measurement.schema_key,
        schema_version=measurement.schema_version,
        default_chart_type=measurement.default_chart_type,
        x_label=measurement.x_label,
        x_unit=measurement.x_unit,
        y_label=measurement.y_label,
        y_unit=measurement.y_unit,
        row_count=measurement.row_count,
        summary_json=measurement.summary_json,
        points_sha256=measurement.points_sha256,
        source_attachment_id=import_record.source_attachment_id,
        source_sha256=import_record.source_sha256,
        created_at=measurement.created_at,
    )


def _preview_out(record: MeasurementImport) -> ImportPreviewOut:
    metadata = record.source_metadata_json or {}
    return ImportPreviewOut(
        id=record.id,
        experiment_id=record.experiment_id,
        source_attachment_id=record.source_attachment_id,
        status=record.status,
        source_format=record.source_format,
        parser_key=record.parser_key,
        parser_version=record.parser_version,
        sheet_name=record.sheet_name,
        available_sheets=metadata.get("available_sheets", []),
        headers=record.header_json,
        preview_rows=metadata.get("preview_rows", []),
        row_count=record.row_count,
        column_count=metadata.get("column_count", len(record.header_json)),
        source_sha256=record.source_sha256,
        warnings=[*record.warnings_json],
        errors=[*record.errors_json],
        created_at=record.created_at,
    )


def _diagnostic(exc: ImportValidationError, import_id: uuid.UUID | None = None) -> dict[str, Any]:
    return ImportDiagnostic(
        code=exc.code,
        message=exc.message,
        import_id=import_id,
        errors=exc.errors,
        warnings=exc.warnings,
    ).model_dump(mode="json")


@router.post("/experiments/{experiment_id}/measurement-imports/attachment", status_code=201)
def upload_import_attachment(
    experiment_id: uuid.UUID, file: UploadFile = File(...), db: Session = Depends(get_db)
) -> dict[str, Any]:
    """Convenience endpoint that creates a normal Phase 1 attachment for the import wizard."""
    experiment = db.get(Experiment, experiment_id)
    if experiment is None:
        raise HTTPException(status_code=404, detail="experiment not found")
    filename = sanitise_filename(file.filename or "attachment")
    attachment_id = uuid.uuid4()
    key = attachment_storage_key(experiment_id, attachment_id, filename)
    adapter = _storage()
    size, digest = adapter.put(key, file.file)
    if size > get_settings().max_upload_bytes:
        adapter.delete(key)
        raise HTTPException(status_code=413, detail="attachment exceeds the 25 MB limit")
    attachment = Attachment(
        id=attachment_id,
        experiment_id=experiment_id,
        original_filename=filename,
        storage_key=key,
        content_type=file.content_type,
        size_bytes=size,
        sha256=digest,
    )
    try:
        db.add(attachment)
        db.commit()
        db.refresh(attachment)
    except Exception:
        db.rollback()
        adapter.delete(key)
        raise
    return {
        "id": str(attachment.id),
        "experiment_id": str(attachment.experiment_id),
        "original_filename": attachment.original_filename,
        "content_type": attachment.content_type,
        "size_bytes": attachment.size_bytes,
        "sha256": attachment.sha256,
        "created_at": attachment.created_at.isoformat(),
    }


@router.post(
    "/experiments/{experiment_id}/measurement-imports/preview",
    response_model=ImportPreviewOut,
    status_code=201,
)
def preview_import(
    experiment_id: uuid.UUID, payload: ImportPreviewRequest, db: Session = Depends(get_db)
) -> ImportPreviewOut:
    experiment = db.get(Experiment, experiment_id)
    if experiment is None:
        raise HTTPException(status_code=404, detail="experiment not found")
    try:
        return _preview_out(create_preview(db, experiment, payload, _storage()))
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ImportValidationError as exc:
        raise HTTPException(status_code=422, detail=_diagnostic(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc


@router.get(
    "/experiments/{experiment_id}/measurement-imports", response_model=list[MeasurementImportOut]
)
def list_imports(
    experiment_id: uuid.UUID, db: Session = Depends(get_db)
) -> list[MeasurementImport]:
    if db.get(Experiment, experiment_id) is None:
        raise HTTPException(status_code=404, detail="experiment not found")
    return list(
        db.scalars(
            select(MeasurementImport)
            .where(MeasurementImport.experiment_id == experiment_id)
            .order_by(MeasurementImport.created_at.desc())
        )
    )


@router.get("/measurement-imports/{import_id}", response_model=ImportPreviewOut)
def get_import(import_id: uuid.UUID, db: Session = Depends(get_db)) -> ImportPreviewOut:
    record = db.get(MeasurementImport, import_id)
    if record is None:
        raise HTTPException(status_code=404, detail="measurement import not found")
    return _preview_out(record)


@router.post(
    "/measurement-imports/{import_id}/commit", response_model=MeasurementOut, status_code=201
)
def commit_import_route(
    import_id: uuid.UUID, payload: ImportCommitMapping, db: Session = Depends(get_db)
) -> MeasurementOut:
    try:
        measurement = commit_import(db, str(import_id), payload, _storage())
    except LookupError as exc:
        db.rollback()
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ImportValidationError as exc:
        db.rollback()
        record = db.get(MeasurementImport, import_id)
        if record is not None and record.status == "preview_ready":
            record.status = "failed"
            record.mapping_json = payload.model_dump(mode="json")
            record.errors_json = exc.errors
            record.warnings_json = exc.warnings
            db.commit()
        raise HTTPException(status_code=422, detail=_diagnostic(exc, import_id)) from exc
    except ValueError as exc:
        db.rollback()
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    except Exception:
        db.rollback()
        raise
    measurement = db.scalar(
        select(Measurement)
        .where(Measurement.id == measurement.id)
        .options(selectinload(Measurement.import_record))
    )
    assert measurement is not None
    return _measurement_out(measurement)


@router.delete("/measurement-imports/{import_id}", status_code=204)
def discard_import(import_id: uuid.UUID, db: Session = Depends(get_db)) -> None:
    record = db.get(MeasurementImport, import_id)
    if record is None:
        raise HTTPException(status_code=404, detail="measurement import not found")
    if record.status == "completed":
        raise HTTPException(
            status_code=409, detail="completed measurement imports cannot be discarded"
        )
    db.delete(record)
    db.commit()


@router.get("/experiments/{experiment_id}/measurements", response_model=list[MeasurementOut])
def list_measurements(
    experiment_id: uuid.UUID, db: Session = Depends(get_db)
) -> list[MeasurementOut]:
    if db.get(Experiment, experiment_id) is None:
        raise HTTPException(status_code=404, detail="experiment not found")
    rows = db.scalars(
        select(Measurement)
        .where(Measurement.experiment_id == experiment_id)
        .options(selectinload(Measurement.import_record))
        .order_by(Measurement.created_at.desc())
    ).all()
    return [_measurement_out(row) for row in rows]


@router.get("/measurements/{measurement_id}", response_model=MeasurementOut)
def get_measurement(measurement_id: uuid.UUID, db: Session = Depends(get_db)) -> MeasurementOut:
    row = db.scalar(
        select(Measurement)
        .where(Measurement.id == measurement_id)
        .options(selectinload(Measurement.import_record))
    )
    if row is None:
        raise HTTPException(status_code=404, detail="measurement not found")
    return _measurement_out(row)


@router.get("/measurements/{measurement_id}/points", response_model=list[MeasurementPointOut])
def list_points(measurement_id: uuid.UUID, db: Session = Depends(get_db)) -> list[MeasurementPoint]:
    if db.get(Measurement, measurement_id) is None:
        raise HTTPException(status_code=404, detail="measurement not found")
    return list(
        db.scalars(
            select(MeasurementPoint)
            .where(MeasurementPoint.measurement_id == measurement_id)
            .order_by(MeasurementPoint.ordinal)
        )
    )
