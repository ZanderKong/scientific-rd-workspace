from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    DateTime,
    Float,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
    event,
    func,
    inspect,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.types import JSON, Uuid

from app.db import Base

JsonColumn = JSON().with_variant(JSONB, "postgresql")


class Project(Base):
    __tablename__ = "projects"
    __table_args__ = (UniqueConstraint("code"),)

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    code: Mapped[str] = mapped_column(String(32), index=True)
    title: Mapped[str] = mapped_column(String(240))
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    status: Mapped[str] = mapped_column(String(32), default="active")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    experiments: Mapped[list[Experiment]] = relationship(
        back_populates="project", cascade="all, delete-orphan"
    )


class ExperimentTemplate(Base):
    __tablename__ = "experiment_templates"
    __table_args__ = (
        UniqueConstraint("key", "version", name="uq_experiment_templates_key_version"),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    key: Mapped[str] = mapped_column(String(120), index=True)
    name: Mapped[str] = mapped_column(String(240))
    version: Mapped[int] = mapped_column(Integer, default=1)
    json_schema: Mapped[dict[str, Any]] = mapped_column(JsonColumn)
    ui_schema: Mapped[dict[str, Any] | None] = mapped_column(JsonColumn, nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    experiments: Mapped[list[Experiment]] = relationship(back_populates="template")


@event.listens_for(ExperimentTemplate, "before_update")
def prevent_template_version_mutation(
    _mapper: Any, _connection: Any, target: ExperimentTemplate
) -> None:
    state = inspect(target)
    immutable_fields = ("key", "name", "version", "json_schema", "ui_schema")
    if any(state.attrs[field].history.has_changes() for field in immutable_fields):
        raise ValueError("experiment template versions are immutable; create a new version row")


class Experiment(Base):
    __tablename__ = "experiments"
    __table_args__ = (UniqueConstraint("code"),)

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    code: Mapped[str] = mapped_column(String(32), index=True)
    project_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("projects.id"), index=True)
    template_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("experiment_templates.id"))
    template_version: Mapped[int] = mapped_column(Integer)
    parent_experiment_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("experiments.id"), nullable=True, index=True
    )
    title: Mapped[str] = mapped_column(String(240))
    status: Mapped[str] = mapped_column(String(32), default="draft")
    objective: Mapped[str | None] = mapped_column(Text, nullable=True)
    structured_data: Mapped[dict[str, Any]] = mapped_column(JsonColumn, default=dict)
    note_document: Mapped[list[dict[str, Any]]] = mapped_column(JsonColumn, default=list)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    project: Mapped[Project] = relationship(back_populates="experiments")
    template: Mapped[ExperimentTemplate] = relationship(back_populates="experiments")
    parent_experiment: Mapped[Experiment | None] = relationship(
        remote_side=[id], back_populates="children"
    )
    children: Mapped[list[Experiment]] = relationship(back_populates="parent_experiment")
    attachments: Mapped[list[Attachment]] = relationship(
        back_populates="experiment", cascade="all, delete-orphan"
    )
    revisions: Mapped[list[ExperimentRevision]] = relationship(
        back_populates="experiment", cascade="all, delete-orphan"
    )
    measurements: Mapped[list[Measurement]] = relationship(
        back_populates="experiment", cascade="all, delete-orphan"
    )
    measurement_imports: Mapped[list[MeasurementImport]] = relationship(
        back_populates="experiment", cascade="all, delete-orphan"
    )
    literature_links: Mapped[list[ExperimentLiteratureLink]] = relationship(
        back_populates="experiment", cascade="all, delete-orphan"
    )
    evidence_records: Mapped[list[EvidenceRecord]] = relationship(
        foreign_keys="EvidenceRecord.context_experiment_id",
        back_populates="context_experiment",
    )


class Attachment(Base):
    __tablename__ = "attachments"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    experiment_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("experiments.id"), index=True)
    original_filename: Mapped[str] = mapped_column(String(255))
    storage_key: Mapped[str] = mapped_column(String(512), unique=True)
    content_type: Mapped[str | None] = mapped_column(String(160), nullable=True)
    size_bytes: Mapped[int] = mapped_column(Integer)
    sha256: Mapped[str] = mapped_column(String(64))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    experiment: Mapped[Experiment] = relationship(back_populates="attachments")
    measurement_imports: Mapped[list[MeasurementImport]] = relationship(
        back_populates="source_attachment"
    )


