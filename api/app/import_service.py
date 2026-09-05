from __future__ import annotations

import csv
import io
import math
import uuid
import zipfile
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, BinaryIO

from openpyxl import load_workbook
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.data_service import _create_representation_in_session
from app.models import Asset, DataImport, DataRepresentation, DataTableRow, ResearchObject
from app.schemas import DataRepresentationCreate, ImportCommitMapping, ImportPreviewRequest
from app.storage import StorageProvider


class ImportValidationError(Exception):
    def __init__(
        self,
        code: str,
        message: str,
        errors: list[dict[str, Any]],
        warnings: list[dict[str, Any]] | None = None,
    ) -> None:
        super().__init__(message)
        self.code, self.message, self.errors, self.warnings = code, message, errors, warnings or []


@dataclass
class ParsedTable:
    source_format: str
    headers: list[str]
    rows: list[list[Any]]
    preview_rows: list[list[Any]]
    sheet_name: str | None
    available_sheets: list[str]
    warnings: list[dict[str, Any]]
    row_count: int
    column_count: int


def _error(message: str, *, row: int | None = None, column: str | None = None) -> dict[str, Any]:
    return {"row": row, "column": column, "message": message}


def _json_value(value: Any) -> Any:
    if value is None or isinstance(value, (str, int, float, bool)):
        return value
    return value.isoformat() if hasattr(value, "isoformat") else str(value)


def _validate_table(
    rows: list[list[Any]],
    *,
    source_format: str,
    sheet_name: str | None,
    available_sheets: list[str],
) -> ParsedTable:
    settings = get_settings()
    if not rows:
        raise ImportValidationError(
            "empty_file", "A header row is required.", [_error("File is empty.")]
        )
    headers = [str(value).strip() if value is not None else "" for value in rows[0]]
    errors: list[dict[str, Any]] = []
    if any(not header for header in headers):
        errors.append(_error("Header must not be blank.", row=1))
    if len(headers) != len(set(headers)):
        errors.append(_error("Header names must be unique after trimming.", row=1))
    if len(headers) > settings.max_import_columns:
        errors.append(
            _error(f"The file has more than {settings.max_import_columns} columns.", row=1)
        )
    nonempty = [
        row
        for row in rows[1:]
        if any(value is not None and (not isinstance(value, str) or value.strip()) for value in row)
    ]
    if len(nonempty) > settings.max_import_rows:
        errors.append(_error(f"The file has more than {settings.max_import_rows} data rows."))
    parsed: list[list[Any]] = []
    for row_number, original in enumerate(rows[1:], start=2):
        values = list(original)
        if len(values) > len(headers):
            errors.append(_error("Row has more cells than the header.", row=row_number))
        values.extend([None] * max(0, len(headers) - len(values)))
        if not any(
            value is not None and (not isinstance(value, str) or value.strip()) for value in values
        ):
            continue
        parsed.append([_json_value(value) for value in values[: len(headers)]])
    if not parsed:
        errors.append(_error("At least one data row is required."))
    if errors:
        raise ImportValidationError("invalid_table", "The file structure is invalid.", errors[:50])
    return ParsedTable(
        source_format,
        headers,
        parsed,
        parsed[: settings.import_preview_rows],
        sheet_name,
        available_sheets,
        [],
        len(parsed),
        len(headers),
    )


def _read_bytes(source: Path | BinaryIO) -> bytes:
    return source.read_bytes() if isinstance(source, Path) else source.read()


def _parse_csv(source: Path | BinaryIO) -> ParsedTable:
    raw = _read_bytes(source)
    if b"\x00" in raw:
        raise ImportValidationError(
            "binary_file",
            "NUL bytes are not supported in CSV files.",
            [_error("Invalid UTF-8 text.")],
        )
    try:
        rows = list(csv.reader(io.StringIO(raw.decode("utf-8-sig")), strict=True))
    except (UnicodeDecodeError, csv.Error) as exc:
        raise ImportValidationError(
            "invalid_csv", "CSV must be valid UTF-8 text.", [_error(str(exc))]
        ) from exc
    return _validate_table(rows, source_format="csv", sheet_name=None, available_sheets=[])


