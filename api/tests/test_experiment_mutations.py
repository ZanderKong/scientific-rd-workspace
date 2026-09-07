from __future__ import annotations


def test_experiment_metadata_and_reference_commands_are_independent(client):
    project_id = client.post(
        "/api/v1/project-records",
        json={"project": {"code": "PRJ-EXP-CMD", "title": "Experiment commands"}},
    ).json()["project"]["id"]
    samples = [
        client.post(
            "/api/v1/objects",
            json={
                "kind": "research_object",
                "code": f"EXP-SAMPLE-{index}",
                "title": f"Sample {index}",
                "project_scope_id": project_id,
                "tags": ["sample"],
            },
        ).json()
        for index in (1, 2)
    ]
    created = client.post(
        "/api/v1/experiment-records",
        json={
            "project_scope_id": project_id,
            "experiment": {"code": "EXP-CMD", "title": "Original"},
            "references": [
                {"target_id": samples[0]["id"], "target_kind": "research_object", "role": "sample"}
            ],
        },
    )
    assert created.status_code == 201, created.text
    body = created.json()
    metadata = client.patch(
        f"/api/v1/experiments/{body['experiment']['id']}/metadata",
        headers={"If-Match": body["record_sha256"]},
        json={"title": "Renamed"},
    )
    assert metadata.status_code == 200, metadata.text
    assert len(metadata.json()["references"]["research_object"]) == 1
    added = client.post(
        f"/api/v1/experiments/{body['experiment']['id']}/references",
        headers={"If-Match": metadata.json()["record_sha256"]},
        json={"target_id": samples[1]["id"], "target_kind": "research_object", "role": "sample"},
    )
    assert added.status_code == 200, added.text
    refs = added.json()["references"]["research_object"]
    reordered = client.put(
        f"/api/v1/experiments/{body['experiment']['id']}/reference-order",
        headers={"If-Match": added.json()["record_sha256"]},
        json={"relation_ids": [refs[1]["relation_id"], refs[0]["relation_id"]]},
    )
    assert reordered.status_code == 200, reordered.text
    ordered = reordered.json()["references"]["research_object"]
    assert [item["relation_id"] for item in ordered] == [
        refs[1]["relation_id"],
        refs[0]["relation_id"],
    ]
    removed = client.delete(
        f"/api/v1/experiments/{body['experiment']['id']}/references/{ordered[1]['relation_id']}",
        headers={"If-Match": reordered.json()["record_sha256"]},
    )
    assert removed.status_code == 200, removed.text
    assert len(removed.json()["references"]["research_object"]) == 1
