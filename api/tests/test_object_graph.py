from __future__ import annotations

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select

from app.core.config import get_settings
from app.main import app
from app.models import ObjectRelation, ObjectType, ObjectTypeVersion, ResearchObject
from app.schemas import ObjectCreate, RelationCreate
from app.seed import _schema
from app.services import create_object, create_relation, sha256_json

client = TestClient(app)

TYPE_LABELS = {
    "material": ("原料 / 试剂", "Material / reagent"),
    "sample": ("样品", "Sample"),
    "equipment": ("设备", "Equipment"),
    "process": ("过程 / 操作", "Process"),
    "data": ("数据 / 测试结果", "Data / test result"),
    "experiment": ("实验", "Experiment"),
    "project": ("项目 / Vault", "Project / Vault"),
}


def install_types(db) -> dict[str, ObjectTypeVersion]:
    versions = {}
    for kind, (zh, en) in TYPE_LABELS.items():
        object_type = ObjectType(key=f"{kind}.generic", kind=kind, label_zh=zh, label_en=en)
        db.add(object_type)
        db.flush()
        version = ObjectTypeVersion(
            object_type_id=object_type.id, version=1, json_schema=_schema(kind), is_active=True
        )
        db.add(version)
        db.flush()
        versions[kind] = version
    db.commit()
    return versions


def make(db, kind: str, title: str, scope=None, code=None, properties=None) -> ResearchObject:
    return create_object(
        db,
        ObjectCreate(
            kind=kind,
            title=title,
            code=code,
            project_scope_id=scope,
            properties_jsonb=properties or {},
        ),
    )


def graph(db):
    install_types(db)
    project = make(db, "project", "Project")
    experiment = make(db, "experiment", "Experiment", project.id)
    material = make(db, "material", "Material", project.id)
    equipment = make(db, "equipment", "Equipment", project.id)
    process0 = make(db, "process", "Prepare", project.id)
    process1 = make(db, "process", "Modify", project.id)
    process_branch = make(db, "process", "Branch", project.id)
    sample0 = make(db, "sample", "S0", project.id)
    sample1 = make(db, "sample", "S1", project.id)
    sample2 = make(db, "sample", "S2", project.id)
    sample_branch = make(db, "sample", "S-branch", project.id)
    data0 = make(db, "data", "D0", project.id)
    data1 = make(db, "data", "D1", project.id)
    create_relation(
        db,
        RelationCreate(
            source_object_id=experiment.id, target_object_id=process1.id, relation_type="contains"
        ),
    )
    create_relation(
        db,
        RelationCreate(
            source_object_id=experiment.id, target_object_id=sample1.id, relation_type="contains"
        ),
    )
    create_relation(
        db,
        RelationCreate(
            source_object_id=experiment.id, target_object_id=data1.id, relation_type="contains"
        ),
    )
    create_relation(
        db,
        RelationCreate(
            source_object_id=process0.id,
            target_object_id=material.id,
            relation_type="uses",
            role="material",
        ),
    )
    create_relation(
        db,
        RelationCreate(
            source_object_id=process0.id,
            target_object_id=equipment.id,
            relation_type="uses",
            role="equipment",
        ),
    )
    create_relation(
        db,
        RelationCreate(
            source_object_id=process0.id, target_object_id=sample0.id, relation_type="produces"
        ),
    )
    create_relation(
        db,
        RelationCreate(
            source_object_id=process0.id, target_object_id=data0.id, relation_type="produces"
        ),
    )
    create_relation(
        db,
        RelationCreate(
            source_object_id=process0.id,
            target_object_id=sample0.id,
            relation_type="uses",
            role="subject",
        ),
    )
    create_relation(
        db,
        RelationCreate(
            source_object_id=process1.id,
            target_object_id=sample0.id,
            relation_type="uses",
            role="precursor",
        ),
    )
    create_relation(
        db,
        RelationCreate(
            source_object_id=process1.id,
            target_object_id=material.id,
            relation_type="uses",
            role="additive",
            properties_jsonb={"quantity": {"value": 1, "unit": "g"}},
        ),
    )
    create_relation(
        db,
        RelationCreate(
            source_object_id=process1.id,
            target_object_id=equipment.id,
            relation_type="uses",
            role="equipment",
        ),
    )
    create_relation(
        db,
        RelationCreate(
            source_object_id=process1.id, target_object_id=sample1.id, relation_type="produces"
        ),
    )
    create_relation(
        db,
        RelationCreate(
            source_object_id=process1.id, target_object_id=data1.id, relation_type="produces"
        ),
    )
    create_relation(
        db,
        RelationCreate(
            source_object_id=process1.id,
            target_object_id=sample1.id,
            relation_type="uses",
            role="subject",
        ),
    )
    create_relation(
        db,
        RelationCreate(
            source_object_id=process_branch.id,
            target_object_id=sample0.id,
            relation_type="uses",
            role="precursor",
        ),
    )
    create_relation(
        db,
        RelationCreate(
            source_object_id=process_branch.id,
            target_object_id=sample_branch.id,
            relation_type="produces",
        ),
    )
    create_relation(
        db,
        RelationCreate(
            source_object_id=process1.id, target_object_id=sample2.id, relation_type="produces"
        ),
    )
    return locals()


