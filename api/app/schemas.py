from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

ProjectStatus = Literal["active", "paused", "completed", "archived"]
ExperimentStatus = Literal["draft", "planned", "running", "completed", "cancelled"]


def non_blank(value: str) -> str:
    value = value.strip()
    if not value:
        raise ValueError("must not be blank")
    return value


class ProjectCreate(BaseModel):
    title: str = Field(min_length=1, max_length=240)
    description: str | None = Field(default=None, max_length=10000)
    status: ProjectStatus = "active"

    _title = field_validator("title")(non_blank)


class ProjectUpdate(BaseModel):
    title: str | None = Field(default=None, min_length=1, max_length=240)
    description: str | None = Field(default=None, max_length=10000)
    status: ProjectStatus | None = None

    _title = field_validator("title")(non_blank)


class ProjectOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    code: str
    title: str
    description: str | None
    status: ProjectStatus
    experiment_count: int = 0
    created_at: datetime
    updated_at: datetime


class TemplateOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    key: str
    name: str
    version: int
    json_schema: dict[str, Any]
    ui_schema: dict[str, Any] | None
    is_active: bool
    created_at: datetime


class ExperimentCreate(BaseModel):
    title: str = Field(min_length=1, max_length=240)
    template_id: uuid.UUID
    status: ExperimentStatus = "draft"
    objective: str | None = Field(default=None, max_length=10000)
    structured_data: dict[str, Any] = Field(default_factory=dict)
    note_document: list[dict[str, Any]] = Field(default_factory=list)

    _title = field_validator("title")(non_blank)


class ExperimentUpdate(BaseModel):
    title: str | None = Field(default=None, min_length=1, max_length=240)
    status: ExperimentStatus | None = None
    objective: str | None = Field(default=None, max_length=10000)
    structured_data: dict[str, Any] | None = None
    note_document: list[dict[str, Any]] | None = None

    _title = field_validator("title")(non_blank)


class ExperimentOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    code: str
    project_id: uuid.UUID
    template_id: uuid.UUID
    template_version: int
    parent_experiment_id: uuid.UUID | None
    title: str
    status: ExperimentStatus
    objective: str | None
    structured_data: dict[str, Any]
    note_document: list[dict[str, Any]]
    created_at: datetime
    updated_at: datetime


class CloneRequest(BaseModel):
    new_title: str = Field(min_length=1, max_length=240)
    copy_note: bool = True
    copy_structured_data: bool = True

    _title = field_validator("new_title")(non_blank)


class AttachmentOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    experiment_id: uuid.UUID
    original_filename: str
    content_type: str | None
    size_bytes: int
    sha256: str
    created_at: datetime


class RevisionCreate(BaseModel):
    change_note: str | None = Field(default=None, max_length=500)


class RevisionOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    experiment_id: uuid.UUID
    revision_number: int
    snapshot_json: dict[str, Any]
    change_note: str | None
    created_at: datetime


MeasurementType = Literal["spectral_response", "time_series", "other_xy"]
ChartType = Literal["line", "scatter"]
ImportStatus = Literal["preview_ready", "completed", "failed"]
LiteratureItemType = Literal[
    "journal_article", "conference_paper", "book_chapter", "report", "preprint", "other"
]
LiteratureRelationship = Literal[
    "background", "method", "comparison", "supporting", "contradicting"
]
EvidenceStance = Literal["supports", "contradicts", "context"]
EvidenceStatus = Literal["active", "withdrawn"]


class ImportErrorItem(BaseModel):
    row: int | None = None
    column: str | None = None
    message: str


class ImportDiagnostic(BaseModel):
    code: str
    message: str
    import_id: uuid.UUID | None = None
    errors: list[ImportErrorItem] = Field(default_factory=list)
    warnings: list[ImportErrorItem] = Field(default_factory=list)


class ImportPreviewRequest(BaseModel):
    source_attachment_id: uuid.UUID
    sheet_name: str | None = Field(default=None, max_length=255)


class ImportCommitMapping(BaseModel):
    measurement_name: str = Field(min_length=1, max_length=240)
    measurement_type: MeasurementType
    default_chart_type: ChartType = "line"
    sheet_name: str | None = Field(default=None, max_length=255)
    x: ImportAxisMapping
    y: ImportAxisMapping

    _name = field_validator("measurement_name")(non_blank)

    @model_validator(mode="after")
    def columns_must_differ(self) -> ImportCommitMapping:
        if self.x.column == self.y.column:
            raise ValueError("x and y columns must be different")
        return self


