"""Allow claims to be drafted before a primary source is chosen."""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "0025_optional_claim_source"
down_revision: str | Sequence[str] | None = "0024_resource_roles"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.alter_column("claim_records", "primary_source_kind", existing_type=sa.String(length=32), nullable=True)
    op.alter_column("claim_records", "primary_source_id", existing_type=sa.UUID(), nullable=True)
    op.alter_column("claim_records", "primary_source_revision_id", existing_type=sa.UUID(), nullable=True)


def downgrade() -> None:
    op.alter_column("claim_records", "primary_source_revision_id", existing_type=sa.UUID(), nullable=False)
    op.alter_column("claim_records", "primary_source_id", existing_type=sa.UUID(), nullable=False)
    op.alter_column("claim_records", "primary_source_kind", existing_type=sa.String(length=32), nullable=False)
