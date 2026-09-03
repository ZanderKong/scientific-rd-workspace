from __future__ import annotations

import copy
import hashlib
import json
import re
import uuid
from typing import Any

from jsonschema import Draft202012Validator
from sqlalchemy import desc, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, selectinload

from app.models import (
    Attachment,
    DataPayload,
    ObjectCodeCounter,
    ObjectRelation,
    ObjectRevision,
    ObjectType,
    ObjectTypeVersion,
    ResearchObject,
)
from app.relation_semantics import (
    RelationCandidate,
    SemanticConflict,
    normalize_relation_role,
    validate_candidate_relations,
    validate_relation_kinds,
    validate_relation_scope,
    validate_scope_mutation,
)
from app.schemas import ObjectCreate, RelationCreate, RelationPatch, UsageSchema

CODE_PREFIX = {
    "material": "MAT",
    "sample": "SMP",
    "equipment": "EQP",
    "process": "PRC",
    "data": "DAT",
    "experiment": "EXP",
    "project": "PRJ",
}
OBJECT_ALIASES = {
    "material": {"material", "reagent", "mat", "原料", "试剂"},
    "sample": {"sample", "smp", "样品"},
    "equipment": {"equipment", "eqp", "设备", "仪器"},
    "process": {"process", "prc", "过程", "操作"},
    "data": {"data", "dat", "数据", "测试结果"},
    "experiment": {"experiment", "exp", "实验"},
    "project": {"project", "prj", "项目", "vault", "scope"},
}


def canonical_json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), default=str)


def sha256_json(value: Any) -> str:
    return hashlib.sha256(canonical_json(value).encode("utf-8")).hexdigest()


def _type_version_query() -> Any:
    return select(ObjectTypeVersion).options(selectinload(ObjectTypeVersion.object_type))


def get_type_version(
    db: Session, kind: str, type_version_id: uuid.UUID | None = None
) -> ObjectTypeVersion:
    if type_version_id is not None:
        version = db.scalar(_type_version_query().where(ObjectTypeVersion.id == type_version_id))
        if version is None:
            raise LookupError("object type version not found")
        if version.object_type.kind != kind:
            raise ValueError("type version kind does not match object kind")
        return version
    version = db.scalar(
        _type_version_query()
        .join(ObjectType)
        .where(
            ObjectType.kind == kind,
            ObjectType.is_default.is_(True),
            ObjectTypeVersion.is_active.is_(True),
        )
        .order_by(ObjectTypeVersion.version.desc())
    )
    if version is None:
        raise LookupError(f"default active object type for {kind} not found")
    return version


def validate_properties(version: ObjectTypeVersion, properties: dict[str, Any]) -> None:
    errors = sorted(
        Draft202012Validator(version.json_schema).iter_errors(properties),
        key=lambda error: list(error.path),
    )
    if errors:
        details = []
        for error in errors[:20]:
            path = ".".join(str(item) for item in error.path) or "$"
            details.append({"path": path, "message": error.message})
        raise ValueError(
            json.dumps({"code": "schema_validation_failed", "errors": details}, ensure_ascii=False)
        )


def validate_object_scope(db: Session, kind: str, project_scope_id: uuid.UUID | None) -> None:
    if kind == "project":
        if project_scope_id is not None:
            raise ValueError("project objects cannot have a project scope")
        return
    if kind not in {"material", "equipment"} and project_scope_id is None:
        raise ValueError(f"{kind} objects require project_scope_id")
    if project_scope_id is not None:
        scope = db.get(ResearchObject, project_scope_id)
        if scope is None or scope.kind != "project":
            raise ValueError("project_scope_id must point to a Project object")


def normalize_usage_schema(kind: str, usage_schema: dict[str, Any] | None) -> dict[str, Any]:
    payload = usage_schema or {}
    if not payload:
        return {}
    if kind not in {"material", "equipment"}:
        raise ValueError("usage_schema_jsonb is only supported for material and equipment objects")
    return UsageSchema.model_validate(payload).model_dump(exclude_none=True)


