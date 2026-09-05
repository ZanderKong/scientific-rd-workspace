"""Smoke benchmark the canonical v0.3 graph without adding disposable domain rows."""

from __future__ import annotations

import time

from sqlalchemy import select

from app.db import SessionLocal
from app.golden_fixture import GoldenCl2WorkflowFactory
from app.graph_query_service import graph_query_service
from app.models import ResearchObject


def timed(label: str, operation) -> None:
    started = time.perf_counter()
    result = operation()
    elapsed = (time.perf_counter() - started) * 1000
    size = len(result) if hasattr(result, "__len__") else 1
    print(f"{label:24} {elapsed:8.1f} ms  ({size} result(s))")


def main() -> None:
    fixture_factory = GoldenCl2WorkflowFactory()
    fixture_factory.create()
    fixture = fixture_factory.fixture
    with SessionLocal() as db:
        fixture_factory.verify(db)
        sample = db.scalar(select(ResearchObject).where(ResearchObject.code == fixture.sample_code))
        data = db.scalar(
            select(ResearchObject).where(ResearchObject.code == fixture.response_data_code)
        )
        if sample is None or data is None:
            raise RuntimeError("golden fixture did not create required v0.3 records")
        timed(
            "project scoped search",
            lambda: graph_query_service.search_objects(
                db, project_scope_id=sample.project_scope_id, q="Cl₂", limit=50
            ),
        )
        timed("sample lineage", lambda: graph_query_service.trace_sample_lineage(db, sample.id, 3))
        timed("data record", lambda: graph_query_service.get_data_context(db, data.id))


if __name__ == "__main__":
    main()
