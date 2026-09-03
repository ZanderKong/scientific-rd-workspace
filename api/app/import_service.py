from __future__ import annotations

import csv
import hashlib
import io
import json
import math
import uuid
import zipfile
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from openpyxl import load_workbook
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.models import Attachment, DataImport, DataPayload, DataPoint, DataTableRow, ResearchObject
from app.schemas import ImportCommitMapping, ImportPreviewRequest
from app.storage import LocalStorageAdapter


class ImportValidationError(Exception):
    def __init__(
        self,
        code: str,
        message: str,
        errors: list[dict[str, Any]],
        warnings: list[dict[str, Any]] | None = None,
    ) -> None:
        super().__init__(message)
        self.code = code
        self.message = message
        self.errors = errors
        self.warnings = warnings or []


@dataclass
class ParsedTable:
    source_format: str
    original_headers: list[Any]
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
    if hasattr(value, "isoformat"):
        return value.isoformat()
    return str(value)


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
    raw_headers = rows[0]
    headers = [str(value).strip() if value is not None else "" for value in raw_headers]
    errors: list[dict[str, Any]] = []
    for index, header in enumerate(headers, start=1):
        if not header:
            errors.append(_error("Header must not be blank.", row=1, column=str(index)))
    if len(set(headers)) != len(headers):
        seen: set[str] = set()
        for header in headers:
            if header and header in seen:
                errors.append(
                    _error("Header names must be unique after trimming.", row=1, column=header)
                )
            seen.add(header)
    if len(headers) > settings.max_import_columns:
        errors.append(
            _error(f"The file has more than {settings.max_import_columns} columns.", row=1)
        )
    data: list[list[Any]] = []
    last_nonempty = 0
    for source_row, original in enumerate(rows[1:], start=2):
        values = list(original)
        if any(
            value is not None and (not isinstance(value, str) or value.strip()) for value in values
        ):
            last_nonempty = source_row
    empty_trailing = 0
    for source_row, original in enumerate(rows[1:], start=2):
        values = list(original)
        if len(values) > len(headers):
            errors.append(_error("Row has more cells than the header.", row=source_row))
        values.extend([None] * max(0, len(headers) - len(values)))
        empty = all(
            value is None or (isinstance(value, str) and not value.strip()) for value in values
        )
        if empty:
            if source_row > last_nonempty:
                empty_trailing += 1
                continue
            errors.append(_error("Internal empty rows are not supported.", row=source_row))
            continue
        data.append([_json_value(value) for value in values[: len(headers)]])
    if len(data) > settings.max_import_rows:
        errors.append(_error(f"The file has more than {settings.max_import_rows} data rows."))
    if not data:
        errors.append(_error("At least one data row is required."))
    if errors:
        raise ImportValidationError("invalid_table", "The file structure is invalid.", errors[:50])
    warnings = (
        [_error(f"Ignored {empty_trailing} completely empty trailing row(s).")]
        if empty_trailing
        else []
    )
    return ParsedTable(
        source_format=source_format,
        original_headers=[_json_value(value) for value in raw_headers],
        headers=headers,
        rows=data,
        preview_rows=data[: settings.import_preview_rows],
        sheet_name=sheet_name,
        available_sheets=available_sheets,
        warnings=warnings,
        row_count=len(data),
        column_count=len(headers),
    )


def _parse_csv(path: Path) -> ParsedTable:
    try:
        raw = path.read_bytes()
        if b"\x00" in raw:
            raise ImportValidationError(
                "binary_file",
                "NUL bytes are not supported in CSV files.",
                [_error("Invalid UTF-8 text.")],
            )
        decoded = raw.decode("utf-8-sig")
        rows = list(csv.reader(io.StringIO(decoded), delimiter=",", strict=True))
    except UnicodeDecodeError as exc:
        raise ImportValidationError(
            "invalid_encoding", "CSV must be UTF-8 text.", [_error("Unable to decode UTF-8.")]
        ) from exc
    except csv.Error as exc:
        raise ImportValidationError(
            "invalid_csv", "CSV quoting is invalid.", [_error(str(exc))]
        ) from exc
    return _validate_table(rows, source_format="csv", sheet_name=None, available_sheets=[])


