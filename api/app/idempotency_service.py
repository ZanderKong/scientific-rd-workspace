from __future__ import annotations

import copy
import uuid
from collections.abc import Callable
from typing import Any

from fastapi.encoders import jsonable_encoder
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.models import IdempotencyRecord
from app.services import sha256_json


class IdempotencyReplay(Exception):
    def __init__(self, response_json: dict[str, Any], status_code: int) -> None:
        self.response_json = response_json
        self.status_code = status_code
        super().__init__("idempotent replay")


def run_idempotent(
    db: Session,
    key: str | None,
    request_payload: Any,
    operation: Callable[[], dict[str, Any]],
    *,
    response_status: int = 200,
) -> dict[str, Any]:
    if not key:
        result = operation()
        # Router operations are intentionally passed with commit=False when
        # they may be wrapped by an idempotency reservation.  The no-key path
        # has no reservation to commit the outer transaction, so it must still
        # durably commit before returning a successful response.
        db.commit()
        return result
    key = key.strip()
    if not key:
        result = operation()
        db.commit()
        return result
    request_hash = sha256_json(request_payload)
    existing = db.scalar(
        select(IdempotencyRecord).where(IdempotencyRecord.idempotency_key == key).with_for_update()
    )
    if existing is not None:
        if existing.request_hash != request_hash:
            raise ValueError("idempotency_conflict") from None
        if existing.response_status == 102:
            raise ValueError("idempotency_in_progress") from None
        raise IdempotencyReplay(
            copy.deepcopy(existing.response_jsonb), existing.response_status
        ) from None
    record = IdempotencyRecord(
        id=uuid.uuid4(),
        idempotency_key=key,
        request_hash=request_hash,
        response_status=102,
        response_jsonb={},
    )
    try:
        # Keep the idempotency reservation inside a savepoint.  A duplicate
        # key is an expected concurrent outcome and must not roll back the
        # caller's aggregate transaction (which may already hold locks or
        # have staged validation work).
        with db.begin_nested():
            db.add(record)
            db.flush()
    except IntegrityError:
        existing = db.scalar(
            select(IdempotencyRecord)
            .where(IdempotencyRecord.idempotency_key == key)
            .with_for_update()
        )
        if existing is None or existing.request_hash != request_hash:
            raise ValueError("idempotency_conflict") from None
        if existing.response_status == 102:
            raise ValueError("idempotency_in_progress") from None
        raise IdempotencyReplay(
            copy.deepcopy(existing.response_jsonb), existing.response_status
        ) from None
    result = operation()
    serialised = jsonable_encoder(result)
    record.response_status = response_status
    record.response_jsonb = copy.deepcopy(serialised)
    db.commit()
    return serialised
