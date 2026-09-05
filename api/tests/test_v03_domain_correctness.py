from __future__ import annotations

from app.claim_service import create_claim, update_claim
from app.models import DataRepresentation, ProcessDefinitionVersion
from app.schemas import ClaimCreate, ClaimPut
from app.storage import LocalStorageProvider, StorageRouter


def _project(client) -> str:
    response = client.post(
        "/api/v1/project-records",
        json={"project": {"code": "PRJ-V03", "title": "v0.3 correctness"}},
    )
    assert response.status_code == 201, response.text
    return response.json()["project"]["id"]


def _definition(client, project_id: str, code: str = "PFD-V03") -> dict:
    response = client.post(
        "/api/v1/process-definitions",
        json={
            "code": code,
            "title": "Measure",
            "project_scope_id": project_id,
            "execution_field_definitions": {
                "temperature": {"label": "Temperature", "value_type": "number"}
            },
        },
    )
    assert response.status_code == 201, response.text
    return response.json()


def _object(
    client, project_id: str, code: str, title: str, *, kind: str = "research_object"
) -> dict:
    response = client.post(
        "/api/v1/objects",
        json={"kind": kind, "code": code, "title": title, "project_scope_id": project_id},
    )
    assert response.status_code == 201, response.text
    return response.json()


def test_process_execution_enforces_binding_kinds_and_one_data_producer(client):
    project_id = _project(client)
    definition = _definition(client, project_id)
    subject = _object(client, project_id, "ROO-SUBJECT", "Subject")
    data = _object(client, project_id, "DAT-V03", "Output", kind="data")
    payload = {
        "process_definition_id": definition["process_definition"]["id"],
        "project_scope_id": project_id,
        "object_bindings": [
            {"research_object_id": subject["id"], "direction": "input", "role": "subject"}
        ],
        "data_bindings": [{"data_id": data["id"], "direction": "output"}],
        "status": "completed",
    }
    created = client.post("/api/v1/process-executions", json=payload)
    assert created.status_code == 201, created.text

    duplicate = client.post("/api/v1/process-executions", json=payload)
    assert duplicate.status_code == 409
    assert duplicate.json()["detail"]["error"]["code"] == "data_already_has_producer"

    invalid_target = client.post(
        "/api/v1/process-executions",
        json={
            **payload,
            "data_bindings": [],
            "object_bindings": [
                {"research_object_id": data["id"], "direction": "input", "role": "subject"}
            ],
        },
    )
    assert invalid_target.status_code == 409
    assert invalid_target.json()["detail"]["error"]["code"] == "invalid_binding_target"


def test_sample_update_preserves_execution_identity_and_order(client):
    project_id = _project(client)
    first = _definition(client, project_id, "PFD-FIRST")
    second = _definition(client, project_id, "PFD-SECOND")
    created = client.post(
        "/api/v1/sample-records",
        json={
            "project_scope_id": project_id,
            "sample": {"code": "ROO-SAMPLE-V03", "title": "Sample", "tags": ["样品"]},
            "steps": [
                {"process_definition_id": first["process_definition"]["id"], "values": {"n": 1}},
                {"process_definition_id": second["process_definition"]["id"], "values": {"n": 2}},
            ],
        },
    )
    assert created.status_code == 201, created.text
    body = created.json()
    first_id, second_id = [step["execution"]["id"] for step in body["steps"]]
    updated = client.put(
        f"/api/v1/samples/{body['sample']['id']}/record",
        json={
            "steps": [
                {
                    "execution_id": second_id,
                    "process_definition_id": second["process_definition"]["id"],
                    "values": {"n": 20},
                },
                {
                    "execution_id": first_id,
                    "process_definition_id": first["process_definition"]["id"],
                    "values": {"n": 10},
                },
            ]
        },
    )
    assert updated.status_code == 200, updated.text
    result = updated.json()
    assert [step["execution"]["id"] for step in result["steps"]] == [second_id, first_id]
    assert [step["execution"]["values"]["n"] for step in result["steps"]] == [20, 10]


def test_definition_versions_and_representations_are_immutable(client, db):
    project_id = _project(client)
    definition = _definition(client, project_id, "PFD-IMMUTABLE")
    version = db.get(ProcessDefinitionVersion, definition["current_version"]["id"])
    assert version is not None
    version.description = "mutated"
    try:
        db.commit()
    except ValueError as exc:
        assert "immutable" in str(exc)
        db.rollback()
    else:
        raise AssertionError("ProcessDefinitionVersion accepted an in-place mutation")

    data = client.post(
        "/api/v1/data-records",
        json={
            "project_scope_id": project_id,
            "data": {"code": "DAT-IMMUTABLE", "title": "Data"},
        },
    )
    assert data.status_code == 201, data.text
    representation = client.post(
        f"/api/v1/data/{data.json()['data']['id']}/representations",
        json={"kind": "table", "name": "raw", "inline_payload_jsonb": {"rows": []}},
    )
    assert representation.status_code == 201, representation.text
    item = db.get(DataRepresentation, representation.json()["id"])
    assert item is not None
    item.name = "mutated"
    try:
        db.commit()
    except ValueError as exc:
        assert "immutable" in str(exc)
        db.rollback()
    else:
        raise AssertionError("DataRepresentation accepted an in-place mutation")


