"""Follow-up acceptance diagnostics for the four repaired boundaries.

Run from api with PYTHONPATH=.:tests and an isolated TEST_DATABASE_URL.
"""

# ruff: noqa: F811 -- pytest fixtures imported from the isolated backend suite

import uuid

from conftest import client, db, override_db  # noqa: F401
from test_v15_repair_regressions import post, project, research_object, sample_payload, update


def make_data(c):
    scope = project(c)
    definition = post(c, "/process-definitions", {"title": "audit", "project_scope_id": scope})
    target = research_object(c, scope, "subject before rename")
    payload = sample_payload(scope, definition, target)
    draft = post(
        c,
        "/data-drafts",
        {
            "project_scope_id": scope,
            "content": {
                "title": "audit data",
                "document": payload["document"],
                "occurrences": payload["occurrences"],
            },
        },
    )
    result = c.post(
        f"/api/v1/data-drafts/{draft['id']}/finalize",
        headers={"Idempotency-Key": str(uuid.uuid4())},
        json={"base_record_sha256": draft["record_sha256"]},
    )
    assert result.status_code == 200, result.text
    return result.json(), target


def test_data_token_is_stable_after_target_rename(client):
    record, target = make_data(client)
    current = client.get(f"/api/v1/objects/{target['id']}")
    renamed = client.patch(
        f"/api/v1/objects/{target['id']}",
        headers={"If-Match": current.headers["etag"]},
        json={"title": "subject after rename"},
    )
    assert renamed.status_code == 200, renamed.text
    reread = client.get(f"/api/v1/data/{record['data']['id']}/record").json()
    assert reread["record_sha256"] == record["record_sha256"]


def test_removed_document_removes_acquisition_subject(client):
    record, target = make_data(client)
    response = client.put(
        f"/api/v1/data/{record['data']['id']}/record",
        headers={"If-Match": record["record_sha256"]},
        json={"document": {"schema_version": 1, "blocks": []}, "occurrences": []},
    )
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["occurrences"] == []
    assert not any(
        item["source_kind"] == "acquisition_document" for item in body["subject_assignments"]
    )


def test_empty_sample_rejects_generic_document_patch(client):
    scope = project(client)
    record = post(
        client,
        "/sample-records",
        {
            "project_scope_id": scope,
            "sample": {"title": "empty", "tags": ["sample"]},
            "document": {"schema_version": 1, "blocks": []},
            "occurrences": [],
        },
    )
    path = f"/api/v1/objects/{record['sample']['id']}"
    current = client.get(path)
    response = client.patch(
        path,
        headers={"If-Match": current.headers["etag"]},
        json={
            "content_document": [
                {
                    "type": "paragraph",
                    "content": [
                        {"type": "objectRef", "props": {"occurrenceId": str(uuid.uuid4())}}
                    ],
                }
            ]
        },
    )
    assert response.status_code == 409, response.text
    assert response.json()["detail"]["error"]["code"] == "managed_record"


def test_unbind_and_restore_preserves_binding_identity(client):
    scope = project(client)
    definition = post(client, "/process-definitions", {"title": "audit", "project_scope_id": scope})
    target = research_object(client, scope, "bound target")
    payload = sample_payload(scope, definition, target)
    record = post(client, "/sample-records", payload)
    original_binding_id = record["occurrences"][1]["binding"]["binding_id"]
    import copy

    unbound_payload = copy.deepcopy(payload)
    unbound_payload["occurrences"][1].pop("binding")
    unbound = update(client, record, unbound_payload)
    assert unbound.status_code == 200, unbound.text
    restore_payload = copy.deepcopy(payload)
    restore_payload["occurrences"][1]["binding"]["binding_id"] = original_binding_id
    restored = update(client, unbound.json(), restore_payload)
    assert restored.status_code == 200, restored.text
    assert restored.json()["occurrences"][1]["binding"]["binding_id"] == original_binding_id
