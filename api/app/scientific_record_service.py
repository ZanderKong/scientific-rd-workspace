"""Shared locking and ownership primitives for Scientific Records.

Sample and Data keep their domain-specific DTO and projection logic, but they
must enter a record mutation through the same owner lock.  Keeping this small
shared boundary prevents one aggregate from accidentally taking a row lock
without first serializing project graph changes.
"""

from __future__ import annotations

import uuid

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import ResearchObject
from app.relation_semantics import lock_project_graph


def lock_record_owner(
    db: Session, owner_id: uuid.UUID, *, expected_kind: str | None = None
) -> ResearchObject:
    """Read scope, acquire the graph lock, then lock and reread the owner."""
    initial = db.scalar(select(ResearchObject).where(ResearchObject.id == owner_id))
    if initial is None or (expected_kind is not None and initial.kind != expected_kind):
        raise LookupError("scientific record owner not found")
    lock_project_graph(db, initial.project_scope_id)
    owner = db.scalar(select(ResearchObject).where(ResearchObject.id == owner_id).with_for_update())
    if owner is None or (expected_kind is not None and owner.kind != expected_kind):
        raise LookupError("scientific record owner not found")
    return owner
