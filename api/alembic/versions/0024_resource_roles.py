"""Add the explicit resource classification used by the unified resource surface."""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "0024_resource_roles"
down_revision: str | Sequence[str] | None = "0023_scientific_document_v2"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("research_objects", sa.Column("resource_role", sa.String(length=16), nullable=True))
    op.create_check_constraint(
        "ck_research_objects_resource_role",
        "research_objects",
        "resource_role is null or resource_role in ('material','equipment','process')",
    )
    op.create_index("ix_research_objects_resource_role", "research_objects", ["resource_role"])
    op.execute(
        "UPDATE research_objects SET resource_role = 'process' "
        "WHERE kind = 'process_definition' AND resource_role IS NULL"
    )


def downgrade() -> None:
    op.drop_index("ix_research_objects_resource_role", table_name="research_objects")
    op.drop_constraint("ck_research_objects_resource_role", "research_objects", type_="check")
    op.drop_column("research_objects", "resource_role")
