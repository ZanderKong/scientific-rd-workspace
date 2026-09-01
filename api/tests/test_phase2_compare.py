from __future__ import annotations

import uuid

from fastapi.testclient import TestClient

from app.main import app
from app.models import Experiment, ExperimentTemplate, Project


def _experiments(db) -> tuple[Project, list[Experiment]]:
    template = ExperimentTemplate(
        key=f"compare-{uuid.uuid4().hex[:8]}",
        name="Compare",
        version=1,
        json_schema={
            "type": "object",
            "properties": {
                "material": {"type": "string"},
                "temperature": {
                    "type": "object",
                    "properties": {"value": {"type": "number"}, "unit": {"type": "string"}},
                },
            },
        },
        is_active=True,
    )
    project = Project(code=f"PRJ-{uuid.uuid4().hex[:6]}", title="Compare", status="active")
    db.add_all([template, project])
    db.flush()
    result = []
    for index, material in enumerate(("A", "B")):
        item = Experiment(
            code=f"EXP-{uuid.uuid4().hex[:6]}",
            project_id=project.id,
            template_id=template.id,
            template_version=1,
            title=f"Experiment {index}",
            status="draft",
            structured_data={"material": material, "temperature": {"value": 60, "unit": "°C"}},
            note_document=[],
        )
        db.add(item)
        result.append(item)
    db.commit()
    return project, result


def test_compare_reports_structured_differences(db) -> None:
    project, experiments = _experiments(db)
    response = TestClient(app).post(
        "/api/v1/comparisons/experiments",
        json={
            "project_id": str(project.id),
            "experiment_ids": [str(item.id) for item in experiments],
        },
    )
    assert response.status_code == 200, response.text
    payload = response.json()
    material = next(row for row in payload["structured_differences"] if row["path"] == "/material")
    assert material["differs"] is True
    assert payload["measurements"] == []


def test_compare_rejects_cross_project_experiment(db) -> None:
    project, experiments = _experiments(db)
    other = Project(code=f"PRJ-{uuid.uuid4().hex[:6]}", title="Other", status="active")
    db.add(other)
    db.commit()
    response = TestClient(app).post(
        "/api/v1/comparisons/experiments",
        json={
            "project_id": str(project.id),
            "experiment_ids": [str(experiments[0].id), str(uuid.uuid4())],
        },
    )
    assert response.status_code == 409
