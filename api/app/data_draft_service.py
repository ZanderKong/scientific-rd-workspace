from __future__ import annotations

import copy
import uuid
from typing import Any

from fastapi.encoders import jsonable_encoder
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.data_service import (
    _create_representation_in_session,
    acquisition_subject_ids,
    get_data_record,
    sync_data_subject_assignments,
)
from app.models import Asset, DataDraft, DataRecord, ObjectAssetLink
from app.relation_semantics import SemanticConflict
from app.schemas import (
    DataDraftAttachmentCreate,
    DataDraftBegin,
    DataDraftContent,
    DataDraftFinalize,
    DataDraftUpdate,
    DataRepresentationCreate,
    ObjectCreate,
)
from app.services import (
    _create_object_in_session,
    _create_revision_in_session,
    _update_object_in_session,
    get_object,
    sha256_json,
)


def _draft(db: Session, draft_id: uuid.UUID, *, lock: bool = False) -> DataDraft:
    statement = select(DataDraft).where(DataDraft.id == draft_id)
    if lock:
        statement = statement.with_for_update()
    item = db.scalar(statement)
    if item is None:
        raise LookupError("Data draft not found")
    return item


def _draft_body(item: DataDraft) -> dict[str, Any]:
    body = {
        "id": item.id,
        "data_id": item.data_id,
        "project_scope_id": item.project_scope_id,
        "status": item.status,
        "content": copy.deepcopy(item.draft_jsonb or {}),
        "attachments": copy.deepcopy(item.attachments_jsonb or []),
        "finalized_result": copy.deepcopy(item.finalized_result_jsonb),
        "created_at": item.created_at,
        "updated_at": item.updated_at,
    }
    token_body = {
        "id": body["id"],
        "data_id": body["data_id"],
        "status": body["status"],
        "content": body["content"],
        "attachments": body["attachments"],
    }
    return {**body, "record_sha256": sha256_json(token_body)}


def begin_data_draft(
    db: Session, payload: DataDraftBegin, *, commit: bool = True
) -> dict[str, Any]:
    try:
        content = payload.content
        data = _create_object_in_session(
            db,
            ObjectCreate(
                kind="data",
                title=content.title,
                status="draft",
                project_scope_id=payload.project_scope_id,
                tags=content.tags,
                content_document=[],
            ),
        )
        data.authoring_kind = "data"
        db.flush()
        db.add(
            DataRecord(
                data_object_id=data.id,
                scientific_type=content.scientific_type,
                description=content.description,
            )
        )
        item = DataDraft(
            data_id=data.id,
            project_scope_id=payload.project_scope_id,
            draft_jsonb=content.model_dump(mode="json"),
        )
        db.add(item)
        db.flush()
        if commit:
            db.commit()
        else:
            db.flush()
        return _draft_body(_draft(db, item.id))
    except Exception:
        db.rollback()
        raise


def get_data_draft(db: Session, draft_id: uuid.UUID) -> dict[str, Any]:
    return _draft_body(_draft(db, draft_id))


def update_data_draft(db: Session, draft_id: uuid.UUID, payload: DataDraftUpdate) -> dict[str, Any]:
    try:
        item = _draft(db, draft_id, lock=True)
        current = _draft_body(item)
        if item.status != "editing":
            raise ValueError("Data draft is already finalized")
        if payload.base_record_sha256 != current["record_sha256"]:
            raise ValueError("stale_record")
        item.draft_jsonb = payload.content.model_dump(mode="json")
        db.flush()
        db.commit()
        return _draft_body(_draft(db, item.id))
    except Exception:
        db.rollback()
        raise


def attach_data_draft_asset(
    db: Session, draft_id: uuid.UUID, payload: DataDraftAttachmentCreate
) -> dict[str, Any]:
    try:
        item = _draft(db, draft_id, lock=True)
        if item.status != "editing":
            raise ValueError("Data draft is already finalized")
        asset = db.get(Asset, payload.asset_id)
        link = db.get(ObjectAssetLink, (item.data_id, payload.asset_id))
        if asset is None or link is None:
            raise ValueError("asset must be uploaded to the draft Data identity")
        existing = next(
            (
                entry
                for entry in item.attachments_jsonb or []
                if entry.get("client_attachment_id") == payload.client_attachment_id
            ),
            None,
        )
        if existing is not None:
            if str(existing.get("asset_id")) != str(asset.id):
                raise SemanticConflict(
                    "client_attachment_id is already mapped to another asset",
                    code="idempotency_conflict",
                )
            db.commit()
            return _draft_body(_draft(db, item.id))
        attachments = [
            entry
            for entry in item.attachments_jsonb or []
            if entry.get("client_attachment_id") != payload.client_attachment_id
        ]
        attachments.append(
            {
                "client_attachment_id": payload.client_attachment_id,
                "asset_id": str(asset.id),
                "name": asset.original_filename,
                "mime_type": asset.mime_type,
                "size_bytes": asset.size_bytes,
                "sha256": asset.sha256,
            }
        )
        item.attachments_jsonb = attachments
        db.commit()
        return _draft_body(_draft(db, item.id))
    except Exception:
        db.rollback()
        raise


