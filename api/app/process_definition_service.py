from __future__ import annotations

import copy
import uuid
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models import (
    ProcessDefinitionState,
    ProcessDefinitionVersion,
    ResearchObject,
)
from app.schemas import ObjectCreate, ProcessDefinitionCreate, ProcessDefinitionVersionCreate
from app.services import (
    _create_object_in_session,
    _create_revision_in_session,
    get_object,
    object_out,
)


def _definition(db: Session, definition_id: uuid.UUID) -> ResearchObject:
    item = get_object(db, definition_id)
    if item is None or item.kind != "process_definition":
        raise LookupError("process definition not found")
    return item


def _version_out(version: ProcessDefinitionVersion) -> dict[str, Any]:
    return {
        "id": version.id,
        "process_definition_id": version.process_definition_id,
        "version": version.version,
        "description": version.description,
        "execution_field_definitions": version.execution_field_definitions_jsonb or {},
        "ui_schema": version.ui_schema_jsonb,
        "created_at": version.created_at,
    }


def get_current_version(db: Session, definition_id: uuid.UUID) -> ProcessDefinitionVersion:
    state = db.get(ProcessDefinitionState, definition_id)
    if state is not None:
        version = db.get(ProcessDefinitionVersion, state.current_version_id)
        if version is not None:
            return version
    version = db.scalar(
        select(ProcessDefinitionVersion)
        .where(ProcessDefinitionVersion.process_definition_id == definition_id)
        .order_by(ProcessDefinitionVersion.version.desc())
    )
    if version is None:
        raise LookupError("process definition has no version")
    return version


def _definition_out(db: Session, definition: ResearchObject) -> dict[str, Any]:
    versions = db.scalars(
        select(ProcessDefinitionVersion)
        .where(ProcessDefinitionVersion.process_definition_id == definition.id)
        .order_by(ProcessDefinitionVersion.version)
    ).all()
    current = get_current_version(db, definition.id)
    return {
        "process_definition": object_out(definition),
        "current_version": _version_out(current),
        "versions": [_version_out(version) for version in versions],
    }


def create_process_definition(db: Session, payload: ProcessDefinitionCreate) -> dict[str, Any]:
    try:
        definition = _create_object_in_session(
            db,
            ObjectCreate(
                kind="process_definition",
                code=payload.code,
                title=payload.title,
                status=payload.status,
                project_scope_id=payload.project_scope_id,
                tags=payload.tags,
                properties_jsonb=payload.properties_jsonb,
                content_document=payload.content_document,
            ),
        )
        version = ProcessDefinitionVersion(
            process_definition_id=definition.id,
            version=payload.version or 1,
            description=payload.description,
            execution_field_definitions_jsonb=copy.deepcopy(payload.execution_field_definitions),
            ui_schema_jsonb=copy.deepcopy(payload.ui_schema),
        )
        db.add(version)
        db.flush()
        db.add(
            ProcessDefinitionState(
                process_definition_id=definition.id, current_version_id=version.id
            )
        )
        _create_revision_in_session(db, definition.id, "create process definition")
        db.commit()
        return _definition_out(db, get_object(db, definition.id) or definition)
    except Exception:
        db.rollback()
        raise


def list_process_definitions(
    db: Session, *, project_scope_id: uuid.UUID | None = None, q: str | None = None, limit: int = 50
) -> list[dict[str, Any]]:
    statement = (
        select(ResearchObject)
        .where(ResearchObject.kind == "process_definition")
        .order_by(ResearchObject.updated_at.desc())
        .limit(limit)
    )
    if project_scope_id is not None:
        statement = statement.where(
            (ResearchObject.project_scope_id == project_scope_id)
            | ResearchObject.project_scope_id.is_(None)
        )
    if q:
        statement = statement.where(ResearchObject.title.ilike(f"%{q.strip().lstrip('/')}%"))
    return [_definition_out(db, item) for item in db.scalars(statement).all()]


def get_process_definition(db: Session, definition_id: uuid.UUID) -> dict[str, Any]:
    return _definition_out(db, _definition(db, definition_id))


def create_process_definition_version(
    db: Session, definition_id: uuid.UUID, payload: ProcessDefinitionVersionCreate
) -> dict[str, Any]:
    try:
        definition = _definition(db, definition_id)
        latest = int(
            db.scalar(
                select(func.max(ProcessDefinitionVersion.version)).where(
                    ProcessDefinitionVersion.process_definition_id == definition.id
                )
            )
            or 0
        )
        version = ProcessDefinitionVersion(
            process_definition_id=definition.id,
            version=latest + 1,
            description=payload.description,
            execution_field_definitions_jsonb=copy.deepcopy(payload.execution_field_definitions),
            ui_schema_jsonb=copy.deepcopy(payload.ui_schema),
        )
        db.add(version)
        db.flush()
        state = db.get(ProcessDefinitionState, definition.id)
        if state is None:
            state = ProcessDefinitionState(
                process_definition_id=definition.id, current_version_id=version.id
            )
            db.add(state)
        else:
            state.current_version_id = version.id
        _create_revision_in_session(
            db, definition.id, f"publish process definition v{version.version}"
        )
        db.commit()
        return _version_out(version)
    except Exception:
        db.rollback()
        raise
