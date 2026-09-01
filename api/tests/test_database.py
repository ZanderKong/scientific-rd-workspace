import os


def test_ci_database_is_real_postgresql_when_configured(db) -> None:
    if os.getenv("TEST_DATABASE_URL"):
        assert db.get_bind().dialect.name == "postgresql"
