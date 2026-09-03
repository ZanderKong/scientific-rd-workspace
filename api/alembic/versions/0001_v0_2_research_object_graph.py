"""v0.2 research object graph baseline.

Revision ID: 0001_v0_2_research_object_graph
Revises:
"""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "0001_v0_2_research_object_graph"
down_revision: str | Sequence[str] | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

uuid_type = postgresql.UUID(as_uuid=True)
json_type = postgresql.JSONB()


def upgrade() -> None:
    op.execute("CREATE EXTENSION IF NOT EXISTS pg_trgm")

    op.create_table(
        "object_types",
        sa.Column("id", uuid_type, primary_key=True),
        sa.Column("key", sa.String(120), nullable=False),
        sa.Column("kind", sa.String(32), nullable=False),
        sa.Column("label_zh", sa.String(120), nullable=False),
        sa.Column("label_en", sa.String(120), nullable=False),
        sa.Column("description_zh", sa.Text(), nullable=True),
        sa.Column("description_en", sa.Text(), nullable=True),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.UniqueConstraint("key", name="uq_object_types_key"),
    )
    op.create_index("ix_object_types_key", "object_types", ["key"])
    op.create_index("ix_object_types_kind", "object_types", ["kind"])

    op.create_table(
        "object_type_versions",
        sa.Column("id", uuid_type, primary_key=True),
        sa.Column("object_type_id", uuid_type, nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("json_schema", json_type, nullable=False),
        sa.Column("ui_schema", json_type, nullable=True),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.ForeignKeyConstraint(["object_type_id"], ["object_types.id"]),
        sa.UniqueConstraint("object_type_id", "version", name="uq_object_type_versions"),
    )
    op.create_index(
        "ix_object_type_versions_object_type_id", "object_type_versions", ["object_type_id"]
    )

    op.create_table(
        "research_objects",
        sa.Column("id", uuid_type, primary_key=True),
        sa.Column("code", sa.String(32), nullable=False),
        sa.Column("kind", sa.String(32), nullable=False),
        sa.Column("title", sa.String(240), nullable=False),
        sa.Column("status", sa.String(32), nullable=False, server_default="active"),
        sa.Column("project_scope_id", uuid_type, nullable=True),
        sa.Column("type_version_id", uuid_type, nullable=False),
        sa.Column(
            "properties_jsonb", json_type, nullable=False, server_default=sa.text("'{}'::jsonb")
        ),
        sa.Column(
            "content_document", json_type, nullable=False, server_default=sa.text("'[]'::jsonb")
        ),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.ForeignKeyConstraint(["project_scope_id"], ["research_objects.id"]),
        sa.ForeignKeyConstraint(["type_version_id"], ["object_type_versions.id"]),
        sa.CheckConstraint(
            "kind in ('material','sample','equipment','process','data','experiment','project')",
            name="ck_research_objects_kind",
        ),
        sa.UniqueConstraint("code", name="uq_research_objects_code"),
    )
    op.create_index("ix_research_objects_code", "research_objects", ["code"])
    op.create_index("ix_research_objects_kind", "research_objects", ["kind"])
    op.create_index(
        "ix_research_objects_project_scope_id", "research_objects", ["project_scope_id"]
    )
    op.create_index(
        "ix_research_objects_project_kind", "research_objects", ["project_scope_id", "kind"]
    )
    op.create_index("ix_research_objects_type_version", "research_objects", ["type_version_id"])
    op.create_index(
        "ix_research_objects_properties_gin",
        "research_objects",
        ["properties_jsonb"],
        postgresql_using="gin",
    )
    op.create_index(
        "ix_research_objects_code_trgm",
        "research_objects",
        ["code"],
        postgresql_using="gin",
        postgresql_ops={"code": "gin_trgm_ops"},
    )
    op.create_index(
        "ix_research_objects_title_trgm",
        "research_objects",
        ["title"],
        postgresql_using="gin",
        postgresql_ops={"title": "gin_trgm_ops"},
    )

    op.create_table(
        "object_code_counters",
        sa.Column("kind", sa.String(32), primary_key=True),
        sa.Column("next_value", sa.Integer(), nullable=False, server_default="1"),
    )
    op.bulk_insert(
        sa.table(
            "object_code_counters",
            sa.column("kind", sa.String),
            sa.column("next_value", sa.Integer),
        ),
        [
            {"kind": kind, "next_value": 1}
            for kind in (
                "material",
                "sample",
                "equipment",
                "process",
                "data",
                "experiment",
                "project",
            )
        ],
    )

    op.create_table(
        "object_relations",
        sa.Column("id", uuid_type, primary_key=True),
        sa.Column("source_object_id", uuid_type, nullable=False),
        sa.Column("target_object_id", uuid_type, nullable=False),
        sa.Column("relation_type", sa.String(32), nullable=False),
        sa.Column("role", sa.String(64), nullable=True),
        sa.Column(
            "properties_jsonb", json_type, nullable=False, server_default=sa.text("'{}'::jsonb")
        ),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.ForeignKeyConstraint(["source_object_id"], ["research_objects.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["target_object_id"], ["research_objects.id"], ondelete="CASCADE"),
        sa.CheckConstraint(
            "relation_type in ('contains','uses','produces','precedes','related_to')",
            name="ck_object_relations_type",
        ),
    )
    op.create_index(
        "ix_object_relations_source_object_id", "object_relations", ["source_object_id"]
    )
    op.create_index(
        "ix_object_relations_target_object_id", "object_relations", ["target_object_id"]
    )
    op.create_index(
        "ix_object_relations_source_type", "object_relations", ["source_object_id", "relation_type"]
    )
    op.create_index(
        "ix_object_relations_target_type", "object_relations", ["target_object_id", "relation_type"]
    )
    op.execute(
        "CREATE UNIQUE INDEX uq_object_relations_semantic "
        "ON object_relations (source_object_id, target_object_id, relation_type, role) "
        "NULLS NOT DISTINCT"
    )

    op.create_table(
        "object_revisions",
        sa.Column("id", uuid_type, primary_key=True),
        sa.Column("object_id", uuid_type, nullable=False),
        sa.Column("revision_number", sa.Integer(), nullable=False),
        sa.Column("snapshot_jsonb", json_type, nullable=False),
        sa.Column("snapshot_sha256", sa.String(64), nullable=False),
        sa.Column("change_note", sa.String(500), nullable=True),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.ForeignKeyConstraint(["object_id"], ["research_objects.id"], ondelete="CASCADE"),
        sa.UniqueConstraint("object_id", "revision_number", name="uq_object_revisions"),
    )
    op.create_index("ix_object_revisions_object_id", "object_revisions", ["object_id"])

    op.create_table(
        "attachments",
        sa.Column("id", uuid_type, primary_key=True),
        sa.Column("object_id", uuid_type, nullable=False),
        sa.Column("original_filename", sa.String(255), nullable=False),
        sa.Column("storage_key", sa.String(512), nullable=False),
        sa.Column("content_type", sa.String(160), nullable=True),
        sa.Column("size_bytes", sa.Integer(), nullable=False),
        sa.Column("sha256", sa.String(64), nullable=False),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.ForeignKeyConstraint(["object_id"], ["research_objects.id"], ondelete="CASCADE"),
        sa.UniqueConstraint("storage_key", name="uq_attachments_storage_key"),
    )
    op.create_index("ix_attachments_object_id", "attachments", ["object_id"])

    op.create_table(
        "data_payloads",
        sa.Column("id", uuid_type, primary_key=True),
        sa.Column("data_object_id", uuid_type, nullable=False),
        sa.Column("payload_kind", sa.String(32), nullable=False),
        sa.Column("name", sa.String(240), nullable=False),
        sa.Column("schema_key", sa.String(120), nullable=False),
        sa.Column("schema_version", sa.Integer(), nullable=False, server_default="1"),
        sa.Column(
            "metadata_jsonb", json_type, nullable=False, server_default=sa.text("'{}'::jsonb")
        ),
        sa.Column(
            "summary_jsonb", json_type, nullable=False, server_default=sa.text("'{}'::jsonb")
        ),
        sa.Column("source_attachment_id", uuid_type, nullable=True),
        sa.Column("payload_sha256", sa.String(64), nullable=False),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.ForeignKeyConstraint(["data_object_id"], ["research_objects.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["source_attachment_id"], ["attachments.id"], ondelete="RESTRICT"),
        sa.CheckConstraint("payload_kind in ('xy_series')", name="ck_data_payloads_kind"),
        sa.CheckConstraint("schema_version > 0", name="ck_data_payloads_schema_version"),
    )
    op.create_index("ix_data_payloads_data_object_id", "data_payloads", ["data_object_id"])
    op.create_index(
        "ix_data_payloads_source_attachment_id", "data_payloads", ["source_attachment_id"]
    )

    op.create_table(
        "data_points",
        sa.Column("payload_id", uuid_type, primary_key=True),
        sa.Column("ordinal", sa.Integer(), primary_key=True),
        sa.Column("source_row_number", sa.Integer(), nullable=False),
        sa.Column("x_value", sa.Float(), nullable=False),
        sa.Column("y_value", sa.Float(), nullable=False),
        sa.ForeignKeyConstraint(["payload_id"], ["data_payloads.id"], ondelete="CASCADE"),
        sa.CheckConstraint("ordinal >= 0", name="ck_data_points_ordinal"),
        sa.CheckConstraint("source_row_number > 0", name="ck_data_points_source_row"),
        sa.UniqueConstraint("payload_id", "source_row_number", name="uq_data_points_source_row"),
    )
    op.create_index("ix_data_points_payload_id", "data_points", ["payload_id"])

    op.create_table(
        "data_imports",
        sa.Column("id", uuid_type, primary_key=True),
        sa.Column("data_object_id", uuid_type, nullable=False),
        sa.Column("source_attachment_id", uuid_type, nullable=False),
        sa.Column("payload_id", uuid_type, nullable=True),
        sa.Column("status", sa.String(32), nullable=False, server_default="preview_ready"),
        sa.Column("source_format", sa.String(16), nullable=False),
        sa.Column("parser_key", sa.String(120), nullable=False, server_default="tabular-xy"),
        sa.Column("parser_version", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("sheet_name", sa.String(255), nullable=True),
        sa.Column("source_sha256", sa.String(64), nullable=False),
        sa.Column("header_json", json_type, nullable=False, server_default=sa.text("'[]'::jsonb")),
        sa.Column(
            "metadata_jsonb", json_type, nullable=False, server_default=sa.text("'{}'::jsonb")
        ),
        sa.Column("mapping_json", json_type, nullable=True),
        sa.Column(
            "warnings_json", json_type, nullable=False, server_default=sa.text("'[]'::jsonb")
        ),
        sa.Column("errors_json", json_type, nullable=False, server_default=sa.text("'[]'::jsonb")),
        sa.Column("row_count", sa.Integer(), nullable=True),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["data_object_id"], ["research_objects.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["source_attachment_id"], ["attachments.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["payload_id"], ["data_payloads.id"], ondelete="RESTRICT"),
        sa.UniqueConstraint("payload_id", name="uq_data_imports_payload_id"),
        sa.CheckConstraint(
            "status in ('preview_ready','completed','failed')", name="ck_data_imports_status"
        ),
        sa.CheckConstraint("source_format in ('csv','xlsx')", name="ck_data_imports_format"),
        sa.CheckConstraint("parser_version > 0", name="ck_data_imports_parser_version"),
        sa.CheckConstraint("row_count is null or row_count >= 0", name="ck_data_imports_row_count"),
    )
    op.create_index("ix_data_imports_data_object_id", "data_imports", ["data_object_id"])
    op.create_index(
        "ix_data_imports_source_attachment_id", "data_imports", ["source_attachment_id"]
    )


def downgrade() -> None:
    op.drop_index("ix_data_imports_source_attachment_id", table_name="data_imports")
    op.drop_index("ix_data_imports_data_object_id", table_name="data_imports")
    op.drop_table("data_imports")
    op.drop_index("ix_data_points_payload_id", table_name="data_points")
    op.drop_table("data_points")
    op.drop_index("ix_data_payloads_source_attachment_id", table_name="data_payloads")
    op.drop_index("ix_data_payloads_data_object_id", table_name="data_payloads")
    op.drop_table("data_payloads")
    op.drop_index("ix_attachments_object_id", table_name="attachments")
    op.drop_table("attachments")
    op.drop_index("ix_object_revisions_object_id", table_name="object_revisions")
    op.drop_table("object_revisions")
    op.execute("DROP INDEX IF EXISTS uq_object_relations_semantic")
    op.drop_index("ix_object_relations_target_type", table_name="object_relations")
    op.drop_index("ix_object_relations_source_type", table_name="object_relations")
    op.drop_index("ix_object_relations_target_object_id", table_name="object_relations")
    op.drop_index("ix_object_relations_source_object_id", table_name="object_relations")
    op.drop_table("object_relations")
    op.drop_table("object_code_counters")
    for name in (
        "ix_research_objects_title_trgm",
        "ix_research_objects_code_trgm",
        "ix_research_objects_properties_gin",
        "ix_research_objects_type_version",
        "ix_research_objects_project_kind",
        "ix_research_objects_project_scope_id",
        "ix_research_objects_kind",
        "ix_research_objects_code",
    ):
        op.drop_index(name, table_name="research_objects")
    op.drop_table("research_objects")
    op.drop_index("ix_object_type_versions_object_type_id", table_name="object_type_versions")
    op.drop_table("object_type_versions")
    op.drop_index("ix_object_types_kind", table_name="object_types")
    op.drop_index("ix_object_types_key", table_name="object_types")
    op.drop_table("object_types")
