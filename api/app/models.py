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
OBJECT_KINDS = (
    "research_object",
    "process_definition",
    "data",
    "experiment",
    "project",
    "view",
    "claim",
)
RELATION_TYPES = ("references", "subject", "derived_from", "related_to")


class ObjectType(Base):
    __tablename__ = "object_types"
    __table_args__ = (
        UniqueConstraint("key", name="uq_object_types_key"),
        CheckConstraint(
            "kind in ("
            "'research_object','process_definition','data','experiment',"
            "'project','view','claim')",
            name="ck_object_types_kind",
        ),
        Index(
            "uq_object_types_one_default_per_kind",
            "kind",
            unique=True,
            postgresql_where=text("is_default = true"),
        ),
    )
    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    key: Mapped[str] = mapped_column(String(120), index=True)
    kind: Mapped[str] = mapped_column(String(32), index=True)
    label_zh: Mapped[str] = mapped_column(String(120))
    label_en: Mapped[str] = mapped_column(String(120))
    description_zh: Mapped[str | None] = mapped_column(Text, nullable=True)
    description_en: Mapped[str | None] = mapped_column(Text, nullable=True)
    is_default: Mapped[bool] = mapped_column(Boolean, default=False, server_default="false")
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
        CheckConstraint("version > 0", name="ck_object_type_versions_version"),
    )
    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    object_type_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("object_types.id"), index=True)
    version: Mapped[int] = mapped_column(Integer)
    json_schema: Mapped[dict[str, Any]] = mapped_column(JsonColumn, default=dict)
    ui_schema: Mapped[dict[str, Any] | None] = mapped_column(JsonColumn, nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, server_default="true")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    created_by: Mapped[str | None] = mapped_column(String(120), nullable=True)
    object_type: Mapped[ObjectType] = relationship(back_populates="versions")
    objects: Mapped[list[ResearchObject]] = relationship(back_populates="type_version")


@event.listens_for(ObjectTypeVersion, "before_update")
def prevent_type_version_mutation(
    _mapper: Any, _connection: Any, target: ObjectTypeVersion
) -> None:
    state = inspect(target)
    if any(
        state.attrs[field].history.has_changes()
        for field in ("object_type_id", "version", "json_schema", "ui_schema")
    ):
        raise ValueError("object type versions are immutable; create a new version")


@event.listens_for(ObjectType, "before_update")
def prevent_object_type_identity_mutation(
    _mapper: Any, _connection: Any, target: ObjectType
) -> None:
    state = inspect(target)
    if state.attrs.key.history.has_changes() or state.attrs.kind.history.has_changes():
        raise ValueError("object type identity is immutable; create a new object type")


