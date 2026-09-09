"""Store V2 semantic rows alongside the BlockNote document.

Revision ID: 0023_scientific_document_v2
Revises: 0022_occurrence_field_labels
"""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "0023_scientific_document_v2"
down_revision: str | Sequence[str] | None = "0022_occurrence_field_labels"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "research_objects",
        sa.Column(
            "semantic_entries_jsonb",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
            server_default=sa.text("'[]'::jsonb"),
        ),
    )


def downgrade() -> None:
    op.drop_column("research_objects", "semantic_entries_jsonb")
