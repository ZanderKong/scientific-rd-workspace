from __future__ import annotations

from sqlalchemy import func, select
from test_object_graph import client, graph, install_types, make

from app.models import ObjectRelation, ObjectType, ResearchObject
from app.schemas import ObjectCreate, RelationCreate
from app.services import create_object, create_relation

MATERIAL_USAGE = {
    "fields": [
        {
            "key": "quantity",
            "label": "用量",
            "value_type": "number",
            "default_unit": "g",
            "required": False,
            "options": [],
            "order": 0,
        }
    ]
}
EQUIPMENT_USAGE = {
    "fields": [
        {
            "key": "rpm",
            "label": "转速",
            "value_type": "number",
            "default_unit": "rpm",
            "required": False,
            "options": [],
            "order": 0,
        }
    ]
}


def test_usage_schema_round_trips_and_is_in_revision_snapshot(db):
    versions = install_types(db)
    project = make(db, "project", "Project")
    material = create_object(
        db,
        ObjectCreate(
            kind="material",
            title="KI",
            project_scope_id=project.id,
            properties_jsonb={"cas": "7681-11-0"},
            usage_schema_jsonb=MATERIAL_USAGE,
        ),
    )
    assert material.usage_schema_jsonb["fields"][0]["key"] == "quantity"
    response = client.get(f"/api/v1/objects/{material.id}")
    assert response.status_code == 200
    assert response.json()["usage_schema_jsonb"]["fields"][0]["key"] == "quantity"
    revision = client.post(
        f"/api/v1/objects/{material.id}/revisions", json={"change_note": "schema"}
    )
    assert revision.status_code in {200, 201}
    assert revision.json()["snapshot_jsonb"]["object"]["usage_schema_jsonb"] == MATERIAL_USAGE
    assert versions["material"].object_type.kind == "material"


def test_usage_schema_is_only_meaningful_for_resources(db):
    install_types(db)
    project = make(db, "project", "Project")
    response = client.post(
        "/api/v1/objects",
        json={
            "kind": "sample",
            "title": "Sample",
            "project_scope_id": str(project.id),
            "usage_schema_jsonb": MATERIAL_USAGE,
        },
    )
    assert response.status_code == 422


def test_usage_values_shape_and_resource_identity_search(db):
    install_types(db)
    project = make(db, "project", "Project")
    material = create_object(
        db,
        ObjectCreate(
            kind="material",
            title="Potassium iodide",
            project_scope_id=project.id,
            properties_jsonb={"cas": "7681-11-0"},
            usage_schema_jsonb=MATERIAL_USAGE,
        ),
    )
    equipment = create_object(
        db,
        ObjectCreate(
            kind="equipment",
            title="Mixer",
            project_scope_id=project.id,
            properties_jsonb={"asset_number": "MX-03"},
            usage_schema_jsonb=EQUIPMENT_USAGE,
        ),
    )
    process = make(db, "process", "Mix", project.id)
    bad = client.post(
        "/api/v1/relations",
        json={
            "source_object_id": str(process.id),
            "target_object_id": str(material.id),
            "relation_type": "uses",
            "role": "material",
            "properties_jsonb": {"usage_values": {"quantity": {"unit": "g"}}},
        },
    )
    assert bad.status_code == 422
    by_cas = client.get(
        "/api/v1/objects",
        params={"q": "7681-11-0", "project_scope_id": str(project.id)},
    )
    assert {item["id"] for item in by_cas.json()} == {str(material.id)}
    by_asset = client.get(
        "/api/v1/objects",
        params={"q": "MX-03", "project_scope_id": str(project.id)},
    )
    assert {item["id"] for item in by_asset.json()} == {str(equipment.id)}


