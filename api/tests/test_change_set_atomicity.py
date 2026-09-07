from __future__ import annotations

import pytest
from sqlalchemy import select
from sqlalchemy.orm import Session

from app import change_set_service
from app.models import ChangeSet, ResearchObject


def test_apply_failure_rolls_back_business_record(client, db: Session, monkeypatch):
    project_response = client.post(
        "/api/v1/project-records",
        json={"project": {"code": "PRJ-CHANGESET-ROLLBACK", "title": "Rollback project"}},
    )
    assert project_response.status_code == 201, project_response.text
    project_id = project_response.json()["project"]["id"]
    proposal_response = client.post(
        "/api/v1/change-sets/propose",
        json={
            "project_scope_id": project_id,
            "operation_kind": "create_research_object",
            "request_payload_jsonb": {
                "kind": "research_object",
                "code": "ROO-MUST-ROLLBACK",
                "title": "Must roll back",
                "project_scope_id": project_id,
            },
        },
    )
    assert proposal_response.status_code == 201, proposal_response.text
    change_set_id = proposal_response.json()["id"]
    original_apply = change_set_service._apply_operation

    def fail_after_business_flush(session, item):
        original_apply(session, item)
        raise RuntimeError("injected failure after business flush")

    monkeypatch.setattr(change_set_service, "_apply_operation", fail_after_business_flush)
    with pytest.raises(RuntimeError, match="injected failure"):
        client.post(f"/api/v1/change-sets/{change_set_id}/apply")

    assert (
        db.scalar(select(ResearchObject).where(ResearchObject.code == "ROO-MUST-ROLLBACK")) is None
    )
    change_set = db.get(ChangeSet, change_set_id)
    assert change_set is not None
    assert change_set.status == "failed"
    assert change_set.failure_jsonb["code"] == "change_set_failed"
