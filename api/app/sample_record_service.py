from __future__ import annotations

import copy
import uuid
from dataclasses import dataclass
from typing import Any

from sqlalchemy.orm import Session

from app.models import ObjectRelation, ResearchObject
from app.relation_semantics import (
    RelationCandidate,
    SemanticConflict,
    normalize_relation_role,
    validate_candidate_relations,
)
from app.schemas import (
    ObjectCreate,
    RelationCreate,
    SampleRecordCreate,
    SampleRecordProcessDraft,
    SampleRecordPut,
    SampleRecordResourceDraft,
    UsageFieldDefinition,
    UsageSchema,
    UsageValue,
)
from app.services import (
    _create_object_in_session,
    _create_relation_in_session,
    _create_revision_in_session,
    _update_object_in_session,
    get_object,
    list_relations,
    object_out,
    sha256_json,
)

RESOURCE_KINDS = frozenset({"material", "equipment"})


@dataclass
class _ResourcePlan:
    draft: SampleRecordResourceDraft
    target: ResearchObject
    role: str
    properties: dict[str, Any]
    candidate: RelationCandidate
    existing_relation: ObjectRelation | None = None


def _unique_messages(messages: list[str]) -> list[str]:
    return list(dict.fromkeys(messages))


def _usage_fields(obj: ResearchObject) -> dict[str, UsageFieldDefinition]:
    schema = UsageSchema.model_validate(obj.usage_schema_jsonb or {})
    return {field.key: field for field in schema.fields}


def _merge_usage_schema(obj: ResearchObject, additions: list[UsageFieldDefinition]) -> bool:
    if not additions:
        return False
    if obj.kind not in RESOURCE_KINDS:
        raise ValueError("usage schema additions require a material or equipment resource")
    existing = _usage_fields(obj)
    fields = list(existing.values())
    changed = False
    for addition in additions:
        prior = existing.get(addition.key)
        if prior is not None:
            if prior.model_dump(exclude_none=True) != addition.model_dump(exclude_none=True):
                raise SemanticConflict(
                    f"usage field {addition.key!r} already exists with a different definition"
                )
            continue
        fields.append(addition)
        existing[addition.key] = addition
        changed = True
    if changed:
        obj.usage_schema_jsonb = {
            "fields": [field.model_dump(exclude_none=True) for field in fields]
        }
    return changed


def _validate_usage_values(
    obj: ResearchObject, values: dict[str, UsageValue]
) -> dict[str, dict[str, Any]]:
    if obj.kind not in RESOURCE_KINDS and values:
        raise ValueError("usage values require a material or equipment resource")
    fields = _usage_fields(obj)
    result: dict[str, dict[str, Any]] = {}
    for key, usage in values.items():
        field = fields.get(key)
        # Legacy quantity relations did not have a per-resource schema. Keep that
        # field editable without inventing a schema mutation during read/upgrade.
        if field is None and key == "quantity":
            value = usage.value
            if isinstance(value, bool) or not isinstance(value, (int, float)):
                raise ValueError("usage field quantity must be numeric")
        elif field is None:
            raise ValueError(f"usage field {key!r} is not defined on {obj.code}")
        else:
            value = usage.value
            if field.value_type == "number" and (
                isinstance(value, bool) or not isinstance(value, (int, float))
            ):
                raise ValueError(f"usage field {key!r} must be numeric")
            if field.value_type == "text" and not isinstance(value, str):
                raise ValueError(f"usage field {key!r} must be text")
            if field.value_type == "boolean" and not isinstance(value, bool):
                raise ValueError(f"usage field {key!r} must be boolean")
            if field.value_type == "select" and value not in field.options:
                raise ValueError(f"usage field {key!r} must match one of its options")
            if field.required and (value is None or value == ""):
                raise ValueError(f"required usage field {key!r} is empty")
        result[key] = usage.model_dump(exclude_none=True)
    return result


