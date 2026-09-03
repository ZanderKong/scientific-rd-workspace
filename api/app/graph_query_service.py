from __future__ import annotations

import uuid

from sqlalchemy import String, cast, or_, select
from sqlalchemy.orm import Session, selectinload

from app.models import ObjectRelation, ObjectType, ObjectTypeVersion, ResearchObject
from app.relation_semantics import normalize_relation_role
from app.services import OBJECT_ALIASES, get_object, object_out

DEFAULT_DEPTH = 3
MAX_DEPTH = 8


def _relations(
    db: Session,
    *,
    source_id: uuid.UUID | None = None,
    target_id: uuid.UUID | None = None,
    relation_type: str | None = None,
) -> list[ObjectRelation]:
    conditions = []
    if source_id is not None:
        conditions.append(ObjectRelation.source_object_id == source_id)
    if target_id is not None:
        conditions.append(ObjectRelation.target_object_id == target_id)
    if relation_type is not None:
        conditions.append(ObjectRelation.relation_type == relation_type)
    return list(
        db.scalars(
            select(ObjectRelation)
            .where(*conditions)
            .options(
                selectinload(ObjectRelation.source_object)
                .selectinload(ResearchObject.type_version)
                .selectinload(ObjectTypeVersion.object_type),
                selectinload(ObjectRelation.target_object)
                .selectinload(ResearchObject.type_version)
                .selectinload(ObjectTypeVersion.object_type),
            )
            .order_by(ObjectRelation.created_at)
        )
    )


def _unique(objects: list[ResearchObject]) -> list[ResearchObject]:
    seen: set[uuid.UUID] = set()
    result = []
    for obj in objects:
        if obj.id not in seen:
            seen.add(obj.id)
            result.append(obj)
    return result


def _edge(relation: ObjectRelation) -> dict[str, object]:
    return {
        "id": relation.id,
        "source": relation.source_object_id,
        "target": relation.target_object_id,
        "type": relation.relation_type,
        "role": relation.role,
    }


def _direct_data(
    db: Session, sample_id: uuid.UUID
) -> tuple[list[ResearchObject], list[ResearchObject]]:
    testing_processes: list[ResearchObject] = []
    data: list[ResearchObject] = []
    for relation in _relations(db, target_id=sample_id, relation_type="uses"):
        if normalize_relation_role(relation.role) != "subject":
            continue
        process = relation.source_object
        if process.kind != "process":
            continue
        outputs = _relations(db, source_id=process.id, relation_type="produces")
        output_data = [item.target_object for item in outputs if item.target_object.kind == "data"]
        if output_data:
            testing_processes.append(process)
            data.extend(output_data)
    return _unique(testing_processes), _unique(data)


def _lineage(
    db: Session,
    sample_id: uuid.UUID,
    *,
    direction: str,
    depth: int,
) -> dict[str, object]:
    frontier = {sample_id}
    visited = {sample_id}
    samples: list[ResearchObject] = []
    data: list[ResearchObject] = []
    edges: list[dict[str, object]] = []
    truncated = False

    for _level in range(depth):
        next_frontier: set[uuid.UUID] = set()
        for current_id in frontier:
            if direction == "upstream":
                produced_relations = _relations(db, target_id=current_id, relation_type="produces")
                for produced in produced_relations:
                    process = produced.source_object
                    for used in _relations(db, source_id=process.id, relation_type="uses"):
                        if used.target_object.kind != "sample":
                            continue
                        if normalize_relation_role(used.role) != "precursor":
                            continue
                        candidate = used.target_object
                        edges.extend([_edge(used), _edge(produced)])
                        if candidate.id not in visited:
                            visited.add(candidate.id)
                            samples.append(candidate)
                            next_frontier.add(candidate.id)
                            _testing, current_data = _direct_data(db, candidate.id)
                            data.extend(current_data)
            else:
                uses = _relations(db, target_id=current_id, relation_type="uses")
                for used in uses:
                    if normalize_relation_role(used.role) != "precursor":
                        continue
                    process = used.source_object
                    if process.kind != "process":
                        continue
                    for produced in _relations(db, source_id=process.id, relation_type="produces"):
                        candidate = produced.target_object
                        if candidate.kind != "sample":
                            continue
                        edges.extend([_edge(used), _edge(produced)])
                        if candidate.id not in visited:
                            visited.add(candidate.id)
                            samples.append(candidate)
                            next_frontier.add(candidate.id)
                            _testing, current_data = _direct_data(db, candidate.id)
                            data.extend(current_data)
        frontier = next_frontier
        if not frontier:
            break
    if frontier:
        truncated = True
    return {
        "samples": _unique(samples),
        "data": _unique(data),
        "edges": edges,
        "depth": depth,
        "truncated": truncated,
    }


