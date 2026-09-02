from __future__ import annotations

import uuid
from datetime import datetime
from typing import Annotated, Any, Literal

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


AnalysisPurpose = Literal["interactive", "evaluation_replay"]
AnalysisRunStatus = Literal["building_context", "running", "completed", "failed", "interrupted"]
StructuredOutputMode = Literal["native_schema", "json_object"]
FindingClaimType = Literal[
    "scientific_observation", "hypothesis", "comparative_finding", "causal_claim", "recommendation"
]
EvidenceGateStatus = Literal[
    "supported", "partially_supported", "insufficient_evidence", "contradicted"
]
ReviewDecisionType = Literal["accept", "reject", "needs_evidence"]
ReviewStatus = Literal["pending_review", "accepted", "rejected", "needs_evidence"]
EvidenceLinkRole = Literal["supporting", "contradicting", "contextual"]


class ExperimentSelection(BaseModel):
    experiment_id: uuid.UUID
    revision_number: int = Field(ge=1)


class AnalysisRunCreate(BaseModel):
    experiment_selections: list[ExperimentSelection] = Field(min_length=2, max_length=5)
    measurement_ids: list[uuid.UUID] = Field(min_length=1, max_length=10)
    literature_ids: list[uuid.UUID] = Field(default_factory=list, max_length=10)
    evidence_ids: list[uuid.UUID] = Field(default_factory=list, max_length=25)
    model_profile_key: str = Field(default="analysis-default", min_length=1, max_length=120)
    prompt_version: int = Field(default=1, ge=1)

    @field_validator("experiment_selections")
    @classmethod
    def unique_experiment_selections(
        cls, values: list[ExperimentSelection]
    ) -> list[ExperimentSelection]:
        ids = [item.experiment_id for item in values]
        if len(set(ids)) != len(ids):
            raise ValueError("experiment_selections must be unique")
        return values

    @field_validator("measurement_ids", "literature_ids", "evidence_ids")
    @classmethod
    def unique_ids(cls, values: list[uuid.UUID]) -> list[uuid.UUID]:
        if len(set(values)) != len(values):
            raise ValueError("selected IDs must be unique")
        return values


class MeasurementComparisonAssertion(BaseModel):
    kind: Literal["measurement_comparison"]
    left_measurement_id: uuid.UUID
    right_measurement_id: uuid.UUID
    metric: Literal["x_min", "x_max", "y_min", "y_max", "y_mean"]
    relation: Literal["greater_than", "less_than", "approximately_equal"]
    rationale: str = Field(min_length=1, max_length=2000)


class ExperimentDifferenceAssertion(BaseModel):
    kind: Literal["experiment_difference"]
    left_experiment_id: uuid.UUID
    left_revision_number: int = Field(ge=1)
    right_experiment_id: uuid.UUID
    right_revision_number: int = Field(ge=1)
    path: str = Field(min_length=1, max_length=500)
    relation: Literal["added", "removed", "changed", "equal"]
    rationale: str = Field(min_length=1, max_length=2000)


class RevisionObservationAssertion(BaseModel):
    kind: Literal["revision_observation"]
    experiment_id: uuid.UUID
    revision_number: int = Field(ge=1)
    path: str = Field(min_length=1, max_length=500)
    operator: Literal["equals", "present", "absent"]
    expected_value: Any | None = None
    rationale: str = Field(min_length=1, max_length=2000)


StructuredSupportAssertion = Annotated[
    MeasurementComparisonAssertion | ExperimentDifferenceAssertion | RevisionObservationAssertion,
    Field(discriminator="kind"),
]


class ComparisonAssertion(BaseModel):
    left_measurement_id: uuid.UUID
    right_measurement_id: uuid.UUID
    metric: Literal["x_min", "x_max", "y_min", "y_max", "y_mean"]
    relation: Literal["greater_than", "less_than", "approximately_equal"]
    rationale: str = Field(min_length=1, max_length=2000)


class FindingLimitation(BaseModel):
    code: str = Field(min_length=1, max_length=120)
    description: str = Field(min_length=1, max_length=2000)


class SuggestedChangeOperation(BaseModel):
    op: Literal["set", "remove"]
    path: str = Field(min_length=1, max_length=500)
    value: Any | None = None
    rationale: str = Field(min_length=1, max_length=2000)


class SuggestedNextExperiment(BaseModel):
    title: str = Field(min_length=1, max_length=240)
    objective: str = Field(min_length=1, max_length=10000)
    base_experiment_id: uuid.UUID
    control_strategy: str = Field(min_length=1, max_length=2000)
    change_operations: list[SuggestedChangeOperation] = Field(max_length=25)
    addresses_missing_evidence_codes: list[str] = Field(default_factory=list, max_length=25)


class CausalTarget(BaseModel):
    factor_paths: list[str] = Field(min_length=1, max_length=25)
    baseline_experiment_id: uuid.UUID
    outcome_experiment_id: uuid.UUID
    outcome_measurement_ids: list[uuid.UUID] = Field(default_factory=list, max_length=10)


class ProposedGate(BaseModel):
    status: EvidenceGateStatus
    rationale: str = Field(min_length=1, max_length=2000)


