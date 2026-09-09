"""Backfill explicit roles for resources created before the role field existed."""

from collections.abc import Sequence

from alembic import op

revision: str = "0026_backfill_resource_roles"
down_revision: str | Sequence[str] | None = "0025_optional_claim_source"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.execute(
        "UPDATE research_objects SET resource_role = 'process' "
        "WHERE kind = 'process_definition' AND resource_role IS NULL"
    )
    op.execute(
        "UPDATE research_objects SET resource_role = 'equipment' "
        "WHERE kind = 'research_object' AND resource_role IS NULL AND tags_jsonb ? '设备'"
    )
    op.execute(
        "UPDATE research_objects SET resource_role = 'material' "
        "WHERE kind = 'research_object' AND resource_role IS NULL AND authoring_kind IS NULL"
    )


def downgrade() -> None:
    op.execute(
        "UPDATE research_objects SET resource_role = NULL "
        "WHERE kind = 'research_object' AND tags_jsonb ?| ARRAY['设备','原料']"
    )
