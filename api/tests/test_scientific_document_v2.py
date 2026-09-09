import os
import uuid

import pytest
from sqlalchemy import create_engine, select

from app.idempotency_service import run_idempotent
from app.models import IdempotencyRecord
from app.sample_record_service import _normalise_document_v2
from app.schemas import ScientificDocumentV1, ScientificOccurrenceDraft


def _document(occurrence_id: uuid.UUID, child_content: list[dict]) -> ScientificDocumentV1:
    return ScientificDocumentV1(
        schema_version=2,
        blocks=[
            {
                "type": "bulletListItem",
                "content": [{"type": "objectRef", "props": {"occurrenceId": str(occurrence_id)}}],
                "children": [{"type": "bulletListItem", "content": child_content}],
            }
        ],
    )


def _occurrence(occurrence_id: uuid.UUID) -> ScientificOccurrenceDraft:
    return ScientificOccurrenceDraft(
        occurrence_id=occurrence_id,
        kind="object",
        target_id=uuid.uuid4(),
        field_definitions={},
        values={},
    )


def test_v2_projects_full_width_property_rows_and_zero_values() -> None:
    occurrence_id = uuid.uuid4()
    document = _document(
        occurrence_id,
        [
            {
                "type": "propertyRef",
                "props": {"occurrenceId": str(occurrence_id), "lineId": "line-1"},
            },
            {"type": "text", "text": "｜温度：60 ℃｜添加量: 0"},
        ],
    )

    result = _normalise_document_v2(document, [_occurrence(occurrence_id)])[0]

    assert result.values["property_line-1_0"] == {"value": "60 ℃", "raw_value": "60 ℃"}
    assert result.values["property_line-1_1"] == {"value": "0", "raw_value": "0"}


def test_v2_rejects_property_rows_from_another_parent() -> None:
    occurrence_id = uuid.uuid4()
    document = _document(
        occurrence_id,
        [
            {
                "type": "propertyRef",
                "props": {"occurrenceId": str(uuid.uuid4()), "lineId": "line-1"},
            },
            {"type": "text", "text": "｜温度: 60 ℃"},
        ],
    )

    with pytest.raises(ValueError, match="parent bullet"):
        _normalise_document_v2(document, [_occurrence(occurrence_id)])


def test_v2_rejects_a_third_bullet_level() -> None:
    occurrence_id = uuid.uuid4()
    document = ScientificDocumentV1(
        schema_version=2,
        blocks=[
            {
                "type": "bulletListItem",
                "content": [{"type": "objectRef", "props": {"occurrenceId": str(occurrence_id)}}],
                "children": [
                    {
                        "type": "bulletListItem",
                        "content": [],
                        "children": [{"type": "bulletListItem", "content": []}],
                    }
                ],
            }
        ],
    )

    with pytest.raises(ValueError, match="two bullet levels"):
        _normalise_document_v2(document, [_occurrence(occurrence_id)])


def test_v2_rebuilds_property_projection_after_child_deletion() -> None:
    occurrence_id = uuid.uuid4()
    occurrence = _occurrence(occurrence_id)
    occurrence.field_definitions = {
        "fields": [
            {
                "key": "property_old_line_0",
                "field_id": "property_old_line_0",
                "source": "local",
                "label": "温度",
            },
            {"key": "template_note", "source": "template", "label": "备注"},
        ]
    }
    occurrence.values = {
        "property_old_line_0": {"value": "60 ℃", "raw_value": "60 ℃"},
        "template_note": {"value": "keep"},
    }
    document = ScientificDocumentV1(
        schema_version=2,
        blocks=[
            {
                "type": "bulletListItem",
                "content": [{"type": "objectRef", "props": {"occurrenceId": str(occurrence_id)}}],
                "children": [],
            }
        ],
    )
    result = _normalise_document_v2(document, [occurrence])[0]
    assert result.values == {"template_note": {"value": "keep"}}
    assert result.field_definitions["fields"] == [
        {"key": "template_note", "source": "template", "label": "备注"}
    ]


def test_v2_rejects_duplicate_property_line_ids() -> None:
    occurrence_id = uuid.uuid4()
    child = [
        {
            "type": "propertyRef",
            "props": {"occurrenceId": str(occurrence_id), "lineId": "same-line"},
        },
        {"type": "text", "text": "｜温度: 60 ℃"},
    ]
    document = ScientificDocumentV1(
        schema_version=2,
        blocks=[
            {
                "type": "bulletListItem",
                "content": [{"type": "objectRef", "props": {"occurrenceId": str(occurrence_id)}}],
                "children": [
                    {"type": "bulletListItem", "content": child},
                    {"type": "bulletListItem", "content": child},
                ],
            }
        ],
    )
    with pytest.raises(ValueError, match="unique stable line IDs"):
        _normalise_document_v2(document, [_occurrence(occurrence_id)])


def test_no_idempotency_key_commits_the_outer_transaction(db) -> None:
    record_id = uuid.uuid4()

    def operation() -> dict[str, str]:
        db.add(
            IdempotencyRecord(
                id=record_id,
                idempotency_key=f"test-{record_id}",
                request_hash="hash",
                response_status=201,
                response_jsonb={"ok": True},
            )
        )
        db.flush()
        return {"id": str(record_id)}

    run_idempotent(db, None, {}, operation)
    external = create_engine(os.environ["TEST_DATABASE_URL"])
    try:
        with external.connect() as connection:
            assert (
                connection.scalar(
                    select(IdempotencyRecord.id).where(IdempotencyRecord.id == record_id)
                )
                == record_id
            )
    finally:
        external.dispose()
