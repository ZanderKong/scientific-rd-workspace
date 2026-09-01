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
