from __future__ import annotations

import hashlib
import io
import json
import uuid
from typing import Any

from sqlalchemy import delete, select

from app.core.config import get_settings
from app.db import SessionLocal
from app.models import (
    Attachment,
    DataImport,
    DataPayload,
    DataPoint,
    DataScalar,
    DataTableRow,
    ObjectRelation,
    ObjectType,
    ObjectTypeVersion,
    ResearchObject,
)
from app.relation_semantics import normalize_relation_role
from app.schemas import ObjectCreate, RelationCreate
from app.services import create_object, create_relation
from app.storage import LocalStorageAdapter, sanitise_filename

DEMO_TAGS = ["synthetic", "anonymised", "demo"]
TYPE_DEFINITIONS = [
    ("material.generic", "material", "原料 / 试剂", "Material / reagent"),
    ("sample.generic", "sample", "样品", "Sample"),
    ("equipment.generic", "equipment", "设备", "Equipment"),
    ("process.generic", "process", "过程 / 操作", "Process"),
    ("data.generic", "data", "数据 / 测试结果", "Data / test result"),
    ("experiment.generic", "experiment", "实验", "Experiment"),
    ("project.generic", "project", "项目 / Vault", "Project / Vault"),
]


def _schema(kind: str) -> dict[str, Any]:
    common = {
        "type": "object",
        "additionalProperties": False,
        "properties": {"demo_tags": {"type": "array", "items": {"type": "string"}}},
    }
    properties: dict[str, Any] = {
        "material": {
            "cas": {"type": "string"},
            "supplier": {"type": "string"},
            "lot": {"type": "string"},
            "arrival_date": {"type": "string"},
        },
        "sample": {"batch": {"type": "string"}, "preparation_note": {"type": "string"}},
        "equipment": {
            "asset_number": {"type": "string"},
            "capabilities": {"type": "array", "items": {"type": "string"}},
        },
        "process": {
            "parameters": {"type": "object", "additionalProperties": True},
            "detailed_steps": {"type": "string"},
        },
        "data": {
            "measurement_kind": {"type": "string"},
            "x_label": {"type": "string"},
            "x_unit": {"type": "string"},
            "y_label": {"type": "string"},
            "y_unit": {"type": "string"},
            "scalar_metrics": {"type": "object", "additionalProperties": True},
        },
        "experiment": {"objective": {"type": "string"}, "note": {"type": "string"}},
        "project": {"description": {"type": "string"}},
    }
    return {**common, "properties": {**common["properties"], **properties[kind]}}


def _type(db, key: str, kind: str, zh: str, en: str) -> ObjectTypeVersion:
    obj_type = db.scalar(select(ObjectType).where(ObjectType.key == key))
    if obj_type is None:
        for sibling in db.scalars(
            select(ObjectType).where(
                ObjectType.kind == kind,
                ObjectType.is_default.is_(True),
            )
        ):
            sibling.is_default = False
        obj_type = ObjectType(key=key, kind=kind, label_zh=zh, label_en=en, is_default=True)
        db.add(obj_type)
        db.flush()
    else:
        obj_type.label_zh = zh
        obj_type.label_en = en
        for sibling in db.scalars(
            select(ObjectType).where(
                ObjectType.kind == kind,
                ObjectType.id != obj_type.id,
                ObjectType.is_default.is_(True),
            )
        ):
            sibling.is_default = False
        obj_type.is_default = True
        db.flush()
    version = db.scalar(
        select(ObjectTypeVersion).where(
            ObjectTypeVersion.object_type_id == obj_type.id,
            ObjectTypeVersion.version == 1,
        )
    )
    if version is None:
        version = ObjectTypeVersion(
            object_type_id=obj_type.id,
            version=1,
            json_schema=_schema(kind),
            ui_schema=None,
            is_active=True,
        )
        db.add(version)
        db.flush()
    return version


def _object(
    db,
    code: str,
    kind: str,
    title: str,
    scope: uuid.UUID | None,
    properties: dict[str, Any],
    status: str = "active",
    usage_schema: dict[str, Any] | None = None,
) -> ResearchObject:
    existing = db.scalar(select(ResearchObject).where(ResearchObject.code == code))
    if existing is not None:
        if usage_schema and not existing.usage_schema_jsonb:
            existing.usage_schema_jsonb = usage_schema
        return existing
    return create_object(
        db,
        ObjectCreate(
            code=code,
            kind=kind,
            title=title,
            status=status,
            project_scope_id=scope,
            properties_jsonb=properties,
            usage_schema_jsonb=usage_schema or {},
        ),
    )