def test_postgres_only_and_seven_kinds(db):
    assert db.get_bind().dialect.name == "postgresql"
    install_types(db)
    project = make(db, "project", "Project")
    for kind in TYPE_LABELS:
        if kind == "project":
            continue
        scope = None if kind in {"material", "equipment"} else project.id
        assert make(db, kind, kind, scope).kind == kind


def test_schema_rejects_unknown_and_invalid_quantity(db):
    install_types(db)
    project = make(db, "project", "Project")
    response = client.post(
        "/api/v1/objects",
        json={
            "kind": "sample",
            "title": "bad",
            "project_scope_id": str(project.id),
            "properties_jsonb": {"unknown": True},
        },
    )
    assert response.status_code == 422
    process = make(db, "process", "Process", project.id)
    material = make(db, "material", "Material", project.id)
    response = client.post(
        "/api/v1/relations",
        json={
            "source_object_id": str(process.id),
            "target_object_id": str(material.id),
            "relation_type": "uses",
            "properties_jsonb": {"quantity": {"value": "1", "unit": "g"}},
        },
    )
    assert response.status_code == 422


def test_scope_and_relation_rules(db):
    values = graph(db)
    response = client.post(
        "/api/v1/relations",
        json={
            "source_object_id": str(values["material"].id),
            "target_object_id": str(values["sample1"].id),
            "relation_type": "produces",
        },
    )
    assert response.status_code == 422
    response = client.post(
        "/api/v1/relations",
        json={
            "source_object_id": str(values["sample1"].id),
            "target_object_id": str(values["sample1"].id),
            "relation_type": "related_to",
        },
    )
    assert response.status_code == 422
    response = client.post(
        "/api/v1/relations",
        json={
            "source_object_id": str(values["process1"].id),
            "target_object_id": str(values["sample0"].id),
            "relation_type": "uses",
            "role": "precursor",
        },
    )
    assert response.status_code == 409


def test_search_alias_and_object_crud(db):
    values = graph(db)
    response = client.get(
        "/api/v1/objects", params={"q": "@sample", "project_scope_id": str(values["project"].id)}
    )
    assert response.status_code == 200
    assert {item["kind"] for item in response.json()} == {"sample"}
    response = client.patch(
        f"/api/v1/objects/{values['sample1'].id}",
        json={"title": "S1 updated", "properties_jsonb": {"batch": "v2"}},
    )
    assert response.status_code == 200
    assert response.json()["title"] == "S1 updated"