class ExperimentRevision(Base):
    __tablename__ = "experiment_revisions"
    __table_args__ = (UniqueConstraint("experiment_id", "revision_number"),)

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    experiment_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("experiments.id"), index=True)
    revision_number: Mapped[int] = mapped_column(Integer)
    snapshot_json: Mapped[dict[str, Any]] = mapped_column(JsonColumn)
    change_note: Mapped[str | None] = mapped_column(String(500), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    experiment: Mapped[Experiment] = relationship(back_populates="revisions")


class MeasurementImport(Base):
    __tablename__ = "measurement_imports"
    __table_args__ = (
        CheckConstraint(
            "status in ('preview_ready', 'completed', 'failed')",
            name="ck_measurement_imports_status",
        ),
        CheckConstraint("source_format in ('csv', 'xlsx')", name="ck_measurement_imports_format"),
        CheckConstraint("parser_version > 0", name="ck_measurement_imports_parser_version"),
        CheckConstraint(
            "row_count is null or row_count >= 0", name="ck_measurement_imports_row_count"
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    experiment_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("experiments.id"), index=True)
    source_attachment_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("attachments.id"), index=True
    )
    status: Mapped[str] = mapped_column(String(32), default="preview_ready")
    source_format: Mapped[str] = mapped_column(String(16))
    parser_key: Mapped[str] = mapped_column(String(120), default="tabular-xy")
    parser_version: Mapped[int] = mapped_column(Integer, default=1)
    sheet_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    source_sha256: Mapped[str] = mapped_column(String(64))
    header_json: Mapped[list[str]] = mapped_column(JsonColumn, default=list)
    source_metadata_json: Mapped[dict[str, Any]] = mapped_column(JsonColumn, default=dict)
    mapping_json: Mapped[dict[str, Any] | None] = mapped_column(JsonColumn, nullable=True)
    warnings_json: Mapped[list[dict[str, Any]]] = mapped_column(JsonColumn, default=list)
    errors_json: Mapped[list[dict[str, Any]]] = mapped_column(JsonColumn, default=list)
    row_count: Mapped[int | None] = mapped_column(Integer, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    experiment: Mapped[Experiment] = relationship(back_populates="measurement_imports")
    source_attachment: Mapped[Attachment] = relationship(back_populates="measurement_imports")
    measurement: Mapped[Measurement | None] = relationship(
        back_populates="import_record", uselist=False
    )


class Measurement(Base):
    __tablename__ = "measurements"
    __table_args__ = (
        CheckConstraint(
            "measurement_type in ('spectral_response', 'time_series', 'other_xy')",
            name="ck_measurements_type",
        ),
        CheckConstraint("schema_version > 0", name="ck_measurements_schema_version"),
        CheckConstraint(
            "default_chart_type in ('line', 'scatter')", name="ck_measurements_chart_type"
        ),
        CheckConstraint("row_count >= 0", name="ck_measurements_row_count"),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    experiment_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("experiments.id"), index=True)
    import_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("measurement_imports.id"), unique=True)
    name: Mapped[str] = mapped_column(String(240))
    measurement_type: Mapped[str] = mapped_column(String(64))
    schema_key: Mapped[str] = mapped_column(String(120), default="xy-series")
    schema_version: Mapped[int] = mapped_column(Integer, default=1)
    default_chart_type: Mapped[str] = mapped_column(String(16), default="line")
    x_label: Mapped[str] = mapped_column(String(120))
    x_unit: Mapped[str] = mapped_column(String(64))
    y_label: Mapped[str] = mapped_column(String(120))
    y_unit: Mapped[str] = mapped_column(String(64))
    row_count: Mapped[int] = mapped_column(Integer)
    summary_json: Mapped[dict[str, Any]] = mapped_column(JsonColumn, default=dict)
    points_sha256: Mapped[str] = mapped_column(String(64))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    experiment: Mapped[Experiment] = relationship(back_populates="measurements")
    import_record: Mapped[MeasurementImport] = relationship(back_populates="measurement")
    points: Mapped[list[MeasurementPoint]] = relationship(
        back_populates="measurement",
        cascade="all, delete-orphan",
        order_by="MeasurementPoint.ordinal",
    )


class MeasurementPoint(Base):
    __tablename__ = "measurement_points"
    __table_args__ = (
        CheckConstraint("ordinal >= 0", name="ck_measurement_points_ordinal"),
        CheckConstraint("source_row_number > 0", name="ck_measurement_points_source_row"),
        UniqueConstraint(
            "measurement_id", "source_row_number", name="uq_measurement_points_source_row"
        ),
        Index("ix_measurement_points_measurement_id", "measurement_id"),
    )

    measurement_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("measurements.id"), primary_key=True
    )
    ordinal: Mapped[int] = mapped_column(Integer, primary_key=True)
    source_row_number: Mapped[int] = mapped_column(Integer)
    x_value: Mapped[float] = mapped_column(Float)
    y_value: Mapped[float] = mapped_column(Float)

    measurement: Mapped[Measurement] = relationship(back_populates="points")


