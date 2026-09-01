from __future__ import annotations

import json
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.models import Experiment, Project
from app.schemas import (
    CompareDifferenceOut,
    CompareExperimentOut,
    CompareMeasurementOut,
    CompareOut,
    CompareRequest,
)


def _leaf_paths(value: Any, path: str = "") -> list[tuple[str, Any]]:
    if isinstance(value, dict):
        if not value:
            return [(path or "/", value)]
        result: list[tuple[str, Any]] = []
        for key, item in value.items():
            result.extend(_leaf_paths(item, f"{path}/{key}"))
        return result
    if isinstance(value, list):
        return [(path or "/", value)]
    return [(path or "/", value)]


def _schema_at(schema: dict[str, Any], path: str) -> dict[str, Any]:
    current: dict[str, Any] = schema
    for segment in path.strip("/").split("/"):
        if not segment:
            continue
        current = (current.get("properties") or {}).get(segment, {})
        if not isinstance(current, dict):
            return {}
    return current


def _display_value(value: Any) -> Any:
    if isinstance(value, dict) and set(value) >= {"value", "unit"}:
        return f"{value.get('value')} {value.get('unit')}"
    return value


def build_compare(db: Session, payload: CompareRequest) -> CompareOut:
    if len(set(payload.experiment_ids)) != len(payload.experiment_ids):
        raise ValueError("experiment_ids must be unique")
    project = db.get(Project, payload.project_id)
    if project is None:
        raise LookupError("project not found")
    experiments = db.scalars(
        select(Experiment)
        .where(
            Experiment.project_id == payload.project_id, Experiment.id.in_(payload.experiment_ids)
        )
        .options(selectinload(Experiment.template), selectinload(Experiment.measurements))
    ).all()
    if len(experiments) != len(payload.experiment_ids):
        raise ValueError("all experiments must belong to the selected project")
    by_id = {item.id: item for item in experiments}
    ordered = [by_id[item] for item in payload.experiment_ids]
    rows: dict[str, dict[str, Any]] = {}
    labels: dict[str, str] = {}
    for experiment in ordered:
        for path, value in _leaf_paths(experiment.structured_data):
            rows.setdefault(path, {})[str(experiment.id)] = _display_value(value)
            labels[path] = _schema_at(experiment.template.json_schema, path).get("title", path)
    differences = []
    for path, values in rows.items():
        canonical = [
            json.dumps(values.get(str(experiment.id), "__missing__"), sort_keys=True, default=str)
            for experiment in ordered
        ]
        differences.append(
            CompareDifferenceOut(
                path=path, label=labels[path], values=values, differs=len(set(canonical)) > 1
            )
        )
    measurements = []
    selected = set(payload.measurement_ids)
    all_measurements = [
        measurement
        for experiment in ordered
        for measurement in experiment.measurements
        if not selected or measurement.id in selected
    ]
    if selected and len(all_measurements) != len(selected):
        raise ValueError("selected measurements must belong to selected experiments")
    baseline = None
    if all_measurements:
        first = all_measurements[0]
        baseline = (
            first.measurement_type,
            first.schema_key,
            first.schema_version,
            first.x_unit.strip(),
            first.y_unit.strip(),
        )
    for measurement in all_measurements:
        signature = (
            measurement.measurement_type,
            measurement.schema_key,
            measurement.schema_version,
            measurement.x_unit.strip(),
            measurement.y_unit.strip(),
        )
        compatible = baseline is None or signature == baseline
        reason = (
            None if compatible else "measurement type/schema version/axis units are incompatible"
        )
        measurements.append(
            CompareMeasurementOut(
                id=measurement.id,
                experiment_id=measurement.experiment_id,
                name=measurement.name,
                measurement_type=measurement.measurement_type,
                schema_key=measurement.schema_key,
                schema_version=measurement.schema_version,
                x_label=measurement.x_label,
                x_unit=measurement.x_unit,
                y_label=measurement.y_label,
                y_unit=measurement.y_unit,
                row_count=measurement.row_count,
                summary_json=measurement.summary_json,
                default_chart_type=measurement.default_chart_type,
                compatible=compatible,
                incompatibility_reason=reason,
            )
        )
    return CompareOut(
        project_id=payload.project_id,
        experiments=[
            CompareExperimentOut(
                id=item.id,
                code=item.code,
                title=item.title,
                status=item.status,
                template_id=item.template_id,
                template_version=item.template_version,
                parent_experiment_id=item.parent_experiment_id,
            )
            for item in ordered
        ],
        structured_differences=differences,
        measurements=measurements,
    )
