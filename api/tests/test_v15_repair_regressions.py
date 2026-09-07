"""Regression coverage for the first v1.5 repair slice."""

import copy
import uuid


def post(c, path, payload):
    response = c.post(
        "/api/v1" + path,
        json=payload,
        headers={"Idempotency-Key": str(uuid.uuid4())},
    )
    assert response.status_code < 300, response.text
    return response.json()


def project(c):
    return post(c, "/project-records", {"project": {"title": "repair project"}})["project"]["id"]


def research_object(c, scope, title):
    return post(
        c,
        "/objects",
        {"kind": "research_object", "title": title, "project_scope_id": scope},
    )


def sample_payload(scope, definition, target, *, process_id=None, object_id=None):
    process_id = process_id or str(uuid.uuid4())
    object_id = object_id or str(uuid.uuid4())
    return {
        "project_scope_id": scope,
        "sample": {"title": "repair sample", "tags": ["sample"]},
        "document": {
            "schema_version": 1,
            "blocks": [
                {
                    "type": "paragraph",
                    "content": [
                        {"type": "processRef", "props": {"occurrenceId": process_id}},
                        {"type": "objectRef", "props": {"occurrenceId": object_id}},
                    ],
                }
            ],
        },
        "occurrences": [
            {
                "occurrence_id": process_id,
                "kind": "process",
                "target_id": definition["process_definition"]["id"],
                "process_definition_version_id": definition["current_version"]["id"],
                "field_definitions": {},
                "values": {},
            },
            {
                "occurrence_id": object_id,
                "kind": "object",
                "target_id": target["id"],
                "field_definitions": {},
                "values": {},
                "binding": {
                    "process_occurrence_id": process_id,
                    "direction": "input",
                    "role": "subject",
                },
            },
        ],
    }


def update(c, record, payload):
    return c.put(
        f"/api/v1/samples/{record['sample']['id']}/record",
        headers={"If-Match": record["record_sha256"]},
        json={
            "document": payload["document"],
            "occurrences": payload["occurrences"],
            "base_record_sha256": record["record_sha256"],
        },
    )


def test_record_write_rejects_cross_scope_unbound_object(client):
    first_scope = project(client)
    second_scope = project(client)
    target = research_object(client, second_scope, "foreign target")
    occurrence_id = str(uuid.uuid4())
    response = client.post(
        "/api/v1/sample-records",
        json={
            "project_scope_id": first_scope,
            "sample": {"title": "cross scope", "tags": ["sample"]},
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
                }
            ],
        },
        headers={"Idempotency-Key": str(uuid.uuid4())},
    )
    assert response.status_code == 409, response.text


def test_scientific_record_contract_rejects_unknown_nested_fields(client):
    scope = project(client)
    response = client.post(
        "/api/v1/sample-records",
        json={
            "project_scope_id": scope,
            "sample": {"title": "strict contract", "unexpected_field": "must fail"},
            "document": {"schema_version": 1, "blocks": []},
            "occurrences": [],
        },
        headers={"Idempotency-Key": str(uuid.uuid4())},
    )
    assert response.status_code == 422, response.text


def test_managed_record_cannot_be_mutated_by_generic_object_patch(client):
    scope = project(client)
    definition = post(
        client, "/process-definitions", {"title": "managed process", "project_scope_id": scope}
    )
    target = research_object(client, scope, "bound object")
    record = post(client, "/sample-records", sample_payload(scope, definition, target))
    execution_id = record["occurrences"][0]["execution_id"]
    execution_before = client.get(f"/api/v1/process-executions/{execution_id}")
    assert execution_before.status_code == 200, execution_before.text
    response = client.patch(
        f"/api/v1/objects/{record['sample']['id']}",
        json={"content_document": []},
    )
    assert response.status_code == 409, response.text


