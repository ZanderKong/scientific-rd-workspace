"""Add narrow tabular measurement provenance tables.

Revision ID: 0003_scientific_measurements
Revises: 0002_immutable_template_versions
"""

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision = "0003_scientific_measurements"
down_revision = "0002_immutable_template_versions"
branch_labels = None
depends_on = None

json_type = sa.JSON().with_variant(postgresql.JSONB(), "postgresql")
uuid_type = sa.Uuid()


def upgrade() -> None:
    op.create_table(
        "measurement_imports",
        sa.Column("id", uuid_type, nullable=False),
        sa.Column("experiment_id", uuid_type, nullable=False),
        sa.Column("source_attachment_id", uuid_type, nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False, server_default="preview_ready"),
        sa.Column("source_format", sa.String(length=16), nullable=False),
        sa.Column("parser_key", sa.String(length=120), nullable=False, server_default="tabular-xy"),
        sa.Column("parser_version", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("sheet_name", sa.String(length=255), nullable=True),
        sa.Column("source_sha256", sa.String(length=64), nullable=False),
        sa.Column("header_json", json_type, nullable=False),
        sa.Column("source_metadata_json", json_type, nullable=False),
        sa.Column("mapping_json", json_type, nullable=True),
        sa.Column("warnings_json", json_type, nullable=False),
        sa.Column("errors_json", json_type, nullable=False),
        sa.Column("row_count", sa.Integer(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.CheckConstraint("status in ('preview_ready', 'completed', 'failed')", name="ck_measurement_imports_status"),
        sa.CheckConstraint("source_format in ('csv', 'xlsx')", name="ck_measurement_imports_format"),
        sa.CheckConstraint("parser_version > 0", name="ck_measurement_imports_parser_version"),
        sa.CheckConstraint("row_count is null or row_count >= 0", name="ck_measurement_imports_row_count"),
        sa.ForeignKeyConstraint(["experiment_id"], ["experiments.id"]),
        sa.ForeignKeyConstraint(["source_attachment_id"], ["attachments.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_measurement_imports_experiment_id", "measurement_imports", ["experiment_id"])
    op.create_index("ix_measurement_imports_source_attachment_id", "measurement_imports", ["source_attachment_id"])

    op.create_table(
        "measurements",
        sa.Column("id", uuid_type, nullable=False),
        sa.Column("experiment_id", uuid_type, nullable=False),
        sa.Column("import_id", uuid_type, nullable=False),
        sa.Column("name", sa.String(length=240), nullable=False),
        sa.Column("measurement_type", sa.String(length=64), nullable=False),
        sa.Column("schema_key", sa.String(length=120), nullable=False, server_default="xy-series"),
        sa.Column("schema_version", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("default_chart_type", sa.String(length=16), nullable=False, server_default="line"),
        sa.Column("x_label", sa.String(length=120), nullable=False),
        sa.Column("x_unit", sa.String(length=64), nullable=False),
        sa.Column("y_label", sa.String(length=120), nullable=False),
        sa.Column("y_unit", sa.String(length=64), nullable=False),
        sa.Column("row_count", sa.Integer(), nullable=False),
        sa.Column("summary_json", json_type, nullable=False),
        sa.Column("points_sha256", sa.String(length=64), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.CheckConstraint("measurement_type in ('spectral_response', 'time_series', 'other_xy')", name="ck_measurements_type"),
        sa.CheckConstraint("schema_version > 0", name="ck_measurements_schema_version"),
        sa.CheckConstraint("default_chart_type in ('line', 'scatter')", name="ck_measurements_chart_type"),
        sa.CheckConstraint("row_count >= 0", name="ck_measurements_row_count"),
        sa.ForeignKeyConstraint(["experiment_id"], ["experiments.id"]),
        sa.ForeignKeyConstraint(["import_id"], ["measurement_imports.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("import_id"),
    )
    op.create_index("ix_measurements_experiment_id", "measurements", ["experiment_id"])

    op.create_table(
        "measurement_points",
        sa.Column("measurement_id", uuid_type, nullable=False),
        sa.Column("ordinal", sa.Integer(), nullable=False),
        sa.Column("source_row_number", sa.Integer(), nullable=False),
        sa.Column("x_value", sa.Float(), nullable=False),
        sa.Column("y_value", sa.Float(), nullable=False),
        sa.CheckConstraint("ordinal >= 0", name="ck_measurement_points_ordinal"),
        sa.CheckConstraint("source_row_number > 0", name="ck_measurement_points_source_row"),
        sa.ForeignKeyConstraint(["measurement_id"], ["measurements.id"]),
        sa.PrimaryKeyConstraint("measurement_id", "ordinal"),
        sa.UniqueConstraint("measurement_id", "source_row_number", name="uq_measurement_points_source_row"),
    )
    op.create_index("ix_measurement_points_measurement_id", "measurement_points", ["measurement_id"])


def downgrade() -> None:
    op.drop_index("ix_measurement_points_measurement_id", table_name="measurement_points")
    op.drop_table("measurement_points")
    op.drop_index("ix_measurements_experiment_id", table_name="measurements")
    op.drop_table("measurements")
    op.drop_index("ix_measurement_imports_source_attachment_id", table_name="measurement_imports")
    op.drop_index("ix_measurement_imports_experiment_id", table_name="measurement_imports")
    op.drop_table("measurement_imports")
