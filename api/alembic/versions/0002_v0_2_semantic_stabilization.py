"""Harden v0.2 graph semantics and database invariants.

Revision ID: 0002_v0_2_semantic_stabilization
Revises: 0001_v0_2_research_object_graph
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "0002_v0_2_semantic_stabilization"
down_revision: str | Sequence[str] | None = "0001_v0_2_research_object_graph"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


OBJECT_KINDS = "'material','sample','equipment','process','data','experiment','project'"


def upgrade() -> None:
    op.add_column(
        "object_types",
        sa.Column("is_default", sa.Boolean(), nullable=False, server_default=sa.false()),
    )
    op.create_check_constraint("ck_object_types_kind", "object_types", f"kind in ({OBJECT_KINDS})")
    op.create_check_constraint(
        "ck_object_type_versions_version", "object_type_versions", "version > 0"
    )

    op.execute(
        "UPDATE object_types SET is_default = true "
        "WHERE key IN ('material.generic','sample.generic','equipment.generic','process.generic',"
        "'data.generic','experiment.generic','project.generic')"
    )
    op.create_index(
        "uq_object_types_one_default_per_kind",
        "object_types",
        ["kind"],
        unique=True,
        postgresql_where=sa.text("is_default = true"),
    )
    op.create_index(
        "uq_object_relations_one_experiment_owner",
        "object_relations",
        ["target_object_id"],
        unique=True,
        postgresql_where=sa.text("relation_type = 'contains'"),
    )
    op.create_index(
        "uq_object_relations_one_producer",
        "object_relations",
        ["target_object_id"],
        unique=True,
        postgresql_where=sa.text("relation_type = 'produces'"),
    )


def downgrade() -> None:
    op.drop_index("uq_object_relations_one_producer", table_name="object_relations")
    op.drop_index("uq_object_relations_one_experiment_owner", table_name="object_relations")
    op.drop_index("uq_object_types_one_default_per_kind", table_name="object_types")
    op.drop_constraint("ck_object_type_versions_version", "object_type_versions", type_="check")
    op.drop_constraint("ck_object_types_kind", "object_types", type_="check")
    op.drop_column("object_types", "is_default")
