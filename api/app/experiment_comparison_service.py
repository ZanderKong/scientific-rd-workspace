from __future__ import annotations

import uuid
from collections import defaultdict
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.experiment_record_service import get_experiment_record
from app.models import DataPayload


def _flatten(value: Any, prefix: str = "") -> dict[str, Any]:
    if not isinstance(value, dict):
        return {prefix: value} if prefix else {}
    flattened: dict[str, Any] = {}
    for key in sorted(value):
        path = f"{prefix}.{key}" if prefix else str(key)
        nested = value[key]
        if isinstance(nested, dict):
            flattened.update(_flatten(nested, path))
        elif isinstance(nested, (str, int, float, bool)) or nested is None:
            flattened[path] = nested
    return flattened


def _value(value: Any, unit: str | None = None, available: bool = True) -> dict[str, Any]:
    return {"value": value, "unit": unit, "available": available}


def _state(values: list[dict[str, Any]]) -> tuple[str, bool]:
    if any(not item.get("available", True) for item in values):
        return "missing", False
    units = {item.get("unit") for item in values}
    if len(units) > 1:
        return "unit_conflict", True
    raw = [item.get("value") for item in values]
    same = all(item == raw[0] for item in raw[1:])
    return ("same" if same else "different"), False


def _dimension(
    key: str,
    label: str,
    group: str,
    values_by_sample: dict[str, dict[str, Any]],
    sample_codes: list[str],
) -> dict[str, Any]:
    values = {
        code: values_by_sample.get(code, _value(None, available=False)) for code in sample_codes
    }
    state, unit_conflict = _state(list(values.values()))
    return {
        "key": key,
        "label": label,
        "group": group,
        "values": values,
        "state": state,
        "unit_conflict": unit_conflict,
    }


def _processes_by_key(record: dict[str, Any]) -> dict[str, dict[str, Any]]:
    occurrences: defaultdict[str, int] = defaultdict(int)
    result: dict[str, dict[str, Any]] = {}
    for step in record["steps"]:
        process = step["process"]
        type_key = process["type_key"]
        occurrences[type_key] += 1
        key = f"{type_key}#{occurrences[type_key]}"
        result[key] = {"process": process, "resources": step.get("resources", [])}
    return result


def _append_sample_dimensions(
    dimensions: dict[str, dict[str, dict[str, Any]]], record: dict[str, Any], sample_code: str
) -> None:
    for key, value in _flatten(record["sample"].get("properties_jsonb") or {}).items():
        dimensions.setdefault(f"sample.{key}", {})[sample_code] = _value(value)
    for process_key, entry in _processes_by_key(record).items():
        process = entry["process"]
        dimensions.setdefault(f"process.{process_key}.presence", {})[sample_code] = _value(True)
        for key, value in _flatten(
            (process.get("properties_jsonb") or {}).get("parameters") or {}
        ).items():
            dimensions.setdefault(f"process.{process_key}.parameter.{key}", {})[sample_code] = (
                _value(value)
            )
        resource_occurrences: defaultdict[str, int] = defaultdict(int)
        for resource in entry["resources"]:
            obj = resource["object"]
            resource_occurrences[obj["kind"]] += 1
            resource_key = (
                f"process.{process_key}.resource.{obj['kind']}#{resource_occurrences[obj['kind']]}"
            )
            dimensions.setdefault(f"{resource_key}.identity", {})[sample_code] = _value(
                str(obj["id"])
            )
            for usage_key, usage_value in sorted((resource.get("usage_values") or {}).items()):
                dimensions.setdefault(f"{resource_key}.usage.{usage_key}", {})[sample_code] = (
                    _value(usage_value.get("value"), usage_value.get("unit"))
                )
    for data in record.get("data", []):
        dimensions.setdefault(f"data.{data['code']}.availability", {})[sample_code] = _value(True)


def _xy_series(db: Session, records: list[dict[str, Any]]) -> list[dict[str, Any]]:
    candidates: list[dict[str, Any]] = []
    for record in records:
        for data in record.get("data", []):
            payloads = db.scalars(
                select(DataPayload)
                .where(
                    DataPayload.data_object_id == uuid.UUID(str(data["id"])),
                    DataPayload.payload_kind == "xy_series",
                )
                .options(selectinload(DataPayload.points))
            ).all()
            for payload in payloads:
                metadata = payload.metadata_jsonb or {}
                signature = (
                    payload.schema_key,
                    metadata.get("x_label"),
                    metadata.get("x_unit"),
                    metadata.get("y_label"),
                    metadata.get("y_unit"),
                )
                candidates.append(
                    {
                        "signature": signature,
                        "sample_id": record["sample"]["id"],
                        "sample_code": record["sample"]["code"],
                        "data_id": data["id"],
                        "data_code": data["code"],
                        "payload_id": payload.id,
                        "name": payload.name,
                        "x_unit": metadata.get("x_unit"),
                        "y_unit": metadata.get("y_unit"),
                        "points": [
                            {
                                "payload_id": point.payload_id,
                                "ordinal": point.ordinal,
                                "source_row_number": point.source_row_number,
                                "x_value": point.x_value,
                                "y_value": point.y_value,
                            }
                            for point in payload.points
                        ],
                    }
                )
    grouped: defaultdict[tuple[Any, ...], list[dict[str, Any]]] = defaultdict(list)
    for item in candidates:
        grouped[item.pop("signature")].append(item)
    compatible: list[dict[str, Any]] = []
    for items in grouped.values():
        if len({item["sample_id"] for item in items}) >= 2:
            compatible.extend(items)
    return compatible


def compare_experiment(
    db: Session, experiment_id: uuid.UUID, *, differences_only: bool = False
) -> dict[str, Any]:
    record = get_experiment_record(db, experiment_id)
    member_records = [
        get_record_for_sample(db, member["sample"]["id"]) for member in record["members"]
    ]
    codes = [item["sample"]["code"] for item in member_records]
    dimensions_by_key: dict[str, dict[str, dict[str, Any]]] = {}
    for sample_record, code in zip(member_records, codes, strict=True):
        _append_sample_dimensions(dimensions_by_key, sample_record, code)
    dimensions = []
    for key in sorted(dimensions_by_key):
        group, label = _dimension_metadata(key)
        dimensions.append(_dimension(key, label, group, dimensions_by_key[key], codes))
    if differences_only:
        dimensions = [item for item in dimensions if item["state"] != "same"]
    experiment = record["experiment"]
    return {
        "experiment": experiment,
        "members": [member["sample"] for member in record["members"]],
        "dimensions": dimensions,
        "xy_series": _xy_series(db, member_records),
        "differences_only": differences_only,
    }


def get_record_for_sample(db: Session, sample_id: uuid.UUID | str) -> dict[str, Any]:
    from app.sample_record_service import get_sample_record

    return get_sample_record(db, uuid.UUID(str(sample_id)))


def _dimension_metadata(key: str) -> tuple[str, str]:
    if key.startswith("sample."):
        return "sample_fields", key.removeprefix("sample.")
    if ".presence" in key:
        return "process_presence", key.removeprefix("process.").removesuffix(".presence")
    if ".parameter." in key:
        return "process_parameters", key.removeprefix("process.")
    if ".identity" in key:
        return "resource_identity", key.removeprefix("process.")
    if ".usage." in key:
        return "resource_usage", key.removeprefix("process.")
    if key.startswith("data."):
        return "data_availability", key.removeprefix("data.")
    return "sample_fields", key