class ResearchObject(Base):
    __tablename__ = "research_objects"
    __table_args__ = (
        CheckConstraint(
            "kind in ("
            "'research_object','process_definition','data','experiment',"
            "'project','view','claim')",
            name="ck_research_objects_kind",
        ),
        UniqueConstraint("code", name="uq_research_objects_code"),
        Index("ix_research_objects_code", "code"),
        Index("ix_research_objects_kind", "kind"),
        Index("ix_research_objects_project_scope_id", "project_scope_id"),
        Index("ix_research_objects_project_kind", "project_scope_id", "kind"),
        Index("ix_research_objects_type_version", "type_version_id"),
        Index("ix_research_objects_properties_gin", "properties_jsonb", postgresql_using="gin"),
        Index("ix_research_objects_tags_gin", "tags_jsonb", postgresql_using="gin"),
        Index(
            "ix_research_objects_code_trgm",
            "code",
            postgresql_using="gin",
            postgresql_ops={"code": "gin_trgm_ops"},
        ),
        Index(
            "ix_research_objects_title_trgm",
            "title",
            postgresql_using="gin",
            postgresql_ops={"title": "gin_trgm_ops"},
        ),
    )
    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    code: Mapped[str] = mapped_column(String(32))
    kind: Mapped[str] = mapped_column(String(32))
    title: Mapped[str] = mapped_column(String(240))
    status: Mapped[str] = mapped_column(String(32), default="active", server_default="active")
    project_scope_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("research_objects.id"), nullable=True
    )
    type_version_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("object_type_versions.id"), nullable=True
    )
    properties_jsonb: Mapped[dict[str, Any]] = mapped_column(
        JsonColumn, default=dict, server_default=text("'{}'::jsonb")
    )
    tags_jsonb: Mapped[list[str]] = mapped_column(
        JsonColumn, default=list, server_default=text("'[]'::jsonb")
    )
    process_field_definitions_jsonb: Mapped[dict[str, Any]] = mapped_column(
        JsonColumn, default=dict, server_default=text("'{}'::jsonb")
    )
    content_document: Mapped[list[dict[str, Any]]] = mapped_column(
        JsonColumn, default=list, server_default=text("'[]'::jsonb")
    )
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )
    project_scope: Mapped[ResearchObject | None] = relationship(
        remote_side=[id], back_populates="scoped_objects"
    )
    scoped_objects: Mapped[list[ResearchObject]] = relationship(back_populates="project_scope")
    type_version: Mapped[ObjectTypeVersion | None] = relationship(back_populates="objects")
    outgoing_relations: Mapped[list[ObjectRelation]] = relationship(
        foreign_keys="ObjectRelation.source_object_id",
        back_populates="source_object",
        cascade="all, delete-orphan",
    )
    incoming_relations: Mapped[list[ObjectRelation]] = relationship(
        foreign_keys="ObjectRelation.target_object_id",
        back_populates="target_object",
        cascade="all, delete-orphan",
    )
    revisions: Mapped[list[ObjectRevision]] = relationship(
        back_populates="object",
        cascade="all, delete-orphan",
        order_by="ObjectRevision.revision_number",
    )
    asset_links: Mapped[list[ObjectAssetLink]] = relationship(
        back_populates="object", cascade="all, delete-orphan"
    )
    data_record: Mapped[DataRecord | None] = relationship(
        back_populates="data_object", uselist=False, cascade="all, delete-orphan"
    )
    process_definition_versions: Mapped[list[ProcessDefinitionVersion]] = relationship(
        back_populates="process_definition",
        foreign_keys="ProcessDefinitionVersion.process_definition_id",
        cascade="all, delete-orphan",
    )
    view_state: Mapped[ViewState | None] = relationship(
        back_populates="view", uselist=False, cascade="all, delete-orphan"
    )
    claim_record: Mapped[ClaimRecord | None] = relationship(
        back_populates="claim", uselist=False, cascade="all, delete-orphan"
    )


class ObjectRelation(Base):
    __tablename__ = "object_relations"
    __table_args__ = (
        CheckConstraint(
            "relation_type in ('references','subject','derived_from','related_to')",
            name="ck_object_relations_type",
        ),
        Index("ix_object_relations_source_type", "source_object_id", "relation_type"),
        Index("ix_object_relations_target_type", "target_object_id", "relation_type"),
        Index(
            "uq_object_relations_semantic",
            "source_object_id",
            "target_object_id",
            "relation_type",
            "role",
            unique=True,
            postgresql_nulls_not_distinct=True,
        ),
        Index(
            "ix_object_relations_system_shortcuts",
            "source_object_id",
            "relation_type",
            postgresql_where=text("relation_type IN ('subject','derived_from')"),
        ),
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
    properties_jsonb: Mapped[dict[str, Any]] = mapped_column(
        JsonColumn, default=dict, server_default=text("'{}'::jsonb")
    )
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
    change_set_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("change_sets.id", ondelete="SET NULL"), nullable=True, index=True
    )
    source_client_name: Mapped[str | None] = mapped_column(String(120), nullable=True)
    source_client_version: Mapped[str | None] = mapped_column(String(120), nullable=True)
    source_transport: Mapped[str | None] = mapped_column(String(32), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    object: Mapped[ResearchObject] = relationship(back_populates="revisions")
    change_set: Mapped[ChangeSet | None] = relationship(back_populates="revisions")


@event.listens_for(ObjectRevision, "before_update", propagate=True)
def prevent_object_revision_mutation(
    _mapper: Any, _connection: Any, target: ObjectRevision
) -> None:
    raise ValueError("object revisions are immutable")


class ObjectCodeCounter(Base):
    __tablename__ = "object_code_counters"
    kind: Mapped[str] = mapped_column(String(32), primary_key=True)
    next_value: Mapped[int] = mapped_column(Integer, default=1)


class ProcessDefinitionVersion(Base):
    __tablename__ = "process_definition_versions"
    __table_args__ = (
        UniqueConstraint("process_definition_id", "version", name="uq_process_definition_versions"),
        CheckConstraint("version > 0", name="ck_process_definition_versions_version"),
    )
    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    process_definition_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("research_objects.id", ondelete="CASCADE"), index=True
    )
    version: Mapped[int] = mapped_column(Integer)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    execution_field_definitions_jsonb: Mapped[dict[str, Any]] = mapped_column(
        JsonColumn, default=dict, server_default=text("'{}'::jsonb")
    )
    ui_schema_jsonb: Mapped[dict[str, Any] | None] = mapped_column(JsonColumn, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    created_by: Mapped[str | None] = mapped_column(String(120), nullable=True)
    process_definition: Mapped[ResearchObject] = relationship(
        back_populates="process_definition_versions", foreign_keys=[process_definition_id]
    )
    executions: Mapped[list[ProcessExecution]] = relationship(back_populates="definition_version")


@event.listens_for(ProcessDefinitionVersion, "before_update")
def prevent_process_definition_version_mutation(
    _mapper: Any, _connection: Any, target: ProcessDefinitionVersion
) -> None:
    state = inspect(target)
    immutable_fields = (
        "process_definition_id",
        "version",
        "description",
        "execution_field_definitions_jsonb",
        "ui_schema_jsonb",
        "created_at",
        "created_by",
    )
    if any(state.attrs[field].history.has_changes() for field in immutable_fields):
        raise ValueError("process definition versions are immutable; publish a new version")


class ProcessDefinitionState(Base):
    __tablename__ = "process_definition_state"
    process_definition_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("research_objects.id", ondelete="CASCADE"), primary_key=True
    )
    current_version_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("process_definition_versions.id")
    )
    current_version: Mapped[ProcessDefinitionVersion] = relationship()


