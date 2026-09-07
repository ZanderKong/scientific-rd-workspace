"""Add v1.5 scientific document identities and projections."""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "0013_v1_5_scientific_records"
down_revision: str | Sequence[str] | None = "0012_v0_3_schema_alignment"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    uuid_type = postgresql.UUID(as_uuid=True)
    json_type = postgresql.JSONB(astext_type=sa.Text())
    op.add_column(
        "research_objects",
        sa.Column("document_format_version", sa.Integer(), server_default="1", nullable=False),
    )
    op.drop_constraint("ck_process_executions_status", "process_executions", type_="check")
    op.create_check_constraint(
        "ck_process_executions_status",
        "process_executions",
        "status in ('draft','recorded','running','completed','cancelled')",
    )
    op.add_column(
        "process_executions",
        sa.Column("authoring_record_id", uuid_type, nullable=True),
    )
    op.add_column(
        "process_executions",
        sa.Column("authoring_occurrence_id", uuid_type, nullable=True),
    )
    op.add_column(
        "process_executions",
        sa.Column("record_validity", sa.String(16), server_default="active", nullable=False),
    )
    op.create_foreign_key(
        "fk_process_executions_authoring_record",
        "process_executions",
        "research_objects",
        ["authoring_record_id"],
        ["id"],
        ondelete="RESTRICT",
    )
    op.create_index(
        "ix_process_executions_authoring_record_id", "process_executions", ["authoring_record_id"]
    )
    op.create_unique_constraint(
        "uq_process_execution_authoring_occurrence",
        "process_executions",
        ["authoring_record_id", "authoring_occurrence_id"],
    )
    op.create_check_constraint(
        "ck_process_executions_record_validity",
        "process_executions",
        "record_validity in ('active','retracted')",
    )

    op.add_column(
        "process_execution_object_bindings",
        sa.Column("research_object_revision_id", uuid_type, nullable=True),
    )
    op.add_column(
        "process_execution_object_bindings",
        sa.Column("authoring_occurrence_id", uuid_type, nullable=True),
    )
    op.create_unique_constraint(
        "uq_execution_object_binding_authoring_occurrence",
        "process_execution_object_bindings",
        ["execution_id", "authoring_occurrence_id"],
    )
    op.create_foreign_key(
        "fk_execution_object_binding_revision",
        "process_execution_object_bindings",
        "object_revisions",
        ["research_object_revision_id"],
        ["id"],
        ondelete="RESTRICT",
    )
    op.create_index(
        "ix_execution_object_binding_revision",
        "process_execution_object_bindings",
        ["research_object_revision_id"],
    )
    op.add_column(
        "process_execution_data_bindings",
        sa.Column("data_revision_id", uuid_type, nullable=True),
    )
    op.create_foreign_key(
        "fk_execution_data_binding_revision",
        "process_execution_data_bindings",
        "object_revisions",
        ["data_revision_id"],
        ["id"],
        ondelete="RESTRICT",
    )
    op.create_index(
        "ix_process_execution_data_bindings_data_revision_id",
        "process_execution_data_bindings",
        ["data_revision_id"],
    )

    op.drop_constraint("uq_execution_relations", "process_execution_relations", type_="unique")
    op.add_column(
        "process_execution_relations",
        sa.Column("source_kind", sa.String(32), server_default="explicit", nullable=False),
    )
    op.add_column(
        "process_execution_relations",
        sa.Column("source_record_id", uuid_type, nullable=True),
    )
    op.create_foreign_key(
        "fk_execution_relations_source_record",
        "process_execution_relations",
        "research_objects",
        ["source_record_id"],
        ["id"],
        ondelete="CASCADE",
    )
    op.create_index(
        "ix_process_execution_relations_source_record_id",
        "process_execution_relations",
        ["source_record_id"],
    )
    op.create_unique_constraint(
        "uq_execution_relations_source",
        "process_execution_relations",
        [
            "source_execution_id",
            "target_execution_id",
            "relation_type",
            "source_kind",
            "source_record_id",
        ],
        postgresql_nulls_not_distinct=True,
    )

    op.create_table(
        "document_occurrences",
        sa.Column("id", uuid_type, primary_key=True),
        sa.Column("owner_id", uuid_type, nullable=False),
        sa.Column("occurrence_id", uuid_type, nullable=False),
        sa.Column("kind", sa.String(16), nullable=False),
        sa.Column("ordinal", sa.Integer(), nullable=False),
        sa.Column("target_id", uuid_type, nullable=False),
        sa.Column("target_revision_id", uuid_type, nullable=True),
        sa.Column("execution_id", uuid_type, nullable=True),
        sa.Column("binding_id", uuid_type, nullable=True),
        sa.Column(
            "field_definition_snapshot_jsonb", json_type, server_default="{}", nullable=False
        ),
        sa.Column("values_jsonb", json_type, server_default="{}", nullable=False),
        sa.CheckConstraint("kind in ('process','object')", name="ck_document_occurrences_kind"),
        sa.ForeignKeyConstraint(["owner_id"], ["research_objects.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["target_id"], ["research_objects.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(
            ["target_revision_id"], ["object_revisions.id"], ondelete="RESTRICT"
        ),
        sa.ForeignKeyConstraint(["execution_id"], ["process_executions.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(
            ["binding_id"], ["process_execution_object_bindings.id"], ondelete="RESTRICT"
        ),
        sa.UniqueConstraint("owner_id", "occurrence_id", name="uq_document_occurrences_owner"),
    )
    op.create_index(
        "ix_document_occurrences_owner_ordinal", "document_occurrences", ["owner_id", "ordinal"]
    )
    op.create_index("ix_document_occurrences_target", "document_occurrences", ["target_id", "kind"])
    op.create_index(
        "ix_document_occurrences_execution_id", "document_occurrences", ["execution_id"]
    )

    op.create_table(
        "data_subject_assignments",
        sa.Column("id", uuid_type, primary_key=True),
        sa.Column("data_id", uuid_type, nullable=False),
        sa.Column("subject_id", uuid_type, nullable=False),
        sa.Column("subject_revision_id", uuid_type, nullable=True),
        sa.Column("source_kind", sa.String(32), nullable=False),
        sa.Column("source_ref_id", uuid_type, nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.CheckConstraint(
            "source_kind in ('manual','acquisition_document','producer')",
            name="ck_data_subject_assignments_source_kind",
        ),
        sa.ForeignKeyConstraint(["data_id"], ["research_objects.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["subject_id"], ["research_objects.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(
            ["subject_revision_id"], ["object_revisions.id"], ondelete="RESTRICT"
        ),
        sa.UniqueConstraint(
            "data_id",
            "subject_id",
            "source_kind",
            "source_ref_id",
            name="uq_data_subject_assignment_source",
            postgresql_nulls_not_distinct=True,
        ),
    )
    op.create_index("ix_data_subject_assignments_data_id", "data_subject_assignments", ["data_id"])
    op.create_index(
        "ix_data_subject_assignments_subject_id", "data_subject_assignments", ["subject_id"]
    )


def downgrade() -> None:
    op.drop_table("data_subject_assignments")
    op.drop_table("document_occurrences")
    op.drop_constraint(
        "uq_execution_relations_source", "process_execution_relations", type_="unique"
    )
    op.drop_index(
        "ix_process_execution_relations_source_record_id", table_name="process_execution_relations"
    )
    op.drop_constraint(
        "fk_execution_relations_source_record", "process_execution_relations", type_="foreignkey"
    )
    op.drop_column("process_execution_relations", "source_record_id")
    op.drop_column("process_execution_relations", "source_kind")
    op.create_unique_constraint(
        "uq_execution_relations",
        "process_execution_relations",
        ["source_execution_id", "target_execution_id", "relation_type"],
    )
    op.drop_index(
        "ix_process_execution_data_bindings_data_revision_id",
        table_name="process_execution_data_bindings",
    )
    op.drop_constraint(
        "fk_execution_data_binding_revision", "process_execution_data_bindings", type_="foreignkey"
    )
    op.drop_column("process_execution_data_bindings", "data_revision_id")
    op.drop_index(
        "ix_execution_object_binding_revision",
        table_name="process_execution_object_bindings",
    )
    op.drop_constraint(
        "fk_execution_object_binding_revision",
        "process_execution_object_bindings",
        type_="foreignkey",
    )
    op.drop_column("process_execution_object_bindings", "research_object_revision_id")
    op.drop_constraint(
        "uq_execution_object_binding_authoring_occurrence",
        "process_execution_object_bindings",
        type_="unique",
    )
    op.drop_column("process_execution_object_bindings", "authoring_occurrence_id")
    op.drop_constraint(
        "uq_process_execution_authoring_occurrence", "process_executions", type_="unique"
    )
    op.drop_index("ix_process_executions_authoring_record_id", table_name="process_executions")
    op.drop_constraint(
        "fk_process_executions_authoring_record", "process_executions", type_="foreignkey"
    )
    op.drop_constraint("ck_process_executions_record_validity", "process_executions", type_="check")
    op.drop_column("process_executions", "record_validity")
    op.drop_column("process_executions", "authoring_occurrence_id")
    op.drop_column("process_executions", "authoring_record_id")
    op.drop_constraint("ck_process_executions_status", "process_executions", type_="check")
    op.create_check_constraint(
        "ck_process_executions_status",
        "process_executions",
        "status in ('draft','running','completed','cancelled')",
    )
    op.drop_column("research_objects", "document_format_version")
