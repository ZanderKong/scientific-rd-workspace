from __future__ import annotations

import hashlib
import uuid
from io import BytesIO
from typing import Any

from sqlalchemy import select

from app.core.config import get_settings
from app.db import SessionLocal
from app.models import (
    Attachment,
    EvidenceRecord,
    Experiment,
    ExperimentLiteratureLink,
    ExperimentRevision,
    ExperimentTemplate,
    LiteratureRecord,
    Measurement,
    MeasurementImport,
    MeasurementPoint,
    Project,
)
from app.services import _snapshot, attachment_storage_key
from app.storage import LocalStorageAdapter


def block(block_type: str, content: str, *, level: int | None = None) -> dict[str, Any]:
    props: dict[str, Any] = {
        "textColor": "default",
        "backgroundColor": "default",
        "textAlignment": "left",
    }
    if level is not None:
        props["level"] = level
    return {
        "id": str(uuid.uuid4()),
        "type": block_type,
        "props": props,
        "content": [{"type": "text", "text": content, "styles": {}}],
        "children": [],
    }


def default_note(title: str) -> list[dict[str, Any]]:
    return [
        block("heading", "Objective", level=2),
        block("paragraph", f"Document the objective for {title}."),
        block("heading", "Procedure", level=2),
        block("paragraph", "Record the formulation and processing steps here."),
        block("heading", "Observation", level=2),
        block("paragraph", "Capture observable outcomes and anomalies."),
        block("heading", "Discussion", level=2),
        block("paragraph", "Add interpretation and the next decision."),
    ]


TEMPLATE_SCHEMA: dict[str, Any] = {
    "type": "object",
    "additionalProperties": False,
    "properties": {
        "primary_material": {"type": "string", "title": "Primary material"},
        "primary_material_concentration": {
            "type": "object",
            "title": "Material concentration",
            "additionalProperties": False,
            "properties": {
                "value": {"type": "number"},
                "unit": {"type": "string", "enum": ["wt%", "g/L", "mol/L"]},
            },
            "required": ["value", "unit"],
        },
        "solvent": {"type": "string", "title": "Solvent"},
        "additives": {
            "type": "array",
            "items": {
                "type": "object",
                "additionalProperties": False,
                "properties": {
                    "name": {"type": "string"},
                    "amount": {"type": "number"},
                    "unit": {"type": "string"},
                },
                "required": ["name"],
            },
        },
        "drying_temperature": {
            "type": "object",
            "additionalProperties": False,
            "properties": {
                "value": {"type": "number"},
                "unit": {"type": "string", "enum": ["°C", "K"]},
            },
            "required": ["value", "unit"],
        },
        "drying_time": {
            "type": "object",
            "additionalProperties": False,
            "properties": {
                "value": {"type": "number"},
                "unit": {"type": "string", "enum": ["min", "h"]},
            },
            "required": ["value", "unit"],
        },
        "substrate": {"type": "string"},
    },
}


def ensure_revision(db, experiment: Experiment, note: str) -> None:
    if db.scalar(
        select(ExperimentRevision.id).where(ExperimentRevision.experiment_id == experiment.id)
    ):
        return
    db.add(
        ExperimentRevision(
            experiment_id=experiment.id,
            revision_number=1,
            snapshot_json=_snapshot(experiment),
            change_note=note,
        )
    )


