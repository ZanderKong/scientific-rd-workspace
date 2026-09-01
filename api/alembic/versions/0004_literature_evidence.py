"""Add literature links and immutable human-authored evidence.

Revision ID: 0004_literature_evidence
Revises: 0003_scientific_measurements
"""

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision = "0004_literature_evidence"
down_revision = "0003_scientific_measurements"
branch_labels = None
depends_on = None

json_type = sa.JSON().with_variant(postgresql.JSONB(), "postgresql")
uuid_type = sa.Uuid()


def upgrade() -> None:
    op.create_table(
        "literature_records",
        sa.Column("id", uuid_type, nullable=False),
        sa.Column("project_id", uuid_type, nullable=False),
        sa.Column("item_type", sa.String(length=64), nullable=False),
        sa.Column("title", sa.String(length=500), nullable=False),
        sa.Column("authors_json", json_type, nullable=False),
        sa.Column("publication_year", sa.Integer(), nullable=True),
        sa.Column("container_title", sa.String(length=500), nullable=True),
        sa.Column("doi", sa.String(length=255), nullable=True),
        sa.Column("url", sa.String(length=2000), nullable=True),
        sa.Column("abstract", sa.Text(), nullable=True),
        sa.Column("provider", sa.String(length=64), nullable=True),
        sa.Column("external_id", sa.String(length=255), nullable=True),
        sa.Column("provider_version", sa.String(length=64), nullable=True),
        sa.Column("raw_provider_json", json_type, nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["project_id"], ["projects.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_literature_records_project_id", "literature_records", ["project_id"])
    op.create_index(
        "uq_literature_provider_external",
        "literature_records",
        ["project_id", "provider", "external_id"],
        unique=True,
        postgresql_where=sa.text("provider is not null and external_id is not null"),
    )

    op.create_table(
        "experiment_literature_links",
        sa.Column("id", uuid_type, nullable=False),
        sa.Column("experiment_id", uuid_type, nullable=False),
        sa.Column("literature_id", uuid_type, nullable=False),
        sa.Column("relationship_type", sa.String(length=32), nullable=False),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["experiment_id"], ["experiments.id"]),
        sa.ForeignKeyConstraint(["literature_id"], ["literature_records.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("experiment_id", "literature_id", name="uq_experiment_literature_links_pair"),
    )
    op.create_index("ix_experiment_literature_links_experiment_id", "experiment_literature_links", ["experiment_id"])
    op.create_index("ix_experiment_literature_links_literature_id", "experiment_literature_links", ["literature_id"])

    op.create_table(
        "evidence_records",
        sa.Column("id", uuid_type, nullable=False),
        sa.Column("project_id", uuid_type, nullable=False),
        sa.Column("context_experiment_id", uuid_type, nullable=True),
        sa.Column("claim_text", sa.Text(), nullable=False),
        sa.Column("stance", sa.String(length=32), nullable=False),
        sa.Column("source_type", sa.String(length=32), nullable=False),
        sa.Column("literature_id", uuid_type, nullable=True),
        sa.Column("measurement_id", uuid_type, nullable=True),
        sa.Column("experiment_revision_id", uuid_type, nullable=True),
        sa.Column("locator", sa.String(length=500), nullable=True),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("source_snapshot_json", json_type, nullable=False),
        sa.Column("status", sa.String(length=16), nullable=False, server_default="active"),
        sa.Column("withdrawal_reason", sa.String(length=1000), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("withdrawn_at", sa.DateTime(timezone=True), nullable=True),
        sa.CheckConstraint("source_type in ('literature', 'measurement', 'experiment_revision')", name="ck_evidence_source_type"),
        sa.CheckConstraint("stance in ('supports', 'contradicts', 'context')", name="ck_evidence_stance"),
        sa.CheckConstraint("status in ('active', 'withdrawn')", name="ck_evidence_status"),
        sa.CheckConstraint(
            "(CASE WHEN literature_id IS NOT NULL THEN 1 ELSE 0 END + "
            "CASE WHEN measurement_id IS NOT NULL THEN 1 ELSE 0 END + "
            "CASE WHEN experiment_revision_id IS NOT NULL THEN 1 ELSE 0 END) = 1",
            name="ck_evidence_exactly_one_source",
        ),
        sa.ForeignKeyConstraint(["project_id"], ["projects.id"]),
        sa.ForeignKeyConstraint(["context_experiment_id"], ["experiments.id"]),
        sa.ForeignKeyConstraint(["literature_id"], ["literature_records.id"]),
        sa.ForeignKeyConstraint(["measurement_id"], ["measurements.id"]),
        sa.ForeignKeyConstraint(["experiment_revision_id"], ["experiment_revisions.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_evidence_records_project_id", "evidence_records", ["project_id"])
    op.create_index("ix_evidence_records_context_experiment_id", "evidence_records", ["context_experiment_id"])


def downgrade() -> None:
    op.drop_index("ix_evidence_records_context_experiment_id", table_name="evidence_records")
    op.drop_index("ix_evidence_records_project_id", table_name="evidence_records")
    op.drop_table("evidence_records")
    op.drop_index("ix_experiment_literature_links_literature_id", table_name="experiment_literature_links")
    op.drop_index("ix_experiment_literature_links_experiment_id", table_name="experiment_literature_links")
    op.drop_table("experiment_literature_links")
    op.drop_index("uq_literature_provider_external", table_name="literature_records")
    op.drop_index("ix_literature_records_project_id", table_name="literature_records")
    op.drop_table("literature_records")