class ImportAxisMapping(BaseModel):
    column: str = Field(min_length=1, max_length=255)
    label: str = Field(min_length=1, max_length=120)
    unit: str = Field(min_length=1, max_length=64)

    _column = field_validator("column")(non_blank)
    _label = field_validator("label")(non_blank)
    _unit = field_validator("unit")(non_blank)


class ImportPreviewOut(BaseModel):
    id: uuid.UUID
    experiment_id: uuid.UUID
    source_attachment_id: uuid.UUID
    status: ImportStatus
    source_format: str
    parser_key: str
    parser_version: int
    sheet_name: str | None
    available_sheets: list[str] = Field(default_factory=list)
    headers: list[str]
    preview_rows: list[list[Any]]
    row_count: int | None
    column_count: int
    source_sha256: str
    warnings: list[ImportErrorItem] = Field(default_factory=list)
    errors: list[ImportErrorItem] = Field(default_factory=list)
    created_at: datetime


class MeasurementImportOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    experiment_id: uuid.UUID
    source_attachment_id: uuid.UUID
    status: ImportStatus
    source_format: str
    parser_key: str
    parser_version: int
    sheet_name: str | None
    source_sha256: str
    header_json: list[str]
    source_metadata_json: dict[str, Any]
    mapping_json: dict[str, Any] | None
    warnings_json: list[dict[str, Any]]
    errors_json: list[dict[str, Any]]
    row_count: int | None
    completed_at: datetime | None
    created_at: datetime


class MeasurementSummary(BaseModel):
    x_min: float
    x_max: float
    y_min: float
    y_max: float
    y_mean: float


class MeasurementOut(BaseModel):
    id: uuid.UUID
    experiment_id: uuid.UUID
    import_id: uuid.UUID
    name: str
    measurement_type: MeasurementType
    schema_key: str
    schema_version: int
    default_chart_type: ChartType
    x_label: str
    x_unit: str
    y_label: str
    y_unit: str
    row_count: int
    summary_json: MeasurementSummary
    points_sha256: str
    source_attachment_id: uuid.UUID
    source_sha256: str
    created_at: datetime


class MeasurementPointOut(BaseModel):
    ordinal: int
    source_row_number: int
    x_value: float
    y_value: float


class LiteratureAuthor(BaseModel):
    family: str | None = Field(default=None, max_length=240)
    given: str | None = Field(default=None, max_length=240)
    literal: str | None = Field(default=None, max_length=500)

    @model_validator(mode="after")
    def has_name(self) -> LiteratureAuthor:
        if not any((self.family, self.given, self.literal)):
            raise ValueError("author must include family/given or literal")
        return self


class LiteratureCreate(BaseModel):
    item_type: LiteratureItemType = "journal_article"
    title: str = Field(min_length=1, max_length=500)
    authors: list[LiteratureAuthor] = Field(default_factory=list)
    publication_year: int | None = Field(default=None, ge=1000, le=3000)
    container_title: str | None = Field(default=None, max_length=500)
    doi: str | None = Field(default=None, max_length=255)
    url: str | None = Field(default=None, max_length=2000)
    abstract: str | None = None

    _title = field_validator("title")(non_blank)

    @field_validator("url")
    @classmethod
    def valid_url(cls, value: str | None) -> str | None:
        if value is not None and not value.strip().lower().startswith(("http://", "https://")):
            raise ValueError("url must use http or https")
        return value.strip() if value else value


class LiteratureUpdate(BaseModel):
    item_type: LiteratureItemType | None = None
    title: str | None = Field(default=None, min_length=1, max_length=500)
    authors: list[LiteratureAuthor] | None = None
    publication_year: int | None = Field(default=None, ge=1000, le=3000)
    container_title: str | None = Field(default=None, max_length=500)
    doi: str | None = Field(default=None, max_length=255)
    url: str | None = Field(default=None, max_length=2000)
    abstract: str | None = None

    _title = field_validator("title")(non_blank)