def test_replace_keeps_binding_identity_and_updates_target(client):
    scope = project(client)
    definition = post(
        client, "/process-definitions", {"title": "replace process", "project_scope_id": scope}
    )
    original = research_object(client, scope, "original")
    replacement = research_object(client, scope, "replacement")
    payload = sample_payload(scope, definition, original)
    record = post(client, "/sample-records", payload)
    old_binding_id = record["occurrences"][1]["binding"]["binding_id"]
    payload["occurrences"][1]["target_id"] = replacement["id"]
    updated = update(client, record, payload)
    assert updated.status_code == 200, updated.text
    body = updated.json()
    assert body["occurrences"][1]["target_id"] == replacement["id"]
    assert body["occurrences"][1]["binding"]["binding_id"] == old_binding_id
    binding = body["occurrences"][0]["execution"]["object_bindings"][0]
    assert binding["id"] == old_binding_id
    assert binding["research_object_id"] == replacement["id"]


def test_retract_restore_reuses_execution_identity(client):
    scope = project(client)
    definition = post(
        client, "/process-definitions", {"title": "restore process", "project_scope_id": scope}
    )
    target = research_object(client, scope, "restore object")
    payload = sample_payload(scope, definition, target)
    record = post(client, "/sample-records", payload)
    execution_id = record["occurrences"][0]["execution_id"]
    empty = {"document": {"schema_version": 1, "blocks": []}, "occurrences": []}
    removed = update(client, record, empty)
    assert removed.status_code == 200, removed.text
    restored = update(client, removed.json(), payload)
    assert restored.status_code == 200, restored.text
    assert restored.json()["occurrences"][0]["execution_id"] == execution_id


def test_sample_token_is_stable_when_related_object_is_renamed(client):
    scope = project(client)
    definition = post(
        client, "/process-definitions", {"title": "token process", "project_scope_id": scope}
    )
    target = research_object(client, scope, "before")
    record = post(client, "/sample-records", sample_payload(scope, definition, target))
    execution_id = record["occurrences"][0]["execution_id"]
    execution_before = client.get(f"/api/v1/process-executions/{execution_id}")
    assert execution_before.status_code == 200, execution_before.text
    revisions_before = client.get(f"/api/v1/objects/{record['sample']['id']}/revisions").json()
    current_target = client.get(f"/api/v1/objects/{target['id']}")
    assert current_target.status_code == 200, current_target.text
    renamed = client.patch(
        f"/api/v1/objects/{target['id']}",
        headers={"If-Match": current_target.headers["ETag"]},
        json={"title": "after"},
    )
    assert renamed.status_code == 200, renamed.text
    current = client.get(f"/api/v1/samples/{record['sample']['id']}/record")
    assert current.status_code == 200
    assert current.json()["record_sha256"] == record["record_sha256"]
    execution_after = client.get(f"/api/v1/process-executions/{execution_id}")
    assert execution_after.status_code == 200, execution_after.text
    assert execution_after.json()["record_sha256"] == execution_before.json()["record_sha256"]
    assert (
        client.get(f"/api/v1/objects/{record['sample']['id']}/revisions").json() == revisions_before
    )


def test_view_rejects_representation_added_after_pinned_data_revision(client):
    scope = project(client)
    data = post(client, "/data-records", {"project_scope_id": scope, "data": {"title": "source"}})
    revision = client.get(f"/api/v1/objects/{data['data']['id']}/revisions").json()[-1]
    representation = post(
        client,
        f"/data/{data['data']['id']}/representations",
        {"kind": "description", "name": "later", "inline_payload_jsonb": {"text": "later"}},
    )
    response = client.post(
        "/api/v1/views",
        json={
            "project_scope_id": scope,
            "title": "invalid pin",
            "data_refs": [
                {
                    "data_id": data["data"]["id"],
                    "data_revision_id": revision["id"],
                    "representation_ids": [representation["id"]],
                }
            ],
        },
    )
    assert response.status_code == 422, response.text


