from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, String, Text, UniqueConstraint, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.types import JSON, Uuid

from app.db import Base

JsonColumn = JSON().with_variant(JSONB, "postgresql")


class Project(Base):
    __tablename__ = "projects"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    code: Mapped[str] = mapped_column(String(32), unique=True, index=True)
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

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    key: Mapped[str] = mapped_column(String(120), unique=True, index=True)
    name: Mapped[str] = mapped_column(String(240))
    version: Mapped[int] = mapped_column(Integer, default=1)
    json_schema: Mapped[dict[str, Any]] = mapped_column(JsonColumn)
    ui_schema: Mapped[dict[str, Any] | None] = mapped_column(JsonColumn, nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    experiments: Mapped[list[Experiment]] = relationship(back_populates="template")


class Experiment(Base):
    __tablename__ = "experiments"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    code: Mapped[str] = mapped_column(String(32), unique=True, index=True)
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