class LiteratureRecord(Base):
    __tablename__ = "literature_records"
    __table_args__ = (
        Index(
            "uq_literature_provider_external",
            "project_id",
            "provider",
            "external_id",
            unique=True,
            postgresql_where=text("provider is not null and external_id is not null"),
            sqlite_where=text("provider is not null and external_id is not null"),
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    project_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("projects.id"), index=True)
    item_type: Mapped[str] = mapped_column(String(64), default="journal_article")
    title: Mapped[str] = mapped_column(String(500))
    authors_json: Mapped[list[dict[str, Any]]] = mapped_column(JsonColumn, default=list)
    publication_year: Mapped[int | None] = mapped_column(Integer, nullable=True)
    container_title: Mapped[str | None] = mapped_column(String(500), nullable=True)
    doi: Mapped[str | None] = mapped_column(String(255), nullable=True)
    url: Mapped[str | None] = mapped_column(String(2000), nullable=True)
    abstract: Mapped[str | None] = mapped_column(Text, nullable=True)
    provider: Mapped[str | None] = mapped_column(String(64), nullable=True)
    external_id: Mapped[str | None] = mapped_column(String(255), nullable=True)
    provider_version: Mapped[str | None] = mapped_column(String(64), nullable=True)
    raw_provider_json: Mapped[dict[str, Any] | None] = mapped_column(JsonColumn, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    project: Mapped[Project] = relationship()
    links: Mapped[list[ExperimentLiteratureLink]] = relationship(
        back_populates="literature", cascade="all, delete-orphan"
    )


class ExperimentLiteratureLink(Base):
    __tablename__ = "experiment_literature_links"
    __table_args__ = (
        UniqueConstraint(
            "experiment_id", "literature_id", name="uq_experiment_literature_links_pair"
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    experiment_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("experiments.id"), index=True)
    literature_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("literature_records.id"), index=True
    )
    relationship_type: Mapped[str] = mapped_column(String(32), default="background")
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    experiment: Mapped[Experiment] = relationship(back_populates="literature_links")
    literature: Mapped[LiteratureRecord] = relationship(back_populates="links")


class EvidenceRecord(Base):
    __tablename__ = "evidence_records"
    __table_args__ = (
        CheckConstraint(
            "source_type in ('literature', 'measurement', 'experiment_revision')",
            name="ck_evidence_source_type",
        ),
        CheckConstraint(
            "stance in ('supports', 'contradicts', 'context')", name="ck_evidence_stance"
        ),
        CheckConstraint("status in ('active', 'withdrawn')", name="ck_evidence_status"),
        CheckConstraint(
            "(CASE WHEN literature_id IS NOT NULL THEN 1 ELSE 0 END + "
            "CASE WHEN measurement_id IS NOT NULL THEN 1 ELSE 0 END + "
            "CASE WHEN experiment_revision_id IS NOT NULL THEN 1 ELSE 0 END) = 1",
            name="ck_evidence_exactly_one_source",
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    project_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("projects.id"), index=True)
    context_experiment_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("experiments.id"), index=True, nullable=True
    )
    claim_text: Mapped[str] = mapped_column(Text)
    stance: Mapped[str] = mapped_column(String(32))
    source_type: Mapped[str] = mapped_column(String(32))
    literature_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("literature_records.id"), nullable=True
    )
    measurement_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("measurements.id"), nullable=True
    )
    experiment_revision_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("experiment_revisions.id"), nullable=True
    )
    locator: Mapped[str | None] = mapped_column(String(500), nullable=True)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    source_snapshot_json: Mapped[dict[str, Any]] = mapped_column(JsonColumn, default=dict)
    status: Mapped[str] = mapped_column(String(16), default="active")
    withdrawal_reason: Mapped[str | None] = mapped_column(String(1000), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    withdrawn_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    project: Mapped[Project] = relationship()
    context_experiment: Mapped[Experiment | None] = relationship(
        foreign_keys=[context_experiment_id], back_populates="evidence_records"
    )
    literature: Mapped[LiteratureRecord | None] = relationship(foreign_keys=[literature_id])
    measurement: Mapped[Measurement | None] = relationship(foreign_keys=[measurement_id])
    experiment_revision: Mapped[ExperimentRevision | None] = relationship(
        foreign_keys=[experiment_revision_id]
    )


class ScientificAnalysisRun(Base):
    __tablename__ = "scientific_analysis_runs"
    __table_args__ = (
        CheckConstraint(
            "purpose in ('interactive', 'evaluation_replay')",
            name="ck_scientific_analysis_runs_purpose",
        ),
        CheckConstraint(
            "status in ('building_context', 'running', 'completed', 'failed', 'interrupted')",
            name="ck_scientific_analysis_runs_status",
        ),
        CheckConstraint(
            "provider_key in ('litellm', 'fixture')",
            name="ck_scientific_analysis_runs_provider",
        ),
        CheckConstraint(
            "structured_output_mode in ('native_schema', 'json_object')",
            name="ck_scientific_analysis_runs_output_mode",
        ),
        CheckConstraint("prompt_version > 0", name="ck_scientific_analysis_runs_prompt_version"),
        CheckConstraint(
            "output_schema_version > 0", name="ck_scientific_analysis_runs_schema_version"
        ),
        CheckConstraint(
            "workflow_version > 0", name="ck_scientific_analysis_runs_workflow_version"
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    project_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("projects.id"), index=True)
    purpose: Mapped[str] = mapped_column(String(32), default="interactive")
    status: Mapped[str] = mapped_column(String(32), default="building_context")
    provider_key: Mapped[str] = mapped_column(String(32), default="fixture")
    model_profile_key: Mapped[str] = mapped_column(String(120))
    structured_output_mode: Mapped[str] = mapped_column(String(32), default="native_schema")
    requested_model: Mapped[str] = mapped_column(String(255))
    resolved_model: Mapped[str | None] = mapped_column(String(255), nullable=True)
    provider_response_id: Mapped[str | None] = mapped_column(String(255), nullable=True)
    provider_model_version: Mapped[str | None] = mapped_column(String(255), nullable=True)
    prompt_key: Mapped[str] = mapped_column(String(120))
    prompt_version: Mapped[int] = mapped_column(Integer, default=1)
    prompt_sha256: Mapped[str] = mapped_column(String(64))
    prompt_snapshot_json: Mapped[dict[str, Any]] = mapped_column(JsonColumn, default=dict)
    output_schema_version: Mapped[int] = mapped_column(Integer, default=1)
    workflow_version: Mapped[int] = mapped_column(Integer, default=1)
    generation_parameters_json: Mapped[dict[str, Any]] = mapped_column(JsonColumn, default=dict)
    model_metadata_json: Mapped[dict[str, Any]] = mapped_column(JsonColumn, default=dict)
    raw_output_text: Mapped[str | None] = mapped_column(Text, nullable=True)
    validated_output_json: Mapped[dict[str, Any] | None] = mapped_column(JsonColumn, nullable=True)
    error_code: Mapped[str | None] = mapped_column(String(120), nullable=True)
    error_message: Mapped[str | None] = mapped_column(String(2000), nullable=True)
    langfuse_trace_id: Mapped[str | None] = mapped_column(String(255), nullable=True)
    langfuse_sync_status: Mapped[str] = mapped_column(String(32), default="disabled")
    langfuse_error: Mapped[str | None] = mapped_column(String(2000), nullable=True)
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    project: Mapped[Project] = relationship()
    context_snapshot: Mapped[AnalysisContextSnapshot | None] = relationship(
        back_populates="analysis_run", uselist=False
    )
    findings: Mapped[list[Finding]] = relationship(back_populates="analysis_run")


class AnalysisContextSnapshot(Base):
    __tablename__ = "analysis_context_snapshots"
    __table_args__ = (UniqueConstraint("analysis_run_id"),)

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    analysis_run_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("scientific_analysis_runs.id"), index=True
    )
    schema_version: Mapped[int] = mapped_column(Integer, default=1)
    snapshot_json: Mapped[dict[str, Any]] = mapped_column(JsonColumn, default=dict)
    snapshot_sha256: Mapped[str] = mapped_column(String(64))
    size_bytes: Mapped[int] = mapped_column(Integer)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    analysis_run: Mapped[ScientificAnalysisRun] = relationship(back_populates="context_snapshot")


class Finding(Base):
    __tablename__ = "findings"
    __table_args__ = (
        UniqueConstraint("analysis_run_id", "ordinal"),
        CheckConstraint(
            "claim_type in ("
            "'scientific_observation', 'hypothesis', 'comparative_finding', "
            "'causal_claim', 'recommendation')",
            name="ck_findings_claim_type",
        ),
        CheckConstraint(
            "confidence_label in ('low', 'medium', 'high')",
            name="ck_findings_confidence_label",
        ),
        CheckConstraint(
            "model_proposed_gate_status in ("
            "'supported', 'partially_supported', 'insufficient_evidence', 'contradicted')",
            name="ck_findings_model_gate_status",
        ),
        CheckConstraint(
            "evidence_gate_status in ("
            "'supported', 'partially_supported', 'insufficient_evidence', 'contradicted')",
            name="ck_findings_evidence_gate_status",
        ),
        CheckConstraint(
            "review_status in ('pending_review', 'accepted', 'rejected', 'needs_evidence')",
            name="ck_findings_review_status",
        ),
        CheckConstraint("gate_policy_version > 0", name="ck_findings_gate_policy_version"),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    project_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("projects.id"), index=True)
    analysis_run_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("scientific_analysis_runs.id"), index=True
    )
    ordinal: Mapped[int] = mapped_column(Integer)
    claim: Mapped[str] = mapped_column(Text)
    claim_type: Mapped[str] = mapped_column(String(48))
    confidence_label: Mapped[str] = mapped_column(String(16))
    confidence_rationale: Mapped[str] = mapped_column(Text)
    applicability_scope: Mapped[str] = mapped_column(Text)
    limitations_json: Mapped[list[dict[str, Any]]] = mapped_column(JsonColumn, default=list)
    risks_json: Mapped[list[dict[str, Any]]] = mapped_column(JsonColumn, default=list)
    missing_evidence_json: Mapped[list[dict[str, Any]]] = mapped_column(JsonColumn, default=list)
    comparison_assertions_json: Mapped[list[dict[str, Any]]] = mapped_column(
        JsonColumn, default=list
    )
    structured_support_json: Mapped[list[dict[str, Any]]] = mapped_column(JsonColumn, default=list)
    causal_target_json: Mapped[dict[str, Any] | None] = mapped_column(JsonColumn, nullable=True)
    suggested_next_experiment_json: Mapped[dict[str, Any] | None] = mapped_column(
        JsonColumn, nullable=True
    )
    model_proposed_gate_status: Mapped[str] = mapped_column(String(32))
    model_proposed_gate_rationale: Mapped[str] = mapped_column(Text)
    evidence_gate_status: Mapped[str] = mapped_column(String(32))
    evidence_gate_rationale_json: Mapped[dict[str, Any]] = mapped_column(JsonColumn, default=dict)
    gate_policy_version: Mapped[int] = mapped_column(Integer, default=1)
    review_status: Mapped[str] = mapped_column(String(32), default="pending_review")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    project: Mapped[Project] = relationship()
    analysis_run: Mapped[ScientificAnalysisRun] = relationship(back_populates="findings")
    evidence_links: Mapped[list[FindingEvidenceLink]] = relationship(
        back_populates="finding", cascade="all, delete-orphan"
    )
    reviews: Mapped[list[ReviewDecision]] = relationship(
        back_populates="finding",
        cascade="all, delete-orphan",
        order_by="ReviewDecision.sequence_number",
    )