def _parse_xlsx(source: Path | BinaryIO, selected_sheet: str | None) -> ParsedTable:
    raw = _read_bytes(source)
    settings = get_settings()
    try:
        with zipfile.ZipFile(io.BytesIO(raw)) as archive:
            if (
                len(archive.infolist()) > settings.max_xlsx_archive_entries
                or sum(item.file_size for item in archive.infolist())
                > settings.max_xlsx_expanded_bytes
            ):
                raise ImportValidationError(
                    "xlsx_limits",
                    "Workbook size limit exceeded.",
                    [_error("Workbook archive is too large.")],
                )
        workbook = load_workbook(io.BytesIO(raw), read_only=True, data_only=True, keep_links=False)
    except ImportValidationError:
        raise
    except Exception as exc:
        raise ImportValidationError(
            "invalid_xlsx", "Workbook is not a readable XLSX file.", [_error(str(exc))]
        ) from exc
    try:
        available = [
            name for name in workbook.sheetnames if workbook[name].sheet_state == "visible"
        ]
        if not available:
            raise ImportValidationError(
                "no_visible_sheet",
                "Workbook has no visible worksheet.",
                [_error("At least one visible sheet is required.")],
            )
        sheet = selected_sheet or available[0]
        if sheet not in available:
            raise ImportValidationError(
                "sheet_not_found",
                "Selected worksheet is not visible or does not exist.",
                [_error(", ".join(available))],
            )
        return _validate_table(
            [list(row) for row in workbook[sheet].iter_rows(values_only=True)],
            source_format="xlsx",
            sheet_name=sheet,
            available_sheets=available,
        )
    finally:
        workbook.close()


def parse_asset(
    asset: Asset, provider: StorageProvider, selected_sheet: str | None = None
) -> ParsedTable:
    if asset.size_bytes > get_settings().max_import_bytes:
        raise ImportValidationError(
            "import_too_large",
            "The asset exceeds the import limit.",
            [_error("Import size limit exceeded.")],
        )
    source = provider.open(asset.object_key)
    suffix = Path(asset.original_filename).suffix.casefold()
    if suffix == ".csv":
        return _parse_csv(source)
    if suffix == ".xlsx":
        return _parse_xlsx(source, selected_sheet)
    raise ImportValidationError(
        "unsupported_format",
        "Only CSV and XLSX imports are supported.",
        [_error("Use a .csv or .xlsx asset.")],
    )


def create_preview(
    db: Session,
    data_object: ResearchObject,
    payload: ImportPreviewRequest,
    provider: StorageProvider,
) -> DataImport:
    if data_object.kind != "data":
        raise ValueError("imports require a Data object")
    asset = db.get(Asset, payload.source_asset_id)
    if asset is None:
        raise LookupError("asset not found")
    parsed = parse_asset(asset, provider, payload.sheet_name)
    record = DataImport(
        data_object_id=data_object.id,
        source_asset_id=asset.id,
        status="preview_ready",
        source_format=parsed.source_format,
        parser_key="tabular",
        parser_version=1,
        sheet_name=parsed.sheet_name,
        source_sha256=asset.sha256,
        header_json=parsed.headers,
        metadata_jsonb={
            "available_sheets": parsed.available_sheets,
            "preview_rows": parsed.preview_rows,
            "column_count": parsed.column_count,
        },
        mapping_json=None,
        warnings_json=parsed.warnings,
        errors_json=[],
        row_count=parsed.row_count,
    )
    db.add(record)
    db.commit()
    db.refresh(record)
    return record


def _finite_number(value: Any) -> float:
    try:
        number = float(value)
    except (TypeError, ValueError) as exc:
        raise ValueError("Expected a finite number.") from exc
    if not math.isfinite(number):
        raise ValueError("Expected a finite number.")
    return number


