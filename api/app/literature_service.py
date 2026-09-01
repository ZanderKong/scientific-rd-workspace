from __future__ import annotations

import copy
import uuid
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.models import (
    EvidenceRecord,
    Experiment,
    ExperimentLiteratureLink,
    ExperimentRevision,
    LiteratureRecord,
    Measurement,
)
from app.schemas import (
    EvidenceCreate,
    EvidenceSourceLiterature,
    EvidenceSourceMeasurement,
    EvidenceSourceRevision,
    LiteratureCreate,
    LiteratureLinkCreate,
    LiteratureLinkUpdate,
    LiteratureUpdate,
)


def literature_out_values(item: LiteratureRecord) -> dict[str, Any]:
    return {
        "id": item.id,
        "project_id": item.project_id,
        "item_type": item.item_type,
        "title": item.title,
        "authors": item.authors_json,
        "publication_year": item.publication_year,
        "container_title": item.container_title,
        "doi": item.doi,
        "url": item.url,
        "abstract": item.abstract,
        "provider": item.provider,
        "external_id": item.external_id,
        "provider_version": item.provider_version,
        "created_at": item.created_at,
        "updated_at": item.updated_at,
    }


def create_literature(
    db: Session, project_id: uuid.UUID, payload: LiteratureCreate
) -> LiteratureRecord:
    item = LiteratureRecord(
        project_id=project_id,
        item_type=payload.item_type,
        title=payload.title.strip(),
        authors_json=[author.model_dump(exclude_none=True) for author in payload.authors],
        publication_year=payload.publication_year,
        container_title=payload.container_title,
        doi=payload.doi.strip() if payload.doi else None,
        url=payload.url,
        abstract=payload.abstract,
    )
    db.add(item)
    db.commit()
    db.refresh(item)
    return item


def update_literature(
    db: Session, item: LiteratureRecord, payload: LiteratureUpdate
) -> LiteratureRecord:
    values = payload.model_dump(exclude_unset=True)
    if "authors" in values:
        values["authors_json"] = [
            author.model_dump(exclude_none=True) for author in payload.authors or []
        ]
        del values["authors"]
    if "title" in values and values["title"] is not None:
        values["title"] = values["title"].strip()
    if "doi" in values and values["doi"]:
        values["doi"] = values["doi"].strip()
    for key, value in values.items():
        setattr(item, key, value)
    db.commit()
    db.refresh(item)
    return item


def create_link(
    db: Session, experiment: Experiment, payload: LiteratureLinkCreate
) -> ExperimentLiteratureLink:
    literature = db.get(LiteratureRecord, payload.literature_id)
    if literature is None:
        raise LookupError("literature record not found")
    if literature.project_id != experiment.project_id:
        raise ValueError("literature record belongs to another project")
    if db.scalar(
        select(ExperimentLiteratureLink.id).where(
            ExperimentLiteratureLink.experiment_id == experiment.id,
            ExperimentLiteratureLink.literature_id == literature.id,
        )
    ):
        raise ValueError("literature record is already linked")
    link = ExperimentLiteratureLink(
        experiment_id=experiment.id,
        literature_id=literature.id,
        relationship_type=payload.relationship_type,
        notes=payload.notes,
    )
    db.add(link)
    db.commit()
    db.refresh(link)
    return link


def update_link(
    db: Session, link: ExperimentLiteratureLink, payload: LiteratureLinkUpdate
) -> ExperimentLiteratureLink:
    for key, value in payload.model_dump(exclude_unset=True).items():
        setattr(link, key, value)
    db.commit()
    db.refresh(link)
    return link


def _literature_snapshot(item: LiteratureRecord) -> dict[str, Any]:
    return {
        "id": str(item.id),
        "project_id": str(item.project_id),
        "title": item.title,
        "authors": copy.deepcopy(item.authors_json),
        "publication_year": item.publication_year,
        "container_title": item.container_title,
        "doi": item.doi,
        "url": item.url,
    }


