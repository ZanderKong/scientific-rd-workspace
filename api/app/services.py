from __future__ import annotations

import copy
import hashlib
import json
import re
import uuid
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.orm import Session, selectinload

from app.models import (
    Experiment,
    ExperimentLiteratureLink,
    ExperimentProvenanceLink,
    ExperimentRevision,
    ExperimentTemplate,
    Finding,
    Measurement,
    Project,
    ReviewDecision,
)
from app.schemas import (
    CloneRequest,
    ExperimentCreate,
    ExperimentPrefillOut,
    ExperimentSuggestionOrigin,
    ExperimentUpdate,
    ProjectCreate,
    ProjectUpdate,
)
from app.storage import sanitise_filename
from app.validation import validate_template_data


def _next_code(db: Session, model: type[Project] | type[Experiment], prefix: str) -> str:
    values = db.scalars(select(model.code).where(model.code.like(f"{prefix}-%"))).all()
    numbers = [
        int(match.group(1))
        for value in values
        if (match := re.fullmatch(rf"{prefix}-(\d+)", value))
    ]
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


def canonical_json_hash(value: Any) -> str:
    encoded = json.dumps(
        value, sort_keys=True, separators=(",", ":"), ensure_ascii=True, allow_nan=False
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def _suggestion_prefill_or_raise(
    db: Session, finding_id: uuid.UUID, origin: ExperimentSuggestionOrigin | None = None
) -> tuple[Finding, ReviewDecision, dict[str, Any], Experiment]:
    finding = db.scalar(
        select(Finding).where(Finding.id == finding_id).options(selectinload(Finding.analysis_run))
    )
    if finding is None:
        raise LookupError("finding not found")
    latest = db.scalar(
        select(ReviewDecision)
        .where(ReviewDecision.finding_id == finding_id)
        .order_by(ReviewDecision.sequence_number.desc())
    )
    if latest is None or latest.decision not in {"accept", "needs_evidence"}:
        raise ValueError("suggestion_review_not_eligible")
    suggestion = finding.suggested_next_experiment_json
    if not suggestion or suggestion.get("validation_status") != "valid":
        raise ValueError("suggestion_invalid")
    prefill = suggestion.get("prefill")
    if not isinstance(prefill, dict):
        raise ValueError("suggestion_invalid")
    expected_hash = canonical_json_hash(prefill)
    if suggestion.get("suggestion_hash") != expected_hash:
        raise ValueError("suggestion_hash_mismatch")
    if origin is not None:
        try:
            origin_template_id = uuid.UUID(str(prefill["template_id"]))
            origin_parent_id = uuid.UUID(str(prefill["parent_experiment_id"]))
            origin_template_version = int(prefill["template_version"])
        except (KeyError, TypeError, ValueError) as exc:
            raise ValueError("suggestion_invalid") from exc
        if (
            origin.finding_id != finding.id
            or origin.analysis_run_id != finding.analysis_run_id
            or origin.enabling_review_decision_id != latest.id
            or origin.suggestion_hash != expected_hash
            or origin.template_id != origin_template_id
            or origin.template_version != origin_template_version
            or origin.parent_experiment_id != origin_parent_id
        ):
            raise ValueError("suggestion_review_changed")
    try:
        parent_id = uuid.UUID(str(prefill["parent_experiment_id"]))
        template_id = uuid.UUID(str(prefill["template_id"]))
        template_version = int(prefill["template_version"])
    except (KeyError, TypeError, ValueError) as exc:
        raise ValueError("suggestion_invalid") from exc
    parent = db.scalar(
        select(Experiment)
        .where(Experiment.id == parent_id)
        .options(selectinload(Experiment.template))
    )
    if parent is None or parent.project_id != finding.project_id:
        raise ValueError("suggestion_base_experiment_changed")
    if parent.template_id != template_id or parent.template_version != template_version:
        raise ValueError("suggestion_template_changed")
    template = db.get(ExperimentTemplate, template_id)
    if template is None or not template.is_active or template.version != template_version:
        raise ValueError("suggestion_template_changed")
    try:
        validate_template_data(template.json_schema, prefill["structured_data"])
    except ValueError as exc:
        raise ValueError("suggestion_invalid") from exc
    return finding, latest, prefill, parent


def suggested_experiment_prefill(db: Session, finding_id: uuid.UUID) -> ExperimentPrefillOut:
    finding, latest, prefill, _parent = _suggestion_prefill_or_raise(db, finding_id)
    return ExperimentPrefillOut(
        project_id=finding.project_id,
        finding_id=finding.id,
        analysis_run_id=finding.analysis_run_id,
        enabling_review_decision_id=latest.id,
        review_sequence_number=latest.sequence_number,
        review_decision=latest.decision,
        suggestion_hash=canonical_json_hash(prefill),
        template_id=uuid.UUID(str(prefill["template_id"])),
        template_version=int(prefill["template_version"]),
        parent_experiment_id=uuid.UUID(str(prefill["parent_experiment_id"])),
        title=prefill["title"],
        objective=prefill["objective"],
        structured_data=prefill["structured_data"],
        control_strategy=prefill["control_strategy"],
        addresses_missing_evidence_codes=prefill.get("addresses_missing_evidence_codes", []),
        change_operations=prefill.get("change_operations", []),
    )


def create_experiment(db: Session, project: Project, payload: ExperimentCreate) -> Experiment:
    template = get_template_or_raise(db, payload.template_id)
    validate_template_data(template.json_schema, payload.structured_data)
    origin = payload.suggestion_origin
    finding = review = prefill = parent = None
    if origin is not None:
        if payload.status != "draft":
            raise ValueError("suggested_experiment_must_be_draft")
        finding, review, prefill, parent = _suggestion_prefill_or_raise(
            db, origin.finding_id, origin
        )
        if finding.project_id != project.id or payload.template_id != template.id:
            raise ValueError("suggestion_project_or_template_changed")
    experiment = Experiment(
        code=_next_code(db, Experiment, "EXP"),
        project_id=project.id,
        template_id=template.id,
        template_version=template.version,
        parent_experiment_id=parent.id if parent is not None else None,
        **payload.model_dump(exclude={"template_id", "suggestion_origin"}),
    )
    db.add(experiment)
    if origin is not None and finding is not None and review is not None and prefill is not None:
        db.flush()
        db.add(
            ExperimentProvenanceLink(
                experiment_id=experiment.id,
                finding_id=finding.id,
                analysis_run_id=finding.analysis_run_id,
                enabling_review_decision_id=review.id,
                suggestion_snapshot_json=copy.deepcopy(finding.suggested_next_experiment_json),
                submitted_values_snapshot_json={
                    "title": payload.title,
                    "objective": payload.objective,
                    "template_id": str(payload.template_id),
                    "template_version": template.version,
                    "status": payload.status,
                    "structured_data": copy.deepcopy(payload.structured_data),
                    "note_document": copy.deepcopy(payload.note_document),
                },
            )
        )
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
    measurements = []
    for measurement in getattr(experiment, "measurements", []):
        import_record = measurement.import_record
        measurements.append(
            {
                "id": str(measurement.id),
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
                "import_id": str(measurement.import_id),
                "source_attachment_id": str(import_record.source_attachment_id),
                "source_sha256": import_record.source_sha256,
            }
        )
    literature_links = []
    for link in getattr(experiment, "literature_links", []):
        literature = link.literature
        literature_links.append(
            {
                "id": str(link.id),
                "literature_id": str(literature.id),
                "relationship_type": link.relationship_type,
                "title": literature.title,
                "authors": copy.deepcopy(literature.authors_json),
                "publication_year": literature.publication_year,
                "doi": literature.doi,
            }
        )
    evidence = []
    for item in getattr(experiment, "evidence_records", []):
        evidence.append(
            {
                "id": str(item.id),
                "claim_text": item.claim_text,
                "stance": item.stance,
                "source_type": item.source_type,
                "source_snapshot_json": copy.deepcopy(item.source_snapshot_json),
                "status": item.status,
            }
        )
    return {
        "snapshot_schema_version": 2,
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
        "measurements": measurements,
        "literature_links": literature_links,
        "evidence": evidence,
    }


def create_revision(
    db: Session, experiment_id: uuid.UUID, change_note: str | None
) -> ExperimentRevision:
    locked = db.scalars(
        select(Experiment)
        .where(Experiment.id == experiment_id)
        .options(
            selectinload(Experiment.attachments),
            selectinload(Experiment.measurements).selectinload(Measurement.import_record),
            selectinload(Experiment.literature_links).selectinload(
                ExperimentLiteratureLink.literature
            ),
            selectinload(Experiment.evidence_records),
        )
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
        structured_data=copy.deepcopy(source.structured_data)
        if payload.copy_structured_data
        else {},
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


def attachment_storage_key(
    experiment_id: uuid.UUID, attachment_id: uuid.UUID, filename: str
) -> str:
    return f"{experiment_id}/{attachment_id}/{sanitise_filename(filename)}"
