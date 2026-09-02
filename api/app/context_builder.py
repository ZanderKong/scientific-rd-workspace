from __future__ import annotations

import copy
import hashlib
import json
import math
import uuid
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.compare_service import build_compare
from app.core.config import Settings
from app.models import (
    EvidenceRecord,
    Experiment,
    ExperimentRevision,
    LiteratureRecord,
    Measurement,
    Project,
)
from app.schemas import AnalysisRunCreate, CompareRequest


class ContextValidationError(ValueError):
    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code
        self.message = message


def canonical_bytes(value: Any) -> bytes:
    try:
        return json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False).encode(
            "utf-8"
        )
    except (ValueError, TypeError) as exc:
        raise ContextValidationError(
            "context_not_canonical", "context contains non-finite values"
        ) from exc


def sha256_json(value: Any) -> str:
    return hashlib.sha256(canonical_bytes(value)).hexdigest()


def _pointer_get(value: Any, pointer: str) -> tuple[bool, Any]:
    if pointer in {"", "/"}:
        return True, value
    current = value
    for raw_segment in pointer.lstrip("/").split("/"):
        segment = raw_segment.replace("~1", "/").replace("~0", "~")
        if isinstance(current, dict) and segment in current:
            current = current[segment]
        elif isinstance(current, list) and segment.startswith("@"):
            current = next(
                (
                    item
                    for item in current
                    if isinstance(item, dict) and item.get("name") == segment[1:]
                ),
                None,
            )
            if current is None:
                return False, None
        elif isinstance(current, list) and segment.isdigit() and int(segment) < len(current):
            current = current[int(segment)]
        else:
            return False, None
    return True, current


def _factor_diff(left: Any, right: Any, path: str = "") -> list[dict[str, Any]]:
    if isinstance(left, dict) and isinstance(right, dict):
        rows: list[dict[str, Any]] = []
        for key in sorted(set(left) | set(right)):
            child_path = f"{path}/{key}"
            if key not in left:
                rows.append(
                    {
                        "path": child_path,
                        "kind": "added",
                        "left": None,
                        "right": right[key],
                        "differs": True,
                    }
                )
            elif key not in right:
                rows.append(
                    {
                        "path": child_path,
                        "kind": "removed",
                        "left": left[key],
                        "right": None,
                        "differs": True,
                    }
                )
            else:
                rows.extend(_factor_diff(left[key], right[key], child_path))
        return rows
    if isinstance(left, list) and isinstance(right, list):
        keyed = all(
            isinstance(item, dict) and isinstance(item.get("name"), str) for item in left + right
        )
        left_names = [item["name"] for item in left]
        right_names = [item["name"] for item in right]
        if (
            keyed
            and len(set(left_names)) == len(left_names)
            and len(set(right_names)) == len(right_names)
        ):
            left_by_name = {item["name"]: item for item in left}
            right_by_name = {item["name"]: item for item in right}
            rows = []
            for name in sorted(set(left_by_name) | set(right_by_name)):
                child_path = f"{path}/@{name}"
                if name not in left_by_name:
                    rows.append(
                        {
                            "path": child_path,
                            "kind": "added",
                            "left": None,
                            "right": right_by_name[name],
                            "differs": True,
                        }
                    )
                elif name not in right_by_name:
                    rows.append(
                        {
                            "path": child_path,
                            "kind": "removed",
                            "left": left_by_name[name],
                            "right": None,
                            "differs": True,
                        }
                    )
                else:
                    rows.extend(_factor_diff(left_by_name[name], right_by_name[name], child_path))
            return rows
        differs = canonical_bytes(left) != canonical_bytes(right)
        return [
            {
                "path": path or "/",
                "kind": "changed" if differs else "equal",
                "left": left,
                "right": right,
                "differs": differs,
            }
        ]
    differs = canonical_bytes(left) != canonical_bytes(right)
    return [
        {
            "path": path or "/",
            "kind": "changed" if differs else "equal",
            "left": left,
            "right": right,
            "differs": differs,
        }
    ]


