"""Finalize v0.3 invariants and query indexes."""

from collections.abc import Sequence

from alembic import op

revision: str = "0010_v0_3_integrity_and_indexes"
down_revision: str | Sequence[str] | None = "0009_v0_3_remove_legacy_runtime"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    for table_name, constraint_name in (
        ("object_types", "ck_object_types_kind"),
        ("research_objects", "ck_research_objects_kind"),
        ("object_relations", "ck_object_relations_type"),
    ):
        op.drop_constraint(constraint_name, table_name, type_="check")
    op.create_check_constraint(
        "ck_object_types_kind",
        "object_types",
        "kind in ('research_object','process_definition','data','experiment','project','view','claim')",
    )
    op.create_check_constraint(
        "ck_research_objects_kind",
        "research_objects",
        "kind in ('research_object','process_definition','data','experiment','project','view','claim')",
    )
    op.create_check_constraint(
        "ck_object_relations_type",
        "object_relations",
        "relation_type in ('references','subject','derived_from','related_to')",
    )
    op.execute(
        """
        ALTER TABLE data_representations
        DROP CONSTRAINT IF EXISTS ck_data_representations_source_not_self
        """
    )
    op.create_check_constraint(
        "ck_data_representations_source_not_self",
        "data_representations",
        "source_representation_id IS NULL OR source_representation_id <> id",
    )
    op.execute(
        "CREATE INDEX IF NOT EXISTS ix_process_execution_object_bindings_direction "
        "ON process_execution_object_bindings (research_object_id, direction)"
    )
    op.execute(
        "CREATE INDEX IF NOT EXISTS ix_process_execution_data_bindings_direction "
        "ON process_execution_data_bindings (data_id, direction)"
    )
    op.execute(
        "CREATE INDEX IF NOT EXISTS ix_object_relations_system_shortcuts "
        "ON object_relations (source_object_id, relation_type) "
        "WHERE relation_type IN ('subject','derived_from')"
    )


def downgrade() -> None:
    op.drop_index("ix_object_relations_system_shortcuts", table_name="object_relations")
    op.drop_index(
        "ix_process_execution_data_bindings_direction", table_name="process_execution_data_bindings"
    )
    op.drop_index(
        "ix_process_execution_object_bindings_direction",
        table_name="process_execution_object_bindings",
    )
    op.drop_constraint(
        "ck_data_representations_source_not_self", "data_representations", type_="check"
    )
