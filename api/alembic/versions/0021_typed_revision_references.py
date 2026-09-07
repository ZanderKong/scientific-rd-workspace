"""Add typed revision sources and targets to historical protection edges."""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "0021_typed_revision_refs"
down_revision: str | Sequence[str] | None = "0020_authoring_binding"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    uuid_type = postgresql.UUID(as_uuid=True)
    for name, foreign_table in (
        ("source_object_revision_id", "object_revisions"),
        ("source_execution_revision_id", "process_execution_revisions"),
        ("target_execution_revision_id", "process_execution_revisions"),
        ("target_view_revision_id", "view_revisions"),
        ("target_claim_revision_id", "claim_revisions"),
    ):
        op.add_column(
            "revision_references",
            sa.Column(name, uuid_type, nullable=True),
        )
        op.create_foreign_key(
            f"fk_revision_refs_{name[:-3]}",
            "revision_references",
            foreign_table,
            [name],
            ["id"],
            ondelete="RESTRICT",
        )

    op.drop_constraint("ck_revision_references_one_source", "revision_references", type_="check")
    op.drop_constraint("ck_revision_references_one_target", "revision_references", type_="check")
    op.create_check_constraint(
        "ck_revision_references_one_source",
        "revision_references",
        "num_nonnulls(source_object_revision_id, source_execution_revision_id, "
        "source_view_revision_id, source_claim_revision_id) = 1",
    )
    op.create_check_constraint(
        "ck_revision_references_one_target",
        "revision_references",
        "num_nonnulls(target_object_revision_id, target_representation_id, "
        "target_execution_revision_id, target_view_revision_id, target_claim_revision_id, "
        "target_asset_id, target_object_id) = 1",
    )
    for name, column in (
        ("ix_revision_references_source_object_revision", "source_object_revision_id"),
        ("ix_revision_references_source_execution_revision", "source_execution_revision_id"),
        ("ix_revision_references_target_execution_revision", "target_execution_revision_id"),
        ("ix_revision_references_target_view_revision", "target_view_revision_id"),
        ("ix_revision_references_target_claim_revision", "target_claim_revision_id"),
    ):
        op.create_index(name, "revision_references", [column])


def downgrade() -> None:
    op.drop_constraint("ck_revision_references_one_source", "revision_references", type_="check")
    op.drop_constraint("ck_revision_references_one_target", "revision_references", type_="check")
    op.create_check_constraint(
        "ck_revision_references_one_source",
        "revision_references",
        "num_nonnulls(source_view_revision_id, source_claim_revision_id) = 1",
    )
    op.create_check_constraint(
        "ck_revision_references_one_target",
        "revision_references",
        "num_nonnulls(target_object_revision_id, target_representation_id, "
        "target_asset_id, target_object_id) = 1",
    )
    for name in (
        "ix_revision_references_target_claim_revision",
        "ix_revision_references_target_view_revision",
        "ix_revision_references_target_execution_revision",
        "ix_revision_references_source_execution_revision",
        "ix_revision_references_source_object_revision",
    ):
        op.drop_index(name, table_name="revision_references")
    for name in (
        "target_claim_revision_id",
        "target_view_revision_id",
        "target_execution_revision_id",
        "source_execution_revision_id",
        "source_object_revision_id",
    ):
        op.drop_constraint(
            f"fk_revision_refs_{name[:-3]}", "revision_references", type_="foreignkey"
        )
        op.drop_column("revision_references", name)
