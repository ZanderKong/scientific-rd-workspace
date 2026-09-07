"""Pin View representations and artifact assets."""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "0016_view_source_manifest"
down_revision: str | Sequence[str] | None = "0015_data_drafts"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    uuid_type = postgresql.UUID(as_uuid=True)
    json_type = postgresql.JSONB(astext_type=sa.Text())
    op.drop_constraint("view_data_refs_data_revision_id_fkey", "view_data_refs", type_="foreignkey")
    op.create_foreign_key(
        "fk_view_data_refs_revision",
        "view_data_refs",
        "object_revisions",
        ["data_revision_id"],
        ["id"],
        ondelete="RESTRICT",
    )
    op.alter_column("view_data_refs", "data_revision_id", nullable=False)
    op.add_column(
        "view_data_refs",
        sa.Column("representation_ids_jsonb", json_type, server_default="[]", nullable=False),
    )
    op.add_column("view_states", sa.Column("artifact_asset_id", uuid_type, nullable=True))
    op.add_column("view_states", sa.Column("artifact_sha256", sa.String(64), nullable=True))
    op.create_foreign_key(
        "fk_view_states_artifact_asset",
        "view_states",
        "assets",
        ["artifact_asset_id"],
        ["id"],
        ondelete="RESTRICT",
    )
    op.create_index("ix_view_states_artifact_asset_id", "view_states", ["artifact_asset_id"])


def downgrade() -> None:
    op.drop_index("ix_view_states_artifact_asset_id", table_name="view_states")
    op.drop_constraint("fk_view_states_artifact_asset", "view_states", type_="foreignkey")
    op.drop_column("view_states", "artifact_sha256")
    op.drop_column("view_states", "artifact_asset_id")
    op.drop_column("view_data_refs", "representation_ids_jsonb")
    op.alter_column("view_data_refs", "data_revision_id", nullable=True)
    op.drop_constraint("fk_view_data_refs_revision", "view_data_refs", type_="foreignkey")
    op.create_foreign_key(
        "view_data_refs_data_revision_id_fkey",
        "view_data_refs",
        "object_revisions",
        ["data_revision_id"],
        ["id"],
        ondelete="SET NULL",
    )
