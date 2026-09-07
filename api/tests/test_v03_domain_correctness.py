from __future__ import annotations

import uuid

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


def test_removing_producer_preserves_manual_data_subject(client):
    project_id = _project(client)
    definition = _definition(client, project_id, "PFD-SUBJECT-SOURCES")
    manual_subject = _object(client, project_id, "ROO-MANUAL-SUBJECT", "Manual subject")
    producer_subject = _object(client, project_id, "ROO-PRODUCER-SUBJECT", "Producer subject")
    data_response = client.post(
        "/api/v1/data-records",
        json={
            "project_scope_id": project_id,
            "data": {"code": "DAT-SUBJECT-SOURCES", "title": "Sourced Data"},
            "subject_ids": [manual_subject["id"]],
        },
    )
    assert data_response.status_code == 201, data_response.text
    data_id = data_response.json()["data"]["id"]

    execution_response = client.post(
        "/api/v1/process-executions",
        json={
            "process_definition_id": definition["process_definition"]["id"],
            "project_scope_id": project_id,
            "status": "recorded",
            "object_bindings": [
                {
                    "research_object_id": producer_subject["id"],
                    "direction": "input",
                    "role": "subject",
                }
            ],
            "data_bindings": [{"data_id": data_id, "direction": "output"}],
        },
    )
    assert execution_response.status_code == 201, execution_response.text
    execution = execution_response.json()
    sourced = client.get(f"/api/v1/data/{data_id}/record").json()
    assert {item["id"] for item in sourced["subjects"]} == {
        manual_subject["id"],
        producer_subject["id"],
    }
    assert {item["source_kind"] for item in sourced["subject_assignments"]} == {
        "manual",
        "producer",
    }

    updated = client.put(
        f"/api/v1/process-executions/{execution['id']}",
        headers={"If-Match": execution["record_sha256"]},
        json={
            "process_definition_id": definition["process_definition"]["id"],
            "project_scope_id": project_id,
            "status": "recorded",
            "object_bindings": [],
            "data_bindings": [],
        },
    )
    assert updated.status_code == 200, updated.text
    remaining = client.get(f"/api/v1/data/{data_id}/record").json()
    assert [item["id"] for item in remaining["subjects"]] == [manual_subject["id"]]
    assert [item["source_kind"] for item in remaining["subject_assignments"]] == ["manual"]


def test_sample_update_preserves_execution_identity_and_order(client):
    project_id = _project(client)
    first = _definition(client, project_id, "PFD-FIRST")
    second = _definition(client, project_id, "PFD-SECOND")
    first_occurrence = str(uuid.uuid4())
    second_occurrence = str(uuid.uuid4())

    def occurrence(definition: dict, occurrence_id: str, value: int) -> dict:
        return {
            "occurrence_id": occurrence_id,
            "kind": "process",
            "target_id": definition["process_definition"]["id"],
            "process_definition_version_id": definition["current_version"]["id"],
            "field_definitions": definition["current_version"]["execution_field_definitions"],
            "values": {"temperature": value},
            "status": "recorded",
        }

    def document(*ids: str) -> dict:
        return {
            "schema_version": 1,
            "blocks": [
                {
                    "type": "paragraph",
                    "content": [
                        {"type": "processRef", "props": {"occurrenceId": item_id}}
                        for item_id in ids
                    ],
                }
            ],
        }

    created = client.post(
        "/api/v1/sample-records",
        json={
            "project_scope_id": project_id,
            "sample": {"code": "ROO-SAMPLE-V03", "title": "Sample", "tags": ["样品"]},
            "document": document(first_occurrence, second_occurrence),
            "occurrences": [
                occurrence(first, first_occurrence, 1),
                occurrence(second, second_occurrence, 2),
            ],
        },
        headers={"Idempotency-Key": "v03-sample-create"},
    )
    assert created.status_code == 201, created.text
    body = created.json()
    first_id, second_id = [item["execution_id"] for item in body["occurrences"]]
    updated = client.put(
        f"/api/v1/samples/{body['sample']['id']}/record",
        json={
            "document": document(second_occurrence, first_occurrence),
            "occurrences": [
                {
                    **occurrence(second, second_occurrence, 20),
                    "execution_id": second_id,
                },
                {
                    **occurrence(first, first_occurrence, 10),
                    "execution_id": first_id,
                },
            ],
            "base_record_sha256": body["record_sha256"],
        },
        headers={"If-Match": body["record_sha256"]},
    )
    assert updated.status_code == 200, updated.text
    result = updated.json()
    assert [item["execution_id"] for item in result["occurrences"]] == [second_id, first_id]
    assert [item["execution"]["values"]["temperature"] for item in result["occurrences"]] == [
        20,
        10,
    ]


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