def ensure_measurement(db, experiment: Experiment, name: str, values: list[float]) -> Measurement:
    existing = db.scalar(
        select(Measurement).where(
            Measurement.experiment_id == experiment.id, Measurement.name == name
        )
    )
    if existing is not None:
        return existing
    rows = [
        ["wavelength_nm", "response_au"],
        *[[440 + index * 10, value] for index, value in enumerate(values)],
    ]
    payload = "\n".join(",".join(str(value) for value in row) for row in rows) + "\n"
    attachment_id = uuid.uuid5(uuid.NAMESPACE_URL, f"phase2:{experiment.id}:{name}")
    filename = f"{experiment.code.lower()}-{name.lower().replace(' ', '-')}.csv"
    key = attachment_storage_key(experiment.id, attachment_id, filename)
    adapter = LocalStorageAdapter(get_settings().storage_root)
    size, digest = adapter.put(key, BytesIO(payload.encode()))
    attachment = Attachment(
        id=attachment_id,
        experiment_id=experiment.id,
        original_filename=filename,
        storage_key=key,
        content_type="text/csv",
        size_bytes=size,
        sha256=digest,
    )
    db.add(attachment)
    import_id = uuid.uuid5(uuid.NAMESPACE_URL, f"phase2-import:{experiment.id}:{name}")
    source_rows = rows[1:]
    import_record = MeasurementImport(
        id=import_id,
        experiment_id=experiment.id,
        source_attachment_id=attachment.id,
        status="completed",
        source_format="csv",
        parser_key="tabular-xy",
        parser_version=1,
        source_sha256=digest,
        header_json=rows[0],
        source_metadata_json={
            "available_sheets": [],
            "row_count": len(source_rows),
            "column_count": 2,
            "preview_rows": source_rows[:20],
        },
        mapping_json={
            "measurement_name": name,
            "measurement_type": "spectral_response",
            "default_chart_type": "line",
            "x": {"column": "wavelength_nm", "label": "Wavelength", "unit": "nm"},
            "y": {"column": "response_au", "label": "Response", "unit": "AU"},
            "ignored_columns": [],
        },
        warnings_json=[],
        errors_json=[],
        row_count=len(source_rows),
    )
    db.add(import_record)
    points = [(index, int(row[0]), float(row[1])) for index, row in enumerate(source_rows)]
    xs, ys = [item[1] for item in points], [item[2] for item in points]
    canonical = "\n".join(
        f"{index},{row},{x:.17g},{y:.17g}" for index, (row, x, y) in enumerate(points)
    )
    measurement = Measurement(
        id=uuid.uuid5(uuid.NAMESPACE_URL, f"phase2-measurement:{experiment.id}:{name}"),
        experiment_id=experiment.id,
        import_id=import_record.id,
        name=name,
        measurement_type="spectral_response",
        schema_key="xy-series",
        schema_version=1,
        default_chart_type="line",
        x_label="Wavelength",
        x_unit="nm",
        y_label="Response",
        y_unit="AU",
        row_count=len(points),
        summary_json={
            "x_min": min(xs),
            "x_max": max(xs),
            "y_min": min(ys),
            "y_max": max(ys),
            "y_mean": sum(ys) / len(ys),
        },
        points_sha256=hashlib.sha256(canonical.encode()).hexdigest(),
    )
    db.add(measurement)
    db.flush()
    db.add_all(
        [
            MeasurementPoint(
                measurement_id=measurement.id,
                ordinal=index,
                source_row_number=row + 2,
                x_value=x,
                y_value=y,
            )
            for index, (row, x, y) in enumerate(points)
        ]
    )
    import_record.completed_at = experiment.created_at
    return measurement


