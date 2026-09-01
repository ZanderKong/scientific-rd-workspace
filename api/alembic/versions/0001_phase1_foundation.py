"""Create Phase 1 foundation tables.

Revision ID: 0001_phase1_foundation
Revises:
Create Date: 2026-09-01
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "0001_phase1_foundation"
down_revision = None
branch_labels = None
depends_on = None

json_type = sa.JSON().with_variant(postgresql.JSONB(), "postgresql")
uuid_type = sa.Uuid()


def upgrade() -> None:
    op.create_table(
        "projects",
        sa.Column("id", uuid_type, nullable=False),
        sa.Column("code", sa.String(length=32), nullable=False),
        sa.Column("title", sa.String(length=240), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("code"),
    )
    op.create_index("ix_projects_code", "projects", ["code"], unique=False)

    op.create_table(
        "experiment_templates",
        sa.Column("id", uuid_type, nullable=False),
        sa.Column("key", sa.String(length=120), nullable=False),
        sa.Column("name", sa.String(length=240), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("json_schema", json_type, nullable=False),
        sa.Column("ui_schema", json_type, nullable=True),
        sa.Column("is_active", sa.Boolean(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("key"),
    )
    op.create_index("ix_experiment_templates_key", "experiment_templates", ["key"], unique=False)

    op.create_table(
        "experiments",
        sa.Column("id", uuid_type, nullable=False),
        sa.Column("code", sa.String(length=32), nullable=False),
        sa.Column("project_id", uuid_type, nullable=False),
        sa.Column("template_id", uuid_type, nullable=False),
        sa.Column("template_version", sa.Integer(), nullable=False),
        sa.Column("parent_experiment_id", uuid_type, nullable=True),
        sa.Column("title", sa.String(length=240), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("objective", sa.Text(), nullable=True),
        sa.Column("structured_data", json_type, nullable=False),
        sa.Column("note_document", json_type, nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["parent_experiment_id"], ["experiments.id"]),
        sa.ForeignKeyConstraint(["project_id"], ["projects.id"]),
        sa.ForeignKeyConstraint(["template_id"], ["experiment_templates.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("code"),
    )
    op.create_index("ix_experiments_code", "experiments", ["code"], unique=False)
    op.create_index("ix_experiments_project_id", "experiments", ["project_id"], unique=False)
    op.create_index("ix_experiments_parent_experiment_id", "experiments", ["parent_experiment_id"], unique=False)

    op.create_table(
        "attachments",
        sa.Column("id", uuid_type, nullable=False),
        sa.Column("experiment_id", uuid_type, nullable=False),
        sa.Column("original_filename", sa.String(length=255), nullable=False),
        sa.Column("storage_key", sa.String(length=512), nullable=False),
        sa.Column("content_type", sa.String(length=160), nullable=True),
        sa.Column("size_bytes", sa.Integer(), nullable=False),
        sa.Column("sha256", sa.String(length=64), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["experiment_id"], ["experiments.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("storage_key"),
    )
    op.create_index("ix_attachments_experiment_id", "attachments", ["experiment_id"], unique=False)

    op.create_table(
        "experiment_revisions",
        sa.Column("id", uuid_type, nullable=False),
        sa.Column("experiment_id", uuid_type, nullable=False),
        sa.Column("revision_number", sa.Integer(), nullable=False),
        sa.Column("snapshot_json", json_type, nullable=False),
        sa.Column("change_note", sa.String(length=500), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["experiment_id"], ["experiments.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("experiment_id", "revision_number"),
    )
    op.create_index("ix_experiment_revisions_experiment_id", "experiment_revisions", ["experiment_id"], unique=False)


def downgrade() -> None:
    op.drop_index("ix_experiment_revisions_experiment_id", table_name="experiment_revisions")
    op.drop_table("experiment_revisions")
    op.drop_index("ix_attachments_experiment_id", table_name="attachments")
    op.drop_table("attachments")
    op.drop_index("ix_experiments_parent_experiment_id", table_name="experiments")
    op.drop_index("ix_experiments_project_id", table_name="experiments")
    op.drop_index("ix_experiments_code", table_name="experiments")
    op.drop_table("experiments")
    op.drop_index("ix_experiment_templates_key", table_name="experiment_templates")
    op.drop_table("experiment_templates")
    op.drop_index("ix_projects_code", table_name="projects")
    op.drop_table("projects")
