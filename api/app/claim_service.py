from __future__ import annotations

import copy
import uuid
from typing import Any

from fastapi.encoders import jsonable_encoder
from sqlalchemy import desc, select
from sqlalchemy.orm import Session

from app.models import (
    ClaimContextReference,
    ClaimEvidence,
    ClaimRecord,
    ClaimRevision,
    ObjectRevision,
    ResearchObject,
    RevisionReference,
    ViewRevision,
)
from app.relation_semantics import SemanticConflict, lock_project_graph
from app.schemas import ClaimCreate, ClaimPrimarySource, ClaimPut, ObjectCreate
from app.services import (
    _create_object_in_session,
    _create_revision_in_session,
    _update_object_in_session,
    get_object,
    object_out,
    sha256_json,
)


def _claim(db: Session, claim_id: uuid.UUID, *, lock: bool = False) -> ResearchObject:
    item = (
        db.scalar(select(ResearchObject).where(ResearchObject.id == claim_id).with_for_update())
        if lock
        else get_object(db, claim_id)
    )
    if item is None or item.kind != "claim":
        raise LookupError("claim not found")
    return item


def _locked_claim(db: Session, claim_id: uuid.UUID) -> ResearchObject:
    item = _claim(db, claim_id)
    lock_project_graph(db, item.project_scope_id)
    return _claim(db, claim_id, lock=True)


def _author_provenance(value: dict[str, Any]) -> dict[str, Any]:
    kind = value.get("kind")
    if kind not in {"human", "literature", "ai", "external"}:
        raise ValueError("Claim author provenance kind is invalid")
    return copy.deepcopy(value)


def _primary_source(
    db: Session,
    project_scope_id: uuid.UUID,
    requested: ClaimPrimarySource,
) -> tuple[ResearchObject, dict[str, Any]]:
    source = get_object(db, requested.object_id)
    if source is None or source.kind != requested.kind:
        raise ValueError("Claim primary source kind does not match its object")
    if source.project_scope_id != project_scope_id:
        raise SemanticConflict(
            "Claim primary source must remain in the same project scope", code="scope_conflict"
        )
    if requested.kind == "view":
        revision = db.get(ViewRevision, requested.revision_id)
        if revision is None or revision.view_id != source.id:
            raise ValueError("Claim View revision does not belong to its source")
        revision_snapshot = revision.snapshot_jsonb
        revision_sha256 = revision.snapshot_sha256
    else:
        revision = db.get(ObjectRevision, requested.revision_id)
        if revision is None or revision.object_id != source.id:
            raise ValueError("Claim source revision does not belong to its source")
        revision_snapshot = revision.snapshot_jsonb
        revision_sha256 = revision.snapshot_sha256
    return source, {
        "kind": requested.kind,
        "object_id": str(source.id),
        "revision_id": str(requested.revision_id),
        "revision_sha256": revision_sha256,
        "source_snapshot": copy.deepcopy(revision_snapshot),
    }


def _capture_context(
    db: Session,
    project_scope_id: uuid.UUID,
    requested: ClaimPrimarySource,
) -> dict[str, Any]:
    source, context = _primary_source(db, project_scope_id, requested)
    source_snapshot = context.get("source_snapshot") or {}
    if requested.kind == "data":
        context["subjects"] = copy.deepcopy(
            (source_snapshot.get("data_record") or {}).get("subject_assignments", [])
        )
    elif requested.kind == "experiment":
        context["members"] = [
            {
                "object_id": item["target_object_id"],
                "revision_id": item.get("target_revision_id"),
                "role": item.get("role"),
                "order_index": (item.get("properties_jsonb") or {}).get("order_index", 0),
            }
            for item in source_snapshot.get("direct_relations", [])
            if item.get("relation_type") == "references"
        ]
    else:
        context["data_refs"] = copy.deepcopy(source_snapshot.get("data_refs", []))
        context["artifact_asset_id"] = source_snapshot.get("artifact_asset_id")
    return context


