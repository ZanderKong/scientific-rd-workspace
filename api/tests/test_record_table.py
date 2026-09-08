from __future__ import annotations

import uuid


def _sample_payload(project_id: str, definition: dict, code: str, values: list[dict]) -> dict:
    occurrence_ids = [str(uuid.uuid4()) for _ in values]
    return {
        "project_scope_id": project_id,
        "sample": {"code": code, "title": code, "tags": ["样品"]},
        "document": {
            "schema_version": 1,
            "blocks": [
                {
                    "type": "paragraph",
                    "content": [
                        {"type": "processRef", "props": {"occurrenceId": occurrence_id}}
                        for occurrence_id in occurrence_ids
                    ],
                }
            ],
        },
        "occurrences": [
            {
                "occurrence_id": occurrence_id,
                "kind": "process",
                "target_id": definition["process_definition"]["id"],
                "process_definition_version_id": definition["current_version"]["id"],
                "field_definitions": definition["current_version"]["execution_field_definitions"],
                "values": item,
                "status": "recorded",
            }
            for occurrence_id, item in zip(occurrence_ids, values, strict=True)
        ],
    }


def test_record_table_filters_fields_within_the_same_occurrence(client):
    project = client.post(
        "/api/v1/project-records",
        json={"project": {"code": "PRJ-TABLE", "title": "Table project"}},
    ).json()["project"]
    definition = client.post(
        "/api/v1/process-definitions",
        json={
            "code": "PFD-TABLE",
            "title": "Measured process",
            "project_scope_id": project["id"],
            "execution_field_definitions": {
                "fields": [
                    {"key": "a", "label": "A", "value_type": "number", "default_unit": "g"},
                    {"key": "b", "label": "B", "value_type": "number", "default_unit": "g"},
                ]
            },
        },
    ).json()
    split = client.post(
        "/api/v1/sample-records",
        headers={"Idempotency-Key": "record-table-split"},
        json=_sample_payload(
            project["id"], definition, "ROO-TABLE-SPLIT", [{"a": 10, "b": 1}, {"a": 1, "b": 10}]
        ),
    )
    matched = client.post(
        "/api/v1/sample-records",
        headers={"Idempotency-Key": "record-table-match"},
        json=_sample_payload(project["id"], definition, "ROO-TABLE-MATCH", [{"a": 10, "b": 10}]),
    )
    assert split.status_code == 201, split.text
    assert matched.status_code == 201, matched.text
    target_id = definition["process_definition"]["id"]
    response = client.post(
        "/api/v1/record-tables/query",
        json={
            "project_scope_id": project["id"],
            "record_kind": "sample",
            "required_refs": [target_id],
            "filters": [
                {"target_id": target_id, "field_key": "a", "operator": "gte", "value": 5},
                {"target_id": target_id, "field_key": "b", "operator": "gte", "value": 5},
            ],
            "display_columns": [
                {"target_id": target_id, "field_key": "a", "label": "A", "value_type": "number"}
            ],
        },
    )
    assert response.status_code == 200, response.text
    result = response.json()
    assert result["total"] == 1
    assert [row["record"]["code"] for row in result["rows"]] == ["ROO-TABLE-MATCH"]
    assert {(item["field_key"], item["value_type"]) for item in result["columns"]} == {
        ("a", "number"),
        ("b", "number"),
    }
    column_key = f"{target_id}:a"
    assert result["rows"][0]["values"][column_key][0]["value"] == 10