def _legacy_and_current_usage_values(relation: ObjectRelation) -> dict[str, dict[str, Any]]:
    properties = relation.properties_jsonb or {}
    values: dict[str, dict[str, Any]] = {}
    legacy = properties.get("quantity")
    if isinstance(legacy, dict) and "value" in legacy:
        values["quantity"] = copy.deepcopy(legacy)
    current = properties.get("usage_values")
    if isinstance(current, dict):
        for key, value in current.items():
            if isinstance(key, str) and isinstance(value, dict) and "value" in value:
                values[key] = copy.deepcopy(value)
    return values


def _incoming_precedes(db: Session, process_id: uuid.UUID) -> list[ObjectRelation]:
    return [
        relation
        for relation in list_relations(db, process_id)
        if relation.relation_type == "precedes" and relation.target_object_id == process_id
    ]


def _outgoing_precedes(db: Session, process_id: uuid.UUID) -> list[ObjectRelation]:
    return [
        relation
        for relation in list_relations(db, process_id)
        if relation.relation_type == "precedes" and relation.source_object_id == process_id
    ]


def _sample_producer(
    db: Session, sample: ResearchObject
) -> tuple[ResearchObject | None, list[str]]:
    relations = [
        relation
        for relation in list_relations(db, sample.id)
        if relation.relation_type == "produces" and relation.target_object_id == sample.id
    ]
    if not relations:
        return None, ["Sample has no producing Process"]
    if len(relations) > 1:
        return None, ["Sample has more than one producing Process"]
    producer = relations[0].source_object
    if producer.kind != "process":
        return None, ["Sample producer is not a Process"]
    return producer, []


def _reconstruct_chain(
    db: Session, producer: ResearchObject
) -> tuple[list[ResearchObject], list[str]]:
    blockers: list[str] = []
    reverse_chain = [producer]
    visited = {producer.id}
    current = producer
    while True:
        incoming = _incoming_precedes(db, current.id)
        if len(incoming) > 1:
            blockers.append(f"Process {current.code} has multiple preceding Process branches")
            break
        if not incoming:
            break
        predecessor = incoming[0].source_object
        if predecessor.id in visited:
            blockers.append("Process precedes chain contains a cycle")
            break
        if predecessor.kind != "process":
            blockers.append("Process precedes chain points to a non-Process object")
            break
        visited.add(predecessor.id)
        reverse_chain.append(predecessor)
        current = predecessor

    chain = list(reversed(reverse_chain))
    for index, process in enumerate(chain):
        incoming = _incoming_precedes(db, process.id)
        outgoing = _outgoing_precedes(db, process.id)
        expected_incoming = chain[index - 1].id if index else None
        expected_outgoing = chain[index + 1].id if index + 1 < len(chain) else None
        if any(relation.source_object_id != expected_incoming for relation in incoming):
            blockers.append(f"Process {process.code} has an external preceding dependency")
        if any(relation.target_object_id != expected_outgoing for relation in outgoing):
            blockers.append(f"Process {process.code} has an external following dependency")
    return chain, _unique_messages(blockers)


def _resource_role(target: ResearchObject, requested: str | None) -> str:
    role = normalize_relation_role(requested)
    if target.kind == "sample":
        if role not in {None, "precursor"}:
            raise ValueError("Sample Record resources may only use a Sample as precursor")
        return "precursor"
    if target.kind in RESOURCE_KINDS:
        return role or target.kind
    raise ValueError("Sample Record resources must be Material, Equipment or precursor Sample")


def _resource_properties(
    target: ResearchObject, draft: SampleRecordResourceDraft
) -> dict[str, Any]:
    values = _validate_usage_values(target, draft.usage_values)
    return {"usage_values": values} if values else {}


def _materialize_resource(
    db: Session,
    project_scope_id: uuid.UUID,
    draft: SampleRecordResourceDraft,
) -> ResearchObject:
    if draft.target_object_id is not None:
        target = get_object(db, draft.target_object_id)
        if target is None:
            raise LookupError("Sample Record resource not found")
        if target.kind not in RESOURCE_KINDS and target.kind != "sample":
            raise ValueError("Sample Record resource must be Material, Equipment or Sample")
        return target
    if draft.create_target is None:
        raise ValueError("Sample Record resource has no target")
    return _create_object_in_session(
        db,
        ObjectCreate(
            kind=draft.create_target.kind,
            code=draft.create_target.code,
            title=draft.create_target.title,
            status=draft.create_target.status,
            project_scope_id=project_scope_id,
            type_version_id=draft.create_target.type_version_id,
            properties_jsonb=copy.deepcopy(draft.create_target.properties_jsonb),
            usage_schema_jsonb=copy.deepcopy(draft.create_target.usage_schema_jsonb),
        ),
    )


