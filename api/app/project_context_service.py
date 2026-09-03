from __future__ import annotations

import copy
import uuid
from typing import Any

from sqlalchemy import String, and_, func, or_, select
from sqlalchemy.orm import Session

from app.capabilities import capabilities
from app.graph_query_service import graph_query_service
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
        for kind in ("material", "sample", "equipment", "process", "data", "experiment", "project")
    }
    counts.update({kind: count for kind, count in rows})
    counts["project"] = 1
    return counts


def get_project_context(db: Session, project_id: uuid.UUID) -> dict[str, Any]:
    project = _project(db, project_id)
    counts = project_counts(db, project_id)
    recent_samples = graph_query_service.search_objects(
        db, kind="sample", project_scope_id=project_id, include_global=False, limit=5
    )
    recent_experiments = graph_query_service.search_objects(
        db, kind="experiment", project_scope_id=project_id, include_global=False, limit=5
    )
    recent_data = graph_query_service.search_objects(
        db, kind="data", project_scope_id=project_id, include_global=False, limit=5
    )
    context = {
        "project": object_out(project),
        "counts": counts,
        "recent_samples": [object_out(item) for item in recent_samples],
        "recent_experiments": [object_out(item) for item in recent_experiments],
        "recent_data": [object_out(item) for item in recent_data],
        "resource_summary": {
            "materials": {"count": counts["material"]},
            "equipment": {"count": counts["equipment"]},
        },
        "capabilities": capabilities(),
    }
    return {"record_sha256": sha256_json(context), **context}


def create_project_record(db: Session, payload: ProjectRecordCreate) -> dict[str, Any]:
    try:
        project = _create_object_in_session(
            db,
            ObjectCreate(
                kind="project",
                code=payload.project.code,
                title=payload.project.title,
                status=payload.project.status,
                type_version_id=payload.project.type_version_id,
                properties_jsonb=copy.deepcopy(payload.project.properties_jsonb),
                content_document=copy.deepcopy(payload.project.content_document),
            ),
        )
        _create_revision_in_session(db, project.id, payload.change_note)
        db.commit()
        context = get_project_context(db, project.id)
        return {
            "record_sha256": sha256_json({"project": object_out(project), "context": context}),
            "project": object_out(project),
            "context": context,
        }
    except Exception:
        db.rollback()
        raise


def get_project_record(db: Session, project_id: uuid.UUID) -> dict[str, Any]:
    project = _project(db, project_id)
    context = get_project_context(db, project.id)
    projection = {"project": object_out(project), "context": context}
    return {"record_sha256": sha256_json(projection), **projection}


def update_project_record(
    db: Session, project_id: uuid.UUID, payload: ProjectRecordPut
) -> dict[str, Any]:
    try:
        project = _project(db, project_id)
        changes = payload.model_dump(exclude_unset=True, exclude={"change_note"})
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
    items = graph_query_service.search_objects(
        db,
        q=q,
        kinds=kinds,
        project_scope_id=project_id,
        status=status,
        include_global=include_global,
        limit=limit,
        offset=offset,
    )
    # Keep the count query aligned with the deterministic graph search filters.
    scope_filter = ResearchObject.project_scope_id == project_id
    if include_global:
        scope_filter = or_(
            scope_filter,
            and_(
                ResearchObject.kind.in_(["material", "equipment"]),
                ResearchObject.project_scope_id.is_(None),
            ),
        )
    statement = select(func.count(ResearchObject.id)).where(scope_filter)
    if kinds:
        statement = statement.where(ResearchObject.kind.in_(kinds))
    if status:
        statement = statement.where(ResearchObject.status == status)
    if q and q.strip():
        pattern = f"%{q.strip().lstrip('@')}%"
        statement = statement.where(
            or_(
                ResearchObject.code.ilike(pattern),
                ResearchObject.title.ilike(pattern),
                ResearchObject.properties_jsonb.cast(String).ilike(pattern),
            )
        )
    total = int(db.scalar(statement) or 0)
    return {
        "items": [object_out(item) for item in items],
        "total": total,
        "limit": limit,
        "offset": offset,
    }