class ProcessExecution(Base):
    __tablename__ = "process_executions"
    __table_args__ = (
        CheckConstraint(
            "status in ('draft','running','completed','cancelled')",
            name="ck_process_executions_status",
        ),
        Index("ix_process_executions_scope", "project_scope_id"),
        Index("ix_process_executions_definition", "process_definition_id"),
    )
    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    project_scope_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("research_objects.id"), nullable=True, index=True
    )
    process_definition_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("research_objects.id"), index=True
    )
    process_definition_version_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("process_definition_versions.id"), index=True
    )
    source_view_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("research_objects.id"), nullable=True, index=True
    )
    source_view_revision_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("view_revisions.id"), nullable=True, index=True
    )
    title_snapshot: Mapped[str | None] = mapped_column(String(240), nullable=True)
    status: Mapped[str] = mapped_column(String(32), default="draft", server_default="draft")
    execution_field_definition_snapshot_jsonb: Mapped[dict[str, Any]] = mapped_column(
        JsonColumn, default=dict, server_default=text("'{}'::jsonb")
    )
    values_jsonb: Mapped[dict[str, Any]] = mapped_column(
        JsonColumn, default=dict, server_default=text("'{}'::jsonb")
    )
    note: Mapped[str | None] = mapped_column(Text, nullable=True)
    occurred_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    created_by: Mapped[str | None] = mapped_column(String(120), nullable=True)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )
    definition: Mapped[ResearchObject] = relationship(foreign_keys=[process_definition_id])
    definition_version: Mapped[ProcessDefinitionVersion] = relationship(back_populates="executions")
    object_bindings: Mapped[list[ProcessExecutionObjectBinding]] = relationship(
        back_populates="execution",
        cascade="all, delete-orphan",
        order_by="ProcessExecutionObjectBinding.order_index",
    )
    data_bindings: Mapped[list[ProcessExecutionDataBinding]] = relationship(
        back_populates="execution",
        cascade="all, delete-orphan",
        order_by="ProcessExecutionDataBinding.order_index",
    )
    revisions: Mapped[list[ProcessExecutionRevision]] = relationship(
        back_populates="execution",
        cascade="all, delete-orphan",
        order_by="ProcessExecutionRevision.revision_number",
    )


