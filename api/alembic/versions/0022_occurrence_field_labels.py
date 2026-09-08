"""Persist occurrence field labels for user-facing dynamic table catalogs.

Revision ID: 0022_occurrence_field_labels
Revises: 0021_typed_revision_refs
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "0022_occurrence_field_labels"
down_revision: str | Sequence[str] | None = "0021_typed_revision_refs"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "occurrence_field_values",
        sa.Column("field_label", sa.String(length=240), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("occurrence_field_values", "field_label")