def _create_record(
    db,
    *,
    include_equipment: bool = True,
    step_titles: tuple[str, ...] = ("Mixing", "Drying"),
) -> tuple[dict, ResearchObject, ResearchObject]:
    if db.scalar(select(ObjectType).limit(1)) is None:
        install_types(db)
    project = make(db, "project", "Project")
    material = create_object(
        db,
        ObjectCreate(
            kind="material",
            title="Potassium iodide",
            project_scope_id=project.id,
            properties_jsonb={"cas": "7681-11-0", "supplier": "Synthetic"},
            usage_schema_jsonb=MATERIAL_USAGE,
        ),
    )
    equipment = create_object(
        db,
        ObjectCreate(
            kind="equipment",
            title="Mixer MX-03",
            project_scope_id=project.id,
            properties_jsonb={"asset_number": "MX-03"},
            usage_schema_jsonb=EQUIPMENT_USAGE,
        ),
    )
    resources = [
        {
            "target_object_id": str(material.id),
            "role": "material",
            "usage_values": {"quantity": {"value": 1.0, "unit": "g"}},
        }
    ]
    if include_equipment:
        resources.append(
            {
                "target_object_id": str(equipment.id),
                "role": "equipment",
                "usage_values": {"rpm": {"value": 700, "unit": "rpm"}},
            }
        )
    response = client.post(
        "/api/v1/sample-records",
        json={
            "project_scope_id": str(project.id),
            "sample": {
                "title": "KI strip",
                "properties_jsonb": {"batch": "draft-01"},
            },
            "steps": [
                {
                    "title": step_titles[0],
                    "properties_jsonb": {
                        "parameters": {"temperature": {"value": 25, "unit": "°C"}}
                    },
                    "resources": resources,
                },
                *({"title": title, "resources": []} for title in step_titles[1:]),
            ],
            "change_note": "record sample",
        },
    )
    assert response.status_code == 201, response.text
    return response.json(), material, equipment


def test_sample_record_create_is_aggregate_and_preserves_usage_values(db):
    record, material, equipment = _create_record(db)
    assert len(record["steps"]) == 2
    assert record["sample"]["kind"] == "sample"
    assert record["steps"][0]["resources"][0]["usage_values"]["quantity"]["value"] == 1.0
    assert record["steps"][0]["resources"][1]["usage_values"]["rpm"]["value"] == 700
    sample_id = record["sample"]["id"]
    process_ids = [step["process"]["id"] for step in record["steps"]]
    assert db.scalar(
        select(ObjectRelation).where(
            ObjectRelation.source_object_id == process_ids[0],
            ObjectRelation.target_object_id == process_ids[1],
            ObjectRelation.relation_type == "precedes",
        )
    )
    assert db.scalar(
        select(ObjectRelation).where(
            ObjectRelation.source_object_id == process_ids[1],
            ObjectRelation.target_object_id == sample_id,
            ObjectRelation.relation_type == "produces",
        )
    )
    assert db.get(ResearchObject, material.id).properties_jsonb["supplier"] == "Synthetic"
    assert db.get(ResearchObject, equipment.id).properties_jsonb["asset_number"] == "MX-03"


def test_sample_record_read_projection_supports_one_and_three_step_chains(db):
    one_step, _material, _equipment = _create_record(db, step_titles=("Mixing",))
    assert [step["ordinal"] for step in one_step["steps"]] == [0]
    assert one_step["editable"] is True

    three_step, _material, _equipment = _create_record(
        db, step_titles=("Mixing", "Drying", "Curing")
    )
    assert [step["process"]["title"] for step in three_step["steps"]] == [
        "Mixing",
        "Drying",
        "Curing",
    ]
    assert [step["ordinal"] for step in three_step["steps"]] == [0, 1, 2]
    assert three_step["editable"] is True