class ProcessExecutionObjectBinding(Base):
    __tablename__ = "process_execution_object_bindings"
    __table_args__ = (
        CheckConstraint(
            "direction in ('input','context','output')",
            name="ck_execution_object_binding_direction",
        ),
        Index("ix_execution_object_bindings_execution", "execution_id"),
        Index("ix_execution_object_bindings_object", "research_object_id"),
        Index("ix_process_execution_object_bindings_direction", "research_object_id", "direction"),
        Index(
            "uq_execution_object_output",
            "research_object_id",
            unique=True,
            postgresql_where=text("direction = 'output'"),
        ),
    )
    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    execution_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("process_executions.id", ondelete="CASCADE"), index=True
    )
    research_object_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("research_objects.id", ondelete="CASCADE"), index=True
    )
    direction: Mapped[str] = mapped_column(String(16))
    role: Mapped[str | None] = mapped_column(String(64), nullable=True)
    field_definition_snapshot_jsonb: Mapped[dict[str, Any]] = mapped_column(
        JsonColumn, default=dict, server_default=text("'{}'::jsonb")
    )
    values_jsonb: Mapped[dict[str, Any]] = mapped_column(
        JsonColumn, default=dict, server_default=text("'{}'::jsonb")
    )
    order_index: Mapped[int] = mapped_column(Integer, default=0, server_default="0")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    execution: Mapped[ProcessExecution] = relationship(back_populates="object_bindings")
    research_object: Mapped[ResearchObject] = relationship()


class ProcessExecutionDataBinding(Base):
    __tablename__ = "process_execution_data_bindings"
    __table_args__ = (
        CheckConstraint(
            "direction in ('input','output')", name="ck_execution_data_binding_direction"
        ),
        Index("ix_execution_data_bindings_execution", "execution_id"),
        Index("ix_execution_data_bindings_data", "data_id"),
        Index("ix_process_execution_data_bindings_direction", "data_id", "direction"),
        Index(
            "uq_execution_data_output",
            "data_id",
            unique=True,
            postgresql_where=text("direction = 'output'"),
        ),
    )
    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    execution_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("process_executions.id", ondelete="CASCADE"), index=True
    )
    data_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("research_objects.id", ondelete="CASCADE"), index=True
    )
    direction: Mapped[str] = mapped_column(String(16))
    role: Mapped[str | None] = mapped_column(String(64), nullable=True)
    values_jsonb: Mapped[dict[str, Any]] = mapped_column(
        JsonColumn, default=dict, server_default=text("'{}'::jsonb")
    )
    order_index: Mapped[int] = mapped_column(Integer, default=0, server_default="0")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    execution: Mapped[ProcessExecution] = relationship(back_populates="data_bindings")
    data: Mapped[ResearchObject] = relationship()


class ProcessExecutionRelation(Base):
    __tablename__ = "process_execution_relations"
    __table_args__ = (
        UniqueConstraint(
            "source_execution_id",
            "target_execution_id",
            "relation_type",
            name="uq_execution_relations",
        ),
        CheckConstraint("relation_type = 'precedes'", name="ck_execution_relations_type"),
    )
    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    source_execution_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("process_executions.id", ondelete="CASCADE"), index=True
    )
    target_execution_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("process_executions.id", ondelete="CASCADE"), index=True
    )
    relation_type: Mapped[str] = mapped_column(
        String(32), default="precedes", server_default="precedes"
    )
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class ProcessExecutionRevision(Base):
    __tablename__ = "process_execution_revisions"
    __table_args__ = (
        UniqueConstraint("execution_id", "revision_number", name="uq_execution_revisions"),
    )
    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    execution_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("process_executions.id", ondelete="CASCADE"), index=True
    )
    revision_number: Mapped[int] = mapped_column(Integer)
    snapshot_jsonb: Mapped[dict[str, Any]] = mapped_column(JsonColumn)
    snapshot_sha256: Mapped[str] = mapped_column(String(64))
    change_note: Mapped[str | None] = mapped_column(String(500), nullable=True)
    change_set_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("change_sets.id", ondelete="SET NULL"), nullable=True, index=True
    )
    source_client_name: Mapped[str | None] = mapped_column(String(120), nullable=True)
    source_client_version: Mapped[str | None] = mapped_column(String(120), nullable=True)
    source_transport: Mapped[str | None] = mapped_column(String(32), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    execution: Mapped[ProcessExecution] = relationship(back_populates="revisions")


class DataRecord(Base):
    __tablename__ = "data_records"
    data_object_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("research_objects.id", ondelete="CASCADE"), primary_key=True
    )
    scientific_type: Mapped[str | None] = mapped_column(String(120), nullable=True)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    origin_representation_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("data_representations.id", ondelete="SET NULL"), nullable=True
    )
    data_object: Mapped[ResearchObject] = relationship(
        back_populates="data_record", foreign_keys=[data_object_id]
    )