def _object_query() -> Any:
    return select(ResearchObject).options(
        selectinload(ResearchObject.type_version).selectinload(ObjectTypeVersion.object_type)
    )


def get_object(db: Session, object_id: uuid.UUID) -> ResearchObject | None:
    return db.scalar(_object_query().where(ResearchObject.id == object_id))


def get_object_by_code(db: Session, code: str) -> ResearchObject | None:
    return db.scalar(_object_query().where(ResearchObject.code == code))


def _next_code(db: Session, kind: str) -> str:
    counter = db.scalar(
        select(ObjectCodeCounter).where(ObjectCodeCounter.kind == kind).with_for_update()
    )
    if counter is None:
        counter = ObjectCodeCounter(kind=kind, next_value=1)
        db.add(counter)
        db.flush()
    value = counter.next_value
    counter.next_value = value + 1
    return f"{CODE_PREFIX[kind]}-{value:03d}"


def _advance_counter(db: Session, kind: str, code: str) -> None:
    match = re.fullmatch(rf"{CODE_PREFIX[kind]}-(\d+)", code.upper())
    if not match:
        return
    number = int(match.group(1))
    counter = db.scalar(
        select(ObjectCodeCounter).where(ObjectCodeCounter.kind == kind).with_for_update()
    )
    if counter is None:
        db.add(ObjectCodeCounter(kind=kind, next_value=number + 1))
    elif counter.next_value <= number:
        counter.next_value = number + 1


def _create_object_in_session(db: Session, payload: ObjectCreate) -> ResearchObject:
    version = get_type_version(db, payload.kind, payload.type_version_id)
    validate_object_scope(db, payload.kind, payload.project_scope_id)
    validate_properties(version, payload.properties_jsonb)
    usage_schema = normalize_usage_schema(payload.kind, payload.usage_schema_jsonb)
    code = (payload.code or _next_code(db, payload.kind)).strip()
    if get_object_by_code(db, code) is not None:
        raise SemanticConflict("object code already exists")
    obj = ResearchObject(
        code=code,
        kind=payload.kind,
        title=payload.title.strip(),
        status=payload.status.strip(),
        project_scope_id=payload.project_scope_id,
        type_version_id=version.id,
        properties_jsonb=copy.deepcopy(payload.properties_jsonb),
        usage_schema_jsonb=copy.deepcopy(usage_schema),
        content_document=copy.deepcopy(payload.content_document),
    )
    db.add(obj)
    _advance_counter(db, payload.kind, code)
    db.flush()
    return obj


def create_object(db: Session, payload: ObjectCreate) -> ResearchObject:
    try:
        obj = _create_object_in_session(db, payload)
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise SemanticConflict("object write conflicts with an existing object") from exc
    return get_object(db, obj.id) or obj


def _validate_object_changes(db: Session, obj: ResearchObject, changes: dict[str, Any]) -> None:
    next_scope = changes.get("project_scope_id", obj.project_scope_id)
    next_properties = changes.get("properties_jsonb", obj.properties_jsonb)
    next_usage_schema = changes.get("usage_schema_jsonb", obj.usage_schema_jsonb)
    validate_object_scope(db, obj.kind, next_scope)
    if next_scope != obj.project_scope_id:
        validate_scope_mutation(db, obj, next_scope)
    validate_properties(obj.type_version, next_properties)
    normalize_usage_schema(obj.kind, next_usage_schema)


def _update_object_in_session(
    db: Session, obj: ResearchObject, changes: dict[str, Any]
) -> ResearchObject:
    _validate_object_changes(db, obj, changes)
    for field in (
        "title",
        "status",
        "project_scope_id",
        "properties_jsonb",
        "usage_schema_jsonb",
        "content_document",
    ):
        if field in changes:
            value = changes[field]
            if field in {"title", "status"}:
                value = value.strip()
                if not value:
                    raise ValueError(f"{field} must not be blank")
            setattr(obj, field, copy.deepcopy(value))
    db.flush()
    return obj


