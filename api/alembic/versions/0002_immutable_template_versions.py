"""Use immutable template-version rows.

Revision ID: 0002_immutable_template_versions
Revises: 0001_phase1_foundation
Create Date: 2026-09-01
"""

import sqlalchemy as sa

from alembic import op

revision = "0002_immutable_template_versions"
down_revision = "0001_phase1_foundation"
branch_labels = None
depends_on = None

SQLITE_NAMING_CONVENTION = {"uq": "uq_%(table_name)s_%(column_0_name)s"}


def upgrade() -> None:
    bind = op.get_bind()
    if bind.dialect.name == "sqlite":
        with op.batch_alter_table(
            "experiment_templates", naming_convention=SQLITE_NAMING_CONVENTION
        ) as batch_op:
            batch_op.drop_constraint("uq_experiment_templates_key", type_="unique")
            batch_op.create_unique_constraint(
                "uq_experiment_templates_key_version", ["key", "version"]
            )
        return

    constraints = sa.inspect(bind).get_unique_constraints("experiment_templates")
    key_constraint = next(
        constraint["name"]
        for constraint in constraints
        if constraint.get("column_names") == ["key"] and constraint.get("name")
    )
    op.drop_constraint(key_constraint, "experiment_templates", type_="unique")
    op.create_unique_constraint(
        "uq_experiment_templates_key_version", "experiment_templates", ["key", "version"]
    )


def downgrade() -> None:
    bind = op.get_bind()
    if bind.dialect.name == "sqlite":
        with op.batch_alter_table(
            "experiment_templates", naming_convention=SQLITE_NAMING_CONVENTION
        ) as batch_op:
            batch_op.drop_constraint("uq_experiment_templates_key_version", type_="unique")
            batch_op.create_unique_constraint("uq_experiment_templates_key", ["key"])
        return

    op.drop_constraint(
        "uq_experiment_templates_key_version", "experiment_templates", type_="unique"
    )
    op.create_unique_constraint("experiment_templates_key_key", "experiment_templates", ["key"])