def _experiment_context(db: Session, experiment: ResearchObject) -> dict[str, object]:
    contained = [
        item.target_object
        for item in _relations(db, source_id=experiment.id, relation_type="contains")
    ]
    processes = _unique([item for item in contained if item.kind == "process"])
    samples = _unique([item for item in contained if item.kind == "sample"])
    data = _unique([item for item in contained if item.kind == "data"])
    owned_sample_ids = {item.id for item in samples}
    input_samples: list[ResearchObject] = []
    materials: list[ResearchObject] = []
    equipment: list[ResearchObject] = []
    for process in processes:
        for relation in _relations(db, source_id=process.id, relation_type="uses"):
            if (
                relation.target_object.kind == "sample"
                and relation.target_object.id not in owned_sample_ids
            ):
                input_samples.append(relation.target_object)
            elif relation.target_object.kind == "material":
                materials.append(relation.target_object)
            elif relation.target_object.kind == "equipment":
                equipment.append(relation.target_object)
    return {
        "experiment": object_out(experiment),
        "processes": [object_out(item) for item in processes],
        "samples": [object_out(item) for item in samples],
        "input_samples": [object_out(item) for item in _unique(input_samples)],
        "data": [object_out(item) for item in data],
        "materials": [object_out(item) for item in _unique(materials)],
        "equipment": [object_out(item) for item in _unique(equipment)],
    }