class FindingEvidenceLink(Base):
    __tablename__ = "finding_evidence_links"
    __table_args__ = (
        UniqueConstraint("finding_id", "evidence_record_id"),
        CheckConstraint(
            "role in ('supporting', 'contradicting', 'contextual')",
            name="ck_finding_evidence_links_role",
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    finding_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("findings.id"), index=True)
    evidence_record_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("evidence_records.id"), index=True
    )
    role: Mapped[str] = mapped_column(String(24))
    rationale: Mapped[str] = mapped_column(Text)
    evidence_snapshot_json: Mapped[dict[str, Any]] = mapped_column(JsonColumn, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    finding: Mapped[Finding] = relationship(back_populates="evidence_links")
    evidence_record: Mapped[EvidenceRecord] = relationship()


class ReviewDecision(Base):
    __tablename__ = "review_decisions"
    __table_args__ = (
        UniqueConstraint("finding_id", "sequence_number"),
        CheckConstraint(
            "decision in ('accept', 'reject', 'needs_evidence')",
            name="ck_review_decisions_decision",
        ),
        CheckConstraint("sequence_number > 0", name="ck_review_decisions_sequence"),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    finding_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("findings.id"), index=True)
    sequence_number: Mapped[int] = mapped_column(Integer)
    decision: Mapped[str] = mapped_column(String(24))
    reviewer_name: Mapped[str] = mapped_column(String(240))
    reason_code: Mapped[str | None] = mapped_column(String(64), nullable=True)
    comment: Mapped[str | None] = mapped_column(Text, nullable=True)
    supersedes_review_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("review_decisions.id"), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    finding: Mapped[Finding] = relationship(back_populates="reviews")
    supersedes: Mapped[ReviewDecision | None] = relationship(remote_side=[id])


class EvaluationCase(Base):
    __tablename__ = "evaluation_cases"
    __table_args__ = (
        CheckConstraint(
            "case_type in ('bad_case', 'reference_case')", name="ck_evaluation_cases_case_type"
        ),
        CheckConstraint("context_schema_version > 0", name="ck_evaluation_cases_context_version"),
        CheckConstraint(
            "langfuse_sync_status in ('disabled', 'pending', 'synced', 'failed')",
            name="ck_evaluation_cases_langfuse_status",
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    project_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("projects.id"), index=True)
    case_type: Mapped[str] = mapped_column(String(24), nullable=False)
    source_finding_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("findings.id"), index=True)
    source_review_decision_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("review_decisions.id"), unique=True
    )
    context_schema_version: Mapped[int] = mapped_column(Integer, default=1)
    context_snapshot_json: Mapped[dict[str, Any]] = mapped_column(JsonColumn, default=dict)
    model_output_snapshot_json: Mapped[dict[str, Any]] = mapped_column(JsonColumn, default=dict)
    finding_snapshot_json: Mapped[dict[str, Any]] = mapped_column(JsonColumn, default=dict)
    gate_snapshot_json: Mapped[dict[str, Any]] = mapped_column(JsonColumn, default=dict)
    review_snapshot_json: Mapped[dict[str, Any]] = mapped_column(JsonColumn, default=dict)
    expected_behavior_json: Mapped[dict[str, Any]] = mapped_column(JsonColumn, default=dict)
    case_tags_json: Mapped[list[str]] = mapped_column(JsonColumn, default=list)
    source_model_config_json: Mapped[dict[str, Any]] = mapped_column(JsonColumn, default=dict)
    source_prompt_snapshot_json: Mapped[dict[str, Any]] = mapped_column(JsonColumn, default=dict)
    case_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    langfuse_dataset_item_id: Mapped[str | None] = mapped_column(String(255), nullable=True)
    langfuse_sync_status: Mapped[str] = mapped_column(String(32), default="disabled")
    langfuse_error: Mapped[str | None] = mapped_column(String(2000), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    project: Mapped[Project] = relationship()
    source_finding: Mapped[Finding] = relationship()
    source_review_decision: Mapped[ReviewDecision] = relationship()
    results: Mapped[list[EvaluationResult]] = relationship(back_populates="evaluation_case")


class EvaluationRun(Base):
    __tablename__ = "evaluation_runs"
    __table_args__ = (
        CheckConstraint(
            "status in ('queued', 'running', 'completed', 'completed_with_errors', 'failed', "
            "'interrupted', 'cancel_requested', 'cancelled')",
            name="ck_evaluation_runs_status",
        ),
        CheckConstraint(
            "structured_output_mode in ('native_schema', 'json_object')",
            name="ck_evaluation_runs_output_mode",
        ),
        CheckConstraint("total_cases >= 0", name="ck_evaluation_runs_total_cases"),
        CheckConstraint("completed_cases >= 0", name="ck_evaluation_runs_completed_cases"),
        CheckConstraint("passed_cases >= 0", name="ck_evaluation_runs_passed_cases"),
        CheckConstraint("failed_cases >= 0", name="ck_evaluation_runs_failed_cases"),
        CheckConstraint("error_cases >= 0", name="ck_evaluation_runs_error_cases"),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    project_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("projects.id"), index=True)
    status: Mapped[str] = mapped_column(String(32), default="queued")
    dataset_version: Mapped[str] = mapped_column(String(64), nullable=False)
    model_profile_key: Mapped[str] = mapped_column(String(120))
    structured_output_mode: Mapped[str] = mapped_column(String(32))
    requested_model: Mapped[str] = mapped_column(String(255))
    prompt_key: Mapped[str] = mapped_column(String(120))
    prompt_version: Mapped[int] = mapped_column(Integer)
    prompt_sha256: Mapped[str] = mapped_column(String(64))
    prompt_snapshot_json: Mapped[dict[str, Any]] = mapped_column(JsonColumn, default=dict)
    workflow_version: Mapped[int] = mapped_column(Integer, default=1)
    output_schema_version: Mapped[int] = mapped_column(Integer, default=1)
    generation_parameters_json: Mapped[dict[str, Any]] = mapped_column(JsonColumn, default=dict)
    judge_enabled: Mapped[bool] = mapped_column(Boolean, default=False)
    judge_model_profile_key: Mapped[str | None] = mapped_column(String(120), nullable=True)
    judge_structured_output_mode: Mapped[str | None] = mapped_column(String(32), nullable=True)
    judge_prompt_version: Mapped[int | None] = mapped_column(Integer, nullable=True)
    baseline_run_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("evaluation_runs.id"), nullable=True
    )
    total_cases: Mapped[int] = mapped_column(Integer, default=0)
    completed_cases: Mapped[int] = mapped_column(Integer, default=0)
    passed_cases: Mapped[int] = mapped_column(Integer, default=0)
    failed_cases: Mapped[int] = mapped_column(Integer, default=0)
    error_cases: Mapped[int] = mapped_column(Integer, default=0)
    aggregate_scores_json: Mapped[dict[str, Any]] = mapped_column(JsonColumn, default=dict)
    regression_summary_json: Mapped[dict[str, Any]] = mapped_column(JsonColumn, default=dict)
    error_code: Mapped[str | None] = mapped_column(String(120), nullable=True)
    error_message: Mapped[str | None] = mapped_column(String(2000), nullable=True)
    langfuse_experiment_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    langfuse_sync_status: Mapped[str] = mapped_column(String(32), default="disabled")
    langfuse_error: Mapped[str | None] = mapped_column(String(2000), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    project: Mapped[Project] = relationship()
    baseline_run: Mapped[EvaluationRun | None] = relationship(remote_side=[id])
    results: Mapped[list[EvaluationResult]] = relationship(
        back_populates="evaluation_run",
        cascade="all, delete-orphan",
        order_by="EvaluationResult.ordinal",
    )


class EvaluationResult(Base):
    __tablename__ = "evaluation_results"
    __table_args__ = (
        UniqueConstraint("evaluation_run_id", "evaluation_case_id"),
        UniqueConstraint("evaluation_run_id", "ordinal"),
        CheckConstraint(
            "status in ('pending', 'running', 'passed', 'failed', 'error', 'cancelled')",
            name="ck_evaluation_results_status",
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    evaluation_run_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("evaluation_runs.id"), index=True
    )
    evaluation_case_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("evaluation_cases.id"), index=True
    )
    ordinal: Mapped[int] = mapped_column(Integer)
    status: Mapped[str] = mapped_column(String(24), default="pending")
    replay_analysis_run_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("scientific_analysis_runs.id"), nullable=True
    )
    deterministic_scores_json: Mapped[dict[str, Any]] = mapped_column(JsonColumn, default=dict)
    judge_scores_json: Mapped[dict[str, Any] | None] = mapped_column(JsonColumn, nullable=True)
    judge_metadata_json: Mapped[dict[str, Any] | None] = mapped_column(JsonColumn, nullable=True)
    failure_tags_json: Mapped[list[str]] = mapped_column(JsonColumn, default=list)
    error_code: Mapped[str | None] = mapped_column(String(120), nullable=True)
    error_message: Mapped[str | None] = mapped_column(String(2000), nullable=True)
    langfuse_trace_id: Mapped[str | None] = mapped_column(String(255), nullable=True)
    langfuse_sync_status: Mapped[str] = mapped_column(String(32), default="disabled")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    evaluation_run: Mapped[EvaluationRun] = relationship(back_populates="results")
    evaluation_case: Mapped[EvaluationCase] = relationship(back_populates="results")
    replay_analysis_run: Mapped[ScientificAnalysisRun | None] = relationship()


