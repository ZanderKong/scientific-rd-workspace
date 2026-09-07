from __future__ import annotations

from collections import defaultdict
from typing import Any

from sqlalchemy import and_, exists, func, or_, select, tuple_
from sqlalchemy.orm import Session, aliased

from app.models import DataDraft, DocumentOccurrence, OccurrenceFieldValue, ResearchObject
from app.schemas import RecordTableFilter, RecordTableQuery
from app.services import object_out


def _field_condition(field: Any, item: RecordTableFilter) -> Any:
    filled = or_(
        field.text_value.is_not(None),
        field.number_value.is_not(None),
        field.boolean_value.is_not(None),
    )
    if item.operator == "is_empty":
        return ~filled
    if item.operator == "is_not_empty":
        return filled
    if item.operator == "contains":
        return field.text_value.ilike(f"%{str(item.value or '')}%")
    if isinstance(item.value, bool):
        value_column = field.boolean_value
    elif isinstance(item.value, (int, float)):
        value_column = field.number_value
    else:
        value_column = field.text_value
    if item.operator == "eq":
        return value_column == item.value
    if item.operator == "gte":
        return value_column >= item.value
    if item.operator == "lte":
        return value_column <= item.value
    raise ValueError("unsupported record table operator")


def _filter_exists(owner_id: Any, target_id: Any, filters: list[RecordTableFilter]) -> Any:
    occurrence = aliased(DocumentOccurrence)
    constraints: list[Any] = [
        occurrence.owner_id == owner_id,
        occurrence.target_id == target_id,
    ]
    for index, item in enumerate(filters):
        field = aliased(OccurrenceFieldValue, name=f"filter_value_{index}")
        field_match = and_(
            field.occurrence_row_id == occurrence.id,
            field.field_key == item.field_key,
        )
        condition = _field_condition(field, item)
        constraints.append(exists(select(1).where(field_match, condition)))
    return exists(select(1).where(*constraints))


