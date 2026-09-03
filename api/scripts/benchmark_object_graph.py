"""Benchmark the PostgreSQL object graph in a rolled-back disposable transaction.

Run against a disposable PostgreSQL database after applying the v0.2 migration. The
default workload is intentionally larger than the demo and never commits its rows.
"""

from __future__ import annotations

import argparse
import time
import uuid

from sqlalchemy import insert, select

from app.db import SessionLocal
from app.graph_query_service import graph_query_service
from app.models import ObjectRelation, ObjectType, ObjectTypeVersion, ResearchObject


def timed(label: str, operation) -> None:
    started = time.perf_counter()
    result = operation()
    elapsed = (time.perf_counter() - started) * 1000
    print(f"{label:24} {elapsed:8.1f} ms  ({len(result)} rows)")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--objects", type=int, default=10_000)
    parser.add_argument("--relations", type=int, default=50_000)
    args = parser.parse_args()
    if args.objects < 100 or args.relations < 100:
        parser.error("use at least 100 objects and relations")

    with SessionLocal() as db:
        sample_version = db.scalar(
            select(ObjectTypeVersion)
            .join(ObjectType)
            .where(ObjectType.kind == "sample")
            .order_by(ObjectTypeVersion.version.desc())
        )
        process_version = db.scalar(
            select(ObjectTypeVersion)
            .join(ObjectType)
            .where(ObjectType.kind == "process")
            .order_by(ObjectTypeVersion.version.desc())
        )
        project_version = db.scalar(
            select(ObjectTypeVersion)
            .join(ObjectType)
            .where(ObjectType.kind == "project")
            .order_by(ObjectTypeVersion.version.desc())
        )
        if sample_version is None or process_version is None or project_version is None:
            raise RuntimeError("seed object types before running the benchmark")

        project_id = uuid.uuid4()
        db.execute(
            insert(ResearchObject),
            {
                "id": project_id,
                "code": "BENCH-PRJ",
                "kind": "project",
                "title": "Disposable benchmark project",
                "status": "active",
                "project_scope_id": None,
                "type_version_id": project_version.id,
                "properties_jsonb": {},
                "content_document": [],
            },
        )
        process_count = min(args.objects // 2, args.relations // 4)
        sample_count = args.objects - process_count - 1
        object_rows = []
        process_ids: list[uuid.UUID] = []
        sample_ids: list[uuid.UUID] = []
        for index in range(process_count):
            object_id = uuid.uuid4()
            process_ids.append(object_id)
            object_rows.append(
                {
                    "id": object_id,
                    "code": f"BENCH-PRC-{index:05d}",
                    "kind": "process",
                    "title": f"Benchmark process {index}",
                    "status": "completed",
                    "project_scope_id": project_id,
                    "type_version_id": process_version.id,
                    "properties_jsonb": {},
                    "content_document": [],
                }
            )
        for index in range(sample_count):
            object_id = uuid.uuid4()
            sample_ids.append(object_id)
            object_rows.append(
                {
                    "id": object_id,
                    "code": f"BENCH-SMP-{index:05d}",
                    "kind": "sample",
                    "title": f"Benchmark sample {index}",
                    "status": "active",
                    "project_scope_id": project_id,
                    "type_version_id": sample_version.id,
                    "properties_jsonb": {},
                    "content_document": [],
                }
            )
        db.execute(insert(ResearchObject), object_rows)
        relation_rows = []
        for index, process_id in enumerate(process_ids):
            relation_rows.append(
                {
                    "id": uuid.uuid4(),
                    "source_object_id": process_id,
                    "target_object_id": sample_ids[index % sample_count],
                    "relation_type": "produces",
                    "role": None,
                    "properties_jsonb": {},
                }
            )
            if index + 1 < sample_count:
                relation_rows.append(
                    {
                        "id": uuid.uuid4(),
                        "source_object_id": process_id,
                        "target_object_id": sample_ids[index + 1],
                        "relation_type": "uses",
                        "role": "precursor",
                        "properties_jsonb": {},
                    }
                )
        cursor = 0
        while len(relation_rows) < args.relations:
            source = process_ids[cursor % process_count]
            target = sample_ids[(cursor * 7 + 11) % sample_count]
            relation_rows.append(
                {
                    "id": uuid.uuid4(),
                    "source_object_id": source,
                    "target_object_id": target,
                    "relation_type": "related_to",
                    "role": f"bench-{cursor}",
                    "properties_jsonb": {},
                }
            )
            cursor += 1
        db.execute(insert(ObjectRelation), relation_rows[: args.relations])
        db.flush()

        timed(
            "project scoped list",
            lambda: db.scalars(
                select(ResearchObject)
                .where(
                    ResearchObject.project_scope_id == project_id,
                    ResearchObject.kind == "sample",
                )
                .limit(50)
            ).all(),
        )
        timed(
            "code/title search",
            lambda: db.scalars(
                select(ResearchObject)
                .where(
                    ResearchObject.project_scope_id == project_id,
                    ResearchObject.code.ilike("%BENCH-SMP-09%"),
                )
                .limit(50)
            ).all(),
        )
        sample = sample_ids[min(100, len(sample_ids) - 1)]
        timed(
            "direct sample context",
            lambda: graph_query_service.get_sample_context(db, sample, 0)["direct"][
                "producing_processes"
            ],
        )
        timed(
            "depth-5 lineage",
            lambda: graph_query_service.trace_sample_lineage(db, sample, 5)["downstream"][
                "samples"
            ],
        )
        print("Rows are intentionally rolled back; no benchmark data was committed.")


if __name__ == "__main__":
    main()