def _relation(
    db,
    source: ResearchObject,
    target: ResearchObject,
    relation_type: str,
    role: str | None = None,
    properties: dict[str, Any] | None = None,
) -> None:
    role = normalize_relation_role(role)
    existing = db.scalar(
        select(ObjectRelation).where(
            ObjectRelation.source_object_id == source.id,
            ObjectRelation.target_object_id == target.id,
            ObjectRelation.relation_type == relation_type,
            ObjectRelation.role.is_not_distinct_from(role),
        )
    )
    if existing is None:
        create_relation(
            db,
            RelationCreate(
                source_object_id=source.id,
                target_object_id=target.id,
                relation_type=relation_type,
                role=role,
                properties_jsonb=properties or {},
            ),
        )


def _seed_data(
    db,
    data_object: ResearchObject,
    adapter: LocalStorageAdapter,
    index: int,
) -> None:
    if db.scalar(select(DataPayload).where(DataPayload.data_object_id == data_object.id)):
        return
    rows = [
        (400.0, 0.16 + index * 0.04),
        (500.0, 0.24 + index * 0.05),
        (600.0, 0.31 + index * 0.06),
        (700.0, 0.22 + index * 0.04),
    ]
    csv_bytes = (
        "wavelength_nm,response\n" + "\n".join(f"{x},{y}" for x, y in rows) + "\n"
    ).encode()
    attachment_id = uuid.uuid4()
    filename = sanitise_filename(f"{data_object.code.lower()}-spectrum.csv")
    key = f"{data_object.id}/{attachment_id}/{filename}"
    size, digest = adapter.put(key, io.BytesIO(csv_bytes))
    attachment = Attachment(
        id=attachment_id,
        object_id=data_object.id,
        original_filename=filename,
        storage_key=key,
        content_type="text/csv",
        size_bytes=size,
        sha256=digest,
    )
    db.add(attachment)
    db.flush()
    canonical = "\n".join(f"{i},{i + 2},{x:.17g},{y:.17g}" for i, (x, y) in enumerate(rows))
    payload = DataPayload(
        data_object_id=data_object.id,
        payload_kind="xy_series",
        name="Synthetic spectral response",
        schema_key="xy-series",
        schema_version=1,
        metadata_jsonb={
            "x_label": "Wavelength",
            "x_unit": "nm",
            "y_label": "Response",
            "y_unit": "a.u.",
            "source": "synthetic demo",
        },
        summary_jsonb={
            "x_min": 400.0,
            "x_max": 700.0,
            "y_min": min(y for _, y in rows),
            "y_max": max(y for _, y in rows),
            "y_mean": sum(y for _, y in rows) / len(rows),
        },
        source_attachment_id=attachment.id,
        payload_sha256=hashlib.sha256(canonical.encode()).hexdigest(),
    )
    db.add(payload)
    db.flush()
    db.add_all(
        [
            DataPoint(
                payload_id=payload.id,
                ordinal=i,
                source_row_number=i + 2,
                x_value=x,
                y_value=y,
            )
            for i, (x, y) in enumerate(rows)
        ]
    )
    db.add(
        DataImport(
            data_object_id=data_object.id,
            source_attachment_id=attachment.id,
            payload_id=payload.id,
            status="completed",
            source_format="csv",
            parser_key="tabular-xy",
            parser_version=1,
            source_sha256=digest,
            header_json=["wavelength_nm", "response"],
            metadata_jsonb={
                "available_sheets": [],
                "preview_rows": [[x, y] for x, y in rows],
                "column_count": 2,
            },
            mapping_json={
                "payload_name": "Synthetic spectral response",
                "x": {"column": "wavelength_nm", "label": "Wavelength", "unit": "nm"},
                "y": {"column": "response", "label": "Response", "unit": "a.u."},
            },
            warnings_json=[],
            errors_json=[],
            row_count=len(rows),
        )
    )
    db.commit()