def test_repin_does_not_release_historical_data_revision(client):
    scope = project(client)
    data = post(client, "/data-records", {"project_scope_id": scope, "data": {"title": "history"}})
    revision = client.get(f"/api/v1/objects/{data['data']['id']}/revisions").json()[-1]
    view = post(
        client,
        "/views",
        {
            "project_scope_id": scope,
            "title": "historical view",
            "data_refs": [{"data_id": data["data"]["id"], "data_revision_id": revision["id"]}],
        },
    )
    repinned = client.put(
        f"/api/v1/views/{view['view']['id']}",
        headers={"If-Match": view["record_sha256"]},
        json={"data_refs": []},
    )
    assert repinned.status_code == 200, repinned.text
    deleted = client.delete(f"/api/v1/objects/{data['data']['id']}")
    assert deleted.status_code == 409, deleted.text


def test_applied_changeset_replays_original_result(client):
    scope = project(client)
    change_set = post(
        client,
        "/change-sets/propose",
        {
            "project_scope_id": scope,
            "operation_kind": "create_research_object",
            "source_client_name": "repair-test",
            "request_payload_jsonb": {
                "kind": "research_object",
                "title": "replayed",
                "project_scope_id": scope,
            },
        },
    )
    first = client.post(f"/api/v1/change-sets/{change_set['id']}/apply")
    assert first.status_code == 200, first.text
    second = client.post(f"/api/v1/change-sets/{change_set['id']}/apply")
    assert second.status_code == 200, second.text
    assert second.json()["status"] == "applied"
    assert second.json()["applied_result_jsonb"] is not None


def test_data_finalize_keeps_manual_and_acquisition_subject_sources(client):
    scope = project(client)
    definition = post(
        client,
        "/process-definitions",
        {"title": "acquisition process", "project_scope_id": scope},
    )
    sample = post(
        client,
        "/sample-records",
        {
            "project_scope_id": scope,
            "sample": {"title": "source sample", "tags": ["sample"]},
            "document": {"schema_version": 1, "blocks": []},
            "occurrences": [],
        },
    )
    target = research_object(client, scope, "acquisition subject")
    payload = sample_payload(scope, definition, target)
    draft = post(
        client,
        "/data-drafts",
        {
            "project_scope_id": scope,
            "content": {
                "title": "acquired data",
                "tags": ["measurement"],
                "scientific_type": "table",
                "description": "observation",
                "document": payload["document"],
                "occurrences": payload["occurrences"],
                "subject_ids": [],
                "source_sample_id": sample["sample"]["id"],
            },
        },
    )
    finalized = client.post(
        f"/api/v1/data-drafts/{draft['id']}/finalize",
        json={"base_record_sha256": draft["record_sha256"]},
        headers={"Idempotency-Key": str(uuid.uuid4())},
    )
    assert finalized.status_code == 200, finalized.text
    assignments = finalized.json()["subject_assignments"]
    assert any(
        item["subject_id"] == sample["sample"]["id"] and item["source_kind"] == "manual"
        for item in assignments
    )
    assert any(
        item["subject_id"] == target["id"] and item["source_kind"] == "acquisition_document"
        for item in assignments
    )


def test_data_record_round_trips_scientific_document_and_occurrences(client):
    scope = project(client)
    definition = post(
        client,
        "/process-definitions",
        {"title": "data acquisition", "project_scope_id": scope},
    )
    target = research_object(client, scope, "data subject")
    payload = sample_payload(scope, definition, target)
    draft = post(
        client,
        "/data-drafts",
        {
            "project_scope_id": scope,
            "content": {
                "title": "round trip data",
                "tags": ["measurement"],
                "scientific_type": "table",
                "document": payload["document"],
                "occurrences": payload["occurrences"],
            },
        },
    )
    finalized = client.post(
        f"/api/v1/data-drafts/{draft['id']}/finalize",
        headers={"Idempotency-Key": str(uuid.uuid4())},
        json={"base_record_sha256": draft["record_sha256"]},
    )
    assert finalized.status_code == 200, finalized.text
    body = finalized.json()
    assert body["document"] == payload["document"]
    assert [item["occurrence_id"] for item in body["occurrences"]] == [
        item["occurrence_id"] for item in payload["occurrences"]
    ]
    reread = client.get(f"/api/v1/data/{body['data']['id']}/record")
    assert reread.status_code == 200, reread.text
    assert len(reread.json()["occurrences"]) == 2
    changed_document = {**payload["document"], "blocks": []}
    updated = client.put(
        f"/api/v1/data/{body['data']['id']}/record",
        headers={"If-Match": body["record_sha256"]},
        json={
            "document": changed_document,
            "occurrences": [],
            "change_note": "round trip correction",
        },
    )
    assert updated.status_code == 200, updated.text
    assert updated.json()["document"]["blocks"] == []