def seed() -> None:
    with SessionLocal() as db:
        project = db.scalar(select(Project).where(Project.code == "PRJ-001"))
        if project is None:
            project = Project(
                code="PRJ-001",
                title="Colorimetric Sensor Formulation Optimisation",
                description="Synthetic/anonymised demo project for formulation iteration.",
                status="active",
            )
            db.add(project)
            db.flush()

        template = db.scalar(
            select(ExperimentTemplate).where(
                ExperimentTemplate.key == "materials-formulation-v1",
                ExperimentTemplate.version == 1,
            )
        )
        if template is None:
            template = ExperimentTemplate(
                key="materials-formulation-v1",
                name="Materials formulation",
                version=1,
                json_schema=TEMPLATE_SCHEMA,
                ui_schema=None,
                is_active=True,
            )
            db.add(template)
            db.flush()

        records = [
            (
                "EXP-041",
                "Baseline formulation",
                None,
                {
                    "primary_material": "Material A",
                    "primary_material_concentration": {"value": 5, "unit": "wt%"},
                    "solvent": "ethanol",
                    "additives": [],
                    "drying_temperature": {"value": 60, "unit": "°C"},
                    "drying_time": {"value": 20, "unit": "min"},
                    "substrate": "polymer film",
                },
            ),
            (
                "EXP-044",
                "Baseline + KI",
                "EXP-041",
                {
                    "primary_material": "Material A",
                    "primary_material_concentration": {"value": 5, "unit": "wt%"},
                    "solvent": "ethanol",
                    "additives": [{"name": "KI", "amount": 1, "unit": "g"}],
                    "drying_temperature": {"value": 60, "unit": "°C"},
                    "drying_time": {"value": 20, "unit": "min"},
                    "substrate": "polymer film",
                },
            ),
            (
                "EXP-045",
                "2-POA + KI + starch",
                "EXP-044",
                {
                    "primary_material": "Material A",
                    "primary_material_concentration": {"value": 5, "unit": "wt%"},
                    "solvent": "ethanol",
                    "additives": [
                        {"name": "KI", "amount": 1, "unit": "g"},
                        {"name": "starch", "amount": 1, "unit": "wt%"},
                    ],
                    "drying_temperature": {"value": 60, "unit": "°C"},
                    "drying_time": {"value": 20, "unit": "min"},
                    "substrate": "polymer film",
                },
            ),
        ]
        by_code: dict[str, Experiment] = {}
        for code, title, parent_code, structured_data in records:
            experiment = db.scalar(select(Experiment).where(Experiment.code == code))
            if experiment is None:
                experiment = Experiment(
                    code=code,
                    project_id=project.id,
                    template_id=template.id,
                    template_version=template.version,
                    title=title,
                    status="completed",
                    objective="Compare formulation choices in a synthetic demo workflow.",
                    structured_data=structured_data,
                    note_document=default_note(title),
                )
                db.add(experiment)
                db.flush()
            by_code[code] = experiment
            if parent_code:
                experiment.parent_experiment_id = by_code[parent_code].id
        for index, code in enumerate(("EXP-041", "EXP-044", "EXP-045")):
            experiment = by_code[code]
            ensure_measurement(
                db,
                experiment,
                "Synthetic response",
                [1.0 + index * 0.2, 1.4 + index * 0.25, 1.9 + index * 0.3, 2.3 + index * 0.35],
            )
            ensure_revision(db, experiment, "Seeded demo snapshot")
        literature = db.scalar(
            select(LiteratureRecord).where(
                LiteratureRecord.project_id == project.id,
                LiteratureRecord.title == "Synthetic response methods",
            )
        )
        if literature is None:
            literature = LiteratureRecord(
                project_id=project.id,
                item_type="journal_article",
                title="Synthetic response methods",
                authors_json=[{"family": "Example", "given": "Ada"}],
                publication_year=2025,
                container_title="Demo Journal",
                doi="10.0000/demo",
            )
            db.add(literature)
            db.flush()
        for experiment in by_code.values():
            if not db.scalar(
                select(ExperimentLiteratureLink.id).where(
                    ExperimentLiteratureLink.experiment_id == experiment.id,
                    ExperimentLiteratureLink.literature_id == literature.id,
                )
            ):
                db.add(
                    ExperimentLiteratureLink(
                        experiment_id=experiment.id,
                        literature_id=literature.id,
                        relationship_type="supporting",
                    )
                )
        measurement = db.scalar(
            select(Measurement).where(
                Measurement.experiment_id == by_code["EXP-045"].id,
                Measurement.name == "Synthetic response",
            )
        )
        if measurement is not None and not db.scalar(
            select(EvidenceRecord.id).where(
                EvidenceRecord.project_id == project.id,
                EvidenceRecord.measurement_id == measurement.id,
            )
        ):
            db.add(
                EvidenceRecord(
                    project_id=project.id,
                    context_experiment_id=by_code["EXP-045"].id,
                    claim_text="The synthetic response increases across the compared formulations.",
                    stance="supports",
                    source_type="measurement",
                    measurement_id=measurement.id,
                    source_snapshot_json={
                        "id": str(measurement.id),
                        "name": measurement.name,
                        "points_sha256": measurement.points_sha256,
                        "summary_json": measurement.summary_json,
                        "import_id": str(measurement.import_id),
                    },
                    status="active",
                )
            )
        db.commit()
        print("Seeded PRJ-001, materials-formulation-v1, EXP-041, EXP-044, and EXP-045")


if __name__ == "__main__":
    seed()