class Asset(Base):
    __tablename__ = "assets"
    __table_args__ = (
        UniqueConstraint(
            "storage_backend", "bucket", "object_key", name="uq_assets_storage_location"
        ),
        Index("ix_assets_sha256", "sha256"),
    )
    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    storage_backend: Mapped[str] = mapped_column(
        String(32), default="local", server_default="local"
    )
    bucket: Mapped[str | None] = mapped_column(String(255), nullable=True)
    object_key: Mapped[str] = mapped_column(String(512))
    original_filename: Mapped[str] = mapped_column(String(255))
    mime_type: Mapped[str | None] = mapped_column(String(160), nullable=True)
    size_bytes: Mapped[int] = mapped_column(Integer)
    sha256: Mapped[str] = mapped_column(String(64))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    created_by: Mapped[str | None] = mapped_column(String(120), nullable=True)
    representations: Mapped[list[DataRepresentation]] = relationship(back_populates="asset")


class ObjectAssetLink(Base):
    __tablename__ = "object_asset_links"
    __table_args__ = (
        UniqueConstraint("object_id", "asset_id", "role", name="uq_object_asset_links"),
    )
    object_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("research_objects.id", ondelete="CASCADE"), primary_key=True
    )
    asset_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("assets.id", ondelete="RESTRICT"), primary_key=True
    )
    role: Mapped[str] = mapped_column(String(64), default="attachment", server_default="attachment")
    order_index: Mapped[int] = mapped_column(Integer, default=0, server_default="0")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    object: Mapped[ResearchObject] = relationship(back_populates="asset_links")
    asset: Mapped[Asset] = relationship()


class DataRepresentation(Base):
    __tablename__ = "data_representations"
    __table_args__ = (
        CheckConstraint(
            "kind in ('raw_file','table','image','description','structured')",
            name="ck_data_representations_kind",
        ),
        Index("ix_data_representations_data", "data_object_id"),
        Index("ix_data_representations_asset", "asset_id"),
        Index("ix_data_representations_source", "source_representation_id"),
        CheckConstraint(
            "source_representation_id IS NULL OR source_representation_id <> id",
            name="ck_data_representations_source_not_self",
        ),
    )
    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    data_object_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("research_objects.id", ondelete="CASCADE"), index=True
    )
    kind: Mapped[str] = mapped_column(String(32))
    name: Mapped[str] = mapped_column(String(240))
    format: Mapped[str | None] = mapped_column(String(64), nullable=True)
    schema_jsonb: Mapped[dict[str, Any]] = mapped_column(
        JsonColumn, default=dict, server_default=text("'{}'::jsonb")
    )
    metadata_jsonb: Mapped[dict[str, Any]] = mapped_column(
        JsonColumn, default=dict, server_default=text("'{}'::jsonb")
    )
    summary_jsonb: Mapped[dict[str, Any]] = mapped_column(
        JsonColumn, default=dict, server_default=text("'{}'::jsonb")
    )
    inline_payload_jsonb: Mapped[dict[str, Any] | None] = mapped_column(JsonColumn, nullable=True)
    asset_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("assets.id", ondelete="RESTRICT"), nullable=True
    )
    source_representation_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("data_representations.id", ondelete="RESTRICT"), nullable=True
    )
    provenance_jsonb: Mapped[dict[str, Any]] = mapped_column(
        JsonColumn, default=dict, server_default=text("'{}'::jsonb")
    )
    representation_sha256: Mapped[str] = mapped_column(String(64))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    created_by: Mapped[str | None] = mapped_column(String(120), nullable=True)
    asset: Mapped[Asset | None] = relationship(back_populates="representations")
    source_representation: Mapped[DataRepresentation | None] = relationship(remote_side=[id])
    points: Mapped[list[DataPoint]] = relationship(
        back_populates="representation", cascade="all, delete-orphan", order_by="DataPoint.ordinal"
    )
    scalar: Mapped[DataScalar | None] = relationship(
        back_populates="representation", cascade="all, delete-orphan", uselist=False
    )
    table_rows: Mapped[list[DataTableRow]] = relationship(
        back_populates="representation",
        cascade="all, delete-orphan",
        order_by="DataTableRow.ordinal",
    )


