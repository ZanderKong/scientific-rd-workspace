"""Bootstrap the local development database.

The production/default database remains PostgreSQL. This module is used by
``scripts/start-local.sh`` when Docker/PostgreSQL is not available; Alembic
still creates the schema, and the normal demo seed is applied afterwards.
"""

from alembic import command
from alembic.config import Config

from app.core.config import get_settings
from app.seed import seed


def upgrade_schema() -> None:
    settings = get_settings()
    config = Config("alembic.ini")
    config.set_main_option("sqlalchemy.url", settings.database_url.replace("%", "%%"))
    command.upgrade(config, "head")


def main() -> None:
    upgrade_schema()
    seed()


if __name__ == "__main__":
    main()