def test_revision_snapshot_is_immutable(db):
    values = graph(db)
    first = client.post(
        f"/api/v1/objects/{values['sample1'].id}/revisions", json={"change_note": "checkpoint"}
    )
    assert first.status_code == 200 or first.status_code == 201
    snapshot = first.json()["snapshot_jsonb"]
    digest = first.json()["snapshot_sha256"]
    relation = db.scalar(
        select(ObjectRelation)
        .where(ObjectRelation.target_object_id == values["sample1"].id)
        .limit(1)
    )
    assert relation is not None
    db.delete(relation)
    db.commit()
    historical = client.get(f"/api/v1/objects/{values['sample1'].id}/revisions/1").json()
    assert historical["snapshot_jsonb"] == snapshot
    assert historical["snapshot_sha256"] == digest == sha256_json(snapshot)


def test_sample_context_separates_direct_upstream_downstream_data(db):
    values = graph(db)
    response = client.get(f"/api/v1/samples/{values['sample1'].id}/context", params={"depth": 4})
    assert response.status_code == 200
    context = response.json()
    assert context["current"]["code"] == values["sample1"].code
    assert values["sample0"].code in {
        item["code"] for item in context["direct"]["precursor_samples"]
    }
    assert values["data1"].code in {item["code"] for item in context["direct"]["data"]}
    assert values["data0"].code in {item["code"] for item in context["upstream"]["data"]}
    assert values["data0"].code not in {item["code"] for item in context["direct"]["data"]}
    assert values["sample2"].code in {item["code"] for item in context["downstream"]["samples"]}
    assert values["sample_branch"].code in {
        item["code"] for item in context["downstream"]["samples"]
    }


def test_context_depth_is_bounded_and_cycle_safe(db):
    values = graph(db)
    response = client.get(f"/api/v1/samples/{values['sample1'].id}/context", params={"depth": 9})
    assert response.status_code == 422
    # An allowed weak edge cannot make the provenance endpoint recurse forever.
    client.post(
        "/api/v1/relations",
        json={
            "source_object_id": str(values["sample0"].id),
            "target_object_id": str(values["sample1"].id),
            "relation_type": "related_to",
        },
    )
    response = client.get(f"/api/v1/samples/{values['sample1'].id}/context", params={"depth": 3})
    assert response.status_code == 200


def test_object_type_versions_are_immutable(db):
    versions = install_types(db)
    version = versions["sample"]
    version.json_schema = {"type": "object"}
    with pytest.raises(ValueError, match="immutable"):
        db.commit()
    db.rollback()


def test_data_import_preview_commit_and_provenance_delete_guard(db, monkeypatch, tmp_path):
    values = graph(db)
    monkeypatch.setattr(get_settings(), "storage_root", tmp_path)
    response = client.post(
        f"/api/v1/objects/{values['data0'].id}/attachments",
        files={"file": ("spectrum.csv", b"x,y\n1,2\n2,3\n", "text/csv")},
    )
    assert response.status_code == 201
    attachment = response.json()

    preview = client.post(
        f"/api/v1/data/{values['data0'].id}/imports/preview",
        json={"source_attachment_id": attachment["id"]},
    )
    assert preview.status_code == 201
    preview_body = preview.json()
    assert preview_body["headers"] == ["x", "y"]
    assert preview_body["row_count"] == 2

    committed = client.post(
        f"/api/v1/data/{values['data0'].id}/imports/{preview_body['id']}/commit",
        json={
            "payload_name": "Imported spectrum",
            "x": {"column": "x", "label": "Time", "unit": "s"},
            "y": {"column": "y", "label": "Signal", "unit": "a.u."},
        },
    )
    assert committed.status_code == 201
    payload = committed.json()
    assert payload["points_count"] == 2
    points = client.get(f"/api/v1/data-payloads/{payload['id']}/points")
    assert points.status_code == 200
    assert [point["y_value"] for point in points.json()] == [2, 3]

    blocked = client.delete(f"/api/v1/attachments/{attachment['id']}")
    assert blocked.status_code == 409

    duplicate = client.post(
        f"/api/v1/data/{values['data0'].id}/imports/{preview_body['id']}/commit",
        json={
            "payload_name": "Duplicate",
            "x": {"column": "x", "label": "Time", "unit": "s"},
            "y": {"column": "y", "label": "Signal", "unit": "a.u."},
        },
    )
    assert duplicate.status_code == 409
