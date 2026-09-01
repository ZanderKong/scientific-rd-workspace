from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile, status
from fastapi.responses import FileResponse
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.db import get_db
from app.models import Attachment, Experiment
from app.schemas import AttachmentOut
from app.services import attachment_storage_key
from app.storage import LocalStorageAdapter, sanitise_filename

router = APIRouter(tags=["attachments"])


def _storage() -> LocalStorageAdapter:
    return LocalStorageAdapter(get_settings().storage_root)


@router.post(
    "/experiments/{experiment_id}/attachments", response_model=AttachmentOut, status_code=201
)
def upload_attachment(
    experiment_id: uuid.UUID,
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
) -> Attachment:
    experiment = db.get(Experiment, experiment_id)
    if experiment is None:
        raise HTTPException(status_code=404, detail="experiment not found")
    filename = sanitise_filename(file.filename or "attachment")
    attachment_id = uuid.uuid4()
    key = attachment_storage_key(experiment_id, attachment_id, filename)
    adapter = _storage()
    size, digest = adapter.put(key, file.file)
    if size > get_settings().max_upload_bytes:
        adapter.delete(key)
        raise HTTPException(status_code=413, detail="attachment exceeds the 25 MB limit")
    attachment = Attachment(
        id=attachment_id,
        experiment_id=experiment_id,
        original_filename=filename,
        storage_key=key,
        content_type=file.content_type,
        size_bytes=size,
        sha256=digest,
    )
    try:
        db.add(attachment)
        db.commit()
        db.refresh(attachment)
    except Exception:
        db.rollback()
        adapter.delete(key)
        raise
    return attachment


@router.get("/experiments/{experiment_id}/attachments", response_model=list[AttachmentOut])
def list_attachments(experiment_id: uuid.UUID, db: Session = Depends(get_db)) -> list[Attachment]:
    if db.get(Experiment, experiment_id) is None:
        raise HTTPException(status_code=404, detail="experiment not found")
    return list(
        db.scalars(
            select(Attachment)
            .where(Attachment.experiment_id == experiment_id)
            .order_by(Attachment.created_at.desc())
        )
    )


@router.get("/attachments/{attachment_id}/download")
def download_attachment(attachment_id: uuid.UUID, db: Session = Depends(get_db)) -> FileResponse:
    attachment = db.get(Attachment, attachment_id)
    if attachment is None:
        raise HTTPException(status_code=404, detail="attachment not found")
    try:
        path = _storage().open(attachment.storage_key)
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail="attachment bytes not found") from exc
    return FileResponse(
        path,
        media_type=attachment.content_type or "application/octet-stream",
        filename=attachment.original_filename,
    )


@router.delete("/attachments/{attachment_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_attachment(attachment_id: uuid.UUID, db: Session = Depends(get_db)) -> None:
    attachment = db.get(Attachment, attachment_id)
    if attachment is None:
        raise HTTPException(status_code=404, detail="attachment not found")
    _storage().delete(attachment.storage_key)
    db.delete(attachment)
    db.commit()