def _measurement_snapshot(measurement: Measurement) -> dict[str, Any]:
    return {
        "id": str(measurement.id),
        "experiment_id": str(measurement.experiment_id),
        "name": measurement.name,
        "measurement_type": measurement.measurement_type,
        "x_label": measurement.x_label,
        "x_unit": measurement.x_unit,
        "y_label": measurement.y_label,
        "y_unit": measurement.y_unit,
        "row_count": measurement.row_count,
        "summary_json": copy.deepcopy(measurement.summary_json),
        "points_sha256": measurement.points_sha256,
        "import_id": str(measurement.import_id),
        "source_attachment_id": str(measurement.import_record.source_attachment_id),
        "source_sha256": measurement.import_record.source_sha256,
    }


def _revision_snapshot(revision: ExperimentRevision) -> dict[str, Any]:
    experiment = revision.experiment
    payload = revision.snapshot_json.get("experiment", {})
    return {
        "experiment_id": str(experiment.id),
        "experiment_code": experiment.code,
        "revision_id": str(revision.id),
        "revision_number": revision.revision_number,
        "template_id": payload.get("template_id", str(experiment.template_id)),
        "template_version": payload.get("template_version", experiment.template_version),
        "created_at": revision.created_at.isoformat() if revision.created_at else None,
    }


def create_evidence(db: Session, project_id: uuid.UUID, payload: EvidenceCreate) -> EvidenceRecord:
    source = payload.source
    literature_id = measurement_id = revision_id = None
    if isinstance(source, EvidenceSourceLiterature):
        literature = db.get(LiteratureRecord, source.literature_id)
        if literature is None:
            raise LookupError("literature record not found")
        if literature.project_id != project_id:
            raise ValueError("literature record belongs to another project")
        literature_id = literature.id
        snapshot = _literature_snapshot(literature)
        locator = source.locator
        source_type = "literature"
    elif isinstance(source, EvidenceSourceMeasurement):
        measurement = db.scalar(
            select(Measurement)
            .where(Measurement.id == source.measurement_id)
            .options(selectinload(Measurement.import_record), selectinload(Measurement.experiment))
        )
        if measurement is None:
            raise LookupError("measurement not found")
        if measurement.experiment.project_id != project_id:
            raise ValueError("measurement belongs to another project")
        measurement_id = measurement.id
        snapshot = _measurement_snapshot(measurement)
        locator = source.locator
        source_type = "measurement"
    elif isinstance(source, EvidenceSourceRevision):
        revision = db.scalar(
            select(ExperimentRevision)
            .join(Experiment)
            .where(
                ExperimentRevision.experiment_id == source.experiment_id,
                ExperimentRevision.revision_number == source.revision_number,
            )
            .options(selectinload(ExperimentRevision.experiment))
        )
        if revision is None:
            raise LookupError("experiment revision not found")
        if revision.experiment.project_id != project_id:
            raise ValueError("experiment revision belongs to another project")
        revision_id = revision.id
        snapshot = _revision_snapshot(revision)
        locator = source.locator
        source_type = "experiment_revision"
    else:
        raise ValueError("unsupported evidence source")
    if payload.context_experiment_id:
        context = db.get(Experiment, payload.context_experiment_id)
        if context is None:
            raise LookupError("context experiment not found")
        if context.project_id != project_id:
            raise ValueError("context experiment belongs to another project")
    item = EvidenceRecord(
        project_id=project_id,
        context_experiment_id=payload.context_experiment_id,
        claim_text=payload.claim_text.strip(),
        stance=payload.stance,
        source_type=source_type,
        literature_id=literature_id,
        measurement_id=measurement_id,
        experiment_revision_id=revision_id,
        locator=locator,
        notes=payload.notes,
        source_snapshot_json=snapshot,
        status="active",
    )
    db.add(item)
    db.commit()
    db.refresh(item)
    return item


def withdraw_evidence(db: Session, item: EvidenceRecord, reason: str) -> EvidenceRecord:
    if item.status == "withdrawn":
        raise ValueError("evidence is already withdrawn")
    item.status = "withdrawn"
    item.withdrawal_reason = reason.strip()
    item.withdrawn_at = datetime.now(UTC)
    db.commit()
    db.refresh(item)
    return item
