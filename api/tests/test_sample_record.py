from __future__ import annotations

from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def test_sample_record_aggregates_all_context_bound_steps(client):
    project = client.post(
        "/api/v1/project-records",
        json={"project": {"code": "PRJ-TS1", "title": "sample projection"}},
    ).json()["project"]["id"]
    first = client.post(
        "/api/v1/process-definitions",
        json={"code": "PFD-TS1", "title": "step one", "project_scope_id": project},
    ).json()
    second = client.post(
        "/api/v1/process-definitions",
        json={"code": "PFD-TS2", "title": "step two", "project_scope_id": project},
    ).json()
    payload = {
        "project_scope_id": project,
        "sample": {"code": "ROO-TS1", "title": "projected sample", "tags": ["样品"]},
        "steps": [
            {
                "process_definition_id": first["process_definition"]["id"],
                "status": "completed",
                "values": {"step": 1},
            },
            {
                "process_definition_id": second["process_definition"]["id"],
                "status": "completed",
                "values": {"step": 2},
            },
        ],
    }
    created = client.post("/api/v1/sample-records", json=payload)
    assert created.status_code == 201, created.text
    body = created.json()
    assert [item["execution"]["values"]["step"] for item in body["steps"]] == [1, 2]
    assert all(
        any(binding["role"] == "sample_record" for binding in item["execution"]["object_bindings"])
        for item in body["steps"]
    )