class ExperimentProvenanceLink(Base):
    __tablename__ = "experiment_provenance_links"
    __table_args__ = (
        UniqueConstraint("experiment_id"),
        CheckConstraint(
            "relation_type = 'suggested_from_finding'", name="ck_experiment_provenance_relation"
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    experiment_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("experiments.id"), unique=True)
    finding_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("findings.id"), index=True)
    analysis_run_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("scientific_analysis_runs.id"), index=True
    )
    enabling_review_decision_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("review_decisions.id"), index=True
    )
    relation_type: Mapped[str] = mapped_column(String(64), default="suggested_from_finding")
    suggestion_snapshot_json: Mapped[dict[str, Any]] = mapped_column(JsonColumn, default=dict)
    submitted_values_snapshot_json: Mapped[dict[str, Any]] = mapped_column(JsonColumn, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    experiment: Mapped[Experiment] = relationship()
    finding: Mapped[Finding] = relationship()
    analysis_run: Mapped[ScientificAnalysisRun] = relationship()
    enabling_review_decision: Mapped[ReviewDecision] = relationship()


def _reject_update(
    _mapper: Any, _connection: Any, target: Any, allowed: tuple[str, ...] = ()
) -> None:
    state = inspect(target)
    changed = [attribute.key for attribute in state.attrs if attribute.history.has_changes()]
    if any(key not in allowed for key in changed):
        raise ValueError(f"{target.__class__.__name__} is immutable")


def _reject_delete(_mapper: Any, _connection: Any, target: Any) -> None:
    raise ValueError(f"{target.__class__.__name__} is immutable")


RUN_PROVENANCE_FIELDS = {
    "project_id",
    "purpose",
    "provider_key",
    "model_profile_key",
    "structured_output_mode",
    "requested_model",
    "prompt_key",
    "prompt_version",
    "prompt_sha256",
    "prompt_snapshot_json",
    "output_schema_version",
    "workflow_version",
    "generation_parameters_json",
}


def _reject_run_provenance_update(
    _mapper: Any, _connection: Any, target: ScientificAnalysisRun
) -> None:
    if target.status == "building_context":
        return
    state = inspect(target)
    changed = {attribute.key for attribute in state.attrs if attribute.history.has_changes()}
    if changed & RUN_PROVENANCE_FIELDS:
        raise ValueError("ScientificAnalysisRun provenance is immutable after context building")


event.listen(ScientificAnalysisRun, "before_update", _reject_run_provenance_update)
event.listen(ScientificAnalysisRun, "before_delete", _reject_delete)
event.listen(AnalysisContextSnapshot, "before_update", _reject_update)
event.listen(AnalysisContextSnapshot, "before_delete", _reject_delete)
event.listen(Finding, "before_update", lambda m, c, t: _reject_update(m, c, t, ("review_status",)))
event.listen(Finding, "before_delete", _reject_delete)
event.listen(FindingEvidenceLink, "before_update", _reject_update)
event.listen(FindingEvidenceLink, "before_delete", _reject_delete)
event.listen(ReviewDecision, "before_update", _reject_update)
event.listen(ReviewDecision, "before_delete", _reject_delete)
event.listen(EvaluationCase, "before_update", _reject_update)
event.listen(EvaluationCase, "before_delete", _reject_delete)

EVALUATION_RUN_PROVENANCE_FIELDS = {
    "project_id",
    "dataset_version",
    "model_profile_key",
    "structured_output_mode",
    "requested_model",
    "prompt_key",
    "prompt_version",
    "prompt_sha256",
    "prompt_snapshot_json",
    "workflow_version",
    "output_schema_version",
    "generation_parameters_json",
    "judge_enabled",
    "judge_model_profile_key",
    "judge_structured_output_mode",
    "judge_prompt_version",
    "baseline_run_id",
}


@event.listens_for(EvaluationRun, "before_update")
def prevent_evaluation_run_provenance_mutation(
    _mapper: Any, _connection: Any, target: EvaluationRun
) -> None:
    state = inspect(target)
    changed = {attribute.key for attribute in state.attrs if attribute.history.has_changes()}
    if changed & EVALUATION_RUN_PROVENANCE_FIELDS:
        raise ValueError("EvaluationRun provenance is immutable")


event.listen(EvaluationRun, "before_delete", _reject_delete)


@event.listens_for(EvaluationResult, "before_update")
def prevent_completed_result_mutation(
    _mapper: Any, _connection: Any, target: EvaluationResult
) -> None:
    state = inspect(target)
    previous_status = state.attrs.status.history.deleted
    was_terminal = bool(
        previous_status and previous_status[0] in {"passed", "failed", "error", "cancelled"}
    )
    if was_terminal:
        changed = {attribute.key for attribute in state.attrs if attribute.history.has_changes()}
        if changed - {"langfuse_trace_id", "langfuse_sync_status"}:
            raise ValueError("completed EvaluationResult is immutable")
        return
    _reject_update(
        _mapper,
        _connection,
        target,
        (
            "status",
            "deterministic_scores_json",
            "judge_scores_json",
            "judge_metadata_json",
            "failure_tags_json",
            "error_code",
            "error_message",
            "replay_analysis_run_id",
            "langfuse_trace_id",
            "langfuse_sync_status",
            "completed_at",
        ),
    )


event.listen(EvaluationResult, "before_delete", _reject_delete)
event.listen(ExperimentProvenanceLink, "before_update", _reject_update)
event.listen(ExperimentProvenanceLink, "before_delete", _reject_delete)
