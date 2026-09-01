from __future__ import annotations

import csv
import hashlib
import io
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
from app.models import Attachment, Experiment, Measurement, MeasurementImport, MeasurementPoint
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
    preview_rows: int,
    source_format: str,
    sheet_name: str | None,
    available_sheets: list[str],
) -> ParsedTable:
    settings = get_settings()
    if not rows:
        raise ImportValidationError(
            "empty_file", "The file contains no header row.", [_error("A header row is required.")]
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
    empty_trailing = 0
    last_nonempty = 0
    for index, original in enumerate(rows[1:], start=2):
        values = list(original)
        if any(
            value is not None and (not isinstance(value, str) or value.strip()) for value in values
        ):
            last_nonempty = index
    for source_row, original in enumerate(rows[1:], start=2):
        values = list(original)
        if len(values) > len(headers):
            errors.append(_error("Row has more cells than the header.", row=source_row))
        if len(values) < len(headers):
            values.extend([None] * (len(headers) - len(values)))
        if all(value is None or (isinstance(value, str) and not value.strip()) for value in values):
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
    warnings = []
    if empty_trailing:
        warnings.append(_error(f"Ignored {empty_trailing} completely empty trailing row(s)."))
    return ParsedTable(
        source_format=source_format,
        original_headers=[_json_value(value) for value in raw_headers],
        headers=headers,
        rows=data,
        preview_rows=data[:preview_rows],
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
                [_error("The file is not valid UTF-8 text.")],
            )
        text = raw.decode("utf-8-sig")
    except UnicodeDecodeError as exc:
        raise ImportValidationError(
            "invalid_encoding",
            "CSV must be UTF-8 text.",
            [_error("Unable to decode the file as UTF-8.")],
        ) from exc
    try:
        rows = list(csv.reader(io.StringIO(text), delimiter=",", strict=True))
    except csv.Error as exc:
        raise ImportValidationError(
            "invalid_csv", "CSV quoting is invalid.", [_error(str(exc))]
        ) from exc
    return _validate_table(
        rows,
        preview_rows=get_settings().import_preview_rows,
        source_format="csv",
        sheet_name=None,
        available_sheets=[],
    )


def _parse_xlsx(path: Path, selected_sheet: str | None) -> ParsedTable:
    settings = get_settings()
    try:
        with zipfile.ZipFile(path) as archive:
            if len(archive.infolist()) > settings.max_xlsx_archive_entries:
                raise ImportValidationError(
                    "xlsx_limits",
                    "The workbook contains too many archive entries.",
                    [_error("Workbook archive is too large.")],
                )
            expanded = sum(info.file_size for info in archive.infolist())
            if expanded > settings.max_xlsx_expanded_bytes:
                raise ImportValidationError(
                    "xlsx_limits",
                    "The workbook expands beyond the safety limit.",
                    [_error("Workbook expanded size is too large.")],
                )
        workbook = load_workbook(path, read_only=True, data_only=True, keep_links=False)
    except ImportValidationError:
        raise
    except (zipfile.BadZipFile, OSError, ValueError) as exc:
        raise ImportValidationError(
            "invalid_xlsx", "The workbook is not a readable XLSX file.", [_error(str(exc))]
        ) from exc
    try:
        available = [
            sheet for sheet in workbook.sheetnames if workbook[sheet].sheet_state == "visible"
        ]
        if not available:
            raise ImportValidationError(
                "no_visible_sheet",
                "The workbook has no visible worksheet.",
                [_error("At least one visible worksheet is required.")],
            )
        sheet = selected_sheet or available[0]
        if sheet not in available:
            raise ImportValidationError(
                "sheet_not_found",
                "The selected worksheet is not visible or does not exist.",
                [_error(f"Choose one of: {', '.join(available)}")],
            )
        worksheet = workbook[sheet]
        rows = [list(row) for row in worksheet.iter_rows(values_only=True)]
        return _validate_table(
            rows,
            preview_rows=settings.import_preview_rows,
            source_format="xlsx",
            sheet_name=sheet,
            available_sheets=available,
        )
    finally:
        workbook.close()


def parse_attachment(
    attachment: Attachment, adapter: LocalStorageAdapter, selected_sheet: str | None = None
) -> ParsedTable:
    settings = get_settings()
    if attachment.size_bytes > settings.max_import_bytes:
        raise ImportValidationError(
            "import_too_large",
            f"Imports are limited to {settings.max_import_bytes} bytes.",
            [_error("The attachment exceeds the import limit.")],
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
    db: Session, experiment: Experiment, payload: ImportPreviewRequest, adapter: LocalStorageAdapter
) -> MeasurementImport:
    attachment = db.get(Attachment, payload.source_attachment_id)
    if attachment is None:
        raise LookupError("attachment not found")
    if attachment.experiment_id != experiment.id:
        raise ValueError("source attachment belongs to another experiment")
    parsed = parse_attachment(attachment, adapter, payload.sheet_name)
    record = MeasurementImport(
        experiment_id=experiment.id,
        source_attachment_id=attachment.id,
        status="preview_ready",
        source_format=parsed.source_format,
        parser_key="tabular-xy",
        parser_version=1,
        sheet_name=parsed.sheet_name,
        source_sha256=attachment.sha256,
        header_json=parsed.headers,
        source_metadata_json={
            "available_sheets": parsed.available_sheets,
            "original_headers": parsed.original_headers,
            "row_count": parsed.row_count,
            "column_count": parsed.column_count,
            "preview_rows": parsed.preview_rows,
        },
        warnings_json=parsed.warnings,
        errors_json=[],
        row_count=parsed.row_count,
    )
    db.add(record)
    db.commit()
    db.refresh(record)
    return record


def _finite_number(value: Any, row: int, column: str) -> float:
    if isinstance(value, bool) or value is None or isinstance(value, (dict, list)):
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
) -> Measurement:
    parsed_import_id = uuid.UUID(str(import_id))
    record = db.scalar(
        select(MeasurementImport).where(MeasurementImport.id == parsed_import_id).with_for_update()
    )
    if record is None:
        raise LookupError("measurement import not found")
    if record.status != "preview_ready":
        raise ValueError("measurement import is no longer available for commit")
    attachment = db.get(Attachment, record.source_attachment_id)
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
    errors: list[dict[str, Any]] = []
    for axis in (mapping.x, mapping.y):
        if axis.column not in columns:
            errors.append(_error("Mapped column does not exist.", column=axis.column))
        if axis.unit.strip() == "":
            errors.append(_error("Unit must not be blank.", column=axis.column))
    if errors:
        raise ImportValidationError("invalid_mapping", "The mapping is invalid.", errors)
    x_index, y_index = columns[mapping.x.column], columns[mapping.y.column]
    points: list[tuple[int, float, float]] = []
    warnings: list[dict[str, Any]] = list(parsed.warnings)
    for source_row, row in enumerate(parsed.rows, start=2):
        try:
            x = _finite_number(row[x_index], source_row, mapping.x.column)
        except ValueError as exc:
            errors.append(_error(str(exc), row=source_row, column=mapping.x.column))
            continue
        try:
            y = _finite_number(row[y_index], source_row, mapping.y.column)
        except ValueError as exc:
            errors.append(_error(str(exc), row=source_row, column=mapping.y.column))
            continue
        points.append((source_row, x, y))
    if len(errors) > 50:
        errors = errors[:50]
    if errors:
        raise ImportValidationError(
            "non_numeric_value", f"{len(errors)} mapped cells are invalid.", errors, warnings
        )
    ignored = [
        header for header in parsed.headers if header not in {mapping.x.column, mapping.y.column}
    ]
    if any(points[index][1] >= points[index + 1][1] for index in range(len(points) - 1)):
        warnings.append(_error("X values are not strictly increasing; source order was preserved."))
    canonical = "\n".join(
        f"{ordinal},{source_row},{x:.17g},{y:.17g}"
        for ordinal, (source_row, x, y) in enumerate(points)
    )
    digest = hashlib.sha256(canonical.encode()).hexdigest()
    xs, ys = [point[1] for point in points], [point[2] for point in points]
    summary = {
        "x_min": min(xs),
        "x_max": max(xs),
        "y_min": min(ys),
        "y_max": max(ys),
        "y_mean": sum(ys) / len(ys),
    }
    measurement = Measurement(
        experiment_id=record.experiment_id,
        import_id=record.id,
        name=mapping.measurement_name.strip(),
        measurement_type=mapping.measurement_type,
        schema_key="xy-series",
        schema_version=1,
        default_chart_type=mapping.default_chart_type,
        x_label=mapping.x.label.strip(),
        x_unit=mapping.x.unit.strip(),
        y_label=mapping.y.label.strip(),
        y_unit=mapping.y.unit.strip(),
        row_count=len(points),
        summary_json=summary,
        points_sha256=digest,
    )
    db.add(measurement)
    db.flush()
    db.add_all(
        [
            MeasurementPoint(
                measurement_id=measurement.id,
                ordinal=ordinal,
                source_row_number=source_row,
                x_value=x,
                y_value=y,
            )
            for ordinal, (source_row, x, y) in enumerate(points)
        ]
    )
    record.status = "completed"
    record.mapping_json = {**mapping.model_dump(mode="json"), "ignored_columns": ignored}
    record.warnings_json = warnings
    record.errors_json = []
    record.completed_at = datetime.now(UTC)
    db.commit()
    db.refresh(measurement)
    return measurement
