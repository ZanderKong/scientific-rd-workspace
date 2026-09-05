from __future__ import annotations

from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def _project() -> str:
    response = client.post(
        "/api/v1/project-records",
        json={"project": {"code": "PRJ-T01", "title": "v0.3 test project"}},
    )
    assert response.status_code == 201, response.text
    return response.json()["project"]["id"]


def _object(project_id: str, title: str, code: str, tags: list[str]) -> dict:
    response = client.post(
        "/api/v1/objects",
        json={
            "kind": "research_object",
            "code": code,
            "title": title,
            "project_scope_id": project_id,
            "tags": tags,
            "process_field_definitions": {
                "fields": [
                    {
                        "key": "quantity",
                        "label": "用量",
                        "value_type": "number",
                        "default_unit": "g",
                    }
                ]
            },
        },
    )
    assert response.status_code == 201, response.text
    return response.json()


def test_capabilities_and_research_object_tags(client):
    body = client.get("/api/v1/capabilities").json()
    assert body["api_contract_version"] == "0.3"
    assert set(body["object_kinds"]) == {
        "research_object",
        "process_definition",
        "data",
        "experiment",
        "project",
        "view",
        "claim",
    }
    project_id = _project()
    item = _object(project_id, "2-POA", "ROO-T01", ["原料", "试剂"])
    assert item["kind"] == "research_object"
    assert item["tags"] == ["原料", "试剂"]
    assert item["process_field_definitions"]["fields"][0]["key"] == "quantity"


def test_generic_relations_reject_system_managed_shortcuts(client):
    project_id = _project()
    source = _object(project_id, "source", "ROO-T02", ["样品"])
    target = _object(project_id, "target", "ROO-T03", ["样品"])
    allowed = client.post(
        "/api/v1/relations",
        json={
            "source_object_id": source["id"],
            "target_object_id": target["id"],
            "relation_type": "related_to",
            "role": "reference",
        },
    )
    assert allowed.status_code == 201, allowed.text
    blocked = client.post(
        "/api/v1/relations",
        json={
            "source_object_id": source["id"],
            "target_object_id": target["id"],
            "relation_type": "subject",
        },
    )
    assert blocked.status_code == 409
    assert blocked.json()["detail"]["error"]["code"] == "system_managed_relation"