def test_empty_sample_is_managed_even_without_occurrences(client):
    scope = project(client)
    record = post(
        client,
        "/sample-records",
        {
            "project_scope_id": scope,
            "sample": {"title": "empty managed sample", "tags": ["sample"]},
            "document": {"schema_version": 1, "blocks": []},
            "occurrences": [],
        },
    )
    path = f"/api/v1/objects/{record['sample']['id']}"
    current = client.get(path)
    response = client.patch(
        path,
        headers={"If-Match": current.headers["etag"]},
        json={"content_document": []},
    )
    assert response.status_code == 409, response.text
    assert response.json()["detail"]["error"]["code"] == "managed_record"


def test_data_token_and_subjects_are_stable_after_target_rename_and_document_removal(client):
    scope = project(client)
    definition = post(
        client, "/process-definitions", {"title": "data source", "project_scope_id": scope}
    )
    target = research_object(client, scope, "source before")
    payload = sample_payload(scope, definition, target)
    draft = post(
        client,
        "/data-drafts",
        {
            "project_scope_id": scope,
            "content": {
                "title": "stable data",
                "document": payload["document"],
                "occurrences": payload["occurrences"],
            },
        },
    )
    finalized = client.post(
        f"/api/v1/data-drafts/{draft['id']}/finalize",
        headers={"Idempotency-Key": str(uuid.uuid4())},
        json={"base_record_sha256": draft["record_sha256"]},
    )
    assert finalized.status_code == 200, finalized.text
    body = finalized.json()
    target_response = client.get(f"/api/v1/objects/{target['id']}")
    renamed = client.patch(
        f"/api/v1/objects/{target['id']}",
        headers={"If-Match": target_response.headers["etag"]},
        json={"title": "source after"},
    )
    assert renamed.status_code == 200, renamed.text
    after_rename = client.get(f"/api/v1/data/{body['data']['id']}/record").json()
    assert after_rename["record_sha256"] == body["record_sha256"]
    corrected = client.put(
        f"/api/v1/data/{body['data']['id']}/record",
        headers={"If-Match": body["record_sha256"]},
        json={"document": {"schema_version": 1, "blocks": []}, "occurrences": []},
    )
    assert corrected.status_code == 200, corrected.text
    assert not any(
        item["source_kind"] == "acquisition_document"
        for item in corrected.json()["subject_assignments"]
    )


def test_binding_unbind_and_restore_preserves_identity(client):
    scope = project(client)
    definition = post(
        client, "/process-definitions", {"title": "binding lifecycle", "project_scope_id": scope}
    )
    target = research_object(client, scope, "binding target")
    payload = sample_payload(scope, definition, target)
    record = post(client, "/sample-records", payload)
    original_binding_id = record["occurrences"][1]["binding"]["binding_id"]
    unbound_payload = copy.deepcopy(payload)
    unbound_payload["occurrences"][1].pop("binding")
    unbound = update(client, record, unbound_payload)
    assert unbound.status_code == 200, unbound.text
    restore_payload = copy.deepcopy(payload)
    restore_payload["occurrences"][1]["binding"]["binding_id"] = original_binding_id
    restored = update(client, unbound.json(), restore_payload)
    assert restored.status_code == 200, restored.text
    assert restored.json()["occurrences"][1]["binding"]["binding_id"] == original_binding_id
