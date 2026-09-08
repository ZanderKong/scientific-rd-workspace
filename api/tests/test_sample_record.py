from __future__ import annotations

import uuid


def _document(*occurrence_ids: str) -> dict:
    return {
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
    }


def _process(definition: dict, occurrence_id: str, values: dict) -> dict:
    return {
        "occurrence_id": occurrence_id,
        "kind": "process",
        "target_id": definition["process_definition"]["id"],
        "process_definition_version_id": definition["current_version"]["id"],
        "label_snapshot": definition["process_definition"]["title"],
        "field_definitions": definition["current_version"]["execution_field_definitions"],
        "values": values,
        "status": "recorded",
    }


def test_sample_record_persists_document_order_without_implicit_product_bindings(client):
    project = client.post(
        "/api/v1/project-records",
        json={"project": {"code": "PRJ-TS1", "title": "sample projection"}},
    ).json()["project"]["id"]
    first = client.post(
        "/api/v1/process-definitions",
        json={
            "code": "PFD-TS1",
            "title": "step one",
            "project_scope_id": project,
            "execution_field_definitions": {
                "fields": [{"key": "step", "label": "Step", "value_type": "number"}]
            },
        },
    ).json()
    second = client.post(
        "/api/v1/process-definitions",
        json={
            "code": "PFD-TS2",
            "title": "step two",
            "project_scope_id": project,
            "execution_field_definitions": {
                "fields": [{"key": "step", "label": "Step", "value_type": "number"}]
            },
        },
    ).json()
    occurrence_ids = [str(uuid.uuid4()), str(uuid.uuid4())]
    payload = {
        "project_scope_id": project,
        "sample": {"code": "ROO-TS1", "title": "projected sample", "tags": ["样品"]},
        "document": _document(*occurrence_ids),
        "occurrences": [
            _process(first, occurrence_ids[0], {"step": 1}),
            _process(second, occurrence_ids[1], {"step": 2}),
        ],
    }
    created = client.post(
        "/api/v1/sample-records",
        json=payload,
        headers={"Idempotency-Key": "sample-create-two-processes"},
    )
    assert created.status_code == 201, created.text
    body = created.json()
    assert [item["execution"]["values"]["step"] for item in body["occurrences"]] == [1, 2]
    assert all(item["execution"]["object_bindings"] == [] for item in body["occurrences"])
    assert [item["occurrence_id"] for item in body["occurrences"]] == occurrence_ids
    replay = client.post(
        "/api/v1/sample-records",
        json=payload,
        headers={"Idempotency-Key": "sample-create-two-processes"},
    )
    assert replay.status_code == 201, replay.text
    assert replay.json()["sample"]["id"] == body["sample"]["id"]
    conflict = client.post(
        "/api/v1/sample-records",
        json={**payload, "sample": {**payload["sample"], "title": "different"}},
        headers={"Idempotency-Key": "sample-create-two-processes"},
    )
    assert conflict.status_code == 409, conflict.text


def test_sample_record_can_explicitly_select_its_producer_process(client):
    project = client.post(
        "/api/v1/project-records",
        json={"project": {"code": "PRJ-PRODUCER", "title": "producer scope"}},
    ).json()["project"]["id"]
    definition = client.post(
        "/api/v1/process-definitions",
        json={
            "code": "PFD-PRODUCER",
            "title": "make sample",
            "project_scope_id": project,
            "execution_field_definitions": {},
        },
    ).json()
    occurrence_id = str(uuid.uuid4())
    created = client.post(
        "/api/v1/sample-records",
        json={
            "project_scope_id": project,
            "sample": {"code": "ROO-PRODUCED", "title": "produced sample"},
            "document": _document(occurrence_id),
            "occurrences": [_process(definition, occurrence_id, {})],
            "producer_process_occurrence_id": occurrence_id,
        },
        headers={"Idempotency-Key": "sample-explicit-producer"},
    )
    assert created.status_code == 201, created.text
    body = created.json()
    assert body["producer_process_occurrence_id"] == occurrence_id
    bindings = body["occurrences"][0]["execution"]["object_bindings"]
    assert [(item["research_object_id"], item["direction"]) for item in bindings] == [
        (body["sample"]["id"], "output")
    ]