def test_view_revision_is_pinned_on_process_execution(client, monkeypatch, tmp_path):
    import app.routers.objects as objects_router

    monkeypatch.setattr(
        objects_router,
        "_storage",
        lambda: StorageRouter(LocalStorageProvider(tmp_path)),
    )
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
    data_revision_id = client.get(f"/api/v1/objects/{data_id}/revisions").json()[-1]["id"]
    view = client.post(
        "/api/v1/views",
        json={
            "project_scope_id": project_id,
            "title": "Pinned view",
            "data_refs": [{"data_id": data_id, "data_revision_id": data_revision_id}],
        },
    )
    assert view.status_code == 201, view.text
    view_body = view.json()
    revision_id = view_body["current_revision_id"]
    assert view_body["data_refs"][0]["data_revision_id"] == data_revision_id
    changed_data = client.put(
        f"/api/v1/data/{data_id}/record",
        headers={"If-Match": data.json()["record_sha256"]},
        json={"title": "Corrected Data title"},
    )
    assert changed_data.status_code == 200, changed_data.text
    unchanged_view = client.get(f"/api/v1/views/{view_body['view']['id']}").json()
    assert unchanged_view["data_refs"][0]["data_revision_id"] == data_revision_id
    metadata_update = client.put(
        f"/api/v1/views/{view_body['view']['id']}",
        headers={"If-Match": unchanged_view["record_sha256"]},
        json={"description": "metadata only"},
    )
    assert metadata_update.status_code == 200, metadata_update.text
    assert metadata_update.json()["current_revision_id"] == revision_id
    uploaded = client.post(
        f"/api/v1/objects/{view_body['view']['id']}/assets",
        files={"file": ("figure.png", b"not-a-real-png", "image/png")},
    )
    assert uploaded.status_code == 201, uploaded.text
    artifact_update = client.put(
        f"/api/v1/views/{view_body['view']['id']}",
        headers={"If-Match": metadata_update.json()["record_sha256"]},
        json={"artifact_asset_id": uploaded.json()["id"]},
    )
    assert artifact_update.status_code == 200, artifact_update.text
    assert artifact_update.json()["current_revision_id"] != revision_id
    assert artifact_update.json()["artifact_sha256"] == uploaded.json()["sha256"]
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
    subject = _object(client, project_id, "ROO-CLAIM-SUBJECT", "Claim subject")
    source_response = client.post(
        "/api/v1/data-records",
        json={
            "project_scope_id": project_id,
            "data": {"code": "DAT-CLAIM-SOURCE", "title": "Claim source"},
            "subject_ids": [subject["id"]],
        },
    )
    assert source_response.status_code == 201, source_response.text
    source_id = source_response.json()["data"]["id"]
    source_revision_id = client.get(f"/api/v1/objects/{source_id}/revisions").json()[-1]["id"]
    primary_source = {
        "kind": "data",
        "object_id": source_id,
        "revision_id": source_revision_id,
    }
    first = create_claim(
        db,
        ClaimCreate(
            project_scope_id=project_id,
            title="Claim A",
            statement="A",
            primary_source=primary_source,
        ),
    )
    assert str(first["primary_source"]["revision_id"]) == source_revision_id
    original_context = first["context_snapshot"]
    assert original_context["subjects"][0]["subject_id"] == subject["id"]
    referencing = client.get(f"/api/v1/claims/by-reference/{source_id}")
    assert referencing.status_code == 200, referencing.text
    assert [item["claim"]["id"] for item in referencing.json()] == [str(first["claim"]["id"])]
    corrected = client.put(
        f"/api/v1/data/{source_id}/record",
        headers={"If-Match": source_response.json()["record_sha256"]},
        json={"title": "Corrected claim source", "subject_ids": []},
    )
    assert corrected.status_code == 200, corrected.text
    statement_only = update_claim(
        db,
        first["claim"]["id"],
        ClaimPut(statement="A refined", base_record_sha256=first["record_sha256"]),
    )
    assert str(statement_only["primary_source"]["revision_id"]) == source_revision_id
    assert statement_only["context_snapshot"] == original_context
    second = create_claim(
        db,
        ClaimCreate(
            project_scope_id=project_id,
            title="Claim B",
            statement="B",
            primary_source=primary_source,
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
            base_record_sha256=statement_only["record_sha256"],
        ),
    )
    try:
        update_claim(
            db,
            claim_b,
            ClaimPut(
                change_note="cycle",
                evidence=[{"evidence_kind": "claim", "evidence_id": claim_a}],
                base_record_sha256=second["record_sha256"],
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


def test_deleting_one_experiment_keeps_shared_reference_targets(client):
    project_id = _project(client)
    shared = _object(client, project_id, "ROO-SHARED", "Shared sample")
    first = client.post(
        "/api/v1/experiment-records",
        json={
            "project_scope_id": project_id,
            "experiment": {"code": "EXP-DELETE-A", "title": "Experiment A"},
            "references": [{"target_id": shared["id"], "role": "sample"}],
        },
    )
    second = client.post(
        "/api/v1/experiment-records",
        json={
            "project_scope_id": project_id,
            "experiment": {"code": "EXP-DELETE-B", "title": "Experiment B"},
            "references": [{"target_id": shared["id"], "role": "sample"}],
        },
    )
    assert first.status_code == 201, first.text
    assert second.status_code == 201, second.text
    deleted = client.delete(f"/api/v1/objects/{first.json()['experiment']['id']}")
    assert deleted.status_code == 204, deleted.text
    assert client.get(f"/api/v1/objects/{shared['id']}").status_code == 200
    remaining = client.get(f"/api/v1/experiments/{second.json()['experiment']['id']}/record")
    assert remaining.status_code == 200, remaining.text
    assert remaining.json()["references"]["research_object"][0]["object"]["id"] == shared["id"]


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
