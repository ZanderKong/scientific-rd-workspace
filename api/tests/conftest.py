from __future__ import annotations

import os
from collections.abc import Generator

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from app.core.config import get_settings
from app.db import Base, get_db
from app.main import app


def _test_database_url() -> str:
    url = os.getenv("TEST_DATABASE_URL") or get_settings().database_url
    if not url.startswith(("postgresql://", "postgresql+psycopg://")):
        pytest.fail("v0.2 backend tests require a PostgreSQL TEST_DATABASE_URL")
    return url


@pytest.fixture
def db() -> Generator[Session, None, None]:
    engine = create_engine(_test_database_url(), pool_pre_ping=True)
    Base.metadata.drop_all(engine)
    Base.metadata.create_all(engine)
    session = sessionmaker(bind=engine, expire_on_commit=False)()
    try:
        yield session
    finally:
        session.close()
        Base.metadata.drop_all(engine)
        engine.dispose()


@pytest.fixture(autouse=True)
def override_db(db: Session) -> Generator[None, None, None]:
    app.dependency_overrides[get_db] = lambda: db
    yield
    app.dependency_overrides.clear()
