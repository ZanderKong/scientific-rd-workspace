from __future__ import annotations

import copy
import uuid
from typing import Any

from fastapi.encoders import jsonable_encoder
from sqlalchemy import desc, select
from sqlalchemy.orm import Session

from app.models import (
    Asset,
    DataRepresentation,
    ObjectRevision,
    ResearchObject,
    RevisionReference,
    ViewDataRef,
    ViewRevision,
    ViewState,
)
from app.relation_semantics import SemanticConflict, lock_project_graph
from app.schemas import ObjectCreate, ViewCreate, ViewDataRefCreate, ViewPut
from app.services import (
    _create_object_in_session,
    _create_revision_in_session,
    _update_object_in_session,
    get_object,
    object_out,
    sha256_json,
)


def _view(db: Session, view_id: uuid.UUID, *, lock: bool = False) -> ResearchObject:
    item = (
        db.scalar(select(ResearchObject).where(ResearchObject.id == view_id).with_for_update())
        if lock
        else get_object(db, view_id)
    )
    if item is None or item.kind != "view":
        raise LookupError("view not found")
    return item


def _locked_view(db: Session, view_id: uuid.UUID) -> ResearchObject:
    view = _view(db, view_id)
    lock_project_graph(db, view.project_scope_id)
    return _view(db, view_id, lock=True)


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
        "data_refs": [
            {
                "data_id": item.data_id,
                "data_revision_id": item.data_revision_id,
                "representation_ids": item.representation_ids_jsonb or [],
                "order_index": item.order_index,
            }
            for item in sorted(state.data_refs, key=lambda ref: ref.order_index)
        ],
        "artifact_asset_id": state.artifact_asset_id,
        "artifact_sha256": state.artifact_sha256,
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
    view_token = {
        key: value for key, value in body["view"].items() if key not in {"created_at", "updated_at"}
    }
    return {
        "record_sha256": sha256_json(
            {
                "view": view_token,
                "description": body["description"],
                "config": body["config"],
                "data_refs": body["data_refs"],
                "artifact_asset_id": body["artifact_asset_id"],
                "artifact_sha256": body["artifact_sha256"],
                "current_revision_id": body["current_revision_id"],
            }
        ),
        **body,
    }


def _replace_refs(db: Session, state: ViewState, refs: list[ViewDataRefCreate]) -> None:
    data_ids = [item.data_id for item in refs]
    if len(data_ids) != len(set(data_ids)):
        raise ValueError("View data sources must be unique")
    db.query(ViewDataRef).filter(ViewDataRef.view_id == state.view_id).delete(
        synchronize_session=False
    )
    for index, requested in enumerate(refs):
        data = get_object(db, requested.data_id)
        if data is None or data.kind != "data":
            raise ValueError("View sources must be Data objects")
        if data.project_scope_id not in {
            None,
            state.view.project_scope_id if hasattr(state, "view") else None,
        }:
            view = get_object(db, state.view_id)
            if view and data.project_scope_id != view.project_scope_id:
                raise ValueError("View source crosses project scope")
        revision = db.get(ObjectRevision, requested.data_revision_id)
        if revision is None or revision.object_id != data.id:
            raise ValueError("View Data revision does not belong to its Data source")
        pinned_representation_ids = {
            str(item.get("id"))
            for item in (revision.snapshot_jsonb or {}).get("representations", [])
            if item.get("id")
        }
        representation_ids = []
        for representation_id in requested.representation_ids:
            representation = db.get(DataRepresentation, representation_id)
            if representation is None or representation.data_object_id != data.id:
                raise ValueError("View Representation does not belong to its Data source")
            if str(representation.id) not in pinned_representation_ids:
                raise ValueError("View Representation is not present in the selected Data revision")
            representation_ids.append(str(representation.id))
        db.add(
            ViewDataRef(
                view_id=state.view_id,
                data_id=data.id,
                data_revision_id=revision.id,
                representation_ids_jsonb=representation_ids,
                order_index=index,
            )
        )
    db.flush()
    db.expire(state, ["data_refs"])


