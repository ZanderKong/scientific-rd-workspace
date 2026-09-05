from __future__ import annotations

import copy
import uuid
from typing import Any

from fastapi.encoders import jsonable_encoder
from sqlalchemy import desc, select
from sqlalchemy.orm import Session

from app.models import ClaimEvidence, ClaimRecord, ClaimRevision, ResearchObject
from app.schemas import ClaimCreate, ClaimPut, ObjectCreate
from app.services import (
    _create_object_in_session,
    _create_revision_in_session,
    _update_object_in_session,
    get_object,
    object_out,
    sha256_json,
)


def _claim(db: Session, claim_id: uuid.UUID) -> ResearchObject:
    item = get_object(db, claim_id)
    if item is None or item.kind != "claim":
        raise LookupError("claim not found")
    return item


def _validate_evidence(
    db: Session, claim_id: uuid.UUID, items: list[dict[str, Any]]
) -> list[dict[str, Any]]:
    result = []
    for index, item in enumerate(items):
        kind = item.get("evidence_kind")
        if kind not in {"data", "view", "claim", "external"}:
            raise ValueError("invalid claim evidence kind")
        evidence_id = item.get("evidence_id")
        target = get_object(db, uuid.UUID(str(evidence_id))) if evidence_id else None
        if kind == "external":
            if evidence_id is not None or not item.get("external_ref"):
                raise ValueError("external evidence requires external_ref")
        else:
            if target is None or target.kind != kind:
                raise ValueError(f"claim evidence must target a {kind}")
            if target.id == claim_id:
                raise ValueError("Claim cannot cite itself")
        polarity = item.get("polarity", "support")
        if polarity not in {"support", "counter"}:
            raise ValueError("claim evidence polarity must be support or counter")
        result.append(
            {
                "evidence_kind": kind,
                "evidence_id": target.id if target else None,
                "external_ref": item.get("external_ref"),
                "polarity": polarity,
                "note": item.get("note"),
                "order_index": item.get("order_index", index),
            }
        )
    return result


def _revision(db: Session, record: ClaimRecord, change_note: str | None) -> ClaimRevision:
    latest = (
        db.scalar(
            select(ClaimRevision.revision_number)
            .where(ClaimRevision.claim_id == record.claim_id)
            .order_by(desc(ClaimRevision.revision_number))
            .limit(1)
        )
        or 0
    )
    evidence = db.scalars(
        select(ClaimEvidence)
        .where(ClaimEvidence.claim_id == record.claim_id)
        .order_by(ClaimEvidence.order_index)
    ).all()
    snapshot = jsonable_encoder(
        {
            "statement": record.statement,
            "source_type": record.source_type,
            "source_ref": record.source_ref,
            "confidence": record.confidence,
            "metadata_jsonb": record.metadata_jsonb or {},
            "evidence": [
                {
                    "evidence_kind": item.evidence_kind,
                    "evidence_id": str(item.evidence_id) if item.evidence_id else None,
                    "external_ref": item.external_ref,
                    "polarity": item.polarity,
                    "note": item.note,
                    "order_index": item.order_index,
                }
                for item in evidence
            ],
        }
    )
    revision = ClaimRevision(
        claim_id=record.claim_id,
        revision_number=latest + 1,
        snapshot_jsonb=snapshot,
        snapshot_sha256=sha256_json(snapshot),
        change_note=change_note,
    )
    db.add(revision)
    db.flush()
    record.current_revision_id = revision.id
    return revision


