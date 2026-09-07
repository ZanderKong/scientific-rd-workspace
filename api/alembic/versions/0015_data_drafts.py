"""Add recoverable Data Composer drafts."""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "0015_data_drafts"
down_revision: str | Sequence[str] | None = "0014_occurrence_field_projection"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    uuid_type = postgresql.UUID(as_uuid=True)
    json_type = postgresql.JSONB(astext_type=sa.Text())
    op.create_table(
        "data_drafts",
        sa.Column("id", uuid_type, primary_key=True),
        sa.Column("data_id", uuid_type, nullable=False),
        sa.Column("project_scope_id", uuid_type, nullable=False),
        sa.Column("status", sa.String(16), server_default="editing", nullable=False),
        sa.Column("draft_jsonb", json_type, server_default="{}", nullable=False),
        sa.Column("attachments_jsonb", json_type, server_default="[]", nullable=False),
        sa.Column("finalize_idempotency_key", sa.String(255), nullable=True),
        sa.Column("finalized_result_jsonb", json_type, nullable=True),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.CheckConstraint("status in ('editing','finalized')", name="ck_data_drafts_status"),
        sa.ForeignKeyConstraint(["data_id"], ["research_objects.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["project_scope_id"], ["research_objects.id"], ondelete="CASCADE"),
        sa.UniqueConstraint("data_id", name="uq_data_drafts_data"),
        sa.UniqueConstraint("finalize_idempotency_key", name="uq_data_drafts_finalize_key"),
    )
    op.create_index("ix_data_drafts_data_id", "data_drafts", ["data_id"])
    op.create_index("ix_data_drafts_project_scope_id", "data_drafts", ["project_scope_id"])
    op.create_index("ix_data_drafts_project_status", "data_drafts", ["project_scope_id", "status"])


def downgrade() -> None:
    op.drop_table("data_drafts")
