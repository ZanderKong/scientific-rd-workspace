"""Persist View revision provenance on ProcessExecution."""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "0011_v0_3_provenance_pins"
down_revision: str | Sequence[str] | None = "0010_v0_3_integrity_and_indexes"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    uuid_type = postgresql.UUID(as_uuid=True)
    op.add_column(
        "process_executions",
        sa.Column("source_view_id", uuid_type, nullable=True),
    )
    op.add_column(
        "process_executions",
        sa.Column("source_view_revision_id", uuid_type, nullable=True),
    )
    op.create_foreign_key(
        "fk_process_executions_source_view",
        "process_executions",
        "research_objects",
        ["source_view_id"],
        ["id"],
    )
    op.create_foreign_key(
        "fk_process_executions_source_view_revision",
        "process_executions",
        "view_revisions",
        ["source_view_revision_id"],
        ["id"],
    )
    op.create_index(
        "ix_process_executions_source_view_id", "process_executions", ["source_view_id"]
    )
    op.create_index(
        "ix_process_executions_source_view_revision_id",
        "process_executions",
        ["source_view_revision_id"],
    )


def downgrade() -> None:
    op.drop_index("ix_process_executions_source_view_revision_id", table_name="process_executions")
    op.drop_index("ix_process_executions_source_view_id", table_name="process_executions")
    op.drop_constraint(
        "fk_process_executions_source_view_revision",
        "process_executions",
        type_="foreignkey",
    )
    op.drop_constraint(
        "fk_process_executions_source_view", "process_executions", type_="foreignkey"
    )
    op.drop_column("process_executions", "source_view_revision_id")
    op.drop_column("process_executions", "source_view_id")
