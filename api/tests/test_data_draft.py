from __future__ import annotations


def test_data_draft_upload_refresh_and_idempotent_finalize(client):
    project = client.post(
        "/api/v1/project-records",
        json={"project": {"code": "PRJ-DATA-DRAFT", "title": "Data draft project"}},
    ).json()["project"]
    sample = client.post(
        "/api/v1/objects",
        json={
            "kind": "research_object",
            "code": "ROO-DATA-SUBJECT",
            "title": "Data subject",
            "project_scope_id": project["id"],
            "tags": ["样品"],
        },
    ).json()
    content = {
        "title": "Recoverable result",
        "tags": ["measurement"],
        "scientific_type": "table",
        "description": "Observed response",
        "document": {"schema_version": 1, "blocks": []},
        "occurrences": [],
        "subject_ids": [],
        "source_sample_id": sample["id"],
    }
    begun = client.post(
        "/api/v1/data-drafts",
        headers={"Idempotency-Key": "begin-data-draft"},
        json={"project_scope_id": project["id"], "content": content},
    )
    assert begun.status_code == 201, begun.text
    draft = begun.json()

    hidden = client.post(
        "/api/v1/record-tables/query",
        json={"project_scope_id": project["id"], "record_kind": "data"},
    )
    assert hidden.status_code == 200, hidden.text
    assert hidden.json()["total"] == 0

    uploaded = client.post(
        f"/api/v1/objects/{draft['data_id']}/assets",
        files={"file": ("raw.csv", b"time,value\n0,1\n", "text/csv")},
    )
    assert uploaded.status_code == 201, uploaded.text
    attachment = client.post(
        f"/api/v1/data-drafts/{draft['id']}/attachments",
        json={"client_attachment_id": "raw-1", "asset_id": uploaded.json()["id"]},
    )
    assert attachment.status_code == 200, attachment.text
    draft = attachment.json()
    assert draft["attachments"][0]["sha256"] == uploaded.json()["sha256"]

    updated = client.put(
        f"/api/v1/data-drafts/{draft['id']}",
        json={
            "base_record_sha256": draft["record_sha256"],
            "content": {**content, "origin_client_attachment_id": "raw-1"},
        },
    )
    assert updated.status_code == 200, updated.text
    draft = updated.json()
    finalized = client.post(
        f"/api/v1/data-drafts/{draft['id']}/finalize",
        headers={"Idempotency-Key": "finalize-data-draft"},
        json={"base_record_sha256": draft["record_sha256"]},
    )
    assert finalized.status_code == 200, finalized.text
    result = finalized.json()
    assert {item["kind"] for item in result["representations"]} == {
        "raw_file",
        "description",
    }
    assert result["origin_representation_id"] is not None
    assert [item["id"] for item in result["subjects"]] == [sample["id"]]
    assert result["subject_assignments"][0]["source_kind"] == "manual"

    replay = client.post(
        f"/api/v1/data-drafts/{draft['id']}/finalize",
        headers={"Idempotency-Key": "finalize-data-draft"},
        json={"base_record_sha256": draft["record_sha256"]},
    )
    assert replay.status_code == 200, replay.text
    assert replay.json()["data"]["id"] == result["data"]["id"]
    assert client.get(f"/api/v1/data-drafts/{draft['id']}").json()["status"] == "finalized"

    visible = client.post(
        "/api/v1/record-tables/query",
        json={"project_scope_id": project["id"], "record_kind": "data"},
    )
    assert visible.status_code == 200, visible.text
    assert visible.json()["total"] == 1