def _seed_variant_payloads(db, data: dict[str, ResearchObject]) -> None:
    scalar_data = data["DAT-001"]
    if not db.scalar(
        select(DataPayload).where(
            DataPayload.data_object_id == scalar_data.id, DataPayload.payload_kind == "scalar"
        )
    ):
        payload = DataPayload(
            data_object_id=scalar_data.id,
            payload_kind="scalar",
            name="Synthetic response time",
            schema_key="scalar",
            schema_version=1,
            metadata_jsonb={"measurement": "response_time"},
            summary_jsonb={"value": 8.3, "unit": "s"},
            payload_sha256=hashlib.sha256(b"DAT-001-response-time-8.3-s").hexdigest(),
        )
        db.add(payload)
        db.flush()
        db.add(DataScalar(payload_id=payload.id, value=8.3, unit="s"))

    table_data = data["DAT-002"]
    if not db.scalar(
        select(DataPayload).where(
            DataPayload.data_object_id == table_data.id, DataPayload.payload_kind == "table"
        )
    ):
        columns = [
            {"key": "concentration", "label": "浓度", "value_type": "number", "unit": "ppm"},
            {"key": "response", "label": "响应", "value_type": "number", "unit": "%"},
            {"key": "note", "label": "备注", "value_type": "text"},
        ]
        rows = [
            {"concentration": 10.0, "response": 0.31, "note": "low"},
            {"concentration": 20.0, "response": 0.52, "note": "mid"},
        ]
        payload = DataPayload(
            data_object_id=table_data.id,
            payload_kind="table",
            name="Synthetic tabular response",
            schema_key="table",
            schema_version=1,
            metadata_jsonb={"columns": columns},
            summary_jsonb={"rows_count": len(rows), "columns_count": len(columns)},
            payload_sha256=hashlib.sha256(json.dumps(rows, sort_keys=True).encode()).hexdigest(),
        )
        db.add(payload)
        db.flush()
        db.add_all(
            [
                DataTableRow(
                    payload_id=payload.id,
                    ordinal=ordinal,
                    source_row_number=ordinal + 1,
                    values_jsonb=row,
                )
                for ordinal, row in enumerate(rows)
            ]
        )
    db.commit()


