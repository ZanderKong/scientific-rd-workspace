from __future__ import annotations

import io
import uuid

from fastapi.testclient import TestClient
from openpyxl import Workbook

from app.core.config import get_settings
from app.main import app
from app.models import Experiment, ExperimentTemplate, Project


def _experiment(db) -> Experiment:
    template = ExperimentTemplate(
        key="xy", name="XY", version=1, json_schema={"type": "object"}, is_active=True
    )
    project = Project(code=f"PRJ-{uuid.uuid4().hex[:6]}", title="Measurements", status="active")
    db.add_all([template, project])
    db.flush()
    experiment = Experiment(
        code=f"EXP-{uuid.uuid4().hex[:6]}",
        project_id=project.id,
        template_id=template.id,
        template_version=1,
        title="XY experiment",
        status="draft",
        structured_data={},
        note_document=[],
    )
    db.add(experiment)
    db.commit()
    return experiment


def test_csv_import_preview_commit_and_attachment_guard(db, monkeypatch, tmp_path) -> None:
    monkeypatch.setenv("STORAGE_ROOT", str(tmp_path))
    get_settings.cache_clear()
    experiment = _experiment(db)
    client = TestClient(app)
    try:
        attachment = client.post(
            f"/api/v1/experiments/{experiment.id}/attachments",
            files={"file": ("series.csv", b"x,y,ignored\n0,1,a\n1,2,b\n2,3,c\n", "text/csv")},
        ).json()
        preview = client.post(
            f"/api/v1/experiments/{experiment.id}/measurement-imports/preview",
            json={"source_attachment_id": attachment["id"]},
        )
        assert preview.status_code == 201
        assert preview.json()["headers"] == ["x", "y", "ignored"]
        assert preview.json()["preview_rows"][0] == ["0", "1", "a"]
        imported = client.post(
            f"/api/v1/measurement-imports/{preview.json()['id']}/commit",
            json={
                "measurement_name": "Response",
                "measurement_type": "other_xy",
                "default_chart_type": "scatter",
                "x": {"column": "x", "label": "X", "unit": "1"},
                "y": {"column": "y", "label": "Y", "unit": "AU"},
            },
        )
        assert imported.status_code == 201, imported.text
        assert imported.json()["row_count"] == 3
        points = client.get(f"/api/v1/measurements/{imported.json()['id']}/points")
        assert [item["x_value"] for item in points.json()] == [0.0, 1.0, 2.0]
        deletion = client.delete(f"/api/v1/attachments/{attachment['id']}")
        assert deletion.status_code == 409
        assert deletion.json()["detail"]["code"] == "attachment_in_use"
    finally:
        get_settings.cache_clear()


def test_invalid_mapped_value_marks_import_failed_and_keeps_attachment(
    db, monkeypatch, tmp_path
) -> None:
    monkeypatch.setenv("STORAGE_ROOT", str(tmp_path))
    get_settings.cache_clear()
    experiment = _experiment(db)
    client = TestClient(app)
    try:
        attachment = client.post(
            f"/api/v1/experiments/{experiment.id}/attachments",
            files={"file": ("series.csv", b"x,y\n0,1\n1,nope\n", "text/csv")},
        ).json()
        preview = client.post(
            f"/api/v1/experiments/{experiment.id}/measurement-imports/preview",
            json={"source_attachment_id": attachment["id"]},
        ).json()
        response = client.post(
            f"/api/v1/measurement-imports/{preview['id']}/commit",
            json={
                "measurement_name": "Response",
                "measurement_type": "other_xy",
                "x": {"column": "x", "label": "X", "unit": "1"},
                "y": {"column": "y", "label": "Y", "unit": "AU"},
            },
        )
        assert response.status_code == 422
        assert response.json()["detail"]["code"] == "non_numeric_value"
        assert (
            client.get(f"/api/v1/measurement-imports/{preview['id']}").json()["status"] == "failed"
        )
        assert client.get(f"/api/v1/experiments/{experiment.id}/measurements").json() == []
    finally:
        get_settings.cache_clear()


def test_xlsx_visible_sheet_preview(db, monkeypatch, tmp_path) -> None:
    monkeypatch.setenv("STORAGE_ROOT", str(tmp_path))
    get_settings.cache_clear()
    experiment = _experiment(db)
    workbook = Workbook()
    workbook.active.title = "Data"
    workbook.active.append(["time", "value"])
    workbook.active.append([0, 10])
    workbook.active.append([1, 12])
    hidden = workbook.create_sheet("Hidden")
    hidden.sheet_state = "hidden"
    hidden.append(["not", "visible"])
    output = io.BytesIO()
    workbook.save(output)
    client = TestClient(app)
    try:
        attachment = client.post(
            f"/api/v1/experiments/{experiment.id}/attachments",
            files={
                "file": (
                    "series.xlsx",
                    output.getvalue(),
                    "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                )
            },
        ).json()
        response = client.post(
            f"/api/v1/experiments/{experiment.id}/measurement-imports/preview",
            json={"source_attachment_id": attachment["id"]},
        )
        assert response.status_code == 201, response.text
        assert response.json()["available_sheets"] == ["Data"]
        assert response.json()["sheet_name"] == "Data"
    finally:
        get_settings.cache_clear()
