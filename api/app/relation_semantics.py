from __future__ import annotations

import uuid
from collections import defaultdict
from collections.abc import Iterable, Mapping
from dataclasses import dataclass

from sqlalchemy import select
from sqlalchemy.orm import Session, aliased

from app.models import ObjectRelation, ResearchObject


class SemanticConflict(ValueError):
    """A graph write conflicts with a canonical domain invariant."""

    def __init__(self, message: str, *, code: str = "semantic_conflict") -> None:
        self.code = code
        super().__init__(message)


ROLE_ALIASES: dict[str, str] = {
    "precursor": "precursor",
    "前驱体": "precursor",
    "前驱样品": "precursor",
    "subject": "subject",
    "specimen": "subject",
    "测试对象": "subject",
    "被测样品": "subject",
    "reference": "reference",
    "参照": "reference",
    "参考样品": "reference",
    "control": "control",
    "对照": "control",
    "对照样品": "control",
}
CANONICAL_SAMPLE_ROLES = frozenset({"precursor", "subject", "reference", "control"})


def normalize_relation_role(role: str | None) -> str | None:
    if role is None:
        return None
    trimmed = role.strip()
    if not trimmed:
        return None
    return ROLE_ALIASES.get(trimmed.casefold(), trimmed)


def relation_key(
    source_object_id: uuid.UUID,
    target_object_id: uuid.UUID,
    relation_type: str,
    role: str | None,
) -> tuple[uuid.UUID, uuid.UUID, str, str | None]:
    return source_object_id, target_object_id, relation_type, normalize_relation_role(role)


def scope_id(obj: ResearchObject, overrides: Mapping[uuid.UUID, uuid.UUID | None] | None = None):
    if obj.kind == "project":
        return obj.id
    if overrides and obj.id in overrides:
        return overrides[obj.id]
    return obj.project_scope_id


def is_global_library_object(obj: ResearchObject) -> bool:
    return obj.kind in {"material", "equipment"} and obj.project_scope_id is None


def validate_relation_kinds(
    source: ResearchObject, target: ResearchObject, relation_type: str
) -> None:
    valid = {
        "contains": source.kind == "experiment" and target.kind in {"process", "sample", "data"},
        "includes": source.kind == "experiment" and target.kind == "sample",
        "uses": source.kind == "process"
        and target.kind in {"material", "sample", "equipment", "data"},
        "produces": source.kind == "process" and target.kind in {"sample", "data"},
        "precedes": source.kind == "process" and target.kind == "process",
        "related_to": True,
    }
    if not valid.get(relation_type, False):
        raise ValueError(f"invalid {relation_type} relation for source/target kinds")
    if source.id == target.id:
        raise ValueError("self relations are not allowed")


def validate_relation_scope(
    source: ResearchObject,
    target: ResearchObject,
    overrides: Mapping[uuid.UUID, uuid.UUID | None] | None = None,
) -> None:
    source_scope = scope_id(source, overrides)
    target_scope = scope_id(target, overrides)
    if source_scope is None or target_scope is None or source_scope == target_scope:
        return
    if is_global_library_object(source) or is_global_library_object(target):
        return
    raise ValueError("relation crosses project scopes")


def validate_relation_metadata(role: str | None, properties: dict[str, object]) -> None:
    if role is not None and not role.strip():
        raise ValueError("relation role must not be blank")
    quantity = properties.get("quantity")
    if quantity is not None:
        if (
            not isinstance(quantity, dict)
            or not isinstance(quantity.get("value"), (int, float))
            or isinstance(quantity.get("value"), bool)
        ):
            raise ValueError("quantity.value must be numeric")
        if not isinstance(quantity.get("unit"), str) or not quantity["unit"].strip():
            raise ValueError("quantity.unit must be a non-empty string")
    usage_values = properties.get("usage_values")
    if usage_values is None:
        return
    if not isinstance(usage_values, Mapping):
        raise ValueError("usage_values must be an object")
    for key, payload in usage_values.items():
        if not isinstance(key, str) or not key.strip():
            raise ValueError("usage_values keys must be non-empty strings")
        if not isinstance(payload, Mapping) or "value" not in payload:
            raise ValueError("each usage value must contain a scalar value")
        value = payload["value"]
        if isinstance(value, (dict, list, tuple, set)):
            raise ValueError("usage value must be scalar")
        if "unit" in payload and payload["unit"] is not None:
            if not isinstance(payload["unit"], str) or not payload["unit"].strip():
                raise ValueError("usage value unit must be a non-empty string")


