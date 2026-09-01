from __future__ import annotations

import uuid

import pytest
from fastapi.testclient import TestClient

from app.core.config import get_settings
from app.main import app
from app.models import Attachment, Experiment, ExperimentTemplate, Project
from app.storage import LocalStorageAdapter


def create_experiment(db) -> Experiment:
    template = ExperimentTemplate(
        key="attachment-template",
        name="Attachment template",
        version=1,
        json_schema={"type": "object"},
        is_active=True,
    )
    project = Project(code="PRJ-001", title="Attachment project", status="active")
    db.add_all([template, project])
    db.flush()
    experiment = Experiment(
        code="EXP-001",
        project_id=project.id,
        template_id=template.id,
        template_version=1,
        title="Attachment experiment",
        status="draft",
        structured_data={},
        note_document=[],
    )
    db.add(experiment)
    db.commit()
    return experiment


def test_failed_metadata_commit_does_not_delete_attachment_bytes(db, monkeypatch, tmp_path) -> None:
    experiment = create_experiment(db)
    monkeypatch.setenv("STORAGE_ROOT", str(tmp_path))
    get_settings.cache_clear()
    client = TestClient(app)
    try:
        upload = client.post(
            f"/api/v1/experiments/{experiment.id}/attachments",
            files={"file": ("result.txt", b"authoritative bytes", "text/plain")},
        )
        assert upload.status_code == 201
        attachment_id = uuid.UUID(upload.json()["id"])
        attachment = db.get(Attachment, attachment_id)
        assert attachment is not None
        storage_key = attachment.storage_key

        def fail_commit() -> None:
            raise RuntimeError("simulated database commit failure")

        monkeypatch.setattr(db, "commit", fail_commit)
        with pytest.raises(RuntimeError, match="simulated database commit failure"):
            client.delete(f"/api/v1/attachments/{attachment_id}")

        db.expire_all()
        assert db.get(Attachment, attachment_id) is not None
        assert (
            LocalStorageAdapter(tmp_path).open(storage_key).read_bytes() == b"authoritative bytes"
        )
    finally:
        get_settings.cache_clear()


def test_byte_cleanup_failure_is_diagnostic_and_leaves_no_metadata(
    db, monkeypatch, tmp_path
) -> None:
    experiment = create_experiment(db)
    monkeypatch.setenv("STORAGE_ROOT", str(tmp_path))
    get_settings.cache_clear()
    client = TestClient(app)
    try:
        upload = client.post(
            f"/api/v1/experiments/{experiment.id}/attachments",
            files={"file": ("result.txt", b"orphan candidate", "text/plain")},
        )
        attachment_id = uuid.UUID(upload.json()["id"])
        attachment = db.get(Attachment, attachment_id)
        assert attachment is not None
        storage_key = attachment.storage_key
        adapter = LocalStorageAdapter(tmp_path)

        def fail_delete(_storage_key: str) -> None:
            raise OSError("simulated byte cleanup failure")

        monkeypatch.setattr(adapter, "delete", fail_delete)
        monkeypatch.setattr("app.routers.attachments._storage", lambda: adapter)
        response = client.delete(f"/api/v1/attachments/{attachment_id}")

        assert response.status_code == 500
        assert "metadata deleted but byte cleanup failed" in response.json()["detail"]
        db.expire_all()
        assert db.get(Attachment, attachment_id) is None
        assert adapter.open(storage_key).read_bytes() == b"orphan candidate"
    finally:
        get_settings.cache_clear()