def commit_import(
    db: Session, import_id: uuid.UUID | str, mapping: ImportCommitMapping, provider: StorageProvider
) -> DataRepresentation:
    record = db.scalar(
        select(DataImport).where(DataImport.id == uuid.UUID(str(import_id))).with_for_update()
    )
    if record is None:
        raise LookupError("data import not found")
    if record.status != "preview_ready":
        raise ValueError("data import is no longer available for commit")
    data = db.get(ResearchObject, record.data_object_id)
    asset = db.get(Asset, record.source_asset_id)
    if data is None or data.kind != "data" or asset is None:
        raise ValueError("source Data or Asset not found")
    if asset.sha256 != record.source_sha256:
        raise ValueError("source asset checksum changed")
    parsed = parse_asset(asset, provider, mapping.sheet_name or record.sheet_name)
    if parsed.headers != record.header_json:
        raise ValueError("source headers changed since preview")
    columns = {header: index for index, header in enumerate(parsed.headers)}
    requested = {column.key: column for column in mapping.columns}
    missing = [column.key for column in mapping.columns if column.key not in columns]
    if missing:
        raise ImportValidationError(
            "invalid_mapping",
            "Mapped column does not exist.",
            [_error(f"Missing: {', '.join(missing)}")],
        )
    rows: list[dict[str, Any]] = []
    for source_row, row in enumerate(parsed.rows, start=2):
        values: dict[str, Any] = {}
        for key, column in requested.items():
            raw = row[columns[key]]
            try:
                if raw in (None, ""):
                    value = None
                elif column.value_type == "number":
                    value = _finite_number(raw)
                elif column.value_type == "boolean":
                    value = (
                        raw
                        if isinstance(raw, bool)
                        else str(raw).strip().casefold() in {"true", "yes", "1"}
                    )
                else:
                    value = str(raw)
            except ValueError as exc:
                raise ImportValidationError(
                    "invalid_table_value",
                    "Table cells are invalid.",
                    [_error(str(exc), row=source_row, column=key)],
                    parsed.warnings,
                ) from exc
            values[key] = value
        rows.append(values)
    raw_rep = db.scalar(
        select(DataRepresentation)
        .where(
            DataRepresentation.data_object_id == data.id,
            DataRepresentation.kind == "raw_file",
            DataRepresentation.asset_id == asset.id,
        )
        .order_by(DataRepresentation.created_at)
    )
    if raw_rep is None:
        raw_rep = _create_representation_in_session(
            db,
            data,
            DataRepresentationCreate(
                kind="raw_file",
                name=asset.original_filename,
                format=record.source_format,
                asset_id=asset.id,
                summary_jsonb={"filename": asset.original_filename, "sha256": asset.sha256},
                provenance_jsonb={"source": "import"},
            ),
        )
    representation = _create_representation_in_session(
        db,
        data,
        DataRepresentationCreate(
            kind="table",
            name=mapping.representation_name,
            format="tabular",
            schema_jsonb={
                "columns": [column.model_dump(exclude_none=True) for column in mapping.columns]
            },
            summary_jsonb={"rows_count": len(rows), "columns_count": len(mapping.columns)},
            source_representation_id=raw_rep.id,
            provenance_jsonb={"import_id": str(record.id), "source_asset_id": str(asset.id)},
        ),
    )
    # Keep source row numbers in the normalized child table for reproducibility.
    for index, values in enumerate(rows):
        db.add(
            DataTableRow(
                representation_id=representation.id,
                ordinal=index,
                source_row_number=index + 2,
                values_jsonb=values,
            )
        )
    record.status = "completed"
    record.representation_id = representation.id
    record.mapping_json = mapping.model_dump(mode="json")
    record.completed_at = datetime.now(UTC)
    db.commit()
    return (
        db.scalar(select(DataRepresentation).where(DataRepresentation.id == representation.id))
        or representation
    )
