"""Do not infer a material role for unclassified legacy objects."""

from collections.abc import Sequence

from alembic import op

revision: str = "0027_clear_unclassified_roles"
down_revision: str | Sequence[str] | None = "0026_backfill_resource_roles"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.execute(
        "UPDATE research_objects SET resource_role = NULL "
        "WHERE kind = 'research_object' AND authoring_kind IS NULL "
        "AND resource_role = 'material' "
        "AND NOT (tags_jsonb ? '原料' OR tags_jsonb ? 'material' "
        "OR tags_jsonb ? '设备' OR tags_jsonb ? 'equipment')"
    )


def downgrade() -> None:
    op.execute(
        "UPDATE research_objects SET resource_role = 'material' "
        "WHERE kind = 'research_object' AND authoring_kind IS NULL "
        "AND resource_role IS NULL"
    )
