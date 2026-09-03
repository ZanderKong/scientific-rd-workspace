from __future__ import annotations

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select

from app.core.config import get_settings
from app.main import app
from app.models import ObjectRelation, ObjectType, ObjectTypeVersion, ResearchObject
from app.schemas import ObjectCreate, RelationCreate
from app.seed import _schema
from app.services import create_object, create_relation, get_type_version, sha256_json

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
        object_type = ObjectType(
            key=f"{kind}.generic",
            kind=kind,
            label_zh=zh,
            label_en=en,
            is_default=True,
        )
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
            target_object_id=sample1.id,
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
            source_object_id=process_branch.id,
            target_object_id=sample2.id,
            relation_type="produces",
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


def test_sample_roles_are_normalized_and_only_subject_drives_current_data(db):
    values = graph(db)
    extra_sample = make(db, "sample", "Extra role sample", values["project"].id)
    for role, target in (
        ("reference", values["sample0"]),
        ("参照", values["sample2"]),
        ("control", values["sample_branch"]),
        ("对照样品", extra_sample),
    ):
        response = client.post(
            "/api/v1/relations",
            json={
                "source_object_id": str(values["process1"].id),
                "target_object_id": str(target.id),
                "relation_type": "uses",
                "role": role,
            },
        )
        assert response.status_code == 201
    alias_duplicate = client.post(
        "/api/v1/relations",
        json={
            "source_object_id": str(values["process1"].id),
            "target_object_id": str(values["sample0"].id),
            "relation_type": "uses",
            "role": "参考样品",
        },
    )
    assert alias_duplicate.status_code == 409
    missing_role = client.post(
        "/api/v1/relations",
        json={
            "source_object_id": str(values["process1"].id),
            "target_object_id": str(values["sample2"].id),
            "relation_type": "uses",
        },
    )
    assert missing_role.status_code == 422
    context = client.get(f"/api/v1/samples/{values['sample1'].id}/context").json()
    assert values["data1"].code in {item["code"] for item in context["direct"]["data"]}
    assert values["data0"].code not in {item["code"] for item in context["direct"]["data"]}
    assert {item["role"] for item in context["direct"]["sample_inputs"]} == {
        "precursor",
        "reference",
        "control",
        "subject",
    }


def test_one_owner_and_one_producer_are_enforced(db):
    values = graph(db)
    other_experiment = make(db, "experiment", "Other experiment", values["project"].id)
    owner_conflict = client.post(
        "/api/v1/relations",
        json={
            "source_object_id": str(other_experiment.id),
            "target_object_id": str(values["sample1"].id),
            "relation_type": "contains",
        },
    )
    assert owner_conflict.status_code == 409
    producer_conflict = client.post(
        "/api/v1/relations",
        json={
            "source_object_id": str(values["process0"].id),
            "target_object_id": str(values["sample1"].id),
            "relation_type": "produces",
        },
    )
    assert producer_conflict.status_code == 409


def test_lineage_and_precedes_cycles_are_rejected(db):
    values = graph(db)
    process_a = make(db, "process", "Cycle A", values["project"].id)
    process_b = make(db, "process", "Cycle B", values["project"].id)
    sample_a = make(db, "sample", "Cycle sample A", values["project"].id)
    sample_b = make(db, "sample", "Cycle sample B", values["project"].id)
    for source, target, relation_type, role in [
        (process_a, sample_b, "uses", "precursor"),
        (process_a, sample_a, "produces", None),
        (process_b, sample_a, "uses", "precursor"),
    ]:
        create_relation(
            db,
            RelationCreate(
                source_object_id=source.id,
                target_object_id=target.id,
                relation_type=relation_type,
                role=role,
            ),
        )
    cycle = client.post(
        "/api/v1/relations",
        json={
            "source_object_id": str(process_b.id),
            "target_object_id": str(sample_b.id),
            "relation_type": "produces",
        },
    )
    assert cycle.status_code == 409
    create_relation(
        db,
        RelationCreate(
            source_object_id=process_a.id,
            target_object_id=process_b.id,
            relation_type="precedes",
        ),
    )
    precedes_cycle = client.post(
        "/api/v1/relations",
        json={
            "source_object_id": str(process_b.id),
            "target_object_id": str(process_a.id),
            "relation_type": "precedes",
        },
    )
    assert precedes_cycle.status_code == 409


