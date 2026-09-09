from __future__ import annotations

import copy
import hashlib
import json
import re
import uuid
from typing import Any

from fastapi.encoders import jsonable_encoder
from jsonschema import Draft202012Validator
from sqlalchemy import desc, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, selectinload

from app.models import (
    Asset,
    DataRecord,
    DataRepresentation,
    DataSubjectAssignment,
    DocumentOccurrence,
    ObjectAssetLink,
    ObjectCodeCounter,
    ObjectRelation,
    ObjectRevision,
    ObjectType,
    ObjectTypeVersion,
    ProcessExecution,
    ProcessExecutionRevision,
    ResearchObject,
)
from app.relation_semantics import (
    SemanticConflict,
    lock_project_graph,
    validate_relation_kinds,
    validate_relation_scope,
    validate_scope_mutation,
)
from app.schemas import ObjectCreate, ProcessFieldSchema, RelationCreate, RelationPatch

CODE_PREFIX = {
    "research_object": "ROO",
    "process_definition": "PFD",
    "data": "DAT",
    "experiment": "EXP",
    "project": "PRJ",
    "view": "VEW",
    "claim": "CLM",
}
OBJECT_ALIASES = {
    "research_object": {"research_object", "object", "resource", "样品", "原料", "设备", "物体"},
    "process_definition": {"process_definition", "definition", "process", "过程", "工艺"},
    "data": {"data", "数据", "测试结果"},
    "experiment": {"experiment", "实验"},
    "project": {"project", "项目", "vault", "scope"},
    "view": {"view", "视图"},
    "claim": {"claim", "判断", "结论"},
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


def validate_properties(version: ObjectTypeVersion | None, properties: dict[str, Any]) -> None:
    if version is None:
        return
    errors = sorted(
        Draft202012Validator(version.json_schema).iter_errors(properties),
        key=lambda error: list(error.path),
    )
    if errors:
        details = [
            {"path": ".".join(str(item) for item in error.path) or "$", "message": error.message}
            for error in errors[:20]
        ]
        raise ValueError(
            json.dumps({"code": "schema_validation_failed", "errors": details}, ensure_ascii=False)
        )


def normalize_tags(tags: list[str] | None) -> list[str]:
    result: list[str] = []
    for tag in tags or []:
        value = str(tag).strip()
        if value and value not in result:
            result.append(value)
    return result


def validate_object_scope(db: Session, kind: str, project_scope_id: uuid.UUID | None) -> None:
    if kind == "project":
        if project_scope_id is not None:
            raise ValueError("project objects cannot have a project scope")
        return
    if project_scope_id is None and kind in {"data", "experiment", "view", "claim"}:
        raise ValueError(f"{kind} objects require project_scope_id")
    if project_scope_id is not None:
        scope = db.get(ResearchObject, project_scope_id)
        if scope is None or scope.kind != "project":
            raise ValueError("project_scope_id must point to a Project object")


def normalize_process_fields(value: dict[str, Any] | None) -> dict[str, Any]:
    if not value:
        return {}
    return ProcessFieldSchema.model_validate(value).model_dump(exclude_none=True)


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
    return f"{CODE_PREFIX[kind]}-{value:04d}"


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
    version = (
        get_type_version(db, payload.kind, payload.type_version_id)
        if payload.type_version_id
        else None
    )
    validate_object_scope(db, payload.kind, payload.project_scope_id)
    validate_properties(version, payload.properties_jsonb)
    fields = normalize_process_fields(payload.process_field_definitions)
    code = (payload.code or _next_code(db, payload.kind)).strip()
    if get_object_by_code(db, code) is not None:
        raise SemanticConflict("object code already exists", code="semantic_conflict")
    obj = ResearchObject(
        code=code,
        kind=payload.kind,
        title=payload.title.strip(),
        status=payload.status.strip(),
        project_scope_id=payload.project_scope_id,
        type_version_id=version.id if version else None,
        properties_jsonb=copy.deepcopy(payload.properties_jsonb),
        tags_jsonb=normalize_tags(payload.tags),
        process_field_definitions_jsonb=fields,
        content_document=copy.deepcopy(payload.content_document),
    )
    db.add(obj)
    _advance_counter(db, payload.kind, code)
    db.flush()
    return obj


def create_object(db: Session, payload: ObjectCreate, *, commit: bool = True) -> ResearchObject:
    try:
        obj = _create_object_in_session(db, payload)
        _create_revision_in_session(db, obj.id, "create Research Object")
        if commit:
            db.commit()
        else:
            db.flush()
    except IntegrityError as exc:
        db.rollback()
        raise SemanticConflict("object write conflicts with an existing object") from exc
    return get_object(db, obj.id) or obj


def _validate_object_changes(
    db: Session,
    obj: ResearchObject,
    changes: dict[str, Any],
    *,
    managed_write: bool = False,
) -> None:
    next_scope = changes.get("project_scope_id", obj.project_scope_id)
    next_properties = changes.get("properties_jsonb", obj.properties_jsonb)
    next_fields = changes.get("process_field_definitions", obj.process_field_definitions_jsonb)
    validate_object_scope(db, obj.kind, next_scope)
    if next_scope != obj.project_scope_id:
        validate_scope_mutation(db, obj, next_scope)
    validate_properties(obj.type_version, next_properties)
    normalize_process_fields(next_fields)

    # A scientific record owns its canonical document, occurrence projection and
    # metadata.  The explicit marker is required because an empty record has no
    # occurrence row to discover.
    if obj.authoring_kind is not None and not managed_write:
        raise SemanticConflict(
            "record-managed objects must be changed through the scientific record command",
            code="managed_record",
        )

    # A scientific record owns its canonical document, occurrence projection
    # and metadata.  Discover records created before the explicit marker from
    # their durable projections as a safety net for direct service callers.
    managed_projection = db.scalar(
        select(DocumentOccurrence.id).where(DocumentOccurrence.owner_id == obj.id).limit(1)
    )
    authored_execution = db.scalar(
        select(ProcessExecution.id).where(ProcessExecution.authoring_record_id == obj.id).limit(1)
    )
    if (managed_projection is not None or authored_execution is not None) and not managed_write:
        raise SemanticConflict(
            "record-managed objects must be changed through the scientific record command",
            code="managed_record",
        )


def _update_object_in_session(
    db: Session,
    obj: ResearchObject,
    changes: dict[str, Any],
    *,
    managed_write: bool = False,
) -> ResearchObject:
    _validate_object_changes(db, obj, changes, managed_write=managed_write)
    for field in (
        "title",
        "status",
        "project_scope_id",
        "properties_jsonb",
        "tags",
        "process_field_definitions",
        "content_document",
    ):
        if field in changes:
            value = changes[field]
            if field in {"title", "status"}:
                value = value.strip()
                if not value:
                    raise ValueError(f"{field} must not be blank")
            if field == "tags":
                value = normalize_tags(value)
            if field == "process_field_definitions":
                value = normalize_process_fields(value)
            if field == "project_scope_id" and value == obj.id:
                raise ValueError("an object cannot scope itself")
            setattr(
                obj,
                "tags_jsonb"
                if field == "tags"
                else "process_field_definitions_jsonb"
                if field == "process_field_definitions"
                else field,
                copy.deepcopy(value),
            )
    db.flush()
    return obj


def update_object(
    db: Session,
    obj: ResearchObject,
    changes: dict[str, Any],
    *,
    expected_record_sha256: str | None = None,
    commit: bool = True,
) -> ResearchObject:
    try:
        current = get_object(db, obj.id)
        if current is None:
            raise LookupError("research object not found")
        scopes = {
            scope
            for scope in (
                current.project_scope_id,
                changes.get("project_scope_id", current.project_scope_id),
            )
            if scope is not None
        }
        for scope in sorted(scopes, key=str):
            lock_project_graph(db, scope)
        locked = db.scalar(
            select(ResearchObject).where(ResearchObject.id == obj.id).with_for_update()
        )
        if locked is None:
            raise LookupError("research object not found")
        if expected_record_sha256 is not None:
            current = sha256_json(object_out(locked))
            if expected_record_sha256.strip('"') != current:
                raise SemanticConflict(
                    "The object changed after it was loaded", code="stale_record"
                )
        change_note = changes.get("change_note") or "update Research Object"
        _update_object_in_session(db, locked, changes)
        _create_revision_in_session(db, locked.id, change_note)
        if commit:
            db.commit()
        else:
            db.flush()
    except IntegrityError as exc:
        db.rollback()
        raise SemanticConflict("object update conflicts with graph integrity") from exc
    return get_object(db, obj.id) or locked


def validate_relation(source: ResearchObject, target: ResearchObject, relation_type: str) -> None:
    validate_relation_kinds(source, target, relation_type)
    validate_relation_scope(source, target)


def _create_relation_in_session(db: Session, payload: RelationCreate) -> ObjectRelation:
    if payload.relation_type in {"subject", "derived_from"}:
        raise SemanticConflict(
            "subject and derived_from are system-managed relations", code="system_managed_relation"
        )
    source = get_object(db, payload.source_object_id)
    target = get_object(db, payload.target_object_id)
    if source is None or target is None:
        raise LookupError("source or target object not found")
    validate_relation(source, target, payload.relation_type)
    lock_project_graph(db, source.project_scope_id or target.project_scope_id)
    relation = ObjectRelation(
        source_object_id=source.id,
        target_object_id=target.id,
        relation_type=payload.relation_type,
        role=payload.role.strip() if payload.role else None,
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


def update_relation(
    db: Session, relation: ObjectRelation, payload: RelationPatch
) -> ObjectRelation:
    if relation.relation_type in {"subject", "derived_from"}:
        raise SemanticConflict(
            "system-managed relations cannot be edited", code="system_managed_relation"
        )
    lock_project_graph(
        db,
        relation.source_object.project_scope_id or relation.target_object.project_scope_id,
    )
    changes = payload.model_dump(exclude_unset=True)
    if "role" in changes:
        relation.role = changes["role"].strip() if changes["role"] else None
    if "properties_jsonb" in changes:
        relation.properties_jsonb = copy.deepcopy(changes["properties_jsonb"] or {})
    try:
        db.flush()
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise SemanticConflict(
            "relation update conflicts with a graph uniqueness invariant"
        ) from exc
    return get_relation(db, relation.id) or relation


def delete_relation(db: Session, relation: ObjectRelation) -> None:
    if relation.relation_type in {"subject", "derived_from"}:
        raise SemanticConflict(
            "system-managed relations cannot be deleted", code="system_managed_relation"
        )
    lock_project_graph(
        db,
        relation.source_object.project_scope_id or relation.target_object.project_scope_id,
    )
    db.delete(relation)
    try:
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise SemanticConflict("relation deletion conflicts with graph integrity") from exc


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
    return jsonable_encoder(
        {
            "id": str(obj.id),
            "code": obj.code,
            "kind": obj.kind,
            "title": obj.title,
            "status": obj.status,
            "project_scope_id": str(obj.project_scope_id) if obj.project_scope_id else None,
            "type_key": obj.type_version.object_type.key if obj.type_version else "generic",
            "type_label_zh": obj.type_version.object_type.label_zh if obj.type_version else "",
            "type_label_en": obj.type_version.object_type.label_en if obj.type_version else "",
        }
    )


def object_out(obj: ResearchObject) -> dict[str, Any]:
    result = {
        "record_sha256": None,
        **_summary(obj),
        "type_version_id": str(obj.type_version_id) if obj.type_version_id else None,
        "type_version": obj.type_version.version if obj.type_version else None,
        "tags": obj.tags_jsonb or [],
        "properties_jsonb": obj.properties_jsonb or {},
        "process_field_definitions": obj.process_field_definitions_jsonb or {},
        "content_document": obj.content_document or [],
        "document_format_version": obj.document_format_version,
        "authoring_kind": obj.authoring_kind,
        "created_at": obj.created_at,
        "updated_at": obj.updated_at,
    }
    if obj.semantic_entries_jsonb:
        result["semantic_entries"] = obj.semantic_entries_jsonb
    return result


def relation_out(relation: ObjectRelation) -> dict[str, Any]:
    return {
        "id": relation.id,
        "source_object_id": relation.source_object_id,
        "target_object_id": relation.target_object_id,
        "relation_type": relation.relation_type,
        "role": relation.role,
        "properties_jsonb": relation.properties_jsonb or {},
        "source": _summary(relation.source_object),
        "target": _summary(relation.target_object),
        "created_at": relation.created_at,
        "updated_at": relation.updated_at,
    }


def _revision_snapshot(db: Session, obj: ResearchObject) -> dict[str, Any]:
    relations = list_relations(db, obj.id)
    relation_snapshots = []
    for relation in relations:
        snapshot = relation_out(relation)
        target_revision_id = db.scalar(
            select(ObjectRevision.id)
            .where(ObjectRevision.object_id == relation.target_object_id)
            .order_by(desc(ObjectRevision.revision_number))
            .limit(1)
        )
        snapshot["target_revision_id"] = target_revision_id
        relation_snapshots.append(snapshot)
    links = db.scalars(select(ObjectAssetLink).where(ObjectAssetLink.object_id == obj.id)).all()
    representations = (
        db.scalars(
            select(DataRepresentation).where(DataRepresentation.data_object_id == obj.id)
        ).all()
        if obj.kind == "data"
        else []
    )
    data_record = db.get(DataRecord, obj.id) if obj.kind == "data" else None
    subject_assignments = (
        db.scalars(
            select(DataSubjectAssignment)
            .where(DataSubjectAssignment.data_id == obj.id)
            .order_by(DataSubjectAssignment.created_at, DataSubjectAssignment.id)
        ).all()
        if obj.kind == "data"
        else []
    )
    authored_executions = list(
        db.scalars(
            select(ProcessExecution).where(
                ProcessExecution.authoring_record_id == obj.id,
                ProcessExecution.record_validity == "active",
            )
        ).all()
    )
    execution_manifest = []
    for execution in authored_executions:
        revision_id = db.scalar(
            select(ProcessExecutionRevision.id)
            .where(ProcessExecutionRevision.execution_id == execution.id)
            .order_by(desc(ProcessExecutionRevision.revision_number))
            .limit(1)
        )
        execution_manifest.append(
            {
                "execution_id": str(execution.id),
                "execution_revision_id": str(revision_id) if revision_id else None,
                "occurrence_id": (
                    str(execution.authoring_occurrence_id)
                    if execution.authoring_occurrence_id
                    else None
                ),
            }
        )
    occurrences = list(
        db.scalars(
            select(DocumentOccurrence)
            .where(DocumentOccurrence.owner_id == obj.id)
            .order_by(DocumentOccurrence.ordinal)
        ).all()
    )
    target_ids = {item.target_id for item in occurrences}
    target_titles = (
        {
            item.id: item.title
            for item in db.scalars(
                select(ResearchObject).where(ResearchObject.id.in_(target_ids))
            ).all()
        }
        if target_ids
        else {}
    )
    return jsonable_encoder(
        {
            "schema_version": 2,
            "object": jsonable_encoder(object_out(obj)),
            "direct_relations": relation_snapshots,
            "assets": [
                {"asset_id": str(item.asset_id), "role": item.role, "order_index": item.order_index}
                for item in links
            ],
            "representations": [
                {
                    "id": str(item.id),
                    "kind": item.kind,
                    "name": item.name,
                    "summary": item.summary_jsonb or {},
                    "representation_sha256": item.representation_sha256,
                }
                for item in representations
            ],
            "data_record": {
                "scientific_type": data_record.scientific_type,
                "description": data_record.description,
                "origin_representation_id": (
                    str(data_record.origin_representation_id)
                    if data_record and data_record.origin_representation_id
                    else None
                ),
                "subject_assignments": [
                    {
                        "subject_id": str(item.subject_id),
                        "subject_revision_id": (
                            str(item.subject_revision_id) if item.subject_revision_id else None
                        ),
                        "source_kind": item.source_kind,
                        "source_ref_id": str(item.source_ref_id) if item.source_ref_id else None,
                    }
                    for item in subject_assignments
                ],
            }
            if data_record
            else None,
            "scientific_manifest": {
                "document_format_version": obj.document_format_version,
                "execution_manifest": execution_manifest,
                "occurrences": [
                    {
                        "occurrence_id": str(item.occurrence_id),
                        "kind": item.kind,
                        "target_id": str(item.target_id),
                        "label_snapshot": target_titles.get(item.target_id),
                        "target_revision_id": (
                            str(item.target_revision_id) if item.target_revision_id else None
                        ),
                        "execution_id": str(item.execution_id) if item.execution_id else None,
                        "binding_id": str(item.binding_id) if item.binding_id else None,
                        "ordinal": item.ordinal,
                        "field_definition_snapshot": copy.deepcopy(
                            item.field_definition_snapshot_jsonb or {}
                        ),
                        "values": copy.deepcopy(item.values_jsonb or {}),
                    }
                    for item in occurrences
                ],
            },
        }
    )


def _create_revision_in_session(
    db: Session,
    object_id: uuid.UUID,
    change_note: str | None,
    *,
    change_set_id: uuid.UUID | None = None,
    source_client_name: str | None = None,
    source_client_version: str | None = None,
    source_transport: str | None = None,
) -> ObjectRevision:
    obj = db.scalar(select(ResearchObject).where(ResearchObject.id == object_id).with_for_update())
    if obj is None:
        raise LookupError("object not found")
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
        change_set_id=change_set_id,
        source_client_name=source_client_name,
        source_client_version=source_client_version,
        source_transport=source_transport,
    )
    db.add(revision)
    db.flush()
    return revision


def create_revision(db: Session, object_id: uuid.UUID, change_note: str | None) -> ObjectRevision:
    revision = _create_revision_in_session(db, object_id, change_note)
    db.commit()
    return revision


def serialize_asset(asset: Asset) -> dict[str, Any]:
    return {
        "id": asset.id,
        "storage_backend": asset.storage_backend,
        "bucket": asset.bucket,
        "object_key": asset.object_key,
        "original_filename": asset.original_filename,
        "mime_type": asset.mime_type,
        "size_bytes": asset.size_bytes,
        "sha256": asset.sha256,
        "created_at": asset.created_at,
    }
