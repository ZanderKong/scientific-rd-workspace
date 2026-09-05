"""Remove v0.2 storage names after the v0.3 copy has completed."""

from collections.abc import Sequence

from alembic import op

revision: str = "0009_v0_3_remove_legacy_runtime"
down_revision: str | Sequence[str] | None = "0008_v0_3_data_migration"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.drop_column("research_objects", "usage_schema_jsonb")
    for table_name in (
        "legacy_sample_executions",
        "legacy_data_imports",
        "legacy_data_table_rows",
        "legacy_data_scalars",
        "legacy_data_points",
        "legacy_data_payloads",
        "legacy_attachments",
    ):
        op.execute(f'DROP TABLE IF EXISTS "{table_name}" CASCADE')
    op.execute(
        "DELETE FROM object_relations WHERE relation_type NOT IN ('references','subject','derived_from','related_to')"
    )


def downgrade() -> None:
    # Legacy storage is intentionally not recreated; v0.3 is a one-way cutover.
    pass
