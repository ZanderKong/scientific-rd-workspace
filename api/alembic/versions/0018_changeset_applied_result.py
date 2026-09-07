"""Persist ChangeSet replay responses."""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "0018_changeset_applied_result"
down_revision: str | Sequence[str] | None = "0017_claim_provenance"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "change_sets",
        sa.Column(
            "applied_result_jsonb",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=True,
        ),
    )


def downgrade() -> None:
    op.drop_column("change_sets", "applied_result_jsonb")
