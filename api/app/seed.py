from __future__ import annotations

import hashlib
import io
import uuid
from typing import Any

from sqlalchemy import select

from app.core.config import get_settings
from app.db import SessionLocal
from app.models import (
    Attachment,
    DataImport,
    DataPayload,
    DataPoint,
    ObjectRelation,
    ObjectType,
    ObjectTypeVersion,
    ResearchObject,
)
from app.schemas import ObjectCreate, RelationCreate
from app.services import create_object, create_relation
from app.storage import LocalStorageAdapter, sanitise_filename

DEMO_TAGS = ["synthetic", "anonymised", "demo"]


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
    result = dict(common)
    result["properties"] = {**common["properties"], **properties[kind]}
    return result


def _type(db, key: str, kind: str, zh: str, en: str) -> ObjectTypeVersion:
    obj_type = db.scalar(select(ObjectType).where(ObjectType.key == key))
    if obj_type is None:
        obj_type = ObjectType(key=key, kind=kind, label_zh=zh, label_en=en)
        db.add(obj_type)
        db.flush()
    version = db.scalar(
        select(ObjectTypeVersion).where(
            ObjectTypeVersion.object_type_id == obj_type.id, ObjectTypeVersion.version == 1
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
        db.commit()
        db.refresh(version)
    return version


def _object(
    db,
    code: str,
    kind: str,
    title: str,
    scope: uuid.UUID | None,
    properties: dict[str, Any],
    status: str = "active",
) -> ResearchObject:
    existing = db.scalar(select(ResearchObject).where(ResearchObject.code == code))
    if existing is not None:
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
    sample: ResearchObject,
    equipment: ResearchObject,
    adapter: LocalStorageAdapter,
    index: int,
) -> None:
    if (
        db.scalar(select(DataPayload).where(DataPayload.data_object_id == data_object.id))
        is not None
    ):
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
                payload_id=payload.id, ordinal=i, source_row_number=i + 2, x_value=x, y_value=y
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
    _relation(db, equipment, data_object, "related_to", "measurement-output")
    _relation(db, data_object, sample, "related_to", "subject")


def seed() -> None:
    adapter = LocalStorageAdapter(get_settings().storage_root)
    with SessionLocal() as db:
        for key, kind, zh, en in [
            ("material.generic", "material", "原料 / 试剂", "Material / reagent"),
            ("sample.generic", "sample", "样品", "Sample"),
            ("equipment.generic", "equipment", "设备", "Equipment"),
            ("process.generic", "process", "过程 / 操作", "Process"),
            ("data.generic", "data", "数据 / 测试结果", "Data / test result"),
            ("experiment.generic", "experiment", "实验", "Experiment"),
            ("project.generic", "project", "项目 / Vault", "Project / Vault"),
        ]:
            _type(db, key, kind, zh, en)
        project = _object(
            db,
            "PRJ-001",
            "project",
            "氯气显色材料研发",
            None,
            {"description": "Demo dataset — synthetic / anonymised", "demo_tags": DEMO_TAGS},
        )
        material_a = _object(
            db,
            "MAT-001",
            "material",
            "Material A / 2-POA anonymized",
            project.id,
            {"supplier": "Synthetic supplier", "lot": "DEMO-A", "demo_tags": DEMO_TAGS},
        )
        ethanol = _object(
            db,
            "MAT-002",
            "material",
            "Ethanol",
            project.id,
            {"supplier": "Synthetic supplier", "lot": "DEMO-ETOH", "demo_tags": DEMO_TAGS},
        )
        ki = _object(
            db,
            "MAT-003",
            "material",
            "Potassium iodide (KI)",
            project.id,
            {"supplier": "Synthetic supplier", "lot": "DEMO-KI", "demo_tags": DEMO_TAGS},
        )
        starch = _object(
            db,
            "MAT-004",
            "material",
            "Starch",
            project.id,
            {"supplier": "Synthetic supplier", "lot": "DEMO-STARCH", "demo_tags": DEMO_TAGS},
        )
        substrate = _object(
            db,
            "MAT-005",
            "material",
            "Base substrate",
            project.id,
            {"supplier": "Synthetic supplier", "lot": "DEMO-BASE", "demo_tags": DEMO_TAGS},
        )
        eq_imp = _object(
            db,
            "EQP-001",
            "equipment",
            "Impregnation setup",
            project.id,
            {"asset_number": "DEMO-IMP", "capabilities": ["impregnation"], "demo_tags": DEMO_TAGS},
        )
        eq_oven = _object(
            db,
            "EQP-002",
            "equipment",
            "Drying oven",
            project.id,
            {"asset_number": "DEMO-OVEN", "capabilities": ["drying"], "demo_tags": DEMO_TAGS},
        )
        eq_spec = _object(
            db,
            "EQP-003",
            "equipment",
            "Spectrometer",
            project.id,
            {
                "asset_number": "DEMO-SPEC",
                "capabilities": ["spectral measurement"],
                "demo_tags": DEMO_TAGS,
            },
        )
        eq_gas = _object(
            db,
            "EQP-004",
            "equipment",
            "Gas exposure setup",
            project.id,
            {"asset_number": "DEMO-GAS", "capabilities": ["gas exposure"], "demo_tags": DEMO_TAGS},
        )
        exp1 = _object(
            db,
            "EXP-001",
            "experiment",
            "基准配方",
            project.id,
            {"objective": "建立基准显色响应", "demo_tags": DEMO_TAGS},
        )
        exp2 = _object(
            db,
            "EXP-002",
            "experiment",
            "KI 改性",
            project.id,
            {"objective": "观察 KI 改性后的响应", "demo_tags": DEMO_TAGS},
        )
        exp3 = _object(
            db,
            "EXP-003",
            "experiment",
            "KI + starch",
            project.id,
            {"objective": "观察 KI + starch 组合的响应", "demo_tags": DEMO_TAGS},
        )
        samples = {
            "SMP-001": _object(
                db,
                "SMP-001",
                "sample",
                "Baseline sample",
                project.id,
                {"batch": "baseline", "demo_tags": DEMO_TAGS},
            ),
            "SMP-002": _object(
                db,
                "SMP-002",
                "sample",
                "Baseline + KI",
                project.id,
                {"batch": "ki", "demo_tags": DEMO_TAGS},
            ),
            "SMP-003": _object(
                db,
                "SMP-003",
                "sample",
                "Baseline + KI + starch",
                project.id,
                {"batch": "ki-starch", "demo_tags": DEMO_TAGS},
            ),
            "SMP-004": _object(
                db,
                "SMP-004",
                "sample",
                "Baseline branch",
                project.id,
                {"batch": "branch", "demo_tags": DEMO_TAGS},
            ),
        }
        processes = {
            "PRC-001": _object(
                db,
                "PRC-001",
                "process",
                "Solution preparation",
                project.id,
                {"parameters": {"duration": {"value": 10, "unit": "min"}}, "demo_tags": DEMO_TAGS},
            ),
            "PRC-002": _object(
                db,
                "PRC-002",
                "process",
                "Baseline impregnation",
                project.id,
                {
                    "parameters": {
                        "duration": {"value": 30, "unit": "min"},
                        "temperature": {"value": 25, "unit": "°C"},
                    },
                    "demo_tags": DEMO_TAGS,
                },
            ),
            "PRC-003": _object(
                db,
                "PRC-003",
                "process",
                "KI modification",
                project.id,
                {
                    "parameters": {
                        "duration": {"value": 30, "unit": "min"},
                        "temperature": {"value": 25, "unit": "°C"},
                    },
                    "demo_tags": DEMO_TAGS,
                },
            ),
            "PRC-004": _object(
                db,
                "PRC-004",
                "process",
                "KI + starch modification",
                project.id,
                {
                    "parameters": {
                        "duration": {"value": 30, "unit": "min"},
                        "temperature": {"value": 25, "unit": "°C"},
                    },
                    "demo_tags": DEMO_TAGS,
                },
            ),
            "PRC-005": _object(
                db,
                "PRC-005",
                "process",
                "Branch preparation",
                project.id,
                {"parameters": {"duration": {"value": 20, "unit": "min"}}, "demo_tags": DEMO_TAGS},
            ),
            "PRC-006": _object(
                db,
                "PRC-006",
                "process",
                "Drying",
                project.id,
                {
                    "parameters": {
                        "temperature": {"value": 60, "unit": "°C"},
                        "duration": {"value": 20, "unit": "min"},
                    },
                    "demo_tags": DEMO_TAGS,
                },
            ),
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
                    "demo_tags": DEMO_TAGS,
                },
            )
            for code, title in [
                ("DAT-001", "Baseline spectral response"),
                ("DAT-002", "KI spectral response"),
                ("DAT-003", "KI + starch spectral response"),
                ("DAT-004", "Branch spectral response"),
            ]
        }
        for experiment, object_codes in [
            (exp1, ["PRC-001", "PRC-002", "PRC-006", "SMP-001", "SMP-004", "DAT-001", "DAT-004"]),
            (exp2, ["PRC-003", "SMP-002", "DAT-002"]),
            (exp3, ["PRC-004", "SMP-003", "DAT-003"]),
        ]:
            for code in object_codes:
                _relation(db, experiment, (processes | samples | data)[code], "contains")
        _relation(
            db,
            processes["PRC-001"],
            material_a,
            "uses",
            "material",
            {"quantity": {"value": 5, "unit": "g"}},
        )
        _relation(
            db,
            processes["PRC-001"],
            ethanol,
            "uses",
            "solvent",
            {"quantity": {"value": 90, "unit": "g"}},
        )
        _relation(
            db,
            processes["PRC-002"],
            material_a,
            "uses",
            "material",
            {"quantity": {"value": 5, "unit": "g"}},
        )
        _relation(
            db,
            processes["PRC-002"],
            ethanol,
            "uses",
            "solvent",
            {"quantity": {"value": 90, "unit": "g"}},
        )
        _relation(db, processes["PRC-002"], eq_imp, "uses", "equipment")
        _relation(db, processes["PRC-002"], samples["SMP-001"], "produces")
        _relation(db, processes["PRC-003"], samples["SMP-001"], "uses", "precursor")
        _relation(
            db,
            processes["PRC-003"],
            ki,
            "uses",
            "additive",
            {"quantity": {"value": 1, "unit": "g"}},
        )
        _relation(db, processes["PRC-003"], eq_imp, "uses", "equipment")
        _relation(db, processes["PRC-003"], samples["SMP-002"], "produces")
        _relation(db, processes["PRC-004"], samples["SMP-002"], "uses", "precursor")
        _relation(
            db,
            processes["PRC-004"],
            ki,
            "uses",
            "additive",
            {"quantity": {"value": 1, "unit": "g"}},
        )
        _relation(
            db,
            processes["PRC-004"],
            starch,
            "uses",
            "additive",
            {"quantity": {"value": 1, "unit": "g"}},
        )
        _relation(db, processes["PRC-004"], eq_imp, "uses", "equipment")
        _relation(db, processes["PRC-004"], samples["SMP-003"], "produces")
        _relation(db, processes["PRC-005"], samples["SMP-001"], "uses", "precursor")
        _relation(db, processes["PRC-005"], substrate, "uses", "substrate")
        _relation(db, processes["PRC-005"], samples["SMP-004"], "produces")
        for process in processes.values():
            if process.code in {"PRC-002", "PRC-003", "PRC-004", "PRC-005"}:
                _relation(db, process, eq_oven, "uses", "equipment")
        for process, sample, datum in [
            (processes["PRC-002"], samples["SMP-001"], data["DAT-001"]),
            (processes["PRC-003"], samples["SMP-002"], data["DAT-002"]),
            (processes["PRC-004"], samples["SMP-003"], data["DAT-003"]),
            (processes["PRC-005"], samples["SMP-004"], data["DAT-004"]),
        ]:
            _relation(db, process, sample, "uses", "subject")
            _relation(db, process, eq_spec, "uses", "equipment")
            _relation(db, process, eq_gas, "uses", "environment")
            _relation(db, process, datum, "produces")
            _seed_data(db, datum, sample, eq_spec, adapter, int(datum.code[-1]))
        _relation(db, processes["PRC-002"], processes["PRC-003"], "precedes")
        _relation(db, processes["PRC-003"], processes["PRC-004"], "precedes")
        db.commit()
    print("Seeded v0.2 synthetic/anonymised research object graph (repeat-safe).")


if __name__ == "__main__":
    seed()