def _parse_xlsx(path: Path, selected_sheet: str | None) -> ParsedTable:
    settings = get_settings()
    try:
        with zipfile.ZipFile(path) as archive:
            if len(archive.infolist()) > settings.max_xlsx_archive_entries:
                raise ImportValidationError(
                    "xlsx_limits",
                    "Workbook archive is too large.",
                    [_error("Too many archive entries.")],
                )
            if (
                sum(info.file_size for info in archive.infolist())
                > settings.max_xlsx_expanded_bytes
            ):
                raise ImportValidationError(
                    "xlsx_limits",
                    "Workbook expanded size is too large.",
                    [_error("Expanded size limit exceeded.")],
                )
        workbook = load_workbook(path, read_only=True, data_only=True, keep_links=False)
    except ImportValidationError:
        raise
    except (zipfile.BadZipFile, OSError, ValueError) as exc:
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
                [_error(f"Choose one of: {', '.join(available)}")],
            )
        rows = [list(row) for row in workbook[sheet].iter_rows(values_only=True)]
        return _validate_table(
            rows, source_format="xlsx", sheet_name=sheet, available_sheets=available
        )
    finally:
        workbook.close()


def parse_attachment(
    attachment: Attachment, adapter: LocalStorageAdapter, selected_sheet: str | None = None
) -> ParsedTable:
    if attachment.size_bytes > get_settings().max_import_bytes:
        raise ImportValidationError(
            "import_too_large",
            "The attachment exceeds the import limit.",
            [_error("Import size limit exceeded.")],
        )
    path = adapter.open(attachment.storage_key)
    suffix = Path(attachment.original_filename).suffix.lower()
    if suffix == ".csv":
        return _parse_csv(path)
    if suffix == ".xlsx":
        return _parse_xlsx(path, selected_sheet)
    raise ImportValidationError(
        "unsupported_format",
        "Only CSV and XLSX imports are supported.",
        [_error("Use a .csv or .xlsx attachment.")],
    )


