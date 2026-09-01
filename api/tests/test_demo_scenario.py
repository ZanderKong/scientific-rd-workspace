from __future__ import annotations

import uuid

from fastapi.testclient import TestClient

from app.core.config import get_settings
from app.main import app
from app.models import Experiment, ExperimentTemplate, Project


SCHEMA = {
    "type": "object",
    "additionalProperties": False,
    "properties": {
        "starch_amount": {"type": "number"},
        "drying_temperature": {"type": "number"},
    },
}


def test_phase_one_demo_flow(db, monkeypatch, tmp_path) -> None:
    template = ExperimentTemplate(
        id=uuid.uuid4(),
        key="materials-formulation-v1-demo",
        name="Materials formulation",
        version=1,
        json_schema=SCHEMA,
        is_active=True,
    )
    project = Project(code="PRJ-001", title="Colorimetric Sensor Formulation Optimisation", status="active")
    db.add_all([template, project])
    db.flush()
    source = Experiment(
        code="EXP-045",
        project_id=project.id,
        template_id=template.id,
        template_version=1,
        title="2-POA + KI + starch",
        status="completed",
        structured_data={"starch_amount": 1.0, "drying_temperature": 60},
        note_document=[{"type": "paragraph", "content": [{"type": "text", "text": "Objective", "styles": {}}]}],
    )
    db.add(source)
    db.commit()

    monkeypatch.setenv("STORAGE_ROOT", str(tmp_path))
    get_settings.cache_clear()
    client = TestClient(app)
    try:
        assert client.get("/api/v1/projects").json()[0]["code"] == "PRJ-001"
        experiment = client.get(f"/api/v1/experiments/{source.id}").json()
        assert experiment["structured_data"]["starch_amount"] == 1.0

        upload = client.post(
            f"/api/v1/experiments/{source.id}/attachments",
            files={"file": ("exp-045-photo.txt", b"demo evidence", "text/plain")},
        )
        assert upload.status_code == 201
        attachment_id = upload.json()["id"]
        assert client.get(f"/api/v1/attachments/{attachment_id}/download").content == b"demo evidence"

        revision = client.post(
            f"/api/v1/experiments/{source.id}/revisions",
            json={"change_note": "Before next formulation iteration"},
        )
        assert revision.status_code == 201
        source_revision = revision.json()

        clone = client.post(
            f"/api/v1/experiments/{source.id}/clone",
            json={"new_title": "EXP-046 — Lower starch loading"},
        )
        assert clone.status_code == 201
        clone_id = clone.json()["id"]
        assert clone.json()["parent_experiment_id"] == str(source.id)
        changed = client.patch(
            f"/api/v1/experiments/{clone_id}",
            json={"structured_data": {"starch_amount": 0.5, "drying_temperature": 60}},
        )
        assert changed.status_code == 200
        assert client.get(f"/api/v1/experiments/{source.id}").json()["structured_data"]["starch_amount"] == 1.0
        assert source_revision["snapshot_json"]["experiment"]["structured_data"]["starch_amount"] == 1.0
    finally:
        get_settings.cache_clear()
