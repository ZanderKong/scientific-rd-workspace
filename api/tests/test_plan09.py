from __future__ import annotations

from sqlalchemy import select
from test_object_graph import client, install_types, make

from app.models import DataPayload, ObjectRelation


def _sample_record(project_id: str, title: str = "Sample") -> dict:
    response = client.post(
        "/api/v1/sample-records",
        json={
            "project_scope_id": project_id,
            "sample": {"title": title},
            "steps": [{"title": "Prepare", "resources": []}],
        },
    )
    assert response.status_code == 201, response.text
    return response.json()


def test_experiment_membership_is_many_to_many_and_non_owning(db):
    install_types(db)
    project = make(db, "project", "Project")
    first = _sample_record(str(project.id), "First sample")
    second = _sample_record(str(project.id), "Second sample")
    payload = {
        "project_scope_id": str(project.id),
        "experiment": {"title": "Shared comparison"},
        "members": [
            {"sample_id": first["sample"]["id"], "note": "baseline"},
            {"sample_id": second["sample"]["id"], "note": "variant"},
        ],
    }
    one = client.post("/api/v1/experiment-records", json=payload)
    assert one.status_code == 201, one.text
    second_experiment = client.post(
        "/api/v1/experiment-records",
        json={
            **payload,
            "experiment": {"title": "Second comparison"},
            "members": [payload["members"][0]],
        },
    )
    assert second_experiment.status_code == 201, second_experiment.text
    assert len(one.json()["members"]) == 2
    assert len(second_experiment.json()["members"]) == 1
    assert db.scalar(
        select(ObjectRelation).where(
            ObjectRelation.relation_type == "includes",
            ObjectRelation.target_object_id == first["sample"]["id"],
        )
    )
    assert (
        db.scalar(
            select(ObjectRelation).where(
                ObjectRelation.relation_type == "contains",
                ObjectRelation.target_object_id == first["sample"]["id"],
            )
        )
        is None
    )

    duplicate = client.put(
        f"/api/v1/experiments/{one.json()['experiment']['id']}/record",
        json={"members": [payload["members"][0], payload["members"][0]]},
    )
    assert duplicate.status_code == 409
    assert duplicate.json()["detail"]["error"]["code"] == "duplicate_membership"


def test_typed_data_payloads_validate_and_preserve_table_rows(db):
    install_types(db)
    project = make(db, "project", "Project")
    data = make(db, "data", "Measurement", project.id)
    scalar = client.post(
        f"/api/v1/data/{data.id}/payloads/scalar",
        json={"name": "Response time", "value": 8.3, "unit": "s"},
    )
    assert scalar.status_code == 201, scalar.text
    table = client.post(
        f"/api/v1/data/{data.id}/payloads/table",
        json={
            "name": "Calibration",
            "columns": [
                {"key": "concentration", "label": "Concentration", "value_type": "number"},
                {"key": "note", "label": "Note", "value_type": "text"},
            ],
            "rows": [
                {"values": {"concentration": 10, "note": "low"}},
                {"values": {"concentration": 20, "note": "high"}},
            ],
        },
    )
    assert table.status_code == 201, table.text
    body = table.json()
    assert body["payload_kind"] == "table"
    assert body["table_rows_count"] == 2
    assert [row["values"]["concentration"] for row in body["table_rows"]] == [10, 20]
    assert db.scalar(select(DataPayload).where(DataPayload.id == body["id"])) is not None

    invalid = client.post(
        f"/api/v1/data/{data.id}/payloads/table",
        json={
            "name": "Invalid",
            "columns": [{"key": "value", "label": "Value", "value_type": "number"}],
            "rows": [{"values": {"value": "not numeric"}}],
        },
    )
    assert invalid.status_code == 422


def test_execution_freezes_plan_and_reports_as_run_change(db):
    install_types(db)
    project = make(db, "project", "Project")
    record = _sample_record(str(project.id), "Planned sample")
    sample_id = record["sample"]["id"]
    started = client.post(f"/api/v1/samples/{sample_id}/execution/start")
    assert started.status_code == 201, started.text
    planned_hash = started.json()["execution"]["plan_snapshot_sha256"]
    process = started.json()["planned"]["steps"][0]["process"]
    changed = client.put(
        f"/api/v1/samples/{sample_id}/record",
        json={
            "sample": {"title": "As-run sample"},
            "steps": [
                {
                    "process_id": process["id"],
                    "title": process["title"],
                    "properties_jsonb": {"parameters": {"temperature": {"value": 85, "unit": "C"}}},
                    "resources": [],
                }
            ],
        },
    )
    assert changed.status_code == 200, changed.text
    execution = client.get(f"/api/v1/samples/{sample_id}/execution")
    assert execution.status_code == 200, execution.text
    assert execution.json()["execution"]["plan_snapshot_sha256"] == planned_hash
    assert any(item["state"] != "same" for item in execution.json()["diff"])
    observation = client.put(
        f"/api/v1/samples/{sample_id}/execution",
        json={"observations": [{"text": "observed"}]},
    )
    assert observation.status_code == 200, observation.text
    completed = client.post(f"/api/v1/samples/{sample_id}/execution/complete")
    assert completed.status_code == 200, completed.text
    assert completed.json()["execution"]["status"] == "completed"


def test_idempotency_replays_and_change_set_requires_review(db):
    install_types(db)
    project = make(db, "project", "Project")
    record = _sample_record(str(project.id), "Proposal sample")
    payload = {
        "project_scope_id": str(project.id),
        "experiment": {"title": "Retry-safe experiment"},
        "members": [{"sample_id": record["sample"]["id"]}],
    }
    first = client.post(
        "/api/v1/experiment-records", json=payload, headers={"Idempotency-Key": "exp-retry"}
    )
    replay = client.post(
        "/api/v1/experiment-records", json=payload, headers={"Idempotency-Key": "exp-retry"}
    )
    assert first.status_code == replay.status_code == 201
    assert first.json()["experiment"]["id"] == replay.json()["experiment"]["id"]
    conflict = client.post(
        "/api/v1/experiment-records",
        json={**payload, "experiment": {"title": "Different request"}},
        headers={"Idempotency-Key": "exp-retry"},
    )
    assert conflict.status_code == 409
    assert conflict.json()["detail"]["error"]["code"] == "idempotency_conflict"

    proposal = client.post(
        "/api/v1/change-sets/propose",
        json={
            "operation_kind": "update_sample_record",
            "project_scope_id": str(project.id),
            "target_id": record["sample"]["id"],
            "base_record_sha256": record["record_sha256"],
            "request_payload_jsonb": {
                "sample": {"title": "Reviewed sample"},
                "steps": [
                    {
                        "process_id": record["steps"][0]["process"]["id"],
                        "title": "Prepare",
                        "resources": [],
                    }
                ],
            },
            "source_client_name": "pytest",
            "source_transport": "rest",
        },
    )
    assert proposal.status_code == 201, proposal.text
    assert (
        client.get(f"/api/v1/samples/{record['sample']['id']}/record").json()["sample"]["title"]
        == "Proposal sample"
    )
    applied = client.post(
        f"/api/v1/change-sets/{proposal.json()['id']}/review", json={"decision": "approve"}
    )
    assert applied.status_code == 200, applied.text
    assert applied.json()["status"] == "applied"
    assert (
        client.get(f"/api/v1/samples/{record['sample']['id']}/record").json()["sample"]["title"]
        == "Reviewed sample"
    )