def seed() -> None:
    adapter = LocalStorageAdapter(get_settings().storage_root)
    with SessionLocal() as db:
        for key, kind, zh, en in TYPE_DEFINITIONS:
            _type(db, key, kind, zh, en)
        db.commit()

        project = _object(
            db,
            "PRJ-001",
            "project",
            "氯气显色材料研发",
            None,
            {"description": "Demo dataset — synthetic / anonymised", "demo_tags": DEMO_TAGS},
        )
        material_usage_schema = {
            "fields": [
                {
                    "key": "quantity",
                    "label": "用量",
                    "value_type": "number",
                    "default_value": None,
                    "default_unit": "g",
                    "required": False,
                    "options": [],
                    "order": 0,
                }
            ]
        }
        materials = {
            code: _object(
                db,
                code,
                "material",
                title,
                project.id,
                props,
                usage_schema=material_usage_schema,
            )
            for code, title, props in [
                (
                    "MAT-001",
                    "Material A / 2-POA anonymized",
                    {
                        "supplier": "Synthetic supplier",
                        "lot": "DEMO-A",
                        "cas": "DEMO-CAS-001",
                    },
                ),
                (
                    "MAT-002",
                    "Ethanol",
                    {
                        "supplier": "Synthetic supplier",
                        "lot": "DEMO-ETOH",
                        "cas": "64-17-5",
                    },
                ),
                (
                    "MAT-003",
                    "Potassium iodide (KI)",
                    {
                        "supplier": "Synthetic supplier",
                        "lot": "DEMO-KI",
                        "cas": "7681-11-0",
                    },
                ),
                (
                    "MAT-004",
                    "Starch",
                    {
                        "supplier": "Synthetic supplier",
                        "lot": "DEMO-STARCH",
                        "cas": "9005-25-8",
                    },
                ),
                (
                    "MAT-005",
                    "Base substrate",
                    {
                        "supplier": "Synthetic supplier",
                        "lot": "DEMO-BASE",
                        "cas": "DEMO-CAS-005",
                    },
                ),
            ]
        }
        equipment_usage_schemas = {
            "EQP-001": {
                "fields": [
                    {
                        "key": "rpm",
                        "label": "转速",
                        "value_type": "number",
                        "default_value": 700,
                        "default_unit": "rpm",
                        "required": False,
                        "options": [],
                        "order": 0,
                    },
                    {
                        "key": "duration",
                        "label": "时间",
                        "value_type": "number",
                        "default_value": 10,
                        "default_unit": "min",
                        "required": False,
                        "options": [],
                        "order": 1,
                    },
                ]
            },
            "EQP-002": {
                "fields": [
                    {
                        "key": "temperature",
                        "label": "温度",
                        "value_type": "number",
                        "default_value": 60,
                        "default_unit": "°C",
                        "required": False,
                        "options": [],
                        "order": 0,
                    },
                    {
                        "key": "duration",
                        "label": "时间",
                        "value_type": "number",
                        "default_value": 20,
                        "default_unit": "min",
                        "required": False,
                        "options": [],
                        "order": 1,
                    },
                ]
            },
            "EQP-003": {
                "fields": [
                    {
                        "key": "duration",
                        "label": "时间",
                        "value_type": "number",
                        "default_value": 30,
                        "default_unit": "min",
                        "required": False,
                        "options": [],
                        "order": 0,
                    }
                ]
            },
            "EQP-004": {
                "fields": [
                    {
                        "key": "duration",
                        "label": "时间",
                        "value_type": "number",
                        "default_value": 10,
                        "default_unit": "min",
                        "required": False,
                        "options": [],
                        "order": 0,
                    }
                ]
            },
        }
        equipment = {
            code: _object(
                db,
                code,
                "equipment",
                title,
                project.id,
                props,
                usage_schema=equipment_usage_schemas[code],
            )
            for code, title, props in [
                (
                    "EQP-001",
                    "Impregnation setup",
                    {"asset_number": "DEMO-IMP", "capabilities": ["impregnation"]},
                ),
                (
                    "EQP-002",
                    "Drying oven",
                    {"asset_number": "DEMO-OVEN", "capabilities": ["drying"]},
                ),
                (
                    "EQP-003",
                    "Spectrometer",
                    {"asset_number": "DEMO-SPEC", "capabilities": ["spectral measurement"]},
                ),
                (
                    "EQP-004",
                    "Gas exposure setup",
                    {"asset_number": "DEMO-GAS", "capabilities": ["gas exposure"]},
                ),
            ]
        }
        experiments = {
            code: _object(db, code, "experiment", title, project.id, {"objective": objective})
            for code, title, objective in [
                ("EXP-001", "基准配方", "建立基准显色响应"),
                ("EXP-002", "KI 改性与分支", "观察 KI 改性及分支响应"),
                ("EXP-003", "KI + starch", "观察 KI + starch 组合的响应"),
            ]
        }
        samples = {
            code: _object(db, code, "sample", title, project.id, {"batch": batch})
            for code, title, batch in [
                ("SMP-001", "Baseline sample", "baseline"),
                ("SMP-002", "Baseline + KI", "ki"),
                ("SMP-003", "Baseline + KI + starch", "ki-starch"),
                ("SMP-004", "Baseline branch", "branch"),
            ]
        }
        processes = {
            code: _object(db, code, "process", title, project.id, {"parameters": parameters})
            for code, title, parameters in [
                ("PRC-001", "Solution preparation", {"duration": {"value": 10, "unit": "min"}}),
                ("PRC-002", "Baseline measurement", {"duration": {"value": 30, "unit": "min"}}),
                ("PRC-003", "KI modification", {"duration": {"value": 30, "unit": "min"}}),
                ("PRC-004", "KI spectral measurement", {"duration": {"value": 30, "unit": "min"}}),
                ("PRC-005", "Branch preparation", {"duration": {"value": 20, "unit": "min"}}),
                (
                    "PRC-006",
                    "Branch spectral measurement",
                    {"duration": {"value": 20, "unit": "min"}},
                ),
                ("PRC-007", "KI + starch modification", {"duration": {"value": 30, "unit": "min"}}),
                (
                    "PRC-008",
                    "KI + starch spectral measurement",
                    {"duration": {"value": 30, "unit": "min"}},
                ),
            ]
        }
        data = {
            code: _object(
                db,
                code,
                "data",
                title,
                project.id,
                {
                    "measurement_kind": "spectral_response",
                    "x_label": "Wavelength",
                    "x_unit": "nm",
                    "y_label": "Response",
                    "y_unit": "a.u.",
                },
            )
            for code, title in [
                ("DAT-001", "Baseline spectral response"),
                ("DAT-002", "KI spectral response"),
                ("DAT-003", "KI + starch spectral response"),
                ("DAT-004", "Branch spectral response"),
            ]
        }
        all_demo_objects = list(materials.values()) + list(equipment.values())
        all_demo_objects += list(experiments.values()) + list(samples.values())
        all_demo_objects += list(processes.values()) + list(data.values()) + [project]
        demo_ids = [item.id for item in all_demo_objects]
        db.execute(
            delete(ObjectRelation).where(
                (ObjectRelation.source_object_id.in_(demo_ids))
                | (ObjectRelation.target_object_id.in_(demo_ids))
            )
        )
        db.commit()

        ownership = {
            "EXP-001": ["PRC-001", "SMP-001", "PRC-002", "DAT-001"],
            "EXP-002": [
                "PRC-003",
                "SMP-002",
                "PRC-004",
                "DAT-002",
                "PRC-005",
                "SMP-004",
                "PRC-006",
                "DAT-004",
            ],
            "EXP-003": ["PRC-007", "SMP-003", "PRC-008", "DAT-003"],
        }
        lookup = {**processes, **samples, **data}
        for experiment_code, object_codes in ownership.items():
            for object_code in object_codes:
                _relation(db, experiments[experiment_code], lookup[object_code], "contains")

        for experiment_code, sample_code in [
            ("EXP-001", "SMP-001"),
            ("EXP-002", "SMP-001"),
            ("EXP-003", "SMP-002"),
        ]:
            _relation(db, experiments[experiment_code], samples[sample_code], "includes")

        prep = processes["PRC-001"]
        _relation(
            db,
            prep,
            materials["MAT-001"],
            "uses",
            "material",
            {"quantity": {"value": 5, "unit": "g"}},
        )
        _relation(
            db,
            prep,
            materials["MAT-002"],
            "uses",
            "solvent",
            {"quantity": {"value": 90, "unit": "g"}},
        )
        _relation(db, prep, equipment["EQP-001"], "uses", "equipment")
        _relation(db, prep, samples["SMP-001"], "produces")

        measurements = [
            ("PRC-002", "SMP-001", "DAT-001"),
            ("PRC-004", "SMP-002", "DAT-002"),
            ("PRC-006", "SMP-004", "DAT-004"),
            ("PRC-008", "SMP-003", "DAT-003"),
        ]
        for process_code, sample_code, data_code in measurements:
            process = processes[process_code]
            _relation(db, process, samples[sample_code], "uses", "subject")
            _relation(db, process, equipment["EQP-003"], "uses", "equipment")
            _relation(db, process, equipment["EQP-004"], "uses", "environment")
            _relation(db, process, data[data_code], "produces")

        for process_code, sample_code in [
            ("PRC-003", "SMP-001"),
            ("PRC-005", "SMP-001"),
            ("PRC-007", "SMP-002"),
        ]:
            _relation(db, processes[process_code], samples[sample_code], "uses", "precursor")
        for process_code, sample_code in [
            ("PRC-003", "SMP-002"),
            ("PRC-005", "SMP-004"),
            ("PRC-007", "SMP-003"),
        ]:
            _relation(db, processes[process_code], samples[sample_code], "produces")
        _relation(
            db,
            processes["PRC-003"],
            materials["MAT-003"],
            "uses",
            "additive",
            {"quantity": {"value": 1, "unit": "g"}},
        )
        _relation(db, processes["PRC-005"], materials["MAT-005"], "uses", "substrate")
        _relation(
            db,
            processes["PRC-007"],
            materials["MAT-003"],
            "uses",
            "additive",
            {"quantity": {"value": 1, "unit": "g"}},
        )
        _relation(
            db,
            processes["PRC-007"],
            materials["MAT-004"],
            "uses",
            "additive",
            {"quantity": {"value": 1, "unit": "g"}},
        )

        for source, target in [
            ("PRC-001", "PRC-002"),
            ("PRC-003", "PRC-004"),
            ("PRC-005", "PRC-006"),
            ("PRC-007", "PRC-008"),
        ]:
            _relation(db, processes[source], processes[target], "precedes")

        for index, datum in enumerate(data.values(), start=1):
            _seed_data(db, datum, adapter, index)
        _seed_variant_payloads(db, data)
        db.commit()
    print("Seeded v0.2 semantic synthetic/anonymised research object graph (repeat-safe).")


if __name__ == "__main__":
    seed()
