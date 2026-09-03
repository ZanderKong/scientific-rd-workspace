from __future__ import annotations

import copy
import uuid
from collections.abc import Callable
from typing import Any

from fastapi.encoders import jsonable_encoder
from sqlalchemy import select
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
        return operation()
    key = key.strip()
    if not key:
        return operation()
    request_hash = sha256_json(request_payload)
    existing = db.scalar(
        select(IdempotencyRecord).where(IdempotencyRecord.idempotency_key == key).with_for_update()
    )
    if existing is not None:
        if existing.request_hash != request_hash:
            raise ValueError("idempotency_conflict")
        raise IdempotencyReplay(copy.deepcopy(existing.response_jsonb), existing.response_status)
    result = operation()
    serialised = jsonable_encoder(result)
    db.add(
        IdempotencyRecord(
            id=uuid.uuid4(),
            idempotency_key=key,
            request_hash=request_hash,
            response_status=response_status,
            response_jsonb=copy.deepcopy(serialised),
        )
    )
    db.commit()
    return serialised
