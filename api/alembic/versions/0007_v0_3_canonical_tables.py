"""Create the v0.3 canonical domain tables beside the v0.2 storage shape."""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "0007_v0_3_canonical_tables"
down_revision: str | Sequence[str] | None = "0006_agent_changes"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

uuid_type = postgresql.UUID(as_uuid=True)
json_type = postgresql.JSONB()


def _create_v03_tables() -> None:
    """Create frozen v0.3 tables without importing runtime model metadata."""
    op.create_table(
        "process_definition_versions",
        sa.Column("id", uuid_type, primary_key=True),
        sa.Column("process_definition_id", uuid_type, nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column(
            "execution_field_definitions_jsonb",
            json_type,
            nullable=False,
            server_default=sa.text("'{}'::jsonb"),
        ),
        sa.Column("ui_schema_jsonb", json_type, nullable=True),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
        sa.Column("created_by", sa.String(120), nullable=True),
        sa.ForeignKeyConstraint(
            ["process_definition_id"], ["research_objects.id"], ondelete="CASCADE"
        ),
        sa.UniqueConstraint(
            "process_definition_id", "version", name="uq_process_definition_versions"
        ),
        sa.CheckConstraint("version > 0", name="ck_process_definition_versions_version"),
    )
    op.create_index(
        "ix_process_definition_versions_process_definition_id",
        "process_definition_versions",
        ["process_definition_id"],
    )
    op.create_table(
        "process_definition_state",
        sa.Column("process_definition_id", uuid_type, primary_key=True),
        sa.Column("current_version_id", uuid_type, nullable=False),
        sa.ForeignKeyConstraint(
            ["process_definition_id"], ["research_objects.id"], ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(["current_version_id"], ["process_definition_versions.id"]),
    )
    op.create_table(
        "process_executions",
        sa.Column("id", uuid_type, primary_key=True),
        sa.Column("project_scope_id", uuid_type, nullable=True),
        sa.Column("process_definition_id", uuid_type, nullable=False),
        sa.Column("process_definition_version_id", uuid_type, nullable=False),
        sa.Column("title_snapshot", sa.String(240), nullable=True),
        sa.Column("status", sa.String(32), nullable=False, server_default="draft"),
        sa.Column(
            "execution_field_definition_snapshot_jsonb",
            json_type,
            nullable=False,
            server_default=sa.text("'{}'::jsonb"),
        ),
        sa.Column("values_jsonb", json_type, nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column("note", sa.Text(), nullable=True),
        sa.Column("occurred_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
        sa.Column("created_by", sa.String(120), nullable=True),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
        sa.ForeignKeyConstraint(["project_scope_id"], ["research_objects.id"]),
        sa.ForeignKeyConstraint(["process_definition_id"], ["research_objects.id"]),
        sa.ForeignKeyConstraint(
            ["process_definition_version_id"], ["process_definition_versions.id"]
        ),
        sa.CheckConstraint(
            "status in ('draft','running','completed','cancelled')",
            name="ck_process_executions_status",
        ),
    )
    op.create_index(
        "ix_process_executions_project_scope_id", "process_executions", ["project_scope_id"]
    )
    op.create_index("ix_process_executions_scope", "process_executions", ["project_scope_id"])
    op.create_index(
        "ix_process_executions_process_definition_id",
        "process_executions",
        ["process_definition_id"],
    )
    op.create_index(
        "ix_process_executions_definition", "process_executions", ["process_definition_id"]
    )
    op.create_table(
        "process_execution_object_bindings",
        sa.Column("id", uuid_type, primary_key=True),
        sa.Column("execution_id", uuid_type, nullable=False),
        sa.Column("research_object_id", uuid_type, nullable=False),
        sa.Column("direction", sa.String(16), nullable=False),
        sa.Column("role", sa.String(64), nullable=True),
        sa.Column(
            "field_definition_snapshot_jsonb",
            json_type,
            nullable=False,
            server_default=sa.text("'{}'::jsonb"),
        ),
        sa.Column("values_jsonb", json_type, nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column("order_index", sa.Integer(), nullable=False, server_default="0"),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
        sa.ForeignKeyConstraint(["execution_id"], ["process_executions.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(
            ["research_object_id"], ["research_objects.id"], ondelete="CASCADE"
        ),
        sa.CheckConstraint(
            "direction in ('input','context','output')",
            name="ck_execution_object_binding_direction",
        ),
    )
    op.create_index(
        "ix_process_execution_object_bindings_execution_id",
        "process_execution_object_bindings",
        ["execution_id"],
    )
    op.create_index(
        "ix_process_execution_object_bindings_research_object_id",
        "process_execution_object_bindings",
        ["research_object_id"],
    )
    op.create_index(
        "ix_execution_object_bindings_execution",
        "process_execution_object_bindings",
        ["execution_id"],
    )
    op.create_index(
        "ix_execution_object_bindings_object",
        "process_execution_object_bindings",
        ["research_object_id"],
    )
    op.create_index(
        "uq_execution_object_output",
        "process_execution_object_bindings",
        ["research_object_id"],
        unique=True,
        postgresql_where=sa.text("direction = 'output'"),
    )
    op.create_table(
        "process_execution_data_bindings",
        sa.Column("id", uuid_type, primary_key=True),
        sa.Column("execution_id", uuid_type, nullable=False),
        sa.Column("data_id", uuid_type, nullable=False),
        sa.Column("direction", sa.String(16), nullable=False),
        sa.Column("role", sa.String(64), nullable=True),
        sa.Column("values_jsonb", json_type, nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column("order_index", sa.Integer(), nullable=False, server_default="0"),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
        sa.ForeignKeyConstraint(["execution_id"], ["process_executions.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["data_id"], ["research_objects.id"], ondelete="CASCADE"),
        sa.CheckConstraint(
            "direction in ('input','output')", name="ck_execution_data_binding_direction"
        ),
    )
    op.create_index(
        "ix_process_execution_data_bindings_execution_id",
        "process_execution_data_bindings",
        ["execution_id"],
    )
    op.create_index(
        "ix_process_execution_data_bindings_data_id", "process_execution_data_bindings", ["data_id"]
    )
    op.create_index(
        "ix_execution_data_bindings_execution", "process_execution_data_bindings", ["execution_id"]
    )
    op.create_index(
        "ix_execution_data_bindings_data", "process_execution_data_bindings", ["data_id"]
    )
    op.create_index(
        "uq_execution_data_output",
        "process_execution_data_bindings",
        ["data_id"],
        unique=True,
        postgresql_where=sa.text("direction = 'output'"),
    )
    op.create_table(
        "process_execution_relations",
        sa.Column("id", uuid_type, primary_key=True),
        sa.Column("source_execution_id", uuid_type, nullable=False),
        sa.Column("target_execution_id", uuid_type, nullable=False),
        sa.Column("relation_type", sa.String(32), nullable=False, server_default="precedes"),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
        sa.ForeignKeyConstraint(
            ["source_execution_id"], ["process_executions.id"], ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(
            ["target_execution_id"], ["process_executions.id"], ondelete="CASCADE"
        ),
        sa.UniqueConstraint(
            "source_execution_id",
            "target_execution_id",
            "relation_type",
            name="uq_execution_relations",
        ),
        sa.CheckConstraint("relation_type = 'precedes'", name="ck_execution_relations_type"),
    )
    op.create_index(
        "ix_process_execution_relations_source_execution_id",
        "process_execution_relations",
        ["source_execution_id"],
    )
    op.create_index(
        "ix_process_execution_relations_target_execution_id",
        "process_execution_relations",
        ["target_execution_id"],
    )
    op.create_table(
        "process_execution_revisions",
        sa.Column("id", uuid_type, primary_key=True),
        sa.Column("execution_id", uuid_type, nullable=False),
        sa.Column("revision_number", sa.Integer(), nullable=False),
        sa.Column("snapshot_jsonb", json_type, nullable=False),
        sa.Column("snapshot_sha256", sa.String(64), nullable=False),
        sa.Column("change_note", sa.String(500), nullable=True),
        sa.Column("change_set_id", uuid_type, nullable=True),
        sa.Column("source_client_name", sa.String(120), nullable=True),
        sa.Column("source_client_version", sa.String(120), nullable=True),
        sa.Column("source_transport", sa.String(32), nullable=True),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
        sa.ForeignKeyConstraint(["execution_id"], ["process_executions.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["change_set_id"], ["change_sets.id"], ondelete="SET NULL"),
        sa.UniqueConstraint("execution_id", "revision_number", name="uq_execution_revisions"),
    )
    op.create_index(
        "ix_process_execution_revisions_execution_id",
        "process_execution_revisions",
        ["execution_id"],
    )
    op.create_index(
        "ix_process_execution_revisions_change_set_id",
        "process_execution_revisions",
        ["change_set_id"],
    )
    op.create_table(
        "assets",
        sa.Column("id", uuid_type, primary_key=True),
        sa.Column("storage_backend", sa.String(32), nullable=False, server_default="local"),
        sa.Column("bucket", sa.String(255), nullable=True),
        sa.Column("object_key", sa.String(512), nullable=False),
        sa.Column("original_filename", sa.String(255), nullable=False),
        sa.Column("mime_type", sa.String(160), nullable=True),
        sa.Column("size_bytes", sa.Integer(), nullable=False),
        sa.Column("sha256", sa.String(64), nullable=False),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
        sa.Column("created_by", sa.String(120), nullable=True),
        sa.UniqueConstraint(
            "storage_backend", "bucket", "object_key", name="uq_assets_storage_location"
        ),
    )
    op.create_index("ix_assets_sha256", "assets", ["sha256"])
    op.create_table(
        "data_representations",
        sa.Column("id", uuid_type, primary_key=True),
        sa.Column("data_object_id", uuid_type, nullable=False),
        sa.Column("kind", sa.String(32), nullable=False),
        sa.Column("name", sa.String(240), nullable=False),
        sa.Column("format", sa.String(64), nullable=True),
        sa.Column("schema_jsonb", json_type, nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column(
            "metadata_jsonb", json_type, nullable=False, server_default=sa.text("'{}'::jsonb")
        ),
        sa.Column(
            "summary_jsonb", json_type, nullable=False, server_default=sa.text("'{}'::jsonb")
        ),
        sa.Column("inline_payload_jsonb", json_type, nullable=True),
        sa.Column("asset_id", uuid_type, nullable=True),
        sa.Column("source_representation_id", uuid_type, nullable=True),
        sa.Column(
            "provenance_jsonb", json_type, nullable=False, server_default=sa.text("'{}'::jsonb")
        ),
        sa.Column("representation_sha256", sa.String(64), nullable=False),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
        sa.Column("created_by", sa.String(120), nullable=True),
        sa.ForeignKeyConstraint(["data_object_id"], ["research_objects.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["asset_id"], ["assets.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(
            ["source_representation_id"], ["data_representations.id"], ondelete="RESTRICT"
        ),
        sa.CheckConstraint(
            "kind in ('raw_file','table','image','description','structured')",
            name="ck_data_representations_kind",
        ),
    )
    op.create_index(
        "ix_data_representations_data_object_id", "data_representations", ["data_object_id"]
    )
    op.create_index("ix_data_representations_data", "data_representations", ["data_object_id"])
    op.create_index("ix_data_representations_asset", "data_representations", ["asset_id"])
    op.create_index(
        "ix_data_representations_source", "data_representations", ["source_representation_id"]
    )
    op.create_table(
        "data_records",
        sa.Column("data_object_id", uuid_type, primary_key=True),
        sa.Column("scientific_type", sa.String(120), nullable=True),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("origin_representation_id", uuid_type, nullable=True),
        sa.ForeignKeyConstraint(["data_object_id"], ["research_objects.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(
            ["origin_representation_id"], ["data_representations.id"], ondelete="SET NULL"
        ),
    )
    op.create_table(
        "object_asset_links",
        sa.Column("object_id", uuid_type, nullable=False),
        sa.Column("asset_id", uuid_type, nullable=False),
        sa.Column("role", sa.String(64), nullable=False, server_default="attachment"),
        sa.Column("order_index", sa.Integer(), nullable=False, server_default="0"),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
        sa.ForeignKeyConstraint(["object_id"], ["research_objects.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["asset_id"], ["assets.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("object_id", "asset_id"),
        sa.UniqueConstraint("object_id", "asset_id", "role", name="uq_object_asset_links"),
    )
    op.create_table(
        "data_points",
        sa.Column("representation_id", uuid_type, nullable=False),
        sa.Column("ordinal", sa.Integer(), nullable=False),
        sa.Column("source_row_number", sa.Integer(), nullable=False),
        sa.Column("x_value", sa.Float(), nullable=False),
        sa.Column("y_value", sa.Float(), nullable=False),
        sa.ForeignKeyConstraint(
            ["representation_id"], ["data_representations.id"], ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("representation_id", "ordinal"),
        sa.UniqueConstraint(
            "representation_id", "source_row_number", name="uq_data_points_source_row"
        ),
        sa.CheckConstraint("ordinal >= 0", name="ck_data_points_ordinal"),
        sa.CheckConstraint("source_row_number > 0", name="ck_data_points_source_row"),
    )
    op.create_table(
        "data_scalars",
        sa.Column("representation_id", uuid_type, primary_key=True),
        sa.Column("value", sa.Float(), nullable=False),
        sa.Column("unit", sa.String(64), nullable=True),
        sa.ForeignKeyConstraint(
            ["representation_id"], ["data_representations.id"], ondelete="CASCADE"
        ),
        sa.CheckConstraint(
            "value = value AND value < 1.7976931348623157e308 AND value > -1.7976931348623157e308",
            name="ck_data_scalars_finite_value",
        ),
    )
    op.create_table(
        "data_table_rows",
        sa.Column("representation_id", uuid_type, nullable=False),
        sa.Column("ordinal", sa.Integer(), nullable=False),
        sa.Column("source_row_number", sa.Integer(), nullable=True),
        sa.Column("values_jsonb", json_type, nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.ForeignKeyConstraint(
            ["representation_id"], ["data_representations.id"], ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("representation_id", "ordinal"),
        sa.CheckConstraint("ordinal >= 0", name="ck_data_table_rows_ordinal"),
    )
    op.create_table(
        "data_imports",
        sa.Column("id", uuid_type, primary_key=True),
        sa.Column("data_object_id", uuid_type, nullable=False),
        sa.Column("source_asset_id", uuid_type, nullable=False),
        sa.Column("representation_id", uuid_type, nullable=True),
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
            "created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["data_object_id"], ["research_objects.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["source_asset_id"], ["assets.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(
            ["representation_id"], ["data_representations.id"], ondelete="RESTRICT"
        ),
        sa.UniqueConstraint("representation_id"),
        sa.CheckConstraint(
            "status in ('preview_ready','completed','failed')", name="ck_data_imports_status"
        ),
        sa.CheckConstraint("source_format in ('csv','xlsx')", name="ck_data_imports_format"),
        sa.CheckConstraint("parser_version > 0", name="ck_data_imports_parser_version"),
        sa.CheckConstraint("row_count is null or row_count >= 0", name="ck_data_imports_row_count"),
    )
    op.create_index("ix_data_imports_data_object_id", "data_imports", ["data_object_id"])
    op.create_index("ix_data_imports_source_asset_id", "data_imports", ["source_asset_id"])
    op.create_table(
        "view_states",
        sa.Column("view_id", uuid_type, primary_key=True),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("config_jsonb", json_type, nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column("current_revision_id", uuid_type, nullable=True),
        sa.ForeignKeyConstraint(["view_id"], ["research_objects.id"], ondelete="CASCADE"),
    )
    op.create_table(
        "view_revisions",
        sa.Column("id", uuid_type, primary_key=True),
        sa.Column("view_id", uuid_type, nullable=False),
        sa.Column("revision_number", sa.Integer(), nullable=False),
        sa.Column("snapshot_jsonb", json_type, nullable=False),
        sa.Column("snapshot_sha256", sa.String(64), nullable=False),
        sa.Column("change_note", sa.String(500), nullable=True),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
        sa.Column("created_by", sa.String(120), nullable=True),
        sa.ForeignKeyConstraint(["view_id"], ["view_states.view_id"], ondelete="CASCADE"),
        sa.UniqueConstraint("view_id", "revision_number", name="uq_view_revisions"),
    )
    op.create_index("ix_view_revisions_view_id", "view_revisions", ["view_id"])
    op.create_foreign_key(
        "fk_view_states_current_revision",
        "view_states",
        "view_revisions",
        ["current_revision_id"],
        ["id"],
        ondelete="SET NULL",
    )
    op.create_table(
        "view_data_refs",
        sa.Column("view_id", uuid_type, nullable=False),
        sa.Column("data_id", uuid_type, nullable=False),
        sa.Column("data_revision_id", uuid_type, nullable=True),
        sa.Column("order_index", sa.Integer(), nullable=False, server_default="0"),
        sa.ForeignKeyConstraint(["view_id"], ["view_states.view_id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["data_id"], ["research_objects.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["data_revision_id"], ["object_revisions.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("view_id", "data_id"),
        sa.UniqueConstraint("view_id", "data_id", name="uq_view_data_refs"),
    )
    op.create_table(
        "claim_records",
        sa.Column("claim_id", uuid_type, primary_key=True),
        sa.Column("statement", sa.Text(), nullable=False),
        sa.Column("source_type", sa.String(32), nullable=False, server_default="human"),
        sa.Column("source_ref", sa.String(500), nullable=True),
        sa.Column("confidence", sa.String(32), nullable=True),
        sa.Column(
            "metadata_jsonb", json_type, nullable=False, server_default=sa.text("'{}'::jsonb")
        ),
        sa.Column("current_revision_id", uuid_type, nullable=True),
        sa.ForeignKeyConstraint(["claim_id"], ["research_objects.id"], ondelete="CASCADE"),
    )
    op.create_table(
        "claim_revisions",
        sa.Column("id", uuid_type, primary_key=True),
        sa.Column("claim_id", uuid_type, nullable=False),
        sa.Column("revision_number", sa.Integer(), nullable=False),
        sa.Column("snapshot_jsonb", json_type, nullable=False),
        sa.Column("snapshot_sha256", sa.String(64), nullable=False),
        sa.Column("change_note", sa.String(500), nullable=True),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
        sa.Column("created_by", sa.String(120), nullable=True),
        sa.ForeignKeyConstraint(["claim_id"], ["claim_records.claim_id"], ondelete="CASCADE"),
        sa.UniqueConstraint("claim_id", "revision_number", name="uq_claim_revisions"),
    )
    op.create_index("ix_claim_revisions_claim_id", "claim_revisions", ["claim_id"])
    op.create_foreign_key(
        "fk_claim_records_current_revision",
        "claim_records",
        "claim_revisions",
        ["current_revision_id"],
        ["id"],
        ondelete="SET NULL",
    )
    op.create_table(
        "claim_evidence",
        sa.Column("id", uuid_type, primary_key=True),
        sa.Column("claim_id", uuid_type, nullable=False),
        sa.Column("evidence_kind", sa.String(32), nullable=False),
        sa.Column("evidence_id", uuid_type, nullable=True),
        sa.Column("external_ref", sa.String(500), nullable=True),
        sa.Column("polarity", sa.String(16), nullable=False, server_default="support"),
        sa.Column("note", sa.Text(), nullable=True),
        sa.Column("order_index", sa.Integer(), nullable=False, server_default="0"),
        sa.ForeignKeyConstraint(["claim_id"], ["claim_records.claim_id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["evidence_id"], ["research_objects.id"], ondelete="RESTRICT"),
        sa.CheckConstraint(
            "evidence_kind in ('data','view','claim','external')", name="ck_claim_evidence_kind"
        ),
        sa.CheckConstraint("polarity in ('support','counter')", name="ck_claim_evidence_polarity"),
    )
    op.create_index("ix_claim_evidence_claim_id", "claim_evidence", ["claim_id"])


def upgrade() -> None:
    # These tables have incompatible primary-key/FK shapes in v0.3. Keep them
    # under explicit legacy names until 0008 has copied their useful records.
    for old_name, legacy_name in (
        ("attachments", "legacy_attachments"),
        ("data_payloads", "legacy_data_payloads"),
        ("data_points", "legacy_data_points"),
        ("data_scalars", "legacy_data_scalars"),
        ("data_table_rows", "legacy_data_table_rows"),
        ("data_imports", "legacy_data_imports"),
        ("sample_executions", "legacy_sample_executions"),
    ):
        op.execute(f'ALTER TABLE IF EXISTS "{old_name}" RENAME TO "{legacy_name}"')
    for index_name, legacy_index_name in (
        ("data_points_pkey", "legacy_data_points_pkey"),
        ("data_table_rows_pkey", "legacy_data_table_rows_pkey"),
        ("data_scalars_pkey", "legacy_data_scalars_pkey"),
        ("data_imports_pkey", "legacy_data_imports_pkey"),
        ("ix_data_points_payload_id", "ix_legacy_data_points_payload_id"),
        ("ix_data_table_rows_payload_id", "ix_legacy_data_table_rows_payload_id"),
        ("ix_data_imports_data_object_id", "ix_legacy_data_imports_data_object_id"),
        ("ix_data_imports_source_attachment_id", "ix_legacy_data_imports_source_attachment_id"),
    ):
        op.execute(f'ALTER INDEX IF EXISTS "{index_name}" RENAME TO "{legacy_index_name}"')
    for table_name, constraint_name, legacy_constraint_name in (
        ("legacy_data_points", "uq_data_points_source_row", "uq_legacy_data_points_source_row"),
        ("legacy_data_points", "ck_data_points_ordinal", "ck_legacy_data_points_ordinal"),
        ("legacy_data_points", "ck_data_points_source_row", "ck_legacy_data_points_source_row"),
        (
            "legacy_data_scalars",
            "ck_data_scalars_finite_value",
            "ck_legacy_data_scalars_finite_value",
        ),
        (
            "legacy_data_table_rows",
            "ck_data_table_rows_ordinal",
            "ck_legacy_data_table_rows_ordinal",
        ),
    ):
        op.execute(
            f'ALTER TABLE "{table_name}" RENAME CONSTRAINT "{constraint_name}" TO "{legacy_constraint_name}"'
        )

    op.drop_constraint("ck_object_types_kind", "object_types", type_="check")
    op.create_check_constraint(
        "ck_object_types_kind",
        "object_types",
        "kind in ('material','sample','equipment','process','research_object','process_definition','data','experiment','project','view','claim')",
    )
    op.add_column("object_type_versions", sa.Column("created_by", sa.String(120), nullable=True))
    op.add_column(
        "research_objects",
        sa.Column(
            "tags_jsonb", postgresql.JSONB(), nullable=False, server_default=sa.text("'[]'::jsonb")
        ),
    )
    op.add_column(
        "research_objects",
        sa.Column(
            "process_field_definitions_jsonb",
            postgresql.JSONB(),
            nullable=False,
            server_default=sa.text("'{}'::jsonb"),
        ),
    )
    op.alter_column("research_objects", "type_version_id", nullable=True)
    op.drop_constraint("ck_research_objects_kind", "research_objects", type_="check")
    op.create_check_constraint(
        "ck_research_objects_kind",
        "research_objects",
        "kind in ('material','sample','equipment','process','research_object','process_definition','data','experiment','project','view','claim')",
    )

    op.drop_constraint("ck_object_relations_type", "object_relations", type_="check")
    op.create_check_constraint(
        "ck_object_relations_type",
        "object_relations",
        "relation_type in ('contains','includes','uses','produces','precedes','references','subject','derived_from','related_to')",
    )
    for index_name in (
        "uq_object_relations_one_experiment_owner",
        "uq_object_relations_one_producer",
    ):
        op.execute(f'DROP INDEX IF EXISTS "{index_name}"')
    op.create_index(
        "ix_research_objects_tags_gin",
        "research_objects",
        ["tags_jsonb"],
        postgresql_using="gin",
    )
    op.execute("DROP INDEX IF EXISTS ix_research_objects_code_trgm")
    op.execute("DROP INDEX IF EXISTS ix_research_objects_title_trgm")
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

    _create_v03_tables()

    op.drop_constraint("ck_change_sets_operation_kind", "change_sets", type_="check")
    op.create_check_constraint(
        "ck_change_sets_operation_kind",
        "change_sets",
        "operation_kind like 'create_%' or operation_kind like 'update_%'",
    )


def downgrade() -> None:
    # Drop only v0.3 tables that did not exist in v0.2. The legacy tables are
    # restored below so a rollback remains useful for operators.
    v03_tables = (
        "claim_evidence",
        "claim_revisions",
        "claim_records",
        "view_data_refs",
        "view_revisions",
        "view_states",
        "data_imports",
        "data_table_rows",
        "data_scalars",
        "data_points",
        "data_records",
        "object_asset_links",
        "data_representations",
        "assets",
        "process_execution_revisions",
        "process_execution_relations",
        "process_execution_data_bindings",
        "process_execution_object_bindings",
        "process_definition_state",
        "process_definition_versions",
        "process_executions",
    )
    for table_name in v03_tables:
        op.drop_table(table_name)
    op.drop_index("ix_research_objects_tags_gin", table_name="research_objects")
    op.drop_constraint("ck_change_sets_operation_kind", "change_sets", type_="check")
    op.create_check_constraint(
        "ck_change_sets_operation_kind",
        "change_sets",
        "operation_kind in ('create_sample_record','update_sample_record','create_experiment_record','update_experiment_record','create_data_record','update_execution')",
    )
    op.drop_constraint("ck_object_relations_type", "object_relations", type_="check")
    op.create_check_constraint(
        "ck_object_relations_type",
        "object_relations",
        "relation_type in ('contains','includes','uses','produces','precedes','related_to')",
    )
    op.drop_constraint("ck_research_objects_kind", "research_objects", type_="check")
    op.create_check_constraint(
        "ck_research_objects_kind",
        "research_objects",
        "kind in ('material','sample','equipment','process','data','experiment','project')",
    )
    op.alter_column("research_objects", "type_version_id", nullable=False)
    op.drop_column("research_objects", "process_field_definitions_jsonb")
    op.drop_column("research_objects", "tags_jsonb")
    op.drop_column("object_type_versions", "created_by")
    op.drop_constraint("ck_object_types_kind", "object_types", type_="check")
    op.create_check_constraint(
        "ck_object_types_kind",
        "object_types",
        "kind in ('material','sample','equipment','process','data','experiment','project')",
    )
    for legacy_name, old_name in (
        ("legacy_sample_executions", "sample_executions"),
        ("legacy_data_imports", "data_imports"),
        ("legacy_data_table_rows", "data_table_rows"),
        ("legacy_data_scalars", "data_scalars"),
        ("legacy_data_points", "data_points"),
        ("legacy_data_payloads", "data_payloads"),
        ("legacy_attachments", "attachments"),
    ):
        op.execute(f'ALTER TABLE IF EXISTS "{legacy_name}" RENAME TO "{old_name}"')