def create_preview(
    db: Session,
    data_object: ResearchObject,
    payload: ImportPreviewRequest,
    adapter: LocalStorageAdapter,
) -> DataImport:
    if data_object.kind != "data":
        raise ValueError("imports require a Data object")
    attachment = db.get(Attachment, payload.source_attachment_id)
    if attachment is None:
        raise LookupError("attachment not found")
    if attachment.object_id != data_object.id:
        raise ValueError("source attachment belongs to another object")
    parsed = parse_attachment(attachment, adapter, payload.sheet_name)
    record = DataImport(
        data_object_id=data_object.id,
        source_attachment_id=attachment.id,
        status="preview_ready",
        source_format=parsed.source_format,
        parser_key="tabular-xy",
        parser_version=1,
        sheet_name=parsed.sheet_name,
        source_sha256=attachment.sha256,
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
    if value is None or isinstance(value, bool) or isinstance(value, (dict, list)):
        raise ValueError("Expected a finite number.")
    try:
        number = float(value)
    except (TypeError, ValueError) as exc:
        raise ValueError("Expected a finite number.") from exc
    if not math.isfinite(number):
        raise ValueError("Expected a finite number.")
    return number


def commit_import(
    db: Session,
    import_id: uuid.UUID | str,
    mapping: ImportCommitMapping,
    adapter: LocalStorageAdapter,
) -> DataPayload:
    record = db.scalar(
        select(DataImport).where(DataImport.id == uuid.UUID(str(import_id))).with_for_update()
    )
    if record is None:
        raise LookupError("data import not found")
    if record.status != "preview_ready":
        raise ValueError("data import is no longer available for commit")
    data_object = db.get(ResearchObject, record.data_object_id)
    attachment = db.get(Attachment, record.source_attachment_id)
    if data_object is None or data_object.kind != "data":
        raise ValueError("source Data object not found")
    if attachment is None:
        raise ValueError("source attachment not found")
    if attachment.sha256 != record.source_sha256:
        raise ValueError("source attachment checksum changed")
    parsed = parse_attachment(attachment, adapter, mapping.sheet_name or record.sheet_name)
    if parsed.headers != record.header_json:
        raise ValueError("source headers changed since preview")
    if mapping.sheet_name and mapping.sheet_name != parsed.sheet_name:
        raise ValueError("selected worksheet changed since preview")
    columns = {header: index for index, header in enumerate(parsed.headers)}
    warnings = list(parsed.warnings)
    if mapping.payload_kind == "table":
        requested = {column.key: column for column in mapping.columns}
        missing = [column.key for column in mapping.columns if column.key not in columns]
        if missing:
            raise ImportValidationError(
                "invalid_mapping",
                "Mapped column does not exist.",
                [_error(f"Missing: {', '.join(missing)}")],
            )
        table_rows: list[tuple[int, dict[str, Any]]] = []
        errors: list[dict[str, Any]] = []
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
                        if isinstance(raw, bool):
                            value = raw
                        elif str(raw).strip().casefold() in {"true", "yes", "1"}:
                            value = True
                        elif str(raw).strip().casefold() in {"false", "no", "0"}:
                            value = False
                        else:
                            raise ValueError("Expected a boolean.")
                    else:
                        value = str(raw)
                    values[key] = value
                except ValueError as exc:
                    errors.append(_error(str(exc), row=source_row, column=key))
            table_rows.append((source_row, values))
        if errors:
            raise ImportValidationError(
                "invalid_table_value", "Table cells are invalid.", errors[:50], warnings
            )
        if not table_rows:
            raise ImportValidationError(
                "empty_payload",
                "No table rows were imported.",
                [_error("At least one row is required.")],
            )
        canonical = "\n".join(
            f"{ordinal},{source_row},"
            f"{json.dumps(values, ensure_ascii=False, sort_keys=True, separators=(',', ':'))}"
            for ordinal, (source_row, values) in enumerate(table_rows)
        )
        payload = DataPayload(
            data_object_id=data_object.id,
            payload_kind="table",
            name=mapping.payload_name.strip(),
            schema_key="table",
            schema_version=1,
            metadata_jsonb={
                "columns": [column.model_dump(exclude_none=True) for column in mapping.columns]
            },
            summary_jsonb={"rows_count": len(table_rows), "columns_count": len(mapping.columns)},
            source_attachment_id=attachment.id,
            payload_sha256=hashlib.sha256(canonical.encode()).hexdigest(),
        )
        db.add(payload)
        db.flush()
        db.add_all(
            [
                DataTableRow(
                    payload_id=payload.id,
                    ordinal=ordinal,
                    source_row_number=source_row,
                    values_jsonb=values,
                )
                for ordinal, (source_row, values) in enumerate(table_rows)
            ]
        )
    else:
        if (
            mapping.x is None
            or mapping.y is None
            or mapping.x.column not in columns
            or mapping.y.column not in columns
        ):
            raise ImportValidationError(
                "invalid_mapping",
                "Mapped column does not exist.",
                [_error("Choose existing columns.")],
            )
        points: list[tuple[int, float, float]] = []
        errors = []
        for source_row, row in enumerate(parsed.rows, start=2):
            try:
                x = _finite_number(row[columns[mapping.x.column]])
                y = _finite_number(row[columns[mapping.y.column]])
                points.append((source_row, x, y))
            except ValueError as exc:
                errors.append(_error(str(exc), row=source_row))
        if errors:
            raise ImportValidationError(
                "non_numeric_value", "Mapped cells are invalid.", errors[:50], warnings
            )
        if not points:
            raise ImportValidationError(
                "empty_payload",
                "No numeric points were imported.",
                [_error("At least one point is required.")],
            )
        if any(points[index][1] >= points[index + 1][1] for index in range(len(points) - 1)):
            warnings.append(
                _error("X values are not strictly increasing; source order was preserved.")
            )
        canonical = "\n".join(
            f"{ordinal},{row},{x:.17g},{y:.17g}" for ordinal, (row, x, y) in enumerate(points)
        )
        xs = [point[1] for point in points]
        ys = [point[2] for point in points]
        payload = DataPayload(
            data_object_id=data_object.id,
            payload_kind="xy_series",
            name=mapping.payload_name.strip(),
            schema_key="xy-series",
            schema_version=1,
            metadata_jsonb={
                "x_label": mapping.x.label.strip(),
                "x_unit": mapping.x.unit.strip(),
                "y_label": mapping.y.label.strip(),
                "y_unit": mapping.y.unit.strip(),
            },
            summary_jsonb={
                "x_min": min(xs),
                "x_max": max(xs),
                "y_min": min(ys),
                "y_max": max(ys),
                "y_mean": sum(ys) / len(ys),
            },
            source_attachment_id=attachment.id,
            payload_sha256=hashlib.sha256(canonical.encode()).hexdigest(),
        )
        db.add(payload)
        db.flush()
        db.add_all(
            [
                DataPoint(
                    payload_id=payload.id,
                    ordinal=ordinal,
                    source_row_number=row,
                    x_value=x,
                    y_value=y,
                )
                for ordinal, (row, x, y) in enumerate(points)
            ]
        )
    record.status = "completed"
    record.payload_id = payload.id
    record.mapping_json = mapping.model_dump(mode="json")
    record.warnings_json = warnings
    record.errors_json = []
    record.completed_at = datetime.now(UTC)
    db.commit()
    db.refresh(payload)
    return payload
