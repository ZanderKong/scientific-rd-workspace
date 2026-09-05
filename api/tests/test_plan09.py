from __future__ import annotations

from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def _project() -> str:
    result = client.post(
        "/api/v1/project-records",
        json={"project": {"code": "PRJ-T09", "title": "domain cutover"}},
    )
    assert result.status_code == 201, result.text
    return result.json()["project"]["id"]


def test_data_record_has_multiple_representations(client):
    project_id = _project()
    response = client.post(
        "/api/v1/data-records",
        json={
            "project_scope_id": project_id,
            "data": {"code": "DAT-T01", "title": "response", "tags": ["response"]},
            "scientific_type": "table",
        },
    )
    assert response.status_code == 201, response.text
    data = response.json()["data"]
    representation = client.post(
        f"/api/v1/data/{data['id']}/representations",
        json={
            "kind": "table",
            "name": "response table",
            "format": "tabular",
            "schema_jsonb": {"columns": [{"key": "response", "value_type": "number"}]},
            "inline_payload_jsonb": {"rows": [{"response": 0.42}, {"response": 0.61}]},
        },
    )
    assert representation.status_code == 201, representation.text
    record = client.get(f"/api/v1/data/{data['id']}/record")
    assert record.status_code == 200, record.text
    assert record.json()["representations"][0]["table_rows_count"] == 2


def test_process_definition_execution_and_sample_projection(client):
    project_id = _project()
    definition = client.post(
        "/api/v1/process-definitions",
        json={"code": "PFD-T01", "title": "prepare", "project_scope_id": project_id},
    )
    assert definition.status_code == 201, definition.text
    definition_id = definition.json()["process_definition"]["id"]
    sample = client.post(
        "/api/v1/objects",
        json={
            "kind": "research_object",
            "code": "ROO-T09",
            "title": "sample",
            "project_scope_id": project_id,
            "tags": ["样品"],
        },
    ).json()
    execution = client.post(
        "/api/v1/process-executions",
        json={
            "process_definition_id": definition_id,
            "project_scope_id": project_id,
            "status": "completed",
            "object_bindings": [
                {
                    "research_object_id": sample["id"],
                    "direction": "output",
                    "role": "product",
                }
            ],
        },
    )
    assert execution.status_code == 201, execution.text
    projection = client.get(f"/api/v1/samples/{sample['id']}/record")
    assert projection.status_code == 200, projection.text
    assert projection.json()["steps"][0]["execution"]["id"] == execution.json()["id"]


def test_removed_v02_routes_are_not_active(client):
    comparison_path = "/api/v1/experiments/00000000-0000-0000-0000-000000000000/comparison"
    composition_path = "/api/v1/processes/00000000-0000-0000-0000-000000000000/composition"
    assert client.get(comparison_path).status_code == 404
    assert client.get(composition_path).status_code == 404
