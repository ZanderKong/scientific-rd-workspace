from __future__ import annotations

import logging
import uuid

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile, status
from fastapi.responses import FileResponse
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.db import get_db
from app.models import Attachment, Experiment, MeasurementImport
from app.schemas import AttachmentOut
from app.services import attachment_storage_key
from app.storage import LocalStorageAdapter, sanitise_filename

router = APIRouter(tags=["attachments"])
logger = logging.getLogger(__name__)


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
    references = db.scalars(
        select(MeasurementImport).where(
            MeasurementImport.source_attachment_id == attachment.id,
            MeasurementImport.status == "completed",
        )
    ).all()
    if references:
        raise HTTPException(
            status_code=409,
            detail={
                "code": "attachment_in_use",
                "message": "Attachment is authoritative raw data for a completed measurement.",
                "import_ids": [str(item.id) for item in references],
            },
        )
    storage_key = attachment.storage_key
    try:
        db.delete(attachment)
        db.commit()
    except Exception:
        db.rollback()
        raise

    try:
        _storage().delete(storage_key)
    except Exception as exc:
        logger.exception(
            "Attachment metadata %s was deleted, but byte cleanup failed for %s",
            attachment_id,
            storage_key,
        )
        raise HTTPException(
            status_code=500,
            detail=(
                "attachment metadata deleted but byte cleanup failed; server cleanup is required"
            ),
        ) from exc
