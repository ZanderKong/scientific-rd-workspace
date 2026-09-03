"""Add per-resource usage field definitions for Sample recording.

Revision ID: 0003_sample_recording_workflow
Revises: 0002_v0_2_semantic_stabilization
"""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "0003_sample_recording_workflow"
down_revision: str | Sequence[str] | None = "0002_v0_2_semantic_stabilization"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "research_objects",
        sa.Column(
            "usage_schema_jsonb",
            postgresql.JSONB(),
            nullable=False,
            server_default=sa.text("'{}'::jsonb"),
        ),
    )


def downgrade() -> None:
    op.drop_column("research_objects", "usage_schema_jsonb")
