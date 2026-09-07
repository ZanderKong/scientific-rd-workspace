"""Add explicit scientific record ownership and durable binding validity."""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "0020_authoring_binding"
down_revision: str | Sequence[str] | None = "0019_revision_references"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "research_objects",
        sa.Column("authoring_kind", sa.String(16), nullable=True),
    )
    op.create_index(
        "ix_research_objects_authoring_kind",
        "research_objects",
        ["authoring_kind"],
    )
    op.create_check_constraint(
        "ck_research_objects_authoring_kind",
        "research_objects",
        "authoring_kind is null or authoring_kind in ('sample','data')",
    )

    op.add_column(
        "process_execution_object_bindings",
        sa.Column("is_active", sa.Boolean(), server_default=sa.true(), nullable=False),
    )
    op.drop_index("uq_execution_object_output", table_name="process_execution_object_bindings")
    op.create_index(
        "uq_execution_object_output",
        "process_execution_object_bindings",
        ["research_object_id"],
        unique=True,
        postgresql_where=sa.text("direction = 'output' AND is_active = true"),
    )


def downgrade() -> None:
    op.drop_index("uq_execution_object_output", table_name="process_execution_object_bindings")
    op.create_index(
        "uq_execution_object_output",
        "process_execution_object_bindings",
        ["research_object_id"],
        unique=True,
        postgresql_where=sa.text("direction = 'output'"),
    )
    op.drop_column("process_execution_object_bindings", "is_active")
    op.drop_constraint("ck_research_objects_authoring_kind", "research_objects", type_="check")
    op.drop_index("ix_research_objects_authoring_kind", table_name="research_objects")
    op.drop_column("research_objects", "authoring_kind")
