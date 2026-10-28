from __future__ import annotations

import os
import uuid
from collections.abc import Iterator
from datetime import UTC, datetime

import pytest
from sqlalchemy import create_engine, text

from clauselens.adapters.persistence.models import Base
from clauselens.adapters.persistence.sqlalchemy_repository import SqlAlchemyRepository, create_db_engine
from clauselens.config import Settings
from clauselens.domain.models import RetrievedSource
from clauselens.observability import metrics

TEST_DATABASE_URL = os.environ.get(
    "TEST_DATABASE_URL", "postgresql+psycopg://clauselens:clauselens@localhost:5432/clauselens_test")


def make_settings(**overrides: object) -> Settings:
    base: dict[str, object] = {
        "environment": "test",
        "web_research_provider": "fixture",
        "llm_provider": "fixture",
        "job_queue_provider": "sync",
        "storage_provider": "none",
        "database_url": "sqlite:///:memory:",
        "log_json": False,
        "_env_file": None,
    }
    base.update(overrides)
    return Settings(**base)  # type: ignore[arg-type]


@pytest.fixture
def settings(tmp_path) -> Settings:
    return make_settings(database_url=f"sqlite:///{tmp_path / 'test.db'}")


@pytest.fixture
def sqlite_repo(settings: Settings) -> SqlAlchemyRepository:
    engine = create_db_engine(settings)
    Base.metadata.create_all(engine)
    return SqlAlchemyRepository(engine)


def postgres_available() -> bool:
    try:
        engine = create_engine(TEST_DATABASE_URL, connect_args={"connect_timeout": 2})
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
        engine.dispose()
        return True
    except Exception:
        return False


@pytest.fixture
def postgres_repo() -> Iterator[SqlAlchemyRepository]:
    if not postgres_available():
        pytest.skip("PostgreSQL not reachable at TEST_DATABASE_URL")
    engine = create_engine(TEST_DATABASE_URL)
    with engine.begin() as conn:
        conn.execute(text("DROP SCHEMA public CASCADE; CREATE SCHEMA public;"))
    from alembic import command
    from alembic.config import Config

    cfg = Config(os.path.join(os.path.dirname(__file__), "..", "alembic.ini"))
    cfg.set_main_option("script_location", os.path.join(os.path.dirname(__file__), "..", "alembic"))
    cfg.attributes["database_url"] = TEST_DATABASE_URL
    command.upgrade(cfg, "head")
    yield SqlAlchemyRepository(engine)
    engine.dispose()


@pytest.fixture(params=["sqlite", "postgres"])
def repo(request) -> SqlAlchemyRepository:  # type: ignore[no-untyped-def]
    return request.getfixturevalue(f"{request.param}_repo")


@pytest.fixture(autouse=True)
def _reset_metrics() -> None:
    metrics.reset()


def source(key: str, content: str, url: str | None = None) -> RetrievedSource:
    import hashlib

    return RetrievedSource(
        source_key=key, url=url or f"https://vendor.example/{key.lower()}", final_url=None, title=f"Page {key}",
        content=content, content_hash=hashlib.sha256((key + content).encode()).hexdigest(),
        retrieved_at=datetime(2026, 10, 1, tzinfo=UTC), provider="test",
    )


def new_id() -> uuid.UUID:
    return uuid.uuid4()
