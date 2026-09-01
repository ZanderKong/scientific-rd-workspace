from __future__ import annotations

import uuid

from fastapi.testclient import TestClient

from app.main import app
from app.models import ExperimentTemplate, Project

client = TestClient(app)

SCHEMA = {
    "type": "object",
    "additionalProperties": False,
    "properties": {
        "material": {"type": "string"},
        "temperature": {
            "type": "object",
            "additionalProperties": False,
            "properties": {
                "value": {"type": "number"},
                "unit": {"type": "string", "enum": ["°C"]},
            },
            "required": ["value", "unit"],
        },
    },
}


def seed_template(db) -> ExperimentTemplate:
    template = ExperimentTemplate(
        id=uuid.uuid4(),
        key="test-template",
        name="Test template",
        version=1,
        json_schema=SCHEMA,
        is_active=True,
    )
    db.add(template)
    db.commit()
    return template


def test_health() -> None:
    response = client.get("/api/v1/health")
    assert response.status_code == 200
    assert response.json() == {"status": "healthy"}


def test_project_and_experiment_round_trip(db) -> None:
    template = seed_template(db)
    project_response = client.post("/api/v1/projects", json={"title": "A project"})
    assert project_response.status_code == 201
    project = project_response.json()
    assert project["code"] == "PRJ-001"

    experiment_response = client.post(
        f"/api/v1/projects/{project['id']}/experiments",
        json={
            "title": "An experiment",
            "template_id": str(template.id),
            "structured_data": {
                "material": "Material A",
                "temperature": {"value": 60, "unit": "°C"},
            },
            "note_document": [],
        },
    )
    assert experiment_response.status_code == 201
    experiment = experiment_response.json()
    assert experiment["template_version"] == 1

    patch_response = client.patch(
        f"/api/v1/experiments/{experiment['id']}",
        json={
            "structured_data": {
                "material": "Material A",
                "temperature": {"value": 65, "unit": "°C"},
            }
        },
    )
    assert patch_response.status_code == 200
    assert patch_response.json()["structured_data"]["temperature"]["value"] == 65

    invalid_response = client.patch(
        f"/api/v1/experiments/{experiment['id']}",
        json={"structured_data": {"temperature": {"value": 65, "unit": "K"}}},
    )
    assert invalid_response.status_code == 422


def test_clone_and_revision_are_independent(db) -> None:
    template = seed_template(db)
    project = Project(code="PRJ-001", title="A project", status="active")
    db.add(project)
    db.commit()
    create_response = client.post(
        f"/api/v1/projects/{project.id}/experiments",
        json={
            "title": "Source",
            "template_id": str(template.id),
            "structured_data": {
                "material": "A",
                "temperature": {"value": 60, "unit": "°C"},
            },
        },
    )
    source = create_response.json()
    clone_response = client.post(
        f"/api/v1/experiments/{source['id']}/clone", json={"new_title": "Clone"}
    )
    assert clone_response.status_code == 201
    clone = clone_response.json()
    assert clone["id"] != source["id"]
    assert clone["parent_experiment_id"] == source["id"]
    assert clone["structured_data"] == source["structured_data"]

    revisions_response = client.get(f"/api/v1/experiments/{clone['id']}/revisions")
    assert revisions_response.status_code == 200
    assert [item["revision_number"] for item in revisions_response.json()] == [1]