def test_sample_record_accepts_precursor_sample_without_reinterpreting_ownership(db):
    source, _material, _equipment = _create_record(
        db, include_equipment=False, step_titles=("Source",)
    )
    source_id = source["sample"]["id"]
    project_id = source["sample"]["project_scope_id"]
    response = client.post(
        "/api/v1/sample-records",
        json={
            "project_scope_id": project_id,
            "sample": {"title": "Downstream sample"},
            "steps": [
                {
                    "title": "Transform precursor",
                    "resources": [
                        {
                            "target_object_id": source_id,
                            "role": "precursor",
                        }
                    ],
                }
            ],
        },
    )
    assert response.status_code == 201, response.text
    body = response.json()
    assert body["editable"] is True
    assert body["steps"][0]["resources"][0]["object"]["id"] == source_id
    assert body["steps"][0]["resources"][0]["role"] == "precursor"
    assert client.get(f"/api/v1/samples/{source_id}/record").json()["sample"]["id"] == source_id


def test_sample_record_create_rolls_back_inline_objects_and_schema_changes(db):
    install_types(db)
    project = make(db, "project", "Project")
    before_count = db.scalar(
        select(func.count())
        .select_from(ResearchObject)
        .where(ResearchObject.project_scope_id == project.id)
    )
    response = client.post(
        "/api/v1/sample-records",
        json={
            "project_scope_id": str(project.id),
            "sample": {"title": "Should roll back"},
            "steps": [
                {
                    "title": "Invalid step",
                    "resources": [
                        {
                            "create_target": {
                                "kind": "material",
                                "title": "Inline material",
                                "properties_jsonb": {},
                            },
                            "usage_schema_additions": [
                                {
                                    "key": "quantity",
                                    "label": "用量",
                                    "value_type": "number",
                                    "default_unit": "g",
                                    "options": [],
                                    "order": 0,
                                }
                            ],
                            "usage_values": {"unknown": {"value": 2, "unit": "g"}},
                        }
                    ],
                }
            ],
        },
    )
    assert response.status_code == 422
    assert (
        db.scalar(select(ResearchObject).where(ResearchObject.title == "Should roll back")) is None
    )
    assert (
        db.scalar(select(ResearchObject).where(ResearchObject.title == "Inline material")) is None
    )
    after_count = db.scalar(
        select(func.count())
        .select_from(ResearchObject)
        .where(ResearchObject.project_scope_id == project.id)
    )
    assert after_count == before_count


def test_sample_record_edit_updates_relation_values_and_usage_schema(db):
    record, material, equipment = _create_record(db)
    first_step = record["steps"][0]
    material_relation = next(
        resource
        for resource in first_step["resources"]
        if resource["object"]["id"] == str(material.id)
    )
    equipment_relation = next(
        resource
        for resource in first_step["resources"]
        if resource["object"]["id"] == str(equipment.id)
    )
    response = client.put(
        f"/api/v1/samples/{record['sample']['id']}/record",
        json={
            "sample": {"title": "KI strip edited"},
            "steps": [
                {
                    "process_id": first_step["process"]["id"],
                    "title": "Mixing edited",
                    "properties_jsonb": {"parameters": {"duration": {"value": 12, "unit": "min"}}},
                    "resources": [
                        {
                            "relation_id": material_relation["relation_id"],
                            "target_object_id": str(material.id),
                            "role": "material",
                            "usage_values": {"quantity": {"value": 2.5, "unit": "g"}},
                        },
                        {
                            "relation_id": equipment_relation["relation_id"],
                            "target_object_id": str(equipment.id),
                            "role": "equipment",
                            "usage_values": {
                                "rpm": {"value": 900, "unit": "rpm"},
                                "torque": {"value": 2, "unit": "N m"},
                            },
                            "usage_schema_additions": [
                                {
                                    "key": "torque",
                                    "label": "扭矩",
                                    "value_type": "number",
                                    "default_unit": "N m",
                                    "options": [],
                                    "order": 1,
                                }
                            ],
                        },
                    ],
                },
                {
                    "process_id": record["steps"][1]["process"]["id"],
                    "title": "Drying",
                    "resources": [],
                },
            ],
            "change_note": "update usage",
        },
    )
    assert response.status_code == 200, response.text
    assert response.json()["sample"]["title"] == "KI strip edited"
    assert (
        response.json()["steps"][0]["resources"][1]["usage_values"]["torque"]["value"] == 2
    ), response.json()
    assert db.get(ResearchObject, material.id).properties_jsonb["supplier"] == "Synthetic"
    assert db.get(ResearchObject, equipment.id).properties_jsonb["asset_number"] == "MX-03"
    assert any(
        field["key"] == "torque"
        for field in db.get(ResearchObject, equipment.id).usage_schema_jsonb["fields"]
    )


