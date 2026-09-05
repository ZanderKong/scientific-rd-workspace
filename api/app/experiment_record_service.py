from __future__ import annotations

import uuid
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import ObjectRelation, ResearchObject
from app.relation_semantics import validate_relation_scope
from app.schemas import ExperimentRecordCreate, ExperimentRecordPut, ObjectCreate
from app.services import (
    _create_object_in_session,
    _create_revision_in_session,
    _update_object_in_session,
    get_object,
    object_out,
    sha256_json,
)

ALLOWED_REFERENCE_KINDS = {"research_object", "data", "process_definition", "view", "claim"}


def _experiment(db: Session, experiment_id: uuid.UUID) -> ResearchObject:
    item = get_object(db, experiment_id)
    if item is None or item.kind != "experiment":
        raise LookupError("experiment not found")
    return item


def _reference_rows(db: Session, experiment_id: uuid.UUID) -> list[ObjectRelation]:
    return list(
        db.scalars(
            select(ObjectRelation)
            .where(
                ObjectRelation.source_object_id == experiment_id,
                ObjectRelation.relation_type == "references",
            )
            .order_by(ObjectRelation.created_at, ObjectRelation.id)
        ).all()
    )


def _record_body(db: Session, experiment: ResearchObject) -> dict[str, Any]:
    grouped: dict[str, list[dict[str, Any]]] = {}
    for relation in _reference_rows(db, experiment.id):
        target = get_object(db, relation.target_object_id)
        if target is None:
            continue
        grouped.setdefault(target.kind, []).append(
            {
                "relation_id": relation.id,
                "role": relation.role,
                "note": (relation.properties_jsonb or {}).get("note"),
                "order_index": (relation.properties_jsonb or {}).get("order_index", 0),
                "object": object_out(target),
            }
        )
    return {"experiment": object_out(experiment), "references": grouped}


def get_experiment_record(db: Session, experiment_id: uuid.UUID) -> dict[str, Any]:
    experiment = _experiment(db, experiment_id)
    body = _record_body(db, experiment)
    return {"record_sha256": sha256_json(body), **body}


def _replace_refs(db: Session, experiment: ResearchObject, refs: list[Any]) -> None:
    db.query(ObjectRelation).filter(
        ObjectRelation.source_object_id == experiment.id,
        ObjectRelation.relation_type == "references",
    ).delete(synchronize_session=False)
    for item in refs:
        target = get_object(db, item.target_id)
        if target is None:
            raise LookupError("experiment reference target not found")
        if target.kind not in ALLOWED_REFERENCE_KINDS:
            raise ValueError(f"Experiments cannot reference {target.kind}")
        if item.target_kind is not None and target.kind != item.target_kind:
            raise ValueError("reference target_kind does not match target")
        validate_relation_scope(experiment, target)
        db.add(
            ObjectRelation(
                source_object_id=experiment.id,
                target_object_id=target.id,
                relation_type="references",
                role=item.role.strip() if item.role else None,
                properties_jsonb={"note": item.note, "order_index": item.order_index},
            )
        )
    db.flush()


def create_experiment_record(db: Session, payload: ExperimentRecordCreate) -> dict[str, Any]:
    try:
        experiment = _create_object_in_session(
            db,
            ObjectCreate(
                kind="experiment",
                code=payload.experiment.code,
                title=payload.experiment.title,
                status=payload.experiment.status,
                project_scope_id=payload.project_scope_id,
                tags=payload.experiment.tags,
                properties_jsonb=payload.experiment.properties_jsonb,
                content_document=payload.experiment.content_document,
            ),
        )
        _replace_refs(db, experiment, payload.references)
        _create_revision_in_session(db, experiment.id, payload.change_note)
        db.commit()
        return get_experiment_record(db, experiment.id)
    except Exception:
        db.rollback()
        raise


def update_experiment_record(
    db: Session, experiment_id: uuid.UUID, payload: ExperimentRecordPut
) -> dict[str, Any]:
    try:
        experiment = _experiment(db, experiment_id)
        changes = {
            key: value
            for key, value in payload.experiment.items()
            if key in {"title", "status", "tags", "properties_jsonb", "content_document"}
        }
        if changes:
            _update_object_in_session(db, experiment, changes)
        _replace_refs(db, experiment, payload.references)
        _create_revision_in_session(db, experiment.id, payload.change_note)
        db.commit()
        return get_experiment_record(db, experiment.id)
    except Exception:
        db.rollback()
        raise
