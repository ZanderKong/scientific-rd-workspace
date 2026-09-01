from __future__ import annotations

import uuid

from fastapi.testclient import TestClient

from app.main import app
from app.models import Experiment, ExperimentTemplate, Project


def _experiment(db) -> tuple[Project, Experiment]:
    template = ExperimentTemplate(
        key=f"lit-{uuid.uuid4().hex[:8]}",
        name="Literature",
        version=1,
        json_schema={"type": "object"},
        is_active=True,
    )
    project = Project(code=f"PRJ-{uuid.uuid4().hex[:6]}", title="Evidence", status="active")
    db.add_all([template, project])
    db.flush()
    experiment = Experiment(
        code=f"EXP-{uuid.uuid4().hex[:6]}",
        project_id=project.id,
        template_id=template.id,
        template_version=1,
        title="Evidence experiment",
        status="draft",
        structured_data={},
        note_document=[],
    )
    db.add(experiment)
    db.commit()
    return project, experiment


def test_literature_link_and_immutable_evidence_snapshot(db) -> None:
    project, experiment = _experiment(db)
    client = TestClient(app)
    literature = client.post(
        f"/api/v1/projects/{project.id}/literature",
        json={
            "title": "A paper",
            "authors": [{"family": "Smith", "given": "Ada"}],
            "publication_year": 2025,
            "doi": "10.1234/example",
        },
    )
    assert literature.status_code == 201, literature.text
    item = literature.json()
    link = client.post(
        f"/api/v1/experiments/{experiment.id}/literature-links",
        json={"literature_id": item["id"], "relationship_type": "supporting"},
    )
    assert link.status_code == 201, link.text
    evidence = client.post(
        f"/api/v1/projects/{project.id}/evidence",
        json={
            "context_experiment_id": str(experiment.id),
            "claim_text": "The paper supports the method.",
            "stance": "supports",
            "source": {"type": "literature", "literature_id": item["id"], "locator": "p. 4"},
        },
    )
    assert evidence.status_code == 201, evidence.text
    evidence_item = evidence.json()
    assert evidence_item["source_type"] == "literature"
    assert evidence_item["source_snapshot_json"]["title"] == "A paper"
    changed = client.patch(f"/api/v1/literature/{item['id']}", json={"title": "A corrected paper"})
    assert changed.status_code == 200
    historical = client.get(f"/api/v1/evidence/{evidence_item['id']}").json()
    assert historical["source_snapshot_json"]["title"] == "A paper"
    withdrawn = client.post(
        f"/api/v1/evidence/{evidence_item['id']}/withdraw", json={"reason": "Superseded"}
    )
    assert withdrawn.status_code == 200
    assert withdrawn.json()["status"] == "withdrawn"
    assert (
        client.post(
            f"/api/v1/evidence/{evidence_item['id']}/withdraw", json={"reason": "Again"}
        ).status_code
        == 409
    )


def test_cross_project_literature_link_is_rejected(db) -> None:
    project, experiment = _experiment(db)
    other = Project(code=f"PRJ-{uuid.uuid4().hex[:6]}", title="Other", status="active")
    db.add(other)
    db.commit()
    client = TestClient(app)
    literature = client.post(
        f"/api/v1/projects/{other.id}/literature", json={"title": "Other paper"}
    ).json()
    response = client.post(
        f"/api/v1/experiments/{experiment.id}/literature-links",
        json={"literature_id": literature["id"]},
    )
    assert response.status_code == 409
