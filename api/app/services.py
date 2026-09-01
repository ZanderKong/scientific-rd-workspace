from __future__ import annotations

import copy
import re
import uuid
from collections.abc import Iterable
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.orm import Session, selectinload

from app.models import Attachment, Experiment, ExperimentRevision, ExperimentTemplate, Project
from app.schemas import CloneRequest, ExperimentCreate, ExperimentUpdate, ProjectCreate, ProjectUpdate
from app.storage import LocalStorageAdapter, sanitise_filename
from app.validation import validate_template_data


def _next_code(db: Session, model: type[Project] | type[Experiment], prefix: str) -> str:
    values = db.scalars(select(model.code).where(model.code.like(f"{prefix}-%"))).all()
    numbers = [int(match.group(1)) for value in values if (match := re.fullmatch(rf"{prefix}-(\d+)", value))]
    return f"{prefix}-{max(numbers, default=0) + 1:03d}"


def create_project(db: Session, payload: ProjectCreate) -> Project:
    project = Project(code=_next_code(db, Project, "PRJ"), **payload.model_dump())
    db.add(project)
    db.commit()
    db.refresh(project)
    return project


def update_project(db: Session, project: Project, payload: ProjectUpdate) -> Project:
    for key, value in payload.model_dump(exclude_unset=True).items():
        setattr(project, key, value)
    db.commit()
    db.refresh(project)
    return project


def get_template_or_raise(db: Session, template_id: uuid.UUID) -> ExperimentTemplate:
    template = db.get(ExperimentTemplate, template_id)
    if template is None:
        raise LookupError("experiment template not found")
    if not template.is_active:
        raise ValueError("experiment template is not active")
    return template


def create_experiment(db: Session, project: Project, payload: ExperimentCreate) -> Experiment:
    template = get_template_or_raise(db, payload.template_id)
    validate_template_data(template.json_schema, payload.structured_data)
    experiment = Experiment(
        code=_next_code(db, Experiment, "EXP"),
        project_id=project.id,
        template_id=template.id,
        template_version=template.version,
        **payload.model_dump(exclude={"template_id"}),
    )
    db.add(experiment)
    db.commit()
    db.refresh(experiment)
    return experiment


def update_experiment(db: Session, experiment: Experiment, payload: ExperimentUpdate) -> Experiment:
    values = payload.model_dump(exclude_unset=True)
    if "structured_data" in values:
        validate_template_data(experiment.template.json_schema, values["structured_data"])
    for key, value in values.items():
        setattr(experiment, key, value)
    db.commit()
    db.refresh(experiment)
    return experiment


def _snapshot(experiment: Experiment) -> dict[str, Any]:
    return {
        "experiment": {
            "title": experiment.title,
            "status": experiment.status,
            "objective": experiment.objective,
            "template_id": str(experiment.template_id),
            "template_version": experiment.template_version,
            "structured_data": copy.deepcopy(experiment.structured_data),
            "note_document": copy.deepcopy(experiment.note_document),
        },
        "attachments": [
            {
                "id": str(attachment.id),
                "original_filename": attachment.original_filename,
                "content_type": attachment.content_type,
                "size_bytes": attachment.size_bytes,
                "sha256": attachment.sha256,
            }
            for attachment in experiment.attachments
        ],
    }


def create_revision(db: Session, experiment_id: uuid.UUID, change_note: str | None) -> ExperimentRevision:
    locked = db.scalars(
        select(Experiment)
        .where(Experiment.id == experiment_id)
        .options(selectinload(Experiment.attachments))
        .with_for_update()
    ).first()
    if locked is None:
        raise LookupError("experiment not found")
    current = db.scalar(
        select(func.max(ExperimentRevision.revision_number)).where(
            ExperimentRevision.experiment_id == experiment_id
        )
    )
    revision = ExperimentRevision(
        experiment_id=experiment_id,
        revision_number=(current or 0) + 1,
        snapshot_json=_snapshot(locked),
        change_note=change_note,
    )
    db.add(revision)
    db.commit()
    db.refresh(revision)
    return revision


def clone_experiment(db: Session, source: Experiment, payload: CloneRequest) -> Experiment:
    validate_template_data(source.template.json_schema, source.structured_data)
    clone = Experiment(
        code=_next_code(db, Experiment, "EXP"),
        project_id=source.project_id,
        template_id=source.template_id,
        template_version=source.template_version,
        parent_experiment_id=source.id,
        title=payload.new_title,
        status="draft",
        objective=source.objective,
        structured_data=copy.deepcopy(source.structured_data) if payload.copy_structured_data else {},
        note_document=copy.deepcopy(source.note_document) if payload.copy_note else [],
    )
    db.add(clone)
    db.flush()
    revision = ExperimentRevision(
        experiment_id=clone.id,
        revision_number=1,
        snapshot_json=_snapshot(clone),
        change_note="Initial clone from " + source.code,
    )
    db.add(revision)
    db.commit()
    db.refresh(clone)
    return clone


def attachment_storage_key(experiment_id: uuid.UUID, attachment_id: uuid.UUID, filename: str) -> str:
    return f"{experiment_id}/{attachment_id}/{sanitise_filename(filename)}"

