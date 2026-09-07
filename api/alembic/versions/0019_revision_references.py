"""Protect immutable historical revision dependencies with typed foreign keys."""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "0019_revision_references"
down_revision: str | Sequence[str] | None = "0018_changeset_applied_result"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    uuid_type = postgresql.UUID(as_uuid=True)
    op.create_table(
        "revision_references",
        sa.Column("id", uuid_type, primary_key=True),
        sa.Column("source_view_revision_id", uuid_type, nullable=True),
        sa.Column("source_claim_revision_id", uuid_type, nullable=True),
        sa.Column("target_object_revision_id", uuid_type, nullable=True),
        sa.Column("target_representation_id", uuid_type, nullable=True),
        sa.Column("target_asset_id", uuid_type, nullable=True),
        sa.Column("target_object_id", uuid_type, nullable=True),
        sa.CheckConstraint(
            "num_nonnulls(source_view_revision_id, source_claim_revision_id) = 1",
            name="ck_revision_references_one_source",
        ),
        sa.CheckConstraint(
            "num_nonnulls(target_object_revision_id, target_representation_id, target_asset_id, target_object_id) = 1",
            name="ck_revision_references_one_target",
        ),
        sa.ForeignKeyConstraint(
            ["source_view_revision_id"], ["view_revisions.id"], ondelete="RESTRICT"
        ),
        sa.ForeignKeyConstraint(
            ["source_claim_revision_id"], ["claim_revisions.id"], ondelete="RESTRICT"
        ),
        sa.ForeignKeyConstraint(
            ["target_object_revision_id"], ["object_revisions.id"], ondelete="RESTRICT"
        ),
        sa.ForeignKeyConstraint(
            ["target_representation_id"], ["data_representations.id"], ondelete="RESTRICT"
        ),
        sa.ForeignKeyConstraint(["target_asset_id"], ["assets.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["target_object_id"], ["research_objects.id"], ondelete="RESTRICT"),
    )
    op.create_index(
        "ix_revision_references_source_view", "revision_references", ["source_view_revision_id"]
    )
    op.create_index(
        "ix_revision_references_source_claim", "revision_references", ["source_claim_revision_id"]
    )
    op.create_index(
        "ix_revision_references_target_revision",
        "revision_references",
        ["target_object_revision_id"],
    )
    op.create_index(
        "ix_revision_references_target_representation",
        "revision_references",
        ["target_representation_id"],
    )
    op.create_index(
        "ix_revision_references_target_asset", "revision_references", ["target_asset_id"]
    )
    op.create_index(
        "ix_revision_references_target_object", "revision_references", ["target_object_id"]
    )


def downgrade() -> None:
    for name in (
        "ix_revision_references_target_object",
        "ix_revision_references_target_asset",
        "ix_revision_references_target_representation",
        "ix_revision_references_target_revision",
        "ix_revision_references_source_claim",
        "ix_revision_references_source_view",
    ):
        op.drop_index(name, table_name="revision_references")
    op.drop_table("revision_references")
