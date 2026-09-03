from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

ObjectKind = Literal["material", "sample", "equipment", "process", "data", "experiment", "project"]
RelationType = Literal["contains", "uses", "produces", "precedes", "related_to"]


class ObjectTypeVersionOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    object_type_id: uuid.UUID
    version: int
    json_schema: dict[str, Any]
    ui_schema: dict[str, Any] | None
    is_active: bool
    created_at: datetime


class ObjectTypeOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    key: str
    kind: ObjectKind
    label_zh: str
    label_en: str
    description_zh: str | None
    description_en: str | None
    is_default: bool
    created_at: datetime
    versions: list[ObjectTypeVersionOut] = Field(default_factory=list)


class ObjectSummary(BaseModel):
    id: uuid.UUID
    code: str
    kind: ObjectKind
    title: str
    status: str
    project_scope_id: uuid.UUID | None
    type_key: str
    type_label_zh: str
    type_label_en: str


class ResearchObjectOut(ObjectSummary):
    type_version_id: uuid.UUID
    type_version: int
    properties_jsonb: dict[str, Any]
    content_document: list[dict[str, Any]]
    created_at: datetime
    updated_at: datetime


class ObjectCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    kind: ObjectKind
    title: str = Field(min_length=1, max_length=240)
    code: str | None = Field(default=None, min_length=1, max_length=32)
    status: str = Field(default="active", min_length=1, max_length=32)
    project_scope_id: uuid.UUID | None = None
    type_version_id: uuid.UUID | None = None
    properties_jsonb: dict[str, Any] = Field(default_factory=dict)
    content_document: list[dict[str, Any]] = Field(default_factory=list)

    @field_validator("title", "status")
    @classmethod
    def strip_required_text(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("must not be blank")
        return value


class ObjectPatch(BaseModel):
    model_config = ConfigDict(extra="forbid")

    title: str | None = Field(default=None, min_length=1, max_length=240)
    status: str | None = Field(default=None, min_length=1, max_length=32)
    project_scope_id: uuid.UUID | None = None
    properties_jsonb: dict[str, Any] | None = None
    content_document: list[dict[str, Any]] | None = None


class RelationCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    source_object_id: uuid.UUID
    target_object_id: uuid.UUID
    relation_type: RelationType
    role: str | None = Field(default=None, max_length=64)
    properties_jsonb: dict[str, Any] = Field(default_factory=dict)

    @field_validator("role")
    @classmethod
    def normalize_role(cls, value: str | None) -> str | None:
        return value.strip() or None if value is not None else None


class RelationPatch(BaseModel):
    model_config = ConfigDict(extra="forbid")

    role: str | None = Field(default=None, max_length=64)
    properties_jsonb: dict[str, Any] | None = None


class ProcessCompositionCreateTarget(BaseModel):
    model_config = ConfigDict(extra="forbid")

    kind: Literal["sample", "data"]
    title: str = Field(min_length=1, max_length=240)
    status: str = Field(default="active", min_length=1, max_length=32)
    type_version_id: uuid.UUID | None = None
    properties_jsonb: dict[str, Any] = Field(default_factory=dict)
    content_document: list[dict[str, Any]] = Field(default_factory=list)

    @field_validator("title", "status")
    @classmethod
    def strip_required_text(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("must not be blank")
        return value


class ProcessCompositionItem(BaseModel):
    model_config = ConfigDict(extra="forbid")

    relation_id: uuid.UUID | None = None
    relation_type: Literal["uses", "produces"]
    target_object_id: uuid.UUID | None = None
    create_target: ProcessCompositionCreateTarget | None = None
    role: str | None = Field(default=None, max_length=64)
    properties_jsonb: dict[str, Any] = Field(default_factory=dict)

    @field_validator("role")
    @classmethod
    def strip_role(cls, value: str | None) -> str | None:
        return value.strip() or None if value is not None else None

    @model_validator(mode="after")
    def validate_target(self) -> ProcessCompositionItem:
        if (self.target_object_id is None) == (self.create_target is None):
            raise ValueError("provide exactly one of target_object_id or create_target")
        if self.relation_id is not None and self.create_target is not None:
            raise ValueError("relation_id cannot be used with create_target")
        return self


class ProcessCompositionPut(BaseModel):
    model_config = ConfigDict(extra="forbid")

    items: list[ProcessCompositionItem] = Field(default_factory=list)


class ProcessCompositionOut(BaseModel):
    process: ResearchObjectOut
    uses: list[ObjectRelationOut]
    produces: list[ObjectRelationOut]


class ObjectRelationOut(BaseModel):
    id: uuid.UUID
    source_object_id: uuid.UUID
    target_object_id: uuid.UUID
    relation_type: RelationType
    role: str | None
    properties_jsonb: dict[str, Any]
    source: ObjectSummary
    target: ObjectSummary
    created_at: datetime
    updated_at: datetime


class RevisionCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    change_note: str | None = Field(default=None, max_length=500)


class ObjectRevisionOut(BaseModel):
    id: uuid.UUID
    object_id: uuid.UUID
    revision_number: int
    snapshot_jsonb: dict[str, Any]
    snapshot_sha256: str
    change_note: str | None
    created_at: datetime


class AttachmentOut(BaseModel):
    id: uuid.UUID
    object_id: uuid.UUID
    original_filename: str
    content_type: str | None
    size_bytes: int
    sha256: str
    created_at: datetime


class ImportPreviewRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    source_attachment_id: uuid.UUID
    sheet_name: str | None = None


class AxisMapping(BaseModel):
    model_config = ConfigDict(extra="forbid")

    column: str = Field(min_length=1)
    label: str = Field(min_length=1, max_length=120)
    unit: str = Field(min_length=1, max_length=64)


class ImportCommitMapping(BaseModel):
    model_config = ConfigDict(extra="forbid")

    payload_name: str = Field(min_length=1, max_length=240)
    x: AxisMapping
    y: AxisMapping
    sheet_name: str | None = None


class Diagnostic(BaseModel):
    row: int | None = None
    column: str | None = None
    message: str


class DataImportOut(BaseModel):
    id: uuid.UUID
    data_object_id: uuid.UUID
    source_attachment_id: uuid.UUID
    payload_id: uuid.UUID | None
    status: str
    source_format: str
    parser_key: str
    parser_version: int
    sheet_name: str | None
    source_sha256: str
    headers: list[str]
    mapping_json: dict[str, Any] | None
    warnings: list[Diagnostic]
    errors: list[Diagnostic]
    row_count: int | None
    created_at: datetime
    completed_at: datetime | None


class ImportPreviewOut(DataImportOut):
    available_sheets: list[str]
    preview_rows: list[list[Any]]
    column_count: int


class DataPayloadOut(BaseModel):
    id: uuid.UUID
    data_object_id: uuid.UUID
    payload_kind: str
    name: str
    schema_key: str
    schema_version: int
    metadata_jsonb: dict[str, Any]
    summary_jsonb: dict[str, Any]
    source_attachment_id: uuid.UUID | None
    payload_sha256: str
    points_count: int
    created_at: datetime


class DataPointOut(BaseModel):
    payload_id: uuid.UUID
    ordinal: int
    source_row_number: int
    x_value: float
    y_value: float


class GraphEdgeOut(BaseModel):
    id: uuid.UUID | None = None
    source: uuid.UUID
    target: uuid.UUID
    type: RelationType
    role: str | None = None


class SampleDirectContext(BaseModel):
    producing_processes: list[ResearchObjectOut]
    precursor_samples: list[ResearchObjectOut]
    materials: list[ResearchObjectOut]
    equipment: list[ResearchObjectOut]
    testing_processes: list[ResearchObjectOut]
    sample_inputs: list[SampleInputContext]
    data: list[ResearchObjectOut]


class SampleInputContext(BaseModel):
    object: ResearchObjectOut
    role: str
    relation_id: uuid.UUID


class LineageContext(BaseModel):
    samples: list[ResearchObjectOut]
    data: list[ResearchObjectOut]
    edges: list[GraphEdgeOut]
    depth: int
    truncated: bool


class ExperimentContext(BaseModel):
    experiment: ResearchObjectOut
    processes: list[ResearchObjectOut]
    samples: list[ResearchObjectOut]
    input_samples: list[ResearchObjectOut]
    data: list[ResearchObjectOut]
    materials: list[ResearchObjectOut]
    equipment: list[ResearchObjectOut]


class SampleContextOut(BaseModel):
    current: ResearchObjectOut
    direct: SampleDirectContext
    upstream: LineageContext
    downstream: LineageContext
    experiment_context: ExperimentContext | None


class ProjectSummaryOut(BaseModel):
    project: ResearchObjectOut
    counts: dict[str, int]
    recent: list[ResearchObjectOut]


class WorkspaceSummaryOut(BaseModel):
    counts: dict[str, int]
    recent: list[ResearchObjectOut]
    projects: list[ResearchObjectOut]


SampleDirectContext.model_rebuild()
ProcessCompositionOut.model_rebuild()
