"""Add non-owning Experiment/Sample membership.

Revision ID: 0004_experiment_membership
Revises: 0003_sample_recording_workflow
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "0004_experiment_membership"
down_revision: str | Sequence[str] | None = "0003_sample_recording_workflow"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.drop_constraint("ck_object_relations_type", "object_relations", type_="check")
    op.create_check_constraint(
        "ck_object_relations_type",
        "object_relations",
        "relation_type in ('contains','includes','uses','produces','precedes','related_to')",
    )
    op.create_index(
        "ix_object_relations_includes_source",
        "object_relations",
        ["source_object_id", "relation_type"],
        postgresql_where=sa.text("relation_type = 'includes'"),
    )
    op.create_index(
        "ix_object_relations_includes_target",
        "object_relations",
        ["target_object_id", "relation_type"],
        postgresql_where=sa.text("relation_type = 'includes'"),
    )


def downgrade() -> None:
    op.drop_index("ix_object_relations_includes_target", table_name="object_relations")
    op.drop_index("ix_object_relations_includes_source", table_name="object_relations")
    op.drop_constraint("ck_object_relations_type", "object_relations", type_="check")
    op.create_check_constraint(
        "ck_object_relations_type",
        "object_relations",
        "relation_type in ('contains','uses','produces','precedes','related_to')",
    )
