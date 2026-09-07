from __future__ import annotations

import uuid
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import ObjectRelation, ResearchObject
from app.relation_semantics import SemanticConflict, lock_project_graph, validate_relation_scope
from app.schemas import (
    ExperimentMetadataPatch,
    ExperimentRecordCreate,
    ExperimentRecordPut,
    ExperimentReferenceCreate,
    ExperimentReferenceOrder,
    ObjectCreate,
)
from app.services import (
    _create_object_in_session,
    _create_revision_in_session,
    _update_object_in_session,
    get_object,
    object_out,
    sha256_json,
)

ALLOWED_REFERENCE_KINDS = {"research_object", "data", "process_definition", "view", "claim"}


def _experiment(db: Session, experiment_id: uuid.UUID, *, lock: bool = False) -> ResearchObject:
    statement = select(ResearchObject).where(ResearchObject.id == experiment_id)
    if lock:
        statement = statement.with_for_update()
    item = db.scalar(statement) if lock else get_object(db, experiment_id)
    if item is None or item.kind != "experiment":
        raise LookupError("experiment not found")
    return item


def _locked_experiment(db: Session, experiment_id: uuid.UUID) -> ResearchObject:
    item = _experiment(db, experiment_id)
    lock_project_graph(db, item.project_scope_id)
    return _experiment(db, experiment_id, lock=True)