class GraphQueryService:
    def get_direct_relations(self, db: Session, object_id: uuid.UUID) -> list[ObjectRelation]:
        if get_object(db, object_id) is None:
            raise LookupError("object not found")
        return _relations(db, source_id=object_id) + [
            relation
            for relation in _relations(db, target_id=object_id)
            if relation.source_object_id != object_id
        ]

    def get_sample_context(
        self, db: Session, sample_id: uuid.UUID, depth: int = DEFAULT_DEPTH
    ) -> dict[str, object]:
        if depth < 0 or depth > MAX_DEPTH:
            raise ValueError(f"depth must be between 0 and {MAX_DEPTH}")
        sample = get_object(db, sample_id)
        if sample is None or sample.kind != "sample":
            raise LookupError("sample not found")
        producing_relations = _relations(db, target_id=sample.id, relation_type="produces")
        producing_processes = [
            item.source_object
            for item in producing_relations
            if item.source_object.kind == "process"
        ]
        precursors: list[ResearchObject] = []
        sample_inputs: list[dict[str, object]] = []
        materials: list[ResearchObject] = []
        equipment: list[ResearchObject] = []
        for process in producing_processes:
            for relation in _relations(db, source_id=process.id, relation_type="uses"):
                if relation.target_object.kind == "sample":
                    role = normalize_relation_role(relation.role)
                    if role is not None:
                        sample_inputs.append(
                            {
                                "object": object_out(relation.target_object),
                                "role": role,
                                "relation_id": relation.id,
                            }
                        )
                    if role == "precursor":
                        precursors.append(relation.target_object)
                elif relation.target_object.kind == "material":
                    materials.append(relation.target_object)
                elif relation.target_object.kind == "equipment":
                    equipment.append(relation.target_object)
        testing_processes, direct_data = _direct_data(db, sample.id)
        upstream = _lineage(db, sample.id, direction="upstream", depth=depth)
        downstream = _lineage(db, sample.id, direction="downstream", depth=depth)
        experiment = None
        experiment_relation = db.scalar(
            select(ObjectRelation)
            .where(
                ObjectRelation.relation_type == "contains",
                ObjectRelation.target_object_id == sample.id,
            )
            .options(selectinload(ObjectRelation.source_object))
        )
        if experiment_relation and experiment_relation.source_object.kind == "experiment":
            experiment = _experiment_context(db, experiment_relation.source_object)
        return {
            "current": object_out(sample),
            "direct": {
                "producing_processes": [object_out(item) for item in _unique(producing_processes)],
                "precursor_samples": [object_out(item) for item in _unique(precursors)],
                "materials": [object_out(item) for item in _unique(materials)],
                "equipment": [object_out(item) for item in _unique(equipment)],
                "testing_processes": [object_out(item) for item in testing_processes],
                "sample_inputs": sample_inputs,
                "data": [object_out(item) for item in direct_data],
            },
            "upstream": {
                **upstream,
                "samples": [object_out(item) for item in upstream["samples"]],
                "data": [object_out(item) for item in upstream["data"]],
            },
            "downstream": {
                **downstream,
                "samples": [object_out(item) for item in downstream["samples"]],
                "data": [object_out(item) for item in downstream["data"]],
            },
            "experiment_context": experiment,
        }

    def get_experiment_context(self, db: Session, experiment_id: uuid.UUID) -> dict[str, object]:
        experiment = get_object(db, experiment_id)
        if experiment is None or experiment.kind != "experiment":
            raise LookupError("experiment not found")
        return _experiment_context(db, experiment)

    def trace_sample_lineage(
        self, db: Session, sample_id: uuid.UUID, depth: int = DEFAULT_DEPTH
    ) -> dict[str, object]:
        context = self.get_sample_context(db, sample_id, depth)
        return {"upstream": context["upstream"], "downstream": context["downstream"]}

    def get_downstream_samples(
        self, db: Session, sample_id: uuid.UUID, depth: int = DEFAULT_DEPTH
    ) -> list[ResearchObject]:
        context = self.get_sample_context(db, sample_id, depth)
        return context["downstream"]["samples"]  # type: ignore[no-any-return]

    def search_objects(
        self,
        db: Session,
        *,
        q: str | None = None,
        kind: str | None = None,
        kinds: list[str] | None = None,
        project_scope_id: uuid.UUID | None = None,
        type_key: str | None = None,
        type_id: uuid.UUID | None = None,
        status: str | None = None,
        include_global: bool = True,
        limit: int = 50,
        offset: int = 0,
    ) -> list[ResearchObject]:
        statement = (
            select(ResearchObject)
            .join(ObjectTypeVersion, ResearchObject.type_version_id == ObjectTypeVersion.id)
            .join(ObjectType, ObjectTypeVersion.object_type_id == ObjectType.id)
            .options(
                selectinload(ResearchObject.type_version).selectinload(
                    ObjectTypeVersion.object_type
                )
            )
        )
        if kind:
            statement = statement.where(ResearchObject.kind == kind)
        if kinds:
            statement = statement.where(ResearchObject.kind.in_(kinds))
        if type_key:
            statement = statement.where(ObjectType.key == type_key)
        if type_id:
            statement = statement.where(ObjectType.id == type_id)
        if project_scope_id:
            if include_global:
                statement = statement.where(
                    (ResearchObject.project_scope_id == project_scope_id)
                    | (
                        ResearchObject.kind.in_(["material", "equipment"])
                        & ResearchObject.project_scope_id.is_(None)
                    )
                )
            else:
                statement = statement.where(ResearchObject.project_scope_id == project_scope_id)
        elif not include_global:
            statement = statement.where(ResearchObject.project_scope_id.is_not(None))
        if status:
            statement = statement.where(ResearchObject.status == status)
        if q:
            normalized = q.strip().lstrip("@").lower()
            matched_kind = next(
                (
                    candidate
                    for candidate, aliases in OBJECT_ALIASES.items()
                    if normalized in aliases
                ),
                None,
            )
            if matched_kind:
                statement = statement.where(ResearchObject.kind == matched_kind)
            else:
                pattern = f"%{q.strip().lstrip('@')}%"
                statement = statement.where(
                    or_(
                        ResearchObject.code.ilike(pattern),
                        ResearchObject.title.ilike(pattern),
                        cast(ResearchObject.properties_jsonb, String).ilike(pattern),
                    )
                )
        return list(
            db.scalars(
                statement.order_by(ResearchObject.updated_at.desc(), ResearchObject.code.asc())
                .offset(offset)
                .limit(limit)
            )
        )


graph_query_service = GraphQueryService()