def _body(db: Session, claim: ResearchObject, record: ClaimRecord) -> dict[str, Any]:
    evidence = db.scalars(
        select(ClaimEvidence)
        .where(ClaimEvidence.claim_id == claim.id)
        .order_by(ClaimEvidence.order_index)
    ).all()
    evidence_out = []
    for item in evidence:
        target = get_object(db, item.evidence_id) if item.evidence_id else None
        evidence_out.append(
            {
                "id": item.id,
                "evidence_kind": item.evidence_kind,
                "evidence_id": item.evidence_id,
                "external_ref": item.external_ref,
                "polarity": item.polarity,
                "note": item.note,
                "order_index": item.order_index,
                "object": object_out(target) if target else None,
            }
        )
    revisions = db.scalars(
        select(ClaimRevision)
        .where(ClaimRevision.claim_id == claim.id)
        .order_by(ClaimRevision.revision_number)
    ).all()
    return {
        "claim": object_out(claim),
        "statement": record.statement,
        "source_type": record.source_type,
        "source_ref": record.source_ref,
        "confidence": record.confidence,
        "metadata_jsonb": record.metadata_jsonb or {},
        "evidence": evidence_out,
        "revisions": [
            {
                "id": item.id,
                "claim_id": item.claim_id,
                "revision_number": item.revision_number,
                "snapshot_jsonb": item.snapshot_jsonb,
                "snapshot_sha256": item.snapshot_sha256,
                "change_note": item.change_note,
                "created_at": item.created_at,
            }
            for item in revisions
        ],
        "current_revision_id": record.current_revision_id,
    }


def get_claim(db: Session, claim_id: uuid.UUID) -> dict[str, Any]:
    claim = _claim(db, claim_id)
    record = db.get(ClaimRecord, claim.id)
    if record is None:
        raise LookupError("claim record not found")
    body = _body(db, claim, record)
    return {
        "record_sha256": sha256_json(
            {key: value for key, value in body.items() if key != "revisions"}
        ),
        **body,
    }


def _replace_evidence(db: Session, record: ClaimRecord, items: list[dict[str, Any]]) -> None:
    validated = _validate_evidence(db, record.claim_id, items)
    db.query(ClaimEvidence).filter(ClaimEvidence.claim_id == record.claim_id).delete(
        synchronize_session=False
    )
    db.add_all(ClaimEvidence(claim_id=record.claim_id, **item) for item in validated)
    db.flush()


def create_claim(db: Session, payload: ClaimCreate) -> dict[str, Any]:
    try:
        claim = _create_object_in_session(
            db,
            ObjectCreate(
                kind="claim",
                code=payload.code,
                title=payload.title,
                project_scope_id=payload.project_scope_id,
                properties_jsonb={},
                content_document=[],
            ),
        )
        record = ClaimRecord(
            claim_id=claim.id,
            statement=payload.statement.strip(),
            source_type=payload.source_type,
            source_ref=payload.source_ref,
            confidence=payload.confidence,
            metadata_jsonb=copy.deepcopy(payload.metadata_jsonb),
        )
        db.add(record)
        db.flush()
        _replace_evidence(db, record, payload.evidence)
        _revision(db, record, "create claim")
        _create_revision_in_session(db, claim.id, "create claim")
        db.commit()
        return get_claim(db, claim.id)
    except Exception:
        db.rollback()
        raise


def update_claim(db: Session, claim_id: uuid.UUID, payload: ClaimPut) -> dict[str, Any]:
    try:
        claim = _claim(db, claim_id)
        record = db.get(ClaimRecord, claim.id)
        if record is None:
            raise LookupError("claim record not found")
        if (
            payload.base_record_sha256
            and payload.base_record_sha256 != get_claim(db, claim.id)["record_sha256"]
        ):
            raise ValueError("stale_record")
        changes = {
            key: value
            for key, value in payload.model_dump(exclude_unset=True).items()
            if key in {"title", "status"}
        }
        if changes:
            _update_object_in_session(db, claim, changes)
        for key in ("statement", "source_type", "source_ref", "confidence", "metadata_jsonb"):
            if key in payload.model_fields_set:
                setattr(record, key, getattr(payload, key))
        if payload.evidence is not None:
            _replace_evidence(db, record, payload.evidence)
        _revision(db, record, payload.change_note)
        _create_revision_in_session(db, claim.id, payload.change_note)
        db.commit()
        return get_claim(db, claim.id)
    except Exception:
        db.rollback()
        raise
