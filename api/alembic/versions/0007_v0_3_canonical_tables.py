"""Create the v0.3 canonical domain tables beside the v0.2 storage shape."""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "0007_v0_3_canonical_tables"
down_revision: str | Sequence[str] | None = "0006_agent_changes"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # These tables have incompatible primary-key/FK shapes in v0.3. Keep them
    # under explicit legacy names until 0008 has copied their useful records.
    for old_name, legacy_name in (
        ("attachments", "legacy_attachments"),
        ("data_payloads", "legacy_data_payloads"),
        ("data_points", "legacy_data_points"),
        ("data_scalars", "legacy_data_scalars"),
        ("data_table_rows", "legacy_data_table_rows"),
        ("data_imports", "legacy_data_imports"),
        ("sample_executions", "legacy_sample_executions"),
    ):
        op.execute(f'ALTER TABLE IF EXISTS "{old_name}" RENAME TO "{legacy_name}"')
    for index_name, legacy_index_name in (
        ("data_points_pkey", "legacy_data_points_pkey"),
        ("data_table_rows_pkey", "legacy_data_table_rows_pkey"),
        ("data_scalars_pkey", "legacy_data_scalars_pkey"),
        ("data_imports_pkey", "legacy_data_imports_pkey"),
        ("ix_data_points_payload_id", "ix_legacy_data_points_payload_id"),
        ("ix_data_table_rows_payload_id", "ix_legacy_data_table_rows_payload_id"),
        ("ix_data_imports_data_object_id", "ix_legacy_data_imports_data_object_id"),
        ("ix_data_imports_source_attachment_id", "ix_legacy_data_imports_source_attachment_id"),
    ):
        op.execute(f'ALTER INDEX IF EXISTS "{index_name}" RENAME TO "{legacy_index_name}"')
    for table_name, constraint_name, legacy_constraint_name in (
        ("legacy_data_points", "uq_data_points_source_row", "uq_legacy_data_points_source_row"),
        ("legacy_data_points", "ck_data_points_ordinal", "ck_legacy_data_points_ordinal"),
        ("legacy_data_points", "ck_data_points_source_row", "ck_legacy_data_points_source_row"),
        (
            "legacy_data_scalars",
            "ck_data_scalars_finite_value",
            "ck_legacy_data_scalars_finite_value",
        ),
        (
            "legacy_data_table_rows",
            "ck_data_table_rows_ordinal",
            "ck_legacy_data_table_rows_ordinal",
        ),
    ):
        op.execute(
            f'ALTER TABLE "{table_name}" RENAME CONSTRAINT "{constraint_name}" TO "{legacy_constraint_name}"'
        )

    op.drop_constraint("ck_object_types_kind", "object_types", type_="check")
    op.create_check_constraint(
        "ck_object_types_kind",
        "object_types",
        "kind in ('material','sample','equipment','process','research_object','process_definition','data','experiment','project','view','claim')",
    )
    op.add_column("object_type_versions", sa.Column("created_by", sa.String(120), nullable=True))
    op.add_column(
        "research_objects",
        sa.Column(
            "tags_jsonb", postgresql.JSONB(), nullable=False, server_default=sa.text("'[]'::jsonb")
        ),
    )
    op.add_column(
        "research_objects",
        sa.Column(
            "process_field_definitions_jsonb",
            postgresql.JSONB(),
            nullable=False,
            server_default=sa.text("'{}'::jsonb"),
        ),
    )
    op.alter_column("research_objects", "type_version_id", nullable=True)
    op.drop_constraint("ck_research_objects_kind", "research_objects", type_="check")
    op.create_check_constraint(
        "ck_research_objects_kind",
        "research_objects",
        "kind in ('material','sample','equipment','process','research_object','process_definition','data','experiment','project','view','claim')",
    )

    op.drop_constraint("ck_object_relations_type", "object_relations", type_="check")
    op.create_check_constraint(
        "ck_object_relations_type",
        "object_relations",
        "relation_type in ('contains','includes','uses','produces','precedes','references','subject','derived_from','related_to')",
    )
    for index_name in (
        "uq_object_relations_one_experiment_owner",
        "uq_object_relations_one_producer",
    ):
        op.execute(f'DROP INDEX IF EXISTS "{index_name}"')
    op.create_index(
        "ix_research_objects_tags_gin",
        "research_objects",
        ["tags_jsonb"],
        postgresql_using="gin",
    )
    op.execute("DROP INDEX IF EXISTS ix_research_objects_code_trgm")
    op.execute("DROP INDEX IF EXISTS ix_research_objects_title_trgm")
    op.create_index(
        "ix_research_objects_code_trgm",
        "research_objects",
        ["code"],
        postgresql_using="gin",
        postgresql_ops={"code": "gin_trgm_ops"},
    )
    op.create_index(
        "ix_research_objects_title_trgm",
        "research_objects",
        ["title"],
        postgresql_using="gin",
        postgresql_ops={"title": "gin_trgm_ops"},
    )

    # Importing the declarative metadata here gives the migration one canonical
    # source for the new tables and their FK/index definitions.
    from app.models import Base

    Base.metadata.create_all(op.get_bind())

    op.drop_constraint("ck_change_sets_operation_kind", "change_sets", type_="check")
    op.create_check_constraint(
        "ck_change_sets_operation_kind",
        "change_sets",
        "operation_kind like 'create_%' or operation_kind like 'update_%'",
    )


