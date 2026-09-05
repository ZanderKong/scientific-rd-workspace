from __future__ import annotations

import uuid
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.claim_service import create_claim
from app.data_service import create_representation
from app.db import SessionLocal
from app.experiment_record_service import create_experiment_record
from app.models import ObjectType, ObjectTypeVersion, ResearchObject
from app.process_definition_service import create_process_definition
from app.process_execution_service import create_process_execution
from app.project_context_service import create_project_record
from app.schemas import (
    ClaimCreate,
    DataRepresentationCreate,
    ExperimentObjectCreate,
    ExperimentRecordCreate,
    ExperimentReferenceCreate,
    ObjectCreate,
    ProcessDefinitionCreate,
    ProcessExecutionCreate,
    ProcessExecutionDataBindingCreate,
    ProcessExecutionObjectBindingCreate,
    ProjectRecordCreate,
    ViewCreate,
)
from app.services import create_object
from app.view_service import create_view

TYPE_DEFINITIONS = [
    ("research_object.material", "research_object", "原料 / 试剂", "Material / reagent"),
    ("research_object.equipment", "research_object", "设备", "Equipment"),
    ("research_object.sample", "research_object", "样品", "Sample"),
    ("process_definition.generic", "process_definition", "过程定义", "Process Definition"),
    ("data.generic", "data", "数据", "Data"),
    ("experiment.generic", "experiment", "实验", "Experiment"),
    ("project.generic", "project", "项目", "Project"),
    ("view.generic", "view", "视图", "View"),
    ("claim.generic", "claim", "判断", "Claim"),
]


def _schema(kind: str) -> dict[str, Any]:
    if kind == "research_object":
        return {"type": "object", "additionalProperties": True}
    return {"type": "object", "additionalProperties": True}


def _type(db: Session, key: str, kind: str, label_zh: str, label_en: str) -> ObjectTypeVersion:
    item = db.scalar(select(ObjectType).where(ObjectType.key == key))
    if item is None:
        db.query(ObjectType).filter(
            ObjectType.kind == kind, ObjectType.is_default.is_(True)
        ).update({ObjectType.is_default: False}, synchronize_session=False)
        item = ObjectType(key=key, kind=kind, label_zh=label_zh, label_en=label_en, is_default=True)
        db.add(item)
        db.flush()
    else:
        item.label_zh = label_zh
        item.label_en = label_en
        db.query(ObjectType).filter(
            ObjectType.kind == kind, ObjectType.id != item.id, ObjectType.is_default.is_(True)
        ).update({ObjectType.is_default: False}, synchronize_session=False)
        item.is_default = True
    version = db.scalar(
        select(ObjectTypeVersion)
        .where(ObjectTypeVersion.object_type_id == item.id)
        .order_by(ObjectTypeVersion.version.desc())
    )
    if version is None:
        version = ObjectTypeVersion(
            object_type_id=item.id, version=1, json_schema=_schema(kind), is_active=True
        )
        db.add(version)
    else:
        version.is_active = True
    db.flush()
    return version


def ensure_default_object_types(db: Session) -> None:
    for definition in TYPE_DEFINITIONS:
        _type(db, *definition)
    db.commit()


def _object(
    db: Session,
    code: str,
    kind: str,
    title: str,
    *,
    scope: uuid.UUID | None = None,
    tags: list[str] | None = None,
    properties: dict[str, Any] | None = None,
    fields: dict[str, Any] | None = None,
) -> ResearchObject:
    item = db.scalar(select(ResearchObject).where(ResearchObject.code == code))
    if item is not None:
        return item
    return create_object(
        db,
        ObjectCreate(
            code=code,
            kind=kind,
            title=title,
            project_scope_id=scope,
            tags=tags or [],
            properties_jsonb=properties or {},
            process_field_definitions=fields or {},
        ),
    )