def test_view_revision_is_pinned_on_process_execution(client):
    project_id = _project(client)
    definition = _definition(client, project_id, "PFD-VIEW")
    data = client.post(
        "/api/v1/data-records",
        json={
            "project_scope_id": project_id,
            "data": {"code": "DAT-VIEW", "title": "View input"},
        },
    )
    assert data.status_code == 201, data.text
    data_id = data.json()["data"]["id"]
    view = client.post(
        "/api/v1/views",
        json={"project_scope_id": project_id, "title": "Pinned view", "data_ids": [data_id]},
    )
    assert view.status_code == 201, view.text
    view_body = view.json()
    revision_id = view_body["current_revision_id"]
    execution = client.post(
        "/api/v1/process-executions",
        json={
            "process_definition_id": definition["process_definition"]["id"],
            "project_scope_id": project_id,
            "source_view_id": view_body["view"]["id"],
            "source_view_revision_id": revision_id,
        },
    )
    assert execution.status_code == 201, execution.text
    assert execution.json()["source_view_revision_id"] == revision_id


def test_claim_evidence_cycle_is_rejected(client, db):
    project_id = _project(client)
    first = create_claim(
        db,
        ClaimCreate(
            project_scope_id=project_id,
            title="Claim A",
            statement="A",
        ),
    )
    second = create_claim(
        db,
        ClaimCreate(
            project_scope_id=project_id,
            title="Claim B",
            statement="B",
        ),
    )
    claim_b = second["claim"]["id"]
    claim_a = first["claim"]["id"]
    update_claim(
        db,
        claim_a,
        ClaimPut(
            change_note="evidence",
            evidence=[{"evidence_kind": "claim", "evidence_id": claim_b}],
        ),
    )
    try:
        update_claim(
            db,
            claim_b,
            ClaimPut(
                change_note="cycle",
                evidence=[{"evidence_kind": "claim", "evidence_id": claim_a}],
            ),
        )
    except Exception as exc:
        assert getattr(exc, "code", None) == "cycle_detected"
    else:
        raise AssertionError("Claim evidence cycle was accepted")


def test_changeset_create_records_target_identity(client):
    project_id = _project(client)
    proposal = client.post(
        "/api/v1/change-sets/propose",
        json={
            "project_scope_id": project_id,
            "operation_kind": "create_research_object",
            "request_payload_jsonb": {
                "kind": "research_object",
                "code": "ROO-CHANGESET",
                "title": "ChangeSet object",
                "project_scope_id": project_id,
            },
        },
    )
    assert proposal.status_code == 201, proposal.text
    change_set_id = proposal.json()["id"]
    applied = client.post(f"/api/v1/change-sets/{change_set_id}/apply")
    assert applied.status_code == 200, applied.text
    body = applied.json()
    assert body["status"] == "applied"
    assert body["target_id"] is not None

    unsupported = client.post(
        "/api/v1/change-sets/propose",
        json={
            "project_scope_id": project_id,
            "operation_kind": "update_process_definition",
            "request_payload_jsonb": {},
        },
    )
    assert unsupported.status_code == 422


def test_asset_upload_uses_opaque_key_and_blocks_referenced_delete(client, monkeypatch, tmp_path):
    import app.routers.objects as objects_router

    monkeypatch.setattr(
        objects_router,
        "_storage",
        lambda: StorageRouter(LocalStorageProvider(tmp_path)),
    )
    project_id = _project(client)
    obj = _object(client, project_id, "ROO-ASSET", "Asset owner")
    uploaded = client.post(
        f"/api/v1/objects/{obj['id']}/assets",
        files={"file": ("../../unsafe/report.csv", b"a,b\n1,2\n", "text/csv")},
    )
    assert uploaded.status_code == 201, uploaded.text
    asset = uploaded.json()
    assert asset["object_key"].startswith("objects/")
    assert "report.csv" not in asset["object_key"]
    assert asset["size_bytes"] == 8
    blocked = client.delete(f"/api/v1/assets/{asset['id']}")
    assert blocked.status_code == 409
    assert blocked.json()["detail"]["error"]["code"] == "asset_in_use"