def _set_artifact(db: Session, state: ViewState, asset_id: uuid.UUID | None) -> None:
    if asset_id is None:
        state.artifact_asset_id = None
        state.artifact_sha256 = None
        return
    asset = db.get(Asset, asset_id)
    if asset is None:
        raise ValueError("View Artifact asset not found")
    if asset.mime_type not in {"image/png", "image/jpeg", "application/pdf", "image/svg+xml"}:
        raise ValueError("View Artifact must be PNG, JPEG, PDF, or SVG")
    state.artifact_asset_id = asset.id
    state.artifact_sha256 = asset.sha256


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
            "data_refs": [
                {
                    "data_id": str(item.data_id),
                    "data_revision_id": str(item.data_revision_id),
                    "representation_ids": item.representation_ids_jsonb or [],
                    "order_index": item.order_index,
                }
                for item in sorted(state.data_refs, key=lambda ref: ref.order_index)
            ],
            "artifact_asset_id": str(state.artifact_asset_id) if state.artifact_asset_id else None,
            "artifact_sha256": state.artifact_sha256,
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
    for data_ref in state.data_refs:
        db.add(
            RevisionReference(
                source_view_revision_id=revision.id,
                target_object_revision_id=data_ref.data_revision_id,
            )
        )
        for representation_id in data_ref.representation_ids_jsonb or []:
            db.add(
                RevisionReference(
                    source_view_revision_id=revision.id,
                    target_representation_id=uuid.UUID(str(representation_id)),
                )
            )
    if state.artifact_asset_id is not None:
        db.add(
            RevisionReference(
                source_view_revision_id=revision.id,
                target_asset_id=state.artifact_asset_id,
            )
        )
    db.flush()
    state.current_revision_id = revision.id
    return revision


def create_view(db: Session, payload: ViewCreate, *, commit: bool = True) -> dict[str, Any]:
    try:
        lock_project_graph(db, payload.project_scope_id)
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
        _replace_refs(db, state, payload.data_refs)
        _set_artifact(db, state, payload.artifact_asset_id)
        _revision(db, view, state, "create view")
        _create_revision_in_session(db, view.id, "create view")
        if commit:
            db.commit()
        else:
            db.flush()
        return get_view(db, view.id)
    except Exception:
        db.rollback()
        raise


def update_view(
    db: Session,
    view_id: uuid.UUID,
    payload: ViewPut,
    *,
    expected_record_sha256: str | None = None,
    commit: bool = True,
) -> dict[str, Any]:
    try:
        view = _locked_view(db, view_id)
        state = _state(db, view.id)
        expected = expected_record_sha256 or payload.base_record_sha256
        if not expected:
            raise ValueError("revision_required")
        current = get_view(db, view.id)
        if expected.strip('"') != current["record_sha256"]:
            raise SemanticConflict("The View changed after it was loaded", code="stale_record")
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
        source_changed = False
        if payload.data_refs is not None:
            _replace_refs(db, state, payload.data_refs)
            source_changed = True
        if "artifact_asset_id" in payload.model_fields_set:
            _set_artifact(db, state, payload.artifact_asset_id)
            source_changed = True
        if source_changed:
            _revision(db, view, state, payload.change_note)
        _create_revision_in_session(db, view.id, payload.change_note)
        if commit:
            db.commit()
        else:
            db.flush()
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


def get_view_revision(db: Session, view_id: uuid.UUID, revision_number: int) -> ViewRevision:
    _view(db, view_id)
    revision = db.scalar(
        select(ViewRevision).where(
            ViewRevision.view_id == view_id,
            ViewRevision.revision_number == revision_number,
        )
    )
    if revision is None:
        raise LookupError("view revision not found")
    return revision