@event.listens_for(DataRepresentation, "before_update")
def prevent_data_representation_mutation(
    _mapper: Any, _connection: Any, target: DataRepresentation
) -> None:
    raise ValueError("data representations are immutable; create a new representation")


class DataPoint(Base):
    __tablename__ = "data_points"
    __table_args__ = (
        CheckConstraint("ordinal >= 0", name="ck_data_points_ordinal"),
        CheckConstraint("source_row_number > 0", name="ck_data_points_source_row"),
        UniqueConstraint(
            "representation_id", "source_row_number", name="uq_data_points_source_row"
        ),
    )
    representation_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("data_representations.id", ondelete="CASCADE"), primary_key=True
    )
    ordinal: Mapped[int] = mapped_column(Integer, primary_key=True)
    source_row_number: Mapped[int] = mapped_column(Integer)
    x_value: Mapped[float] = mapped_column(Float)
    y_value: Mapped[float] = mapped_column(Float)
    representation: Mapped[DataRepresentation] = relationship(back_populates="points")


class DataScalar(Base):
    __tablename__ = "data_scalars"
    __table_args__ = (
        CheckConstraint(
            "value = value AND value < 1.7976931348623157e308 AND value > -1.7976931348623157e308",
            name="ck_data_scalars_finite_value",
        ),
    )
    representation_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("data_representations.id", ondelete="CASCADE"), primary_key=True
    )
    value: Mapped[float] = mapped_column(Float)
    unit: Mapped[str | None] = mapped_column(String(64), nullable=True)
    representation: Mapped[DataRepresentation] = relationship(back_populates="scalar")


class DataTableRow(Base):
    __tablename__ = "data_table_rows"
    __table_args__ = (CheckConstraint("ordinal >= 0", name="ck_data_table_rows_ordinal"),)
    representation_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("data_representations.id", ondelete="CASCADE"), primary_key=True
    )
    ordinal: Mapped[int] = mapped_column(Integer, primary_key=True)
    source_row_number: Mapped[int | None] = mapped_column(Integer, nullable=True)
    values_jsonb: Mapped[dict[str, Any]] = mapped_column(
        JsonColumn, default=dict, server_default=text("'{}'::jsonb")
    )
    representation: Mapped[DataRepresentation] = relationship(back_populates="table_rows")


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
    source_asset_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("assets.id", ondelete="RESTRICT"), index=True
    )
    representation_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("data_representations.id", ondelete="RESTRICT"), nullable=True, unique=True
    )
    status: Mapped[str] = mapped_column(String(32), default="preview_ready")
    source_format: Mapped[str] = mapped_column(String(16))
    parser_key: Mapped[str] = mapped_column(String(120), default="tabular-xy")
    parser_version: Mapped[int] = mapped_column(Integer, default=1)
    sheet_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    source_sha256: Mapped[str] = mapped_column(String(64))
    header_json: Mapped[list[str]] = mapped_column(
        JsonColumn, default=list, server_default=text("'[]'::jsonb")
    )
    metadata_jsonb: Mapped[dict[str, Any]] = mapped_column(
        JsonColumn, default=dict, server_default=text("'{}'::jsonb")
    )
    mapping_json: Mapped[dict[str, Any] | None] = mapped_column(JsonColumn, nullable=True)
    warnings_json: Mapped[list[dict[str, Any]]] = mapped_column(
        JsonColumn, default=list, server_default=text("'[]'::jsonb")
    )
    errors_json: Mapped[list[dict[str, Any]]] = mapped_column(
        JsonColumn, default=list, server_default=text("'[]'::jsonb")
    )
    row_count: Mapped[int | None] = mapped_column(Integer, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    source_asset: Mapped[Asset] = relationship()
    representation: Mapped[DataRepresentation | None] = relationship()


class ViewState(Base):
    __tablename__ = "view_states"
    view_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("research_objects.id", ondelete="CASCADE"), primary_key=True
    )
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    config_jsonb: Mapped[dict[str, Any]] = mapped_column(
        JsonColumn, default=dict, server_default=text("'{}'::jsonb")
    )
    current_revision_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("view_revisions.id", ondelete="SET NULL", use_alter=True), nullable=True
    )
    view: Mapped[ResearchObject] = relationship(back_populates="view_state", foreign_keys=[view_id])
    data_refs: Mapped[list[ViewDataRef]] = relationship(
        back_populates="view_state",
        cascade="all, delete-orphan",
        order_by="ViewDataRef.order_index",
    )
    revisions: Mapped[list[ViewRevision]] = relationship(
        back_populates="view_state",
        foreign_keys="ViewRevision.view_id",
        cascade="all, delete-orphan",
        order_by="ViewRevision.revision_number",
    )