def _replace_context_references(db: Session, record: ClaimRecord) -> None:
    db.query(ClaimContextReference).filter(
        ClaimContextReference.claim_id == record.claim_id
    ).delete(synchronize_session=False)
    rows: list[ClaimContextReference] = []
    if record.primary_source_id is not None:
        rows.append(
            ClaimContextReference(
                claim_id=record.claim_id,
                reference_kind="primary",
                object_id=record.primary_source_id,
                revision_id=record.primary_source_revision_id,
            )
        )
    context = record.context_snapshot_jsonb or {}
    if record.primary_source_kind == "data":
        items = context.get("subjects", [])
        object_key, revision_key = "subject_id", "subject_revision_id"
    elif record.primary_source_kind == "experiment":
        items = context.get("members", [])
        object_key, revision_key = "object_id", "revision_id"
    else:
        items = context.get("data_refs", [])
        object_key, revision_key = "data_id", "data_revision_id"
    seen = {record.primary_source_id}
    for item in items:
        object_id = uuid.UUID(str(item[object_key]))
        if object_id in seen:
            continue
        seen.add(object_id)
        revision_value = item.get(revision_key)
        rows.append(
            ClaimContextReference(
                claim_id=record.claim_id,
                reference_kind="context",
                object_id=object_id,
                revision_id=uuid.UUID(str(revision_value)) if revision_value else None,
            )
        )
    db.add_all(rows)
    db.flush()


def _validate_evidence(
    db: Session, claim_id: uuid.UUID, items: list[dict[str, Any]]
) -> list[dict[str, Any]]:
    claim = get_object(db, claim_id)
    if claim is not None:
        lock_project_graph(db, claim.project_scope_id)
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
                raise SemanticConflict("Claim cannot cite itself", code="cycle_detected")
            claim = get_object(db, claim_id)
            if claim is None or target.project_scope_id != claim.project_scope_id:
                raise SemanticConflict(
                    "Claim evidence must remain in the same project scope", code="scope_conflict"
                )
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
    adjacency: dict[uuid.UUID, set[uuid.UUID]] = {}
    rows = db.scalars(select(ClaimEvidence).where(ClaimEvidence.evidence_kind == "claim")).all()
    for row in rows:
        if row.evidence_id is not None and row.claim_id != claim_id:
            adjacency.setdefault(row.claim_id, set()).add(row.evidence_id)
    adjacency[claim_id] = {
        item["evidence_id"]
        for item in result
        if item["evidence_kind"] == "claim" and item["evidence_id"] is not None
    }
    visiting: set[uuid.UUID] = set()
    visited: set[uuid.UUID] = set()

    def visit(node: uuid.UUID) -> bool:
        if node in visiting:
            return True
        if node in visited:
            return False
        visiting.add(node)
        if any(visit(child) for child in adjacency.get(node, ())):
            return True
        visiting.remove(node)
        visited.add(node)
        return False

    if any(visit(node) for node in adjacency):
        raise SemanticConflict("Claim evidence cycle is not allowed", code="cycle_detected")
    return result