def test_record_table_returns_ordered_multi_values_and_distinguishes_empty(client):
    project = client.post(
        "/api/v1/project-records",
        json={"project": {"code": "PRJ-TABLE-MULTI", "title": "Table multi"}},
    ).json()["project"]
    definition = client.post(
        "/api/v1/process-definitions",
        json={
            "code": "PFD-TABLE-MULTI",
            "title": "Repeated process",
            "project_scope_id": project["id"],
            "execution_field_definitions": {
                "fields": [{"key": "note", "label": "Note", "value_type": "text"}]
            },
        },
    ).json()
    created = client.post(
        "/api/v1/sample-records",
        headers={"Idempotency-Key": "record-table-multi"},
        json=_sample_payload(
            project["id"], definition, "ROO-TABLE-MULTI", [{"note": "first"}, {}, {"note": "third"}]
        ),
    )
    assert created.status_code == 201, created.text
    target_id = definition["process_definition"]["id"]
    result = client.post(
        "/api/v1/record-tables/query",
        json={
            "project_scope_id": project["id"],
            "record_kind": "sample",
            "display_columns": [
                {"target_id": target_id, "field_key": "note", "value_type": "text"}
            ],
        },
    ).json()
    values = result["rows"][0]["values"][f"{target_id}:note"]
    assert [item["value"] for item in values] == ["first", None, "third"]
    assert result["rows"][0]["referenced_target_ids"] == [target_id]


def test_record_table_exposes_referenced_but_unfilled_field(client):
    project = client.post(
        "/api/v1/project-records",
        json={"project": {"code": "PRJ-TABLE-EMPTY", "title": "Table empty"}},
    ).json()["project"]
    definition = client.post(
        "/api/v1/process-definitions",
        json={
            "code": "PFD-TABLE-EMPTY",
            "title": "Empty process",
            "project_scope_id": project["id"],
            "execution_field_definitions": {
                "fields": [{"key": "reading", "label": "Reading", "value_type": "number"}]
            },
        },
    ).json()
    created = client.post(
        "/api/v1/sample-records",
        headers={"Idempotency-Key": "record-table-empty"},
        json=_sample_payload(project["id"], definition, "ROO-TABLE-EMPTY", [{}]),
    )
    assert created.status_code == 201, created.text
    target_id = definition["process_definition"]["id"]
    result = client.post(
        "/api/v1/record-tables/query",
        json={
            "project_scope_id": project["id"],
            "record_kind": "sample",
            "display_columns": [{"target_id": target_id, "field_key": "reading"}],
        },
    )
    assert result.status_code == 200, result.text
    body = result.json()
    assert body["columns"] == [
        {
            "target_id": target_id,
            "field_key": "reading",
            "label": "Empty process · Reading",
            "value_type": "number",
        }
    ]
    values = body["rows"][0]["values"][f"{target_id}:reading"]
    assert values[0]["value"] is None


def test_record_table_catalog_includes_fieldless_refs_and_honors_record_ids(client):
    project = client.post(
        "/api/v1/project-records",
        json={"project": {"code": "PRJ-TABLE-REF", "title": "Table refs"}},
    ).json()["project"]
    target = client.post(
        "/api/v1/objects",
        json={
            "kind": "research_object",
            "code": "ROO-FIELDLESS",
            "title": "Fieldless reference",
            "project_scope_id": project["id"],
        },
    ).json()
    occurrence_id = str(uuid.uuid4())
    included = client.post(
        "/api/v1/sample-records",
        headers={"Idempotency-Key": "record-table-fieldless-included"},
        json={
            "project_scope_id": project["id"],
            "sample": {"code": "ROO-INCLUDED", "title": "Included", "tags": ["sample"]},
            "document": {
                "schema_version": 1,
                "blocks": [
                    {
                        "type": "paragraph",
                        "content": [
                            {"type": "objectRef", "props": {"occurrenceId": occurrence_id}}
                        ],
                    }
                ],
            },
            "occurrences": [
                {
                    "occurrence_id": occurrence_id,
                    "kind": "object",
                    "target_id": target["id"],
                    "field_definitions": {},
                    "values": {},
                }
            ],
        },
    ).json()
    response = client.post(
        "/api/v1/record-tables/query",
        json={
            "project_scope_id": project["id"],
            "record_kind": "sample",
            "record_ids": [included["sample"]["id"]],
        },
    )
    assert response.status_code == 200, response.text
    body = response.json()
    assert [row["record"]["id"] for row in body["rows"]] == [included["sample"]["id"]]
    assert [(item["id"], item["title"]) for item in body["available_refs"]] == [
        (target["id"], "Fieldless reference")
    ]