class ViewDataRef(Base):
    __tablename__ = "view_data_refs"
    __table_args__ = ()
    view_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("view_states.view_id", ondelete="CASCADE"), primary_key=True
    )
    data_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("research_objects.id", ondelete="CASCADE"), primary_key=True
    )
    data_revision_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("object_revisions.id", ondelete="SET NULL"), nullable=True
    )
    order_index: Mapped[int] = mapped_column(Integer, default=0, server_default="0")
    view_state: Mapped[ViewState] = relationship(back_populates="data_refs")
    data: Mapped[ResearchObject] = relationship()


class ViewRevision(Base):
    __tablename__ = "view_revisions"
    __table_args__ = (UniqueConstraint("view_id", "revision_number", name="uq_view_revisions"),)
    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    view_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("view_states.view_id", ondelete="CASCADE"), index=True
    )
    revision_number: Mapped[int] = mapped_column(Integer)
    snapshot_jsonb: Mapped[dict[str, Any]] = mapped_column(JsonColumn)
    snapshot_sha256: Mapped[str] = mapped_column(String(64))
    change_note: Mapped[str | None] = mapped_column(String(500), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    created_by: Mapped[str | None] = mapped_column(String(120), nullable=True)
    view_state: Mapped[ViewState] = relationship(back_populates="revisions", foreign_keys=[view_id])


class ClaimRecord(Base):
    __tablename__ = "claim_records"
    claim_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("research_objects.id", ondelete="CASCADE"), primary_key=True
    )
    statement: Mapped[str] = mapped_column(Text)
    source_type: Mapped[str] = mapped_column(String(32), default="human", server_default="human")
    source_ref: Mapped[str | None] = mapped_column(String(500), nullable=True)
    confidence: Mapped[str | None] = mapped_column(String(32), nullable=True)
    metadata_jsonb: Mapped[dict[str, Any]] = mapped_column(
        JsonColumn, default=dict, server_default=text("'{}'::jsonb")
    )
    current_revision_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("claim_revisions.id", ondelete="SET NULL", use_alter=True), nullable=True
    )
    claim: Mapped[ResearchObject] = relationship(
        back_populates="claim_record", foreign_keys=[claim_id]
    )
    evidence: Mapped[list[ClaimEvidence]] = relationship(
        back_populates="claim_record",
        cascade="all, delete-orphan",
        order_by="ClaimEvidence.order_index",
    )
    revisions: Mapped[list[ClaimRevision]] = relationship(
        back_populates="claim_record",
        foreign_keys="ClaimRevision.claim_id",
        cascade="all, delete-orphan",
        order_by="ClaimRevision.revision_number",
    )


class ClaimEvidence(Base):
    __tablename__ = "claim_evidence"
    __table_args__ = (
        CheckConstraint(
            "evidence_kind in ('data','view','claim','external')", name="ck_claim_evidence_kind"
        ),
        CheckConstraint("polarity in ('support','counter')", name="ck_claim_evidence_polarity"),
    )
    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    claim_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("claim_records.claim_id", ondelete="CASCADE"), index=True
    )
    evidence_kind: Mapped[str] = mapped_column(String(32))
    evidence_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("research_objects.id", ondelete="RESTRICT"), nullable=True
    )
    external_ref: Mapped[str | None] = mapped_column(String(500), nullable=True)
    polarity: Mapped[str] = mapped_column(String(16), default="support", server_default="support")
    note: Mapped[str | None] = mapped_column(Text, nullable=True)
    order_index: Mapped[int] = mapped_column(Integer, default=0, server_default="0")
    claim_record: Mapped[ClaimRecord] = relationship(back_populates="evidence")
    evidence: Mapped[ResearchObject | None] = relationship()