def update_object(db: Session, obj: ResearchObject, changes: dict[str, Any]) -> ResearchObject:
    try:
        _update_object_in_session(db, obj, changes)
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise SemanticConflict("object update conflicts with graph integrity") from exc
    return get_object(db, obj.id) or obj


def validate_relation(source: ResearchObject, target: ResearchObject, relation_type: str) -> None:
    """Keep the historical public helper while routing kind/scope checks centrally."""
    validate_relation_kinds(source, target, relation_type)
    validate_relation_scope(source, target)


def _candidate(
    source: ResearchObject,
    target: ResearchObject,
    relation_type: str,
    role: str | None,
    properties: dict[str, Any],
    relation_id: uuid.UUID | None = None,
) -> RelationCandidate:
    return RelationCandidate(
        source=source,
        target=target,
        relation_type=relation_type,
        role=normalize_relation_role(role),
        properties=copy.deepcopy(properties),
        relation_id=relation_id,
    )


def _create_relation_in_session(db: Session, payload: RelationCreate) -> ObjectRelation:
    source = get_object(db, payload.source_object_id)
    target = get_object(db, payload.target_object_id)
    if source is None or target is None:
        raise LookupError("source or target object not found")
    candidate = _candidate(
        source, target, payload.relation_type, payload.role, payload.properties_jsonb
    )
    validate_candidate_relations(db, [candidate])
    relation = ObjectRelation(
        source_object_id=source.id,
        target_object_id=target.id,
        relation_type=payload.relation_type,
        role=candidate.role,
        properties_jsonb=copy.deepcopy(payload.properties_jsonb),
    )
    db.add(relation)
    db.flush()
    return relation


def create_relation(db: Session, payload: RelationCreate) -> ObjectRelation:
    try:
        relation = _create_relation_in_session(db, payload)
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise SemanticConflict("relation conflicts with a graph uniqueness invariant") from exc
    return get_relation(db, relation.id) or relation


def get_relation(db: Session, relation_id: uuid.UUID) -> ObjectRelation | None:
    return db.scalar(
        select(ObjectRelation)
        .where(ObjectRelation.id == relation_id)
        .options(
            selectinload(ObjectRelation.source_object)
            .selectinload(ResearchObject.type_version)
            .selectinload(ObjectTypeVersion.object_type),
            selectinload(ObjectRelation.target_object)
            .selectinload(ResearchObject.type_version)
            .selectinload(ObjectTypeVersion.object_type),
        )
    )


def _update_relation_in_session(
    db: Session, relation: ObjectRelation, payload: RelationPatch
) -> ObjectRelation:
    changes = payload.model_dump(exclude_unset=True)
    role = normalize_relation_role(changes.get("role", relation.role))
    properties = changes.get("properties_jsonb", relation.properties_jsonb) or {}
    candidate = _candidate(
        relation.source_object,
        relation.target_object,
        relation.relation_type,
        role,
        properties,
        relation.id,
    )
    validate_candidate_relations(db, [candidate], exclude_ids={relation.id})
    relation.role = role
    relation.properties_jsonb = copy.deepcopy(properties)
    db.flush()
    return relation


def update_relation(
    db: Session, relation: ObjectRelation, payload: RelationPatch
) -> ObjectRelation:
    try:
        _update_relation_in_session(db, relation, payload)
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise SemanticConflict(
            "relation update conflicts with a graph uniqueness invariant"
        ) from exc
    return get_relation(db, relation.id) or relation


