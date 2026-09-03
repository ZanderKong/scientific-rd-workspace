"""Add scientific payload variants and SampleExecution.

Revision ID: 0005_scientific_data_and_execution
Revises: 0004_experiment_membership
"""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "0005_scientific_data_and_execution"
down_revision: str | Sequence[str] | None = "0004_experiment_membership"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

uuid_type = postgresql.UUID(as_uuid=True)
json_type = postgresql.JSONB()


def upgrade() -> None:
    op.drop_constraint("ck_data_payloads_kind", "data_payloads", type_="check")
    op.create_check_constraint(
        "ck_data_payloads_kind",
        "data_payloads",
        "payload_kind in ('scalar','xy_series','table','file')",
    )
    op.create_table(
        "data_scalars",
        sa.Column("payload_id", uuid_type, primary_key=True),
        sa.Column("value", sa.Float(), nullable=False),
        sa.Column("unit", sa.String(64), nullable=True),
        sa.ForeignKeyConstraint(["payload_id"], ["data_payloads.id"], ondelete="CASCADE"),
        sa.CheckConstraint(
            "value = value AND value < 1.7976931348623157e308 AND value > -1.7976931348623157e308",
            name="ck_data_scalars_finite_value",
        ),
    )
    op.create_table(
        "data_table_rows",
        sa.Column("payload_id", uuid_type, primary_key=True),
        sa.Column("ordinal", sa.Integer(), primary_key=True),
        sa.Column("source_row_number", sa.Integer(), nullable=True),
        sa.Column("values_jsonb", json_type, nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.ForeignKeyConstraint(["payload_id"], ["data_payloads.id"], ondelete="CASCADE"),
        sa.UniqueConstraint("payload_id", "ordinal", name="uq_data_table_rows_ordinal"),
        sa.CheckConstraint("ordinal >= 0", name="ck_data_table_rows_ordinal"),
    )
    op.create_index("ix_data_table_rows_payload_id", "data_table_rows", ["payload_id"])
    op.create_table(
        "sample_executions",
        sa.Column("id", uuid_type, primary_key=True),
        sa.Column("sample_id", uuid_type, nullable=False),
        sa.Column("status", sa.String(32), nullable=False, server_default="running"),
        sa.Column("plan_snapshot_jsonb", json_type, nullable=False),
        sa.Column("plan_snapshot_sha256", sa.String(64), nullable=False),
        sa.Column(
            "observations_jsonb", json_type, nullable=False, server_default=sa.text("'[]'::jsonb")
        ),
        sa.Column(
            "deviation_notes_jsonb",
            json_type,
            nullable=False,
            server_default=sa.text("'[]'::jsonb"),
        ),
        sa.Column(
            "started_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
        sa.ForeignKeyConstraint(["sample_id"], ["research_objects.id"], ondelete="CASCADE"),
        sa.UniqueConstraint("sample_id", name="uq_sample_executions_sample"),
        sa.CheckConstraint(
            "status in ('planned','running','completed','cancelled')",
            name="ck_sample_executions_status",
        ),
    )
    op.create_index("ix_sample_executions_sample_id", "sample_executions", ["sample_id"])
    op.create_index("ix_sample_executions_status", "sample_executions", ["status"])


def downgrade() -> None:
    op.drop_index("ix_sample_executions_status", table_name="sample_executions")
    op.drop_index("ix_sample_executions_sample_id", table_name="sample_executions")
    op.drop_table("sample_executions")
    op.drop_index("ix_data_table_rows_payload_id", table_name="data_table_rows")
    op.drop_table("data_table_rows")
    op.drop_table("data_scalars")
    op.drop_constraint("ck_data_payloads_kind", "data_payloads", type_="check")
    op.create_check_constraint(
        "ck_data_payloads_kind", "data_payloads", "payload_kind in ('xy_series')"
    )