class ClaimRevision(Base):
    __tablename__ = "claim_revisions"
    __table_args__ = (UniqueConstraint("claim_id", "revision_number", name="uq_claim_revisions"),)
    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    claim_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("claim_records.claim_id", ondelete="CASCADE"), index=True
    )
    revision_number: Mapped[int] = mapped_column(Integer)
    snapshot_jsonb: Mapped[dict[str, Any]] = mapped_column(JsonColumn)
    snapshot_sha256: Mapped[str] = mapped_column(String(64))
    change_note: Mapped[str | None] = mapped_column(String(500), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    created_by: Mapped[str | None] = mapped_column(String(120), nullable=True)
    claim_record: Mapped[ClaimRecord] = relationship(
        back_populates="revisions", foreign_keys=[claim_id]
    )


@event.listens_for(ProcessExecutionRevision, "before_update", propagate=True)
def prevent_process_execution_revision_mutation(
    _mapper: Any, _connection: Any, target: ProcessExecutionRevision
) -> None:
    raise ValueError("process execution revisions are immutable")


@event.listens_for(ViewRevision, "before_update", propagate=True)
def prevent_view_revision_mutation(_mapper: Any, _connection: Any, target: ViewRevision) -> None:
    raise ValueError("view revisions are immutable")


@event.listens_for(ClaimRevision, "before_update", propagate=True)
def prevent_claim_revision_mutation(_mapper: Any, _connection: Any, target: ClaimRevision) -> None:
    raise ValueError("claim revisions are immutable")


class IdempotencyRecord(Base):
    __tablename__ = "api_idempotency_records"
    __table_args__ = (
        UniqueConstraint("idempotency_key", name="uq_api_idempotency_key"),
        Index("ix_api_idempotency_created_at", "created_at"),
    )
    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    idempotency_key: Mapped[str] = mapped_column(String(255))
    request_hash: Mapped[str] = mapped_column(String(64))
    response_status: Mapped[int] = mapped_column(Integer)
    response_jsonb: Mapped[dict[str, Any]] = mapped_column(JsonColumn)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )


class ChangeSet(Base):
    __tablename__ = "change_sets"
    __table_args__ = (
        CheckConstraint(
            "status in ('proposed','approved','rejected','applied','stale','failed')",
            name="ck_change_sets_status",
        ),
        CheckConstraint(
            "operation_kind like 'create_%' or operation_kind like 'update_%'",
            name="ck_change_sets_operation_kind",
        ),
        Index("ix_change_sets_project_status", "project_scope_id", "status"),
        Index("ix_change_sets_target", "target_kind", "target_id"),
        Index("ix_change_sets_created_at", "created_at"),
        UniqueConstraint("idempotency_key", name="uq_change_sets_idempotency_key"),
    )
    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    project_scope_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("research_objects.id", ondelete="CASCADE"), index=True
    )
    status: Mapped[str] = mapped_column(String(32), default="proposed", server_default="proposed")
    operation_kind: Mapped[str] = mapped_column(String(64))
    target_kind: Mapped[str] = mapped_column(String(32))
    target_id: Mapped[uuid.UUID | None] = mapped_column(Uuid, nullable=True)
    base_record_sha256: Mapped[str | None] = mapped_column(String(64), nullable=True)
    request_payload_jsonb: Mapped[dict[str, Any]] = mapped_column(JsonColumn)
    preview_jsonb: Mapped[dict[str, Any]] = mapped_column(JsonColumn)
    diff_jsonb: Mapped[list[dict[str, Any]]] = mapped_column(
        JsonColumn, default=list, server_default=text("'[]'::jsonb")
    )
    source_client_name: Mapped[str] = mapped_column(
        String(120), default="unknown", server_default="unknown"
    )
    source_client_version: Mapped[str | None] = mapped_column(String(120), nullable=True)
    source_transport: Mapped[str] = mapped_column(String(32), default="rest", server_default="rest")
    idempotency_key: Mapped[str | None] = mapped_column(String(255), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    reviewed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    applied_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    failure_jsonb: Mapped[dict[str, Any] | None] = mapped_column(JsonColumn, nullable=True)
    project_scope: Mapped[ResearchObject] = relationship(foreign_keys=[project_scope_id])
    revisions: Mapped[list[ObjectRevision]] = relationship(back_populates="change_set")
