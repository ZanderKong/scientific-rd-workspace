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
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.types import JSON, Uuid

from app.db import Base

JsonColumn = JSON().with_variant(JSONB, "postgresql")

OBJECT_KINDS = (
    "material",
    "sample",
    "equipment",
    "process",
    "data",
    "experiment",
    "project",
)
RELATION_TYPES = ("contains", "uses", "produces", "precedes", "related_to")


class ObjectType(Base):
    __tablename__ = "object_types"
    __table_args__ = (UniqueConstraint("key", name="uq_object_types_key"),)

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    key: Mapped[str] = mapped_column(String(120), index=True)
    kind: Mapped[str] = mapped_column(String(32), index=True)
    label_zh: Mapped[str] = mapped_column(String(120))
    label_en: Mapped[str] = mapped_column(String(120))
    description_zh: Mapped[str | None] = mapped_column(Text, nullable=True)
    description_en: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    versions: Mapped[list[ObjectTypeVersion]] = relationship(
        back_populates="object_type",
        cascade="all, delete-orphan",
        order_by="ObjectTypeVersion.version",
    )


class ObjectTypeVersion(Base):
    __tablename__ = "object_type_versions"
    __table_args__ = (
        UniqueConstraint("object_type_id", "version", name="uq_object_type_versions"),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    object_type_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("object_types.id"), index=True)
    version: Mapped[int] = mapped_column(Integer)
    json_schema: Mapped[dict[str, Any]] = mapped_column(JsonColumn)
    ui_schema: Mapped[dict[str, Any] | None] = mapped_column(JsonColumn, nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    object_type: Mapped[ObjectType] = relationship(back_populates="versions")
    objects: Mapped[list[ResearchObject]] = relationship(back_populates="type_version")


@event.listens_for(ObjectTypeVersion, "before_update")
def prevent_type_version_mutation(
    _mapper: Any, _connection: Any, target: ObjectTypeVersion
) -> None:
    state = inspect(target)
    immutable_fields = ("object_type_id", "version", "json_schema", "ui_schema")
    if any(state.attrs[field].history.has_changes() for field in immutable_fields):
        raise ValueError("object type versions are immutable; create a new version")


class ResearchObject(Base):
    __tablename__ = "research_objects"
    __table_args__ = (
        CheckConstraint(
            "kind in ('material','sample','equipment','process','data','experiment','project')",
            name="ck_research_objects_kind",
        ),
        Index("ix_research_objects_project_kind", "project_scope_id", "kind"),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    code: Mapped[str] = mapped_column(String(32), unique=True, index=True)
    kind: Mapped[str] = mapped_column(String(32), index=True)
    title: Mapped[str] = mapped_column(String(240))
    status: Mapped[str] = mapped_column(String(32), default="active")
    project_scope_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("research_objects.id"), nullable=True, index=True
    )
    type_version_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("object_type_versions.id"), index=True
    )
    properties_jsonb: Mapped[dict[str, Any]] = mapped_column(JsonColumn, default=dict)
    content_document: Mapped[list[dict[str, Any]]] = mapped_column(JsonColumn, default=list)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    project_scope: Mapped[ResearchObject | None] = relationship(
        remote_side=[id], back_populates="scoped_objects"
    )
    scoped_objects: Mapped[list[ResearchObject]] = relationship(back_populates="project_scope")
    type_version: Mapped[ObjectTypeVersion] = relationship(back_populates="objects")
    outgoing_relations: Mapped[list[ObjectRelation]] = relationship(
        foreign_keys="ObjectRelation.source_object_id",
        back_populates="source_object",
        cascade="all, delete-orphan",
    )
    incoming_relations: Mapped[list[ObjectRelation]] = relationship(
        foreign_keys="ObjectRelation.target_object_id",
        back_populates="target_object",
    )
    revisions: Mapped[list[ObjectRevision]] = relationship(
        back_populates="object",
        cascade="all, delete-orphan",
        order_by="ObjectRevision.revision_number",
    )
    attachments: Mapped[list[Attachment]] = relationship(
        back_populates="object", cascade="all, delete-orphan"
    )
    data_payloads: Mapped[list[DataPayload]] = relationship(
        back_populates="data_object", cascade="all, delete-orphan"
    )
    data_imports: Mapped[list[DataImport]] = relationship(
        back_populates="data_object", cascade="all, delete-orphan"
    )


