from __future__ import annotations

import uuid
from collections import deque

from sqlalchemy import String, cast, or_, select
from sqlalchemy.orm import Session

from app.models import (
    ObjectRelation,
    ObjectType,
    ObjectTypeVersion,
    ProcessExecution,
    ProcessExecutionObjectBinding,
    ResearchObject,
)
from app.process_execution_service import execution_out
from app.services import OBJECT_ALIASES, get_object, object_out

DEFAULT_DEPTH = 3
MAX_DEPTH = 8


def _unique(items: list[ResearchObject]) -> list[ResearchObject]:
    result: list[ResearchObject] = []
    seen: set[uuid.UUID] = set()
    for item in items:
        if item.id not in seen:
            seen.add(item.id)
            result.append(item)
    return result


class GraphQueryService:
    def search_objects(
        self,
        db: Session,
        *,
        q: str | None = None,
        kind: str | None = None,
        kinds: list[str] | None = None,
        project_scope_id: uuid.UUID | None = None,
        type_key: str | None = None,
        type_id: uuid.UUID | None = None,
        status: str | None = None,
        include_global: bool = True,
        limit: int = 50,
        offset: int = 0,
    ) -> list[ResearchObject]:
        statement = (
            select(ResearchObject)
            .outerjoin(ObjectTypeVersion, ResearchObject.type_version_id == ObjectTypeVersion.id)
            .outerjoin(ObjectType, ObjectTypeVersion.object_type_id == ObjectType.id)
        )
        if kind:
            statement = statement.where(ResearchObject.kind == kind)
        if kinds:
            statement = statement.where(ResearchObject.kind.in_(kinds))
        if type_key:
            statement = statement.where(ObjectType.key == type_key)
        if type_id:
            statement = statement.where(ObjectType.id == type_id)
        if project_scope_id is not None:
            if include_global:
                statement = statement.where(
                    (ResearchObject.project_scope_id == project_scope_id)
                    | (
                        (ResearchObject.kind == "research_object")
                        & ResearchObject.project_scope_id.is_(None)
                    )
                )
            else:
                statement = statement.where(ResearchObject.project_scope_id == project_scope_id)
        elif not include_global:
            statement = statement.where(ResearchObject.project_scope_id.is_not(None))
        if status:
            statement = statement.where(ResearchObject.status == status)
        if q and q.strip():
            normalized = q.strip().lstrip("@").casefold()
            alias = next(
                (
                    candidate
                    for candidate, aliases in OBJECT_ALIASES.items()
                    if normalized in aliases
                ),
                None,
            )
            if alias:
                statement = statement.where(ResearchObject.kind == alias)
            else:
                pattern = f"%{q.strip().lstrip('@')}%"
                statement = statement.where(
                    or_(
                        ResearchObject.code.ilike(pattern),
                        ResearchObject.title.ilike(pattern),
                        cast(ResearchObject.properties_jsonb, String).ilike(pattern),
                        cast(ResearchObject.tags_jsonb, String).ilike(pattern),
                    )
                )
        return list(
            db.scalars(
                statement.order_by(ResearchObject.updated_at.desc(), ResearchObject.code)
                .offset(offset)
                .limit(limit)
            )
        )

    def _upstream_ids(self, db: Session, object_id: uuid.UUID) -> list[uuid.UUID]:
        rows = db.scalars(
            select(ProcessExecutionObjectBinding.execution_id).where(
                ProcessExecutionObjectBinding.research_object_id == object_id,
                ProcessExecutionObjectBinding.direction == "output",
                ProcessExecutionObjectBinding.is_active.is_(True),
            )
        ).all()
        result: list[uuid.UUID] = []
        for execution_id in rows:
            result.extend(
                db.scalars(
                    select(ProcessExecutionObjectBinding.research_object_id).where(
                        ProcessExecutionObjectBinding.execution_id == execution_id,
                        ProcessExecutionObjectBinding.direction == "input",
                        ProcessExecutionObjectBinding.is_active.is_(True),
                    )
                ).all()
            )
        return result

    def _downstream_ids(self, db: Session, object_id: uuid.UUID) -> list[uuid.UUID]:
        execution_ids = db.scalars(
            select(ProcessExecutionObjectBinding.execution_id).where(
                ProcessExecutionObjectBinding.research_object_id == object_id,
                ProcessExecutionObjectBinding.direction.in_(["input", "context"]),
                ProcessExecutionObjectBinding.is_active.is_(True),
            )
        ).all()
        result: list[uuid.UUID] = []
        for execution_id in execution_ids:
            result.extend(
                db.scalars(
                    select(ProcessExecutionObjectBinding.research_object_id).where(
                        ProcessExecutionObjectBinding.execution_id == execution_id,
                        ProcessExecutionObjectBinding.direction == "output",
                        ProcessExecutionObjectBinding.is_active.is_(True),
                    )
                ).all()
            )
        return result

    def _bounded_objects(
        self, db: Session, object_id: uuid.UUID, *, direction: str, depth: int
    ) -> list[ResearchObject]:
        queue: deque[tuple[uuid.UUID, int]] = deque([(object_id, 0)])
        visited = {object_id}
        result: list[ResearchObject] = []
        while queue:
            current, distance = queue.popleft()
            if distance >= depth:
                continue
            ids = (
                self._upstream_ids(db, current)
                if direction == "upstream"
                else self._downstream_ids(db, current)
            )
            for next_id in ids:
                if next_id in visited:
                    continue
                visited.add(next_id)
                item = get_object(db, next_id)
                if item:
                    result.append(item)
                    queue.append((next_id, distance + 1))
        return result

    def get_sample_context(
        self, db: Session, sample_id: uuid.UUID, depth: int = DEFAULT_DEPTH
    ) -> dict[str, object]:
        if depth < 0 or depth > MAX_DEPTH:
            raise ValueError(f"depth must be between 0 and {MAX_DEPTH}")
        sample = get_object(db, sample_id)
        if sample is None or sample.kind != "research_object":
            raise LookupError("Research Object not found")
        output_execution_ids = db.scalars(
            select(ProcessExecutionObjectBinding.execution_id).where(
                ProcessExecutionObjectBinding.research_object_id == sample.id,
                ProcessExecutionObjectBinding.direction == "output",
                ProcessExecutionObjectBinding.is_active.is_(True),
            )
        ).all()
        executions = [
            ProcessExecution
            for ProcessExecution in (
                db.get(ProcessExecution, item) for item in output_execution_ids
            )
            if ProcessExecution is not None
        ]
        input_ids: list[uuid.UUID] = []
        for execution_id in output_execution_ids:
            input_ids.extend(
                db.scalars(
                    select(ProcessExecutionObjectBinding.research_object_id).where(
                        ProcessExecutionObjectBinding.execution_id == execution_id,
                        ProcessExecutionObjectBinding.direction == "input",
                        ProcessExecutionObjectBinding.is_active.is_(True),
                    )
                ).all()
            )
        data_ids = db.scalars(
            select(ObjectRelation.source_object_id).where(
                ObjectRelation.target_object_id == sample.id,
                ObjectRelation.relation_type == "subject",
            )
        ).all()
        return {
            "current": object_out(sample),
            "producing_executions": [execution_out(db, item) for item in executions],
            "inputs": [
                object_out(item)
                for item in _unique(
                    [
                        get_object(db, item_id)
                        for item_id in input_ids
                        if get_object(db, item_id) is not None
                    ]
                )
            ],
            "data": [
                object_out(item)
                for item in _unique(
                    [
                        get_object(db, item_id)
                        for item_id in data_ids
                        if get_object(db, item_id) is not None
                    ]
                )
            ],
            "upstream": [
                object_out(item)
                for item in self._bounded_objects(db, sample.id, direction="upstream", depth=depth)
            ],
            "downstream": [
                object_out(item)
                for item in self._bounded_objects(
                    db, sample.id, direction="downstream", depth=depth
                )
            ],
        }

    def get_research_object_context(
        self, db: Session, object_id: uuid.UUID, depth: int = DEFAULT_DEPTH
    ) -> dict[str, object]:
        return self.get_sample_context(db, object_id, depth)

    def get_sample_projection(self, db: Session, object_id: uuid.UUID) -> dict[str, object]:
        from app.sample_record_service import get_sample_record

        return get_sample_record(db, object_id)

    def get_data_context(self, db: Session, data_id: uuid.UUID) -> dict[str, object]:
        from app.data_service import get_data_record

        return get_data_record(db, data_id)

    def get_experiment_context(self, db: Session, experiment_id: uuid.UUID) -> dict[str, object]:
        from app.experiment_record_service import get_experiment_record

        return get_experiment_record(db, experiment_id)

    def trace_object_lineage(
        self, db: Session, object_id: uuid.UUID, depth: int = DEFAULT_DEPTH
    ) -> dict[str, object]:
        if depth < 0 or depth > MAX_DEPTH:
            raise ValueError(f"depth must be between 0 and {MAX_DEPTH}")
        if get_object(db, object_id) is None:
            raise LookupError("object not found")
        return {
            "upstream": [
                object_out(item)
                for item in self._bounded_objects(db, object_id, direction="upstream", depth=depth)
            ],
            "downstream": [
                object_out(item)
                for item in self._bounded_objects(
                    db, object_id, direction="downstream", depth=depth
                )
            ],
            "depth": depth,
        }

    def get_downstream_objects(
        self, db: Session, object_id: uuid.UUID, depth: int = DEFAULT_DEPTH
    ) -> list[ResearchObject]:
        return self._bounded_objects(db, object_id, direction="downstream", depth=depth)

    def trace_sample_lineage(
        self, db: Session, sample_id: uuid.UUID, depth: int = DEFAULT_DEPTH
    ) -> dict[str, object]:
        return self.trace_object_lineage(db, sample_id, depth)


graph_query_service = GraphQueryService()
