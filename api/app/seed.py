from __future__ import annotations

import uuid
from typing import Any

from sqlalchemy import select

from app.db import SessionLocal
from app.models import Experiment, ExperimentRevision, ExperimentTemplate, Project


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
            snapshot_json={
                "experiment": {
                    "title": experiment.title,
                    "status": experiment.status,
                    "objective": experiment.objective,
                    "template_id": str(experiment.template_id),
                    "template_version": experiment.template_version,
                    "structured_data": experiment.structured_data,
                    "note_document": experiment.note_document,
                },
                "attachments": [],
            },
            change_note=note,
        )
    )


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
            ensure_revision(db, experiment, "Seeded demo snapshot")
        db.commit()
        print("Seeded PRJ-001, materials-formulation-v1, EXP-041, EXP-044, and EXP-045")


if __name__ == "__main__":
    seed()
