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


def test_sample_record_update_keeps_existing_and_new_steps_in_sample_scope(client):
    project = client.post(
        "/api/v1/project-records",
        json={"project": {"code": "PRJ-TS2", "title": "sample update scope"}},
    ).json()["project"]["id"]
    first = client.post(
        "/api/v1/process-definitions",
        json={"code": "PFD-TS3", "title": "first", "project_scope_id": project},
    ).json()
    second = client.post(
        "/api/v1/process-definitions",
        json={"code": "PFD-TS4", "title": "second", "project_scope_id": project},
    ).json()
    material = client.post(
        "/api/v1/objects",
        json={
            "kind": "research_object",
            "code": "ROO-TS2-MATERIAL",
            "title": "scope material",
            "project_scope_id": project,
            "tags": ["原料"],
        },
    ).json()
    created = client.post(
        "/api/v1/sample-records",
        json={
            "project_scope_id": project,
            "sample": {"code": "ROO-TS2", "title": "scope sample", "tags": ["样品"]},
            "steps": [
                {
                    "process_definition_id": first["process_definition"]["id"],
                    "object_bindings": [
                        {
                            "research_object_id": material["id"],
                            "direction": "input",
                            "role": "reagent",
                            "values": {"quantity": {"value": 1, "unit": "g"}},
                        }
                    ],
                }
            ],
        },
    )
    assert created.status_code == 201, created.text
    sample = created.json()
    existing_id = sample["steps"][0]["execution"]["id"]

    updated = client.put(
        f"/api/v1/samples/{sample['sample']['id']}/record",
        json={
            "steps": [
                {
                    "execution_id": existing_id,
                    "process_definition_id": first["process_definition"]["id"],
                    "values": {"retained": True},
                    "object_bindings": [
                        {
                            "research_object_id": material["id"],
                            "direction": "input",
                            "role": "reagent",
                            "values": {"quantity": {"value": 2, "unit": "g"}},
                        }
                    ],
                },
                {
                    "process_definition_id": second["process_definition"]["id"],
                    "values": {"added": True},
                },
            ]
        },
    )
    assert updated.status_code == 200, updated.text
    steps = updated.json()["steps"]
    assert steps[0]["execution"]["id"] == existing_id
    assert all(step["execution"]["project_scope_id"] == project for step in steps)
    assert [step["execution"]["values"] for step in steps] == [
        {"retained": True},
        {"added": True},
    ]
    assert steps[0]["execution"]["object_bindings"][0]["values"] == {
        "quantity": {"value": 2, "unit": "g"}
    }