class ObjectRelation(Base):
    __tablename__ = "object_relations"
    __table_args__ = (
        CheckConstraint(
            "relation_type in ('contains','uses','produces','precedes','related_to')",
            name="ck_object_relations_type",
        ),
        Index("ix_object_relations_source_type", "source_object_id", "relation_type"),
        Index("ix_object_relations_target_type", "target_object_id", "relation_type"),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    source_object_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("research_objects.id", ondelete="CASCADE"), index=True
    )
    target_object_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("research_objects.id", ondelete="CASCADE"), index=True
    )
    relation_type: Mapped[str] = mapped_column(String(32))
    role: Mapped[str | None] = mapped_column(String(64), nullable=True)
    properties_jsonb: Mapped[dict[str, Any]] = mapped_column(JsonColumn, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    source_object: Mapped[ResearchObject] = relationship(
        foreign_keys=[source_object_id], back_populates="outgoing_relations"
    )
    target_object: Mapped[ResearchObject] = relationship(
        foreign_keys=[target_object_id], back_populates="incoming_relations"
    )


class ObjectRevision(Base):
    __tablename__ = "object_revisions"
    __table_args__ = (UniqueConstraint("object_id", "revision_number", name="uq_object_revisions"),)

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    object_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("research_objects.id", ondelete="CASCADE"), index=True
    )
    revision_number: Mapped[int] = mapped_column(Integer)
    snapshot_jsonb: Mapped[dict[str, Any]] = mapped_column(JsonColumn)
    snapshot_sha256: Mapped[str] = mapped_column(String(64))
    change_note: Mapped[str | None] = mapped_column(String(500), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    object: Mapped[ResearchObject] = relationship(back_populates="revisions")


class ObjectCodeCounter(Base):
    __tablename__ = "object_code_counters"

    kind: Mapped[str] = mapped_column(String(32), primary_key=True)
    next_value: Mapped[int] = mapped_column(Integer, default=1)


class Attachment(Base):
    __tablename__ = "attachments"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    object_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("research_objects.id", ondelete="CASCADE"), index=True
    )
    original_filename: Mapped[str] = mapped_column(String(255))
    storage_key: Mapped[str] = mapped_column(String(512), unique=True)
    content_type: Mapped[str | None] = mapped_column(String(160), nullable=True)
    size_bytes: Mapped[int] = mapped_column(Integer)
    sha256: Mapped[str] = mapped_column(String(64))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    object: Mapped[ResearchObject] = relationship(back_populates="attachments")
    data_imports: Mapped[list[DataImport]] = relationship(back_populates="source_attachment")


class DataPayload(Base):
    __tablename__ = "data_payloads"
    __table_args__ = (
        CheckConstraint("payload_kind in ('xy_series')", name="ck_data_payloads_kind"),
        CheckConstraint("schema_version > 0", name="ck_data_payloads_schema_version"),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    data_object_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("research_objects.id", ondelete="CASCADE"), index=True
    )
    payload_kind: Mapped[str] = mapped_column(String(32))
    name: Mapped[str] = mapped_column(String(240))
    schema_key: Mapped[str] = mapped_column(String(120))
    schema_version: Mapped[int] = mapped_column(Integer, default=1)
    metadata_jsonb: Mapped[dict[str, Any]] = mapped_column(JsonColumn, default=dict)
    summary_jsonb: Mapped[dict[str, Any]] = mapped_column(JsonColumn, default=dict)
    source_attachment_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("attachments.id", ondelete="RESTRICT"), nullable=True, index=True
    )
    payload_sha256: Mapped[str] = mapped_column(String(64))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    data_object: Mapped[ResearchObject] = relationship(back_populates="data_payloads")
    source_attachment: Mapped[Attachment | None] = relationship()
    points: Mapped[list[DataPoint]] = relationship(
        back_populates="payload", cascade="all, delete-orphan", order_by="DataPoint.ordinal"
    )


class DataPoint(Base):
    __tablename__ = "data_points"
    __table_args__ = (
        CheckConstraint("ordinal >= 0", name="ck_data_points_ordinal"),
        CheckConstraint("source_row_number > 0", name="ck_data_points_source_row"),
        UniqueConstraint("payload_id", "source_row_number", name="uq_data_points_source_row"),
        Index("ix_data_points_payload_id", "payload_id"),
    )

    payload_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("data_payloads.id", ondelete="CASCADE"), primary_key=True
    )
    ordinal: Mapped[int] = mapped_column(Integer, primary_key=True)
    source_row_number: Mapped[int] = mapped_column(Integer)
    x_value: Mapped[float] = mapped_column(Float)
    y_value: Mapped[float] = mapped_column(Float)

    payload: Mapped[DataPayload] = relationship(back_populates="points")


class DataImport(Base):
    __tablename__ = "data_imports"
    __table_args__ = (
        CheckConstraint(
            "status in ('preview_ready','completed','failed')", name="ck_data_imports_status"
        ),
        CheckConstraint("source_format in ('csv','xlsx')", name="ck_data_imports_format"),
        CheckConstraint("parser_version > 0", name="ck_data_imports_parser_version"),
        CheckConstraint("row_count is null or row_count >= 0", name="ck_data_imports_row_count"),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    data_object_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("research_objects.id", ondelete="CASCADE"), index=True
    )
    source_attachment_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("attachments.id", ondelete="RESTRICT"), index=True
    )
    payload_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("data_payloads.id", ondelete="RESTRICT"), nullable=True, unique=True
    )
    status: Mapped[str] = mapped_column(String(32), default="preview_ready")
    source_format: Mapped[str] = mapped_column(String(16))
    parser_key: Mapped[str] = mapped_column(String(120), default="tabular-xy")
    parser_version: Mapped[int] = mapped_column(Integer, default=1)
    sheet_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    source_sha256: Mapped[str] = mapped_column(String(64))
    header_json: Mapped[list[str]] = mapped_column(JsonColumn, default=list)
    metadata_jsonb: Mapped[dict[str, Any]] = mapped_column(JsonColumn, default=dict)
    mapping_json: Mapped[dict[str, Any] | None] = mapped_column(JsonColumn, nullable=True)
    warnings_json: Mapped[list[dict[str, Any]]] = mapped_column(JsonColumn, default=list)
    errors_json: Mapped[list[dict[str, Any]]] = mapped_column(JsonColumn, default=list)
    row_count: Mapped[int | None] = mapped_column(Integer, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    data_object: Mapped[ResearchObject] = relationship(back_populates="data_imports")
    source_attachment: Mapped[Attachment] = relationship(back_populates="data_imports")
    payload: Mapped[DataPayload | None] = relationship(foreign_keys=[payload_id])
