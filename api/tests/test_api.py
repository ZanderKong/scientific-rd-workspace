from __future__ import annotations

import uuid

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.exc import IntegrityError

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


def test_revision_detail_uses_number_and_snapshot_remains_immutable(db) -> None:
    template = seed_template(db)
    project = Project(code="PRJ-001", title="A project", status="active")
    db.add(project)
    db.commit()
    created = client.post(
        f"/api/v1/projects/{project.id}/experiments",
        json={
            "title": "Versioned experiment",
            "template_id": str(template.id),
            "structured_data": {
                "material": "A",
                "temperature": {"value": 60, "unit": "°C"},
            },
            "note_document": [
                {
                    "type": "paragraph",
                    "content": [{"type": "text", "text": "Original note", "styles": {}}],
                }
            ],
        },
    ).json()
    revision = client.post(
        f"/api/v1/experiments/{created['id']}/revisions",
        json={"change_note": "Before edit"},
    ).json()
    assert revision["revision_number"] == 1

    changed = client.patch(
        f"/api/v1/experiments/{created['id']}",
        json={
            "structured_data": {
                "material": "A",
                "temperature": {"value": 65, "unit": "°C"},
            },
            "note_document": [
                {
                    "type": "paragraph",
                    "content": [{"type": "text", "text": "Changed note", "styles": {}}],
                }
            ],
        },
    )
    assert changed.status_code == 200

    detail = client.get(f"/api/v1/experiments/{created['id']}/revisions/1")
    assert detail.status_code == 200
    snapshot = detail.json()["snapshot_json"]["experiment"]
    assert snapshot["structured_data"]["temperature"]["value"] == 60
    assert snapshot["note_document"][0]["content"][0]["text"] == "Original note"


def test_experiments_remain_bound_to_their_exact_template_version(db) -> None:
    version_one = ExperimentTemplate(
        key="versioned-template",
        name="Versioned template",
        version=1,
        json_schema={
            "type": "object",
            "additionalProperties": False,
            "properties": {"legacy_field": {"type": "string"}},
            "required": ["legacy_field"],
        },
        is_active=True,
    )
    project = Project(code="PRJ-001", title="A project", status="active")
    db.add_all([version_one, project])
    db.commit()

    source_response = client.post(
        f"/api/v1/projects/{project.id}/experiments",
        json={
            "title": "Version one experiment",
            "template_id": str(version_one.id),
            "structured_data": {"legacy_field": "kept"},
        },
    )
    assert source_response.status_code == 201
    source = source_response.json()

    version_one.is_active = False
    version_two = ExperimentTemplate(
        key="versioned-template",
        name="Versioned template",
        version=2,
        json_schema={
            "type": "object",
            "additionalProperties": False,
            "properties": {"new_field": {"type": "number"}},
            "required": ["new_field"],
        },
        is_active=True,
    )
    db.add(version_two)
    db.commit()

    historical_update = client.patch(
        f"/api/v1/experiments/{source['id']}",
        json={"structured_data": {"legacy_field": "still valid"}},
    )
    assert historical_update.status_code == 200
    wrong_schema_update = client.patch(
        f"/api/v1/experiments/{source['id']}",
        json={"structured_data": {"new_field": 2}},
    )
    assert wrong_schema_update.status_code == 422

    clone = client.post(
        f"/api/v1/experiments/{source['id']}/clone", json={"new_title": "Historical clone"}
    )
    assert clone.status_code == 201
    assert clone.json()["template_id"] == str(version_one.id)
    assert clone.json()["template_version"] == 1

    current = client.post(
        f"/api/v1/projects/{project.id}/experiments",
        json={
            "title": "Version two experiment",
            "template_id": str(version_two.id),
            "structured_data": {"new_field": 2},
        },
    )
    assert current.status_code == 201
    assert current.json()["template_id"] == str(version_two.id)
    assert current.json()["template_version"] == 2

    version_one.json_schema = {"type": "object"}
    with pytest.raises(ValueError, match="template versions are immutable"):
        db.commit()
    db.rollback()


def test_template_key_and_version_pair_is_unique(db) -> None:
    db.add_all(
        [
            ExperimentTemplate(
                key="same-template",
                name="Same template",
                version=1,
                json_schema={"type": "object"},
                is_active=True,
            ),
            ExperimentTemplate(
                key="same-template",
                name="Same template",
                version=1,
                json_schema={"type": "object"},
                is_active=False,
            ),
        ]
    )
    with pytest.raises(IntegrityError):
        db.commit()
    db.rollback()