def query_record_table(db: Session, query: RecordTableQuery) -> dict[str, Any]:
    # Keep the field catalog independent from the active row filters.  A query
    # that returns zero rows must still expose the fields used by the filter so
    # that the caller can remove or amend the condition.
    catalog_statement = select(ResearchObject).where(
        ResearchObject.project_scope_id == query.project_scope_id
    )
    if query.record_kind == "sample":
        kind_condition = and_(
            ResearchObject.kind == "research_object",
            or_(
                func.jsonb_exists(ResearchObject.tags_jsonb, "样品"),
                func.jsonb_exists(ResearchObject.tags_jsonb, "sample"),
                ResearchObject.authoring_kind == "sample",
            ),
        )
    else:
        kind_condition = and_(
            ResearchObject.kind == "data",
            ~exists(
                select(1).where(
                    DataDraft.data_id == ResearchObject.id,
                    DataDraft.status == "editing",
                )
            ),
        )
    statement = catalog_statement.where(kind_condition)
    if query.record_ids is not None:
        catalog_statement = catalog_statement.where(ResearchObject.id.in_(query.record_ids))
    catalog_statement = catalog_statement.where(kind_condition)
    if query.q and query.q.strip():
        pattern = f"%{query.q.strip()}%"
        statement = statement.where(
            or_(ResearchObject.code.ilike(pattern), ResearchObject.title.ilike(pattern))
        )
    for target_id in query.required_refs:
        statement = statement.where(
            exists(
                select(1).where(
                    DocumentOccurrence.owner_id == ResearchObject.id,
                    DocumentOccurrence.target_id == target_id,
                )
            )
        )
    grouped_filters: dict[Any, list[RecordTableFilter]] = defaultdict(list)
    for item in query.filters:
        grouped_filters[item.target_id].append(item)
    for target_id, items in grouped_filters.items():
        statement = statement.where(_filter_exists(ResearchObject.id, target_id, items))

    total = db.scalar(select(func.count()).select_from(statement.order_by(None).subquery())) or 0
    catalog_ids = catalog_statement.with_only_columns(ResearchObject.id).order_by(None).subquery()
    catalog_rows = db.execute(
        select(
            OccurrenceFieldValue.target_id,
            OccurrenceFieldValue.field_key,
            OccurrenceFieldValue.value_type,
        )
        .join(catalog_ids, catalog_ids.c.id == OccurrenceFieldValue.owner_id)
        .group_by(
            OccurrenceFieldValue.target_id,
            OccurrenceFieldValue.field_key,
            OccurrenceFieldValue.value_type,
        )
        .order_by(OccurrenceFieldValue.target_id, OccurrenceFieldValue.field_key)
    ).all()
    catalog_target_ids = {row.target_id for row in catalog_rows}
    catalog_titles = {
        item.id: item.title
        for item in db.scalars(
            select(ResearchObject).where(ResearchObject.id.in_(catalog_target_ids))
        ).all()
    }
    if query.sort:
        if query.sort.value_type == "number":
            sort_column = OccurrenceFieldValue.number_value
        elif query.sort.value_type == "boolean":
            sort_column = OccurrenceFieldValue.boolean_value
        else:
            sort_column = OccurrenceFieldValue.text_value
        sort_value = (
            select(sort_column)
            .where(
                OccurrenceFieldValue.owner_id == ResearchObject.id,
                OccurrenceFieldValue.target_id == query.sort.target_id,
                OccurrenceFieldValue.field_key == query.sort.field_key,
            )
            .order_by(OccurrenceFieldValue.ordinal)
            .limit(1)
            .scalar_subquery()
        )
        order = sort_value.asc().nulls_last()
        if query.sort.direction == "desc":
            order = sort_value.desc().nulls_last()
        statement = statement.order_by(order, ResearchObject.id)
    else:
        statement = statement.order_by(ResearchObject.created_at.desc(), ResearchObject.id)
    records = list(db.scalars(statement.offset(query.offset).limit(query.limit)).all())
    owner_ids = [item.id for item in records]
    occurrences = (
        list(
            db.scalars(
                select(DocumentOccurrence)
                .where(DocumentOccurrence.owner_id.in_(owner_ids))
                .order_by(DocumentOccurrence.owner_id, DocumentOccurrence.ordinal)
            ).all()
        )
        if owner_ids
        else []
    )
    references: dict[Any, list[Any]] = defaultdict(list)
    for item in occurrences:
        if item.target_id not in references[item.owner_id]:
            references[item.owner_id].append(item.target_id)

    requested = {(item.target_id, item.field_key) for item in query.display_columns}
    values: dict[Any, dict[str, list[dict[str, Any]]]] = defaultdict(lambda: defaultdict(list))
    if owner_ids and requested:
        field_rows = db.scalars(
            select(OccurrenceFieldValue)
            .where(
                OccurrenceFieldValue.owner_id.in_(owner_ids),
                tuple_(OccurrenceFieldValue.target_id, OccurrenceFieldValue.field_key).in_(
                    list(requested)
                ),
            )
            .order_by(OccurrenceFieldValue.owner_id, OccurrenceFieldValue.ordinal)
        ).all()
        for item in field_rows:
            value: str | float | bool | None
            if item.value_type == "number":
                value = item.number_value
            elif item.value_type == "boolean":
                value = item.boolean_value
            else:
                value = item.text_value
            values[item.owner_id][f"{item.target_id}:{item.field_key}"].append(
                {
                    "occurrence_id": item.occurrence_id,
                    "target_id": item.target_id,
                    "field_key": item.field_key,
                    "value_type": item.value_type,
                    "value": value,
                    "unit": item.unit,
                    "ordinal": item.ordinal,
                }
            )
    return {
        "rows": [
            {
                "record": object_out(record),
                "referenced_target_ids": references[record.id],
                "values": dict(values[record.id]),
            }
            for record in records
        ],
        "total": total,
        "limit": query.limit,
        "offset": query.offset,
        "columns": [
            {
                "target_id": row.target_id,
                "field_key": row.field_key,
                "label": f"{catalog_titles.get(row.target_id, 'Ref')} · {row.field_key}",
                "value_type": row.value_type,
            }
            for row in catalog_rows
        ],
    }