class FindingCandidateV1(BaseModel):
    model_config = ConfigDict(extra="forbid")

    claim: str = Field(min_length=1, max_length=4000)
    claim_type: FindingClaimType
    confidence_label: Literal["low", "medium", "high"]
    confidence_rationale: str = Field(min_length=1, max_length=2000)
    applicability_scope: str = Field(min_length=1, max_length=2000)
    evidence_links: list[dict[str, Any]] = Field(default_factory=list, max_length=25)
    structured_support_assertions: list[StructuredSupportAssertion] = Field(
        default_factory=list, max_length=25
    )
    limitations: list[FindingLimitation] = Field(default_factory=list, max_length=25)
    risks: list[FindingLimitation] = Field(default_factory=list, max_length=25)
    missing_evidence: list[FindingLimitation] = Field(default_factory=list, max_length=25)
    comparison_assertions: list[ComparisonAssertion] = Field(default_factory=list, max_length=25)
    causal_target: CausalTarget | None = None
    suggested_next_experiment: SuggestedNextExperiment | None = None
    proposed_gate: ProposedGate

    @model_validator(mode="after")
    def causal_target_shape(self) -> FindingCandidateV1:
        if self.claim_type == "causal_claim" and self.causal_target is None:
            raise ValueError("causal_claim requires causal_target")
        if self.claim_type != "causal_claim" and self.causal_target is not None:
            raise ValueError("causal_target is only valid for causal_claim")
        return self


class ScientificAnalysisResponseV1(BaseModel):
    model_config = ConfigDict(extra="forbid")

    analysis_summary: str = Field(min_length=1, max_length=4000)
    findings: list[FindingCandidateV1] = Field(min_length=1, max_length=5)


class ModelProfileOut(BaseModel):
    key: str
    provider: str
    model: str
    label: str
    structured_output_mode: StructuredOutputMode
    available: bool
    capability_reason: str | None = None


class PromptVersionOut(BaseModel):
    key: str
    version: int
    sha256: str


class EvidenceLinkOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    evidence_record_id: uuid.UUID
    role: EvidenceLinkRole
    rationale: str
    evidence_snapshot_json: dict[str, Any]
    created_at: datetime


class ReviewDecisionOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    finding_id: uuid.UUID
    sequence_number: int
    decision: ReviewDecisionType
    reviewer_name: str
    reason_code: str | None
    comment: str | None
    supersedes_review_id: uuid.UUID | None
    created_at: datetime


class ReviewDecisionCreate(BaseModel):
    decision: ReviewDecisionType
    reviewer_name: str = Field(min_length=1, max_length=240)
    reason_code: str | None = Field(default=None, max_length=64)
    comment: str | None = Field(default=None, max_length=10000)
    supersedes_review_id: uuid.UUID | None = None

    _reviewer = field_validator("reviewer_name")(non_blank)

    @model_validator(mode="after")
    def decision_requirements(self) -> ReviewDecisionCreate:
        if self.decision == "reject" and (not self.reason_code or not self.comment):
            raise ValueError("reject requires reason_code and comment")
        if self.decision == "needs_evidence" and not self.comment:
            raise ValueError("needs_evidence requires comment")
        return self


class FindingOut(BaseModel):
    id: uuid.UUID
    project_id: uuid.UUID
    analysis_run_id: uuid.UUID
    ordinal: int
    claim: str
    claim_type: FindingClaimType
    confidence_label: Literal["low", "medium", "high"]
    confidence_rationale: str
    applicability_scope: str
    limitations_json: list[dict[str, Any]]
    risks_json: list[dict[str, Any]]
    missing_evidence_json: list[dict[str, Any]]
    comparison_assertions_json: list[dict[str, Any]]
    structured_support_json: list[dict[str, Any]]
    causal_target_json: dict[str, Any] | None
    suggested_next_experiment_json: dict[str, Any] | None
    model_proposed_gate_status: EvidenceGateStatus
    model_proposed_gate_rationale: str
    evidence_gate_status: EvidenceGateStatus
    evidence_gate_rationale_json: dict[str, Any]
    gate_policy_version: int
    review_status: ReviewStatus
    evidence_links: list[EvidenceLinkOut] = Field(default_factory=list)
    reviews: list[ReviewDecisionOut] = Field(default_factory=list)
    created_at: datetime


class AnalysisContextOut(BaseModel):
    id: uuid.UUID
    analysis_run_id: uuid.UUID
    schema_version: int
    snapshot_json: dict[str, Any]
    snapshot_sha256: str
    size_bytes: int
    created_at: datetime


class AnalysisRunOut(BaseModel):
    id: uuid.UUID
    project_id: uuid.UUID
    purpose: AnalysisPurpose
    status: AnalysisRunStatus
    provider_key: Literal["litellm", "fixture"]
    model_profile_key: str
    structured_output_mode: StructuredOutputMode
    requested_model: str
    resolved_model: str | None
    provider_response_id: str | None
    provider_model_version: str | None
    prompt_key: str
    prompt_version: int
    prompt_sha256: str
    output_schema_version: int
    workflow_version: int
    generation_parameters_json: dict[str, Any]
    model_metadata_json: dict[str, Any]
    validated_output_json: dict[str, Any] | None
    error_code: str | None
    error_message: str | None
    langfuse_trace_id: str | None
    langfuse_sync_status: str
    started_at: datetime | None
    completed_at: datetime | None
    created_at: datetime
    context_snapshot: AnalysisContextOut | None = None
    findings: list[FindingOut] = Field(default_factory=list)


ImportCommitMapping.model_rebuild()