def _prepare_resource_plan(
    db: Session,
    process: ResearchObject,
    project_scope_id: uuid.UUID,
    draft: SampleRecordResourceDraft,
    existing_relations: list[ObjectRelation] | None = None,
) -> _ResourcePlan:
    target = _materialize_resource(db, project_scope_id, draft)
    _merge_usage_schema(target, draft.usage_schema_additions)
    role = _resource_role(target, draft.role)
    properties = _resource_properties(target, draft)
    candidate = RelationCandidate(
        source=process,
        target=target,
        relation_type="uses",
        role=role,
        properties=properties,
        relation_id=draft.relation_id,
    )
    existing_relation = None
    if draft.relation_id is not None:
        relation_map = {relation.id: relation for relation in existing_relations or []}
        existing_relation = relation_map.get(draft.relation_id)
        if existing_relation is None or existing_relation.source_object_id != process.id:
            raise ValueError("resource relation_id does not belong to this Process")
        if existing_relation.relation_type != "uses":
            raise ValueError("resource relation_id must refer to a uses relation")
    return _ResourcePlan(
        draft=draft,
        target=target,
        role=role,
        properties=properties,
        candidate=candidate,
        existing_relation=existing_relation,
    )


def _resource_output(relation: ObjectRelation) -> dict[str, Any]:
    role = normalize_relation_role(relation.role) or relation.target_object.kind
    return {
        "relation_id": relation.id,
        "object": object_out(relation.target_object),
        "role": role,
        "usage_values": _legacy_and_current_usage_values(relation),
    }


def _record_structure(
    db: Session, sample: ResearchObject
) -> tuple[ResearchObject | None, list[ResearchObject], list[str]]:
    producer, blockers = _sample_producer(db, sample)
    if producer is None:
        return None, [], blockers
    chain, chain_blockers = _reconstruct_chain(db, producer)
    blockers.extend(chain_blockers)
    return producer, chain, _unique_messages(blockers)


def get_sample_record(db: Session, sample_id: uuid.UUID) -> dict[str, Any]:
    sample = get_object(db, sample_id)
    if sample is None or sample.kind != "sample":
        raise LookupError("sample not found")
    _producer, chain, blockers = _record_structure(db, sample)
    data: list[ResearchObject] = []
    data_ids: set[uuid.UUID] = set()
    steps: list[dict[str, Any]] = []
    chain_ids = {process.id for process in chain}
    for ordinal, process in enumerate(chain):
        relations = list_relations(db, process.id)
        resources: list[dict[str, Any]] = []
        for relation in relations:
            if relation.source_object_id != process.id:
                continue
            if relation.relation_type == "uses":
                target = relation.target_object
                if target.kind in RESOURCE_KINDS or target.kind == "sample":
                    role = normalize_relation_role(relation.role)
                    if target.kind == "sample" and role != "precursor":
                        blockers.append(
                            f"Process {process.code} uses Sample {target.code} "
                            "with unsupported role"
                        )
                    else:
                        resources.append(_resource_output(relation))
                elif target.kind == "data":
                    blockers.append(f"Process {process.code} uses Data outside the Sample composer")
            elif relation.relation_type == "produces":
                target = relation.target_object
                if target.kind == "data":
                    if target.id not in data_ids:
                        data.append(target)
                        data_ids.add(target.id)
                elif target.kind == "sample" and target.id != sample.id:
                    blockers.append(
                        f"Process {process.code} produces another Sample not represented "
                        "by this record"
                    )
        steps.append(
            {
                "process": object_out(process),
                "ordinal": ordinal,
                "resources": resources,
            }
        )
    if chain and any(process.id not in chain_ids for process in chain):
        blockers.append("Sample Record chain could not be represented without loss")
    blockers = _unique_messages(blockers)
    projection = {
        "sample": object_out(sample),
        "steps": steps,
        "data": [object_out(item) for item in data],
        "editable": bool(chain) and not blockers,
        "edit_blockers": blockers,
    }
    return {"record_sha256": sha256_json(projection), **projection}


