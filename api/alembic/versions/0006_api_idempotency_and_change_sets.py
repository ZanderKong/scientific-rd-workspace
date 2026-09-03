"""Add persistent idempotency and reviewed ChangeSets.

Revision ID: 0006_api_idempotency_and_change_sets
Revises: 0005_scientific_data_and_execution
"""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "0006_api_idempotency_and_change_sets"
down_revision: str | Sequence[str] | None = "0005_scientific_data_and_execution"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

uuid_type = postgresql.UUID(as_uuid=True)
json_type = postgresql.JSONB()


def upgrade() -> None:
    op.create_table(
        "api_idempotency_records",
        sa.Column("id", uuid_type, primary_key=True),
        sa.Column("idempotency_key", sa.String(255), nullable=False),
        sa.Column("request_hash", sa.String(64), nullable=False),
        sa.Column("response_status", sa.Integer(), nullable=False),
        sa.Column("response_jsonb", json_type, nullable=False),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
        sa.UniqueConstraint("idempotency_key", name="uq_api_idempotency_key"),
    )
    op.create_index("ix_api_idempotency_created_at", "api_idempotency_records", ["created_at"])
    op.create_table(
        "change_sets",
        sa.Column("id", uuid_type, primary_key=True),
        sa.Column("project_scope_id", uuid_type, nullable=False),
        sa.Column("status", sa.String(32), nullable=False, server_default="proposed"),
        sa.Column("operation_kind", sa.String(64), nullable=False),
        sa.Column("target_kind", sa.String(32), nullable=False),
        sa.Column("target_id", uuid_type, nullable=True),
        sa.Column("base_record_sha256", sa.String(64), nullable=True),
        sa.Column("request_payload_jsonb", json_type, nullable=False),
        sa.Column("preview_jsonb", json_type, nullable=False),
        sa.Column("diff_jsonb", json_type, nullable=False, server_default=sa.text("'[]'::jsonb")),
        sa.Column("source_client_name", sa.String(120), nullable=False, server_default="unknown"),
        sa.Column("source_client_version", sa.String(120), nullable=True),
        sa.Column("source_transport", sa.String(32), nullable=False, server_default="rest"),
        sa.Column("idempotency_key", sa.String(255), nullable=True),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
        sa.Column("reviewed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("applied_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("failure_jsonb", json_type, nullable=True),
        sa.ForeignKeyConstraint(["project_scope_id"], ["research_objects.id"], ondelete="CASCADE"),
        sa.UniqueConstraint("idempotency_key", name="uq_change_sets_idempotency_key"),
        sa.CheckConstraint(
            "status in ('proposed','approved','rejected','applied','stale','failed')",
            name="ck_change_sets_status",
        ),
        sa.CheckConstraint(
            "operation_kind in ("
            "'create_sample_record','update_sample_record',"
            "'create_experiment_record','update_experiment_record',"
            "'create_data_record','update_execution')",
            name="ck_change_sets_operation_kind",
        ),
    )
    op.create_index("ix_change_sets_project_scope_id", "change_sets", ["project_scope_id"])
    op.create_index("ix_change_sets_project_status", "change_sets", ["project_scope_id", "status"])
    op.create_index("ix_change_sets_target", "change_sets", ["target_kind", "target_id"])
    op.create_index("ix_change_sets_created_at", "change_sets", ["created_at"])
    op.add_column("object_revisions", sa.Column("change_set_id", uuid_type, nullable=True))
    op.add_column(
        "object_revisions", sa.Column("source_client_name", sa.String(120), nullable=True)
    )
    op.add_column(
        "object_revisions", sa.Column("source_client_version", sa.String(120), nullable=True)
    )
    op.add_column("object_revisions", sa.Column("source_transport", sa.String(32), nullable=True))
    op.create_foreign_key(
        "fk_object_revisions_change_set_id",
        "object_revisions",
        "change_sets",
        ["change_set_id"],
        ["id"],
        ondelete="SET NULL",
    )
    op.create_index("ix_object_revisions_change_set_id", "object_revisions", ["change_set_id"])


def downgrade() -> None:
    op.drop_index("ix_object_revisions_change_set_id", table_name="object_revisions")
    op.drop_constraint("fk_object_revisions_change_set_id", "object_revisions", type_="foreignkey")
    op.drop_column("object_revisions", "source_transport")
    op.drop_column("object_revisions", "source_client_version")
    op.drop_column("object_revisions", "source_client_name")
    op.drop_column("object_revisions", "change_set_id")
    op.drop_index("ix_change_sets_created_at", table_name="change_sets")
    op.drop_index("ix_change_sets_target", table_name="change_sets")
    op.drop_index("ix_change_sets_project_status", table_name="change_sets")
    op.drop_index("ix_change_sets_project_scope_id", table_name="change_sets")
    op.drop_table("change_sets")
    op.drop_index("ix_api_idempotency_created_at", table_name="api_idempotency_records")
    op.drop_table("api_idempotency_records")