def _sample_points(
    points: list[dict[str, Any]], limit: int
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    if len(points) <= limit:
        return points, {
            "sampled": False,
            "original_count": len(points),
            "sample_count": len(points),
        }
    if limit < 2:
        selected = points[:limit]
    else:
        indices = [round(index * (len(points) - 1) / (limit - 1)) for index in range(limit)]
        selected = [points[index] for index in indices]
    return selected, {
        "sampled": True,
        "original_count": len(points),
        "sample_count": len(selected),
        "method": "even_ordinal_with_endpoints",
    }


def _revision_experiment_snapshot(
    experiment: Experiment, revision: ExperimentRevision
) -> dict[str, Any]:
    snapshot = revision.snapshot_json.get("experiment")
    if not isinstance(snapshot, dict):
        raise ContextValidationError(
            "invalid_revision_snapshot", "revision has no experiment snapshot"
        )
    expected = {
        "title": experiment.title,
        "status": experiment.status,
        "objective": experiment.objective,
        "template_id": str(experiment.template_id),
        "template_version": experiment.template_version,
        "structured_data": experiment.structured_data,
        "note_document": experiment.note_document,
    }
    if canonical_bytes(snapshot) != canonical_bytes(expected):
        raise ContextValidationError(
            "experiment_changed_since_revision",
            f"experiment {experiment.code} changed since revision {revision.revision_number}",
        )
    return copy.deepcopy(snapshot)


def build_scientific_context(
    db: Session, project_id: uuid.UUID, payload: AnalysisRunCreate, settings: Settings
) -> tuple[dict[str, Any], str, int]:
    project = db.get(Project, project_id)
    if project is None:
        raise ContextValidationError("project_not_found", "project not found")
    experiment_ids = [item.experiment_id for item in payload.experiment_selections]
    experiments = db.scalars(
        select(Experiment)
        .where(Experiment.project_id == project_id, Experiment.id.in_(experiment_ids))
        .options(selectinload(Experiment.template), selectinload(Experiment.revisions))
    ).all()
    if len(experiments) != len(experiment_ids):
        raise ContextValidationError(
            "experiment_selection_invalid", "all experiments must belong to project"
        )
    by_id = {item.id: item for item in experiments}
    revision_rows: list[dict[str, Any]] = []
    revision_keys: set[tuple[uuid.UUID, int]] = set()
    for selection in payload.experiment_selections:
        experiment = by_id[selection.experiment_id]
        revision = next(
            (
                item
                for item in experiment.revisions
                if item.revision_number == selection.revision_number
            ),
            None,
        )
        if revision is None:
            raise ContextValidationError(
                "revision_not_found", f"revision {selection.revision_number} not found"
            )
        experiment_snapshot = _revision_experiment_snapshot(experiment, revision)
        revision_keys.add((experiment.id, revision.revision_number))
        revision_rows.append(
            {
                "id": str(revision.id),
                "experiment_id": str(experiment.id),
                "experiment_code": experiment.code,
                "revision_number": revision.revision_number,
                "snapshot_json": copy.deepcopy(revision.snapshot_json),
                "experiment_snapshot": experiment_snapshot,
                "template_schema": copy.deepcopy(experiment.template.json_schema),
                "template_schema_sha256": sha256_json(experiment.template.json_schema),
            }
        )

    measurement_rows = db.scalars(
        select(Measurement)
        .where(Measurement.id.in_(payload.measurement_ids))
        .options(selectinload(Measurement.import_record), selectinload(Measurement.points))
    ).all()
    if len(measurement_rows) != len(payload.measurement_ids):
        raise ContextValidationError("measurement_not_found", "selected measurement not found")
    measurements_by_id = {item.id: item for item in measurement_rows}
    selected_measurements: list[dict[str, Any]] = []
    measurement_ids = {item.id for item in measurement_rows}
    for measurement_id in payload.measurement_ids:
        measurement = measurements_by_id[measurement_id]
        if measurement.experiment_id not in by_id:
            raise ContextValidationError(
                "measurement_project_mismatch", "measurement is outside selected experiments"
            )
        selected_revision = next(
            row for row in revision_rows if row["experiment_id"] == str(measurement.experiment_id)
        )
        revision_measurement_ids = {
            str(item.get("id"))
            for item in selected_revision["snapshot_json"].get("measurements", [])
        }
        if str(measurement.id) not in revision_measurement_ids:
            raise ContextValidationError(
                "measurement_not_in_revision", "measurement is not in selected revision"
            )
        points = [
            {
                "ordinal": point.ordinal,
                "source_row_number": point.source_row_number,
                "x_value": point.x_value,
                "y_value": point.y_value,
            }
            for point in measurement.points
        ]
        if any(
            not math.isfinite(value)
            for point in points
            for value in (point["x_value"], point["y_value"])
        ):
            raise ContextValidationError(
                "measurement_non_finite", "measurement contains non-finite values"
            )
        sampled, sampling = _sample_points(points, settings.ai_max_measurement_points)
        selected_measurements.append(
            {
                "id": str(measurement.id),
                "experiment_id": str(measurement.experiment_id),
                "name": measurement.name,
                "measurement_type": measurement.measurement_type,
                "schema_key": measurement.schema_key,
                "schema_version": measurement.schema_version,
                "x_label": measurement.x_label,
                "x_unit": measurement.x_unit,
                "y_label": measurement.y_label,
                "y_unit": measurement.y_unit,
                "row_count": measurement.row_count,
                "summary_json": copy.deepcopy(measurement.summary_json),
                "points_sha256": measurement.points_sha256,
                "points": sampled,
                "sampling": sampling,
                "import": {
                    "id": str(measurement.import_id),
                    "source_attachment_id": str(measurement.import_record.source_attachment_id),
                    "source_sha256": measurement.import_record.source_sha256,
                    "parser_key": measurement.import_record.parser_key,
                    "parser_version": measurement.import_record.parser_version,
                },
            }
        )
    total_points = sum(len(item["points"]) for item in selected_measurements)
    if total_points > settings.ai_max_total_points:
        raise ContextValidationError("analysis_context_too_large", "too many measurement points")

    literature_rows = db.scalars(
        select(LiteratureRecord).where(
            LiteratureRecord.project_id == project_id,
            LiteratureRecord.id.in_(payload.literature_ids),
        )
    ).all()
    if len(literature_rows) != len(payload.literature_ids):
        raise ContextValidationError(
            "literature_selection_invalid", "literature is outside selected project"
        )
    literature_by_id = {item.id: item for item in literature_rows}
    selected_literature = [
        {
            "id": str(item.id),
            "title": item.title,
            "authors": copy.deepcopy(item.authors_json),
            "publication_year": item.publication_year,
            "container_title": item.container_title,
            "doi": item.doi,
            "url": item.url,
            "abstract": item.abstract,
        }
        for literature_id in payload.literature_ids
        for item in [literature_by_id[literature_id]]
    ]

    evidence_rows = db.scalars(
        select(EvidenceRecord).where(
            EvidenceRecord.project_id == project_id, EvidenceRecord.id.in_(payload.evidence_ids)
        )
    ).all()
    if len(evidence_rows) != len(payload.evidence_ids):
        raise ContextValidationError(
            "evidence_selection_invalid", "evidence is outside selected project"
        )
    selected_literature_ids = {item.id for item in literature_rows}
    selected_evidence: list[dict[str, Any]] = []
    evidence_by_id = {item.id: item for item in evidence_rows}
    for evidence_id in payload.evidence_ids:
        evidence = evidence_by_id[evidence_id]
        if evidence.status != "active":
            raise ContextValidationError(
                "evidence_withdrawn", "withdrawn EvidenceRecord cannot be selected"
            )
        source_ok = (
            evidence.measurement_id in measurement_ids
            or evidence.literature_id in selected_literature_ids
            or evidence.experiment_revision_id in {uuid.UUID(row["id"]) for row in revision_rows}
        )
        if not source_ok:
            raise ContextValidationError(
                "evidence_source_unselected", "Evidence source is not in frozen context"
            )
        selected_evidence.append(
            {
                "id": str(evidence.id),
                "claim_text": evidence.claim_text,
                "stance": evidence.stance,
                "source_type": evidence.source_type,
                "literature_id": str(evidence.literature_id) if evidence.literature_id else None,
                "measurement_id": str(evidence.measurement_id) if evidence.measurement_id else None,
                "experiment_revision_id": str(evidence.experiment_revision_id)
                if evidence.experiment_revision_id
                else None,
                "source_snapshot_json": copy.deepcopy(evidence.source_snapshot_json),
            }
        )

    compare = build_compare(
        db,
        CompareRequest(
            project_id=project_id,
            experiment_ids=experiment_ids,
            measurement_ids=payload.measurement_ids,
        ),
    )
    factor_differences: list[dict[str, Any]] = []
    for index, left_selection in enumerate(payload.experiment_selections):
        left_snapshot = revision_rows[index]["experiment_snapshot"]["structured_data"]
        for right_index in range(index + 1, len(payload.experiment_selections)):
            right_selection = payload.experiment_selections[right_index]
            right_snapshot = revision_rows[right_index]["experiment_snapshot"]["structured_data"]
            for difference in _factor_diff(left_snapshot, right_snapshot):
                factor_differences.append(
                    {
                        "left_experiment_id": str(left_selection.experiment_id),
                        "left_revision_number": left_selection.revision_number,
                        "right_experiment_id": str(right_selection.experiment_id),
                        "right_revision_number": right_selection.revision_number,
                        **difference,
                    }
                )
    context = {
        "schema_version": 1,
        "project": {"id": str(project.id), "code": project.code, "title": project.title},
        "selection": {
            "experiments": [
                {"experiment_id": str(item.experiment_id), "revision_number": item.revision_number}
                for item in payload.experiment_selections
            ],
            "measurement_ids": [str(item) for item in payload.measurement_ids],
            "literature_ids": [str(item) for item in payload.literature_ids],
            "evidence_ids": [str(item) for item in payload.evidence_ids],
        },
        "experiments": revision_rows,
        "measurements": selected_measurements,
        "literature": selected_literature,
        "evidence": selected_evidence,
        "compare": compare.model_dump(mode="json"),
        "factor_differences": factor_differences,
        "limits": {
            "max_context_bytes": settings.ai_max_context_bytes,
            "max_measurement_points": settings.ai_max_measurement_points,
            "max_total_points": settings.ai_max_total_points,
            "sampling_policy": "even_ordinal_with_endpoints",
        },
    }
    encoded = canonical_bytes(context)
    if len(encoded) > settings.ai_max_context_bytes:
        raise ContextValidationError(
            "analysis_context_too_large", "canonical context exceeds byte limit"
        )
    return context, hashlib.sha256(encoded).hexdigest(), len(encoded)