def _excluded(statement, exclude_ids: set[uuid.UUID]):
    return statement.where(ObjectRelation.id.not_in(exclude_ids)) if exclude_ids else statement


def owner_experiment_id(
    db: Session, object_id: uuid.UUID, exclude_ids: set[uuid.UUID] | None = None
) -> uuid.UUID | None:
    statement = select(ObjectRelation.source_object_id).where(
        ObjectRelation.target_object_id == object_id,
        ObjectRelation.relation_type == "contains",
    )
    return db.scalar(_excluded(statement, exclude_ids or set()))


def producer_process_id(
    db: Session, object_id: uuid.UUID, exclude_ids: set[uuid.UUID] | None = None
) -> uuid.UUID | None:
    statement = select(ObjectRelation.source_object_id).where(
        ObjectRelation.target_object_id == object_id,
        ObjectRelation.relation_type == "produces",
    )
    return db.scalar(_excluded(statement, exclude_ids or set()))


def _relation_exists_for_key(
    db: Session,
    source_id: uuid.UUID,
    target_id: uuid.UUID,
    relation_type: str,
    role: str | None,
    exclude_ids: set[uuid.UUID],
) -> bool:
    statement = select(ObjectRelation.id).where(
        ObjectRelation.source_object_id == source_id,
        ObjectRelation.target_object_id == target_id,
        ObjectRelation.relation_type == relation_type,
        ObjectRelation.role.is_not_distinct_from(normalize_relation_role(role)),
    )
    return db.scalar(_excluded(statement, exclude_ids)) is not None


def _count_incoming(
    db: Session, target_id: uuid.UUID, relation_type: str, exclude_ids: set[uuid.UUID]
) -> int:
    statement = select(ObjectRelation.id).where(
        ObjectRelation.target_object_id == target_id,
        ObjectRelation.relation_type == relation_type,
    )
    return len(db.scalars(_excluded(statement, exclude_ids)).all())


def _precedes_neighbors(
    db: Session, process_id: uuid.UUID, exclude_ids: set[uuid.UUID]
) -> list[uuid.UUID]:
    statement = select(ObjectRelation.source_object_id, ObjectRelation.target_object_id).where(
        ObjectRelation.relation_type == "precedes",
        (ObjectRelation.source_object_id == process_id)
        | (ObjectRelation.target_object_id == process_id),
    )
    return [
        target_id if source_id == process_id else source_id
        for source_id, target_id in db.execute(_excluded(statement, exclude_ids))
    ]


@dataclass(frozen=True)
class RelationCandidate:
    source: ResearchObject
    target: ResearchObject
    relation_type: str
    role: str | None
    properties: dict[str, object]
    relation_id: uuid.UUID | None = None


def validate_relation_ownership(
    db: Session,
    candidate: RelationCandidate,
    *,
    exclude_ids: set[uuid.UUID] | None = None,
) -> None:
    excluded = exclude_ids or set()
    source = candidate.source
    target = candidate.target
    relation_type = candidate.relation_type

    if relation_type == "contains":
        existing_owner = owner_experiment_id(db, target.id, excluded)
        if existing_owner is not None and existing_owner != source.id:
            raise SemanticConflict("target already belongs to another Experiment")
        if target.kind == "process":
            for neighbor_id in _precedes_neighbors(db, target.id, excluded):
                neighbor_owner = owner_experiment_id(db, neighbor_id, excluded)
                if neighbor_owner is not None and neighbor_owner != source.id:
                    raise SemanticConflict(
                        "contained Process has a precedes neighbor owned by another Experiment"
                    )
        if target.kind in {"sample", "data"}:
            producer_id = producer_process_id(db, target.id, excluded)
            if producer_id is not None:
                producer_owner = owner_experiment_id(db, producer_id, excluded)
                if producer_owner is not None and producer_owner != source.id:
                    raise SemanticConflict("contained output is produced by another Experiment")

    if relation_type == "produces":
        source_owner = owner_experiment_id(db, source.id, excluded)
        target_owner = owner_experiment_id(db, target.id, excluded)
        if source_owner is not None and target_owner is not None and source_owner != target_owner:
            raise SemanticConflict("producer and output belong to different Experiments")

    if relation_type == "precedes":
        source_owner = owner_experiment_id(db, source.id, excluded)
        target_owner = owner_experiment_id(db, target.id, excluded)
        if source_owner is not None and target_owner is not None and source_owner != target_owner:
            raise SemanticConflict("precedes cannot cross Experiment ownership")


