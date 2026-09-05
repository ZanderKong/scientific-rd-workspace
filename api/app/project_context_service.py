from __future__ import annotations

import uuid
from typing import Any

from sqlalchemy import String, and_, func, or_, select
from sqlalchemy.orm import Session

from app.capabilities import capabilities
from app.models import ResearchObject
from app.schemas import ObjectCreate, ProjectRecordCreate, ProjectRecordPut
from app.services import (
    _create_object_in_session,
    _create_revision_in_session,
    _update_object_in_session,
    get_object,
    object_out,
    sha256_json,
)


def _project(db: Session, project_id: uuid.UUID) -> ResearchObject:
    project = get_object(db, project_id)
    if project is None or project.kind != "project":
        raise LookupError("project not found")
    return project


def project_counts(db: Session, project_id: uuid.UUID) -> dict[str, int]:
    rows = db.execute(
        select(ResearchObject.kind, func.count())
        .where(ResearchObject.project_scope_id == project_id)
        .group_by(ResearchObject.kind)
    )
    counts = {
        kind: 0
        for kind in ("research_object", "process_definition", "data", "experiment", "view", "claim")
    }
    counts.update({kind: count for kind, count in rows})
    counts["project"] = 1
    return counts


def _recent(
    db: Session, project_id: uuid.UUID, kind: str | None = None, limit: int = 5
) -> list[ResearchObject]:
    statement = select(ResearchObject).where(
        ResearchObject.project_scope_id == project_id, ResearchObject.status != "archived"
    )
    if kind:
        statement = statement.where(ResearchObject.kind == kind)
    return list(db.scalars(statement.order_by(ResearchObject.updated_at.desc()).limit(limit)))


def get_project_context(db: Session, project_id: uuid.UUID) -> dict[str, Any]:
    project = _project(db, project_id)
    counts = project_counts(db, project_id)
    body = {
        "project": object_out(project),
        "counts": counts,
        "recent_research_objects": [
            object_out(item) for item in _recent(db, project_id, "research_object")
        ],
        "recent_experiments": [object_out(item) for item in _recent(db, project_id, "experiment")],
        "recent_data": [object_out(item) for item in _recent(db, project_id, "data")],
        "capabilities": capabilities(),
    }
    return {"record_sha256": sha256_json(body), **body}


def create_project_record(db: Session, payload: ProjectRecordCreate) -> dict[str, Any]:
    try:
        project = _create_object_in_session(
            db,
            ObjectCreate(
                kind="project",
                title=payload.project.get("title", "Project"),
                code=payload.project.get("code"),
                status=payload.project.get("status", "active"),
                tags=payload.project.get("tags", []),
                properties_jsonb=payload.project.get("properties_jsonb", {}),
                content_document=payload.project.get("content_document", []),
            ),
        )
        _create_revision_in_session(db, project.id, payload.change_note)
        db.commit()
        return get_project_record(db, project.id)
    except Exception:
        db.rollback()
        raise


def get_project_record(db: Session, project_id: uuid.UUID) -> dict[str, Any]:
    project = _project(db, project_id)
    context = get_project_context(db, project.id)
    body = {"project": object_out(project), "context": context}
    return {"record_sha256": sha256_json(body), **body}


def update_project_record(
    db: Session, project_id: uuid.UUID, payload: ProjectRecordPut
) -> dict[str, Any]:
    try:
        project = _project(db, project_id)
        changes = {
            key: value
            for key, value in payload.model_dump(exclude_unset=True).items()
            if key != "change_note"
        }
        if changes:
            _update_object_in_session(db, project, changes)
        _create_revision_in_session(db, project.id, payload.change_note)
        db.commit()
        return get_project_record(db, project.id)
    except Exception:
        db.rollback()
        raise


def search_project(
    db: Session,
    project_id: uuid.UUID,
    *,
    q: str | None = None,
    kinds: list[str] | None = None,
    status: str | None = None,
    include_global: bool = False,
    limit: int = 50,
    offset: int = 0,
) -> dict[str, Any]:
    _project(db, project_id)
    scope_filter = ResearchObject.project_scope_id == project_id
    if include_global:
        scope_filter = or_(
            scope_filter,
            and_(
                ResearchObject.kind == "research_object", ResearchObject.project_scope_id.is_(None)
            ),
        )
    statement = select(ResearchObject).where(scope_filter)
    count_statement = select(func.count(ResearchObject.id)).where(scope_filter)
    if kinds:
        statement = statement.where(ResearchObject.kind.in_(kinds))
        count_statement = count_statement.where(ResearchObject.kind.in_(kinds))
    if status:
        statement = statement.where(ResearchObject.status == status)
        count_statement = count_statement.where(ResearchObject.status == status)
    if q and q.strip():
        pattern = f"%{q.strip().lstrip('@')}%"
        condition = or_(
            ResearchObject.code.ilike(pattern),
            ResearchObject.title.ilike(pattern),
            ResearchObject.properties_jsonb.cast(String).ilike(pattern),
            ResearchObject.tags_jsonb.cast(String).ilike(pattern),
        )
        statement = statement.where(condition)
        count_statement = count_statement.where(condition)
    items = db.scalars(
        statement.order_by(ResearchObject.updated_at.desc(), ResearchObject.code)
        .offset(offset)
        .limit(limit)
    ).all()
    return {
        "items": [object_out(item) for item in items],
        "total": int(db.scalar(count_statement) or 0),
        "limit": limit,
        "offset": offset,
    }