def _retained_step_payload(step: dict) -> dict:
    return {
        "process_id": step["process"]["id"],
        "title": step["process"]["title"],
        "status": step["process"]["status"],
        "properties_jsonb": step["process"]["properties_jsonb"],
        "content_document": step["process"]["content_document"],
        "resources": [
            {
                "relation_id": resource["relation_id"],
                "target_object_id": resource["object"]["id"],
                "role": resource["role"],
                "usage_values": resource["usage_values"],
            }
            for resource in step["resources"]
        ],
    }


def test_sample_record_edit_reorders_and_adds_a_process_step(db):
    record, _material, _equipment = _create_record(db)
    reordered = client.put(
        f"/api/v1/samples/{record['sample']['id']}/record",
        json={
            "steps": [
                _retained_step_payload(record["steps"][1]),
                _retained_step_payload(record["steps"][0]),
            ]
        },
    )
    assert reordered.status_code == 200, reordered.text
    assert [step["process"]["id"] for step in reordered.json()["steps"]] == [
        record["steps"][1]["process"]["id"],
        record["steps"][0]["process"]["id"],
    ]

    added = client.put(
        f"/api/v1/samples/{record['sample']['id']}/record",
        json={
            "steps": [
                _retained_step_payload(reordered.json()["steps"][0]),
                _retained_step_payload(reordered.json()["steps"][1]),
                {"title": "Curing", "resources": []},
            ]
        },
    )
    assert added.status_code == 200, added.text
    assert [step["process"]["title"] for step in added.json()["steps"]] == [
        "Drying",
        "Mixing",
        "Curing",
    ]


def test_sample_record_edit_archives_a_safe_removed_step(db):
    record, _material, _equipment = _create_record(db)
    removed_id = record["steps"][0]["process"]["id"]
    response = client.put(
        f"/api/v1/samples/{record['sample']['id']}/record",
        json={"steps": [_retained_step_payload(record["steps"][1])]},
    )
    assert response.status_code == 200, response.text
    assert len(response.json()["steps"]) == 1
    assert db.get(ResearchObject, removed_id).status == "archived"
    assert db.get(ResearchObject, response.json()["steps"][0]["process"]["id"]).status == "active"


def test_sample_record_edit_rejects_removing_externally_referenced_process(db):
    record, _material, _equipment = _create_record(db)
    data = make(db, "data", "External data", record["sample"]["project_scope_id"])
    first_process_id = record["steps"][0]["process"]["id"]
    create_relation(
        db,
        RelationCreate(
            source_object_id=first_process_id,
            target_object_id=data.id,
            relation_type="produces",
        ),
    )
    response = client.put(
        f"/api/v1/samples/{record['sample']['id']}/record",
        json={"steps": [_retained_step_payload(record["steps"][1])]},
    )
    assert response.status_code == 409
    assert db.get(ResearchObject, first_process_id).status == "active"


def test_ambiguous_process_graph_is_readable_but_not_editable(db):
    values = graph(db)
    predecessor_a = make(db, "process", "Earlier A", values["project"].id)
    predecessor_b = make(db, "process", "Earlier B", values["project"].id)
    for predecessor in (predecessor_a, predecessor_b):
        create_relation(
            db,
            RelationCreate(
                source_object_id=predecessor.id,
                target_object_id=values["process1"].id,
                relation_type="precedes",
            ),
        )
    response = client.get(f"/api/v1/samples/{values['sample1'].id}/record")
    assert response.status_code == 200
    body = response.json()
    assert body["editable"] is False
    assert any("branches" in blocker for blocker in body["edit_blockers"])
