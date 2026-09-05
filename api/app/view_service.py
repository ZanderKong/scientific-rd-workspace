from __future__ import annotations

import copy
import uuid
from typing import Any

from fastapi.encoders import jsonable_encoder
from sqlalchemy import desc, select
from sqlalchemy.orm import Session

from app.models import ObjectRevision, ResearchObject, ViewDataRef, ViewRevision, ViewState
from app.schemas import ObjectCreate, ViewCreate, ViewPut
from app.services import (
    _create_object_in_session,
    _create_revision_in_session,
    _update_object_in_session,
    get_object,
    object_out,
    sha256_json,
)


def _view(db: Session, view_id: uuid.UUID) -> ResearchObject:
    item = get_object(db, view_id)
    if item is None or item.kind != "view":
        raise LookupError("view not found")
    return item


def _state(db: Session, view_id: uuid.UUID) -> ViewState:
    state = db.get(ViewState, view_id)
    if state is None:
        raise LookupError("view state not found")
    return state


def _view_body(db: Session, view: ResearchObject, state: ViewState) -> dict[str, Any]:
    data = [
        get_object(db, item.data_id)
        for item in sorted(state.data_refs, key=lambda ref: (ref.order_index, str(ref.data_id)))
    ]
    return {
        "view": object_out(view),
        "description": state.description,
        "config": state.config_jsonb or {},
        "data": [object_out(item) for item in data if item is not None],
        "current_revision_id": state.current_revision_id,
        "revisions": [
            {
                "id": rev.id,
                "view_id": rev.view_id,
                "revision_number": rev.revision_number,
                "snapshot_jsonb": rev.snapshot_jsonb,
                "snapshot_sha256": rev.snapshot_sha256,
                "change_note": rev.change_note,
                "created_at": rev.created_at,
            }
            for rev in state.revisions
        ],
    }


def get_view(db: Session, view_id: uuid.UUID) -> dict[str, Any]:
    view = _view(db, view_id)
    body = _view_body(db, view, _state(db, view.id))
    return {
        "record_sha256": sha256_json(
            {key: value for key, value in body.items() if key != "revisions"}
        ),
        **body,
    }


def _replace_refs(db: Session, state: ViewState, data_ids: list[uuid.UUID]) -> None:
    if len(data_ids) != len(set(data_ids)):
        raise ValueError("View data sources must be unique")
    db.query(ViewDataRef).filter(ViewDataRef.view_id == state.view_id).delete(
        synchronize_session=False
    )
    for index, data_id in enumerate(data_ids):
        data = get_object(db, data_id)
        if data is None or data.kind != "data":
            raise ValueError("View sources must be Data objects")
        if data.project_scope_id not in {
            None,
            state.view.project_scope_id if hasattr(state, "view") else None,
        }:
            view = get_object(db, state.view_id)
            if view and data.project_scope_id != view.project_scope_id:
                raise ValueError("View source crosses project scope")
        latest = db.scalar(
            select(ObjectRevision.id)
            .where(ObjectRevision.object_id == data.id)
            .order_by(desc(ObjectRevision.revision_number))
            .limit(1)
        )
        db.add(
            ViewDataRef(
                view_id=state.view_id, data_id=data.id, data_revision_id=latest, order_index=index
            )
        )
    db.flush()


def _revision(
    db: Session, view: ResearchObject, state: ViewState, change_note: str | None
) -> ViewRevision:
    latest = (
        db.scalar(
            select(ViewRevision.revision_number)
            .where(ViewRevision.view_id == view.id)
            .order_by(desc(ViewRevision.revision_number))
            .limit(1)
        )
        or 0
    )
    snapshot = jsonable_encoder(
        {
            "view": object_out(view),
            "description": state.description,
            "config": state.config_jsonb or {},
            "data_ids": [
                str(item.data_id)
                for item in sorted(state.data_refs, key=lambda ref: ref.order_index)
            ],
            "data_revision_ids": [
                str(item.data_revision_id) if item.data_revision_id else None
                for item in sorted(state.data_refs, key=lambda ref: ref.order_index)
            ],
        }
    )
    revision = ViewRevision(
        view_id=view.id,
        revision_number=latest + 1,
        snapshot_jsonb=snapshot,
        snapshot_sha256=sha256_json(snapshot),
        change_note=change_note,
    )
    db.add(revision)
    db.flush()
    state.current_revision_id = revision.id
    return revision


def create_view(db: Session, payload: ViewCreate) -> dict[str, Any]:
    try:
        view = _create_object_in_session(
            db,
            ObjectCreate(
                kind="view",
                code=payload.code,
                title=payload.title,
                project_scope_id=payload.project_scope_id,
                properties_jsonb={},
                content_document=[],
            ),
        )
        state = ViewState(
            view_id=view.id,
            description=payload.description,
            config_jsonb=copy.deepcopy(payload.config),
        )
        db.add(state)
        db.flush()
        _replace_refs(db, state, payload.data_ids)
        _revision(db, view, state, "create view")
        _create_revision_in_session(db, view.id, "create view")
        db.commit()
        return get_view(db, view.id)
    except Exception:
        db.rollback()
        raise


def update_view(db: Session, view_id: uuid.UUID, payload: ViewPut) -> dict[str, Any]:
    try:
        view = _view(db, view_id)
        state = _state(db, view.id)
        object_changes = {
            key: value
            for key, value in payload.model_dump(exclude_unset=True).items()
            if key in {"title", "status"}
        }
        if object_changes:
            _update_object_in_session(db, view, object_changes)
        if payload.description is not None:
            state.description = payload.description
        if payload.config is not None:
            state.config_jsonb = copy.deepcopy(payload.config)
        if payload.data_ids is not None:
            _replace_refs(db, state, payload.data_ids)
        _revision(db, view, state, payload.change_note)
        _create_revision_in_session(db, view.id, payload.change_note)
        db.commit()
        return get_view(db, view.id)
    except Exception:
        db.rollback()
        raise


def list_view_revisions(db: Session, view_id: uuid.UUID) -> list[dict[str, Any]]:
    state = _state(db, _view(db, view_id).id)
    return [
        {
            "id": rev.id,
            "view_id": rev.view_id,
            "revision_number": rev.revision_number,
            "snapshot_jsonb": rev.snapshot_jsonb,
            "snapshot_sha256": rev.snapshot_sha256,
            "change_note": rev.change_note,
            "created_at": rev.created_at,
        }
        for rev in state.revisions
    ]
