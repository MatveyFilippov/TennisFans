import os
from pathlib import Path
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient
from pydantic import SecretStr
from sqlalchemy import text
from sqlalchemy.engine import make_url

from tennisfans.core.config import Settings
from tennisfans.db.base import Base
from tennisfans.db.runtime import engine_for, lock
from tennisfans.domain.permissions import Role
from tennisfans.main import create_app
from tennisfans.modules.auth import create_user

PASSWORD = "durable sample password"  # noqa: S105 - isolated test credential
ORIGIN = "http://localhost:5173"


@pytest.fixture
def settings(tmp_path: Path) -> Settings:
    url = os.environ.get("TENNISFANS_TEST_DATABASE_URL")
    if not url:
        pytest.skip("Set TENNISFANS_TEST_DATABASE_URL for PostgreSQL tests")
    if not (make_url(url).database or "").endswith("_test"):
        pytest.fail("Integration tests require a dedicated database with a name ending in _test")
    return Settings(
        database_url=SecretStr(url),
        session_secret=SecretStr(uuid4().hex),
        environment="test",
        media_root=tmp_path / "media",
        upload_bytes=4096,
        upload_request_bytes=8192,
        reconcile_seconds=60,
    )


@pytest.fixture
def clean_schema(settings: Settings) -> None:
    engine = engine_for(settings)
    with engine.begin() as conn:
        # This fixture only runs against the purpose-built, suffix-checked test DB.
        conn.execute(text("DROP SCHEMA public CASCADE"))
        conn.execute(text("CREATE SCHEMA public"))
    engine.dispose()


@pytest.fixture
def app(settings: Settings, clean_schema: None) -> TestClient:
    service = create_app(settings)
    with TestClient(service, headers={"Origin": ORIGIN}) as client:
        with service.state.runtime.db.begin() as db:
            lock(db)
            create_user(db, "admin", PASSWORD, "Administrator", Role.ADMIN)
        yield client


def count_tables(settings: Settings) -> int:
    return len(Base.metadata.tables) + 1