def _step_object_create(
    project_scope_id: uuid.UUID, draft: SampleRecordProcessDraft
) -> ObjectCreate:
    return ObjectCreate(
        kind="process",
        title=draft.title,
        status=draft.status,
        project_scope_id=project_scope_id,
        type_version_id=draft.type_version_id,
        properties_jsonb=copy.deepcopy(draft.properties_jsonb),
        content_document=copy.deepcopy(draft.content_document),
    )


def _relation_for_candidate(candidate: RelationCandidate) -> ObjectRelation:
    return ObjectRelation(
        source_object_id=candidate.source.id,
        target_object_id=candidate.target.id,
        relation_type=candidate.relation_type,
        role=candidate.role,
        properties_jsonb=copy.deepcopy(candidate.properties),
    )


def _validate_and_apply_new_graph(
    db: Session,
    candidates: list[RelationCandidate],
) -> list[ObjectRelation]:
    validate_candidate_relations(db, candidates)
    relations = [_relation_for_candidate(candidate) for candidate in candidates]
    db.add_all(relations)
    db.flush()
    return relations


def create_sample_record(db: Session, payload: SampleRecordCreate) -> dict[str, Any]:
    try:
        project = get_object(db, payload.project_scope_id)
        if project is None or project.kind != "project":
            raise ValueError("project_scope_id must point to a Project object")

        created_resources: list[ResearchObject] = []
        resources_by_id: set[uuid.UUID] = set()
        processes: list[ResearchObject] = []
        process_resource_plans: list[_ResourcePlan] = []
        for step in payload.steps:
            process = _create_object_in_session(
                db, _step_object_create(payload.project_scope_id, step)
            )
            processes.append(process)
            existing_relations: list[ObjectRelation] = []
            for resource in step.resources:
                target_before = resource.target_object_id
                plan = _prepare_resource_plan(
                    db, process, payload.project_scope_id, resource, existing_relations
                )
                process_resource_plans.append(plan)
                if target_before is None and plan.target.id not in resources_by_id:
                    created_resources.append(plan.target)
                    resources_by_id.add(plan.target.id)

        sample = _create_object_in_session(
            db,
            ObjectCreate(
                kind="sample",
                code=payload.sample.code,
                title=payload.sample.title,
                status=payload.sample.status,
                project_scope_id=payload.project_scope_id,
                type_version_id=payload.sample.type_version_id,
                properties_jsonb=copy.deepcopy(payload.sample.properties_jsonb),
                content_document=copy.deepcopy(payload.sample.content_document),
            ),
        )
        candidates = [plan.candidate for plan in process_resource_plans]
        candidates.extend(
            RelationCandidate(
                source=processes[index],
                target=processes[index + 1],
                relation_type="precedes",
                role=None,
                properties={},
            )
            for index in range(len(processes) - 1)
        )
        candidates.append(
            RelationCandidate(
                source=processes[-1],
                target=sample,
                relation_type="produces",
                role=None,
                properties={},
            )
        )
        _validate_and_apply_new_graph(db, candidates)
        revision_targets = [sample, *processes, *created_resources]
        db.flush()
        seen: set[uuid.UUID] = set()
        for obj in revision_targets:
            if obj.id not in seen:
                _create_revision_in_session(db, obj.id, payload.change_note)
                seen.add(obj.id)
        db.commit()
        return get_sample_record(db, sample.id)
    except Exception:
        db.rollback()
        raise


