from __future__ import annotations

import copy
import uuid
from collections import Counter
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.models import ObjectRelation, ResearchObject
from app.relation_semantics import RelationCandidate, SemanticConflict, validate_candidate_relations
from app.schemas import (
    ExperimentRecordCreate,
    ExperimentRecordPut,
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


def _membership_relations(db: Session, experiment_id: uuid.UUID) -> list[ObjectRelation]:
    return list(
        db.scalars(
            select(ObjectRelation)
            .where(
                ObjectRelation.source_object_id == experiment_id,
                ObjectRelation.relation_type == "includes",
            )
            .options(selectinload(ObjectRelation.target_object))
            .order_by(ObjectRelation.created_at, ObjectRelation.id)
        )
    )


def _validate_project(db: Session, project_scope_id: uuid.UUID) -> ResearchObject:
    project = get_object(db, project_scope_id)
    if project is None or project.kind != "project":
        raise ValueError("project_scope_id must point to a Project object")
    return project


def _normalised_members(
    db: Session, project_scope_id: uuid.UUID, members: list[Any]
) -> list[tuple[ResearchObject, int, str | None]]:
    seen: set[uuid.UUID] = set()
    result: list[tuple[ResearchObject, int, str | None]] = []
    for ordinal, member in enumerate(members):
        if member.sample_id in seen:
            raise SemanticConflict(
                "The same Sample cannot be included twice.", code="duplicate_membership"
            )
        seen.add(member.sample_id)
        sample = get_object(db, member.sample_id)
        if sample is None or sample.kind != "sample":
            raise LookupError("member Sample not found")
        if sample.project_scope_id != project_scope_id:
            raise ValueError("Experiment membership crosses project scopes")
        result.append((sample, ordinal, member.note.strip() if member.note else None))
    return result


def _legacy_context(db: Session, experiment_id: uuid.UUID) -> dict[str, int]:
    relations = db.scalars(
        select(ObjectRelation)
        .where(
            ObjectRelation.source_object_id == experiment_id,
            ObjectRelation.relation_type == "contains",
        )
        .options(selectinload(ObjectRelation.target_object))
    ).all()
    counts = Counter(relation.target_object.kind for relation in relations)
    return {
        "process_count": counts.get("process", 0),
        "sample_count": counts.get("sample", 0),
        "data_count": counts.get("data", 0),
    }


def _record_projection(db: Session, experiment: ResearchObject) -> dict[str, Any]:
    memberships = _membership_relations(db, experiment.id)
    members = [
        {
            "membership_id": relation.id,
            "ordinal": (relation.properties_jsonb or {}).get("ordinal", index),
            "note": (relation.properties_jsonb or {}).get("note"),
            "sample": object_out(relation.target_object),
        }
        for index, relation in enumerate(memberships)
    ]
    members.sort(key=lambda item: (item["ordinal"], str(item["membership_id"])))
    projection = {
        "experiment": object_out(experiment),
        "members": members,
        "member_count": len(members),
        "legacy_ownership_context": _legacy_context(db, experiment.id),
    }
    return {"record_sha256": sha256_json(projection), **projection}


def get_experiment_record(db: Session, experiment_id: uuid.UUID) -> dict[str, Any]:
    experiment = get_object(db, experiment_id)
    if experiment is None or experiment.kind != "experiment":
        raise LookupError("experiment not found")
    return _record_projection(db, experiment)


def create_experiment_record(db: Session, payload: ExperimentRecordCreate) -> dict[str, Any]:
    try:
        _validate_project(db, payload.project_scope_id)
        members = _normalised_members(db, payload.project_scope_id, payload.members)
        experiment = _create_object_in_session(
            db,
            ObjectCreate(
                kind="experiment",
                code=payload.experiment.code,
                title=payload.experiment.title,
                status=payload.experiment.status,
                project_scope_id=payload.project_scope_id,
                type_version_id=payload.experiment.type_version_id,
                properties_jsonb=copy.deepcopy(payload.experiment.properties_jsonb),
                content_document=copy.deepcopy(payload.experiment.content_document),
            ),
        )
        candidates = [
            RelationCandidate(
                source=experiment,
                target=sample,
                relation_type="includes",
                role=None,
                properties={"ordinal": ordinal, **({"note": note} if note else {})},
            )
            for sample, ordinal, note in members
        ]
        validate_candidate_relations(db, candidates)
        db.add_all(
            [
                ObjectRelation(
                    source_object_id=experiment.id,
                    target_object_id=sample.id,
                    relation_type="includes",
                    role=None,
                    properties_jsonb=candidate.properties,
                )
                for candidate, (sample, _ordinal, _note) in zip(candidates, members, strict=True)
            ]
        )
        db.flush()
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
        experiment = get_object(db, experiment_id)
        if experiment is None or experiment.kind != "experiment":
            raise LookupError("experiment not found")
        if experiment.project_scope_id is None:
            raise ValueError("Experiment has no project scope")
        members = _normalised_members(db, experiment.project_scope_id, payload.members)
        current = _membership_relations(db, experiment.id)
        current_by_sample = {relation.target_object_id: relation for relation in current}
        candidates = [
            RelationCandidate(
                source=experiment,
                target=sample,
                relation_type="includes",
                role=None,
                properties={"ordinal": ordinal, **({"note": note} if note else {})},
            )
            for sample, ordinal, note in members
        ]
        validate_candidate_relations(
            db, candidates, exclude_ids={relation.id for relation in current}
        )
        changes = payload.experiment.model_dump(exclude_unset=True)
        if changes:
            _update_object_in_session(db, experiment, changes)
        desired_samples = {sample.id for sample, _ordinal, _note in members}
        for relation in current:
            if relation.target_object_id not in desired_samples:
                db.delete(relation)
        db.flush()
        for candidate, (sample, _ordinal, _note) in zip(candidates, members, strict=True):
            relation = current_by_sample.get(sample.id)
            if relation is None:
                db.add(
                    ObjectRelation(
                        source_object_id=experiment.id,
                        target_object_id=sample.id,
                        relation_type="includes",
                        role=None,
                        properties_jsonb=copy.deepcopy(candidate.properties),
                    )
                )
            else:
                relation.properties_jsonb = copy.deepcopy(candidate.properties)
        db.flush()
        _create_revision_in_session(db, experiment.id, payload.change_note)
        db.commit()
        return get_experiment_record(db, experiment.id)
    except Exception:
        db.rollback()
        raise