def test_sample_record_update_preserves_execution_and_binding_identity(client):
    project = client.post(
        "/api/v1/project-records",
        json={"project": {"code": "PRJ-TS2", "title": "sample update scope"}},
    ).json()["project"]["id"]
    first = client.post(
        "/api/v1/process-definitions",
        json={
            "code": "PFD-TS3",
            "title": "first",
            "project_scope_id": project,
            "execution_field_definitions": {
                "fields": [{"key": "retained", "label": "Retained", "value_type": "boolean"}]
            },
        },
    ).json()
    material = client.post(
        "/api/v1/objects",
        json={
            "kind": "research_object",
            "code": "ROO-TS2-MATERIAL",
            "title": "scope material",
            "project_scope_id": project,
            "tags": ["原料"],
            "process_field_definitions": {
                "fields": [
                    {
                        "key": "quantity",
                        "label": "Quantity",
                        "value_type": "number",
                        "default_unit": "g",
                    }
                ]
            },
        },
    ).json()
    process_occurrence = str(uuid.uuid4())
    material_occurrence = str(uuid.uuid4())
    document = {
        "schema_version": 1,
        "blocks": [
            {
                "type": "paragraph",
                "content": [
                    {"type": "processRef", "props": {"occurrenceId": process_occurrence}},
                    {"type": "objectRef", "props": {"occurrenceId": material_occurrence}},
                ],
            }
        ],
    }
    material_draft = {
        "occurrence_id": material_occurrence,
        "kind": "object",
        "target_id": material["id"],
        "label_snapshot": material["title"],
        "field_definitions": material["process_field_definitions"],
        "values": {"quantity": {"value": 1, "unit": "g"}},
        "binding": {
            "process_occurrence_id": process_occurrence,
            "direction": "input",
            "role": "reagent",
        },
    }
    created = client.post(
        "/api/v1/sample-records",
        json={
            "project_scope_id": project,
            "sample": {"code": "ROO-TS2", "title": "scope sample", "tags": ["样品"]},
            "document": document,
            "occurrences": [
                _process(first, process_occurrence, {"retained": True}),
                material_draft,
            ],
        },
        headers={"Idempotency-Key": "sample-create-with-binding"},
    )
    assert created.status_code == 201, created.text
    body = created.json()
    execution_id = body["occurrences"][0]["execution_id"]
    binding_id = body["occurrences"][1]["binding"]["binding_id"]

    material_draft["values"]["quantity"]["value"] = 2
    material_draft["binding"]["binding_id"] = binding_id
    process_draft = {
        **_process(first, process_occurrence, {"retained": True}),
        "execution_id": execution_id,
    }
    updated = client.put(
        f"/api/v1/samples/{body['sample']['id']}/record",
        json={
            "document": document,
            "occurrences": [process_draft, material_draft],
            "base_record_sha256": body["record_sha256"],
        },
        headers={"If-Match": body["record_sha256"]},
    )
    assert updated.status_code == 200, updated.text
    result = updated.json()
    assert result["occurrences"][0]["execution_id"] == execution_id
    assert result["occurrences"][1]["binding"]["binding_id"] == binding_id
    assert result["occurrences"][1]["values"] == {"quantity": {"value": 2, "unit": "g"}}
    historical = client.get(f"/api/v1/samples/{body['sample']['id']}/record/revisions/1")
    assert historical.status_code == 200, historical.text
    assert historical.json()["editable"] is False
    assert historical.json()["occurrences"][1]["values"] == {"quantity": {"value": 1, "unit": "g"}}


def test_sample_record_can_be_saved_without_process(client):
    project = client.post(
        "/api/v1/project-records",
        json={"project": {"code": "PRJ-NO-PROCESS", "title": "no process"}},
    ).json()["project"]["id"]
    created = client.post(
        "/api/v1/sample-records",
        json={
            "project_scope_id": project,
            "sample": {"code": "ROO-NO-PROCESS", "title": "observation only"},
            "document": {
                "schema_version": 1,
                "blocks": [{"type": "paragraph", "content": [{"type": "text", "text": "观察"}]}],
            },
            "occurrences": [],
        },
        headers={"Idempotency-Key": "sample-create-no-process"},
    )
    assert created.status_code == 201, created.text
    assert created.json()["occurrences"] == []
