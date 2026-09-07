from __future__ import annotations

import uuid
from collections import defaultdict
from dataclasses import dataclass
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models import ObjectRelation, ResearchObject


class SemanticConflict(ValueError):
    def __init__(self, message: str, *, code: str = "semantic_conflict") -> None:
        self.code = code
        super().__init__(message)


ROLE_ALIASES = {
    "参照": "reference",
    "参考样品": "reference",
    "对照": "control",
    "对照样品": "control",
    "前驱体": "precursor",
    "前驱样品": "precursor",
    "被测样品": "subject",
    "测试对象": "subject",
    "specimen": "subject",
}


def normalize_relation_role(role: str | None) -> str | None:
    if role is None:
        return None
    value = role.strip()
    if not value:
        return None
    return ROLE_ALIASES.get(value.casefold(), value)


def scope_id(
    obj: ResearchObject, overrides: dict[uuid.UUID, uuid.UUID | None] | None = None
) -> uuid.UUID | None:
    if overrides and obj.id in overrides:
        return overrides[obj.id]
    if obj.kind == "project":
        return obj.id
    return obj.project_scope_id


def validate_relation_scope(
    source: ResearchObject,
    target: ResearchObject,
    overrides: dict[uuid.UUID, uuid.UUID | None] | None = None,
) -> None:
    source_scope = scope_id(source, overrides)
    target_scope = scope_id(target, overrides)
    if source_scope is None or target_scope is None or source_scope == target_scope:
        return
    if source.kind == "research_object" and source_scope is None:
        return
    if target.kind == "research_object" and target_scope is None:
        return
    raise SemanticConflict("relation crosses project scopes", code="scope_conflict")


def lock_project_graph(db: Session, project_scope_id: uuid.UUID | None) -> None:
    """Serialize graph mutations for one project for the transaction lifetime."""
    if project_scope_id is None:
        return
    db.execute(select(func.pg_advisory_xact_lock(func.hashtext(str(project_scope_id)))))


def validate_relation_kinds(
    source: ResearchObject, target: ResearchObject, relation_type: str
) -> None:
    valid = {
        "references": source.kind == "experiment"
        and target.kind in {"research_object", "data", "process_definition", "view", "claim"},
        "subject": source.kind == "data" and target.kind == "research_object",
        "derived_from": source.kind == "data" and target.kind == "data",
        "related_to": True,
    }
    if not valid.get(relation_type, False):
        raise ValueError(f"invalid {relation_type} relation for source/target kinds")
    if source.id == target.id:
        raise ValueError("self relations are not allowed")


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


def validate_derived_cycle(db: Session, source: ResearchObject, target: ResearchObject) -> None:
    rows = db.execute(
        select(ObjectRelation.source_object_id, ObjectRelation.target_object_id).where(
            ObjectRelation.relation_type == "derived_from"
        )
    ).all()
    adjacency: dict[uuid.UUID, set[uuid.UUID]] = defaultdict(set)
    for source_id, target_id in rows:
        adjacency[source_id].add(target_id)
    adjacency[source.id].add(target.id)
    if _has_cycle(adjacency):
        raise SemanticConflict("Data derived_from cycle is not allowed")


def validate_relation_metadata(role: str | None, properties: dict[str, Any]) -> None:
    if role is not None and not role.strip():
        raise ValueError("relation role must not be blank")
    quantity = properties.get("quantity")
    if quantity is not None:
        if (
            not isinstance(quantity, dict)
            or not isinstance(quantity.get("value"), (int, float))
            or isinstance(quantity.get("value"), bool)
            or not isinstance(quantity.get("unit"), str)
            or not quantity["unit"].strip()
        ):
            raise ValueError("quantity must contain numeric value and unit")


def validate_scope_mutation(db: Session, obj: ResearchObject, next_scope: uuid.UUID | None) -> None:
    if next_scope == obj.project_scope_id:
        return
    overrides = {obj.id: next_scope}
    relations = db.scalars(
        select(ObjectRelation).where(
            (ObjectRelation.source_object_id == obj.id)
            | (ObjectRelation.target_object_id == obj.id)
        )
    ).all()
    for relation in relations:
        source = (
            obj
            if relation.source_object_id == obj.id
            else db.get(ResearchObject, relation.source_object_id)
        )
        target = (
            obj
            if relation.target_object_id == obj.id
            else db.get(ResearchObject, relation.target_object_id)
        )
        if source is not None and target is not None:
            validate_relation_scope(source, target, overrides)


@dataclass
class RelationCandidate:
    source: ResearchObject
    target: ResearchObject
    relation_type: str
    role: str | None = None
    properties: dict[str, Any] | None = None
    relation_id: uuid.UUID | None = None