def test_scope_mutation_revalidates_existing_relations(db):
    values = graph(db)
    other_project = make(db, "project", "Other project")
    response = client.patch(
        f"/api/v1/objects/{values['sample1'].id}",
        json={"project_scope_id": str(other_project.id)},
    )
    assert response.status_code == 422


def test_default_type_selects_highest_active_version_and_identity_is_immutable(db):
    versions = install_types(db)
    versions["sample"].object_type.is_default = False
    custom = ObjectType(
        key="sample.special",
        kind="sample",
        label_zh="特殊样品",
        label_en="Special sample",
        is_default=True,
    )
    db.add(custom)
    db.flush()
    db.add(
        ObjectTypeVersion(
            object_type_id=custom.id,
            version=1,
            json_schema=_schema("sample"),
            is_active=True,
        )
    )
    version2 = ObjectTypeVersion(
        object_type_id=custom.id,
        version=2,
        json_schema=_schema("sample"),
        is_active=True,
    )
    db.add(version2)
    db.commit()
    project = make(db, "project", "Project")
    sample = make(db, "sample", "Sample", project.id)
    assert sample.type_version_id == version2.id
    assert get_type_version(db, "sample").id == version2.id
    custom.key = "sample.renamed"
    with pytest.raises(ValueError, match="identity is immutable"):
        db.commit()
    db.rollback()


def test_experiment_context_exposes_cross_experiment_inputs(db):
    values = graph(db)
    context = client.get(f"/api/v1/experiments/{values['experiment'].id}/context")
    assert context.status_code == 200
    assert values["sample0"].code in {item["code"] for item in context.json()["input_samples"]}
    assert values["sample0"].code not in {item["code"] for item in context.json()["samples"]}


def test_process_composition_is_desired_state_atomic_and_auto_owns_outputs(db):
    values = graph(db)
    composition = client.get(f"/api/v1/processes/{values['process1'].id}/composition")
    assert composition.status_code == 200
    body = composition.json()
    items = [
        {
            "relation_id": relation["id"],
            "relation_type": relation["relation_type"],
            "target_object_id": relation["target_object_id"],
            "role": relation["role"],
            "properties_jsonb": relation["properties_jsonb"],
        }
        for relation in body["uses"] + body["produces"]
    ]
    items.append(
        {
            "relation_type": "produces",
            "create_target": {"kind": "sample", "title": "Atomic output"},
        }
    )
    saved = client.put(
        f"/api/v1/processes/{values['process1'].id}/composition", json={"items": items}
    )
    assert saved.status_code == 200
    created = next(
        item for item in saved.json()["produces"] if item["target"]["title"] == "Atomic output"
    )
    owner = db.scalar(
        select(ObjectRelation).where(
            ObjectRelation.relation_type == "contains",
            ObjectRelation.target_object_id == created["target_object_id"],
        )
    )
    assert owner is not None and owner.source_object_id == values["experiment"].id

    failed = client.put(
        f"/api/v1/processes/{values['process1'].id}/composition",
        json={
            "items": [
                {
                    "relation_type": "produces",
                    "create_target": {"kind": "sample", "title": "Rolled back"},
                },
                {
                    "relation_type": "uses",
                    "target_object_id": str(values["experiment"].id),
                    "role": "subject",
                },
            ]
        },
    )
    assert failed.status_code == 422
    assert db.scalar(select(ResearchObject).where(ResearchObject.title == "Rolled back")) is None


def test_search_filters_are_applied_before_pagination(db):
    values = graph(db)
    response = client.get(
        "/api/v1/objects",
        params=[
            ("kinds", "sample"),
            ("kinds", "data"),
            ("project_scope_id", str(values["project"].id)),
            ("type_key", "sample.generic"),
            ("limit", 1),
            ("offset", 0),
        ],
    )
    assert response.status_code == 200
    assert len(response.json()) == 1
    assert response.json()[0]["kind"] == "sample"
