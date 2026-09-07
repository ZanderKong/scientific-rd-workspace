"""Add typed occurrence field projections for record table queries."""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "0014_occurrence_field_projection"
down_revision: str | Sequence[str] | None = "0013_v1_5_scientific_records"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    uuid_type = postgresql.UUID(as_uuid=True)
    op.create_table(
        "occurrence_field_values",
        sa.Column("id", uuid_type, primary_key=True),
        sa.Column("occurrence_row_id", uuid_type, nullable=False),
        sa.Column("owner_id", uuid_type, nullable=False),
        sa.Column("occurrence_id", uuid_type, nullable=False),
        sa.Column("target_id", uuid_type, nullable=False),
        sa.Column("field_key", sa.String(120), nullable=False),
        sa.Column("value_type", sa.String(16), nullable=False),
        sa.Column("text_value", sa.Text(), nullable=True),
        sa.Column("number_value", sa.Float(), nullable=True),
        sa.Column("boolean_value", sa.Boolean(), nullable=True),
        sa.Column("unit", sa.String(64), nullable=True),
        sa.Column("ordinal", sa.Integer(), nullable=False),
        sa.CheckConstraint(
            "value_type in ('number','text','boolean','select')",
            name="ck_occurrence_field_values_type",
        ),
        sa.ForeignKeyConstraint(
            ["occurrence_row_id"], ["document_occurrences.id"], ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(["owner_id"], ["research_objects.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["target_id"], ["research_objects.id"], ondelete="RESTRICT"),
        sa.UniqueConstraint(
            "occurrence_row_id", "field_key", name="uq_occurrence_field_values_field"
        ),
    )
    op.create_index(
        "ix_occurrence_field_values_occurrence_row_id",
        "occurrence_field_values",
        ["occurrence_row_id"],
    )
    op.create_index("ix_occurrence_field_values_owner_id", "occurrence_field_values", ["owner_id"])
    op.create_index(
        "ix_occurrence_field_values_target_id", "occurrence_field_values", ["target_id"]
    )
    op.create_index(
        "ix_occurrence_field_values_lookup",
        "occurrence_field_values",
        ["owner_id", "target_id", "field_key"],
    )
    op.create_index(
        "ix_occurrence_field_values_number",
        "occurrence_field_values",
        ["target_id", "field_key", "number_value"],
    )
    op.create_index(
        "ix_occurrence_field_values_text",
        "occurrence_field_values",
        ["target_id", "field_key", "text_value"],
    )


def downgrade() -> None:
    op.drop_table("occurrence_field_values")
