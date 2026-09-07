from __future__ import annotations

import math
import uuid
from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

ObjectKind = Literal[
    "research_object", "process_definition", "data", "experiment", "project", "view", "claim"
]
RelationType = Literal["references", "subject", "derived_from", "related_to"]
BindingDirection = Literal["input", "context", "output"]
RepresentationKind = Literal["raw_file", "table", "image", "description", "structured"]
ValueType = Literal["number", "text", "boolean", "select"]


class UsageFieldDefinition(BaseModel):
    model_config = ConfigDict(extra="forbid")
    key: str = Field(min_length=1, max_length=120)
    label: str = Field(min_length=1, max_length=120)
    value_type: ValueType
    default_value: Any = None
    default_unit: str | None = Field(default=None, max_length=64)
    required: bool = False
    options: list[str] = Field(default_factory=list)
    order: int = Field(default=0, ge=0)

    @field_validator("key", "label")
    @classmethod
    def non_blank(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("must not be blank")
        return value

    @model_validator(mode="after")
    def validate_options(self) -> UsageFieldDefinition:
        if self.value_type == "select" and not self.options:
            raise ValueError("select fields require options")
        if self.value_type != "select" and self.options:
            raise ValueError("options are only valid for select fields")
        if len(set(self.options)) != len(self.options):
            raise ValueError("field options must be unique")
        return self


class ProcessFieldSchema(BaseModel):
    model_config = ConfigDict(extra="forbid")
    fields: list[UsageFieldDefinition] = Field(default_factory=list)

    @model_validator(mode="after")
    def unique_keys(self) -> ProcessFieldSchema:
        keys = [field.key for field in self.fields]
        if len(keys) != len(set(keys)):
            raise ValueError("field keys must be unique")
        return self


class UsageValue(BaseModel):
    model_config = ConfigDict(extra="forbid")
    value: Any
    unit: str | None = Field(default=None, max_length=64)

    @model_validator(mode="after")
    def scalar_only(self) -> UsageValue:
        if isinstance(self.value, (dict, list, tuple, set)):
            raise ValueError("binding values must be scalar")
        if isinstance(self.value, float) and not math.isfinite(self.value):
            raise ValueError("binding value must be finite")
        return self


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
    type_key: str = "generic"
    type_label_zh: str = ""
    type_label_en: str = ""


class ResearchObjectOut(ObjectSummary):
    type_version_id: uuid.UUID | None = None
    type_version: int | None = None
    tags: list[str] = Field(default_factory=list)
    properties_jsonb: dict[str, Any] = Field(default_factory=dict)
    process_field_definitions: dict[str, Any] = Field(default_factory=dict)
    content_document: list[dict[str, Any]] = Field(default_factory=list)
    document_format_version: int = 1
    authoring_kind: Literal["sample", "data"] | None = None
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
    tags: list[str] = Field(default_factory=list)
    properties_jsonb: dict[str, Any] = Field(default_factory=dict)
    process_field_definitions: dict[str, Any] = Field(default_factory=dict)
    content_document: list[dict[str, Any]] = Field(default_factory=list)

    @field_validator("title", "status")
    @classmethod
    def text_value(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("must not be blank")
        return value

    @field_validator("tags")
    @classmethod
    def normalize_tags(cls, value: list[str]) -> list[str]:
        result: list[str] = []
        for item in value:
            item = item.strip()
            if item and item not in result:
                result.append(item)
        return result


class ResearchObjectCreate(BaseModel):
    model_config = ConfigDict(extra="allow")
    project_scope_id: uuid.UUID | None = None
    title: str = Field(min_length=1, max_length=240)
    code: str | None = Field(default=None, min_length=1, max_length=32)
    status: str = Field(default="active", min_length=1, max_length=32)
    tags: list[str] = Field(default_factory=list)
    properties_jsonb: dict[str, Any] = Field(default_factory=dict)
    process_field_definitions: dict[str, Any] = Field(default_factory=dict)
    content_document: list[dict[str, Any]] = Field(default_factory=list)
    type_version_id: uuid.UUID | None = None


class ObjectPatch(BaseModel):
    model_config = ConfigDict(extra="forbid")
    title: str | None = Field(default=None, min_length=1, max_length=240)
    status: str | None = Field(default=None, min_length=1, max_length=32)
    project_scope_id: uuid.UUID | None = None
    tags: list[str] | None = None
    properties_jsonb: dict[str, Any] | None = None
    process_field_definitions: dict[str, Any] | None = None
    content_document: list[dict[str, Any]] | None = None


class RelationCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")
    source_object_id: uuid.UUID
    target_object_id: uuid.UUID
    relation_type: RelationType
    role: str | None = Field(default=None, max_length=64)
    properties_jsonb: dict[str, Any] = Field(default_factory=dict)


class RelationPatch(BaseModel):
    model_config = ConfigDict(extra="forbid")
    role: str | None = Field(default=None, max_length=64)
    properties_jsonb: dict[str, Any] | None = None


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


class ProcessDefinitionCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")
    project_scope_id: uuid.UUID | None = None
    title: str = Field(min_length=1, max_length=240)
    code: str | None = Field(default=None, min_length=1, max_length=32)
    status: str = Field(default="active", min_length=1, max_length=32)
    tags: list[str] = Field(default_factory=list)
    properties_jsonb: dict[str, Any] = Field(default_factory=dict)
    content_document: list[dict[str, Any]] = Field(default_factory=list)
    description: str | None = None
    execution_field_definitions: dict[str, Any] = Field(default_factory=dict)
    ui_schema: dict[str, Any] | None = None
    version: int | None = Field(default=None, ge=1)


class ProcessDefinitionVersionCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")
    description: str | None = None
    execution_field_definitions: dict[str, Any] = Field(default_factory=dict)
    ui_schema: dict[str, Any] | None = None


class ProcessDefinitionVersionOut(BaseModel):
    id: uuid.UUID
    process_definition_id: uuid.UUID
    version: int
    description: str | None
    execution_field_definitions: dict[str, Any]
    ui_schema: dict[str, Any] | None
    created_at: datetime


class ProcessDefinitionOut(BaseModel):
    process_definition: ResearchObjectOut
    current_version: ProcessDefinitionVersionOut
    versions: list[ProcessDefinitionVersionOut] = Field(default_factory=list)


class ProcessExecutionObjectBindingCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")
    research_object_id: uuid.UUID | None = None
    object_id: uuid.UUID | None = None
    binding_id: uuid.UUID | None = None
    authoring_occurrence_id: uuid.UUID | None = None
    research_object_revision_id: uuid.UUID | None = None
    direction: BindingDirection
    role: str | None = Field(default=None, max_length=64)
    field_definition_snapshot: dict[str, Any] | None = None
    values: dict[str, UsageValue] = Field(default_factory=dict)
    order_index: int = Field(default=0, ge=0)

    @model_validator(mode="after")
    def object_identity(self) -> ProcessExecutionObjectBindingCreate:
        if self.research_object_id is None:
            self.research_object_id = self.object_id
        if self.research_object_id is None:
            raise ValueError("research_object_id is required")
        return self


class ProcessExecutionDataBindingCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")
    data_id: uuid.UUID
    binding_id: uuid.UUID | None = None
    data_revision_id: uuid.UUID | None = None
    direction: Literal["input", "output"]
    role: str | None = Field(default=None, max_length=64)
    values: dict[str, Any] = Field(default_factory=dict)
    order_index: int = Field(default=0, ge=0)


class ProcessExecutionCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")
    process_definition_id: uuid.UUID
    process_definition_version_id: uuid.UUID | None = None
    project_scope_id: uuid.UUID | None = None
    title_snapshot: str | None = Field(default=None, max_length=240)
    status: Literal["draft", "recorded", "running", "completed", "cancelled"] = "draft"
    execution_field_definitions: dict[str, Any] | None = None
    values: dict[str, Any] = Field(default_factory=dict)
    note: str | None = None
    occurred_at: datetime | None = None
    object_bindings: list[ProcessExecutionObjectBindingCreate] = Field(default_factory=list)
    data_bindings: list[ProcessExecutionDataBindingCreate] = Field(default_factory=list)
    precedes_execution_ids: list[uuid.UUID] = Field(default_factory=list)
    source_view_id: uuid.UUID | None = None
    source_view_revision_id: uuid.UUID | None = None


class ProcessExecutionPut(ProcessExecutionCreate):
    process_definition_id: uuid.UUID | None = None
    execution_id: uuid.UUID | None = None
    change_note: str | None = None
    base_record_sha256: str | None = None


class ProcessExecutionObjectBindingOut(BaseModel):
    id: uuid.UUID
    authoring_occurrence_id: uuid.UUID | None = None
    research_object_id: uuid.UUID
    research_object_revision_id: uuid.UUID | None = None
    direction: BindingDirection
    role: str | None
    is_active: bool = True
    field_definition_snapshot: dict[str, Any]
    values: dict[str, Any]
    order_index: int
    object: ResearchObjectOut


class ProcessExecutionDataBindingOut(BaseModel):
    id: uuid.UUID
    data_id: uuid.UUID
    data_revision_id: uuid.UUID | None = None
    direction: Literal["input", "output"]
    role: str | None
    values: dict[str, Any]
    order_index: int
    data: ResearchObjectOut


class ProcessExecutionOut(BaseModel):
    record_sha256: str
    id: uuid.UUID
    authoring_record_id: uuid.UUID | None = None
    authoring_occurrence_id: uuid.UUID | None = None
    project_scope_id: uuid.UUID | None
    process_definition_id: uuid.UUID
    process_definition_version_id: uuid.UUID
    source_view_id: uuid.UUID | None = None
    source_view_revision_id: uuid.UUID | None = None
    title_snapshot: str | None
    status: str
    record_validity: Literal["active", "retracted"] = "active"
    execution_field_definitions: dict[str, Any]
    values: dict[str, Any]
    note: str | None
    occurred_at: datetime | None
    started_at: datetime | None
    completed_at: datetime | None
    created_at: datetime
    updated_at: datetime
    object_bindings: list[ProcessExecutionObjectBindingOut]
    data_bindings: list[ProcessExecutionDataBindingOut]
    precedes_execution_ids: list[uuid.UUID] = Field(default_factory=list)


class ProcessExecutionRevisionOut(BaseModel):
    id: uuid.UUID
    execution_id: uuid.UUID
    revision_number: int
    snapshot_jsonb: dict[str, Any]
    snapshot_sha256: str
    change_note: str | None
    created_at: datetime


class ScientificDocumentV1(BaseModel):
    model_config = ConfigDict(extra="forbid")
    schema_version: Literal[1] = 1
    blocks: list[dict[str, Any]] = Field(default_factory=list)


class ScientificBindingDraft(BaseModel):
    model_config = ConfigDict(extra="forbid")
    process_occurrence_id: uuid.UUID
    binding_id: uuid.UUID | None = None
    direction: BindingDirection
    role: str | None = Field(default=None, max_length=64)


class ScientificOccurrenceDraft(BaseModel):
    model_config = ConfigDict(extra="forbid")
    occurrence_id: uuid.UUID
    kind: Literal["process", "object"]
    target_id: uuid.UUID
    target_revision_id: uuid.UUID | None = None
    execution_id: uuid.UUID | None = None
    process_definition_version_id: uuid.UUID | None = None
    label_snapshot: str | None = Field(default=None, max_length=240)
    field_definitions: dict[str, Any] = Field(default_factory=dict)
    values: dict[str, Any] = Field(default_factory=dict)
    status: Literal["recorded", "running", "completed"] = "recorded"
    binding: ScientificBindingDraft | None = None

    @model_validator(mode="after")
    def validate_kind_fields(self) -> ScientificOccurrenceDraft:
        if self.kind == "process" and self.binding is not None:
            raise ValueError("process occurrences cannot carry object bindings")
        if self.kind == "object" and self.execution_id is not None:
            raise ValueError("object occurrences cannot carry execution_id")
        return self


class ScientificOccurrenceOut(ScientificOccurrenceDraft):
    execution: ProcessExecutionOut | None = None
    object: ResearchObjectOut | None = None


class SampleRecordObjectCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")
    title: str = Field(min_length=1, max_length=240)
    code: str | None = Field(default=None, min_length=1, max_length=32)
    status: str = "draft"
    tags: list[str] = Field(default_factory=lambda: ["样品"])
    properties_jsonb: dict[str, Any] = Field(default_factory=dict)
    process_field_definitions: dict[str, Any] = Field(default_factory=dict)
    content_document: list[dict[str, Any]] = Field(default_factory=list)


class SampleRecordStepDraft(BaseModel):
    model_config = ConfigDict(extra="allow")
    execution_id: uuid.UUID | None = None
    process_definition_id: uuid.UUID
    process_definition_version_id: uuid.UUID | None = None
    title_snapshot: str | None = None
    status: Literal["draft", "running", "completed", "cancelled"] = "draft"
    values: dict[str, Any] = Field(default_factory=dict)
    object_bindings: list[ProcessExecutionObjectBindingCreate] = Field(default_factory=list)
    data_bindings: list[ProcessExecutionDataBindingCreate] = Field(default_factory=list)


class SampleRecordCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")
    project_scope_id: uuid.UUID
    sample: SampleRecordObjectCreate
    document: ScientificDocumentV1 = Field(default_factory=ScientificDocumentV1)
    occurrences: list[ScientificOccurrenceDraft] = Field(default_factory=list)
    change_note: str | None = None


class SampleRecordPut(BaseModel):
    model_config = ConfigDict(extra="forbid")
    sample: dict[str, Any] = Field(default_factory=dict)
    document: ScientificDocumentV1
    occurrences: list[ScientificOccurrenceDraft] = Field(default_factory=list)
    base_record_sha256: str
    change_note: str | None = None


class SampleRecordStepOut(BaseModel):
    execution: ProcessExecutionOut
    ordinal: int


class SampleRecordOut(BaseModel):
    record_sha256: str
    sample: ResearchObjectOut
    document: ScientificDocumentV1
    occurrences: list[ScientificOccurrenceOut]
    data: list[ResearchObjectOut]
    editable: bool = True
    edit_blockers: list[str] = Field(default_factory=list)


class SampleBatchRow(BaseModel):
    model_config = ConfigDict(extra="forbid")
    client_row_id: str = Field(min_length=1, max_length=120)
    record: SampleRecordCreate


class SampleBatchCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")
    project_scope_id: uuid.UUID
    rows: list[SampleBatchRow] = Field(min_length=1, max_length=100)


class SampleBatchResultRow(BaseModel):
    client_row_id: str
    record: SampleRecordOut


class SampleBatchOut(BaseModel):
    rows: list[SampleBatchResultRow]


class RecordTableFieldRef(BaseModel):
    model_config = ConfigDict(extra="forbid")
    target_id: uuid.UUID
    field_key: str = Field(min_length=1, max_length=120)
    label: str | None = Field(default=None, max_length=240)
    value_type: ValueType | None = None

    @property
    def column_key(self) -> str:
        return f"{self.target_id}:{self.field_key}"


class RecordTableFilter(RecordTableFieldRef):
    operator: Literal["eq", "contains", "gte", "lte", "is_empty", "is_not_empty"]
    value: str | float | bool | None = None


class RecordTableSort(RecordTableFieldRef):
    direction: Literal["asc", "desc"] = "asc"


class RecordTableQuery(BaseModel):
    model_config = ConfigDict(extra="forbid")
    project_scope_id: uuid.UUID
    record_kind: Literal["sample", "data"] = "sample"
    q: str | None = Field(default=None, max_length=240)
    record_ids: list[uuid.UUID] | None = None
    required_refs: list[uuid.UUID] = Field(default_factory=list)
    filters: list[RecordTableFilter] = Field(default_factory=list)
    display_columns: list[RecordTableFieldRef] = Field(default_factory=list)
    sort: RecordTableSort | None = None
    limit: int = Field(default=50, ge=1, le=200)
    offset: int = Field(default=0, ge=0)


class RecordTableValueOut(BaseModel):
    occurrence_id: uuid.UUID
    target_id: uuid.UUID
    field_key: str
    value_type: ValueType
    value: str | float | bool | None
    unit: str | None
    ordinal: int


class RecordTableRowOut(BaseModel):
    record: ResearchObjectOut
    referenced_target_ids: list[uuid.UUID]
    values: dict[str, list[RecordTableValueOut]]


class RecordTableResultOut(BaseModel):
    rows: list[RecordTableRowOut]
    total: int
    limit: int
    offset: int
    columns: list[RecordTableFieldRef]


class ExperimentObjectCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")
    title: str = Field(min_length=1, max_length=240)
    code: str | None = None
    status: str = "draft"
    tags: list[str] = Field(default_factory=list)
    properties_jsonb: dict[str, Any] = Field(default_factory=dict)
    content_document: list[dict[str, Any]] = Field(default_factory=list)


class ExperimentReferenceCreate(BaseModel):
    target_id: uuid.UUID
    target_kind: ObjectKind | None = None
    role: str | None = Field(default=None, max_length=64)
    note: str | None = Field(default=None, max_length=500)
    order_index: int = Field(default=0, ge=0)


class ExperimentRecordCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")
    project_scope_id: uuid.UUID
    experiment: ExperimentObjectCreate
    references: list[ExperimentReferenceCreate] = Field(default_factory=list)
    change_note: str | None = None


class ExperimentRecordPut(BaseModel):
    model_config = ConfigDict(extra="forbid")
    experiment: dict[str, Any] = Field(default_factory=dict)
    references: list[ExperimentReferenceCreate] = Field(default_factory=list)
    change_note: str | None = None
    base_record_sha256: str | None = Field(default=None, min_length=64, max_length=64)


class ExperimentMetadataPatch(BaseModel):
    model_config = ConfigDict(extra="forbid")
    title: str | None = Field(default=None, min_length=1, max_length=240)
    status: str | None = None
    tags: list[str] | None = None
    properties_jsonb: dict[str, Any] | None = None
    content_document: list[dict[str, Any]] | None = None
    change_note: str | None = None


class ExperimentReferenceOrder(BaseModel):
    model_config = ConfigDict(extra="forbid")
    relation_ids: list[uuid.UUID]
    change_note: str | None = None


class ExperimentReferenceOut(BaseModel):
    relation_id: uuid.UUID
    role: str | None
    note: str | None
    order_index: int
    object: ResearchObjectOut


class ExperimentRecordOut(BaseModel):
    record_sha256: str
    experiment: ResearchObjectOut
    references: dict[str, list[ExperimentReferenceOut]]


class DataRecordObjectCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")
    title: str = Field(min_length=1, max_length=240)
    code: str | None = None
    status: str = "draft"
    tags: list[str] = Field(default_factory=list)
    properties_jsonb: dict[str, Any] = Field(default_factory=dict)
    content_document: list[dict[str, Any]] = Field(default_factory=list)


class DataRecordCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")
    project_scope_id: uuid.UUID
    data: DataRecordObjectCreate
    scientific_type: str | None = None
    description: str | None = None
    subject_ids: list[uuid.UUID] = Field(default_factory=list)
    change_note: str | None = None


class DataRecordPut(BaseModel):
    model_config = ConfigDict(extra="forbid")
    title: str | None = None
    status: str | None = None
    tags: list[str] | None = None
    properties_jsonb: dict[str, Any] | None = None
    scientific_type: str | None = None
    description: str | None = None
    subject_ids: list[uuid.UUID] | None = None
    document: ScientificDocumentV1 | None = None
    occurrences: list[ScientificOccurrenceDraft] | None = None
    change_note: str | None = None
    base_record_sha256: str | None = Field(default=None, min_length=64, max_length=64)


class DataSubjectAssignmentOut(BaseModel):
    id: uuid.UUID
    subject_id: uuid.UUID
    subject_revision_id: uuid.UUID | None
    source_kind: Literal["manual", "acquisition_document", "producer"]
    source_ref_id: uuid.UUID | None


class DataTableColumn(BaseModel):
    model_config = ConfigDict(extra="forbid")
    key: str = Field(min_length=1, max_length=120)
    label: str = Field(min_length=1, max_length=240)
    value_type: Literal["number", "text", "boolean"]
    unit: str | None = None
    role: (
        Literal[
            "coordinate", "value", "entity", "category", "uncertainty", "timestamp", "replicate"
        ]
        | None
    ) = None
    semantic_name: str | None = None


class DataRepresentationCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")
    kind: RepresentationKind
    name: str = Field(min_length=1, max_length=240)
    format: str | None = None
    schema_jsonb: dict[str, Any] = Field(default_factory=dict)
    metadata_jsonb: dict[str, Any] = Field(default_factory=dict)
    summary_jsonb: dict[str, Any] = Field(default_factory=dict)
    inline_payload_jsonb: dict[str, Any] | None = None
    asset_id: uuid.UUID | None = None
    source_representation_id: uuid.UUID | None = None
    provenance_jsonb: dict[str, Any] = Field(default_factory=dict)


class DataRepresentationOut(BaseModel):
    id: uuid.UUID
    data_object_id: uuid.UUID
    kind: RepresentationKind
    name: str
    format: str | None
    schema_jsonb: dict[str, Any]
    metadata_jsonb: dict[str, Any]
    summary_jsonb: dict[str, Any]
    inline_payload_jsonb: dict[str, Any] | None
    asset_id: uuid.UUID | None
    source_representation_id: uuid.UUID | None
    provenance_jsonb: dict[str, Any]
    representation_sha256: str
    points_count: int = 0
    table_rows_count: int = 0
    table_rows: list[dict[str, Any]] = Field(default_factory=list)
    scalar: dict[str, Any] | None = None
    created_at: datetime


class DataRecordOut(BaseModel):
    record_sha256: str
    data: ResearchObjectOut
    document: ScientificDocumentV1 = Field(default_factory=ScientificDocumentV1)
    occurrences: list[ScientificOccurrenceOut] = Field(default_factory=list)
    editable: bool = True
    edit_blockers: list[str] = Field(default_factory=list)
    scientific_type: str | None
    description: str | None
    origin_representation_id: uuid.UUID | None
    representations: list[DataRepresentationOut]
    subjects: list[ResearchObjectOut] = Field(default_factory=list)
    subject_assignments: list[DataSubjectAssignmentOut] = Field(default_factory=list)
    derived_from: list[ResearchObjectOut] = Field(default_factory=list)
    imports: list[dict[str, Any]] = Field(default_factory=list)


class DataDraftContent(BaseModel):
    model_config = ConfigDict(extra="forbid")
    title: str = Field(min_length=1, max_length=240)
    tags: list[str] = Field(default_factory=list)
    scientific_type: str | None = None
    description: str | None = None
    document: ScientificDocumentV1 = Field(default_factory=ScientificDocumentV1)
    occurrences: list[ScientificOccurrenceDraft] = Field(default_factory=list)
    subject_ids: list[uuid.UUID] = Field(default_factory=list)
    source_sample_id: uuid.UUID | None = None
    origin_client_attachment_id: str | None = Field(default=None, max_length=120)


class DataDraftBegin(BaseModel):
    model_config = ConfigDict(extra="forbid")
    project_scope_id: uuid.UUID
    content: DataDraftContent


class DataDraftUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")
    base_record_sha256: str
    content: DataDraftContent


class DataDraftAttachmentCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")
    client_attachment_id: str = Field(min_length=1, max_length=120)
    asset_id: uuid.UUID


class DataDraftFinalize(BaseModel):
    model_config = ConfigDict(extra="forbid")
    base_record_sha256: str


class DataDraftOut(BaseModel):
    id: uuid.UUID
    data_id: uuid.UUID
    project_scope_id: uuid.UUID
    status: Literal["editing", "finalized"]
    content: DataDraftContent
    attachments: list[dict[str, Any]]
    record_sha256: str
    finalized_result: DataRecordOut | None = None
    created_at: datetime
    updated_at: datetime


class AssetOut(BaseModel):
    id: uuid.UUID
    storage_backend: str
    bucket: str | None
    object_key: str
    original_filename: str
    mime_type: str | None
    size_bytes: int
    sha256: str
    created_at: datetime


class ViewDataRefCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")
    data_id: uuid.UUID
    data_revision_id: uuid.UUID
    representation_ids: list[uuid.UUID] = Field(default_factory=list)


class ViewDataRefOut(ViewDataRefCreate):
    order_index: int


class ViewCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")
    project_scope_id: uuid.UUID
    title: str = Field(min_length=1, max_length=240)
    code: str | None = None
    description: str | None = None
    config: dict[str, Any] = Field(default_factory=dict)
    data_refs: list[ViewDataRefCreate] = Field(default_factory=list)
    artifact_asset_id: uuid.UUID | None = None


class ViewPut(BaseModel):
    model_config = ConfigDict(extra="forbid")
    title: str | None = None
    status: str | None = None
    description: str | None = None
    config: dict[str, Any] | None = None
    data_refs: list[ViewDataRefCreate] | None = None
    artifact_asset_id: uuid.UUID | None = None
    change_note: str | None = None
    base_record_sha256: str | None = None


class ViewRevisionOut(BaseModel):
    id: uuid.UUID
    view_id: uuid.UUID
    revision_number: int
    snapshot_jsonb: dict[str, Any]
    snapshot_sha256: str
    change_note: str | None
    created_at: datetime


class ViewOut(BaseModel):
    record_sha256: str
    view: ResearchObjectOut
    description: str | None
    config: dict[str, Any]
    data: list[ResearchObjectOut]
    data_refs: list[ViewDataRefOut]
    artifact_asset_id: uuid.UUID | None
    artifact_sha256: str | None
    current_revision_id: uuid.UUID | None
    revisions: list[ViewRevisionOut] = Field(default_factory=list)


class ClaimPrimarySource(BaseModel):
    model_config = ConfigDict(extra="forbid")
    kind: Literal["experiment", "data", "view"]
    object_id: uuid.UUID
    revision_id: uuid.UUID


class ClaimCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")
    project_scope_id: uuid.UUID
    title: str | None = Field(default=None, min_length=1, max_length=240)
    statement: str = Field(min_length=1)
    code: str | None = None
    author_provenance: dict[str, Any] = Field(default_factory=lambda: {"kind": "human"})
    primary_source: ClaimPrimarySource
    confidence: str | None = None
    metadata_jsonb: dict[str, Any] = Field(default_factory=dict)
    evidence: list[dict[str, Any]] = Field(default_factory=list)


class ClaimPut(BaseModel):
    model_config = ConfigDict(extra="forbid")
    title: str | None = None
    status: str | None = None
    statement: str | None = None
    author_provenance: dict[str, Any] | None = None
    primary_source: ClaimPrimarySource | None = None
    refresh_context: bool = False
    confidence: str | None = None
    metadata_jsonb: dict[str, Any] | None = None
    evidence: list[dict[str, Any]] | None = None
    change_note: str | None = None
    base_record_sha256: str | None = None


class ClaimEvidenceOut(BaseModel):
    id: uuid.UUID
    evidence_kind: Literal["data", "view", "claim", "external"]
    evidence_id: uuid.UUID | None
    external_ref: str | None
    polarity: Literal["support", "counter"]
    note: str | None
    order_index: int
    object: ResearchObjectOut | None = None


class ClaimRevisionOut(BaseModel):
    id: uuid.UUID
    claim_id: uuid.UUID
    revision_number: int
    snapshot_jsonb: dict[str, Any]
    snapshot_sha256: str
    change_note: str | None
    created_at: datetime


class ClaimOut(BaseModel):
    record_sha256: str
    claim: ResearchObjectOut
    statement: str
    author_provenance: dict[str, Any]
    primary_source: ClaimPrimarySource
    primary_source_object: ResearchObjectOut
    context_snapshot: dict[str, Any]
    confidence: str | None
    metadata_jsonb: dict[str, Any]
    evidence: list[ClaimEvidenceOut]
    revisions: list[ClaimRevisionOut]
    current_revision_id: uuid.UUID | None


class SampleContextOut(BaseModel):
    current: ResearchObjectOut
    producing_executions: list[ProcessExecutionOut]
    inputs: list[ResearchObjectOut]
    data: list[ResearchObjectOut]
    upstream: list[ResearchObjectOut]
    downstream: list[ResearchObjectOut]


class ProjectContextOut(BaseModel):
    record_sha256: str
    project: ResearchObjectOut
    counts: dict[str, int]
    recent_research_objects: list[ResearchObjectOut] = Field(default_factory=list)
    recent_experiments: list[ResearchObjectOut] = Field(default_factory=list)
    recent_data: list[ResearchObjectOut] = Field(default_factory=list)
    capabilities: dict[str, Any] = Field(default_factory=dict)


class WorkspaceSummaryOut(BaseModel):
    counts: dict[str, int]
    recent: list[ResearchObjectOut] = Field(default_factory=list)
    projects: list[ResearchObjectOut] = Field(default_factory=list)


class ProjectRecordCreate(BaseModel):
    project: dict[str, Any]
    change_note: str | None = None


class ProjectRecordPut(BaseModel):
    model_config = ConfigDict(extra="allow")
    title: str | None = None
    status: str | None = None
    tags: list[str] | None = None
    properties_jsonb: dict[str, Any] | None = None
    content_document: list[dict[str, Any]] | None = None
    change_note: str | None = None


class ProjectRecordOut(BaseModel):
    record_sha256: str
    project: ResearchObjectOut
    context: dict[str, Any]


class ProjectSearchOut(BaseModel):
    items: list[ResearchObjectOut]
    total: int
    limit: int
    offset: int


class ChangeSetOut(BaseModel):
    id: uuid.UUID
    project_scope_id: uuid.UUID
    status: Literal["proposed", "approved", "rejected", "applied", "stale", "failed"]
    operation_kind: str
    target_kind: str
    target_id: uuid.UUID | None
    base_record_sha256: str | None
    request_payload_jsonb: dict[str, Any]
    preview_jsonb: dict[str, Any]
    diff_jsonb: list[dict[str, Any]]
    source_client_name: str
    source_client_version: str | None
    source_transport: str
    idempotency_key: str | None
    created_at: datetime
    reviewed_at: datetime | None
    applied_at: datetime | None
    applied_result_jsonb: dict[str, Any] | None
    failure_jsonb: dict[str, Any] | None


class ChangeSetProposal(BaseModel):
    model_config = ConfigDict(extra="forbid")
    operation_kind: Literal[
        "create_research_object",
        "update_research_object",
        "create_process_definition",
        "create_process_execution",
        "update_process_execution",
        "create_sample_record",
        "update_sample_record",
        "create_data_record",
        "update_data_record",
        "create_experiment_record",
        "update_experiment_record",
        "create_view",
        "update_view",
        "create_claim",
        "update_claim",
    ]
    project_scope_id: uuid.UUID
    target_id: uuid.UUID | None = None
    base_record_sha256: str | None = None
    request_payload_jsonb: dict[str, Any]
    source_client_name: str = "external-agent"
    source_client_version: str | None = None
    source_transport: str = "mcp"


class ChangeSetReview(BaseModel):
    model_config = ConfigDict(extra="forbid")
    decision: Literal["approve", "reject"]
    edited_payload_jsonb: dict[str, Any] | None = None


class RevisionCreate(BaseModel):
    change_note: str | None = None


class ObjectRevisionOut(BaseModel):
    id: uuid.UUID
    object_id: uuid.UUID
    revision_number: int
    snapshot_jsonb: dict[str, Any]
    snapshot_sha256: str
    change_note: str | None
    change_set_id: uuid.UUID | None = None
    source_client_name: str | None = None
    source_client_version: str | None = None
    source_transport: str | None = None
    created_at: datetime


class ImportPreviewRequest(BaseModel):
    source_asset_id: uuid.UUID
    sheet_name: str | None = None


class ImportCommitMapping(BaseModel):
    model_config = ConfigDict(extra="allow")
    representation_name: str = Field(min_length=1, max_length=240)
    representation_kind: Literal["table"] = "table"
    columns: list[DataTableColumn] = Field(min_length=1)
    sheet_name: str | None = None


class DataImportOut(BaseModel):
    id: uuid.UUID
    data_object_id: uuid.UUID
    source_asset_id: uuid.UUID
    representation_id: uuid.UUID | None
    status: str
    source_format: str
    parser_key: str
    parser_version: int
    sheet_name: str | None
    source_sha256: str
    headers: list[str]
    mapping_json: dict[str, Any] | None
    warnings: list[dict[str, Any]]
    errors: list[dict[str, Any]]
    row_count: int | None
    created_at: datetime
    completed_at: datetime | None


class ImportPreviewOut(DataImportOut):
    available_sheets: list[str]
    preview_rows: list[list[Any]]
    column_count: int
