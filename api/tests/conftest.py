from __future__ import annotations

import os
from collections.abc import Generator
from urllib.parse import urlsplit

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, text
from sqlalchemy.orm import Session, sessionmaker

from app.core.config import get_settings
from app.db import Base, get_db
from app.main import app


def _test_database_url() -> str:
    url = os.getenv("TEST_DATABASE_URL")
    if not url:
        pytest.fail("set TEST_DATABASE_URL to an isolated PostgreSQL test database")
    if not url.startswith(("postgresql://", "postgresql+psycopg://")):
        pytest.fail("v0.3 backend tests require a PostgreSQL TEST_DATABASE_URL")
    configured = get_settings().database_url
    test_parts = urlsplit(url)
    configured_parts = urlsplit(configured)
    database_name = test_parts.path.lstrip("/").lower()
    database_tokens = set(database_name.replace("-", "_").split("_"))
    if not database_name or not database_tokens.intersection({"test", "ci", "pytest"}):
        pytest.fail("TEST_DATABASE_URL must point to a database named for tests")
    if (
        test_parts.hostname == configured_parts.hostname
        and test_parts.port == configured_parts.port
        and database_name == configured_parts.path.lstrip("/").lower()
    ):
        pytest.fail("TEST_DATABASE_URL must not equal the application DATABASE_URL")
    return url


@pytest.fixture
def db() -> Generator[Session, None, None]:
    engine = create_engine(_test_database_url(), pool_pre_ping=True)
    with engine.begin() as connection:
        connection.execute(text("DROP SCHEMA IF EXISTS public CASCADE"))
        connection.execute(text("CREATE SCHEMA public"))
        connection.execute(text("CREATE EXTENSION IF NOT EXISTS pg_trgm"))
    Base.metadata.create_all(engine)
    session = sessionmaker(bind=engine, expire_on_commit=False)()
    try:
        yield session
    finally:
        session.close()
        with engine.begin() as connection:
            connection.execute(text("DROP SCHEMA IF EXISTS public CASCADE"))
        engine.dispose()


@pytest.fixture(autouse=True)
def override_db(db: Session) -> Generator[None, None, None]:
    app.dependency_overrides[get_db] = lambda: db
    yield
    app.dependency_overrides.clear()


@pytest.fixture
def client() -> TestClient:
    return TestClient(app)