def remove_data_draft_asset(
    db: Session, draft_id: uuid.UUID, client_attachment_id: str
) -> dict[str, Any]:
    try:
        item = _draft(db, draft_id, lock=True)
        if item.status != "editing":
            raise ValueError("Data draft is already finalized")
        removed = [
            entry
            for entry in item.attachments_jsonb or []
            if entry.get("client_attachment_id") == client_attachment_id
        ]
        item.attachments_jsonb = [
            entry
            for entry in item.attachments_jsonb or []
            if entry.get("client_attachment_id") != client_attachment_id
        ]
        for entry in removed:
            asset_id = uuid.UUID(str(entry["asset_id"]))
            link = db.get(ObjectAssetLink, (item.data_id, asset_id))
            if link is not None:
                db.delete(link)
        db.commit()
        return _draft_body(_draft(db, item.id))
    except Exception:
        db.rollback()
        raise


def finalize_data_draft(
    db: Session,
    draft_id: uuid.UUID,
    payload: DataDraftFinalize,
    *,
    idempotency_key: str,
) -> dict[str, Any]:
    try:
        item = _draft(db, draft_id, lock=True)
        if item.status == "finalized":
            if item.finalize_idempotency_key == idempotency_key and item.finalized_result_jsonb:
                return copy.deepcopy(item.finalized_result_jsonb)
            raise ValueError("Data draft is already finalized")
        current = _draft_body(item)
        if payload.base_record_sha256 != current["record_sha256"]:
            raise ValueError("stale_record")
        content = DataDraftContent.model_validate(item.draft_jsonb)
        data = get_object(db, item.data_id)
        if data is None:
            raise LookupError("draft Data identity not found")
        _update_object_in_session(
            db,
            data,
            {"title": content.title, "status": "active", "tags": content.tags},
            managed_write=True,
        )
        record = db.get(DataRecord, data.id)
        if record is None:
            record = DataRecord(data_object_id=data.id)
            db.add(record)
        record.scientific_type = content.scientific_type
        record.description = content.description

        # A source Sample is an explicit manual subject. Acquisition-document
        # subjects are kept separately and come only from subject bindings in
        # the Data document.
        manual_subjects = list(content.subject_ids)
        if content.source_sample_id is not None:
            source = get_object(db, content.source_sample_id)
            if source is None or source.kind != "research_object":
                raise ValueError("source Sample is invalid")
            manual_subjects.append(source.id)
        sync_data_subject_assignments(
            db,
            data.id,
            subject_ids=manual_subjects,
            source_kind="manual",
            source_ref_id=None,
        )
        acquisition_subjects = acquisition_subject_ids(content.occurrences)
        sync_data_subject_assignments(
            db,
            data.id,
            subject_ids=acquisition_subjects,
            source_kind="acquisition_document",
            source_ref_id=data.id,
        )

        from app.sample_record_service import _sync_record

        _sync_record(db, data, content.document, content.occurrences, "finalize Data record")
        sync_data_subject_assignments(
            db,
            data.id,
            subject_ids=acquisition_subject_ids(content.occurrences),
            source_kind="acquisition_document",
            source_ref_id=data.id,
        )
        representation_by_client_id: dict[str, Any] = {}
        for entry in item.attachments_jsonb or []:
            asset = db.get(Asset, uuid.UUID(str(entry["asset_id"])))
            if asset is None:
                raise ValueError("draft attachment is missing")
            representation = _create_representation_in_session(
                db,
                data,
                DataRepresentationCreate(
                    kind="raw_file",
                    name=entry.get("name") or asset.original_filename,
                    format=asset.original_filename.rsplit(".", 1)[-1].lower()
                    if "." in asset.original_filename
                    else None,
                    asset_id=asset.id,
                    provenance_jsonb={"client_attachment_id": entry["client_attachment_id"]},
                ),
            )
            representation_by_client_id[entry["client_attachment_id"]] = representation
        if content.description:
            _create_representation_in_session(
                db,
                data,
                DataRepresentationCreate(
                    kind="description",
                    name="Observation",
                    format="text/plain",
                    inline_payload_jsonb={"text": content.description},
                ),
            )
        selected_origin = representation_by_client_id.get(content.origin_client_attachment_id)
        if content.origin_client_attachment_id is not None and selected_origin is None:
            raise ValueError("origin_client_attachment_id must reference an attached asset")
        record.origin_representation_id = selected_origin.id if selected_origin else None
        _create_revision_in_session(db, data.id, "finalize Data record")
        item.status = "finalized"
        item.finalize_idempotency_key = idempotency_key
        db.flush()
        result = jsonable_encoder(get_data_record(db, data.id))
        item.finalized_result_jsonb = copy.deepcopy(result)
        db.commit()
        return result
    except Exception:
        db.rollback()
        raise
