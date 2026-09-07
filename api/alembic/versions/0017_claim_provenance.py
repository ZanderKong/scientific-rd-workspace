"""Separate Claim author provenance from pinned scientific source."""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "0017_claim_provenance"
down_revision: str | Sequence[str] | None = "0016_view_source_manifest"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    uuid_type = postgresql.UUID(as_uuid=True)
    json_type = postgresql.JSONB(astext_type=sa.Text())
    op.drop_column("claim_records", "source_ref")
    op.drop_column("claim_records", "source_type")
    op.add_column(
        "claim_records",
        sa.Column(
            "author_provenance_jsonb",
            json_type,
            server_default="{}",
            nullable=False,
        ),
    )
    op.add_column("claim_records", sa.Column("primary_source_kind", sa.String(32), nullable=False))
    op.add_column("claim_records", sa.Column("primary_source_id", uuid_type, nullable=False))
    op.add_column(
        "claim_records", sa.Column("primary_source_revision_id", uuid_type, nullable=False)
    )
    op.add_column(
        "claim_records",
        sa.Column("context_snapshot_jsonb", json_type, server_default="{}", nullable=False),
    )
    op.create_check_constraint(
        "ck_claim_primary_source_kind",
        "claim_records",
        "primary_source_kind in ('experiment','data','view')",
    )
    op.create_foreign_key(
        "fk_claim_records_primary_source",
        "claim_records",
        "research_objects",
        ["primary_source_id"],
        ["id"],
        ondelete="RESTRICT",
    )
    op.create_index("ix_claim_records_primary_source_id", "claim_records", ["primary_source_id"])
    op.create_index(
        "ix_claim_records_primary_source_revision_id",
        "claim_records",
        ["primary_source_revision_id"],
    )
    op.create_table(
        "claim_context_references",
        sa.Column("id", uuid_type, primary_key=True),
        sa.Column("claim_id", uuid_type, nullable=False),
        sa.Column("reference_kind", sa.String(16), nullable=False),
        sa.Column("object_id", uuid_type, nullable=False),
        sa.Column("revision_id", uuid_type, nullable=True),
        sa.CheckConstraint(
            "reference_kind in ('primary','context')",
            name="ck_claim_context_reference_kind",
        ),
        sa.ForeignKeyConstraint(["claim_id"], ["claim_records.claim_id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["object_id"], ["research_objects.id"], ondelete="RESTRICT"),
        sa.UniqueConstraint(
            "claim_id", "reference_kind", "object_id", name="uq_claim_context_reference"
        ),
    )
    op.create_index(
        "ix_claim_context_references_claim_id", "claim_context_references", ["claim_id"]
    )
    op.create_index(
        "ix_claim_context_references_object_id", "claim_context_references", ["object_id"]
    )
    op.create_index(
        "ix_claim_context_references_revision_id", "claim_context_references", ["revision_id"]
    )


def downgrade() -> None:
    op.drop_index("ix_claim_context_references_revision_id", table_name="claim_context_references")
    op.drop_index("ix_claim_context_references_object_id", table_name="claim_context_references")
    op.drop_index("ix_claim_context_references_claim_id", table_name="claim_context_references")
    op.drop_table("claim_context_references")
    op.drop_index("ix_claim_records_primary_source_revision_id", table_name="claim_records")
    op.drop_index("ix_claim_records_primary_source_id", table_name="claim_records")
    op.drop_constraint("fk_claim_records_primary_source", "claim_records", type_="foreignkey")
    op.drop_constraint("ck_claim_primary_source_kind", "claim_records", type_="check")
    op.drop_column("claim_records", "context_snapshot_jsonb")
    op.drop_column("claim_records", "primary_source_revision_id")
    op.drop_column("claim_records", "primary_source_id")
    op.drop_column("claim_records", "primary_source_kind")
    op.drop_column("claim_records", "author_provenance_jsonb")
    op.add_column(
        "claim_records",
        sa.Column("source_type", sa.String(32), server_default="human", nullable=False),
    )
    op.add_column("claim_records", sa.Column("source_ref", sa.String(500), nullable=True))