def validate_relation_cardinality(
    db: Session,
    candidate: RelationCandidate,
    *,
    exclude_ids: set[uuid.UUID] | None = None,
) -> None:
    excluded = exclude_ids or set()
    if candidate.relation_type == "contains" and _count_incoming(
        db, candidate.target.id, "contains", excluded
    ):
        raise SemanticConflict("target already has an owning Experiment")
    if candidate.relation_type in {"produces"} and _count_incoming(
        db, candidate.target.id, "produces", excluded
    ):
        raise SemanticConflict("target already has a producing Process")


def _scoped_lineage_rows(
    db: Session, project_scope_id: uuid.UUID | None, exclude_ids: set[uuid.UUID]
) -> list[tuple[uuid.UUID, uuid.UUID, str, str | None, str, str]]:
    if project_scope_id is None:
        return []
    source = aliased(ResearchObject)
    target = aliased(ResearchObject)
    statement = (
        select(
            ObjectRelation.source_object_id,
            ObjectRelation.target_object_id,
            ObjectRelation.relation_type,
            ObjectRelation.role,
            source.kind,
            target.kind,
        )
        .join(source, source.id == ObjectRelation.source_object_id)
        .join(target, target.id == ObjectRelation.target_object_id)
        .where(
            source.project_scope_id == project_scope_id,
            target.project_scope_id == project_scope_id,
            ObjectRelation.relation_type.in_(["uses", "produces"]),
        )
    )
    rows = db.execute(_excluded(statement, exclude_ids)).all()
    return list(rows)


def _scoped_precedes_rows(
    db: Session, project_scope_id: uuid.UUID | None, exclude_ids: set[uuid.UUID]
) -> list[tuple[uuid.UUID, uuid.UUID]]:
    if project_scope_id is None:
        return []
    source = aliased(ResearchObject)
    target = aliased(ResearchObject)
    statement = (
        select(ObjectRelation.source_object_id, ObjectRelation.target_object_id)
        .join(source, source.id == ObjectRelation.source_object_id)
        .join(target, target.id == ObjectRelation.target_object_id)
        .where(
            source.project_scope_id == project_scope_id,
            target.project_scope_id == project_scope_id,
            ObjectRelation.relation_type == "precedes",
        )
    )
    return list(db.execute(_excluded(statement, exclude_ids)).all())


def _has_cycle(adjacency: dict[uuid.UUID, set[uuid.UUID]]) -> bool:
    visiting: set[uuid.UUID] = set()
    visited: set[uuid.UUID] = set()

    def visit(node: uuid.UUID) -> bool:
        if node in visiting:
            return True
        if node in visited:
            return False
        visiting.add(node)
        if any(visit(child) for child in adjacency.get(node, ())):
            return True
        visiting.remove(node)
        visited.add(node)
        return False

    return any(visit(node) for node in adjacency)


def validate_lineage_cycle(
    db: Session,
    candidates: Iterable[RelationCandidate],
    *,
    exclude_ids: set[uuid.UUID] | None = None,
) -> None:
    candidates = list(candidates)
    project_scope_id = next(
        (
            scope_id(candidate.source)
            for candidate in candidates
            if scope_id(candidate.source) is not None
        ),
        None,
    )
    if project_scope_id is None:
        return
    precursors: dict[uuid.UUID, set[uuid.UUID]] = defaultdict(set)
    outputs: dict[uuid.UUID, set[uuid.UUID]] = defaultdict(set)
    for source_id, target_id, relation_type, role, source_kind, target_kind in _scoped_lineage_rows(
        db, project_scope_id, exclude_ids or set()
    ):
        if relation_type == "uses" and source_kind == "process" and target_kind == "sample":
            if normalize_relation_role(role) == "precursor":
                precursors[source_id].add(target_id)
        elif relation_type == "produces" and source_kind == "process" and target_kind == "sample":
            outputs[source_id].add(target_id)
    for candidate in candidates:
        if candidate.relation_type == "uses" and candidate.target.kind == "sample":
            if normalize_relation_role(candidate.role) == "precursor":
                precursors[candidate.source.id].add(candidate.target.id)
        elif candidate.relation_type == "produces" and candidate.target.kind == "sample":
            outputs[candidate.source.id].add(candidate.target.id)
    adjacency: dict[uuid.UUID, set[uuid.UUID]] = defaultdict(set)
    for process_id, input_ids in precursors.items():
        for input_id in input_ids:
            adjacency[input_id].update(outputs.get(process_id, set()))
    if _has_cycle(adjacency):
        raise SemanticConflict("sample precursor lineage cycle is not allowed")


