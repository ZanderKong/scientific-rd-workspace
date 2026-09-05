"""Align explicit v0.3 migration indexes with the runtime metadata."""

from collections.abc import Sequence

from alembic import op

revision: str = "0012_v0_3_schema_alignment"
down_revision: str | Sequence[str] | None = "0011_v0_3_provenance_pins"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    for index_name in (
        "ix_object_relations_includes_source",
        "ix_object_relations_includes_target",
    ):
        op.execute(f'DROP INDEX IF EXISTS "{index_name}"')
    op.create_index(
        "ix_process_executions_process_definition_version_id",
        "process_executions",
        ["process_definition_version_id"],
    )
    op.execute(
        'ALTER TABLE "view_data_refs" RENAME CONSTRAINT "uq_view_data_refs" TO "view_data_refs_pkey"'
    )


def downgrade() -> None:
    op.execute(
        'ALTER TABLE "view_data_refs" RENAME CONSTRAINT "view_data_refs_pkey" TO "uq_view_data_refs"'
    )
    op.drop_index(
        "ix_process_executions_process_definition_version_id",
        table_name="process_executions",
    )
    op.create_index(
        "ix_object_relations_includes_source",
        "object_relations",
        ["source_object_id", "relation_type"],
    )
    op.create_index(
        "ix_object_relations_includes_target",
        "object_relations",
        ["target_object_id", "relation_type"],
    )