def _reference_rows(db: Session, experiment_id: uuid.UUID) -> list[ObjectRelation]:
    rows = list(
        db.scalars(
            select(ObjectRelation)
            .where(
                ObjectRelation.source_object_id == experiment_id,
                ObjectRelation.relation_type == "references",
            )
            .order_by(ObjectRelation.created_at, ObjectRelation.id)
        ).all()
    )
    return sorted(
        rows,
        key=lambda row: ((row.properties_jsonb or {}).get("order_index", 0), str(row.id)),
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
    stable_references = [
        {
            "relation_id": item["relation_id"],
            "target_id": item["object"]["id"],
            "role": item["role"],
            "note": item["note"],
            "order_index": item["order_index"],
        }
        for values in body["references"].values()
        for item in values
    ]
    token_body = {
        "experiment": {
            key: value
            for key, value in body["experiment"].items()
            if key not in {"created_at", "updated_at"}
        },
        "references": stable_references,
    }
    return {"record_sha256": sha256_json(token_body), **body}


def _check_revision(
    db: Session, experiment: ResearchObject, expected_record_sha256: str | None
) -> None:
    if not expected_record_sha256:
        raise ValueError("revision_required")
    current = get_experiment_record(db, experiment.id)["record_sha256"]
    if expected_record_sha256.strip('"') != current:
        raise SemanticConflict("The Experiment changed after it was loaded", code="stale_record")


def _replace_refs(db: Session, experiment: ResearchObject, refs: list[Any]) -> None:
    lock_project_graph(db, experiment.project_scope_id)
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


def _add_ref(
    db: Session, experiment: ResearchObject, item: ExperimentReferenceCreate
) -> ObjectRelation:
    target = get_object(db, item.target_id)
    if target is None:
        raise LookupError("experiment reference target not found")
    if target.kind not in ALLOWED_REFERENCE_KINDS:
        raise ValueError(f"Experiments cannot reference {target.kind}")
    if item.target_kind is not None and target.kind != item.target_kind:
        raise ValueError("reference target_kind does not match target")
    validate_relation_scope(experiment, target)
    lock_project_graph(db, experiment.project_scope_id)
    duplicate = db.scalar(
        select(ObjectRelation).where(
            ObjectRelation.source_object_id == experiment.id,
            ObjectRelation.target_object_id == target.id,
            ObjectRelation.relation_type == "references",
        )
    )
    if duplicate is not None:
        raise ValueError("Experiment already references this target")
    relation = ObjectRelation(
        source_object_id=experiment.id,
        target_object_id=target.id,
        relation_type="references",
        role=item.role.strip() if item.role else None,
        properties_jsonb={"note": item.note, "order_index": item.order_index},
    )
    db.add(relation)
    db.flush()
    return relation


def create_experiment_record(
    db: Session, payload: ExperimentRecordCreate, *, commit: bool = True
) -> dict[str, Any]:
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
        if commit:
            db.commit()
        else:
            db.flush()
        return get_experiment_record(db, experiment.id)
    except Exception:
        db.rollback()
        raise


def update_experiment_record(
    db: Session,
    experiment_id: uuid.UUID,
    payload: ExperimentRecordPut,
    *,
    expected_record_sha256: str | None = None,
    commit: bool = True,
) -> dict[str, Any]:
    try:
        experiment = _locked_experiment(db, experiment_id)
        _check_revision(db, experiment, expected_record_sha256 or payload.base_record_sha256)
        changes = {
            key: value
            for key, value in payload.experiment.items()
            if key in {"title", "status", "tags", "properties_jsonb", "content_document"}
        }
        if changes:
            _update_object_in_session(db, experiment, changes)
        _replace_refs(db, experiment, payload.references)
        _create_revision_in_session(db, experiment.id, payload.change_note)
        if commit:
            db.commit()
        else:
            db.flush()
        return get_experiment_record(db, experiment.id)
    except Exception:
        db.rollback()
        raise


def patch_experiment_metadata(
    db: Session,
    experiment_id: uuid.UUID,
    payload: ExperimentMetadataPatch,
    *,
    expected_record_sha256: str | None = None,
) -> dict[str, Any]:
    try:
        experiment = _locked_experiment(db, experiment_id)
        _check_revision(db, experiment, expected_record_sha256)
        changes = {
            key: value
            for key, value in payload.model_dump(exclude_unset=True).items()
            if key in {"title", "status", "tags", "properties_jsonb", "content_document"}
        }
        if changes:
            _update_object_in_session(db, experiment, changes)
        _create_revision_in_session(db, experiment.id, payload.change_note)
        db.commit()
        return get_experiment_record(db, experiment.id)
    except Exception:
        db.rollback()
        raise


def add_experiment_reference(
    db: Session,
    experiment_id: uuid.UUID,
    payload: ExperimentReferenceCreate,
    *,
    expected_record_sha256: str | None = None,
) -> dict[str, Any]:
    try:
        experiment = _locked_experiment(db, experiment_id)
        _check_revision(db, experiment, expected_record_sha256)
        _add_ref(db, experiment, payload)
        _create_revision_in_session(db, experiment.id, "add experiment reference")
        db.commit()
        return get_experiment_record(db, experiment.id)
    except Exception:
        db.rollback()
        raise


def remove_experiment_reference(
    db: Session,
    experiment_id: uuid.UUID,
    relation_id: uuid.UUID,
    *,
    expected_record_sha256: str | None = None,
) -> dict[str, Any]:
    try:
        experiment = _locked_experiment(db, experiment_id)
        _check_revision(db, experiment, expected_record_sha256)
        relation = db.get(ObjectRelation, relation_id)
        if (
            relation is None
            or relation.source_object_id != experiment.id
            or relation.relation_type != "references"
        ):
            raise LookupError("experiment reference not found")
        db.delete(relation)
        db.flush()
        _create_revision_in_session(db, experiment.id, "remove experiment reference")
        db.commit()
        return get_experiment_record(db, experiment.id)
    except Exception:
        db.rollback()
        raise


def reorder_experiment_references(
    db: Session,
    experiment_id: uuid.UUID,
    payload: ExperimentReferenceOrder,
    *,
    expected_record_sha256: str | None = None,
) -> dict[str, Any]:
    try:
        experiment = _locked_experiment(db, experiment_id)
        _check_revision(db, experiment, expected_record_sha256)
        rows = _reference_rows(db, experiment.id)
        by_id = {row.id: row for row in rows}
        if len(payload.relation_ids) != len(set(payload.relation_ids)) or set(
            payload.relation_ids
        ) != set(by_id):
            raise ValueError("Reference order must contain every relation exactly once")
        for order_index, relation_id in enumerate(payload.relation_ids):
            relation = by_id[relation_id]
            relation.properties_jsonb = {
                **(relation.properties_jsonb or {}),
                "order_index": order_index,
            }
        _create_revision_in_session(db, experiment.id, payload.change_note or "reorder references")
        db.commit()
        return get_experiment_record(db, experiment.id)
    except Exception:
        db.rollback()
        raise