def validate_precedes_cycle(
    db: Session,
    candidates: Iterable[RelationCandidate],
    *,
    exclude_ids: set[uuid.UUID] | None = None,
) -> None:
    candidates = list(candidates)
    project_scope_id = next(
        (
            scope_id(candidate.source)
            for candidate in candidates
            if scope_id(candidate.source) is not None
        ),
        None,
    )
    if project_scope_id is None:
        return
    adjacency: dict[uuid.UUID, set[uuid.UUID]] = defaultdict(set)
    for source_id, target_id in _scoped_precedes_rows(db, project_scope_id, exclude_ids or set()):
        adjacency[source_id].add(target_id)
    for candidate in candidates:
        if candidate.relation_type == "precedes":
            adjacency[candidate.source.id].add(candidate.target.id)
    if _has_cycle(adjacency):
        raise SemanticConflict("Process precedes cycle is not allowed")


def validate_candidate_relations(
    db: Session,
    candidates: Iterable[RelationCandidate],
    *,
    exclude_ids: set[uuid.UUID] | None = None,
) -> None:
    candidates = list(candidates)
    excluded = exclude_ids or set()
    keys: set[tuple[uuid.UUID, uuid.UUID, str, str | None]] = set()
    incoming_targets: set[tuple[uuid.UUID, str]] = set()
    for candidate in candidates:
        role = normalize_relation_role(candidate.role)
        candidate = RelationCandidate(
            source=candidate.source,
            target=candidate.target,
            relation_type=candidate.relation_type,
            role=role,
            properties=candidate.properties,
            relation_id=candidate.relation_id,
        )
        validate_relation_kinds(candidate.source, candidate.target, candidate.relation_type)
        validate_relation_scope(candidate.source, candidate.target)
        validate_relation_metadata(candidate.role, candidate.properties)
        if candidate.relation_type == "includes" and candidate.role is not None:
            raise ValueError("Experiment Sample membership does not support a role")
        if (
            candidate.relation_type == "uses"
            and candidate.target.kind == "sample"
            and candidate.role is None
        ):
            raise ValueError("Process uses Sample requires a relation role")
        key = relation_key(
            candidate.source.id, candidate.target.id, candidate.relation_type, candidate.role
        )
        if key in keys or _relation_exists_for_key(
            db,
            candidate.source.id,
            candidate.target.id,
            candidate.relation_type,
            candidate.role,
            excluded,
        ):
            raise SemanticConflict("duplicate relation")
        keys.add(key)
        cardinality_key = (candidate.target.id, candidate.relation_type)
        if candidate.relation_type in {"contains", "produces"}:
            if cardinality_key in incoming_targets:
                raise SemanticConflict("target violates relation cardinality")
            incoming_targets.add(cardinality_key)
        validate_relation_cardinality(db, candidate, exclude_ids=excluded)
        validate_relation_ownership(db, candidate, exclude_ids=excluded)
    validate_lineage_cycle(db, candidates, exclude_ids=excluded)
    validate_precedes_cycle(db, candidates, exclude_ids=excluded)


def validate_scope_mutation(db: Session, obj: ResearchObject, next_scope: uuid.UUID | None) -> None:
    if next_scope == obj.project_scope_id:
        return
    relations = db.scalars(
        select(ObjectRelation).where(
            (ObjectRelation.source_object_id == obj.id)
            | (ObjectRelation.target_object_id == obj.id)
        )
    ).all()
    overrides = {obj.id: next_scope}
    objects: dict[uuid.UUID, ResearchObject] = {obj.id: obj}
    for relation in relations:
        for object_id in (relation.source_object_id, relation.target_object_id):
            if object_id not in objects:
                other = db.get(ResearchObject, object_id)
                if other is not None:
                    objects[object_id] = other
    for relation in relations:
        source = objects[relation.source_object_id]
        target = objects[relation.target_object_id]
        validate_relation_kinds(source, target, relation.relation_type)
        validate_relation_scope(source, target, overrides)