def _prepare_edit_relation_plan(
    db: Session,
    process: ResearchObject,
    project_scope_id: uuid.UUID,
    drafts: list[SampleRecordResourceDraft],
) -> tuple[list[ObjectRelation], list[_ResourcePlan]]:
    current = [
        relation
        for relation in list_relations(db, process.id)
        if relation.source_object_id == process.id and relation.relation_type == "uses"
    ]
    current_by_key: dict[tuple[uuid.UUID, str], list[ObjectRelation]] = {}
    for relation in current:
        current_by_key.setdefault(
            (relation.target_object_id, normalize_relation_role(relation.role) or ""), []
        ).append(relation)
    plans: list[_ResourcePlan] = []
    used_ids: set[uuid.UUID] = set()
    for draft in drafts:
        plan = _prepare_resource_plan(db, process, project_scope_id, draft, current)
        if plan.existing_relation is None and draft.relation_id is None:
            matches = current_by_key.get((plan.target.id, plan.role), [])
            plan.existing_relation = next(
                (relation for relation in matches if relation.id not in used_ids), None
            )
        if plan.existing_relation is not None:
            if plan.existing_relation.id in used_ids:
                raise SemanticConflict("a resource relation cannot appear more than once")
            used_ids.add(plan.existing_relation.id)
        plans.append(plan)
    return current, plans


def _removal_blockers(
    db: Session,
    sample: ResearchObject,
    process: ResearchObject,
    current_chain_ids: set[uuid.UUID],
) -> list[str]:
    blockers: list[str] = []
    for relation in list_relations(db, process.id):
        if relation.relation_type == "precedes":
            other_id = (
                relation.target_object_id
                if relation.source_object_id == process.id
                else relation.source_object_id
            )
            if other_id not in current_chain_ids:
                blockers.append(
                    f"cannot archive {process.code}: it has an external Process ordering dependency"
                )
        elif relation.relation_type == "produces" and relation.target_object_id != sample.id:
            blockers.append(f"cannot archive {process.code}: it produces an external object")
    return blockers