def _revision_target(
    db: Session,
    kind: str,
    object_id: uuid.UUID,
    revision_id: uuid.UUID | None,
) -> dict[str, uuid.UUID]:
    """Return exactly one typed revision/object target for a protection edge."""
    if revision_id is None:
        return {"target_object_id": object_id}
    if kind == "view":
        revision = db.get(ViewRevision, revision_id)
        if revision is None or revision.view_id != object_id:
            raise ValueError("Claim context View revision does not belong to its source")
        return {"target_view_revision_id": revision.id}
    if kind == "claim":
        revision = db.get(ClaimRevision, revision_id)
        if revision is None or revision.claim_id != object_id:
            raise ValueError("Claim evidence revision does not belong to its source")
        return {"target_claim_revision_id": revision.id}
    revision = db.get(ObjectRevision, revision_id)
    if revision is None or revision.object_id != object_id:
        raise ValueError("Claim context revision does not belong to its source")
    return {"target_object_revision_id": revision.id}


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
            "author_provenance": record.author_provenance_jsonb or {},
            "primary_source": (
                {
                    "kind": record.primary_source_kind,
                    "object_id": str(record.primary_source_id),
                    "revision_id": str(record.primary_source_revision_id),
                }
                if record.primary_source_id is not None
                else None
            ),
            "context_snapshot": record.context_snapshot_jsonb or {},
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
    references: list[RevisionReference] = []
    if record.primary_source_id is not None and record.primary_source_kind is not None:
        references.append(
            RevisionReference(
                source_claim_revision_id=revision.id,
                **_revision_target(
                    db,
                    record.primary_source_kind,
                    record.primary_source_id,
                    record.primary_source_revision_id,
                ),
            )
        )
    context = record.context_snapshot_jsonb or {}
    for item in context.get("subjects", []) + context.get("members", []):
        value = item.get("subject_id") or item.get("object_id")
        if value:
            object_id = uuid.UUID(str(value))
            revision_value = item.get("subject_revision_id") or item.get("revision_id")
            references.append(
                RevisionReference(
                    source_claim_revision_id=revision.id,
                    **_revision_target(
                        db,
                        "object",
                        object_id,
                        uuid.UUID(str(revision_value)) if revision_value else None,
                    ),
                )
            )
    for item in context.get("data_refs", []):
        if item.get("data_id"):
            object_id = uuid.UUID(str(item["data_id"]))
            revision_value = item.get("data_revision_id")
            references.append(
                RevisionReference(
                    source_claim_revision_id=revision.id,
                    **_revision_target(
                        db,
                        "data",
                        object_id,
                        uuid.UUID(str(revision_value)) if revision_value else None,
                    ),
                )
            )
    evidence = db.scalars(
        select(ClaimEvidence).where(ClaimEvidence.claim_id == record.claim_id)
    ).all()
    references.extend(
        RevisionReference(source_claim_revision_id=revision.id, target_object_id=item.evidence_id)
        for item in evidence
        if item.evidence_id is not None
    )
    db.add_all(references)
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
        "author_provenance": record.author_provenance_jsonb or {},
        "primary_source": (
            {
                "kind": record.primary_source_kind,
                "object_id": record.primary_source_id,
                "revision_id": record.primary_source_revision_id,
            }
            if record.primary_source_id is not None
            else None
        ),
        "primary_source_object": object_out(record.primary_source)
        if record.primary_source is not None
        else None,
        "context_snapshot": record.context_snapshot_jsonb or {},
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
    claim_token = {
        key: value
        for key, value in body["claim"].items()
        if key not in {"created_at", "updated_at"}
    }
    return {
        "record_sha256": sha256_json(
            {
                "claim": claim_token,
                "statement": body["statement"],
                "author_provenance": body["author_provenance"],
                "primary_source": body["primary_source"],
                "context_snapshot": body["context_snapshot"],
                "confidence": body["confidence"],
                "metadata_jsonb": body["metadata_jsonb"],
                "evidence": [
                    {key: value for key, value in item.items() if key != "object"}
                    for item in body["evidence"]
                ],
                "current_revision_id": body["current_revision_id"],
            }
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


def create_claim(db: Session, payload: ClaimCreate, *, commit: bool = True) -> dict[str, Any]:
    try:
        statement = payload.statement.strip()
        if not statement:
            raise ValueError("Claim statement is required")
        source = None
        if payload.primary_source is not None:
            source, _ = _primary_source(db, payload.project_scope_id, payload.primary_source)
        claim = _create_object_in_session(
            db,
            ObjectCreate(
                kind="claim",
                code=payload.code,
                title=payload.title or statement[:120],
                project_scope_id=payload.project_scope_id,
                properties_jsonb={},
                content_document=[],
            ),
        )
        record = ClaimRecord(
            claim_id=claim.id,
            statement=statement,
            author_provenance_jsonb=_author_provenance(payload.author_provenance),
            primary_source_kind=payload.primary_source.kind if payload.primary_source else None,
            primary_source_id=source.id if source else None,
            primary_source_revision_id=payload.primary_source.revision_id
            if payload.primary_source
            else None,
            context_snapshot_jsonb=(
                _capture_context(db, payload.project_scope_id, payload.primary_source)
                if payload.primary_source
                else {}
            ),
            confidence=payload.confidence,
            metadata_jsonb=copy.deepcopy(payload.metadata_jsonb),
        )
        db.add(record)
        db.flush()
        _replace_context_references(db, record)
        _replace_evidence(db, record, payload.evidence)
        _revision(db, record, "create claim")
        _create_revision_in_session(db, claim.id, "create claim")
        if commit:
            db.commit()
        else:
            db.flush()
        return get_claim(db, claim.id)
    except Exception:
        db.rollback()
        raise


def update_claim(
    db: Session,
    claim_id: uuid.UUID,
    payload: ClaimPut,
    *,
    expected_record_sha256: str | None = None,
    commit: bool = True,
) -> dict[str, Any]:
    try:
        claim = _locked_claim(db, claim_id)
        record = db.get(ClaimRecord, claim.id)
        if record is None:
            raise LookupError("claim record not found")
        expected = expected_record_sha256 or payload.base_record_sha256
        if not expected:
            raise ValueError("revision_required")
        if expected.strip('"') != get_claim(db, claim.id)["record_sha256"]:
            raise SemanticConflict("The Claim changed after it was loaded", code="stale_record")
        changes = {
            key: value
            for key, value in payload.model_dump(exclude_unset=True).items()
            if key in {"title", "status"}
        }
        if changes:
            _update_object_in_session(db, claim, changes)
        for key in ("statement", "confidence", "metadata_jsonb"):
            if key in payload.model_fields_set:
                setattr(record, key, getattr(payload, key))
        if payload.author_provenance is not None:
            record.author_provenance_jsonb = _author_provenance(payload.author_provenance)
        if payload.primary_source is not None:
            source, _ = _primary_source(db, claim.project_scope_id, payload.primary_source)
            record.primary_source_kind = payload.primary_source.kind
            record.primary_source_id = source.id
            record.primary_source_revision_id = payload.primary_source.revision_id
            record.context_snapshot_jsonb = _capture_context(
                db, claim.project_scope_id, payload.primary_source
            )
        elif payload.refresh_context and record.primary_source_id and record.primary_source_kind:
            record.context_snapshot_jsonb = _capture_context(
                db,
                claim.project_scope_id,
                ClaimPrimarySource(
                    kind=record.primary_source_kind,
                    object_id=record.primary_source_id,
                    revision_id=record.primary_source_revision_id,
                ),
            )
        if payload.primary_source is not None or payload.refresh_context:
            _replace_context_references(db, record)
        if payload.evidence is not None:
            _replace_evidence(db, record, payload.evidence)
        _revision(db, record, payload.change_note)
        _create_revision_in_session(db, claim.id, payload.change_note)
        if commit:
            db.commit()
        else:
            db.flush()
        return get_claim(db, claim.id)
    except Exception:
        db.rollback()
        raise


def list_claims_referencing(db: Session, object_id: uuid.UUID) -> list[dict[str, Any]]:
    claim_ids = db.scalars(
        select(ClaimContextReference.claim_id)
        .where(ClaimContextReference.object_id == object_id)
        .order_by(ClaimContextReference.claim_id)
    ).all()
    return [get_claim(db, claim_id) for claim_id in claim_ids]


def get_claim_revision(db: Session, claim_id: uuid.UUID, revision_number: int) -> ClaimRevision:
    _claim(db, claim_id)
    revision = db.scalar(
        select(ClaimRevision).where(
            ClaimRevision.claim_id == claim_id,
            ClaimRevision.revision_number == revision_number,
        )
    )
    if revision is None:
        raise LookupError("claim revision not found")
    return revision