def downgrade() -> None:
    from app.models import Base

    # Drop only v0.3 tables that did not exist in v0.2. The legacy tables are
    # restored below so a rollback remains useful for operators.
    v03_tables = (
        "claim_revisions",
        "claim_evidence",
        "claim_records",
        "view_revisions",
        "view_data_refs",
        "view_states",
        "data_imports",
        "data_table_rows",
        "data_scalars",
        "data_points",
        "data_representations",
        "object_asset_links",
        "assets",
        "data_records",
        "process_execution_revisions",
        "process_execution_relations",
        "process_execution_data_bindings",
        "process_execution_object_bindings",
        "process_definition_state",
        "process_definition_versions",
        "process_executions",
    )
    for table_name in v03_tables:
        if table_name in Base.metadata.tables:
            op.drop_table(table_name)
    op.drop_index("ix_research_objects_tags_gin", table_name="research_objects")
    op.drop_constraint("ck_change_sets_operation_kind", "change_sets", type_="check")
    op.create_check_constraint(
        "ck_change_sets_operation_kind",
        "change_sets",
        "operation_kind in ('create_sample_record','update_sample_record','create_experiment_record','update_experiment_record','create_data_record','update_execution')",
    )
    op.drop_constraint("ck_object_relations_type", "object_relations", type_="check")
    op.create_check_constraint(
        "ck_object_relations_type",
        "object_relations",
        "relation_type in ('contains','includes','uses','produces','precedes','related_to')",
    )
    op.drop_constraint("ck_research_objects_kind", "research_objects", type_="check")
    op.create_check_constraint(
        "ck_research_objects_kind",
        "research_objects",
        "kind in ('material','sample','equipment','process','data','experiment','project')",
    )
    op.alter_column("research_objects", "type_version_id", nullable=False)
    op.drop_column("research_objects", "process_field_definitions_jsonb")
    op.drop_column("research_objects", "tags_jsonb")
    op.drop_column("object_type_versions", "created_by")
    op.drop_constraint("ck_object_types_kind", "object_types", type_="check")
    op.create_check_constraint(
        "ck_object_types_kind",
        "object_types",
        "kind in ('material','sample','equipment','process','data','experiment','project')",
    )
    for legacy_name, old_name in (
        ("legacy_sample_executions", "sample_executions"),
        ("legacy_data_imports", "data_imports"),
        ("legacy_data_table_rows", "data_table_rows"),
        ("legacy_data_scalars", "data_scalars"),
        ("legacy_data_points", "data_points"),
        ("legacy_data_payloads", "data_payloads"),
        ("legacy_attachments", "attachments"),
    ):
        op.execute(f'ALTER TABLE IF EXISTS "{legacy_name}" RENAME TO "{old_name}"')