def update_sample_record(
    db: Session, sample_id: uuid.UUID, payload: SampleRecordPut
) -> dict[str, Any]:
    try:
        sample = get_object(db, sample_id)
        if sample is None or sample.kind != "sample":
            raise LookupError("sample not found")
        record = get_sample_record(db, sample.id)
        if not record["editable"]:
            raise SemanticConflict(
                "Sample Record is not safely editable: " + "; ".join(record["edit_blockers"])
            )
        current_chain = [get_object(db, item["process"]["id"]) for item in record["steps"]]
        current_chain = [process for process in current_chain if process is not None]
        current_by_id = {process.id: process for process in current_chain}
        desired_existing_ids = [step.process_id for step in payload.steps if step.process_id]
        if len(set(desired_existing_ids)) != len(desired_existing_ids):
            raise SemanticConflict("a Process cannot appear more than once in a Sample Record")
        if any(process_id not in current_by_id for process_id in desired_existing_ids):
            raise ValueError("Sample Record edit may only reference its current Process chain")

        removed_ids = set(current_by_id) - set(desired_existing_ids)
        removal_blockers = [
            message
            for process_id in removed_ids
            for message in _removal_blockers(
                db, sample, current_by_id[process_id], set(current_by_id)
            )
        ]
        if removal_blockers:
            raise SemanticConflict("; ".join(_unique_messages(removal_blockers)))

        processes: list[ResearchObject] = []
        process_resource_plans: list[
            tuple[ResearchObject, list[ObjectRelation], list[_ResourcePlan]]
        ] = []
        created_resources: list[ResearchObject] = []
        changed_resource_ids: set[uuid.UUID] = set()
        changed_process_ids: set[uuid.UUID] = set()
        for step in payload.steps:
            if step.process_id is None:
                process = _create_object_in_session(
                    db, _step_object_create(sample.project_scope_id, step)
                )
                processes.append(process)
                changed_process_ids.add(process.id)
                current_relations: list[ObjectRelation] = []
                plans: list[_ResourcePlan] = []
                for resource in step.resources:
                    plan = _prepare_resource_plan(
                        db, process, sample.project_scope_id, resource, current_relations
                    )
                    plans.append(plan)
            else:
                process = current_by_id[step.process_id]
                before = (
                    process.title,
                    process.status,
                    process.properties_jsonb,
                    process.content_document,
                )
                _update_object_in_session(
                    db,
                    process,
                    {
                        "title": step.title,
                        "status": step.status,
                        "properties_jsonb": copy.deepcopy(step.properties_jsonb),
                        "content_document": copy.deepcopy(step.content_document),
                    },
                )
                current_relations, plans = _prepare_edit_relation_plan(
                    db, process, sample.project_scope_id, step.resources
                )
                if (
                    before
                    != (
                        process.title,
                        process.status,
                        process.properties_jsonb,
                        process.content_document,
                    )
                    or plans
                ):
                    changed_process_ids.add(process.id)
                processes.append(process)
            for plan in plans:
                if plan.draft.target_object_id is None and plan.target.id not in {
                    resource.id for resource in created_resources
                }:
                    created_resources.append(plan.target)
                if plan.draft.usage_schema_additions:
                    changed_resource_ids.add(plan.target.id)
            process_resource_plans.append((process, current_relations, plans))

        sample_changes = payload.sample.model_dump(exclude_unset=True)
        if sample_changes:
            _update_object_in_session(db, sample, sample_changes)

        current_use_ids = {
            relation.id
            for _process, relations, _plans in process_resource_plans
            for relation in relations
        }
        current_precedes = [
            relation
            for process in current_chain
            for relation in _outgoing_precedes(db, process.id)
            if relation.target_object_id in current_by_id
        ]
        current_precedes_ids = {relation.id for relation in current_precedes}
        current_sample_produces = [
            relation
            for relation in list_relations(db, sample.id)
            if relation.relation_type == "produces" and relation.target_object_id == sample.id
        ]
        exclude_ids = (
            current_use_ids
            | current_precedes_ids
            | {relation.id for relation in current_sample_produces}
        )
        candidates = [
            plan.candidate
            for _process, _relations, plans in process_resource_plans
            for plan in plans
        ]
        candidates.extend(
            RelationCandidate(
                source=processes[index],
                target=processes[index + 1],
                relation_type="precedes",
                role=None,
                properties={},
            )
            for index in range(len(processes) - 1)
        )
        candidates.append(
            RelationCandidate(
                source=processes[-1],
                target=sample,
                relation_type="produces",
                role=None,
                properties={},
            )
        )
        validate_candidate_relations(db, candidates, exclude_ids=exclude_ids)

        retained_use_ids = {
            plan.existing_relation.id
            for _process, _relations, plans in process_resource_plans
            for plan in plans
            if plan.existing_relation is not None
        }
        for _process, relations, _plans in process_resource_plans:
            for relation in relations:
                if relation.id not in retained_use_ids:
                    db.delete(relation)
        for relation in current_precedes:
            db.delete(relation)
        for relation in current_sample_produces:
            db.delete(relation)
        db.flush()

        for _process, _current_relations, plans in process_resource_plans:
            for plan in plans:
                if plan.existing_relation is not None:
                    relation = plan.existing_relation
                    relation.target_object_id = plan.target.id
                    relation.role = plan.role
                    relation.properties_jsonb = copy.deepcopy(plan.properties)
                else:
                    db.add(_relation_for_candidate(plan.candidate))
        for index in range(len(processes) - 1):
            _create_relation_in_session(
                db,
                RelationCreate(
                    source_object_id=processes[index].id,
                    target_object_id=processes[index + 1].id,
                    relation_type="precedes",
                ),
            )
        _create_relation_in_session(
            db,
            RelationCreate(
                source_object_id=processes[-1].id,
                target_object_id=sample.id,
                relation_type="produces",
            ),
        )
        for process_id in removed_ids:
            _update_object_in_session(db, current_by_id[process_id], {"status": "archived"})
        db.flush()

        revision_targets: list[ResearchObject] = [sample]
        revision_targets.extend(
            process for process in processes if process.id in changed_process_ids
        )
        revision_targets.extend(current_by_id[process_id] for process_id in removed_ids)
        revision_targets.extend(created_resources)
        revision_targets.extend(
            plan.target
            for _process, _relations, plans in process_resource_plans
            for plan in plans
            if plan.target.kind in RESOURCE_KINDS and plan.target.id in changed_resource_ids
        )
        seen: set[uuid.UUID] = set()
        for obj in revision_targets:
            if obj.id not in seen:
                _create_revision_in_session(db, obj.id, payload.change_note)
                seen.add(obj.id)
        db.commit()
        return get_sample_record(db, sample.id)
    except Exception:
        db.rollback()
        raise
