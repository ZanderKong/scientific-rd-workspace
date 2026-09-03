from __future__ import annotations

import copy
import uuid
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.experiment_comparison_service import (
    _append_sample_dimensions,
    _dimension,
    _dimension_metadata,
)
from app.models import ResearchObject, SampleExecution
from app.sample_record_service import get_sample_record
from app.schemas import SampleExecutionUpdate
from app.services import (
    _create_revision_in_session,
    _update_object_in_session,
    get_object,
    sha256_json,
)


def _sample(db: Session, sample_id: uuid.UUID) -> ResearchObject:
    sample = get_object(db, sample_id)
    if sample is None or sample.kind != "sample":
        raise LookupError("sample not found")
    return sample


def _execution_out(execution: SampleExecution) -> dict[str, Any]:
    return {
        "id": execution.id,
        "sample_id": execution.sample_id,
        "status": execution.status,
        "plan_snapshot_jsonb": execution.plan_snapshot_jsonb,
        "plan_snapshot_sha256": execution.plan_snapshot_sha256,
        "observations": execution.observations_jsonb or [],
        "deviation_notes": execution.deviation_notes_jsonb or [],
        "started_at": execution.started_at,
        "completed_at": execution.completed_at,
        "created_at": execution.created_at,
        "updated_at": execution.updated_at,
    }


def _record_diff(planned: dict[str, Any], as_run: dict[str, Any]) -> list[dict[str, Any]]:
    dimensions_by_key: dict[str, dict[str, dict[str, Any]]] = {}
    _append_sample_dimensions(dimensions_by_key, planned, "planned")
    _append_sample_dimensions(dimensions_by_key, as_run, "as_run")
    result = []
    for key in sorted(dimensions_by_key):
        group, label = _dimension_metadata(key)
        result.append(_dimension(key, label, group, dimensions_by_key[key], ["planned", "as_run"]))
    return result


def _execution_projection(
    db: Session, execution: SampleExecution, *, as_run: dict[str, Any] | None = None
) -> dict[str, Any]:
    current = as_run or get_sample_record(db, execution.sample_id)
    plan = execution.plan_snapshot_jsonb
    return {
        "execution": _execution_out(execution),
        "planned": plan,
        "as_run": current,
        "diff": _record_diff(plan, current),
        "observations": execution.observations_jsonb or [],
        "deviation_notes": execution.deviation_notes_jsonb or [],
    }


def get_execution(db: Session, sample_id: uuid.UUID) -> dict[str, Any]:
    _sample(db, sample_id)
    execution = db.scalar(select(SampleExecution).where(SampleExecution.sample_id == sample_id))
    if execution is None:
        raise LookupError("sample execution not found")
    projection = _execution_projection(db, execution)
    return {"record_sha256": sha256_json(projection), **projection}


def start_execution(db: Session, sample_id: uuid.UUID) -> dict[str, Any]:
    try:
        sample = _sample(db, sample_id)
        existing = db.scalar(
            select(SampleExecution).where(SampleExecution.sample_id == sample.id).with_for_update()
        )
        if existing is not None:
            raise ValueError("sample execution already exists")
        snapshot = get_sample_record(db, sample.id)
        plan_hash = sha256_json(
            {key: value for key, value in snapshot.items() if key != "record_sha256"}
        )
        execution = SampleExecution(
            sample_id=sample.id,
            status="running",
            plan_snapshot_jsonb=copy.deepcopy(snapshot),
            plan_snapshot_sha256=plan_hash,
            observations_jsonb=[],
            deviation_notes_jsonb=[],
        )
        db.add(execution)
        _update_object_in_session(db, sample, {"status": "running"})
        db.flush()
        _create_revision_in_session(db, sample.id, "Execution started")
        db.commit()
        return get_execution(db, sample.id)
    except Exception:
        db.rollback()
        raise


def update_execution(
    db: Session, sample_id: uuid.UUID, payload: SampleExecutionUpdate
) -> dict[str, Any]:
    try:
        _sample(db, sample_id)
        execution = db.scalar(
            select(SampleExecution).where(SampleExecution.sample_id == sample_id).with_for_update()
        )
        if execution is None:
            raise LookupError("sample execution not found")
        if execution.status not in {"running", "planned"}:
            raise ValueError("completed or cancelled execution is immutable")
        if payload.observations is not None:
            execution.observations_jsonb = copy.deepcopy(payload.observations)
        if payload.deviation_notes is not None:
            execution.deviation_notes_jsonb = copy.deepcopy(payload.deviation_notes)
        db.flush()
        db.commit()
        return get_execution(db, sample_id)
    except Exception:
        db.rollback()
        raise


def finish_execution(db: Session, sample_id: uuid.UUID, *, cancelled: bool) -> dict[str, Any]:
    try:
        sample = _sample(db, sample_id)
        execution = db.scalar(
            select(SampleExecution).where(SampleExecution.sample_id == sample_id).with_for_update()
        )
        if execution is None:
            raise LookupError("sample execution not found")
        if execution.status in {"completed", "cancelled"}:
            raise ValueError("sample execution is already closed")
        execution.status = "cancelled" if cancelled else "completed"
        execution.completed_at = datetime.now(UTC)
        _update_object_in_session(db, sample, {"status": "cancelled" if cancelled else "completed"})
        db.flush()
        _create_revision_in_session(
            db, sample.id, "Execution cancelled" if cancelled else "Execution completed"
        )
        db.commit()
        return get_execution(db, sample.id)
    except Exception:
        db.rollback()
        raise
