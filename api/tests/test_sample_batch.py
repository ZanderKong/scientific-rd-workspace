from __future__ import annotations


def _record(project_id: str, code: str, title: str) -> dict:
    return {
        "project_scope_id": project_id,
        "sample": {"code": code, "title": title, "tags": ["sample"]},
        "document": {"schema_version": 1, "blocks": []},
        "occurrences": [],
    }


def test_sample_batch_is_atomic_and_idempotent(client):
    project_id = client.post(
        "/api/v1/project-records",
        json={"project": {"code": "PRJ-BATCH", "title": "Batch project"}},
    ).json()["project"]["id"]
    another_project_id = client.post(
        "/api/v1/project-records",
        json={"project": {"code": "PRJ-BATCH-OTHER", "title": "Other project"}},
    ).json()["project"]["id"]
    invalid = {
        "project_scope_id": project_id,
        "rows": [
            {"client_row_id": "row-1", "record": _record(project_id, "BAT-1", "Batch 1")},
            {
                "client_row_id": "row-2",
                "record": _record(another_project_id, "BAT-2", "Batch 2"),
            },
        ],
    }
    failed = client.post(
        "/api/v1/sample-records/batch",
        json=invalid,
        headers={"Idempotency-Key": "batch-invalid"},
    )
    assert failed.status_code == 422, failed.text
    remaining = client.get(
        "/api/v1/objects",
        params={"kind": "research_object", "project_scope_id": project_id, "q": "Batch 1"},
    )
    assert remaining.status_code == 200
    assert remaining.json() == []

    valid = {
        "project_scope_id": project_id,
        "rows": [
            {"client_row_id": "row-1", "record": _record(project_id, "BAT-1", "Batch 1")},
            {"client_row_id": "row-2", "record": _record(project_id, "BAT-2", "Batch 2")},
        ],
    }
    created = client.post(
        "/api/v1/sample-records/batch",
        json=valid,
        headers={"Idempotency-Key": "batch-valid"},
    )
    assert created.status_code == 201, created.text
    assert [row["client_row_id"] for row in created.json()["rows"]] == ["row-1", "row-2"]
    replay = client.post(
        "/api/v1/sample-records/batch",
        json=valid,
        headers={"Idempotency-Key": "batch-valid"},
    )
    assert replay.status_code == 201, replay.text
    assert [row["client_row_id"] for row in replay.json()["rows"]] == ["row-1", "row-2"]
    assert [row["record"]["sample"]["id"] for row in replay.json()["rows"]] == [
        row["record"]["sample"]["id"] for row in created.json()["rows"]
    ]
