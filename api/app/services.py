from __future__ import annotations

import copy
import hashlib
import json
import re
import uuid
from typing import Any

from jsonschema import Draft202012Validator
from sqlalchemy import desc, select
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
from app.schemas import ObjectCreate, RelationCreate, RelationPatch

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
        .where(ObjectType.kind == kind, ObjectTypeVersion.is_active.is_(True))
        .order_by(ObjectTypeVersion.version.desc())
    )
    if version is None:
        raise LookupError(f"active object type for {kind} not found")
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


def _validate_scope(db: Session, kind: str, project_scope_id: uuid.UUID | None) -> None:
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


def create_object(db: Session, payload: ObjectCreate) -> ResearchObject:
    version = get_type_version(db, payload.kind, payload.type_version_id)
    _validate_scope(db, payload.kind, payload.project_scope_id)
    validate_properties(version, payload.properties_jsonb)
    code = payload.code or _next_code(db, payload.kind)
    if get_object_by_code(db, code) is not None:
        raise ValueError("object code already exists")
    obj = ResearchObject(
        code=code,
        kind=payload.kind,
        title=payload.title.strip(),
        status=payload.status.strip(),
        project_scope_id=payload.project_scope_id,
        type_version_id=version.id,
        properties_jsonb=copy.deepcopy(payload.properties_jsonb),
        content_document=copy.deepcopy(payload.content_document),
    )
    db.add(obj)
    _advance_counter(db, payload.kind, code)
    db.commit()
    return get_object(db, obj.id) or obj


def update_object(db: Session, obj: ResearchObject, changes: dict[str, Any]) -> ResearchObject:
    next_scope = changes.get("project_scope_id", obj.project_scope_id)
    next_properties = changes.get("properties_jsonb", obj.properties_jsonb)
    _validate_scope(db, obj.kind, next_scope)
    validate_properties(obj.type_version, next_properties)
    for field in ("title", "status", "project_scope_id", "properties_jsonb", "content_document"):
        if field in changes:
            value = changes[field]
            if field in {"title", "status"}:
                value = value.strip()
                if not value:
                    raise ValueError(f"{field} must not be blank")
            setattr(obj, field, copy.deepcopy(value))
    db.commit()
    return get_object(db, obj.id) or obj


def _scope_id(obj: ResearchObject) -> uuid.UUID | None:
    return obj.id if obj.kind == "project" else obj.project_scope_id


def _validate_relation_scope(source: ResearchObject, target: ResearchObject) -> None:
    source_scope = _scope_id(source)
    target_scope = _scope_id(target)
    if source_scope is not None and target_scope is not None and source_scope != target_scope:
        global_target = target.kind in {"material", "equipment"} and target.project_scope_id is None
        global_source = source.kind in {"material", "equipment"} and source.project_scope_id is None
        if not global_target and not global_source:
            raise ValueError("relation crosses project scopes")


def validate_relation(source: ResearchObject, target: ResearchObject, relation_type: str) -> None:
    valid = {
        "contains": source.kind == "experiment" and target.kind in {"process", "sample", "data"},
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
    _validate_relation_scope(source, target)


def _validate_relation_metadata(role: str | None, properties: dict[str, Any]) -> None:
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


def create_relation(db: Session, payload: RelationCreate) -> ObjectRelation:
    source = get_object(db, payload.source_object_id)
    target = get_object(db, payload.target_object_id)
    if source is None or target is None:
        raise LookupError("source or target object not found")
    validate_relation(source, target, payload.relation_type)
    _validate_relation_metadata(payload.role, payload.properties_jsonb)
    duplicate = db.scalar(
        select(ObjectRelation).where(
            ObjectRelation.source_object_id == source.id,
            ObjectRelation.target_object_id == target.id,
            ObjectRelation.relation_type == payload.relation_type,
            ObjectRelation.role.is_not_distinct_from(payload.role),
        )
    )
    if duplicate is not None:
        raise ValueError("duplicate relation")
    relation = ObjectRelation(
        source_object_id=source.id,
        target_object_id=target.id,
        relation_type=payload.relation_type,
        role=payload.role,
        properties_jsonb=copy.deepcopy(payload.properties_jsonb),
    )
    db.add(relation)
    db.commit()
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


def update_relation(
    db: Session, relation: ObjectRelation, payload: RelationPatch
) -> ObjectRelation:
    changes = payload.model_dump(exclude_unset=True)
    role = changes.get("role", relation.role)
    properties = changes.get("properties_jsonb", relation.properties_jsonb)
    _validate_relation_metadata(role, properties)
    duplicate = db.scalar(
        select(ObjectRelation).where(
            ObjectRelation.id != relation.id,
            ObjectRelation.source_object_id == relation.source_object_id,
            ObjectRelation.target_object_id == relation.target_object_id,
            ObjectRelation.relation_type == relation.relation_type,
            ObjectRelation.role.is_not_distinct_from(role),
        )
    )
    if duplicate is not None:
        raise ValueError("duplicate relation")
    relation.role = role.strip() if isinstance(role, str) else role
    relation.properties_jsonb = copy.deepcopy(properties)
    db.commit()
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


def create_revision(db: Session, object_id: uuid.UUID, change_note: str | None) -> ObjectRevision:
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
    db.commit()
    db.refresh(revision)
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