def _definition(db: Session, code: str, title: str, scope: uuid.UUID) -> ResearchObject:
    item = db.scalar(select(ResearchObject).where(ResearchObject.code == code))
    if item is not None:
        return item
    result = create_process_definition(
        db,
        ProcessDefinitionCreate(
            code=code,
            title=title,
            project_scope_id=scope,
            execution_field_definitions={
                "fields": [
                    {
                        "key": "temperature",
                        "label": "温度",
                        "value_type": "number",
                        "default_unit": "°C",
                    }
                ]
            },
        ),
    )
    return db.get(ResearchObject, result["process_definition"]["id"])


def seed() -> None:
    with SessionLocal() as db:
        ensure_default_object_types(db)
        if db.scalar(select(ResearchObject).where(ResearchObject.code == "PRJ-001")) is not None:
            return
        project = create_project_record(
            db,
            ProjectRecordCreate(
                project={
                    "code": "PRJ-001",
                    "title": "氯气显色材料研发",
                    "properties_jsonb": {"demo": True, "dataset": "synthetic/anonymised"},
                }
            ),
        )
        project_id = uuid.UUID(str(project["project"]["id"]))
        raw_material = _object(
            db,
            "ROO-001",
            "research_object",
            "2-POA",
            scope=None,
            tags=["原料", "试剂"],
            properties={"supplier": "Synthetic supplier", "lot": "DEMO-2POA"},
            fields={
                "fields": [
                    {
                        "key": "quantity",
                        "label": "用量",
                        "value_type": "number",
                        "default_unit": "g",
                    },
                    {
                        "key": "concentration",
                        "label": "浓度",
                        "value_type": "number",
                        "default_unit": "mol/L",
                    },
                ]
            },
        )
        potassium_iodide = _object(
            db,
            "ROO-002",
            "research_object",
            "Potassium iodide (KI)",
            scope=None,
            tags=["原料", "试剂"],
            properties={"supplier": "Synthetic supplier", "lot": "DEMO-KI"},
            fields={
                "fields": [
                    {
                        "key": "quantity",
                        "label": "用量",
                        "value_type": "number",
                        "default_unit": "g",
                    }
                ]
            },
        )
        mixer = _object(
            db,
            "ROO-003",
            "research_object",
            "实验室搅拌器",
            scope=project_id,
            tags=["设备", "搅拌"],
            properties={"asset_number": "DEMO-MIXER"},
            fields={
                "fields": [
                    {"key": "rpm", "label": "转速", "value_type": "number", "default_unit": "rpm"},
                    {
                        "key": "duration",
                        "label": "时间",
                        "value_type": "number",
                        "default_unit": "min",
                    },
                ]
            },
        )
        chamber = _object(
            db,
            "ROO-004",
            "research_object",
            "Cl₂ 暴露腔",
            scope=project_id,
            tags=["设备", "气体检测"],
            properties={"asset_number": "DEMO-CHAMBER"},
        )
        substrate = _object(
            db,
            "ROO-005",
            "research_object",
            "滤纸基材",
            scope=project_id,
            tags=["样品", "基材"],
            properties={"batch": "DEMO-SUBSTRATE"},
        )
        l1 = _object(
            db,
            "ROO-006",
            "research_object",
            "L1 浸渍液",
            scope=project_id,
            tags=["样品", "原料", "浸渍液"],
            properties={"batch": "DEMO-L1"},
        )
        s1 = _object(
            db,
            "ROO-007",
            "research_object",
            "S1 气敏纸带",
            scope=project_id,
            tags=["样品", "气敏纸带"],
            properties={"batch": "DEMO-S1"},
        )
        definitions = [
            _definition(db, "PFD-001", "配液", project_id),
            _definition(db, "PFD-002", "浸渍", project_id),
            _definition(db, "PFD-003", "Cl₂ 响应测试", project_id),
            _definition(db, "PFD-004", "增长率计算", project_id),
        ]
        d1 = _object(
            db,
            "DAT-001",
            "data",
            "S1 Cl₂ 响应曲线",
            scope=project_id,
            tags=["光谱", "响应"],
            properties={"measurement_kind": "spectral_response"},
        )
        d2 = _object(
            db,
            "DAT-002",
            "data",
            "S1 响应增长率",
            scope=project_id,
            tags=["计算结果"],
            properties={"measurement_kind": "growth_rate"},
        )
        d3 = _object(
            db,
            "DAT-003",
            "data",
            "S1 原始记录",
            scope=project_id,
            tags=["原始"],
            properties={"measurement_kind": "instrument_export"},
        )
        from app.models import DataRecord

        for data, scientific_type, description in (
            (d1, "xy_series", "Synthetic chlorine response"),
            (d2, "scalar", "Synthetic growth rate"),
            (d3, "table", "Synthetic instrument export"),
        ):
            if db.get(DataRecord, data.id) is None:
                db.add(
                    DataRecord(
                        data_object_id=data.id,
                        scientific_type=scientific_type,
                        description=description,
                    )
                )
                db.commit()
        create_representation(
            db,
            d1.id,
            DataRepresentationCreate(
                kind="table",
                name="响应曲线",
                format="tabular",
                schema_jsonb={
                    "columns": [
                        {
                            "key": "time_min",
                            "label": "时间",
                            "value_type": "number",
                            "unit": "min",
                            "role": "coordinate",
                        },
                        {
                            "key": "response",
                            "label": "响应",
                            "value_type": "number",
                            "unit": "%",
                            "role": "value",
                        },
                    ]
                },
                inline_payload_jsonb={
                    "rows": [
                        {"time_min": 0, "response": 0.05},
                        {"time_min": 5, "response": 0.31},
                        {"time_min": 10, "response": 0.52},
                    ]
                },
                summary_jsonb={"rows_count": 3},
            ),
        )
        create_representation(
            db,
            d2.id,
            DataRepresentationCreate(
                kind="structured",
                name="增长率",
                format="scalar",
                inline_payload_jsonb={"value": 0.47, "unit": "%/min"},
            ),
        )
        create_representation(
            db,
            d3.id,
            DataRepresentationCreate(
                kind="description",
                name="仪器导出说明",
                format="text",
                inline_payload_jsonb={"text": "Synthetic and anonymised instrument export."},
            ),
        )
        exec_a = create_process_execution(
            db,
            ProcessExecutionCreate(
                process_definition_id=definitions[0].id,
                project_scope_id=project_id,
                status="completed",
                object_bindings=[
                    ProcessExecutionObjectBindingCreate(
                        research_object_id=raw_material.id,
                        direction="input",
                        role="reagent",
                        values={"quantity": {"value": 5, "unit": "g"}},
                    ),
                    ProcessExecutionObjectBindingCreate(
                        research_object_id=potassium_iodide.id,
                        direction="input",
                        role="reagent",
                        values={"quantity": {"value": 1, "unit": "g"}},
                    ),
                    ProcessExecutionObjectBindingCreate(
                        research_object_id=mixer.id,
                        direction="context",
                        role="equipment",
                        values={"rpm": {"value": 700, "unit": "rpm"}},
                    ),
                    ProcessExecutionObjectBindingCreate(
                        research_object_id=l1.id, direction="output", role="solution", values={}
                    ),
                ],
            ),
        )
        exec_b = create_process_execution(
            db,
            ProcessExecutionCreate(
                process_definition_id=definitions[1].id,
                project_scope_id=project_id,
                status="completed",
                object_bindings=[
                    ProcessExecutionObjectBindingCreate(
                        research_object_id=l1.id, direction="input", role="solution", values={}
                    ),
                    ProcessExecutionObjectBindingCreate(
                        research_object_id=substrate.id,
                        direction="input",
                        role="substrate",
                        values={},
                    ),
                    ProcessExecutionObjectBindingCreate(
                        research_object_id=mixer.id,
                        direction="context",
                        role="equipment",
                        values={},
                    ),
                    ProcessExecutionObjectBindingCreate(
                        research_object_id=s1.id, direction="output", role="product", values={}
                    ),
                ],
                precedes_execution_ids=[uuid.UUID(str(exec_a["id"]))],
            ),
        )
        exec_c = create_process_execution(
            db,
            ProcessExecutionCreate(
                process_definition_id=definitions[2].id,
                project_scope_id=project_id,
                status="completed",
                object_bindings=[
                    ProcessExecutionObjectBindingCreate(
                        research_object_id=s1.id, direction="input", role="subject", values={}
                    ),
                    ProcessExecutionObjectBindingCreate(
                        research_object_id=chamber.id,
                        direction="context",
                        role="equipment",
                        values={},
                    ),
                ],
                data_bindings=[
                    ProcessExecutionDataBindingCreate(
                        data_id=d1.id, direction="output", role="response"
                    )
                ],
                precedes_execution_ids=[uuid.UUID(str(exec_b["id"]))],
            ),
        )
        create_process_execution(
            db,
            ProcessExecutionCreate(
                process_definition_id=definitions[3].id,
                project_scope_id=project_id,
                status="completed",
                data_bindings=[
                    ProcessExecutionDataBindingCreate(
                        data_id=d1.id, direction="input", role="baseline"
                    ),
                    ProcessExecutionDataBindingCreate(
                        data_id=d2.id, direction="output", role="growth_rate"
                    ),
                ],
                precedes_execution_ids=[uuid.UUID(str(exec_c["id"]))],
            ),
        )
        create_experiment_record(
            db,
            ExperimentRecordCreate(
                project_scope_id=project_id,
                experiment=ExperimentObjectCreate(code="EXP-001", title="基准方案"),
                references=[
                    ExperimentReferenceCreate(
                        target_id=s1.id, target_kind="research_object", role="sample"
                    ),
                    ExperimentReferenceCreate(target_id=d1.id, target_kind="data", role="response"),
                    ExperimentReferenceCreate(
                        target_id=definitions[2].id, target_kind="process_definition", role="method"
                    ),
                ],
            ),
        )
        create_experiment_record(
            db,
            ExperimentRecordCreate(
                project_scope_id=project_id,
                experiment=ExperimentObjectCreate(code="EXP-002", title="KI 改性分支"),
                references=[
                    ExperimentReferenceCreate(
                        target_id=potassium_iodide.id, target_kind="research_object", role="reagent"
                    ),
                    ExperimentReferenceCreate(
                        target_id=d2.id, target_kind="data", role="derived_result"
                    ),
                ],
            ),
        )
        view_a = create_view(
            db,
            ViewCreate(
                project_scope_id=project_id,
                code="VEW-001",
                title="S1 响应总览",
                description="Data-only view",
                config={"chart": "line", "x": "time_min", "y": "response"},
                data_ids=[d1.id, d2.id],
            ),
        )
        create_view(
            db,
            ViewCreate(
                project_scope_id=project_id,
                code="VEW-002",
                title="增长率卡片",
                config={"metric": "growth_rate"},
                data_ids=[d2.id],
            ),
        )
        create_claim(
            db,
            ClaimCreate(
                project_scope_id=project_id,
                code="CLM-001",
                title="S1 对 Cl₂ 有响应",
                statement="S1 exhibits a measurable chlorine response in the synthetic run.",
                source_type="analysis",
                confidence="medium",
                evidence=[
                    {
                        "evidence_kind": "data",
                        "evidence_id": d1.id,
                        "polarity": "support",
                        "note": "Response curve",
                    },
                    {
                        "evidence_kind": "view",
                        "evidence_id": uuid.UUID(str(view_a["view"]["id"])),
                        "polarity": "support",
                        "note": "Summary view",
                    },
                ],
            ),
        )
        db.commit()


if __name__ == "__main__":
    seed()