def list_relations(db: Session, object_id: uuid.UUID) -> list[ObjectRelation]:
    return list(
        db.scalars(
            select(ObjectRelation)
            .where(
                (ObjectRelation.source_object_id == object_id)
                | (ObjectRelation.target_object_id == object_id)
            )
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


def _summary(obj: ResearchObject) -> dict[str, Any]:
    return {
        "id": str(obj.id),
        "code": obj.code,
        "kind": obj.kind,
        "title": obj.title,
        "status": obj.status,
        "project_scope_id": str(obj.project_scope_id) if obj.project_scope_id else None,
        "type_key": obj.type_version.object_type.key,
        "type_label_zh": obj.type_version.object_type.label_zh,
        "type_label_en": obj.type_version.object_type.label_en,
    }


def object_out(obj: ResearchObject) -> dict[str, Any]:
    return {
        **_summary(obj),
        "type_version_id": str(obj.type_version_id),
        "type_version": obj.type_version.version,
        "properties_jsonb": obj.properties_jsonb or {},
        "usage_schema_jsonb": obj.usage_schema_jsonb or {},
        "content_document": obj.content_document or [],
        "created_at": obj.created_at.isoformat() if obj.created_at else None,
        "updated_at": obj.updated_at.isoformat() if obj.updated_at else None,
    }


def relation_out(relation: ObjectRelation) -> dict[str, Any]:
    return {
        "id": str(relation.id),
        "source_object_id": str(relation.source_object_id),
        "target_object_id": str(relation.target_object_id),
        "relation_type": relation.relation_type,
        "role": relation.role,
        "properties_jsonb": relation.properties_jsonb or {},
        "source": _summary(relation.source_object),
        "target": _summary(relation.target_object),
        "created_at": relation.created_at.isoformat() if relation.created_at else None,
        "updated_at": relation.updated_at.isoformat() if relation.updated_at else None,
    }


def _revision_snapshot(db: Session, obj: ResearchObject) -> dict[str, Any]:
    relations = list_relations(db, obj.id)
    attachments = db.scalars(select(Attachment).where(Attachment.object_id == obj.id)).all()
    payloads = db.scalars(select(DataPayload).where(DataPayload.data_object_id == obj.id)).all()
    return {
        "schema_version": 1,
        "object": object_out(obj),
        "direct_relations": [relation_out(item) for item in relations],
        "attachments": [
            {
                "id": str(item.id),
                "original_filename": item.original_filename,
                "content_type": item.content_type,
                "size_bytes": item.size_bytes,
                "sha256": item.sha256,
            }
            for item in attachments
        ],
        "data_payloads": [
            {
                "id": str(item.id),
                "payload_kind": item.payload_kind,
                "name": item.name,
                "summary": item.summary_jsonb or {},
                "payload_sha256": item.payload_sha256,
            }
            for item in payloads
        ],
    }


def _create_revision_in_session(
    db: Session, object_id: uuid.UUID, change_note: str | None
) -> ObjectRevision:
    obj = db.scalar(select(ResearchObject).where(ResearchObject.id == object_id).with_for_update())
    if obj is None:
        raise LookupError("object not found")
    obj = get_object(db, object_id) or obj
    latest = db.scalar(
        select(ObjectRevision.revision_number)
        .where(ObjectRevision.object_id == object_id)
        .order_by(desc(ObjectRevision.revision_number))
        .limit(1)
    )
    snapshot = _revision_snapshot(db, obj)
    revision = ObjectRevision(
        object_id=object_id,
        revision_number=(latest or 0) + 1,
        snapshot_jsonb=copy.deepcopy(snapshot),
        snapshot_sha256=sha256_json(snapshot),
        change_note=change_note.strip() if change_note else None,
    )
    db.add(revision)
    db.flush()
    return revision


def create_revision(db: Session, object_id: uuid.UUID, change_note: str | None) -> ObjectRevision:
    revision = _create_revision_in_session(db, object_id, change_note)
    db.commit()
    return revision


def serialize_attachment(attachment: Attachment) -> dict[str, Any]:
    return {
        "id": attachment.id,
        "object_id": attachment.object_id,
        "original_filename": attachment.original_filename,
        "content_type": attachment.content_type,
        "size_bytes": attachment.size_bytes,
        "sha256": attachment.sha256,
        "created_at": attachment.created_at,
    }
