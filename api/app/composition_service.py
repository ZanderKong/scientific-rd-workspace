from __future__ import annotations

import copy
import uuid

from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.models import ObjectRelation, ResearchObject
from app.relation_semantics import (
    RelationCandidate,
    SemanticConflict,
    normalize_relation_role,
    owner_experiment_id,
    validate_candidate_relations,
)
from app.schemas import (
    ObjectCreate,
    ProcessCompositionItem,
    ProcessCompositionPut,
    RelationCreate,
)
from app.services import (
    _create_object_in_session,
    _create_relation_in_session,
    get_object,
    list_relations,
    object_out,
    relation_out,
)


def _composition_relations(db: Session, process_id: uuid.UUID) -> list[ObjectRelation]:
    return [
        relation
        for relation in list_relations(db, process_id)
        if relation.source_object_id == process_id
        and relation.relation_type in {"uses", "produces"}
    ]


def get_process_composition(db: Session, process_id: uuid.UUID) -> dict[str, object]:
    process = get_object(db, process_id)
    if process is None or process.kind != "process":
        raise LookupError("process not found")
    relations = _composition_relations(db, process.id)
    return {
        "process": object_out(process),
        "uses": [relation_out(item) for item in relations if item.relation_type == "uses"],
        "produces": [relation_out(item) for item in relations if item.relation_type == "produces"],
    }


def _materialize_target(
    db: Session, process: ResearchObject, item: ProcessCompositionItem
) -> ResearchObject:
    if item.target_object_id is not None:
        target = get_object(db, item.target_object_id)
        if target is None:
            raise LookupError("composition target object not found")
        return target
    if item.create_target is None:
        raise ValueError("composition item has no target")
    payload = ObjectCreate(
        kind=item.create_target.kind,
        title=item.create_target.title,
        status=item.create_target.status,
        type_version_id=item.create_target.type_version_id,
        project_scope_id=process.project_scope_id,
        properties_jsonb=copy.deepcopy(item.create_target.properties_jsonb),
        content_document=copy.deepcopy(item.create_target.content_document),
    )
    return _create_object_in_session(db, payload)


def _candidate_for_item(
    process: ResearchObject, target: ResearchObject, item: ProcessCompositionItem
) -> RelationCandidate:
    return RelationCandidate(
        source=process,
        target=target,
        relation_type=item.relation_type,
        role=normalize_relation_role(item.role),
        properties=copy.deepcopy(item.properties_jsonb),
        relation_id=item.relation_id,
    )


def put_process_composition(
    db: Session, process_id: uuid.UUID, payload: ProcessCompositionPut
) -> dict[str, object]:
    process = get_object(db, process_id)
    if process is None or process.kind != "process":
        raise LookupError("process not found")
    current = _composition_relations(db, process.id)
    current_by_id = {relation.id: relation for relation in current}
    current_ids = set(current_by_id)
    seen_relation_ids: set[uuid.UUID] = set()
    candidates: list[RelationCandidate] = []
    materialized: list[tuple[ProcessCompositionItem, RelationCandidate]] = []
    for item in payload.items:
        if item.relation_id is not None:
            if item.relation_id in seen_relation_ids:
                raise SemanticConflict("composition relation_id appears more than once")
            seen_relation_ids.add(item.relation_id)
            relation = current_by_id.get(item.relation_id)
            if relation is None:
                raise ValueError("relation_id does not belong to this Process composition")
            if relation.relation_type != item.relation_type:
                raise ValueError("composition relation_type does not match relation_id")
        target = _materialize_target(db, process, item)
        candidate = _candidate_for_item(process, target, item)
        candidates.append(candidate)
        materialized.append((item, candidate))

    # The current composition is replaced as a set. Excluding all old uses/
    # produces rows lets validation reason about the desired state before any
    # delete/update occurs, while unrelated contains/precedes/related_to edges
    # remain part of the graph and ownership checks.
    validate_candidate_relations(db, candidates, exclude_ids=current_ids)

    process_owner = owner_experiment_id(db, process.id)
    auto_owner_targets: list[ResearchObject] = []
    if process_owner is not None:
        for candidate in candidates:
            if candidate.relation_type != "produces":
                continue
            target_owner = owner_experiment_id(db, candidate.target.id)
            if target_owner is not None and target_owner != process_owner:
                raise SemanticConflict("output belongs to another Experiment")
            if target_owner is None:
                auto_owner_targets.append(candidate.target)

    for relation in current:
        if relation.id not in seen_relation_ids:
            db.delete(relation)
    db.flush()

    for target in auto_owner_targets:
        _create_relation_in_session(
            db,
            RelationCreate(
                source_object_id=process_owner,  # type: ignore[arg-type]
                target_object_id=target.id,
                relation_type="contains",
            ),
        )

    for item, candidate in materialized:
        if item.relation_id is not None:
            relation = current_by_id[item.relation_id]
            relation.target_object_id = candidate.target.id
            relation.role = candidate.role
            relation.properties_jsonb = copy.deepcopy(candidate.properties)
        else:
            db.add(
                ObjectRelation(
                    source_object_id=process.id,
                    target_object_id=candidate.target.id,
                    relation_type=candidate.relation_type,
                    role=candidate.role,
                    properties_jsonb=copy.deepcopy(candidate.properties),
                )
            )
    try:
        db.flush()
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise SemanticConflict("composition conflicts with a graph uniqueness invariant") from exc
    return get_process_composition(db, process.id)