class LiteratureOut(BaseModel):
    id: uuid.UUID
    project_id: uuid.UUID
    item_type: LiteratureItemType
    title: str
    authors: list[LiteratureAuthor]
    publication_year: int | None
    container_title: str | None
    doi: str | None
    url: str | None
    abstract: str | None
    provider: str | None
    external_id: str | None
    provider_version: str | None
    created_at: datetime
    updated_at: datetime


class LiteratureLinkCreate(BaseModel):
    literature_id: uuid.UUID
    relationship_type: LiteratureRelationship = "background"
    notes: str | None = Field(default=None, max_length=10000)


class LiteratureLinkUpdate(BaseModel):
    relationship_type: LiteratureRelationship | None = None
    notes: str | None = Field(default=None, max_length=10000)


class LiteratureLinkOut(BaseModel):
    id: uuid.UUID
    experiment_id: uuid.UUID
    literature_id: uuid.UUID
    relationship_type: LiteratureRelationship
    notes: str | None
    created_at: datetime
    literature: LiteratureOut | None = None


class EvidenceSourceLiterature(BaseModel):
    type: Literal["literature"]
    literature_id: uuid.UUID
    locator: str | None = Field(default=None, max_length=500)


class EvidenceSourceMeasurement(BaseModel):
    type: Literal["measurement"]
    measurement_id: uuid.UUID
    locator: str | None = Field(default=None, max_length=500)


class EvidenceSourceRevision(BaseModel):
    type: Literal["experiment_revision"]
    experiment_id: uuid.UUID
    revision_number: int = Field(ge=1)
    locator: str | None = Field(default=None, max_length=500)


EvidenceSource = EvidenceSourceLiterature | EvidenceSourceMeasurement | EvidenceSourceRevision


class EvidenceCreate(BaseModel):
    context_experiment_id: uuid.UUID | None = None
    claim_text: str = Field(min_length=1, max_length=10000)
    stance: EvidenceStance
    source: EvidenceSource
    notes: str | None = Field(default=None, max_length=10000)

    _claim = field_validator("claim_text")(non_blank)


class EvidenceOut(BaseModel):
    id: uuid.UUID
    project_id: uuid.UUID
    context_experiment_id: uuid.UUID | None
    claim_text: str
    stance: EvidenceStance
    source_type: str
    literature_id: uuid.UUID | None
    measurement_id: uuid.UUID | None
    experiment_revision_id: uuid.UUID | None
    locator: str | None
    notes: str | None
    source_snapshot_json: dict[str, Any]
    status: EvidenceStatus
    withdrawal_reason: str | None
    created_at: datetime
    withdrawn_at: datetime | None


class EvidenceWithdrawRequest(BaseModel):
    reason: str = Field(min_length=1, max_length=1000)

    _reason = field_validator("reason")(non_blank)


class CompareRequest(BaseModel):
    project_id: uuid.UUID
    experiment_ids: list[uuid.UUID] = Field(min_length=2, max_length=5)
    measurement_ids: list[uuid.UUID] = Field(default_factory=list)

    @field_validator("experiment_ids")
    @classmethod
    def unique_experiments(cls, values: list[uuid.UUID]) -> list[uuid.UUID]:
        if len(set(values)) != len(values):
            raise ValueError("experiment_ids must be unique")
        return values


class CompareExperimentOut(BaseModel):
    id: uuid.UUID
    code: str
    title: str
    status: ExperimentStatus
    template_id: uuid.UUID
    template_version: int
    parent_experiment_id: uuid.UUID | None


class CompareDifferenceOut(BaseModel):
    path: str
    label: str
    values: dict[str, Any]
    differs: bool


class CompareMeasurementOut(BaseModel):
    id: uuid.UUID
    experiment_id: uuid.UUID
    name: str
    measurement_type: MeasurementType
    schema_key: str
    schema_version: int
    x_label: str
    x_unit: str
    y_label: str
    y_unit: str
    row_count: int
    summary_json: MeasurementSummary
    default_chart_type: ChartType
    compatible: bool
    incompatibility_reason: str | None = None


class CompareOut(BaseModel):
    project_id: uuid.UUID
    experiments: list[CompareExperimentOut]
    structured_differences: list[CompareDifferenceOut]
    measurements: list[CompareMeasurementOut]


ImportCommitMapping.model_rebuild()
